# Statement Automation Design
## Email & API Integration for Automatic Statement Fetching

### Overview
Yes, automation is absolutely possible! This document outlines three approaches to automatically fetch and process account statements:

1. **Email Binding** – Monitor bank email accounts for statement attachments
2. **Bank API Integration** – Direct connection to bank APIs (Plaid, Yodlee, Open Banking)
3. **Scheduled Web Scraping** – Automated login and statement download

---

## Approach 1: Email Binding (Most Accessible)

### How It Works
- User provides Gmail/Outlook credentials (or app-specific password)
- System monitors designated inbox for incoming statements
- Automatically extracts CSV/PDF attachments from bank emails
- Triggers categorization & review workflow
- Optionally auto-commits if confidence is high

### Supported Banks (Email-Based)
| Bank | Email Domain | Typical Attachments |
|------|--------------|-------------------|
| Bank of America | statements@bankofamerica.com | CSV, PDF |
| Chase | statement@chase.com | PDF, CSV |
| Fidelity | statements@fidelity.com | CSV, PDF |
| Vanguard | statements@vanguard.com | PDF |
| Schwab | statements@schwab.com | PDF, CSV |
| American Express | statements@americanexpress.com | PDF |
| Discover | statement@discover.com | PDF |
| Ally Bank | statements@ally.com | PDF, CSV |
| Capital One | notices@capitalone.com | PDF |
| Savings institutions | (varies) | CSV, PDF |

### Implementation: Email Fetcher

```python
# backend/statements/email_fetcher.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import imaplib
import email
from email.header import decode_header
import re
import base64
import io

@dataclass
class EmailCredential:
    """Securely stored email credentials"""
    email_address: str
    provider: str  # gmail, outlook, etc.
    app_password: str  # OAuth token or app-specific password
    imap_server: str
    imap_port: int = 993
    account_name: str = ""  # e.g., "Checking", "Credit Card"
    enabled: bool = True
    last_checked: Optional[datetime] = None

class EmailStatementFetcher:
    """Monitors email for bank statements and extracts attachments"""
    
    PROVIDER_CONFIG = {
        "gmail": {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "note": "Use app-specific password (not your Gmail password)"
        },
        "outlook": {
            "imap_server": "imap-mail.outlook.com",
            "imap_port": 993,
        },
        "yahoo": {
            "imap_server": "imap.mail.yahoo.com",
            "imap_port": 993,
            "note": "Use app-specific password"
        },
    }
    
    def __init__(self, credential: EmailCredential):
        self.credential = credential
        self.mail = None
    
    def connect(self) -> bool:
        """Establish IMAP connection"""
        try:
            self.mail = imaplib.IMAP4_SSL(
                self.credential.imap_server,
                self.credential.imap_port
            )
            self.mail.login(
                self.credential.email_address,
                self.credential.app_password
            )
            return True
        except Exception as e:
            print(f"IMAP connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close IMAP connection"""
        if self.mail:
            self.mail.close()
            self.mail.logout()
    
    def fetch_recent_statements(
        self, 
        days_back: int = 30,
        sender_patterns: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Fetch statement emails from past N days
        
        Args:
            days_back: Look back this many days
            sender_patterns: Optional list of sender email patterns to match
                           (e.g., ["statements@bankofamerica.com", "noreply@*"])
        
        Returns:
            List of dicts with attachment data
        """
        if not self.connect():
            return []
        
        try:
            self.mail.select("INBOX")
            
            # Build search query
            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            search_criteria = f'SINCE {since_date}'
            
            # Search for emails
            status, email_ids = self.mail.search(None, search_criteria)
            if status != "OK":
                return []
            
            statements = []
            for email_id in email_ids[-50:]:  # Last 50 emails
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue
                
                msg = email.message_from_bytes(msg_data[0][1])
                sender = msg.get("From", "")
                
                # Filter by sender if patterns provided
                if sender_patterns:
                    if not self._matches_patterns(sender, sender_patterns):
                        continue
                
                # Extract attachments
                attachments = self._extract_attachments(msg)
                if attachments:
                    statements.append({
                        "email_id": email_id,
                        "sender": sender,
                        "subject": msg.get("Subject", ""),
                        "date": msg.get("Date", ""),
                        "attachments": attachments,
                        "message": msg
                    })
            
            return statements
        
        finally:
            self.disconnect()
    
    def _matches_patterns(self, sender: str, patterns: List[str]) -> bool:
        """Check if sender matches any pattern (supports wildcards)"""
        for pattern in patterns:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*").replace("@", r"\@")
            if re.match(regex_pattern, sender, re.IGNORECASE):
                return True
        return False
    
    def _extract_attachments(self, msg: email.message.Message) -> List[dict]:
        """Extract file attachments from email"""
        attachments = []
        
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            
            filename = part.get_filename()
            if not filename:
                continue
            
            # Only extract CSV, PDF, XLS
            if not any(filename.lower().endswith(ext) for ext in ['.csv', '.pdf', '.xls', '.xlsx', '.ofx']):
                continue
            
            try:
                payload = part.get_payload(decode=True)
                attachments.append({
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                    "data": payload,
                    "data_base64": base64.b64encode(payload).decode('utf-8')
                })
            except Exception as e:
                print(f"Failed to extract attachment {filename}: {e}")
        
        return attachments
```

