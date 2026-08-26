# Despliegue en notebook Ubuntu

## Servidor

- Host: `sgc2026`
- Sistema: Ubuntu Server 26.04 LTS
- IP fija: `172.16.245.253/16`
- Usuario de administracion: `sgc`
- Aplicacion: `/opt/calidad/app`
- Datos persistentes: `/srv/calidad-platform`
- Configuracion secreta: `/srv/calidad-platform/config/.env.server.local`

Las contrasenas y secretos no se documentan en el repositorio.

## Acceso

```text
http://172.16.245.253:8088/login
https://172.16.245.253:8443/login
```

HTTPS utiliza inicialmente un certificado autofirmado. Para el piloto interno
puede usarse HTTP; para produccion formal debe instalarse un certificado emitido
por IT.

## Servicios

El despliegue usa Docker Compose:

- PostgreSQL 17 sin puerto publicado a la LAN;
- Django/Gunicorn solo dentro de la red Docker;
- React/Nginx publicado en `8088` y `8443`.

Los contenedores tienen politica `restart: unless-stopped` y Docker esta
habilitado en systemd, por lo que vuelven a iniciar despues de reiniciar Ubuntu.

El envio de correos utiliza `calidad-email-dispatch.timer`. El timer consulta la
cola una vez por minuto, pero no envia nada mientras
`EMAIL_NOTIFICATIONS_ENABLED=False` en el archivo de configuracion secreta.

El mismo despachador genera, desde las `EMAIL_DUE_DIGEST_HOUR` (07:00 por
defecto), un resumen diario que agrupa por usuario los pendientes vencidos y los
que vencen en los proximos `EMAIL_DUE_REMINDER_DAYS` dias. El proceso es
idempotente y evita repetir el resumen del mismo dia.

Para Google Workspace se usa `smtp.gmail.com`, puerto `587` y TLS. La cuenta
remitente debe ser una cuenta tecnica `@schneider.ar` con verificacion en dos
pasos y una contrasena de aplicacion. Esa contrasena se guarda unicamente en
`/srv/calidad-platform/config/.env.server.local`; nunca en Git.

La carga se realiza interactivamente en el servidor, sin mostrar la credencial:

```bash
cd /opt/calidad/app
ENV_FILE=/srv/calidad-platform/config/.env.server.local \
  bash deploy/scripts/configure_gmail_smtp.sh marcelo.v@schneider.ar
```

El script conserva `EMAIL_NOTIFICATIONS_ENABLED=False`. Luego de reconstruir el
backend se valida con un solo correo controlado:

```bash
docker compose \
  --env-file /srv/calidad-platform/config/.env.server.local \
  -f deploy/docker/docker-compose.local.yml \
  exec -T backend python manage.py test_email_configuration \
  --to marcelo.v@schneider.ar --confirm
```

Estado:

```bash
cd /opt/calidad/app
docker compose \
  --env-file /srv/calidad-platform/config/.env.server.local \
  -f deploy/docker/docker-compose.local.yml ps
```

Logs:

```bash
cd /opt/calidad/app
docker compose \
  --env-file /srv/calidad-platform/config/.env.server.local \
  -f deploy/docker/docker-compose.local.yml logs --tail=200
```

## Backups

El timer `calidad-backup.timer` ejecuta un backup diario aproximadamente a las
02:00 y guarda PostgreSQL, media y metadatos en:

```text
/srv/calidad-platform/backups
```

Verificacion:

```bash
systemctl status calidad-backup.timer
systemctl list-timers calidad-backup.timer
```

Se configuraron 30 dias de retencion local. Debe mantenerse ademas una copia
periodica fuera de la notebook.

## Actualizacion

Antes de actualizar:

```bash
sudo systemctl start calidad-backup.service
```

Luego copiar la nueva version a `/opt/calidad/app` y ejecutar:

```bash
cd /opt/calidad/app
ENV_FILE=/srv/calidad-platform/config/.env.server.local \
  sh deploy/scripts/deploy_update.sh
```

Este comando publica el estado del despliegue para que los dispositivos abiertos
muestren el aviso de actualizacion, protege formularios con cambios sin guardar y
habilita la recarga automatica al finalizar. Finalmente comprobar `/healthz`, la
API y el estado de los contenedores.
