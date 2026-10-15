#!/usr/bin/env bash
# start-prod.sh — start all services in production mode (Linux / macOS).
#
# Services started:
#   • daphne (ASGI — HTTP + WebSocket)  on $PORT (default 8000)
#   • Celery worker
#   • Celery beat
#
# For systemd / supervisor deployment, run each process individually.
# See docs/DEPLOYMENT_GUIDE.md for unit file examples.

set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"
[ -d "$VENV_DIR" ] || { echo "Run MODE=prod ./scripts/setup.sh first."; exit 1; }

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-4}"

# Load .env if it exists
[ -f .env ] && set -a && source .env && set +a

# Guard: refuse to start if the secret key is still the placeholder
if [[ "${DJANGO_SECRET_KEY:-}" == "local-development-secret-key" || -z "${DJANGO_SECRET_KEY:-}" ]]; then
    echo "ERROR: DJANGO_SECRET_KEY is not set or is still the placeholder."
    echo "       Generate one with:"
    echo "       python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    exit 1
fi

# ── Pre-flight ────────────────────────────────────────────────────────────────
echo "Running migrations ..."
(cd backend && python manage.py migrate --settings="$DJANGO_SETTINGS_MODULE" --noinput)

echo "Collecting static files ..."
(cd backend && python manage.py collectstatic --noinput --settings="$DJANGO_SETTINGS_MODULE")

PIDS=()
cleanup() {
    echo "Stopping services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# ── ASGI server (daphne) ──────────────────────────────────────────────────────
(cd backend && daphne -b 0.0.0.0 -p "$PORT" config.asgi:application) &
PIDS+=($!)
echo "  API        → http://0.0.0.0:$PORT  (daphne ASGI)"

# ── Celery worker ─────────────────────────────────────────────────────────────
(cd backend && celery -A config.celery worker --loglevel=info --concurrency="$WORKERS") &
PIDS+=($!)
echo "  Celery     → worker ($WORKERS concurrency)"

# ── Celery beat ───────────────────────────────────────────────────────────────
(cd backend && celery -A config.celery beat --loglevel=info) &
PIDS+=($!)
echo "  Celery     → beat"

echo ""
echo "NHWZ running. Press Ctrl-C to stop."
wait