### Backend API for Email Integration

```python
# backend/backend.py (additions)

from backend.statements.email_fetcher import EmailStatementFetcher, EmailCredential
from backend.engine.state import EmailCredentialState

email_credential_state = EmailCredentialState()

@app.route("/api/email/credentials", methods=["GET"])
def list_email_credentials():
    """List all configured email accounts (redacted passwords)"""
    credentials = email_credential_state.list_credentials()
    return jsonify({
        "credentials": [
            {
                "id": c["id"],
                "email_address": c["email_address"],
                "account_name": c["account_name"],
                "provider": c["provider"],
                "enabled": c["enabled"],
                "last_checked": c.get("last_checked"),
                "status": "connected" if c["enabled"] else "disabled"
            }
            for c in credentials
        ]
    })

@app.route("/api/email/credentials", methods=["POST"])
def add_email_credential():
    """
    Add new email account to monitor
    
    Body:
    {
        "email_address": "user@gmail.com",
        "app_password": "xxxx xxxx xxxx xxxx",
        "provider": "gmail",
        "account_name": "Checking Account"
    }
    """
    data = request.json
    
    # Validate connection
    try:
        fetcher = EmailStatementFetcher(
            EmailCredential(
                email_address=data["email_address"],
                app_password=data["app_password"],
                provider=data["provider"],
                account_name=data.get("account_name", ""),
                imap_server=EmailStatementFetcher.PROVIDER_CONFIG[data["provider"]]["imap_server"]
            )
        )
        if not fetcher.connect():
            return jsonify({"error": "Failed to connect. Check credentials."}), 400
        fetcher.disconnect()
    except Exception as e:
        return jsonify({"error": f"Connection test failed: {str(e)}"}), 400
    
    # Store credential (encrypted)
    credential_id = email_credential_state.add_credential(
        email_address=data["email_address"],
        app_password=data["app_password"],
        provider=data["provider"],
        account_name=data.get("account_name", "")
    )
    
    return jsonify({
        "status": "added",
        "id": credential_id,
        "message": "Email account added. Monitoring will start with next scheduled check."
    }), 201

@app.route("/api/email/credentials/<credential_id>", methods=["DELETE"])
def remove_email_credential(credential_id: str):
    """Remove an email account from monitoring"""
    email_credential_state.delete_credential(credential_id)
    return jsonify({"status": "removed"})

@app.route("/api/email/fetch-now/<credential_id>", methods=["POST"])
def fetch_statements_now(credential_id: str):
    """
    Manually trigger statement fetch for a credential
    (useful for testing or forcing immediate check)
    """
    credential = email_credential_state.get_credential(credential_id)
    if not credential:
        return jsonify({"error": "Credential not found"}), 404
    
    fetcher = EmailStatementFetcher(
        EmailCredential(
            email_address=credential["email_address"],
            app_password=credential["app_password"],
            provider=credential["provider"],
            account_name=credential["account_name"],
            imap_server=EmailStatementFetcher.PROVIDER_CONFIG[credential["provider"]]["imap_server"]
        )
    )
    
    statements = fetcher.fetch_recent_statements(
        days_back=30,
        sender_patterns=credential.get("sender_patterns", [])
    )
    
    # Store fetched attachments temporarily
    import_ids = []
    for statement_email in statements:
        for attachment in statement_email["attachments"]:
            import_id = store_fetched_statement(
                attachment["data"],
                attachment["filename"],
                credential["account_name"],
                email_source=statement_email["sender"]
            )
            import_ids.append(import_id)
    
    return jsonify({
        "status": "fetched",
        "statements_found": len(statements),
        "attachments_processed": len(import_ids),
        "import_ids": import_ids
    })

@app.route("/api/email/schedule", methods=["POST"])
def configure_email_schedule():
    """
    Configure automatic checking schedule
    
    Body:
    {
        "frequency": "daily",  # daily, weekly, hourly
        "time": "09:00",       # check at this time (UTC)
        "auto_commit": false,  # auto-commit if confidence > threshold
        "confidence_threshold": 0.85
    }
    """
    config = request.json
    email_credential_state.set_schedule_config(config)
    return jsonify({"status": "scheduled", "config": config})
```

