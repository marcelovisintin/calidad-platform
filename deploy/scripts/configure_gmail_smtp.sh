#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/calidad-platform/config/.env.server.local}"
SENDER_EMAIL="${1:-marcelo.v@schneider.ar}"
APP_PUBLIC_URL_VALUE="${APP_PUBLIC_URL_VALUE:-http://172.16.245.253:8088}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "No se encontro el archivo de configuracion: $ENV_FILE" >&2
    exit 1
fi

read -r -s -p "Contrasena de aplicacion de Google (16 caracteres): " app_password
echo
app_password="${app_password// /}"
if [[ ${#app_password} -ne 16 ]]; then
    unset app_password
    echo "La contrasena de aplicacion debe tener 16 caracteres, sin espacios." >&2
    exit 1
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"; unset app_password' EXIT
chmod 600 "$tmp_file"
declare -A configured=()

write_setting() {
    local key="$1"
    case "$key" in
        APP_PUBLIC_URL) printf '%s=%s\n' "$key" "$APP_PUBLIC_URL_VALUE" ;;
        EMAIL_NOTIFICATIONS_ENABLED) printf '%s=False\n' "$key" ;;
        EMAIL_BACKEND) printf '%s=django.core.mail.backends.smtp.EmailBackend\n' "$key" ;;
        EMAIL_HOST) printf '%s=smtp.gmail.com\n' "$key" ;;
        EMAIL_PORT) printf '%s=587\n' "$key" ;;
        EMAIL_HOST_USER) printf '%s=%s\n' "$key" "$SENDER_EMAIL" ;;
        EMAIL_HOST_PASSWORD) printf '%s=%s\n' "$key" "$app_password" ;;
        EMAIL_USE_TLS) printf '%s=True\n' "$key" ;;
        EMAIL_USE_SSL) printf '%s=False\n' "$key" ;;
        EMAIL_TIMEOUT) printf '%s=10\n' "$key" ;;
        DEFAULT_FROM_EMAIL) printf '%s=%s\n' "$key" "$SENDER_EMAIL" ;;
        EMAIL_MAX_RETRIES) printf '%s=3\n' "$key" ;;
        EMAIL_RETRY_DELAY_MINUTES) printf '%s=5\n' "$key" ;;
        EMAIL_PROCESSING_TIMEOUT_MINUTES) printf '%s=10\n' "$key" ;;
    esac
}

settings=(
    APP_PUBLIC_URL
    EMAIL_NOTIFICATIONS_ENABLED
    EMAIL_BACKEND
    EMAIL_HOST
    EMAIL_PORT
    EMAIL_HOST_USER
    EMAIL_HOST_PASSWORD
    EMAIL_USE_TLS
    EMAIL_USE_SSL
    EMAIL_TIMEOUT
    DEFAULT_FROM_EMAIL
    EMAIL_MAX_RETRIES
    EMAIL_RETRY_DELAY_MINUTES
    EMAIL_PROCESSING_TIMEOUT_MINUTES
)

while IFS= read -r line || [[ -n "$line" ]]; do
    key="${line%%=*}"
    replacement=false
    for setting in "${settings[@]}"; do
        if [[ "$key" == "$setting" ]]; then
            write_setting "$setting" >> "$tmp_file"
            configured["$setting"]=1
            replacement=true
            break
        fi
    done
    if [[ "$replacement" == false ]]; then
        printf '%s\n' "$line" >> "$tmp_file"
    fi
done < "$ENV_FILE"

for setting in "${settings[@]}"; do
    if [[ -z "${configured[$setting]:-}" ]]; then
        write_setting "$setting" >> "$tmp_file"
    fi
done

mv -f "$tmp_file" "$ENV_FILE"
chmod 600 "$ENV_FILE"
unset app_password
trap - EXIT

echo "Google Workspace configurado para $SENDER_EMAIL."
echo "El envio global permanece desactivado hasta completar la prueba."
