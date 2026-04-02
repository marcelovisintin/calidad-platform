#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/../docker/docker-compose.local.yml}"
DEFAULT_LOCAL_ENV="$SCRIPT_DIR/../docker/.env.server.local"
ENV_FILE="${ENV_FILE:-$DEFAULT_LOCAL_ENV}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  echo "Set ENV_FILE to a secure external path or copy deploy/docker/.env.server.example to an untracked deploy/docker/.env.server.local."
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

RESTORE_SOURCE="${1:-${RESTORE_SOURCE:-}}"
if [ -z "$RESTORE_SOURCE" ]; then
  RESTORE_SOURCE=$(find "$HOST_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
fi

if [ -z "$RESTORE_SOURCE" ] || [ ! -d "$RESTORE_SOURCE" ]; then
  echo "Backup directory not found. Provide a directory as first argument or set RESTORE_SOURCE."
  exit 1
fi

if [ ! -f "$RESTORE_SOURCE/postgres.sql.gz" ]; then
  echo "Missing postgres.sql.gz in $RESTORE_SOURCE"
  exit 1
fi

if [ ! -f "$RESTORE_SOURCE/media.tar.gz" ]; then
  echo "Missing media.tar.gz in $RESTORE_SOURCE"
  exit 1
fi

echo "Restoring database from $RESTORE_SOURCE/postgres.sql.gz"
gunzip -c "$RESTORE_SOURCE/postgres.sql.gz" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db sh -c "psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""

echo "Restoring media files into $HOST_MEDIA_ROOT"
mkdir -p "$HOST_MEDIA_ROOT"
find "$HOST_MEDIA_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
tar -xzf "$RESTORE_SOURCE/media.tar.gz" -C "$HOST_MEDIA_ROOT"

echo "Restore completed from: $RESTORE_SOURCE"