### Background Worker for Scheduled Checks

```python
# backend/statements/email_scheduler.py

import threading
from datetime import datetime, time
from typing import Optional, List
import schedule
import time as time_module

class EmailScheduler:
    """Background worker that periodically checks email for statements"""
    
    def __init__(self, credential_state, import_handler):
        self.credential_state = credential_state
        self.import_handler = import_handler
        self.scheduler = schedule.Scheduler()
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self, frequency: str = "daily", check_time: str = "09:00"):
        """Start background scheduler"""
        if self.running:
            return
        
        # Schedule job
        if frequency == "hourly":
            self.scheduler.every().hour.do(self._check_all_emails)
        elif frequency == "daily":
            hour, minute = map(int, check_time.split(":"))
            self.scheduler.every().day.at(f"{hour:02d}:{minute:02d}").do(self._check_all_emails)
        elif frequency == "weekly":
            hour, minute = map(int, check_time.split(":"))
            self.scheduler.every().monday.at(f"{hour:02d}:{minute:02d}").do(self._check_all_emails)
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        print(f"Email scheduler started (frequency: {frequency}, time: {check_time})")
    
    def stop(self):
        """Stop background scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Email scheduler stopped")
    
    def _run_scheduler(self):
        """Run scheduler loop"""
        while self.running:
            self.scheduler.run_pending()
            time_module.sleep(60)  # Check every minute
    
    def _check_all_emails(self):
        """Check all enabled email credentials"""
        credentials = self.credential_state.list_credentials()
        for credential in credentials:
            if not credential["enabled"]:
                continue
            
            try:
                self._check_single_email(credential)
            except Exception as e:
                print(f"Error checking email {credential['email_address']}: {e}")
    
    def _check_single_email(self, credential: dict):
        """Fetch statements for single email credential"""
        from .email_fetcher import EmailStatementFetcher, EmailCredential
        
        fetcher = EmailStatementFetcher(
            EmailCredential(
                email_address=credential["email_address"],
                app_password=credential["app_password"],
                provider=credential["provider"],
                account_name=credential["account_name"],
                imap_server=EmailStatementFetcher.PROVIDER_CONFIG[credential["provider"]]["imap_server"]
            )
        )
        
        statements = fetcher.fetch_recent_statements(
            days_back=7,  # Check last 7 days
            sender_patterns=credential.get("sender_patterns", [])
        )
        
        for statement_email in statements:
            for attachment in statement_email["attachments"]:
                # Import and optionally auto-commit
                import_id = self.import_handler.import_statement(
                    attachment["data"],
                    attachment["filename"],
                    credential["account_name"]
                )
                
                # Auto-commit if configured
                if credential.get("auto_commit"):
                    self.import_handler.auto_commit(
                        import_id,
                        confidence_threshold=credential.get("confidence_threshold", 0.85)
                    )
        
        # Update last checked timestamp
        self.credential_state.update_last_checked(credential["id"])
```

