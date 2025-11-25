# engine/storage.py
import os
import json
import math
import pandas as pd
from typing import Dict, List, Any


def ensure_user_data_dir(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


def _sanitize_json_compat(value: Any):
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {key: _sanitize_json_compat(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_compat(item) for item in value]
    return value


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


def load_plans(path: str) -> Dict[str, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
            if not raw_text:
                return {}
            data = json.loads(raw_text)
            return _sanitize_json_compat(data)
    except (json.JSONDecodeError, OSError):
        return {}


def save_plans(path: str, plans: Dict[str, dict]) -> None:
    ensure_user_data_dir(path)
    tmp_path = f"{path}.tmp"
    clean = _sanitize_json_compat(plans)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, allow_nan=False)
    os.replace(tmp_path, path)


def load_layout(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
            if not raw_text:
                return []
            data = json.loads(raw_text)
            return _sanitize_json_compat(data)
    except (json.JSONDecodeError, OSError):
        return []


def save_layout(path: str, layout: List[dict]) -> None:
    ensure_user_data_dir(path)
    tmp_path = f"{path}.tmp"
    clean = _sanitize_json_compat(layout)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, allow_nan=False)
    os.replace(tmp_path, path)
