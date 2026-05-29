# Guia de desbloqueo para auditoria

Esta guia documenta como exponer la aplicacion de forma verificable para una corrida de auditoria funcional y de seguridad. El objetivo inmediato es que el auditor pueda llegar al login, identificar artefactos operativos y reiniciar datos de prueba de manera reproducible.

## Artefactos operativos

| Elemento | Ubicacion |
| --- | --- |
| Compose local | `deploy/docker/docker-compose.local.yml` |
| Variables ejemplo | `deploy/docker/.env.server.example` |
| Variables reales locales | `deploy/docker/.env.server.local` o `deploy/docker/.env.server` |
| Dockerfile backend | `deploy/docker/backend.Dockerfile` |
| Dockerfile frontend | `deploy/docker/frontend.Dockerfile` |
| Nginx / proxy API | `deploy/nginx/calidad.conf` |
| Arranque Windows | `deploy/scripts/start_local_stack.ps1` |
| Reset datos de prueba | `deploy/scripts/reset_test_data.ps1` |
| Backups | `deploy/backups/backup_local.sh` y `deploy/backups/restore_local.sh` |

El archivo Compose define tres servicios:

- `db`: PostgreSQL 17 sin puerto publicado a la red.
- `backend`: Django + DRF + Gunicorn, expuesto solo dentro de la red Docker como `backend:8000`.
- `frontend`: Nginx + build React, publica HTTP y HTTPS al host y hace proxy de `/api/` al backend.

La red Docker es `calidad-internal`. Los datos persistentes se montan desde rutas configuradas en el archivo env.

## Politica de variables y secretos

El repositorio versiona solo ejemplos:

- `.env.example`
- `deploy/docker/.env.server.example`

Los archivos reales quedan fuera de Git por `.gitignore`:

- `.env`
- `.env.*`
- `deploy/docker/.env.server`
- `deploy/docker/.env.server.local`

Variables sensibles actuales:

- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- credenciales operativas que se creen para auditoria o administracion

Para una auditoria local controlada se acepta `env_file`/`--env-file` con archivo no versionado. Para un entorno productivo o compartido, la mejora recomendada es mover secretos sensibles a Docker secrets o al gestor corporativo de secretos, manteniendo en env solo configuracion no sensible.

## Acceso verificable

Arranque recomendado en Windows:

```powershell
cd D:\SCHNEIDER\2026\CALIDAD
powershell -ExecutionPolicy Bypass -File deploy/scripts/start_local_stack.ps1
```

El script muestra las URLs detectadas. Con la configuracion actual de `deploy/docker/docker-compose.local.yml`, el frontend publica:

- HTTP: `0.0.0.0:${FRONTEND_BIND_PORT}`; por defecto `8088`
- HTTPS: `0.0.0.0:${FRONTEND_TLS_BIND_PORT}`; por defecto `8443`

URLs esperadas:

```text
http://localhost:8088/login
http://<IP_LAN_DEL_SERVIDOR>:8088/login
https://localhost:8443/login
https://<IP_LAN_DEL_SERVIDOR>:8443/login
```

Verificaciones no destructivas:

```powershell
docker compose --env-file deploy/docker/.env.server.local -f deploy/docker/docker-compose.local.yml ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8088/healthz
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8088/api/v1/core/health/
```

Si el auditor ejecuta desde otra PC o VM, validar:

- que `FRONTEND_BIND_PORT` y `FRONTEND_TLS_BIND_PORT` esten publicados;
- que el binding sea `0.0.0.0` si se requiere acceso LAN;
- que el firewall permita el puerto desde la red de auditoria;
- que `DJANGO_ALLOWED_HOSTS` incluya el hostname/IP usado;
- que `DJANGO_CSRF_TRUSTED_ORIGINS` incluya el origen HTTP/HTTPS usado.

## Logs

Logs rapidos por contenedor:

```powershell
docker compose --env-file deploy/docker/.env.server.local -f deploy/docker/docker-compose.local.yml logs backend
docker compose --env-file deploy/docker/.env.server.local -f deploy/docker/docker-compose.local.yml logs frontend
docker compose --env-file deploy/docker/.env.server.local -f deploy/docker/docker-compose.local.yml logs db
```

Logs persistentes de aplicacion:

- habilitar `DJANGO_LOG_TO_FILE=true`;
- revisar `APP_LOG_FILE`, por defecto `calidad-platform.log`;
- ruta dentro del contenedor: `${LOG_DIR}`;
- ruta en host: `${HOST_LOG_ROOT}`.

Con el env ejemplo:

```text
D:/calidad-platform/runtime/logs/calidad-platform.log
```

## Reset reproducible de datos de prueba

Para reiniciar datos de prueba y crear un usuario auditor:

```powershell
cd D:\SCHNEIDER\2026\CALIDAD
powershell -ExecutionPolicy Bypass -File deploy/scripts/reset_test_data.ps1 -AuditPassword "Cambiar-Esta-Clave-Larga-2026"
```

El script:

- detiene el stack Compose;
- elimina datos persistentes de PostgreSQL, media, tmp y static definidos en el env;
- no elimina backups;
- no elimina certificados TLS;
- levanta el stack nuevamente;
- ejecuta migraciones mediante el comando del backend;
- crea o actualiza el usuario `auditor` como superusuario/desarrollador.

Para limpiar tambien logs de prueba:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/scripts/reset_test_data.ps1 -AuditPassword "Cambiar-Esta-Clave-Larga-2026" -ClearLogs
```

Para ver que haria sin borrar:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/scripts/reset_test_data.ps1 -AuditPassword "Cambiar-Esta-Clave-Larga-2026" -WhatIf
```

## Secuencia sugerida de auditoria funcional

1. Login y gestion de sesion.
2. Inventario de usuarios, roles, permisos y alcances reales.
3. Control de acceso por modulo y por request.
4. Ciclo completo de anomalias/incidentes.
5. API discovery y pruebas no destructivas de auth bypass, IDOR, CSRF y XSS.
6. Uploads y descarga protegida de evidencias.
7. Password reset y politicas de credenciales.
8. Logging, auditoria y reporting.
9. Usabilidad, mobile y accesibilidad WCAG 2.2.

## Criterios de seguridad a observar en la segunda fase

- minimo privilegio y validacion por request;
- expiracion y revocacion de sesion/token;
- no usar GET para cambios de estado;
- password reset robusto;
- uploads con validacion de tipo, tamano y acceso;
- logs suficientes para eventos sensibles;
- politicas de contrasena basadas en longitud razonable;
- accesibilidad evaluada con WCAG 2.2.
