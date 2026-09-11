#!/usr/bin/env bash
# Run the whole thing on this Mac: API and front end, no deploy.
# Reads deploy.env for the module names and the front end folder.
#
# Vite cannot run from a folder whose path contains '#' or other odd characters, so the
# web folder is mirrored to a plain path under /tmp and served from there. Edit web/ here;
# rerun this to re-mirror.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
[ -f deploy.env ] && set -a && . ./deploy.env && set +a

APP_NAME="${APP_NAME:-$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')}"
API_MODULE="${API_MODULE:-app.api.run}"
INGEST_MODULE="${INGEST_MODULE:-app.ingest.run}"
WEB_DIR="${WEB_DIR:-web}"
ORIGINS_VAR="${ORIGINS_VAR:-APP_ALLOWED_ORIGINS}"
HEALTH_PATH="${HEALTH_PATH:-/health}"
INDEX_DIR="${INDEX_DIR:-store/chroma}"
API_PORT="${API_PORT:-8020}"
WEB_PORT="${WEB_PORT:-5199}"
MIRROR="/tmp/$APP_NAME-web"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "no .venv here. run: python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
mkdir -p runs

echo "== API on http://localhost:$API_PORT"
[ -d "$INDEX_DIR" ] || { echo "no index yet, running $INGEST_MODULE"; "$PY" -m "$INGEST_MODULE"; }
(env PORT="$API_PORT" "$ORIGINS_VAR=http://localhost:$WEB_PORT" \
  "$PY" -m "$API_MODULE" > runs/api.log 2>&1 &)
until curl -fsS -m 2 "http://localhost:$API_PORT$HEALTH_PATH" >/dev/null 2>&1; do printf '.'; sleep 1; done
echo " api up: $(curl -s "http://localhost:$API_PORT$HEALTH_PATH")"

echo "== Front end on http://localhost:$WEB_PORT"
mkdir -p "$MIRROR"
rsync -a --delete --exclude node_modules --exclude dist "$ROOT/$WEB_DIR/" "$MIRROR/"
[ -d "$MIRROR/node_modules" ] || (cd "$MIRROR" && npm install --silent)
(cd "$MIRROR" && VITE_API_URL="http://localhost:$API_PORT" VITE_USE_FIXTURES=0 VITE_INTERNAL_TOKEN="" \
  npx vite --port "$WEB_PORT" --strictPort > "$ROOT/runs/web.log" 2>&1 &)
until curl -fsS -m 2 "http://localhost:$WEB_PORT/" >/dev/null 2>&1; do printf '.'; sleep 1; done
echo " web up"
echo
echo "Open http://localhost:$WEB_PORT"
echo "Logs: runs/api.log and runs/web.log. Stop both: pkill -f '$API_MODULE'; pkill -f 'vite --port $WEB_PORT'"
