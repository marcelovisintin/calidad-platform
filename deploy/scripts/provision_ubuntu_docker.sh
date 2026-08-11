#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/calidad/app}"
DATA_ROOT="${DATA_ROOT:-/srv/calidad-platform}"
SERVER_IP="${SERVER_IP:-172.16.245.253}"
ENV_FILE="${ENV_FILE:-$DATA_ROOT/config/.env.server.local}"

if [[ ! -f "$APP_DIR/deploy/docker/docker-compose.local.yml" ]]; then
    echo "No se encontro la aplicacion en $APP_DIR" >&2
    exit 1
fi

sudo mkdir -p \
    "$DATA_ROOT/postgres" \
    "$DATA_ROOT/storage/media" \
    "$DATA_ROOT/storage/tmp" \
    "$DATA_ROOT/runtime/staticfiles" \
    "$DATA_ROOT/runtime/logs" \
    "$DATA_ROOT/runtime/certs" \
    "$DATA_ROOT/backups" \
    "$DATA_ROOT/config"
sudo chown -R "$(id -un):$(id -gn)" "$DATA_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
    django_secret="$(openssl rand -hex 48)"
    postgres_password="$(openssl rand -hex 32)"

    cat > "$ENV_FILE" <<EOF
APP_SLUG=calidad-platform
PUBLIC_HOSTNAME=$SERVER_IP
FRONTEND_BIND_PORT=8088
FRONTEND_TLS_BIND_PORT=8443
TLS_CERT_DAYS=825
TLS_SAN=DNS:localhost,DNS:calidad-srv,IP:127.0.0.1,IP:$SERVER_IP

DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=$django_secret
DJANGO_ALLOWED_HOSTS=$SERVER_IP,calidad-srv,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://$SERVER_IP:8088,https://$SERVER_IP:8443,http://localhost:8088,https://localhost:8443
DJANGO_DEBUG=False

POSTGRES_DB=calidad
POSTGRES_USER=calidad
POSTGRES_PASSWORD=$postgres_password
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60

LANGUAGE_CODE=es-ar
TIME_ZONE=America/Argentina/Buenos_Aires
LOG_LEVEL=INFO
DJANGO_LOG_TO_FILE=true
APP_LOG_FILE=calidad-platform.log

CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=
CORS_ALLOWED_ORIGIN_REGEXES=

HOST_POSTGRES_DATA=$DATA_ROOT/postgres
HOST_MEDIA_ROOT=$DATA_ROOT/storage/media
HOST_TMP_ROOT=$DATA_ROOT/storage/tmp
HOST_STATIC_ROOT=$DATA_ROOT/runtime/staticfiles
HOST_LOG_ROOT=$DATA_ROOT/runtime/logs
HOST_BACKUP_ROOT=$DATA_ROOT/backups
HOST_TLS_CERTS=$DATA_ROOT/runtime/certs

STORAGE_ROOT=/srv/calidad/storage
MEDIA_ROOT=/srv/calidad/storage/media
TEMP_FILES_ROOT=/srv/calidad/storage/tmp
STATIC_ROOT=/srv/calidad/runtime/staticfiles
LOG_DIR=/srv/calidad/runtime/logs

FILE_UPLOAD_MAX_MEMORY_SIZE=5242880
DATA_UPLOAD_MAX_MEMORY_SIZE=10485760
EVIDENCE_FILE_MAX_SIZE=20971520
USER_PHOTO_MAX_SIZE=5242880
LAST_ACTIVITY_UPDATE_WINDOW_SECONDS=300
ANOMALY_CODE_RESERVATION_MINUTES=10
JWT_ACCESS_TOKEN_MINUTES=15
JWT_REFRESH_TOKEN_MINUTES=480
DRF_ANON_RATE=60/minute
DRF_USER_RATE=6000/hour
DRF_LOGIN_RATE=10/minute

GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
BACKUP_RETENTION_DAYS=30
EOF
    chmod 600 "$ENV_FILE"
    echo "Configuracion creada en $ENV_FILE"
else
    echo "Se conserva la configuracion existente en $ENV_FILE"
fi

sudo systemctl enable --now docker
docker compose \
    --env-file "$ENV_FILE" \
    -f "$APP_DIR/deploy/docker/docker-compose.local.yml" \
    config --quiet

echo "Provision inicial completo."
