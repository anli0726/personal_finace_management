#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-4173}"
FRONTEND_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/frontend" && pwd)"
cd "$FRONTEND_DIR"
echo "Serving frontend on http://localhost:${PORT}"
python3 -m http.server "$PORT"
