# engine/storage.py
import os
import json
import pandas as pd
from typing import Dict

def ensure_user_data_dir(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

def save_scenarios(path: str, scenario_dict: Dict[str, pd.DataFrame]) -> None:
    ensure_user_data_dir(path)
    data = {}
    for name, df in scenario_dict.items():
        data[name] = df.to_dict(orient="records")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_scenarios(path: str) -> Dict[str, pd.DataFrame]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
            if not raw_text:
                return {}
            raw = json.loads(raw_text)
    except (json.JSONDecodeError, OSError):
        return {}
    res = {}
    for name, records in raw.items():
        res[name] = pd.DataFrame(records)
    return res
