#!/usr/bin/env bash
# Finish a deploy whose Railway half already succeeded. Sets the internal token, builds
# and deploys the front end with the API URL inlined, then allows the front end's origin.
# Only the last variable triggers a rebuild, so this costs one Railway build, not three.
#
# Reads the same deploy.env as deploy.sh. Run it when deploy.sh died after "railway up".
set -euo pipefail

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n!! %s\n' "$*" >&2; exit 1; }

[ -f deploy.env ] && set -a && . ./deploy.env && set +a
WEB_DIR="${WEB_DIR:-web}"
ORIGINS_VAR="${ORIGINS_VAR:-APP_ALLOWED_ORIGINS}"
TOKEN_VAR="${TOKEN_VAR:-APP_INTERNAL_TOKEN}"
HEALTH_PATH="${HEALTH_PATH:-/health}"
PROBE_PATH="${PROBE_PATH:-$HEALTH_PATH}"
INTERNAL_PATH="${INTERNAL_PATH:-}"
DEMO_HINT="${DEMO_HINT:-}"
BUILD_MINUTES="${BUILD_MINUTES:-4-5}"

API_URL="${API_URL:-https://$(railway variable list --kv 2>/dev/null | grep -m1 RAILWAY_PUBLIC_DOMAIN | cut -d= -f2- | tr -d ' ')}"
[ "$API_URL" != "https://" ] || die "could not read RAILWAY_PUBLIC_DOMAIN. pass API_URL=..."
echo "  API: $API_URL"

DEMO_INTERNAL="${DEMO_INTERNAL:-1}"
say "Internal token"
if [ "$DEMO_INTERNAL" = "1" ]; then
  TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  printf '%s' "$TOKEN" | railway variable set "$TOKEN_VAR" --stdin --skip-deploys >/dev/null
  echo "  generated and set as $TOKEN_VAR. internal surfaces will be reachable"
else
  TOKEN=""
  echo "  left unset. internal routes stay localhost only"
fi

say "Vercel"
# VITE_ vars must be BUILD-time: Vite inlines them, a runtime env is ignored.
VOUT=$(vercel deploy --prod --yes --cwd "$WEB_DIR" \
        --build-env "VITE_API_URL=$API_URL" \
        --build-env "VITE_USE_FIXTURES=0" \
        --build-env "VITE_INTERNAL_TOKEN=$TOKEN" 2>&1 | tee /dev/stderr)
ALIAS=$(printf '%s' "$VOUT" | grep -iE 'Aliased' | grep -oE 'https://[A-Za-z0-9.-]+\.vercel\.app' | tail -1)
DEP=$(printf '%s' "$VOUT" | grep -oE 'https://[A-Za-z0-9.-]+\.vercel\.app' | tail -1)
WEB="${ALIAS:-$DEP}"
[ -n "$WEB" ] || die "could not read the Vercel URL"
ORIGINS="$WEB"; [ -n "$ALIAS" ] && [ "$ALIAS" != "$DEP" ] && ORIGINS="$ALIAS,$DEP"
echo "  WEB: $WEB"

say "Allow the front end, then wait out the one rebuild"
printf '%s' "$ORIGINS" | railway variable set "$ORIGINS_VAR" --stdin >/dev/null
printf '  rebuilding (%s min, it re-runs ingest)' "$BUILD_MINUTES"
sleep 30
until curl -fsS -m 15 -o /dev/null "$API_URL$HEALTH_PATH" 2>/dev/null \
   || curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$PROBE_PATH" | grep -q '^4'; do
  printf '.'; sleep 10
done
echo " up"

say "Verify"
for p in /docs /redoc /openapi.json; do
  printf '  %-22s %s (expect 404)\n' "$p" "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$p")"
done
if [ -n "$INTERNAL_PATH" ]; then
  printf '  %-22s %s (expect 403, no token)\n' "$INTERNAL_PATH" \
    "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH")"
  if [ -n "$TOKEN" ]; then
    printf '  %-22s %s (expect 200, right token)\n' "$INTERNAL_PATH" \
      "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH" -H "X-Internal-Token: $TOKEN")"
    printf '  %-22s %s (expect 403, wrong token)\n' "$INTERNAL_PATH" \
      "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH" -H "X-Internal-Token: nope")"
  fi
fi
printf '  CORS for the alias:    %s\n' \
  "$(curl -s -D- -o /dev/null -m 15 "$API_URL$PROBE_PATH" -X OPTIONS \
     -H "Origin: $WEB" -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type" \
     | grep -ic 'access-control-allow-origin' | sed 's/^1$/allowed/;s/^0$/MISSING/')"

say "Done"
echo "  API  $API_URL"
echo "  WEB  $WEB"
echo
[ -z "$DEMO_HINT" ] || echo "  $DEMO_HINT"
