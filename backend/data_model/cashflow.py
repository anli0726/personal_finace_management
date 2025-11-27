from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

import pandas as pd

from .base import ColumnDefinition, TableModel

INCOME_CATEGORIES = ["salary", "bonus", "rental", "business", "other"]
SPENDING_CATEGORIES = ["living", "parents", "debt", "health", "other"]


def _income_defaults() -> List[dict[str, float | str]]:
    return [
        {
            "Name": "Household Salary",
            "Category": "salary",
            "Annual Amount": 75000.0,
            "Start Month": "",
            "End Month": "",
        },
        {
            "Name": "Other Income",
            "Category": "other",
            "Annual Amount": 6000.0,
            "Start Month": "",
            "End Month": "",
        }
    ]


def _spending_defaults() -> List[dict[str, float | str]]:
    return [
        {
            "Name": "Household Expenses",
            "Category": "living",
            "Annual Amount": 36000.0,
            "Start Month": "",
            "End Month": "",
        },
        {
            "Name": "Debt Payments",
            "Category": "debt",
            "Annual Amount": 6000.0,
            "Start Month": "",
            "End Month": "",
        },
    ]


class IncomeTableModel(TableModel):
    def __init__(self) -> None:
        columns = [
            ColumnDefinition("Name", "Name"),
            ColumnDefinition(
                "Category",
                "Category",
                kind="select",
                default="salary",
                options=INCOME_CATEGORIES,
            ),
            ColumnDefinition(
                "Annual Amount",
                "Annual Amount (USD)",
                kind="number",
                default=0.0,
                min_value=0.0,
                step=1000.0,
                format="%.2f",
            ),
            ColumnDefinition("Start Month", "Start Month", kind="select", default="", options=None, help="開始月份"),
            ColumnDefinition("End Month", "End Month (empty=all)", kind="select", default="", options=None, help="結束月份（空白=全期間）"),
        ]
        super().__init__("income", columns, _income_defaults())


class SpendingTableModel(TableModel):
    def __init__(self) -> None:
        columns = [
            ColumnDefinition("Name", "Name"),
            ColumnDefinition(
                "Category",
                "Category",
                kind="select",
                default="living",
                options=SPENDING_CATEGORIES,
            ),
            ColumnDefinition(
                "Annual Amount",
                "Annual Amount (USD)",
                kind="number",
                default=0.0,
                min_value=0.0,
                step=1000.0,
                format="%.2f",
            ),
            ColumnDefinition("Start Month", "Start Month", kind="select", default="", options=None, help="開始月份"),
            ColumnDefinition("End Month", "End Month (empty=all)", kind="select", default="", options=None, help="結束月份（空白=全期間）"),
        ]
        super().__init__("spending", columns, _spending_defaults())


@dataclass
class CashflowItem:
    name: str
    annual_amount: float
    category: str
    start_year: float = 0.0
    end_year: float = 0.0
    flow_type: Literal["income", "spending"] = "income"
    taxable: bool = False
    inflation_rate: float = 0.0

    def amount_per_month(self) -> float:
        return self.annual_amount / 12.0


def dataframe_to_cashflows(df: pd.DataFrame, flow_type: Literal["income", "spending"]) -> List[CashflowItem]:
    rows: List[CashflowItem] = []
    for row in df.to_dict("records"):
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        amount = float(row.get("Annual Amount", 0.0) or 0.0)
        if amount == 0.0:
            continue
        inflation_rate = float(row.get("Inflation Rate (%)", 0.0) or 0.0) / 100.0
        rows.append(
            CashflowItem(
                name=name,
                annual_amount=amount,
                category=str(row.get("Category", "other")),
                start_year=float(row.get("Start Year", 0.0) or 0.0),
                end_year=float(row.get("End Year", 0.0) or 0.0),
                flow_type=flow_type,
                taxable=bool(row.get("Taxable", False)),
                inflation_rate=inflation_rate if flow_type == "spending" else 0.0,
            )
        )
    return rows
