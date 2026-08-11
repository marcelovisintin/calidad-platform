#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
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
