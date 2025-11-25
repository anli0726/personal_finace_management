import json
import math

from backend.backend import _sanitize_records
from backend.engine.storage import _sanitize_json_compat, save_plans


def test_sanitize_json_compat_replaces_special_numbers():
    payload = {
        "float": math.nan,
        "list": [1, float("inf"), -float("inf")],
        "nested": {"value": math.nan},
    }

    clean = _sanitize_json_compat(payload)

    assert clean == {
        "float": None,
        "list": [1, None, None],
        "nested": {"value": None},
    }


def test_save_plans_persists_sanitized_values(tmp_path):
    path = tmp_path / "plans.json"
    data = {"Plan": {"value": math.nan, "items": [1, float("inf")]}}

    save_plans(str(path), data)

    with path.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)

    assert stored == {"Plan": {"value": None, "items": [1, None]}}


def test_sanitize_records_used_for_api_payloads():
    rows = [{"value": float("nan"), "other": 5}]

    clean = _sanitize_records(rows)

    assert clean == [{"value": None, "other": 5}]
