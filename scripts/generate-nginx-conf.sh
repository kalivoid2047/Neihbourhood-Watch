#!/usr/bin/env bash
# generate-nginx-conf.sh
# Renders infra/nginx/default.conf.template into infra/nginx/generated/default.conf
# using the NHWZ_* variables from .env (or from the environment).
#
# Usage:
#   bash scripts/generate-nginx-conf.sh
#   sudo cp infra/nginx/generated/default.conf /etc/nginx/sites-available/nhwz
#   sudo ln -sf /etc/nginx/sites-available/nhwz /etc/nginx/sites-enabled/nhwz
#   sudo nginx -t && sudo systemctl reload nginx

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE="$ROOT_DIR/infra/nginx/default.conf.template"
OUTPUT_DIR="$ROOT_DIR/infra/nginx/generated"
OUTPUT="$OUTPUT_DIR/default.conf"

# Load .env if present (does not override existing env vars)
if [[ -f "$ROOT_DIR/.env" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -v '^\s*#' "$ROOT_DIR/.env" | grep -v '^\s*$')
    set +o allexport
fi

: "${NHWZ_API_HOST:?'NHWZ_API_HOST is not set. Add it to .env (e.g. NHWZ_API_HOST=127.0.0.1:8000)'}"
: "${NHWZ_STATIC_PATH:?'NHWZ_STATIC_PATH is not set. Add it to .env (e.g. NHWZ_STATIC_PATH=/opt/nhwz/staticfiles/)'}"
: "${NHWZ_MEDIA_PATH:?'NHWZ_MEDIA_PATH is not set. Add it to .env (e.g. NHWZ_MEDIA_PATH=/opt/nhwz/media/)'}"

mkdir -p "$OUTPUT_DIR"

# Only substitute the three NHWZ_* placeholders; leave nginx's own $host etc. intact.
envsubst '${NHWZ_API_HOST} ${NHWZ_STATIC_PATH} ${NHWZ_MEDIA_PATH}' \
    < "$TEMPLATE" \
    > "$OUTPUT"

echo "Generated: $OUTPUT"
echo ""
echo "  NHWZ_API_HOST  = $NHWZ_API_HOST"
echo "  NHWZ_STATIC_PATH = $NHWZ_STATIC_PATH"
echo "  NHWZ_MEDIA_PATH  = $NHWZ_MEDIA_PATH"
echo ""
echo "Next steps:"
echo "  sudo cp '$OUTPUT' /etc/nginx/sites-available/nhwz"
echo "  sudo ln -sf /etc/nginx/sites-available/nhwz /etc/nginx/sites-enabled/nhwz"
echo "  sudo nginx -t && sudo systemctl reload nginx"