---

## Approach 2: Bank API Integration (More Reliable)

### Plaid Integration

**What is Plaid?**
- Third-party service that connects to 12,000+ financial institutions
- Handles OAuth authentication, multi-factor auth, etc.
- Returns standardized transaction data
- No need to store passwords

**Setup:**
```bash
pip install plaid-python
```

### Implementation: Plaid Connector

```python
# backend/statements/plaid_connector.py

from plaid import ApiClient, Configuration
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import json

@dataclass
class PlaidConnection:
    """Stored Plaid connection info"""
    id: str
    user_id: str
    access_token: str  # encrypted storage
    item_id: str
    institution_name: str
    institution_id: str
    accounts: List[dict]  # list of connected accounts
    created_at: datetime
    last_synced: Optional[datetime] = None

class PlaidConnector:
    """Connect to banks via Plaid API"""
    
    def __init__(self, client_id: str, secret: str, environment: str = "production"):
        """
        Args:
            client_id: Plaid API client ID
            secret: Plaid API secret
            environment: 'sandbox' or 'production'
        """
        config = Configuration(
            host=getattr(
                plaid.model.environment,
                f"Environment{environment.capitalize()}" if environment != "production" else "PRODUCTION"
            ),
            api_key={
                'clientId': client_id,
                'secret': secret,
            }
        )
        self.client = ApiClient(config)
        self.plaid_api = plaid_api.PlaidApi(self.client)
    
    def create_link_token(self, user_id: str) -> str:
        """
        Generate link token for web flow
        
        User clicks button → opens Plaid Link UI → selects bank & logs in
        → returns public_token → swap for access_token
        
        Returns:
            link_token (user includes in frontend request)
        """
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.country_code import CountryCode
        from plaid.model.products import Products
        
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name="Personal Finance Manager",
            user={"client_user_id": user_id},
            country_codes=[CountryCode("US")],
            language="en"
        )
        
        response = self.plaid_api.link_token_create(request)
        return response.link_token
    
    def exchange_public_token(self, public_token: str) -> dict:
        """
        Exchange public token (from frontend) for access token
        
        Args:
            public_token: Returned from Plaid Link UI
        
        Returns:
            {
                "access_token": "access-...",
                "item_id": "item-...",
                "accounts": [{"id": "...", "name": "Checking", ...}]
            }
        """
        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
        
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = self.plaid_api.item_public_token_exchange(request)
        
        # Fetch accounts
        accounts_request = AccountsGetRequest(access_token=response.access_token)
        accounts_response = self.plaid_api.accounts_get(accounts_request)
        
        return {
            "access_token": response.access_token,
            "item_id": response.item_id,
            "accounts": [
                {
                    "id": acc.account_id,
                    "name": acc.name,
                    "type": acc.type,
                    "subtype": acc.subtype,
                    "mask": acc.mask,
                }
                for acc in accounts_response.accounts
            ]
        }
    
    def fetch_transactions(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
        account_id: Optional[str] = None
    ) -> List[dict]:
        """
        Fetch transactions for date range
        
        Returns standardized transaction data
        """
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date.date(),
            end_date=end_date.date(),
            options={
                "account_ids": [account_id] if account_id else None
            }
        )
        
        response = self.plaid_api.transactions_get(request)
        
        transactions = []
        for txn in response.transactions:
            transactions.append({
                "date": txn.date.isoformat(),
                "amount": txn.amount,
                "description": txn.name,
                "merchant": txn.merchant_name,
                "category": txn.personal_finance_category.primary if txn.personal_finance_category else None,
                "account_id": txn.account_id,
                "pending": txn.pending,
            })
        
        return transactions
```

### Plaid Backend Endpoints

