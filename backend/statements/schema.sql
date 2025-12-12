PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS imports (
  import_id TEXT PRIMARY KEY,
  account_name TEXT NOT NULL,
  source TEXT NOT NULL,
  filename TEXT,
  file_hash TEXT,
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
CREATE INDEX IF NOT EXISTS idx_attachment_import ON attachments(import_id);

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
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_txn_import ON transactions(import_id);
CREATE INDEX IF NOT EXISTS idx_txn_is_income ON transactions(is_income);
CREATE INDEX IF NOT EXISTS idx_txn_reconciled ON transactions(reconciled);

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
