#!/usr/bin/env sh
set -eu

CERT_FILE="${TLS_CERT_FILE:-/etc/nginx/certs/local.crt}"
KEY_FILE="${TLS_KEY_FILE:-/etc/nginx/certs/local.key}"
COMMON_NAME="${TLS_COMMON_NAME:-calidad.local}"
CERT_DAYS="${TLS_CERT_DAYS:-825}"
SAN_LIST="${TLS_SAN:-DNS:localhost,DNS:calidad.local,DNS:calidad-srv,IP:127.0.0.1}"

mkdir -p "$(dirname "$CERT_FILE")"

if [ ! -s "$CERT_FILE" ] || [ ! -s "$KEY_FILE" ]; then
  echo "Generating self-signed TLS certificate for ${COMMON_NAME}"
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -days "$CERT_DAYS" \
    -subj "/CN=${COMMON_NAME}" \
    -addext "subjectAltName = ${SAN_LIST}"

  chmod 600 "$KEY_FILE"
fi