```python
# backend/backend.py (additions)

from backend.statements.plaid_connector import PlaidConnector
from backend.engine.state import PlaidConnectionState

plaid_connector = PlaidConnector(
    client_id=os.getenv("PLAID_CLIENT_ID"),
    secret=os.getenv("PLAID_SECRET"),
    environment=os.getenv("PLAID_ENV", "production")
)
plaid_state = PlaidConnectionState()

@app.route("/api/plaid/link-token", methods=["POST"])
def get_plaid_link_token():
    """
    Initiate Plaid Link flow
    Frontend calls this → gets link_token → opens Plaid UI
    """
    user_id = request.json.get("user_id", "default_user")
    link_token = plaid_connector.create_link_token(user_id)
    
    return jsonify({
        "link_token": link_token,
        "client_id": os.getenv("PLAID_CLIENT_ID")
    })

@app.route("/api/plaid/connect", methods=["POST"])
def connect_plaid_account():
    """
    Complete Plaid Link flow
    Frontend sends public_token from Plaid UI
    """
    public_token = request.json.get("public_token")
    account_name = request.json.get("account_name")
    
    try:
        result = plaid_connector.exchange_public_token(public_token)
        
        # Store connection
        connection_id = plaid_state.add_connection(
            access_token=result["access_token"],
            item_id=result["item_id"],
            institution_name=account_name,
            accounts=result["accounts"]
        )
        
        return jsonify({
            "status": "connected",
            "connection_id": connection_id,
            "accounts": result["accounts"]
        })
    
    except Exception as e:
        return jsonify({"error": f"Connection failed: {str(e)}"}), 400

@app.route("/api/plaid/sync/<connection_id>", methods=["POST"])
def sync_plaid_transactions(connection_id: str):
    """
    Fetch transactions from connected Plaid account
    """
    connection = plaid_state.get_connection(connection_id)
    if not connection:
        return jsonify({"error": "Connection not found"}), 404
    
    start_date = datetime.now() - timedelta(days=90)
    end_date = datetime.now()
    
    transactions = plaid_connector.fetch_transactions(
        access_token=connection["access_token"],
        start_date=start_date,
        end_date=end_date
    )
    
    # Import transactions using statement importer
    import_id = store_transactions_as_statement(
        transactions,
        f"Plaid - {connection['institution_name']}",
        account_name=connection['institution_name']
    )
    
    plaid_state.update_last_synced(connection_id)
    
    return jsonify({
        "status": "synced",
        "transaction_count": len(transactions),
        "import_id": import_id,
        "date_range": f"{start_date.date()} to {end_date.date()}"
    })
```

---

## Approach 3: Web Scraping (Use with Caution)

```python
# backend/statements/web_scraper.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time

class BankScraper:
    """
    Automated login & statement download
    
    ⚠️ SECURITY NOTES:
    - Store credentials encrypted, never in plain text
    - Banks may block/ban automated access (check ToS)
    - Prefer Plaid/email approaches when possible
    - Use headless browser to avoid detection
    """
    
    BANK_PROFILES = {
        "chase": {
            "login_url": "https://www.chase.com",
            "selectors": {
                "username": "#userId",
                "password": "#password",
                "login_button": "#loginSubmitBtn",
                "accounts": ".account-row",
                "download_button": ".download-statement"
            }
        },
        "bofa": {
            "login_url": "https://www.bankofamerica.com",
            # ...similar structure
        }
    }
    
    def __init__(self, bank_name: str, username: str, password: str):
        self.bank_name = bank_name
        self.username = username
        self.password = password
        self.driver = None
    
    def login_and_download(self) -> List[bytes]:
        """Login to bank, navigate to statements, download CSVs"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")  # Don't show browser window
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            self.driver = webdriver.Chrome(options=options)
            profile = self.BANK_PROFILES.get(self.bank_name)
            
            # Login
            self.driver.get(profile["login_url"])
            self.driver.find_element(By.CSS_SELECTOR, profile["selectors"]["username"]).send_keys(self.username)
            self.driver.find_element(By.CSS_SELECTOR, profile["selectors"]["password"]).send_keys(self.password)
            self.driver.find_element(By.CSS_SELECTOR, profile["selectors"]["login_button"]).click()
            
            # Wait for 2FA if needed
            WebDriverWait(self.driver, 30).until(EC.presence_of_elements_by_css_selector(profile["selectors"]["accounts"]))
            
            # Download statements
            download_buttons = self.driver.find_elements(By.CSS_SELECTOR, profile["selectors"]["download_button"])
            statements = []
            for btn in download_buttons:
                btn.click()
                time.sleep(2)  # Wait for download
                # Retrieve from downloads folder (more complex in practice)
            
            return statements
        
        finally:
            if self.driver:
                self.driver.quit()
```

