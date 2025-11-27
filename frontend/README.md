# Frontend (Personal Financial Tool)

Vanilla HTML/CSS/JS dashboard for editing plans, triggering simulations, and visualizing results returned by the Flask backend.

## Stack
- Static HTML (served via any static server)
- Modern ES modules (`frontend/main.js`)
- CSS-only styling with custom grid/drag handles (`frontend/styles.css`)
- Chart.js (via CDN) for line charts

## Running Locally
```bash
./run_frontend.sh          # serves from frontend/ on http://localhost:4173
```
To point at a different backend base URL, set `window.APP_CONFIG` before loading `main.js` (see `index.html` comment).

## Key Files
- `index.html` – Layout markup: plan controls, tables, charts, aggregate grid.
- `styles.css` – Dark theme, responsive panel grid, draggable/resizable panels.
- `main.js` – Fetches backend schema, manages plan state, renders tables, handles simulations, and updates Chart.js visuals.

## UI Concepts
- **Plan Basics**: Scenario name, start year, duration, tax rate, frequency selector.
- **Tables**: Accounts / Income / Spending tables generated dynamically from schema metadata (column definitions shared with backend).
- **Living Cost Inflation Rate**: Input above the spending table. The value (percent) is cached with the plan and sent to the backend; all `living` expenses inflate annually at this rate.
- **Scenario Management**: Save/load/delete plans locally; multiple scenarios plotted simultaneously until cleared.
- **Layout Persistence**: Drag panels or resize them; click “Save Layout” to write preferences to the backend/local storage.

## Development Notes
- `createTableManager` in `main.js` manages dynamic tables (row add/remove, column resizing, etc.).
- The frontend assumes the backend exposes `/api/schema`, `/api/plans`, `/api/scenarios`, and `/api/layout`. Errors are surfaced via a status banner at the top.
- For styling tweaks, prefer editing `styles.css`; minimal inline styles exist in DOM creation.
- No build tooling is required—just edit the source files and refresh the browser.
