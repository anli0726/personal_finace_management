from __future__ import annotations

from .constants import ACCOUNT_CATEGORIES, END_ACTION_OPTIONS
from .defaults import default_account_rows
from ..base import ColumnDefinition, TableModel


class AccountTableModel(TableModel):
    """Schema + defaults for account-style rows."""

    def __init__(self) -> None:
        columns = [
            ColumnDefinition("Name", "Name"),
            ColumnDefinition(
                "Category",
                "Category",
                kind="select",
                default="asset",
                options=ACCOUNT_CATEGORIES,
                help="cash/asset/debt/investment",
            ),
            ColumnDefinition(
                "Principal",
                "Amount (USD)",
                kind="number",
                default=0.0,
                min_value=0.0,
                step=500.0,
                format="%.2f",
            ),
            ColumnDefinition("APR (%)", "APR (%)", kind="number", default=0.0, step=0.25, help="年化報酬（可負）"),
            ColumnDefinition(
                "Interest Rate (%)",
                "Interest Rate (%)",
                kind="number",
                default=0.0,
                step=0.25,
                help="替代 APR 用於存款",
            ),
            ColumnDefinition("Start Month", "Start Month", kind="select", default="", options=None, help="開始月份"),
            ColumnDefinition("End Month", "End Month (empty=all)", kind="select", default="", options=None, help="結束月份（空白=全期間）"),
            ColumnDefinition(
                "Action at End",
                "Action at End",
                kind="select",
                default="keep",
                options=END_ACTION_OPTIONS,
                help="期末行為",
            ),
        ]

        super().__init__("accounts", columns, default_account_rows())

