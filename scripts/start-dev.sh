#!/usr/bin/env bash
# start-dev.sh — start all services for local development (Linux / macOS).
#
# Services started:
#   • Django runserver  on :8000
#   • Celery worker
#   • Celery beat
#   • Vite dev server   on :5173
#
# Ctrl-C shuts everything down cleanly.

set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"
[ -d "$VENV_DIR" ] || { echo "Run ./scripts/setup.sh first."; exit 1; }

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"

# Load .env if it exists (set -a exports every variable it defines)
[ -f .env ] && set -a && source .env && set +a

PIDS=()

cleanup() {
    echo ""
    echo "Stopping services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup INT TERM EXIT

# ── Django dev server ─────────────────────────────────────────────────────────
(cd backend && python manage.py runserver 0.0.0.0:8000) &
PIDS+=($!)
echo "  Django     → http://localhost:8000"

# ── Celery worker ─────────────────────────────────────────────────────────────
(cd backend && celery -A config.celery worker --loglevel=warning --concurrency=2) &
PIDS+=($!)
echo "  Celery     → worker started"

# ── Celery beat ───────────────────────────────────────────────────────────────
(cd backend && celery -A config.celery beat --loglevel=warning) &
PIDS+=($!)
echo "  Celery     → beat started"

# ── Vite dev server ───────────────────────────────────────────────────────────
if command -v npm >/dev/null 2>&1 && [ -d frontend/node_modules ]; then
    (cd frontend && npm run dev) &
    PIDS+=($!)
    echo "  Frontend   → http://localhost:5173"
else
    echo "  Frontend   → skipped (run 'cd frontend && npm ci && npm run dev' manually)"
fi

echo ""
echo "All services running. Press Ctrl-C to stop."
wait
