from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

import pandas as pd


@dataclass
class ColumnDefinition:
    """Lightweight schema descriptor used by Streamlit editors."""

    field: str
    label: str
    kind: str = "text"  # text | number | select
    default: Any = ""
    options: List[str] | None = None
    min_value: float | None = None
    step: float | None = None
    format: str | None = None
    help: str | None = None


@dataclass
class TableModel:
    """Container for a table schema plus default rows."""

    name: str
    columns: List[ColumnDefinition]
    default_rows: List[dict[str, Any]] = field(default_factory=list)

    def create_default_df(self) -> pd.DataFrame:
        if self.default_rows:
            return pd.DataFrame(self.default_rows)
        seed = {col.field: col.default for col in self.columns}
        return pd.DataFrame([seed])

