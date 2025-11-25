"""REST backend for personal financial scenarios."""

from __future__ import annotations

import os
import sys

import math
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, jsonify, request

from backend.data_model import (
    AccountItem,
    AccountTableModel,
    CashflowItem,
    IncomeTableModel,
    PlanConfig,
    SpendingTableModel,
)
from backend.engine.aggregate import aggregate_period
from backend.engine.simulator import simulate_monthly
from backend.engine.state import ScenarioState

app = Flask(__name__)

state = ScenarioState()

ACCOUNT_MODEL = AccountTableModel()
INCOME_MODEL = IncomeTableModel()
SPENDING_MODEL = SpendingTableModel()


def month_string_to_year_offset(month_str: str, plan_start_year: int) -> float:
    if not month_str or not str(month_str).strip():
        return 0.0
    try:
        year, month = map(int, str(month_str).split("-"))
        offset = (year - plan_start_year) + (month - 1) / 12.0
        return max(0.0, offset)
    except (ValueError, TypeError):
        return 0.0


def generate_month_options(start_year: int, years: int) -> list[str]:
    months: list[str] = []
    if not start_year or not years:
        return months
    for year in range(int(start_year), int(start_year) + int(years)):
        for month in range(1, 13):
            months.append(f"{year}-{month:02d}")
    return months


def is_taxable_income_category(category: str) -> bool:
    return str(category).strip().lower() in {"salary", "bonus", "business"}


def parse_accounts(rows: list[dict], plan_start_year: int) -> list[AccountItem]:
    accounts: list[AccountItem] = []
    for row in rows or []:
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        principal = float(row.get("Amount (USD)", row.get("Principal", 0.0)) or 0.0)
        if principal == 0.0:
            continue
        start_month = str(row.get("Start Month", "")).strip()
        end_month = str(row.get("End Month", "")).strip()
        accounts.append(
            AccountItem(
                name=name,
                category=str(row.get("Category", "asset")).lower(),
                principal=principal,
                apr=float(row.get("APR (%)", 0.0) or 0.0) / 100.0,
                interest_rate=float(row.get("Interest Rate (%)", 0.0) or 0.0) / 100.0,
                start_year=month_string_to_year_offset(start_month, plan_start_year),
                end_year=0.0 if not end_month else month_string_to_year_offset(end_month, plan_start_year),
                end_action=str(row.get("Action at End", "keep")),
            )
        )
    return accounts


def parse_cashflows(rows: list[dict], plan_start_year: int, flow_type: str) -> list[CashflowItem]:
    flows: list[CashflowItem] = []
    for row in rows or []:
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        amount = float(row.get("Annual Amount", 0.0) or 0.0)
        if amount == 0.0:
            continue
        start_month = str(row.get("Start Month", "")).strip()
        end_month = str(row.get("End Month", "")).strip()
        category = str(row.get("Category", "other"))
        flows.append(
            CashflowItem(
                name=name,
                annual_amount=amount,
                category=category,
                start_year=month_string_to_year_offset(start_month, plan_start_year),
                end_year=0.0 if not end_month else month_string_to_year_offset(end_month, plan_start_year),
                flow_type=flow_type,
                taxable=is_taxable_income_category(category) if flow_type == "income" else False,
            )
        )
    return flows


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _sanitize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clean_rows: List[Dict[str, Any]] = []
    for row in records:
        clean_rows.append({key: (None if _is_nan(value) else value) for key, value in row.items()})
    return clean_rows


def _model_payload(model: AccountTableModel | IncomeTableModel | SpendingTableModel) -> Dict[str, Any]:
    columns: List[Dict[str, Any]] = []
    month_fields: List[str] = []
    for col in model.columns:
        columns.append(
            {
                "field": col.field,
                "label": col.label,
                "kind": col.kind,
                "default": col.default,
                "options": col.options or [],
                "min": col.min_value,
                "step": col.step,
                "format": col.format,
                "help": col.help,
            }
        )
        if col.kind == "select" and not col.options:
            month_fields.append(col.field)
    defaults = _sanitize_records(model.create_default_df().to_dict("records"))
    return {
        "name": model.name,
        "columns": columns,
        "defaults": defaults,
        "monthFields": month_fields,
    }


def _aggregated_payload(freq: str) -> Dict[str, Any]:
    freq = (freq or "Q").upper()
    monthly_all = state.get_all_monthly()
    if monthly_all.empty:
        return {"scenarios": state.list_names(), "data": [], "freq": freq}
    agg_df = aggregate_period(monthly_all, freq=freq)
    return {
        "scenarios": state.list_names(),
        "freq": freq,
        "data": agg_df.to_dict(orient="records"),
    }


def _extract_payload_value(payload: dict, *keys: str, default=None):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


@app.after_request
def apply_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.get("/api/health")
def healthcheck():
    return jsonify({"status": "ok"})


@app.get("/api/schema")
def get_schema():
    payload = {
        "planDefaults": {
            "name": "MyPlan",
            "startYear": 2024,
            "years": 5,
            "taxRate": 25.0,
            "freq": "Q",
        },
        "accounts": _model_payload(ACCOUNT_MODEL),
        "incomes": _model_payload(INCOME_MODEL),
        "spendings": _model_payload(SPENDING_MODEL),
        "freqOptions": [
            {"label": "Monthly", "value": "M"},
            {"label": "Quarterly", "value": "Q"},
            {"label": "Yearly", "value": "Y"},
        ],
    }
    return jsonify(payload)


@app.get("/api/months")
def month_options():
    start_year = int(request.args.get("startYear", 2024))
    years = int(request.args.get("years", 1))
    months = generate_month_options(start_year, years)
    return jsonify({"months": months})


@app.get("/api/scenarios")
def list_scenarios():
    freq = request.args.get("freq", "Q")
    return jsonify(_aggregated_payload(freq))


@app.post("/api/scenarios")
def add_scenario():
    payload = request.get_json(silent=True) or {}
    freq = str(_extract_payload_value(payload, "freq", "frequency", default="Q") or "Q").upper()
    try:
        name = str(_extract_payload_value(payload, "name", "planName", default="Scenario")).strip() or "Scenario"
        start_year = int(_extract_payload_value(payload, "startYear", "planStartYear", default=2024))
        years = int(_extract_payload_value(payload, "years", "planYears", default=1))
        tax_rate = float(_extract_payload_value(payload, "taxRate", "tax_rate", default=0.0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid plan parameters."}), 400

    account_rows = payload.get("accounts") or payload.get("accountRows") or []
    income_rows = payload.get("income") or payload.get("incomes") or []
    spending_rows = payload.get("spending") or payload.get("spendings") or payload.get("expenses") or []

    accounts_list = parse_accounts(account_rows, start_year)
    if not accounts_list:
        return jsonify({"error": "At least one account with a non-zero principal is required."}), 400
    income_list = parse_cashflows(income_rows, start_year, "income")
    spending_list = parse_cashflows(spending_rows, start_year, "spending")

    cfg = PlanConfig(
        name=name,
        start_year=start_year,
        years=years,
        tax_rate=tax_rate / 100.0,
        accounts=accounts_list,
        incomes=income_list,
        spendings=spending_list,
    )

    df_monthly = simulate_monthly(cfg)
    state.add_scenario(name, df_monthly)
    return jsonify(_aggregated_payload(freq))


@app.delete("/api/scenarios")
def clear_scenarios():
    state.clear()
    return jsonify({"message": "All scenarios cleared.", "scenarios": []})


if __name__ == "__main__":
    app.run(debug=True, port=8000)