---

## Comparison: Email vs. Plaid vs. Web Scraping

| Feature | Email | Plaid | Web Scraping |
|---------|-------|-------|-------------|
| **Setup Difficulty** | ⭐ Easy | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐ Hard |
| **Security** | ⭐⭐ (store passwords) | ⭐⭐⭐⭐⭐ (OAuth) | ⭐⭐ (unreliable) |
| **Reliability** | ⭐⭐⭐ (bank-dependent) | ⭐⭐⭐⭐⭐ (very reliable) | ⭐⭐ (breaks easily) |
| **Cost** | Free | Free (up to limits) | Free |
| **Bank Coverage** | ~100s | 12,000+ | ~10s (custom per bank) |
| **Data Format** | CSV/PDF | Standardized JSON | HTML/PDF |
| **Maintenance** | Low | None (Plaid updates) | High (banks change UI) |
| **ToS Compliance** | ✅ Yes | ✅ Yes | ❌ Often violates ToS |

**Recommendation:**
- Start with **Email** (most banks support, free, low friction)
- Add **Plaid** if you need real-time access or broader coverage
- Avoid **Web Scraping** (maintenance nightmare)

---

## Full Automation Architecture

### 1. **Setup Phase** (User Actions)

```
User Opens Frontend
  ↓
Settings → "Link Account"
  ↓
Choose: [Email] [Plaid] [Manual Upload]
  ├─ Email: Enter email + app password
  ├─ Plaid: Click "Link Bank" → Plaid UI → select bank + login
  └─ Manual: Upload CSV file
  ↓
System Tests Connection
  ↓
Account Linked & Monitoring Started
```

### 2. **Monitoring Phase** (Background)

```
Scheduled Check (Daily 9 AM)
  ├─ For each Email credential:
  │   ├─ Connect to IMAP
  │   ├─ Search for new statement emails (last 7 days)
  │   ├─ Download attachments
  │   └─ Import & queue for review
  │
  ├─ For each Plaid connection:
  │   ├─ Call Plaid API (last 30 days)
  │   ├─ Fetch transactions
  │   └─ Import & queue for review
  │
  └─ Notify user of new statements
      ├─ Show summary (N transactions, X income, Y spending)
      └─ Option to [Review Now] [Auto-Commit]
```

### 3. **Processing Phase**

```
Statement Imported
  ├─ Parse transactions
  ├─ Categorize (rule-based)
  ├─ Score confidence
  │
  ├─ If confidence ≥ threshold & auto-commit enabled:
  │   └─ Auto-commit to plan
  │       └─ Update simulator & dashboard
  │
  └─ Otherwise:
      └─ Queue in review table
          └─ Wait for user action
              ├─ [Edit categories]
              ├─ [Merge with existing rows]
              └─ [Commit to plan]
```

---

## Storage: Encrypted Credentials

### Option 1: File-Based (Cryptography Library)

