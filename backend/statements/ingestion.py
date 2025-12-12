"""CSV ingestion utilities for statement tracking.

Provides functions to initialize DB schema, compute hashes, save attachments,
and import CSV bytes into the SQLite transactions DB with deduplication.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import os
import sqlite3
import uuid
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "user_data")
LEDGER_DIR = os.path.join(DATA_DIR, "ledger")
STATEMENTS_DIR = os.path.join(DATA_DIR, "statements")
ATTACHMENTS_DIR = os.path.join(STATEMENTS_DIR, "attachments")
DB_PATH = os.path.join(LEDGER_DIR, "transactions.sqlite")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_dirs() -> None:
    os.makedirs(LEDGER_DIR, exist_ok=True)
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)


def ensure_db() -> None:
    """Create DB file and run schema if missing."""
    ensure_dirs()
    need_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    if need_init:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
    conn.close()


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def transaction_hash(date: str, amount: float, description: str, account: str) -> str:
    canonical = f"{date}|{amount:.2f}|{(description or '').strip().lower()}|{(account or '').lower()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_attachment(import_id: str, filename: str, data: bytes) -> str:
    safe_name = filename.replace("/", "_")
    dest_name = f"{import_id}__{safe_name}"
    dest_path = os.path.join(ATTACHMENTS_DIR, dest_name)
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path


def parse_csv_rows(file_bytes: bytes) -> list[Dict[str, Any]]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    rows = [r for r in reader]
    return rows


def parse_transaction_chase(row: Dict[str, Any]) -> tuple[str, float, str, str] | None:
    """Parse Chase credit card CSV format.
    
    Returns (date, amount, description, category) or None if parsing fails.
    Chase format: Transaction Date, Post Date, Description, Category, Type, Amount
    
    Chase convention: negative = spending, positive = refund/payment
    This matches our normalized convention, so we keep as-is.
    """
    date = (row.get("Transaction Date") or "").strip()
    desc = (row.get("Description") or "").strip()
    category = (row.get("Category") or "").strip()
    
    if not date or not desc:
        return None
    
    amount_str = (row.get("Amount") or "").strip()
    if not amount_str:
        return None
    
    try:
        amount = float(amount_str.replace("$", "").replace(",", "").replace("\u2009", ""))
        # Chase already uses correct convention: negative for spending, positive for income
        return (date, amount, desc, category)
    except (ValueError, AttributeError):
        return None


def parse_transaction_citi(row: Dict[str, Any]) -> tuple[str, float, str, str] | None:
    """Parse Citi credit card CSV format.
    
    Returns (date, amount, description, category) or None if parsing fails.
    Citi format: Status, Date, Description, Debit, Credit, Member Name
    
    Citi convention: Debit (positive) = spending, Credit (positive) = payment
    We normalize to: negative = spending, positive = income/payment
    So: Debit becomes negative, Credit stays positive (but is payment, so goes to positive)
    """
    date = (row.get("Date") or "").strip()
    desc = (row.get("Description") or "").strip()
    
    if not date or not desc:
        return None
    
    amount = 0.0
    debit = (row.get("Debit") or "").strip()
    credit = (row.get("Credit") or "").strip()

    # Citi format: Debit = spending (positive value), Credit = payment/refund (any sign)
    # Normalize to: negative = spending/expense, positive = payment/income/refund

    # If Debit column is present and non-empty, treat as spending (negative)
    if debit:
        try:
            amount = -abs(float(debit.replace("$", "").replace(",", "").replace("\u2009", "")))
            return (date, amount, desc, "")
        except (ValueError, AttributeError):
            pass

    # If Credit column is present and non-empty, treat as payment/refund (positive, even if negative in CSV)
    if credit:
        try:
            amount = abs(float(credit.replace("$", "").replace(",", "").replace("\u2009", "")))
            return (date, amount, desc, "")
        except (ValueError, AttributeError):
            pass

    # If both are empty or neither parsed, this is an error
    return None


def parse_transaction_generic(row: Dict[str, Any]) -> tuple[str, float, str, str] | None:
    """Parse generic CSV format with Amount, Debit/Credit, or similar columns."""
    date = (row.get("Date") or row.get("date") or row.get("Transaction Date") or "").strip()
    desc = (row.get("Description") or row.get("description") or row.get("Transaction Description") or "").strip()
    category = (row.get("Category") or row.get("category") or "").strip()
    
    if not date or not desc:
        return None
    
    amount = 0.0
    amount_raw = (row.get("Amount") or row.get("amount") or row.get("Debit/Credit") or row.get("Value") or "").strip()
    
    if amount_raw:
        amt = amount_raw.replace("$", "").replace(",", "").replace("\u2009", "")
        try:
            amount = float(amt)
        except (ValueError, AttributeError):
            return None
    else:
        # Try separate Debit/Credit columns
        debit = (row.get("Debit") or "").strip()
        credit = (row.get("Credit") or "").strip()
        
        if debit and debit.upper() != "DEBIT":
            try:
                amount = float(debit.replace("$", "").replace(",", "").replace("\u2009", ""))
            except (ValueError, AttributeError):
                pass
        elif credit and credit.upper() != "CREDIT":
            try:
                amount = -float(credit.replace("$", "").replace(",", "").replace("\u2009", ""))
            except (ValueError, AttributeError):
                pass
        else:
            return None
    
    return (date, amount, desc, category)


def import_csv_bytes(file_bytes: bytes, filename: str, account_name: str, bank: str | None = None, force: bool = False) -> Dict[str, Any]:
    """Import a CSV (bytes) into the ledger DB.

    Args:
        file_bytes: CSV file content as bytes
        filename: Original filename
        account_name: Account name to associate with transactions
        bank: Bank name (used to select parser: "citi", "chase", etc.)
        force: If True, bypass deduplication check and re-import file

    Returns summary dict with import_id and counts.
    """
    ensure_db()
    fhash = sha256_bytes(file_bytes)
    import_id = f"import-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{str(uuid.uuid4())[:8]}"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check file hash (unless force=True)
    if not force:
        cur.execute("SELECT import_id FROM imports WHERE file_hash = ?", (fhash,))
        if cur.fetchone():
            conn.close()
            return {"error": "File already imported", "imported": False}

    # Parse rows
    try:
        rows = parse_csv_rows(file_bytes)
    except Exception as e:
        conn.close()
        return {"error": f"Failed to parse CSV: {e}", "imported": False}

    # Insert imports record
    cur.execute(
        "INSERT INTO imports(import_id, account_name, source, filename, file_hash, rows_expected) VALUES (?,?,?,?,?,?)",
        (import_id, account_name, "csv", filename, fhash, len(rows)),
    )

    # Save attachment
    saved_path = save_attachment(import_id, filename, file_bytes)
    cur.execute(
        "INSERT INTO attachments(import_id, path, filename, size, mime_type) VALUES (?,?,?,?,?)",
        (import_id, os.path.relpath(saved_path, DATA_DIR), filename, len(file_bytes), "text/csv"),
    )

    # Select parser based on bank
    if bank == "citi":
        parser = parse_transaction_citi
    elif bank == "chase":
        parser = parse_transaction_chase
    else:
        parser = parse_transaction_generic

    parsed = 0
    duplicate = 0
    errors = 0
    for r in rows:
        try:
            result = parser(r)
            if not result:
                errors += 1
                continue
            
            date, amount, desc, category = result

            txnid = transaction_hash(date, amount, desc, account_name)
            raw_json = json.dumps(r, ensure_ascii=False)
            try:
                cur.execute(
                    "INSERT INTO transactions(txn_id, import_id, date, amount, description, account, category, raw_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (txnid, import_id, date, amount, desc, account_name, category, raw_json, datetime.datetime.utcnow(), datetime.datetime.utcnow()),
                )
                parsed += 1
            except sqlite3.IntegrityError:
                duplicate += 1
        except Exception:
            errors += 1

    cur.execute(
        "UPDATE imports SET rows_parsed = ?, rows_duplicate = ?, rows_error = ?, updated_at = CURRENT_TIMESTAMP WHERE import_id = ?",
        (parsed, duplicate, errors, import_id),
    )
    conn.commit()
    conn.close()

    return {
        "import_id": import_id,
        "filename": filename,
        "rows_expected": len(rows),
        "rows_parsed": parsed,
        "rows_duplicate": duplicate,
        "rows_error": errors,
        "saved_path": os.path.relpath(saved_path, BASE_DIR),
    }


def list_transactions(limit: int = 100, offset: int = 0, account: str | None = None) -> list[Dict[str, Any]]:
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sql = "SELECT txn_id, date, amount, description, merchant, category, account, currency, reconciled FROM transactions"
    params = []
    if account:
        sql += " WHERE account = ?"
        params.append(account)
    sql += " ORDER BY date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cur.execute(sql, tuple(params))
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows
