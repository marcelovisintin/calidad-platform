#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/../docker/docker-compose.local.yml}"
LOCAL_ENV="$SCRIPT_DIR/../docker/.env.server.local"
DEFAULT_ENV="$SCRIPT_DIR/../docker/.env.server"
ENV_FILE="${ENV_FILE:-}"

if [ -z "$ENV_FILE" ]; then
  if [ -f "$LOCAL_ENV" ]; then
    ENV_FILE="$LOCAL_ENV"
  else
    ENV_FILE="$DEFAULT_ENV"
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

RELEASE_COMMIT_FILE="${APP_GIT_COMMIT_FILE:-$PROJECT_ROOT/.git-commit}"
RELEASE_HISTORY_FILE="${APP_GIT_HISTORY_FILE:-$PROJECT_ROOT/.git-history.tsv}"

if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  APP_GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse HEAD)
  APP_GIT_SHORT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
  APP_GIT_BRANCH=$(git -C "$PROJECT_ROOT" branch --show-current)
  APP_GIT_DIRTY=false
  if [ -n "$(git -C "$PROJECT_ROOT" status --porcelain)" ]; then
    APP_GIT_DIRTY=true
  fi
  APP_GIT_HISTORY_B64=$(git -C "$PROJECT_ROOT" log -n 30 --date=iso-strict --pretty=format:'%H%x09%h%x09%aI%x09%an%x09%s%x09%D' | base64 | tr -d '\n\r')
else
  if [ -z "${APP_GIT_COMMIT:-}" ] && [ -f "$RELEASE_COMMIT_FILE" ]; then
    APP_GIT_COMMIT=$(sed -n '1{s/[[:space:]]//g;p;}' "$RELEASE_COMMIT_FILE")
  fi
  if [ -z "${APP_GIT_COMMIT:-}" ]; then
    echo "Missing release commit metadata. Set APP_GIT_COMMIT or create $RELEASE_COMMIT_FILE"
    exit 1
  fi

  APP_GIT_SHORT_COMMIT="${APP_GIT_SHORT_COMMIT:-$(printf '%s' "$APP_GIT_COMMIT" | cut -c1-7)}"
  APP_GIT_BRANCH="${APP_GIT_BRANCH:-main}"
  APP_GIT_DIRTY="${APP_GIT_DIRTY:-false}"
  if [ -z "${APP_GIT_HISTORY_B64:-}" ] && [ -f "$RELEASE_HISTORY_FILE" ]; then
    APP_GIT_HISTORY_B64=$(base64 "$RELEASE_HISTORY_FILE" | tr -d '\n\r')
  fi
  APP_GIT_HISTORY_B64="${APP_GIT_HISTORY_B64:-}"
  echo "Using packaged release metadata: $APP_GIT_SHORT_COMMIT ($APP_GIT_BRANCH)"
fi
APP_DEPLOYMENT_ENV=production
export APP_GIT_COMMIT APP_GIT_SHORT_COMMIT APP_GIT_BRANCH APP_GIT_DIRTY APP_DEPLOYMENT_ENV APP_GIT_HISTORY_B64

UPDATE_STATUS_ROOT="${HOST_UPDATE_STATUS_ROOT:-/srv/calidad-platform/runtime/update}"
STATUS_FILE="$UPDATE_STATUS_ROOT/status.json"
STATUS_TMP="$UPDATE_STATUS_ROOT/status.json.tmp"
DEPLOY_SUCCEEDED=false

write_status() {
  status="$1"
  version="${2:-}"
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  printf '{"status":"%s","version":"%s","updated_at":"%s"}\n' "$status" "$version" "$timestamp" > "$STATUS_TMP"
  mv "$STATUS_TMP" "$STATUS_FILE"
}

handle_exit() {
  exit_code=$?
  if [ "$DEPLOY_SUCCEEDED" != "true" ]; then
    write_status "failed"
  fi
  exit "$exit_code"
}

mkdir -p "$UPDATE_STATUS_ROOT"
trap handle_exit EXIT HUP INT TERM

write_status "updating"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  up -d --build

version=$(docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  exec -T frontend \
  sh -c "sed -n 's/.*\"version\":\"\\([^\"]*\\)\".*/\\1/p' /usr/share/nginx/html/version.json")

write_status "ready" "$version"
DEPLOY_SUCCEEDED=true
trap - EXIT HUP INT TERM

echo "Actualizacion completada. Version: $version"
