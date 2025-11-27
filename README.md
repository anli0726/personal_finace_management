# Personal Financial Tool

A lightweight planning sandbox for modeling multi-year personal finance scenarios. Define assets, income streams, spending patterns, and a living-cost inflation rate, then compare the resulting net-worth and liquidity trajectories through an interactive dashboard.

## What You Can Do
- Capture current accounts (cash, investments, liabilities) plus future-dated income/spending rows.
- Model lifestyle inflation globally by setting a single **Living Cost Inflation Rate** that automatically escalates all `living` expenses.
- Simulate multiple scenarios and visualize the outcomes side-by-side (net worth, liquid assets, aggregated table).
- Save/load plan definitions and preferred dashboard layouts locally.

## Quick Start
1. **Backend** – start the REST API (Python 3.11+, Flask).
   ```bash
   ./run_backend.sh
   ```
   The service listens on `http://localhost:8000`.
2. **Frontend** – serve the static UI (vanilla HTML/CSS/JS).
   ```bash
   ./run_frontend.sh   # defaults to http://localhost:4173
   ```
3. Open the frontend in a browser, fill in plan basics, add accounts/income/spending rows, set the living-cost inflation rate, and click **Simulate & Plot**.

## Tech Snapshot
- **Backend**: Python, Flask, Pandas. Provides REST endpoints for schema metadata, plan CRUD, scenario execution, and layout storage. Persists data under `user_data/`.
- **Frontend**: Vanilla JS, Chart.js for visualization, CSS layout tuned for drag/resizable panels. Talks to the backend via fetch/XHR.
- **Data Model**: Plans carry accounts/income/spending arrays plus a living inflation rate. Scenarios are simulated monthly and aggregated to monthly/quarterly/yearly views.

## API & Interface Summary
- `GET /api/schema` – Returns table metadata, defaults, and frequency options used by the UI.
- `POST /api/scenarios` – Accepts the current plan payload, runs the simulator, and returns aggregated data for plotting.
- `GET/POST/DELETE /api/plans` – Manage locally persisted plan definitions.
- `GET/POST /api/layout` – Load/store dashboard layouts.

All endpoints are unauthenticated and intended for local use. See `backend/README.md` for detailed API contracts and module structure.

## Repository Layout
- `backend/` – Flask app, simulation engine, data models, storage helpers. (More detail in `backend/README.md`.)
- `frontend/` – Static UI assets (HTML, CSS, JS). (More detail in `frontend/README.md`.)
- `user_data/` – Local persistence for plans, scenarios, and layout preferences (git-ignored).
- `run_backend.sh` / `run_frontend.sh` – Convenience launch scripts.

## Notes
- Plans and scenarios stay on disk so you can close/reopen the UI without losing work.
- The simulator currently assumes deterministic growth; incorporate market swings by editing account return rates or duplicating scenarios with different assumptions.
- Contributions welcome—open an issue or PR with ideas or fixes. For development details (dependencies, linting, etc.), consult the per-directory READMEs.
