# Revised Architecture: Modular Financial App

## Three Core Modules

### 1. **Tracker Module** (Expense/Income History)
- Real-time transaction logging
- Manual entry + automated imports (email, CSV)
- Account balance tracking
- Transaction categorization & tagging
- Historical ledger

### 2. **Planner Module** (Current Planning/Projection)
- Define future scenarios
- Manual income/spending rows (what you plan for)
- Project net worth & cash flow
- Compare multiple scenarios
- Dashboard visualization

### 3. **Analyzer Module** (Historical → Projection Bridge)
- Analyze historical expense/income patterns
- Calculate averages, trends, seasonality
- Generate suggested spending rows (from history)
- Propose adjustments to plan based on actuals
- Show variance between planned vs actual

---

## Data Flow

```
┌─────────────────────────────────────────────────────┐
│ TRACKER (Historical Data)                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Transaction Entry                                  │
│    ├─ Manual: User types expense                   │
│    ├─ Email Import: Parse bank statement CSV       │
│    ├─ Manual CSV Upload: Download from DCU app    │
│    └─ Auto-categorize                             │
│                                                     │
│  Ledger Storage                                     │
│    ├─ Jan 2025: Groceries $500                    │
│    ├─ Jan 2025: Salary +$5000                     │
│    └─ Feb 2025: ...                               │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Extract Historical Patterns
                   ↓
┌─────────────────────────────────────────────────────┐
│ ANALYZER (Pattern Recognition)                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Compute from last 6-12 months:                    │
│    ├─ Average monthly spending by category         │
│    ├─ Min/max spending ranges                      │
│    ├─ Trends (increasing/decreasing)              │
│    ├─ Seasonality (holiday spending, etc.)        │
│    ├─ Monthly savings rate                        │
│    └─ Income stability                            │
│                                                     │
│  Suggest Plan Rows:                                │
│    ├─ "Groceries: $500/month (avg from history)"  │
│    ├─ "Salary: $5000/month (consistent)"          │
│    └─ "Bonus: $2000 (Dec only, seasonal)"         │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Feed into Plan
                   ↓
┌─────────────────────────────────────────────────────┐
│ PLANNER (Future Projection)                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Plan Definition (what you expect):                │
│    ├─ Income rows (salary, bonus, etc.)           │
│    ├─ Spending rows (living, utilities, etc.)     │
│    ├─ Accounts (checking, savings, investment)    │
│    └─ Assumptions (inflation rate, ROI, etc.)     │
│                                                     │
│  Simulator:                                        │
│    ├─ Run 12-60 month projection                  │
│    ├─ Calculate net worth trajectory              │
│    ├─ Show cash flow each month                   │
│    └─ Identify cash crunches                      │
│                                                     │
│  Dashboard:                                        │
│    ├─ Charts (net worth, liquid assets)           │
│    ├─ Multiple scenarios side-by-side             │
│    ├─ What-if analysis                            │
│    └─ Plan adjustments                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Module Breakdown

### TRACKER Module

**Purpose:** Keep ledger of actual transactions

**Features:**
- Add transaction manually (date, amount, category, account, description)
- Import from CSV (bank statement exports)
- Import from email (automated via email fetcher)
- View transaction history (filterable, sortable)
- Account balance reconciliation
- Export transaction ledger

**Data Model:**
```python
@dataclass
class Transaction:
    id: str
    date: str              # YYYY-MM-DD
    amount: float          # positive=income, negative=expense
    description: str
    category: str          # "groceries", "salary", "utilities", etc.
    account: str           # "Checking", "Credit Card", "DCU Savings"
    source: str            # "manual", "email_import", "csv_upload"
    reconciled: bool       # confirmed against bank statement
    tags: List[str]        # custom tags for organization
    created_at: datetime
    updated_at: datetime
```

**Backend Endpoints:**
```
POST   /api/transactions           # Add new transaction
GET    /api/transactions           # List with filters (date, category, account)
PUT    /api/transactions/{id}      # Edit transaction
DELETE /api/transactions/{id}      # Delete transaction
POST   /api/transactions/import    # Bulk import from CSV
GET    /api/transactions/summary   # Get period summary (by category, etc.)
GET    /api/accounts/balance       # Current balance by account
POST   /api/accounts/reconcile     # Mark transactions as reconciled
```

**Storage:**
```
user_data/
  └─ ledger/
      ├─ transactions.json        # All historical transactions
      ├─ accounts.json            # Account list + balances
      └─ transaction_archive/
          ├─ 2025-01.json
          ├─ 2025-02.json
          └─ ...
