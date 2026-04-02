# Despliegue local inicial cloud-ready

## Arquitectura recomendada

Para el despliegue inicial en planta recomiendo un servidor local dedicado dentro de la red interna, idealmente una VM o host Linux administrado por IT. La PC de calidad debe seguir siendo solo terminal de uso. La topologia recomendada es esta:

- `frontend`: contenedor Nginx que sirve el build de React/PWA, hace proxy de `/api` y `/static`, y bloquea el acceso directo a `/media`
- `backend`: contenedor Django + DRF ejecutando con Gunicorn
- `db`: contenedor PostgreSQL, sin exponer el puerto a la red interna
- `storage`: volumen o ruta del host para adjuntos y temporales
- `runtime`: rutas del host para staticfiles y logs
- `backups`: ruta del host para copias de seguridad nocturnas

La red interna accede solo al `frontend` por HTTP o HTTPS. El frontend no necesita saber la IP del backend, porque consume por misma origin (`/api/v1`). Eso deja el cambio a nube muy desacoplado.

## Separacion de componentes

La separacion operativa recomendada es esta:

- Aplicacion backend:
  - imagen `backend`
  - codigo Django/DRF
  - no guarda datos persistentes dentro del contenedor
- Frontend:
  - imagen `frontend`
  - build estatico de React + TypeScript + PWA
  - expone la UI y reenvia `/api/` hacia Django
- Base de datos:
  - contenedor PostgreSQL
  - almacenamiento persistente propio
- Archivos adjuntos:
  - ruta separada del host para `media`
  - desacoplada del codigo y del contenedor
- Configuracion:
  - archivo de entorno real fuera del repo, por ejemplo `D:/calidad-platform/config/.env.server.local` o `/srv/calidad-platform/config/.env.server.local`
  - sin IPs hardcodeadas en el codigo
- Logs:
  - stdout de contenedores para observacion rapida
  - logs de aplicacion en `runtime/logs` si `DJANGO_LOG_TO_FILE=true`
- Backups:
  - salida en ruta separada del host
  - respaldo de PostgreSQL y de `media`

## Rutas recomendadas en el servidor

Estas rutas deben vivir fuera del arbol del codigo para que una actualizacion de app no toque datos operativos:

```text
/srv/calidad-platform/
|- postgres/
|- storage/
|  |- media/
|  \- tmp/
|- runtime/
|  |- staticfiles/
|  \- logs/
\- backups/
```

El repositorio puede quedar, por ejemplo, en:

```text
/opt/calidad/app
```

Con esto, una migracion futura a nube implica mover imagenes y montar estos mismos conceptos en otro storage.

## Buenas practicas operativas

### Variables de entorno

- mantener secretos y configuracion fuera del repo
- usar `DJANGO_SETTINGS_MODULE=config.settings.production` en servidor
- definir `DJANGO_SECRET_KEY`, credenciales PostgreSQL y hosts permitidos por entorno
- mantener `VITE_API_BASE_URL=/api/v1` en produccion para evitar hardcodear host

### No hardcodear IPs

- publicar la app con un nombre DNS interno, por ejemplo `calidad.local` o `calidad-srv`
- usar ese hostname en `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`
- desde frontend, siempre consumir ` /api/v1 ` por misma origin

### Adjuntos

- guardar adjuntos solo en `media`
- no guardar adjuntos dentro del contenedor
- incluir `media` en backups y en plan de migracion
- no exponer `/media/` directamente; usar descarga protegida por backend o URLs firmadas
- en nube, esta capa puede migrarse a NAS administrado o a object storage sin redisenar el dominio

### Backups

- ejecutar backup nocturno de PostgreSQL con `pg_dump`
- validar restauracion periodica con `deploy/backups/restore_local.sh`
- comprimir y copiar `media`
- guardar al menos 14 dias locales y, si es posible, una copia fuera del servidor
- probar restauracion periodicamente

### Logs

- mantener logs por stdout para soporte rapido con Docker
- habilitar `DJANGO_LOG_TO_FILE=true` para disponer de logs persistentes en `runtime/logs`
- separar logs de aplicacion de datos y backups

### Seguridad basica

- no exponer PostgreSQL a la LAN
- limitar firewall del servidor a `80/443` y puertos de administracion
- usar secretos fuertes
- usar `DEBUG=False`
- si la red lo permite, preferir HTTPS interno con certificado corporativo o reverse proxy de IT
- usar cuentas de aplicacion y de base de datos dedicadas

## Por que Docker si

Para este escenario si recomiendo Docker Compose, porque:

- separa backend, frontend y PostgreSQL sin instalar todo en el host
- hace mas predecible el despliegue en planta
- simplifica backups, rollback y actualizaciones
- prepara una futura migracion a nube con cambios minimos
- evita dependencia en configuraciones manuales de una PC puntual

No lo recomendaria solo si el area de infraestructura prohibe contenedores. En ese caso, la alternativa seria:

- Nginx nativo
- Django en un servicio del sistema
- PostgreSQL nativo o gestionado

pero se pierde portabilidad y se incrementa el trabajo de migracion futura.

## Que debe mantenerse desacoplado para migrar a nube

Para que la migracion futura implique sobre todo infraestructura y configuracion, conviene mantener desacoplado:

- backend como imagen o proceso independiente
- frontend como build estatico separado
- PostgreSQL como servicio de datos migrable
- `media` como almacenamiento aparte del codigo
- configuracion por variables de entorno
- backups y logs fuera de la app

Mapa de migracion esperado:

- Local actual:
  - Docker Compose + rutas del host
- Futuro nube:
  - frontend en CDN o container app
  - backend en container app, VM o Kubernetes
  - PostgreSQL administrado
  - `media` en object storage o file share
  - secretos en vault o secret manager

## Archivos incluidos en esta base de despliegue

- `deploy/docker/docker-compose.local.yml`
- `deploy/docker/backend.Dockerfile`
- `deploy/docker/frontend.Dockerfile`
- `deploy/docker/.env.server.example`
- archivo real recomendado: `D:/calidad-platform/config/.env.server.local` (Windows) o `/srv/calidad-platform/config/.env.server.local` (Linux)
- `deploy/nginx/calidad.conf`
- `deploy/scripts/start_local_stack.sh`
- `deploy/backups/backup_local.sh`
- `deploy/backups/restore_local.sh`

## Puesta en marcha sugerida

1. Copiar `deploy/docker/.env.server.example` a un archivo seguro fuera del repo, por ejemplo `D:/calidad-platform/config/.env.server.local`
2. Ajustar secretos, hostname y rutas del host
3. Ejecutar:

```bash
cd deploy/docker
../scripts/start_local_stack.sh
```

4. Verificar:

- frontend: `http://calidad.local/`
- backend health: `http://calidad.local/api/v1/core/health/`
- admin: `http://calidad.local/admin/`

## Notas de consistencia con la app actual

- el backend ya soporta `STORAGE_ROOT`, `MEDIA_ROOT`, `TEMP_FILES_ROOT` y `STATIC_ROOT` por variables de entorno
- el frontend ya usa `VITE_API_BASE_URL` con default `/api/v1`, lo cual es ideal para misma origin
- la configuracion agregada para logs a archivo es opcional y no rompe el flujo actual de desarrollo
