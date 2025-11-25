# engine/state.py
from typing import Dict
import pandas as pd
from .storage import (
    load_scenarios,
    save_scenarios,
    load_plans,
    save_plans,
    load_layout,
    save_layout,
)

class ScenarioState:
    def __init__(self, storage_path: str = "user_data/scenarios.json"):
        self.storage_path = storage_path
        self.scenarios: Dict[str, pd.DataFrame] = load_scenarios(storage_path)

    def add_scenario(self, name: str, df: pd.DataFrame) -> None:
        self.scenarios[name] = df
        self._save()

    def clear(self) -> None:
        self.scenarios = {}
        self._save()

    def _save(self):
        save_scenarios(self.storage_path, self.scenarios)

    def get_all_monthly(self) -> pd.DataFrame:
        if not self.scenarios:
            return pd.DataFrame()
        return pd.concat(self.scenarios.values(), ignore_index=True)

    def list_names(self):
        return list(self.scenarios.keys())


class PlanState:
    def __init__(self, storage_path: str = "user_data/plans.json"):
        self.storage_path = storage_path
        self.plans: Dict[str, dict] = load_plans(storage_path)

    def list_names(self):
        return sorted(self.plans.keys())

    def get(self, name: str) -> dict | None:
        return self.plans.get(name)

    def save(self, name: str, payload: dict) -> None:
        self.plans[name] = payload
        self._save()

    def delete(self, name: str) -> None:
        if name in self.plans:
            del self.plans[name]
            self._save()

    def _save(self) -> None:
        save_plans(self.storage_path, self.plans)


class LayoutState:
    def __init__(self, storage_path: str = "user_data/layout.json"):
        self.storage_path = storage_path
        self.layout = load_layout(storage_path)

    def get(self):
        return self.layout

    def save(self, layout: list[dict]) -> None:
        self.layout = layout or []
        save_layout(self.storage_path, self.layout)
