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

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_DIR="${HOST_BACKUP_ROOT%/}/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db sh -c "pg_dump -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"" | gzip > "$BACKUP_DIR/postgres.sql.gz"

tar -czf "$BACKUP_DIR/media.tar.gz" -C "$HOST_MEDIA_ROOT" .

cat > "$BACKUP_DIR/metadata.txt" <<EOF
app_slug=${APP_SLUG:-calidad-platform}
generated_at=$(date +"%Y-%m-%dT%H:%M:%S%z")
postgres_db=$POSTGRES_DB
media_root=$HOST_MEDIA_ROOT
EOF

find "$HOST_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"${BACKUP_RETENTION_DAYS:-14}" -exec rm -rf {} +

echo "Backup completed: $BACKUP_DIR"