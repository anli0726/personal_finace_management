## Personal Financial Tool

This iteration drops Dash in favor of a lightweight REST backend (Flask) plus a vanilla HTML/JS frontend. The Python side keeps the existing simulator/data-model logic, while the browser handles data entry, charts (Chart.js), and presentation.

### Backend

1. From the repo root run:
   ```bash
   ./run_backend.sh
   ```
   This creates/activates `.venv`, installs backend deps, and launches the API.
   The server listens on `http://localhost:8000` and exposes:
   - `GET /api/schema` — table metadata & defaults
   - `GET /api/months` — helper endpoint for month dropdowns
   - `GET /api/scenarios?freq=Q` — aggregated series (M/Q/Y)
   - `POST /api/scenarios` — run a simulation with the posted payload
   - `DELETE /api/scenarios` — wipe stored scenarios

Scenarios are still persisted to `user_data/scenarios.json` (this file is ignored by git so personal runs stay local).

### Frontend

The static frontend lives in `frontend/`. Any static file server will work; for example:

```bash
./run_frontend.sh            # defaults to port 4173
```

Open `http://localhost:4173` in a browser. By default the UI points to `http://localhost:8000`. If you run the API elsewhere, configure it before loading the page:

```html
<script>
  window.APP_CONFIG = { apiBase: "http://127.0.0.1:9000" };
</script>
<script src="main.js" type="module" defer></script>
```

### Workflow

1. Fill in plan basics (name, start year, horizon, tax rate & frequency). The action buttons live on the same card.
- Enter account/income/spending rows (add/remove rows with the buttons). Drag column dividers or the lower-right handle to resize table columns/height inside each card.
- Click **Add Scenario** to simulate; charts + aggregated table update automatically and accumulate multiple scenarios.
- Use **Clear Scenarios** to wipe everything and start over.
- Save/load/delete named plans via the controls on the plan card; the definitions live locally in `user_data/plans.json`.
- Adjust the dashboard layout (drag handles / resize corners) and click **Save Layout** to keep your preferred arrangement as the default (stored locally in `user_data/layout.json`).
- Reorder dashboard cards via the "::" handle (dropping a card below the grid creates a new row) and resize panels from the bottom-right corner.

The new UI uses Chart.js (via CDN) for the net-worth/liquidity plots and works against the REST API, so backend & frontend can evolve independently.
