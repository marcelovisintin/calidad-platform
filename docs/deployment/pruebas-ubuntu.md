# Instancia Pruebas en Ubuntu

La instancia **Pruebas** corre en el mismo servidor que producción, con un proyecto Docker Compose independiente (`calidad-pruebas`). Producción conserva los puertos `8088` y `8443`; Pruebas usa `8092` y `8452`.

| Recurso | Producción | Pruebas |
| --- | --- | --- |
| Aplicación | `/opt/calidad/app` | `/opt/calidad/pruebas/app` |
| Configuración | `/srv/calidad-platform/config/.env.server.local` | `/srv/calidad-platform/pruebas/config/.env.server.local` |
| PostgreSQL y adjuntos | `/srv/calidad-platform` | `/srv/calidad-platform/pruebas` |
| Proyecto Compose | `docker` | `calidad-pruebas` |

La base inicial de Pruebas es una copia de la instancia local `docker` del 21/09/2026: **600 anomalías sintéticas**. La instancia local `calidad-test` contiene solo 21 y no se usa como origen. Se copiaron el respaldo PostgreSQL y los archivos multimedia asociados. Las credenciales de usuarios son las de esa base local.

El respaldo inicial quedó en `/srv/calidad-platform/pruebas/backups/inicial-20260921.dump` junto con `inicial-20260921-media.tar.gz`.

La aplicación muestra **ENTORNO DE PRUEBAS** en el inicio de sesión y en la navegación. El correo está desactivado y configurado con el backend `dummy`. Pruebas utiliza una clave Django y una contraseña PostgreSQL independientes.

## Comandos operativos

```bash
ENV_FILE=/srv/calidad-platform/pruebas/config/.env.server.local
COMPOSE_FILE=/opt/calidad/pruebas/app/deploy/docker/docker-compose.local.yml
docker compose --project-name calidad-pruebas --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
docker compose --project-name calidad-pruebas --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=100
```

La actualización de Pruebas debe usar su propio directorio de aplicación y el proyecto `calidad-pruebas`. No ejecutar `deploy_update.sh` para esta instancia: ese script fija la etiqueta de entorno como `production` y el estado de actualización de producción.

Antes de actualizar o reemplazar la base de Pruebas, generar un respaldo de su PostgreSQL y sus adjuntos en `/srv/calidad-platform/pruebas/backups`. La copia inicial no se sincroniza automáticamente con la base local.
