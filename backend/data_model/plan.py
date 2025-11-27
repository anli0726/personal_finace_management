# data_model/plan.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .accounts import AccountItem
from .cashflow import CashflowItem


@dataclass
class PlanConfig:
    name: str
    start_year: int
    years: int
    tax_rate: float = 0.0
    accounts: List[AccountItem] = field(default_factory=list)
    incomes: List[CashflowItem] = field(default_factory=list)
    spendings: List[CashflowItem] = field(default_factory=list)
    living_inflation_rate: float = 0.0
