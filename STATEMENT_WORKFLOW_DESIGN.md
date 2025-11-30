# Statement-Driven Workflow Design
## Income & Expense Entry from Account Statements

### Overview
This workflow allows you to import transactions from account statements (checking, saving, credit, HSA, stock plan, etc.) and automatically categorize them into income and expense entries in your financial plan.

---

## Architecture

### 1. **Statement Import Pipeline**

```
Account Statement (CSV/JSON)
         ↓
    Parser Module (detect format, headers)
         ↓
    Transaction Extractor (date, amount, description)
         ↓
    Categorizer Engine (ML-based or rule-based)
         ↓
    Transaction Table (review & edit before commit)
         ↓
    Income/Expense Aggregator (monthly/annual rollup)
         ↓
    Plan Integration (add/update income & spending rows)
```

### 2. **Key Components to Build**

#### A. **Statement Parser** (`backend/statements/parser.py`)
- Detect common formats: CSV, OFX, QIF, JSON
- Handle multiple bank/account statement formats
- Extract: date, amount, description, category (if present)
- Normalize transaction data into a common schema

#### B. **Transaction Categorizer** (`backend/statements/categorizer.py`)
- Rule-based: match description patterns → category
- Machine learning optional: train on user's historical categorizations
- Built-in categories: income, salary, bonus, living, debt, health, utilities, etc.
- Allow user override before committing

#### C. **Transaction Model** (`backend/data_model/transaction.py`)
```python
@dataclass
class Transaction:
    date: str              # YYYY-MM-DD
    amount: float          # positive=income, negative=expense
    description: str
    source_account: str    # which account statement provided this
    category: str          # categorizer output
    confidence: float      # 0.0-1.0 for ML categorization
    is_income: bool        # True if positive amount & income-like
    user_confirmed: bool   # True if user reviewed
```

#### D. **Statement Import Handler** (`backend/statements/importer.py`)
- API endpoint to receive statement files
- Batch process transactions
- Match transactions to existing income/spending rows (avoid duplicates)
- Provide aggregated monthly/annual view

#### E. **Transaction Review UI** (`frontend/transactions.html`)
- Table of parsed transactions with editable category/account fields
- Filter & sort by date, category, amount
- Bulk actions: approve, reject, re-categorize
- Preview: show how transactions will roll up into income/spending rows

---

## Data Flow: Detailed Example

### Scenario: Import Checking Account Statement (Jan-Mar 2025)

**Input CSV:**
```
Date,Description,Amount
2025-01-01,Direct Deposit - Employer,3500.00
2025-01-05,Walmart - Grocery,-150.00
2025-01-10,Starbucks,-12.50
2025-01-15,HSA Contribution (employer),-500.00
2025-02-01,Direct Deposit - Employer,3500.00
2025-02-08,Whole Foods Market,-85.00
2025-03-01,Direct Deposit - Employer,3500.00
```

**After Parsing & Categorization:**
```
Transaction 1:
  - Date: 2025-01-01
  - Amount: +3500.00
  - Description: Direct Deposit - Employer
  - Category: salary (HIGH confidence)
  - Is Income: True

Transaction 2:
  - Date: 2025-01-05
  - Amount: -150.00
  - Description: Walmart - Grocery
  - Category: living (HIGH confidence)
  - Is Income: False

... (similar for remaining transactions)
```

**Aggregated View (User Reviews):**
```
Income Summary (Jan-Mar 2025):
  - Salary: $10,500 (3 deposits × $3,500)
  - HSA Contribution: -$500 (treated as employee pre-tax deduction)

Spending Summary (Jan-Mar 2025):
  - Groceries/Living: $235.00 ($150 + $85)
  - Other (Starbucks): $12.50
```

**User Selects:** "Commit to plan as single 'Household Salary' income row ($10,500/3 months = $42,000/year)"

**Result:**
- New income row added to plan:
  ```
  Name: Household Salary (Checking Account)
  Category: salary
  Annual Amount: 42000
  Start Month: 2025-01
  End Month: 2025-03
  ```

---

## Backend API Endpoints