```

---

### ANALYZER Module

**Purpose:** Extract patterns from historical data → suggest plan rows

**Features:**
- Analyze last 6/12 months of transactions
- Calculate spending averages by category
- Detect trends (is grocery spending increasing?)
- Identify seasonal patterns (holiday spending spike?)
- Compute income consistency
- Generate suggested spending/income rows
- Compare history vs. current plan (variance analysis)

**Analysis Functions:**
```python
class TransactionAnalyzer:
    def __init__(self, transactions: List[Transaction]):
        self.transactions = transactions
    
    def spending_by_category(self, months: int = 12) -> Dict[str, float]:
        """Average monthly spending per category (last N months)"""
        # Returns: {"groceries": 500.0, "utilities": 150.0, ...}
    
    def spending_range(self, category: str) -> Dict[str, float]:
        """Min, max, avg for category"""
        # Returns: {"min": 400, "max": 650, "avg": 500, "std_dev": 50}
    
    def trend(self, category: str, months: int = 6) -> Dict:
        """Is spending increasing or decreasing?"""
        # Returns: {"direction": "up", "rate": 2.5, "note": "+2.5% per month"}
    
    def seasonality(self, category: str) -> Dict[str, float]:
        """Monthly pattern: which months spend more?"""
        # Returns: {"Jan": 1.2, "Feb": 1.1, ..., "Dec": 1.5}
        # (1.2 = 20% above average)
    
    def income_consistency(self) -> Dict:
        """How stable is income month-to-month?"""
        # Returns: {"avg": 5000, "std_dev": 200, "variation": "3.2%"}
    
    def suggested_plan_rows(self) -> List[dict]:
        """Generate income/spending rows from history"""
        # Returns: [
        #   {
        #     "type": "spending",
        #     "name": "Groceries",
        #     "category": "living",
        #     "annual_amount": 6000,
        #     "confidence": 0.95,
        #     "note": "Average from Jan-Nov 2024"
        #   },
        #   ...
        # ]
    
    def variance_report(self, plan: PlanConfig) -> Dict:
        """Compare planned vs actual"""
        # Returns: {
        #   "groceries": {
        #     "planned": 500/month,
        #     "actual": 520/month,
        #     "variance": "+4%",
        #     "total_variance": "+$240/year"
        #   },
        #   ...
        # }
```

**Backend Endpoints:**
```
GET /api/analysis/spending-by-category?months=12
    # Response: {"groceries": 500, "utilities": 150, ...}

GET /api/analysis/spending-range?category=groceries
    # Response: {"min": 400, "max": 650, "avg": 500, "std_dev": 50}

GET /api/analysis/trend?category=groceries&months=6
    # Response: {"direction": "up", "rate": 2.5, "note": "+2.5% per month"}

GET /api/analysis/seasonality?category=groceries
    # Response: {"Jan": 1.2, "Feb": 1.1, ..., "Dec": 1.5}

GET /api/analysis/income-consistency
    # Response: {"avg": 5000, "std_dev": 200, "variation": "3.2%"}

GET /api/analysis/suggested-plan-rows?months=12
    # Response: [
    #   {"type": "spending", "name": "Groceries", "annual_amount": 6000, ...},
    #   ...
    # ]

GET /api/analysis/variance-report?plan_id=my-plan
    # Response: {
    #   "groceries": {
    #     "planned": 500,
    #     "actual": 520,
    #     "variance": "+4%",
    #     ...
    #   },
    #   ...
    # }
```

---

### PLANNER Module (Existing, Enhanced)

**Purpose:** Define plans, run projections, visualize scenarios

**No changes needed** – your current implementation is the Planner module

**Enhanced with Analyzer:**
- "Suggest from history" button → pre-populate spending rows
- "Compare to history" tab → show variance report
- "Auto-adjust spending" option → update based on recent trends

---

## Updated App UI Flow

```
┌──────────────────────────────────────────────────────────┐
│ Top Navigation                                           │
├──────────────────────────────────────────────────────────┤
│  [Tracker]  [Analyzer]  [Planner]                        │
└──────────────────────────────────────────────────────────┘

TRACKER TAB:
┌──────────────────────────────────────────────────────────┐
│ Add Transaction | Import CSV | View Ledger              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ [+] Add Transaction                                     │
│ Date: 2025-11-29                                        │
│ Amount: -50                                             │
│ Category: [Groceries       ▼]                           │
│ Account: [Checking Account ▼]                           │
│ Description: Safeway                                    │
│ [Save]                                                  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Recent Transactions (Last 30 days)                       │
├──────────────────────────────────────────────────────────┤
│ Date      │ Description │ Category   │ Amount │ Account  │
│ 2025-11-29│ Safeway    │ Groceries  │-50    │Checking  │
│ 2025-11-28│ Payroll    │ Salary     │+5000  │Checking  │
│ 2025-11-27│ Electric   │ Utilities  │-85    │Checking  │
│                                                          │
│ Period Summary:
│ Income: +$10,000 | Spending: -$500 | Net: +$9,500
└──────────────────────────────────────────────────────────┘

