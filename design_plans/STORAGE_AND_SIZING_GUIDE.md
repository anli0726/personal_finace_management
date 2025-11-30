# Storage and Sizing Guide: 3-Year Statement Import

This guide covers storage estimation, schema design, ingestion strategies, and operational best practices for storing up to 3 years of bank statement data (transactions + attachments).

---

## Table of Contents

1. [Size Estimates](#size-estimates)
2. [Storage Architecture](#storage-architecture)
3. [Database Schema](#database-schema)
4. [Deduplication Strategy](#deduplication-strategy)
5. [Ingestion & Query Examples](#ingestion--query-examples)
6. [Retention, Compression & Backups](#retention-compression--backups)
7. [Security & Access Control](#security--access-control)
8. [Performance Tips](#performance-tips)
9. [Implementation Checklist](#implementation-checklist)

---

## Size Estimates

### Assumptions

- **Time window:** 36 months (3 years)
- **Per-transaction record:** ~500 bytes (JSON + metadata)
- **CSV statement per month:** ~30 KB average
- **PDF statement per month:** ~200 KB average (varies by bank: 50–400 KB)
- **Database overhead:** ~20% (indexes, page allocation)

### Three Scenarios

#### Scenario A: Low Activity (Light User)

| Item | Value |
|------|-------|
| Accounts | 5 |
| Transactions/month/account | 50 |
| Total transactions | 9,000 |
| Parsed storage (DB) | ~4.5 MB |
| CSV exports | ~5.4 MB |
| PDF statements | ~36 MB |
| DB + overhead | ~5.4 MB |
| **Total** | **~47.8 MB** |
| **Recommended disk allocation** | **100 MB** |

#### Scenario B: Medium Activity (Typical User)

| Item | Value |
|------|-------|
| Accounts | 10 |
| Transactions/month/account | 150 |
| Total transactions | 54,000 |
| Parsed storage (DB) | ~27 MB |
| CSV exports | ~10.8 MB |
| PDF statements | ~72 MB |
| DB + overhead | ~32.4 MB |
| **Total** | **~115.2 MB** |
| **Recommended disk allocation** | **200–300 MB** |

#### Scenario C: High Activity (Active User)

| Item | Value |
|------|-------|
| Accounts | 20 |
| Transactions/month/account | 300 |
| Total transactions | 216,000 |
| Parsed storage (DB) | ~108 MB |
| CSV exports | ~21.6 MB |
| PDF statements | ~144 MB |
| DB + overhead | ~129.6 MB |
| **Total** | **~295.2 MB** |
| **Recommended disk allocation** | **500 MB – 1 GB** |

### Calculation Formulas

```
total_transactions = accounts × transactions_per_month × 36

parsed_storage ≈ total_transactions × 500 bytes

raw_csv_storage ≈ accounts × 36 × 30 KB

pdf_storage ≈ accounts × 36 × 200 KB

final_total ≈ (parsed_storage × 1.2) + raw_csv_storage + pdf_storage
```

### Key Insights

- **PDFs dominate storage:** If you keep full attachments, PDFs account for ~70% of total size.
- **CSV-only option:** Storing only parsed DB + CSVs (no PDFs) reduces total by ~60%, fitting in <100 MB even for high activity.
- **Long-term growth:** 3 years is small; even aggressive users fit comfortably under 1 GB without compression.
- **Compression wins:** Gzipping CSVs/PDFs can reduce storage by 30–60%.

---

## Storage Architecture

### Filesystem Layout

Organize statement data under `user_data/` as follows:

```
user_data/
├── ledger/
│   └── transactions.sqlite          # Primary SQLite database
├── statements/
│   ├── imports/                     # Import metadata
│   │   ├── import-2025-01-chase.json
│   │   ├── import-2025-02-chase.json
│   │   └── ...
│   ├── attachments/                 # Raw statements (PDF, CSV)
│   │   ├── import-2025-01-chase__checking_statement.csv
│   │   ├── import-2025-01-chase__checking_statement.pdf
│   │   └── ...
│   └── transactions/                # Optional per-import archives (JSON)
│       ├── import-2025-01-chase.json
│       └── ...
├── backups/
│   ├── transactions.sqlite.2025-11-29
│   ├── statements-2025-11.tar.gz    # Compressed attachments + metadata
│   └── ...
└── .gitignore                       # Ensures ledger data not committed
```

### Why SQLite?

✅ **Single-file database** – Zero configuration, easy to backup  
✅ **Performance** – Fast queries with indexes on typical personal data volumes  
✅ **Python integration** – Built-in `sqlite3` library; integrates with Pandas  
✅ **Transaction support** – ACID compliance prevents data loss  
✅ **No server needed** – Lightweight for single-user desktop app  
✅ **Easy scaling** – Handles millions of rows before needing migration  

---

## Database Schema

### Table: `imports`

Tracks each import batch (email, CSV file, API sync).

```sql
CREATE TABLE IF NOT EXISTS imports (
  import_id TEXT PRIMARY KEY,
  account_name TEXT NOT NULL,
  source TEXT NOT NULL,           -- 'email', 'csv', 'plaid', 'manual'
  filename TEXT,
  file_hash TEXT,                 -- SHA256 of file (detect re-imports)
  imported_at TIMESTAMP,
  rows_expected INTEGER,          -- Expected rows in file
  rows_parsed INTEGER,            -- Actually inserted
  rows_duplicate INTEGER DEFAULT 0,
  rows_error INTEGER DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_import_file_hash ON imports(file_hash);
```

**Example row:**
```json
{
  "import_id": "import-2025-01-chase-20251130",
  "account_name": "Chase Checking",
  "source": "csv",
  "filename": "checking_jan_2025.csv",
  "file_hash": "a3f9e...",
  "imported_at": "2025-11-30T10:30:00",
  "rows_expected": 47,
  "rows_parsed": 47,
  "rows_duplicate": 0,
  "rows_error": 0
}
```

### Table: `attachments`

Links raw files to imports (track storage location).

```sql
CREATE TABLE IF NOT EXISTS attachments (
  attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id TEXT NOT NULL REFERENCES imports(import_id),
  path TEXT NOT NULL,             -- Relative path within user_data/
  filename TEXT,
  size INTEGER,                   -- File size in bytes
  mime_type TEXT,                 -- 'text/csv', 'application/pdf', etc.
  created_at TIMESTAMP
);

CREATE INDEX idx_attachment_import ON attachments(import_id);
```

**Example row:**
```json
{
  "attachment_id": 1,
  "import_id": "import-2025-01-chase-20251130",
  "path": "statements/attachments/import-2025-01-chase__checking_jan_2025.csv",
  "filename": "checking_jan_2025.csv",
  "size": 47823,
  "mime_type": "text/csv"
}
```

### Table: `transactions`

Core transaction ledger (deduplicated).

```sql
CREATE TABLE IF NOT EXISTS transactions (
  txn_id TEXT PRIMARY KEY,           -- SHA256 hash for deduplication
  import_id TEXT REFERENCES imports(import_id),
  date TEXT NOT NULL,                -- YYYY-MM-DD
  amount REAL NOT NULL,              -- Positive = income, negative = expense
  description TEXT,
  merchant TEXT,                     -- Parsed merchant name (optional)
  category TEXT,                     -- 'groceries', 'salary', 'utilities', etc.
  account TEXT NOT NULL,             -- 'Checking', 'Credit Card', etc.
  currency TEXT DEFAULT 'USD',
  is_income INTEGER,                 -- 0 = expense, 1 = income, NULL = auto-detect
  confidence REAL,                   -- 0.0-1.0 categorizer confidence
  reconciled INTEGER DEFAULT 0,      -- 0 = unreviewed, 1 = user confirmed
  raw_json TEXT,                     -- Original parsed row (traceability)
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_txn_date ON transactions(date);
CREATE INDEX idx_txn_account ON transactions(account);
CREATE INDEX idx_txn_category ON transactions(category);
CREATE INDEX idx_txn_import ON transactions(import_id);
CREATE INDEX idx_txn_is_income ON transactions(is_income);
CREATE INDEX idx_txn_reconciled ON transactions(reconciled);
```

**Example row:**
```json
{
  "txn_id": "3a7f9e1c2b...",
  "import_id": "import-2025-01-chase-20251130",
  "date": "2025-01-15",
  "amount": -50.25,
  "description": "SAFEWAY STORE #2049",
  "merchant": "Safeway",
  "category": "groceries",
  "account": "Chase Checking",
  "currency": "USD",
  "is_income": 0,
  "confidence": 0.95,
  "reconciled": 1,
  "raw_json": "{\"Date\":\"01/15/2025\",\"Description\":\"SAFEWAY STORE #2049\",\"Amount\":-50.25,...}"
}
```

### Table: `monthly_aggregates` (Optional, Materialized)

Pre-computed monthly summaries for analyzer performance.

```sql
CREATE TABLE IF NOT EXISTS monthly_aggregates (
  agg_id INTEGER PRIMARY KEY AUTOINCREMENT,
  year_month TEXT NOT NULL,          -- 'YYYY-MM'
  account TEXT,
  category TEXT,
  total_amount REAL,
  transaction_count INTEGER,
  is_income INTEGER,
  computed_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_agg_ym_acct_cat ON monthly_aggregates(year_month, account, category);
```

**Example row:**
```json
{
  "year_month": "2025-01",
  "account": "Chase Checking",
  "category": "groceries",
  "total_amount": -520.00,
  "transaction_count": 12,
  "is_income": 0
}
```

### Complete Schema Creation Script

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS imports (
  import_id TEXT PRIMARY KEY,
  account_name TEXT NOT NULL,
  source TEXT NOT NULL,
  filename TEXT,
  file_hash TEXT UNIQUE,
  imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  rows_expected INTEGER,
  rows_parsed INTEGER DEFAULT 0,
  rows_duplicate INTEGER DEFAULT 0,
  rows_error INTEGER DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attachments (
  attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id TEXT NOT NULL REFERENCES imports(import_id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  filename TEXT,
  size INTEGER,
  mime_type TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_attachment_import ON attachments(import_id);

CREATE TABLE IF NOT EXISTS transactions (
  txn_id TEXT PRIMARY KEY,
  import_id TEXT REFERENCES imports(import_id) ON DELETE SET NULL,
  date TEXT NOT NULL,
  amount REAL NOT NULL,
  description TEXT,
  merchant TEXT,
  category TEXT,
  account TEXT NOT NULL,
  currency TEXT DEFAULT 'USD',
  is_income INTEGER,
  confidence REAL,
  reconciled INTEGER DEFAULT 0,
  raw_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_txn_date ON transactions(date);
CREATE INDEX idx_txn_account ON transactions(account);
CREATE INDEX idx_txn_category ON transactions(category);
CREATE INDEX idx_txn_import ON transactions(import_id);
CREATE INDEX idx_txn_is_income ON transactions(is_income);
CREATE INDEX idx_txn_reconciled ON transactions(reconciled);

CREATE TABLE IF NOT EXISTS monthly_aggregates (
  agg_id INTEGER PRIMARY KEY AUTOINCREMENT,
  year_month TEXT NOT NULL,
  account TEXT,
  category TEXT,
  total_amount REAL,
  transaction_count INTEGER,
  is_income INTEGER,
  computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(year_month, account, category)
);
```

---

## Deduplication Strategy

Deduplication prevents duplicate transactions when the same file is imported multiple times or when records overlap across imports.

### Hash-Based Deduplication

Compute a canonical hash from immutable transaction fields:

```python
import hashlib

def transaction_hash(date: str, amount: float, description: str, account: str) -> str:
    """
    Generate unique hash for a transaction.
    
    Args:
        date: YYYY-MM-DD format
        amount: numeric value (e.g., -50.25)
        description: transaction description
        account: account name
    
    Returns:
        SHA256 hex digest (used as txn_id)
    """
    canonical = f"{date}|{amount:.2f}|{description.strip().lower()}|{account.lower()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### File Deduplication

Prevent re-importing the same file by computing file hash:

```python
def file_hash(filepath: str) -> str:
    """Compute SHA256 of file contents."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### Insert Logic

```python
import sqlite3

def insert_transaction_dedup(
    cur: sqlite3.Cursor,
    txn_id: str,
    import_id: str,
    date: str,
    amount: float,
    description: str,
    category: str,
    account: str,
    **kwargs
):
    """Insert transaction; skip if txn_id already exists."""
    try:
        cur.execute("""
            INSERT INTO transactions (
                txn_id, import_id, date, amount, description,
                category, account, created_at, updated_at, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """, (
            txn_id, import_id, date, amount, description,
            category, account, kwargs.get("raw_json", "{}")
        ))
        return True  # inserted
    except sqlite3.IntegrityError:
        # Duplicate key
        return False
```

---

## Ingestion & Query Examples

### Python: CSV Import with Deduplication

```python
import sqlite3
import csv
import json
import hashlib
import datetime
import os
import uuid

DB_PATH = "user_data/ledger/transactions.sqlite"

def ensure_db():
    """Create DB and tables if not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Run schema creation
    with open("backend/statements/schema.sql") as f:
        cur.executescript(f.read())
    
    conn.commit()
    conn.close()

def transaction_hash(date: str, amount: float, description: str, account: str) -> str:
    canonical = f"{date}|{amount:.2f}|{description.strip().lower()}|{account.lower()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def file_hash(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def import_csv(
    csv_path: str,
    account_name: str,
    source: str = "csv",
    column_map: dict = None
) -> dict:
    """
    Import CSV into transactions table with deduplication.
    
    Args:
        csv_path: path to CSV file
        account_name: e.g., "Chase Checking"
        source: 'csv', 'email', 'plaid', etc.
        column_map: dict mapping CSV columns to standard names
                    (optional; defaults to common bank CSV headers)
    
    Returns:
        {
            "import_id": "import-...",
            "rows_expected": 50,
            "rows_parsed": 48,
            "rows_duplicate": 2,
            "rows_error": 0
        }
    """
    ensure_db()
    
    # Default column mapping
    if column_map is None:
        column_map = {
            "Date": "date",
            "Amount": "amount",
            "Description": "description",
            "Merchant": "merchant",
            "Category": "category"
        }
    
    import_id = f"import-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    fhash = file_hash(csv_path)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check if file already imported
    cur.execute("SELECT import_id FROM imports WHERE file_hash = ?", (fhash,))
    if cur.fetchone():
        conn.close()
        return {
            "error": "File already imported",
            "import_id": None
        }
    
    # Read CSV
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Insert import record
    cur.execute("""
        INSERT INTO imports (import_id, account_name, source, filename, file_hash, rows_expected)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (import_id, account_name, source, os.path.basename(csv_path), fhash, len(rows)))
    
    parsed = 0
    duplicate = 0
    error = 0
    
    # Parse and insert transactions
    for row in rows:
        try:
            date = row.get("Date", "").strip()
            amount_str = row.get("Amount", "0").strip().replace("$", "").replace(",", "")
            amount = float(amount_str)
            desc = row.get("Description", "").strip()
            
            if not date or not desc:
                error += 1
                continue
            
            category = row.get("Category", "uncategorized").strip()
            txn_id = transaction_hash(date, amount, desc, account_name)
            
            try:
                cur.execute("""
                    INSERT INTO transactions (
                        txn_id, import_id, date, amount, description, category, account,
                        raw_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    txn_id, import_id, date, amount, desc, category, account_name,
                    json.dumps(row, ensure_ascii=False)
                ))
                parsed += 1
            except sqlite3.IntegrityError:
                duplicate += 1
        
        except Exception as e:
            print(f"Error parsing row {row}: {e}")
            error += 1
    
    # Update import record
    cur.execute("""
        UPDATE imports
        SET rows_parsed = ?, rows_duplicate = ?, rows_error = ?, updated_at = CURRENT_TIMESTAMP
        WHERE import_id = ?
    """, (parsed, duplicate, error, import_id))
    
    conn.commit()
    conn.close()
    
    return {
        "import_id": import_id,
        "rows_expected": len(rows),
        "rows_parsed": parsed,
        "rows_duplicate": duplicate,
        "rows_error": error
    }

# Example usage
if __name__ == "__main__":
    result = import_csv(
        "downloads/checking_jan_2025.csv",
        account_name="Chase Checking"
    )
    print(f"Imported: {result['rows_parsed']} | Duplicates: {result['rows_duplicate']} | Errors: {result['rows_error']}")
```

### Common Queries

#### Monthly spending by category

```python
import pandas as pd
import sqlite3

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    strftime('%Y-%m', date) AS month,
    category,
    SUM(amount) AS total,
    COUNT(*) AS count
FROM transactions
WHERE is_income = 0
  AND account = 'Chase Checking'
GROUP BY month, category
ORDER BY month DESC, total DESC
"""

df = pd.read_sql_query(query, conn)
print(df)
```

**Output:**
```
      month       category   total  count
0  2025-11        groceries -520.00     12
1  2025-11       utilities  -155.00      2
2  2025-11   entertainment -100.00      5
```

#### Total income vs. spending per month

```python
query = """
SELECT
    strftime('%Y-%m', date) AS month,
    is_income,
    SUM(amount) AS total
FROM transactions
GROUP BY month, is_income
ORDER BY month DESC
"""

df = pd.read_sql_query(query, conn)
print(df.pivot(index='month', columns='is_income', values='total'))
```

#### Unreconciled transactions

```python
query = """
SELECT date, description, amount, category, account
FROM transactions
WHERE reconciled = 0
ORDER BY date DESC
LIMIT 50
"""

df = pd.read_sql_query(query, conn)
print(df)
```

---

## Retention, Compression & Backups

### Attachment Retention Policy

| Attachment Type | Retention | Reason |
|---|---|---|
| CSV exports | 3 years (permanent) | Lightweight; useful for re-import or audit |
| PDF statements | 1–2 years | Space-heavy; parsed data in DB is permanent |
| Email attachments | Compress after 6 months | Archive infrequently accessed |

### Compression

Reduce PDF/CSV storage using gzip:

```bash
# Compress all attachments older than 6 months
find user_data/statements/attachments -name "*.pdf" -o -name "*.csv" \
  -mtime +180 \
  -exec gzip {} \;

# Create archive of entire statements folder
tar -czf user_data/backups/statements-$(date +%Y-%m-%d).tar.gz \
  user_data/statements/

# Verify compression ratio
du -sh user_data/statements/
du -sh user_data/backups/statements-*.tar.gz
```

### Database Backups

Create snapshots of SQLite database:

```bash
#!/bin/bash
# daily_backup.sh

BACKUP_DIR="user_data/backups"
mkdir -p "$BACKUP_DIR"

# Backup DB
cp user_data/ledger/transactions.sqlite \
   "$BACKUP_DIR/transactions.sqlite.$(date +%Y-%m-%d)"

# Keep only last 30 daily backups
ls -t "$BACKUP_DIR"/transactions.sqlite.* | tail -n +31 | xargs rm -f
```

### SQL Dump (Text-based backup)

```bash
sqlite3 user_data/ledger/transactions.sqlite ".dump" > user_data/backups/transactions.sql.$(date +%Y-%m-%d)
gzip user_data/backups/transactions.sql.*
```

### Restore from Backup

```bash
# Restore from copy
cp user_data/backups/transactions.sqlite.2025-11-30 user_data/ledger/transactions.sqlite

# Restore from SQL dump
sqlite3 user_data/ledger/transactions.sqlite < user_data/backups/transactions.sql.2025-11-30
```

---

## Security & Access Control

### File Permissions

Restrict access to sensitive data:

```bash
# Restrictive permissions on data directory
chmod 700 user_data/

# Restrictive permissions on DB file
chmod 600 user_data/ledger/transactions.sqlite

# Restrictive permissions on backups
chmod 600 user_data/backups/*
```

### Encryption Options

#### Option 1: OS-Level Encryption (Recommended for simplicity)

- **macOS:** FileVault 2 (built-in)
- **Linux:** LUKS/dm-crypt (built-in)
- **Windows:** BitLocker (Windows Pro+)

Encrypts entire home directory transparently; automatic on login.

#### Option 2: Encrypted Container

```bash
# Create encrypted container using VeraCrypt
veracrypt --create --filesystem=ext4 --size=500M user_data.vc

# Mount container
veracrypt --mount user_data.vc /mnt/personal_finance

# Unmount when done
veracrypt --dismount /mnt/personal_finance
```

#### Option 3: SQLCipher (Database-level encryption)

Add to `requirements.txt`:
```
sqlcipher3>=3.8.10.2
```

Usage:
```python
import sqlcipher3

conn = sqlcipher3.connect(":memory:")
conn.execute("PRAGMA key = 'yourpassword123'")
# Create tables, queries proceed normally
```

⚠️ **Trade-off:** Slower than unencrypted SQLite; choose only if sensitive data.

### Git & Version Control

Ensure `user_data/` is **never** committed:

```bash
# .gitignore
user_data/
*.db
*.sqlite
*.sqlite-wal
.env
```

---

## Performance Tips

### Database Optimization

Enable WAL mode and relaxed sync settings for better performance:

```sql
-- Add to schema or run once
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  -- 64 MB cache
PRAGMA temp_store = MEMORY;
```

### Vacuum & Analyze

Periodically optimize DB:

```bash
# Run weekly
sqlite3 user_data/ledger/transactions.sqlite "VACUUM; ANALYZE;"
```

### Index Strategy

Ensure indexes match common query patterns:

```sql
-- Already in schema, but verify if adding new queries:
CREATE INDEX idx_txn_date ON transactions(date);
CREATE INDEX idx_txn_account ON transactions(account);
CREATE INDEX idx_txn_category ON transactions(category);

-- Add if you query by is_income frequently:
CREATE INDEX idx_txn_is_income ON transactions(is_income);

-- Add if you query by reconciliation status:
CREATE INDEX idx_txn_reconciled ON transactions(reconciled);
```

### Materialized Aggregates

For frequent analyzer queries, pre-compute monthly summaries:

```python
import sqlite3
from datetime import datetime

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Compute aggregates for all months with transactions
cur.execute("""
    INSERT OR REPLACE INTO monthly_aggregates (year_month, account, category, total_amount, transaction_count, is_income, computed_at)
    SELECT
        strftime('%Y-%m', date) AS year_month,
        account,
        category,
        SUM(amount),
        COUNT(*),
        is_income,
        CURRENT_TIMESTAMP
    FROM transactions
    GROUP BY year_month, account, category, is_income
""")

conn.commit()
conn.close()
```

Run this nightly or weekly for fast analyzer UI responses.

### Query Profiling

Identify slow queries:

```python
import sqlite3

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA query_only = TRUE")

# Enable query profiling
conn.execute("PRAGMA compile_options = ENABLE_TRACE")

# Run your query
result = conn.execute("""
    SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions GROUP BY month
""").fetchall()

# Explain plan
plan = conn.execute("""
    EXPLAIN QUERY PLAN
    SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions GROUP BY month
""").fetchall()

for row in plan:
    print(row)
```

---

## Implementation Checklist

### Phase 1: Core Schema & Ingestion

- [ ] Copy schema SQL to `backend/statements/schema.sql`
- [ ] Create `backend/statements/ingestion.py` with `import_csv()` function
- [ ] Add unit tests in `tests/test_ingestion.py`
- [ ] Verify deduplication (import same file twice, check rows_duplicate)
- [ ] Update `requirements.txt` (no new deps needed; using built-in `sqlite3`)
- [ ] Test with real CSV from your bank

### Phase 2: Backend API Endpoints

- [ ] `POST /api/transactions` – Add manual transaction
- [ ] `GET /api/transactions` – Query with filters (date, category, account)
- [ ] `POST /api/transactions/import` – Upload & process CSV
- [ ] `GET /api/transactions/summary` – Monthly aggregates by category

### Phase 3: Frontend UI

- [ ] Transaction entry form
- [ ] Transaction ledger table (sortable, filterable)
- [ ] Upload CSV modal
- [ ] Period summary view

### Phase 4: Analyzer Integration

- [ ] `GET /api/analysis/spending-by-category` – Query aggregates
- [ ] `GET /api/analysis/variance-report` – Compare history to plan
- [ ] Materialize monthly aggregates nightly

### Phase 5: Backup & Maintenance

- [ ] Script daily DB backups (`scripts/backup.sh`)
- [ ] Document recovery procedure
- [ ] Add `.gitignore` entries for `user_data/`

---

## Next Steps

1. **Create schema file:** Copy `schema.sql` from this guide to `backend/statements/schema.sql`
2. **Implement ingestion module:** Create `backend/statements/ingestion.py` with CSV import function
3. **Test with sample data:** Download a real statement CSV and test deduplication
4. **Add backend endpoints:** Expose ingestion & query via Flask routes
5. **Wire frontend:** Build UI for transaction entry and import

Would you like me to:
- ✅ Generate the schema and ingestion module files?
- ✅ Create unit tests for deduplication?
- ✅ Provide example bank CSV formats?
- ✅ Build the Flask endpoints?