### Upload & Parse Statement
```
POST /api/statements/upload
Content-Type: multipart/form-data

Parameters:
  - file: CSV/JSON/OFX file
  - account_name: (e.g., "Checking")
  - account_type: (e.g., "asset", "credit")

Response:
{
  "import_id": "uuid-123",
  "file_name": "checking_jan_mar_2025.csv",
  "transaction_count": 7,
  "parsed_transactions": [
    {
      "id": "txn-1",
      "date": "2025-01-01",
      "amount": 3500.00,
      "description": "Direct Deposit - Employer",
      "category": "salary",
      "is_income": true,
      "confidence": 0.95,
      "user_confirmed": false
    },
    ...
  ]
}
```

### Get Transactions (with Filters)
```
GET /api/statements/{import_id}/transactions?category=salary&start_date=2025-01-01

Response:
{
  "transactions": [...],
  "summary": {
    "total_income": 10500.0,
    "total_spending": 247.50,
    "period": "2025-01 to 2025-03"
  }
}
```

### Update Transaction Category (User Override)
```
PUT /api/statements/transactions/{txn_id}
{
  "category": "living",
  "user_confirmed": true
}

Response: { "status": "updated", "transaction": {...} }
```

### Commit Transactions to Plan
```
POST /api/statements/{import_id}/commit
{
  "plan_id": "my-plan-123",
  "grouping": "monthly",  // or "quarterly", "annual", "category-based"
  "create_new_rows": true,
  "start_date": "2025-01-01",
  "end_date": "2025-03-31"
}

Response:
{
  "status": "committed",
  "income_rows_added": [
    { "name": "Household Salary", "annual_amount": 42000, ... }
  ],
  "spending_rows_added": [
    { "name": "Groceries", "annual_amount": 940, ... }
  ]
}
```

### Get Aggregated Summary (before commit)
```
GET /api/statements/{import_id}/summary?group_by=category&period=month

Response:
{
  "grouped_transactions": {
    "2025-01": {
      "salary": { "total": 3500, "count": 1 },
      "living": { "total": -247.50, "count": 3 }
    },
    "2025-02": { ... },
    "2025-03": { ... }
  }
}
```

---

## Frontend Screens

### 1. **Statement Upload Screen**
- Drag-and-drop file upload
- Select account name/type
- Display file preview (first 10 rows)
- Submit button → triggers parsing

### 2. **Transaction Review Table**
- Sortable columns: Date, Description, Amount, Category, Confidence
- Inline edit for category (dropdown)
- Highlight rows needing user confirmation (confidence < 0.8)
- Bulk actions: approve all, re-categorize selected, reject selected
- Filter by date range, category, income/expense

### 3. **Summary & Aggregation View**
- Show grouped totals (by month, category, account type)
- Pie chart: income vs. spending breakdown
- Comparison with existing plan rows (detect duplicates)
- Options to group by: calendar month, category, fiscal quarter

### 4. **Commit Options Modal**
- Choose grouping strategy (monthly/quarterly/annual/category-based)
- Preview: what new rows will be created
- Option to merge with existing rows or create new ones
- Confirm before committing to plan

---

## Categorization Strategy

### Built-in Rules (Rule-Based Engine)
```python
CATEGORIZATION_RULES = {
    "salary": {
        "patterns": ["payroll", "salary", "direct deposit", "employer", "net pay"],
        "is_income": True,
    },
    "bonus": {
        "patterns": ["bonus", "incentive", "commission"],
        "is_income": True,
    },
    "rental": {
        "patterns": ["rent deposit", "rental", "lease payment received"],
        "is_income": True,
    },
    "living": {
        "patterns": ["grocery", "walmart", "costco", "whole foods", "safeway", "kroger", "trader joe"],
        "is_income": False,
    },
    "utilities": {
        "patterns": ["electric", "water", "gas", "internet", "phone"],
        "is_income": False,
    },
    "health": {
        "patterns": ["pharmacy", "doctor", "hospital", "medical", "dental", "cvs", "walgreens"],
        "is_income": False,
    },
    "debt": {
        "patterns": ["loan payment", "credit card payment", "mortgage", "student loan"],
        "is_income": False,
    },
    ...
}
```

### Confidence Scoring
- Exact match (description contains keyword): 0.95
- Partial match (2+ keywords match): 0.80
- Fuzzy match (similar to known merchant): 0.60
- No match (default to "other"): 0.30

### User Feedback Loop (Optional ML)
- Track user corrections and re-train classifier
- Build merchant → category mapping over time
- Surface similar unmapped transactions for batch-categorization