ANALYZER TAB:
┌──────────────────────────────────────────────────────────┐
│ Analyze Last [12 ▼] Months                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ SPENDING BREAKDOWN (Average/Month)                      │
│ Groceries:    $520/mo   (trend: ↑ +2.5%/mo)           │
│ Utilities:    $150/mo   (trend: → stable)             │
│ Entertainment: $100/mo   (trend: ↓ -5%/mo)            │
│ ...                                                     │
│                                                          │
│ INCOME (Last 12 Months)                                │
│ Salary:       $5000/mo  (consistency: 99%)            │
│ Bonus:        $2000     (seasonal: Dec only)          │
│                                                          │
│ [Generate Suggested Plan Rows] ←─────────────┐
│                                               │
│ VARIANCE REPORT (vs. Current Plan)            │
│                                               │
│ Category       │ Planned   │ Actual  │ Diff   │
│ Groceries      │ $500/mo   │ $520/mo │ +4%    │
│ Utilities      │ $150/mo   │ $155/mo │ +3%    │
│ Entertainment  │ $150/mo   │ $100/mo │ -33%   │
│                                               │
│ [Adjust Plan Based on Variance]               │
└──────────────────────────────────────────────────────────┘
                                                       │
                                                       │ Click
                                                       ↓
PLANNER TAB (Enhanced):
┌──────────────────────────────────────────────────────────┐
│ Plan: Q4 2025 Projection                                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Income Rows:                                            │
│ ☑ Household Salary - $5000/month (from history)        │
│ ☑ Bonus - $2000 (seasonal, suggested from analysis)   │
│                                                          │
│ Spending Rows:                                          │
│ ☑ Groceries - $520/month (suggested from analysis)     │
│ ☑ Utilities - $155/month (adjusted from variance)      │
│ ☑ Entertainment - $100/month (revised down)            │
│                                                          │
│ [Simulate & Plot]                                       │
│                                                          │
│ Results: Net Worth Projection Q4-Q1                     │
│ [Chart showing trajectory]                              │
│                                                          │
│ [Show Variance Report] ←─ link back to Analyzer         │
└──────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Tracker Foundation
1. Transaction data model
2. Manual transaction entry UI
3. Transaction ledger view
4. Account balance tracking
5. Simple CSV import

### Phase 2: Analyzer Foundation
1. Transaction query/aggregation
2. Spending by category analysis
3. Income consistency check
4. Suggested plan row generation

### Phase 3: Integration
1. Analyzer → Planner UI linking
2. Pre-populate plan rows from suggestions
3. Variance report display
4. Auto-adjust spending options

### Phase 4: Advanced Tracker
1. Email statement fetcher
2. Auto-categorization
3. Transaction reconciliation
4. Account sync

---

## Database Schema

```sql
-- Transactions table
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    plan_id VARCHAR(255),              -- optional, link to plan
    date DATE NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    account VARCHAR(100),
    source VARCHAR(50),                -- "manual", "email", "csv"
    reconciled BOOLEAN DEFAULT FALSE,
    tags TEXT,                         -- JSON array
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    INDEX(plan_id, date),
    INDEX(category),
    INDEX(account)
);

-- Account balances (snapshot)
CREATE TABLE account_balances (
    id UUID PRIMARY KEY,
    account_name VARCHAR(100),
    balance DECIMAL(12, 2),
    date DATE,
    source VARCHAR(50),                -- "manual", "statement"
    UNIQUE(account_name, date)
);

-- Analysis cache (periodic materialization)
CREATE TABLE spending_analysis (
    id UUID PRIMARY KEY,
    plan_id VARCHAR(255),
    period_start DATE,
    period_end DATE,
    category VARCHAR(50),
    average DECIMAL(12, 2),
    min DECIMAL(12, 2),
    max DECIMAL(12, 2),
    std_dev DECIMAL(12, 2),
    trend_direction VARCHAR(10),       -- "up", "down", "stable"
    created_at TIMESTAMP,
    INDEX(plan_id, category)
);
```

---

## Key Design Benefits

1. **Clear Separation of Concerns**
   - Tracker = data capture
   - Analyzer = insight extraction
   - Planner = scenario simulation

2. **Historical Data Drives Plans**
   - Import 6-12 months of real transactions
   - Analyzer extracts patterns automatically
   - Planner uses realistic numbers instead of guesses

3. **Continuous Improvement**
   - Each month, new transactions update analysis
   - Variance reports show where actual diverges from plan
   - Plan rows can be re-suggested/auto-adjusted

4. **Privacy-Respecting**
   - All transaction data stays local (CSV import + email parsing)
   - No third-party APIs required
   - User controls categorization

5. **Flexible Input Methods**
   - Manual entry (one-off transactions)
   - CSV upload (DCU monthly download)
   - Email import (Chase, BOA, etc.)

---

## Migration Path from Current App

Your current Planner works great. To add these modules:

1. **Add Tracker** (new module)
   - Store historical transactions
   - Support manual entry + CSV import

2. **Add Analyzer** (new module)
   - Query Tracker data
   - Generate insights

3. **Enhance Planner** (existing module)
   - Add buttons: "Suggest from history", "Compare to history"
   - Link to Analyzer data

**No breaking changes** – your existing plans/scenarios keep working.

---

Does this architecture make sense? Should I start implementing:
- ✅ Tracker module (transaction entry + ledger)?
- ✅ Analyzer module (pattern recognition)?
- ✅ Both?