```python
# backend/engine/credential_storage.py

from cryptography.fernet import Fernet
import json
import os

class CredentialStorage:
    """Securely store email/API credentials"""
    
    def __init__(self, key_path: str = "user_data/.encryption_key"):
        self.key_path = key_path
        self._ensure_key()
        self.cipher = Fernet(self._load_key())
    
    def _ensure_key(self):
        """Create encryption key if doesn't exist"""
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, 'wb') as f:
                f.write(key)
            os.chmod(self.key_path, 0o600)  # Read-only
    
    def _load_key(self) -> bytes:
        """Load encryption key"""
        with open(self.key_path, 'rb') as f:
            return f.read()
    
    def encrypt(self, data: str) -> str:
        """Encrypt string"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def save_credential(self, name: str, cred_dict: dict) -> None:
        """Save encrypted credential"""
        encrypted = self.encrypt(json.dumps(cred_dict))
        path = f"user_data/credentials/{name}.enc"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(encrypted)
    
    def load_credential(self, name: str) -> dict:
        """Load encrypted credential"""
        path = f"user_data/credentials/{name}.enc"
        with open(path, 'r') as f:
            encrypted = f.read()
        return json.loads(self.decrypt(encrypted))
```

### Option 2: Environment Variables (Simplest)

```bash
# .env file (git-ignored)
PLAID_CLIENT_ID=xxx
PLAID_SECRET=xxx
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
CHASE_USERNAME=myemail@gmail.com
# ... etc
```

---

## Requirements Update

```txt
flask>=2.3,<3.0
pandas>=2.1,<3.0

# Email fetching
imap-tools>=1.5.0

# Bank API integration
plaid-python>=20.0.0

# Encryption
cryptography>=41.0.0

# Scheduling
schedule>=1.2.0

# Optional: Web scraping (NOT recommended)
# selenium>=4.0.0
# webdriver-manager>=4.0.0

# Optional: Enhanced PDF parsing
# pdfplumber>=0.10.0
```

---

## Deployment Considerations

### Local (Single User)
✅ Email + File-based encryption = sufficient
✅ Run Flask with APScheduler for background tasks

### Production (Multiple Users)
❌ Don't store plaintext credentials
✅ Use environment variables or secrets manager
✅ Use Plaid instead of email/web scraping (more secure)
✅ Run background worker on separate process/server
✅ Implement rate limiting (banks block aggressive requests)

### Docker Setup

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Background scheduler runs in separate container
CMD ["python", "backend/statements/email_scheduler_daemon.py"]
```

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports:
      - "8000:5000"
    env_file: .env
    volumes:
      - ./user_data:/app/user_data

  scheduler:
    build: .
    command: python backend/statements/email_scheduler_daemon.py
    env_file: .env
    volumes:
      - ./user_data:/app/user_data
```

---

## Configuration Example

```json
// user_data/automation_config.json
{
  "email_monitoring": {
    "enabled": true,
    "frequency": "daily",
    "check_time": "09:00",
    "days_lookback": 7,
    "credentials": [
      {
        "id": "cred-1",
        "email_address": "user@gmail.com",
        "provider": "gmail",
        "account_name": "Checking Account",
        "enabled": true,
        "sender_patterns": [
          "statements@chase.com",
          "statement@chase.com",
          "*noreply@chase*"
        ],
        "auto_commit": false
      }
    ]
  },
  "plaid": {
    "enabled": false,
    "connections": []
  },
  "auto_commit": {
    "enabled": false,
    "confidence_threshold": 0.90,
    "skip_review": false
  },
  "notifications": {
    "email_on_new_statement": true,
    "desktop_notification": true,
    "slack_webhook": null
  }
}
```

---

## Next Steps: Implementation Priority

1. **Email Fetcher** (highest ROI, lowest effort)
   - Most banks email statements
   - Minimal setup friction
   - No API keys needed

2. **Background Scheduler** (enables full automation)
   - Runs periodically
   - Triggers email fetcher
   - Handles failures gracefully

3. **Plaid Integration** (optional, for broader coverage)
   - Real-time data
   - No password storage
   - Better UX

4. **Auto-Commit Logic** (optional, trust after testing)
   - High-confidence transactions skip review
   - Saves manual work
   - Configurable threshold

---

Would you like me to implement:
- ✅ Email fetcher + IMAP integration?
- ✅ Background scheduler daemon?
- ✅ Frontend for credential management?
- ✅ Plaid integration setup?
- ✅ All of the above?
