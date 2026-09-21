"""Create an isolated server env file for the Pruebas Docker Compose project."""

import argparse
import os
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--http-port", type=int, required=True)
    parser.add_argument("--https-port", type=int, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        parser.error("Source and output env files must differ.")
    if not 1 <= args.http_port <= 65535 or not 1 <= args.https_port <= 65535:
        parser.error("Ports must be between 1 and 65535.")
    if args.http_port == args.https_port:
        parser.error("HTTP and HTTPS ports must differ.")

    values = {}
    for line in args.source.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    if not values.get("POSTGRES_DB") or not values.get("POSTGRES_USER"):
        parser.error("Source env file is missing PostgreSQL settings.")

    root = args.data_root.resolve()
    for key in ("HOST_POSTGRES_DATA", "HOST_MEDIA_ROOT", "HOST_TLS_CERTS"):
        source_path = Path(values.get(key, "/")).resolve()
        if source_path == root or root in source_path.parents or source_path in root.parents:
            parser.error(f"Pruebas data root overlaps the production path in {key}.")

    values.update(
        APP_SLUG="calidad-pruebas",
        APP_PUBLIC_URL=f"http://{args.host}:{args.http_port}",
        PUBLIC_HOSTNAME=args.host,
        FRONTEND_BIND_PORT=str(args.http_port),
        FRONTEND_TLS_BIND_PORT=str(args.https_port),
        TLS_SAN=f"IP:{args.host},IP:127.0.0.1,DNS:localhost",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(48),
        DJANGO_ALLOWED_HOSTS=f"{args.host},localhost,127.0.0.1",
        DJANGO_CSRF_TRUSTED_ORIGINS=(
            f"http://{args.host}:{args.http_port},https://{args.host}:{args.https_port},"
            f"http://localhost:{args.http_port},https://localhost:{args.https_port}"
        ),
        POSTGRES_DB="calidad_pruebas",
        POSTGRES_USER="calidad_pruebas",
        POSTGRES_PASSWORD=secrets.token_urlsafe(36),
        HOST_POSTGRES_DATA=str(root / "postgres"),
        HOST_MEDIA_ROOT=str(root / "storage" / "media"),
        HOST_TMP_ROOT=str(root / "storage" / "tmp"),
        HOST_STATIC_ROOT=str(root / "runtime" / "staticfiles"),
        HOST_LOG_ROOT=str(root / "runtime" / "logs"),
        HOST_BACKUP_ROOT=str(root / "backups"),
        HOST_TLS_CERTS=str(root / "runtime" / "certs"),
        HOST_UPDATE_STATUS_ROOT=str(root / "runtime" / "update"),
        HOST_SMTP_CA_DIR=str(root / "runtime" / "smtp-ca"),
        EMAIL_NOTIFICATIONS_ENABLED="False",
        EMAIL_LOCAL_DISPATCH_ENABLED="False",
        EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend",
        EMAIL_HOST="localhost",
        EMAIL_PORT="25",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
        EMAIL_USE_TLS="False",
        EMAIL_USE_SSL="False",
        EMAIL_CA_CERT_FILE="",
        DEFAULT_FROM_EMAIL="pruebas@localhost",
        GUNICORN_WORKERS="1",
        APP_DEPLOYMENT_ENV="pruebas",
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        target.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")


if __name__ == "__main__":
    main()
