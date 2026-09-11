#!/usr/bin/env bash
# One command: GitHub repo, Railway API, Vercel front end, wired together and verified.
#
# This script is a template. It knows nothing about your app except what deploy.env
# tells it. Copy deploy.env.example to deploy.env, fill in the handful of names, and run.
#
# Provide once, before running this:
#   gh auth login  ·  railway login  ·  vercel login
# Secrets come from ./.env and go in over stdin. They are never printed and never appear
# in a process argument list.
#
# Folder shape it expects:
#   ./Dockerfile          builds the API image and runs ingest inside the build
#   ./web/                the Vite front end (override with WEB_DIR)
#   ./.env                real keys, gitignored
#   ./deploy.env          per-project names, safe to commit
#
# DEMO_INTERNAL=1 (default) puts any internal surfaces behind a generated shared token.
# Understand what that token is: Vite inlines build variables into the JavaScript bundle,
# so anyone who views source can read it. It stops a crawler. It is not authentication.
# DEMO_INTERNAL=0 leaves the token unset, and the internal routes refuse every
# non-localhost caller, so you demo them from your machine.
# Either is defensible. Shipping the token without saying what it is, is not.

set -euo pipefail

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n!! %s\n' "$*" >&2; exit 1; }

# ---- Per-project names. deploy.env overrides these; the environment overrides both. ----
[ -f deploy.env ] && set -a && . ./deploy.env && set +a

# Folder name, lowercased, anything odd turned into a dash. "Perficent test #2" -> "perficent-test-2"
APP_NAME="${APP_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')}"
REPO_NAME="${REPO_NAME:-$APP_NAME}"
PROJECT="${PROJECT:-$APP_NAME}"
SERVICE="${SERVICE:-api}"
WEB_DIR="${WEB_DIR:-web}"

# What the API reads for allowed origins and the internal token. Must match config.py.
ORIGINS_VAR="${ORIGINS_VAR:-APP_ALLOWED_ORIGINS}"
TOKEN_VAR="${TOKEN_VAR:-APP_INTERNAL_TOKEN}"

# Routes. HEALTH_PATH must return 200 when the app is up. PROBE_PATH is any path the app
# routes; a 4xx from it means uvicorn is up, only a connection failure means it is not.
# INTERNAL_PATH is a token-gated route to verify, or empty to skip the token checks.
HEALTH_PATH="${HEALTH_PATH:-/health}"
PROBE_PATH="${PROBE_PATH:-$HEALTH_PATH}"
INTERNAL_PATH="${INTERNAL_PATH:-}"

# Keys that must be non-empty in .env before anything is pushed anywhere.
# ANTHROPIC_WORKSPACE_ID is copied up only when present, since not every key needs it.
REQUIRED_KEYS="${REQUIRED_KEYS:-ANTHROPIC_API_KEY LANGSMITH_API_KEY}"

# Words for humans. The commit message on first push and the one-line demo hint at the end.
COMMIT_MSG="${COMMIT_MSG:-$APP_NAME: first deploy}"
DEMO_HINT="${DEMO_HINT:-}"
BUILD_MINUTES="${BUILD_MINUTES:-4-5}"

say "Preflight"
for c in gh git railway vercel npm curl python3; do command -v "$c" >/dev/null || die "$c is not installed"; done
gh auth status >/dev/null 2>&1 || die "run: gh auth login"
railway whoami  >/dev/null 2>&1 || die "run: railway login"
vercel whoami   >/dev/null 2>&1 || die "run: vercel login"
[ -f .env ] || die "no .env here"
[ -f Dockerfile ] || die "no Dockerfile here"
[ -d "$WEB_DIR" ] || die "no $WEB_DIR/ folder here (set WEB_DIR if it lives elsewhere)"
get() { grep -m1 "^$1=" .env | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '"'"'"' \r'; }
for k in $REQUIRED_KEYS; do
  [ -n "$(get "$k")" ] || die "$k is empty in .env"
done
echo "  app $APP_NAME  repo $REPO_NAME  railway $PROJECT/$SERVICE  web $WEB_DIR/"
echo "  CLIs authed, .env has the keys"

say "GitHub"
# The corpus makes the first push large enough that git's 1MB default post buffer and
# HTTP/2 both fail it with an RPC 400.
git config --local http.postBuffer 524288000 2>/dev/null || true
git config --local http.version HTTP/1.1 2>/dev/null || true
if [ ! -d .git ]; then
  git init -b main -q
  git config --local http.postBuffer 524288000
  git config --local http.version HTTP/1.1
  git add -A
  git commit -qm "$COMMIT_MSG"
  gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
else
  git add -A
  git commit -qm "deploy: $(date -u +%FT%TZ)" || echo "  nothing new to commit"
  git push -q origin main 2>/dev/null || gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
fi
echo "  $(git ls-files | wc -l | tr -d ' ') files tracked"

say "Railway (API)"
railway status >/dev/null 2>&1 || railway init --name "$PROJECT" >/dev/null
railway service list 2>/dev/null | grep -qw "$SERVICE" || { railway add --service "$SERVICE" >/dev/null; echo "  created service $SERVICE"; }
railway service "$SERVICE" >/dev/null 2>&1 || true
railway status 2>&1 | grep -E "Project:|Service:" | sed 's/^/  /'

