# Despliegue nativo en Raspberry Pi 4 sin Docker

## Objetivo

Desplegar la plataforma de calidad en una Raspberry Pi 4 con Ubuntu Server 64-bit, sin Docker, usando servicios nativos:

- Nginx para servir el frontend y hacer proxy de API
- Gunicorn + Django para backend
- PostgreSQL local
- systemd para arranque automatico
- rutas persistentes para media, static, logs y backups

Esta opcion sirve para piloto productivo liviano en red interna.

## Arquitectura

```text
Usuarios LAN
   |
   | HTTPS / HTTP interno
   v
Nginx Raspberry
   |- /              -> React build
   |- /api/          -> Gunicorn Django
   |- /static/       -> staticfiles Django
   |- /media/        -> bloqueado
   v
Gunicorn
   v
Django + PostgreSQL local
```

## Recomendacion para Raspberry Pi 4

Usar:

- Raspberry Pi 4 de 4 GB
- Ubuntu Server 64-bit
- SSD USB 3.0 para datos operativos
- swap de 2 GB
- PostgreSQL, media, logs y backups en SSD
- `GUNICORN_WORKERS=2`

No usar microSD comun para la base de datos si el sistema va a operar todos los dias.

## Rutas recomendadas

Codigo:

```text
/opt/calidad/app
```

Datos persistentes:

```text
/srv/calidad-platform/
|- postgres/              # opcional si PostgreSQL se reubica al SSD
|- storage/
|  |- media/
|  \- tmp/
|- runtime/
|  |- staticfiles/
|  \- logs/
\- backups/
```

## Paquetes base

```bash
sudo apt update
sudo apt install -y \
  git nginx postgresql postgresql-contrib \
  python3 python3-venv python3-dev build-essential libpq-dev \
  nodejs npm
```

Verificar que Node sea una version suficientemente nueva para Vite. Si Ubuntu instala una version vieja, instalar Node LTS desde NodeSource.

## Usuario de servicio

```bash
sudo adduser --system --group --home /opt/calidad calidad
sudo mkdir -p /opt/calidad/app
sudo mkdir -p /srv/calidad-platform/storage/media
sudo mkdir -p /srv/calidad-platform/storage/tmp
sudo mkdir -p /srv/calidad-platform/runtime/staticfiles
sudo mkdir -p /srv/calidad-platform/runtime/logs
sudo mkdir -p /srv/calidad-platform/backups
sudo chown -R calidad:calidad /opt/calidad /srv/calidad-platform
```

## Base de datos

```bash
sudo -u postgres psql
```

Dentro de `psql`:

```sql
CREATE DATABASE calidad;
CREATE USER calidad WITH PASSWORD 'CAMBIAR_PASSWORD_SEGURO';
ALTER ROLE calidad SET client_encoding TO 'utf8';
ALTER ROLE calidad SET default_transaction_isolation TO 'read committed';
ALTER ROLE calidad SET timezone TO 'America/Argentina/Buenos_Aires';
GRANT ALL PRIVILEGES ON DATABASE calidad TO calidad;
\q
```

## Variables de entorno

Crear:

```text
/srv/calidad-platform/config/.env
```

Contenido sugerido:

```env
APP_SLUG=calidad-platform
PUBLIC_HOSTNAME=calidad-srv

DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=CAMBIAR_POR_SECRETO_LARGO_DE_MAS_DE_32_CARACTERES
DJANGO_ALLOWED_HOSTS=calidad-srv,calidad.local,localhost,127.0.0.1,IP_DE_LA_RASPBERRY
DJANGO_CSRF_TRUSTED_ORIGINS=https://calidad-srv,https://calidad.local,https://IP_DE_LA_RASPBERRY
DJANGO_DEBUG=False

POSTGRES_DB=calidad
POSTGRES_USER=calidad
POSTGRES_PASSWORD=CAMBIAR_PASSWORD_SEGURO
POSTGRES_HOST=localhost
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

STORAGE_ROOT=/srv/calidad-platform/storage
MEDIA_ROOT=/srv/calidad-platform/storage/media
TEMP_FILES_ROOT=/srv/calidad-platform/storage/tmp
STATIC_ROOT=/srv/calidad-platform/runtime/staticfiles
LOG_DIR=/srv/calidad-platform/runtime/logs

FILE_UPLOAD_MAX_MEMORY_SIZE=5242880
DATA_UPLOAD_MAX_MEMORY_SIZE=10485760
LAST_ACTIVITY_UPDATE_WINDOW_SECONDS=300
JWT_ACCESS_TOKEN_MINUTES=15
JWT_REFRESH_TOKEN_MINUTES=480
DRF_ANON_RATE=60/minute
DRF_USER_RATE=6000/hour
DRF_LOGIN_RATE=10/minute

GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
```

Proteger el archivo:

```bash
sudo chown calidad:calidad /srv/calidad-platform/config/.env
sudo chmod 600 /srv/calidad-platform/config/.env
```

## Backend