---

## Integration with Existing Data Model

### Updated `CashflowItem` (optional extension)
```python
@dataclass
class CashflowItem:
    name: str
    annual_amount: float
    category: str
    start_year: float = 0.0
    end_year: float = 0.0
    flow_type: Literal["income", "spending"] = "income"
    taxable: bool = False
    
    # NEW: track origin from statement import
    source_statement_id: str | None = None  # UUID of import
    source_transactions: List[str] = field(default_factory=list)  # txn IDs
    user_confirmed: bool = False
```

### New Storage: `user_data/statements/`
```
user_data/
  └─ statements/
      ├─ imports.json           # metadata on uploaded statements
      ├─ transactions.json      # all parsed transactions (archive)
      └─ {import_id}.json       # per-import transaction details
```

---

## Implementation Roadmap

### Phase 1: Foundation
1. Define transaction model and storage schema
2. Build CSV parser (most common format)
3. Implement basic rule-based categorizer
4. Create transaction review API endpoint
5. Basic frontend upload + review screen

### Phase 2: Integration
1. Build commit logic (add/merge with existing rows)
2. Aggregate views (monthly, category-based)
3. Duplicate detection (compare with existing plan rows)
4. Update `PlanConfig` serialization to track statement sources

### Phase 3: Enhancement
1. Support multiple formats (OFX, QIF, JSON)
2. ML-based categorizer (Naive Bayes or similar)
3. Batch transaction management (edit, delete, re-import)
4. Merchant name normalization & mapping
5. Tax categorization hints (HSA, 401k, etc.)

### Phase 4: Advanced
1. Recurring transaction detection
2. Outlier detection (unusual amounts)
3. Statement reconciliation (verify amounts match account balances)
4. Multi-year import & trend analysis
5. Export normalized transactions to accounting software

---

## Database Schema (if migrating to persistent DB)

```sql
CREATE TABLE statements (
    id UUID PRIMARY KEY,
    plan_id VARCHAR(255),
    account_name VARCHAR(255),
    account_type VARCHAR(50),  -- asset, credit, investment, etc.
    file_name VARCHAR(255),
    file_hash VARCHAR(64),     -- detect duplicate uploads
    imported_at TIMESTAMP,
    transaction_count INT,
    created_at TIMESTAMP
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    statement_id UUID REFERENCES statements(id),
    date DATE,
    amount DECIMAL(12, 2),
    description TEXT,
    category VARCHAR(50),
    is_income BOOLEAN,
    confidence FLOAT,
    user_confirmed BOOLEAN,
    user_category_override VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE transaction_categories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),     -- if multi-user
    merchant_name VARCHAR(255),
    category VARCHAR(50),
    count INT DEFAULT 1,
    last_used TIMESTAMP
    -- tracks user's merchant → category mappings for ML
);

CREATE TABLE committed_batches (
    id UUID PRIMARY KEY,
    statement_id UUID,
    plan_id VARCHAR(255),
    grouping_strategy VARCHAR(50),  -- monthly, category-based, etc.
    income_row_ids TEXT,            -- JSON array
    spending_row_ids TEXT,          -- JSON array
    committed_at TIMESTAMP
);
```

---

## Sample Workflow: End-to-End

1. **User downloads March 2025 checking statement** from their bank
2. **Uploads CSV** via frontend → parser detects format
3. **Categorizer runs** on 25 transactions → 22 auto-categorized, 3 flagged
4. **Review screen shows:**
   - Table of 25 transactions
   - Confidence scores highlighted
   - 3 uncertain ones filtered to top
5. **User approves auto-categorized** transactions in bulk
6. **User manually fixes** the 3 uncertain ones (e.g., "Amazon" → check ASIN to determine if household item or work supply)
7. **Preview aggregation:** 
   - Income: $10,500 (3 × payroll)
   - Spending: $847 (groceries $635, utilities $150, other $62)
8. **User selects "group by calendar month"** and commits
9. **New rows added to plan:**
   - Income: "Checking Account - March Deposits" ($42,000/yr annualized)
   - Spending: "Checking Account - March Transactions" ($3,388/yr annualized)
10. **Simulator re-runs** with updated plan, net worth graph updated

---

## Benefits of This Workflow

