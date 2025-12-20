# Backend (Personal Financial Tool)

Python/Flask REST service that parses plan payloads, runs the financial simulator, and stores plan/layout metadata on disk.

## Stack & Dependencies
- Python 3.11+
- Flask (REST API)
- Pandas (time-series manipulation)

Install/run via repo script:
```bash
./run_backend.sh       # creates .venv, installs deps, launches http://localhost:8000
```

## Architecture Overview
- `backend.py` – Flask application, request/response handling, schema metadata, plan/layout CRUD.
- `data_model/` – Dataclasses defining accounts, cashflows, plan config, and table metadata.
- `engine/simulator.py` – Monthly simulator (accounts, income, spending, living inflation logic).
- `engine/aggregate.py` – Converts monthly output to monthly/quarterly/yearly snapshots.
- `engine/state.py` – Manages persisted plans/scenarios/layouts via `engine/storage.py`.
- `user_data/` – JSON files written/read by the service (git-ignored).

## Key Endpoints
| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/schema` | Returns plan defaults, table metadata, frequency options. |
| GET | `/api/months?startYear=&years=` | Generates month dropdown values. |
| GET | `/api/plans` | List saved plan names. |
| GET | `/api/plans/<name>` | Fetch a saved plan payload. |
| POST | `/api/plans` | Save/overwrite a plan (JSON body). |
| DELETE | `/api/plans/<name>` | Delete a plan. |
| POST | `/api/scenarios` | Run simulator for supplied plan payload; returns aggregated data. |
| GET | `/api/scenarios?freq=` | Retrieve aggregated data for previously run scenarios. |
| DELETE | `/api/scenarios` | Clear all stored scenarios. |
| GET/POST | `/api/layout` | Load/store dashboard layout preferences. |

See `backend/backend.py` for exact schemas and helper functions like `parse_accounts`/`parse_cashflows`.

## Plan Payload Notes
```jsonc
{
  "name": "Scenario A",
  "startYear": 2026,
  "years": 5,
  "taxRate": 25,
  "freq": "Q",
  "livingInflationRate": 2.5,          // applied to all spending rows with category "living"
  "accounts": [...],
  "incomes": [...],
  "spendings": [...]
}
```

Each account/cashflow row mirrors the frontend tables. Spending entries ignore per-row inflation; instead, the simulator calculates `(1 + livingInflationRate/100) ^ years_elapsed` for `living` expenses.

## Development Tips
- Modify simulator behavior in `engine/simulator.py`; aggregate logic in `engine/aggregate.py`.
- When changing persisted payloads, ensure backward compatibility in `state.PlanState` or migrate `user_data/`.
- Add new endpoints/modules under `backend/` and update `run_backend.sh` if extra deps are needed.

## Statement ingestion & categorization (experimental)
- CSV ingestion lives in `backend/statements/ingestion.py` (`import_csv_bytes`).
- Rule-based categorization lives in `backend/statements/categorizer.py`; it runs only when you pass `auto_categorize=True` or set `STATEMENT_CATEGORIZER_ENABLED=1`.
- Env toggles: `STATEMENT_MERCHANT_MAP` (path to JSON merchant->category overrides), `STATEMENT_RULE_CONFIDENCE` (rule threshold before fallback), `STATEMENT_EXTERNAL_URL`/`STATEMENT_EXTERNAL_TOKEN` (optional Plaid/Yodlee proxy), `STATEMENT_LLM_ENABLE=1` + `STATEMENT_LLM_API_KEY`/`OPENAI_API_KEY` (optional LLM fallback).
