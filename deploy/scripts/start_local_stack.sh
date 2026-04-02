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
  echo "Copy deploy/docker/.env.server.example to deploy/docker/.env.server or set ENV_FILE to an external secure path."
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

mkdir -p "$HOST_POSTGRES_DATA" "$HOST_MEDIA_ROOT" "$HOST_TMP_ROOT" "$HOST_STATIC_ROOT" "$HOST_LOG_ROOT" "$HOST_BACKUP_ROOT" "$HOST_TLS_CERTS"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

PORT="${FRONTEND_BIND_PORT:-8088}"
TLS_PORT="${FRONTEND_TLS_BIND_PORT:-8443}"
HOSTNAME_VALUE=$(hostname)

echo ""
echo "Stack levantado correctamente"
echo "Login local HTTP:   http://localhost:${PORT}/login"
echo "Login host HTTP:    http://${HOSTNAME_VALUE}:${PORT}/login"
echo "Login local HTTPS:  https://localhost:${TLS_PORT}/login"
echo "Login host HTTPS:   https://${HOSTNAME_VALUE}:${TLS_PORT}/login"
