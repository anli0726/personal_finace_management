## Personal Financial Tool

This iteration drops Dash in favor of a lightweight REST backend (Flask) plus a vanilla HTML/JS frontend. The Python side keeps the existing simulator/data-model logic, while the browser handles data entry, charts (Chart.js), and presentation.

### Backend

1. (Optional but recommended) create a virtual environment so the backend deps stay isolated:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the API:
   ```bash
   python3 backend.py
   ```
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
cd frontend
python3 -m http.server 4173
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
2. Enter account/income/spending rows (add/remove rows with the buttons). Drag column dividers or the lower-right handle to resize table columns/height inside each card.
3. Click **Add Scenario** to simulate; charts + aggregated table update automatically and accumulate multiple scenarios.
4. Use **Clear Scenarios** to wipe everything and start over.
- Reorder dashboard cards via the "::" handle (dropping a card below the grid creates a new row) and resize panels from the bottom-right corner.

The new UI uses Chart.js (via CDN) for the net-worth/liquidity plots and works against the REST API, so backend & frontend can evolve independently.
