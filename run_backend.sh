#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
BACKEND_DIR="$SCRIPT_DIR/backend"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    if [ -d "$VENV_DIR" ]; then
        echo "Removing corrupt virtual environment at $VENV_DIR"
        rm -rf "$VENV_DIR"
    fi
    echo "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

echo "Activating virtual environment"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "Upgrading pip"
python -m pip install --upgrade pip

if [ -f "$REQ_FILE" ]; then
    echo "Installing dependencies from $REQ_FILE"
    pip install -r "$REQ_FILE"
else
    echo "No requirements.txt found at $REQ_FILE, skipping dependency installation"
fi

echo "Starting backend..."
python "$BACKEND_DIR/backend.py"
