import pandas as pd

from ..data_model import AccountItem, CashflowItem, PlanConfig

LIQUID_CATEGORIES = {"cash", "investment"}


def _build_account_state(item: AccountItem, n_months: int) -> dict:
    start_m = max(0, int(round(item.start_year * 12)))
    end_m = n_months - 1 if item.end_year <= 0 else min(int(round(item.end_year * 12)), n_months - 1)
    if end_m < start_m:
        end_m = start_m
    initial_value = item.principal
    if item.normalized_category() == "debt":
        initial_value = -abs(initial_value)
    return {
        "item": item,
        "value": 0.0,
        "initial_value": initial_value,
        "rate_m": item.monthly_rate(),
        "start_m": start_m,
        "end_m": end_m,
        "active": False,
        "completed": False,
        "taxable_investment": item.normalized_category() == "investment" and "hsa" not in item.name.lower(),
    }


def _build_cashflow_state(item: CashflowItem, n_months: int) -> dict:
    start_m = max(0, int(round(item.start_year * 12)))
    end_m = n_months - 1 if item.end_year <= 0 else min(int(round(item.end_year * 12)), n_months - 1)
    if end_m < start_m:
        end_m = start_m
    return {
        "item": item,
        "start_m": start_m,
        "end_m": end_m,
        "amount_m": item.amount_per_month(),
        "taxable": getattr(item, "taxable", False),
        "inflation_rate": getattr(item, "inflation_rate", 0.0) or 0.0,
    }


def _ensure_primary_cash(states: list[dict], n_months: int) -> dict:
    cash_states = [s for s in states if s["item"].normalized_category() == "cash"]
    if cash_states:
        return cash_states[0]
    virtual_cash = AccountItem(name="Cash Reserve", category="cash", principal=0.0, end_year=0.0)
    cash_state = _build_account_state(virtual_cash, n_months)
    cash_state["active"] = True
    states.insert(0, cash_state)
    return cash_state


def simulate_monthly(cfg: PlanConfig) -> pd.DataFrame:
    n_months = max(1, cfg.years * 12)
    tax_rate = cfg.tax_rate or 0.0

    account_states = [_build_account_state(item, n_months) for item in cfg.accounts]
    income_states = [_build_cashflow_state(item, n_months) for item in cfg.incomes]
    spending_states = [_build_cashflow_state(item, n_months) for item in cfg.spendings]

    primary_cash = _ensure_primary_cash(account_states, n_months)
    records = []
    cash_buffer = 0.0

    for m in range(n_months):
        year_num = m // 12
        month_in_year = (m % 12) + 1
        calendar_year = cfg.start_year + year_num
        month_label = f"{calendar_year}-{month_in_year:02d}"

        def _sum_cashflow(states: list[dict]) -> float:
            return sum(state["amount_m"] for state in states if state["start_m"] <= m <= state["end_m"])

        total_income = _sum_cashflow(income_states)
        total_spending = 0.0
        taxable_income = sum(
            state["amount_m"]
            for state in income_states
            if state["start_m"] <= m <= state["end_m"] and state.get("taxable", False)
        )

        for state in account_states:
            if state.get("completed"):
                continue
            if m >= state["start_m"] and not state["active"]:
                state["value"] = state["initial_value"]
                state["active"] = True

        taxable_investment_growth = 0.0
        for state in account_states:
            if not state["active"] or state.get("completed"):
                continue
            if m <= state["end_m"] and state.get("taxable_investment", False):
                monthly_yield = max(0.0, state["value"] * state["rate_m"])
                taxable_investment_growth += monthly_yield

        taxable_base = taxable_income + taxable_investment_growth
        tax_amount = taxable_base * tax_rate
        net_cashflow = total_income - total_spending - tax_amount

        if primary_cash["active"]:
            primary_cash["value"] += cash_buffer
            cash_buffer = 0.0
            primary_cash["value"] += net_cashflow
        else:
            cash_buffer += net_cashflow

        for state in account_states:
            if not state["active"] or state.get("completed"):
                continue
            if m <= state["end_m"]:
                state["value"] *= 1 + state["rate_m"]

        for state in account_states:
            if state["active"] and m == state["end_m"]:
                action = state["item"].end_action
                if action == "liquidate_to_cash":
                    primary_cash["value"] += state["value"]
                    state["value"] = 0.0
                    state["active"] = False
                    state["completed"] = True
                elif action == "drop":
                    state["value"] = 0.0
                    state["active"] = False
                    state["completed"] = True
                else:
                    state["rate_m"] = 0.0

        for state in spending_states:
            if not (state["start_m"] <= m <= state["end_m"]):
                continue
            years_elapsed = max(0.0, (m - state["start_m"]) / 12.0)
            rate = state.get("inflation_rate", 0.0) or 0.0
            multiplier = (1.0 + rate) ** years_elapsed if rate else 1.0
            total_spending += state["amount_m"] * multiplier

        snapshot = {
            "Scenario": cfg.name,
            "MonthIndex": m,
            "Month": month_label,
            "CalendarYear": calendar_year,
            "MonthInYear": month_in_year,
            "TotalIncome": total_income,
            "TotalSpending": total_spending,
            "TaxableIncome": taxable_income,
            "TaxableInvestmentGrowth": taxable_investment_growth,
            "TaxableBase": taxable_base,
            "TotalTax": tax_amount,
            "NetCashflow": net_cashflow,
        }

        total_assets = 0.0
        total_debt = 0.0
        liquid_total = 0.0

        for state in account_states:
            label = state["item"].name
            snapshot[label] = state["value"]
            if state["value"] >= 0:
                total_assets += state["value"]
            else:
                total_debt += state["value"]

            if state["item"].normalized_category() in LIQUID_CATEGORIES:
                liquid_total += state["value"]

        snapshot["Liquid"] = liquid_total
        snapshot["NetWorth"] = total_assets + total_debt
        records.append(snapshot)

    return pd.DataFrame(records)