| Benefit | Details |
|---------|---------|
| **Accuracy** | Real transaction data replaces estimates |
| **Audit Trail** | Link every plan row to source statement transactions |
| **Time Savings** | Batch import beats manual row entry |
| **Deduplication** | Detect & prevent duplicate entries |
| **Flexibility** | Group transactions by month, category, or custom period |
| **Extensibility** | Easy to add more account types or statement formats |
| **Pattern Learning** | ML layer can improve over time based on user feedback |

---

## Considerations & Edge Cases

### 1. **Multi-Currency Transactions**
- Store original amount & currency
- Apply exchange rate at commit time
- Flag mixed-currency batches for user review

### 2. **Internal Transfers**
- Detect transfers between user's own accounts
- Optionally hide from income/expense
- Track for account balance reconciliation

### 3. **Pending Transactions**
- Some statements include "pending" flag
- Option to include or exclude pending
- Clear labeling in UI

### 4. **Reconciliation**
- Warn if total committed transactions don't match account statement totals
- Provide reconciliation view

### 5. **Duplicate Prevention**
- Hash transaction (date + amount + description) to detect re-imports
- Warn user before re-importing same file

### 6. **Tax Categorization**
- Add field for tax treatment (taxable, pre-tax, post-tax)
- Auto-detect from category (salary = taxable, HSA = pre-tax)
- Link to HSA/401k accounts for validation

---

## UI Mockup (Text)

```
┌─────────────────────────────────────────────────────┐
│ STATEMENT IMPORT                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│ [ Drag CSV/JSON here ] or [ Browse ]               │
│                                                     │
│ Account Name: [Checking Account      ▼]            │
│ Account Type: [Asset                 ▼]            │
│                                                     │
│ [ Preview (10 rows) ] [ Upload & Parse ]           │
│                                                     │
├─────────────────────────────────────────────────────┤
│ REVIEW & CATEGORIZE (25 transactions)               │
├─────────────────────────────────────────────────────┤
│ Filter: [Date Range] [Category] [Confidence ≥]     │
│                                                     │
│ ☑ Date      │ Description          │ Amt    │Cat   │
│ ──────────────────────────────────────────────────  │
│ ☑ 2025-03-01│ Direct Deposit       │+3500  │salary│
│ ☐ 2025-03-05│ Walmart Grocery      │-150   │living│
│ ◆ 2025-03-07│ Amazon Purchase      │-45    │? ??? │ (flagged)
│ ☑ 2025-03-10│ Phone Bill - Verizon │-85    │utils │
│                                                     │
│ [ Approve All ] [ Resolve Flagged ] [ Reset ]      │
│                                                     │
├─────────────────────────────────────────────────────┤
│ SUMMARY                                             │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Period: Mar 1 - Mar 31, 2025                        │
│                                                     │
│ [PIE CHART]     Income:    $10,500 (12 entries)    │
│                 Spending:  -$847   (13 entries)    │
│                                                     │
│ Grouped by Month:                                   │
│   Mar 2025:  +$10,500 income, -$847 spending      │
│                                                     │
│ [ Group By: Month ▼ ] [ Group By: Category ▼ ]    │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [ Cancel ]  [ Preview Commit ]  [ Commit to Plan ] │
└─────────────────────────────────────────────────────┘
```

---

## Configuration & Defaults

```json
{
  "categorizer": {
    "confidence_threshold": 0.75,
    "enable_ml": false,
    "ml_model_path": "user_data/models/categorizer.pkl"
  },
  "statement_formats": [
    "csv",
    "json"
  ],
  "default_categories": {
    "income": ["salary", "bonus", "rental", "business", "other"],
    "spending": ["living", "utilities", "health", "debt", "parents", "other"]
  },
  "deduplication": {
    "enabled": true,
    "hash_algorithm": "sha256"
  },
  "storage": {
    "archive_imported_files": true,
    "retention_days": 365
  }
}
```

---

## Next Steps

Would you like me to:
1. **Implement Phase 1** (transaction model + CSV parser + basic categorizer)?
2. **Design the database schema** for permanent statement storage?
3. **Build the frontend screens** for upload and review?
4. **Create example CSV formats** for different bank types?
5. **Outline merchant normalization logic** (e.g., "Starbucks Coffee #1234" → "Starbucks")?

Let me know which aspect to prioritize!
