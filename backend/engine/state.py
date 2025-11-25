# engine/state.py
from typing import Dict
import pandas as pd
from .storage import load_scenarios, save_scenarios

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