Clonar o copiar el repositorio en:

```text
/opt/calidad/app
```

Instalar dependencias:

```bash
cd /opt/calidad/app/backend
sudo -u calidad python3 -m venv .venv
sudo -u calidad .venv/bin/pip install --upgrade pip
sudo -u calidad .venv/bin/pip install -r requirements/production.txt
```

Ejecutar migraciones y staticfiles:

```bash
cd /opt/calidad/app/backend
sudo -u calidad env $(cat /srv/calidad-platform/config/.env | xargs) .venv/bin/python manage.py migrate
sudo -u calidad env $(cat /srv/calidad-platform/config/.env | xargs) .venv/bin/python manage.py collectstatic --noinput
sudo -u calidad env $(cat /srv/calidad-platform/config/.env | xargs) .venv/bin/python manage.py check
```

## systemd para backend

Crear:

```text
/etc/systemd/system/calidad-backend.service
```

Contenido:

```ini
[Unit]
Description=Calidad Platform Backend
After=network.target postgresql.service

[Service]
User=calidad
Group=calidad
WorkingDirectory=/opt/calidad/app/backend
EnvironmentFile=/srv/calidad-platform/config/.env
ExecStart=/opt/calidad/app/backend/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable calidad-backend
sudo systemctl start calidad-backend
sudo systemctl status calidad-backend
```

## Frontend

Construir React:

```bash
cd /opt/calidad/app/frontend
npm ci
VITE_API_BASE_URL=/api/v1 VITE_CATALOG_BOOTSTRAP_URL=/catalog.bootstrap.json npm run build
```

Publicar build:

```bash
sudo mkdir -p /var/www/calidad
sudo rsync -a --delete /opt/calidad/app/frontend/dist/ /var/www/calidad/
sudo chown -R www-data:www-data /var/www/calidad
```

## HTTPS interno

Para piloto puede usarse certificado autofirmado:

```bash
sudo mkdir -p /etc/nginx/certs
sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout /etc/nginx/certs/calidad.local.key \
  -out /etc/nginx/certs/calidad.local.crt \
  -subj "/CN=calidad-srv"
```

En produccion formal, preferir certificado emitido por IT.

## Nginx

Crear:

```text
/etc/nginx/sites-available/calidad
```

Contenido:

```nginx
server {
    listen 80;
    server_name calidad-srv calidad.local IP_DE_LA_RASPBERRY;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name calidad-srv calidad.local IP_DE_LA_RASPBERRY;
    server_tokens off;

    root /var/www/calidad;
    index index.html;
    client_max_body_size 20m;

    ssl_certificate /etc/nginx/certs/calidad.local.crt;
    ssl_certificate_key /etc/nginx/certs/calidad.local.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "same-origin" always;

    location = /healthz {
        add_header Content-Type text/plain;
        return 200 "ok";
    }

    location /static/ {
        alias /srv/calidad-platform/runtime/staticfiles/;
        access_log off;
        expires 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    location /media/ {
        return 403;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Activar:

```bash
sudo ln -s /etc/nginx/sites-available/calidad /etc/nginx/sites-enabled/calidad
sudo nginx -t
sudo systemctl reload nginx
```

## Verificacion

```bash
systemctl status calidad-backend
curl -k https://localhost/healthz
curl -k https://localhost/api/v1/core/health/
```

Desde una PC de la red:

```text
https://IP_DE_LA_RASPBERRY/login
```

## Backups minimos

Crear backup diario de PostgreSQL y media:

```bash
pg_dump -U calidad -h localhost calidad > /srv/calidad-platform/backups/calidad_$(date +%Y%m%d_%H%M%S).sql
tar -czf /srv/calidad-platform/backups/media_$(date +%Y%m%d_%H%M%S).tar.gz -C /srv/calidad-platform/storage media
```

Programar con cron y guardar al menos 14 dias.

## Actualizacion de version

Secuencia recomendada:

```bash
cd /opt/calidad/app
git pull

cd backend
sudo -u calidad .venv/bin/pip install -r requirements/production.txt
sudo -u calidad env $(cat /srv/calidad-platform/config/.env | xargs) .venv/bin/python manage.py migrate
sudo -u calidad env $(cat /srv/calidad-platform/config/.env | xargs) .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart calidad-backend

cd ../frontend
npm ci
VITE_API_BASE_URL=/api/v1 VITE_CATALOG_BOOTSTRAP_URL=/catalog.bootstrap.json npm run build
sudo rsync -a --delete dist/ /var/www/calidad/
sudo systemctl reload nginx
```

## Riesgos y limites

- La Raspberry Pi 4 de 4 GB sirve para piloto y uso liviano.
- Para muchos usuarios concurrentes o reportes pesados, conviene mini PC con 8 GB o mas.
- PostgreSQL debe vivir preferentemente en SSD.
- El backend en produccion usa cookies seguras, por eso HTTPS es recomendable desde el inicio.
- No correr vision artificial, modelos IA ni servicios pesados en esta misma Raspberry.