setvar() { printf '%s' "$2" | railway variable set "$1" --stdin --skip-deploys >/dev/null; echo "  set $1"; }
for k in $REQUIRED_KEYS; do setvar "$k" "$(get "$k")"; done
if [ -n "$(get ANTHROPIC_WORKSPACE_ID)" ]; then setvar ANTHROPIC_WORKSPACE_ID "$(get ANTHROPIC_WORKSPACE_ID)"; fi
setvar LANGSMITH_TRACING "true"
LS_PROJECT="$(get LANGSMITH_PROJECT)"; setvar LANGSMITH_PROJECT "${LS_PROJECT:-$PROJECT}"

echo "  deploying. the build runs ingest, so expect $BUILD_MINUTES minutes"
railway up -y --ci

railway domain >/dev/null 2>&1 || true
API_URL="https://$(railway domain 2>/dev/null | grep -oE '[A-Za-z0-9.-]+\.up\.railway\.app' | head -1)"
[ "$API_URL" != "https://" ] || die "could not read the Railway domain. run: railway domain"
echo "  API: $API_URL"
printf '  waiting for the app to answer on %s' "$PROBE_PATH"
until [ -n "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$API_URL$PROBE_PATH" 2>/dev/null | grep -E '^[2345]')" ]; do
  printf '.'; sleep 5
done
echo " up"

DEMO_INTERNAL="${DEMO_INTERNAL:-1}"
if [ "$DEMO_INTERNAL" = "1" ]; then
  INTERNAL_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  printf '%s' "$INTERNAL_TOKEN" | railway variable set "$TOKEN_VAR" --stdin --skip-deploys >/dev/null
  echo "  set $TOKEN_VAR (generated, internal surfaces will be live behind it)"
else
  INTERNAL_TOKEN=""
  echo "  $TOKEN_VAR left unset: internal routes will be localhost only"
fi

say "Vercel (front end)"
# VITE_ vars must be BUILD-time variables: Vite inlines them, a runtime env is ignored.
# VITE_INTERNAL_TOKEN carries the generated token, or is empty when DEMO_INTERNAL=0.
VOUT=$(vercel deploy --prod --yes --cwd "$WEB_DIR" \
        --build-env "VITE_API_URL=$API_URL" \
        --build-env "VITE_USE_FIXTURES=0" \
        --build-env "VITE_INTERNAL_TOKEN=$INTERNAL_TOKEN" 2>&1 | tee /dev/stderr)
# Vercel prints a per-deployment URL and a stable alias. The alias is what a human opens
# and it survives redeploys, so both go in the allowed origins and the alias is reported.
WEB_ALIAS=$(printf '%s' "$VOUT" | grep -iE 'Aliased' | grep -oE 'https://[A-Za-z0-9.-]+\.vercel\.app' | tail -1)
WEB_DEPLOY=$(printf '%s' "$VOUT" | grep -oE 'https://[A-Za-z0-9.-]+\.vercel\.app' | tail -1)
WEB_URL="${WEB_ALIAS:-$WEB_DEPLOY}"
[ -n "$WEB_URL" ] || die "could not read the Vercel URL"
ORIGINS="$WEB_URL"
[ -n "$WEB_ALIAS" ] && [ "$WEB_ALIAS" != "$WEB_DEPLOY" ] && ORIGINS="$WEB_ALIAS,$WEB_DEPLOY"
echo "  WEB: $WEB_URL"

say "Wiring CORS back"
printf '%s' "$ORIGINS" | railway variable set "$ORIGINS_VAR" --stdin >/dev/null
echo "  $ORIGINS_VAR set, Railway is rebuilding (another $BUILD_MINUTES min, it re-runs ingest)"
sleep 20
printf '  waiting'
until curl -fsS -m 10 "$API_URL$HEALTH_PATH" >/dev/null 2>&1; do printf '.'; sleep 10; done
echo " healthy"

say "Verify"
printf '  %-22s %s\n' "$HEALTH_PATH" "$(curl -s -m 15 "$API_URL$HEALTH_PATH")"
for p in /docs /redoc /openapi.json; do
  printf '  %-22s %s (expect 404)\n' "$p" "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$p")"
done
if [ -n "$INTERNAL_PATH" ]; then
  printf '  %-22s %s (expect 403, no token sent)\n' "$INTERNAL_PATH" \
    "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH")"
  if [ -n "$INTERNAL_TOKEN" ]; then
    printf '  %-22s %s (expect 200, correct token)\n' "$INTERNAL_PATH" \
      "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH" -H "X-Internal-Token: $INTERNAL_TOKEN")"
    printf '  %-22s %s (expect 403, wrong token)\n' "$INTERNAL_PATH" \
      "$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$API_URL$INTERNAL_PATH" -H "X-Internal-Token: wrong")"
  fi
fi
printf '  CORS for the alias:    %s\n' \
  "$(curl -s -D- -o /dev/null -m 15 "$API_URL$HEALTH_PATH" -H "Origin: $WEB_URL" \
     | grep -ic 'access-control-allow-origin' | sed 's/^1$/allowed/;s/^0$/MISSING/')"

say "Done"
echo "  API  $API_URL"
echo "  WEB  $WEB_URL"
echo "  repo $(gh repo view --json url -q .url 2>/dev/null)"
echo
[ -z "$DEMO_HINT" ] || echo "  $DEMO_HINT"
if [ -n "$INTERNAL_TOKEN" ]; then
  echo "  Internal surfaces: live, behind a generated token."
  echo "  Say the caveat before anyone asks: that token is compiled into the front end"
  echo "  bundle, so it is demo-grade. In production these sit behind the client's SSO."
else
  echo "  Internal surfaces: localhost only, by design."
fi
