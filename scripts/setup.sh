#!/usr/bin/env bash
# setup.sh — first-time environment setup for Linux and macOS.
#
# Usage:
#   ./scripts/setup.sh            # creates .venv, installs deps, migrates
#   PYTHON=python3.12 ./scripts/setup.sh   # use a specific Python
#   MODE=dev ./scripts/setup.sh   # install dev deps instead of prod

set -euo pipefail

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
MODE="${MODE:-dev}"   # dev | prod

# ── 0. Sanity checks ─────────────────────────────────────────────────────────
command -v "$PYTHON" >/dev/null 2>&1 || { echo "ERROR: $PYTHON not found."; exit 1; }
command -v node      >/dev/null 2>&1 || echo "WARNING: node not found — frontend build will be skipped."
command -v npm       >/dev/null 2>&1 || echo "WARNING: npm not found  — frontend build will be skipped."

PY_VER=$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "Using Python $PY_VER"

# ── 1. Virtual environment ────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet

# ── 2. Python dependencies ────────────────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
    REQS="requirements/prod.txt"
else
    REQS="requirements/dev.txt"
fi
echo "Installing $REQS ..."
pip install -r "$REQS" --quiet

# ── 3. Environment file ───────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ✓ Created .env from .env.example"
    echo "  ! Edit .env and set DATABASE_URL, REDIS_URL, DJANGO_SECRET_KEY, etc."
    echo ""
fi

# ── 4. Database migrations ────────────────────────────────────────────────────
SETTINGS="config.settings.local"
[ "$MODE" = "prod" ] && SETTINGS="config.settings.production"

echo "Running migrations (settings: $SETTINGS) ..."
(cd backend && python manage.py migrate --settings="$SETTINGS")
(cd backend && python manage.py seed_roles --settings="$SETTINGS")

# ── 5. Static files (production only) ────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
    echo "Collecting static files ..."
    (cd backend && python manage.py collectstatic --noinput --settings="$SETTINGS")
fi

# ── 6. Frontend ───────────────────────────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
    echo "Installing frontend dependencies ..."
    (cd frontend && npm ci --silent)
    if [ "$MODE" = "prod" ]; then
        echo "Building frontend ..."
        (cd frontend && npm run build)
    fi
fi

echo ""
echo "Setup complete."
if [ "$MODE" = "prod" ]; then
    echo "  Start: ./scripts/start-prod.sh"
else
    echo "  Start: ./scripts/start-dev.sh"
fi
