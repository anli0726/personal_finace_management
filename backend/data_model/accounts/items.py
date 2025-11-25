from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class AccountItem:
    name: str
    category: str
    principal: float
    apr: float = 0.0
    interest_rate: float = 0.0
    start_year: float = 0.0
    end_year: float = 0.0
    end_action: str = "keep"

    def normalized_category(self) -> str:
        return self.category.lower()

    def monthly_rate(self) -> float:
        rate = self.apr if self.apr != 0 else self.interest_rate
        return rate / 12.0


def dataframe_to_accounts(df: pd.DataFrame) -> List[AccountItem]:
    items: List[AccountItem] = []
    for row in df.to_dict("records"):
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        principal = float(row.get("Principal", 0.0) or 0.0)
        if principal == 0.0:
            continue
        items.append(
            AccountItem(
                name=name,
                category=str(row.get("Category", "asset")).lower(),
                principal=principal,
                apr=float(row.get("APR (%)", 0.0) or 0.0) / 100.0,
                interest_rate=float(row.get("Interest Rate (%)", 0.0) or 0.0) / 100.0,
                start_year=float(row.get("Start Year", 0.0) or 0.0),
                end_year=float(row.get("End Year", 0.0) or 0.0),
                end_action=str(row.get("Action at End", "keep")),
            )
        )
    return items

