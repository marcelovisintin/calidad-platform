# Inicio de datos reales - 25/08/2026

## Objetivo

Separar definitivamente los datos operativos de prueba de la base de producción,
sin modificar usuarios, permisos, alcances ni catálogos maestros. La copia previa
queda disponible como entorno local para validar cambios antes de desplegarlos.

## Respaldo de referencia

- Servidor: `/srv/calidad-platform/backups/20260825-074003`
- Copia local (excluida de Git): `backups/20260825-pre-produccion-real`
- Base, SHA-256: `1a952875d8f937082c3e042ffa439dc18d5dc8b28b49f3196f86c7ce3336f15f`
- Archivos, SHA-256: `7eeaa7c977feb8acfda1bee82d27df2588f428807a18782e9eb2cbebb80644f6`
- Contenido: dump completo de PostgreSQL, fotos, adjuntos y evidencias.

La copia fue validada con `gzip -t`, `tar -tzf` y mediante una restauración real
en PostgreSQL local antes de limpiar producción.

## Inventario preservado en producción

- 30 usuarios.
- 5 roles y 63 relaciones rol-permiso.
- 22 permisos específicos de usuario.
- 4 alcances de usuario.
- 147 registros de catálogos: sectores/áreas, sitios, orígenes, tipos,
  prioridades, severidades y tipos de acción.
- Fotos de usuario y demás archivos no asociados a registros operativos.

## Datos operativos retirados

- 15 anomalías y todas sus clasificaciones, seguimientos, participantes,
  verificaciones y reservas de código.
- 4 tratamientos y todas sus causas, participantes, tareas, lecciones y
  relaciones con anomalías.
- Adjuntos y evidencias asociados a esos registros.
- Notificaciones, pendientes y eventos de auditoría generados durante las
  pruebas.

Después de la limpieza todas las tablas operativas quedaron en cero y la próxima
anomalía y el próximo tratamiento comenzarán en `0001` para el año vigente.

## Entorno local de pruebas

- URL: `http://127.0.0.1:8091/login`
- Proyecto Docker Compose: `calidad-test`
- Configuración local excluida de Git: `deploy/docker/.env.test.local`
- Datos persistentes excluidos de Git: `backups/local-test-runtime`
- Datos restaurados: 30 usuarios, 15 anomalías, 4 tratamientos y 44 archivos.
- Correo: deshabilitado con `EMAIL_NOTIFICATIONS_ENABLED=False` y backend de
  memoria; este entorno nunca debe enviar mensajes reales.

Inicio del entorno ya restaurado:

```powershell
docker compose -p calidad-test `
  --env-file deploy/docker/.env.test.local `
  -f deploy/docker/docker-compose.local.yml `
  up -d --no-build
```

Detención sin borrar la base ni los archivos:

```powershell
docker compose -p calidad-test `
  --env-file deploy/docker/.env.test.local `
  -f deploy/docker/docker-compose.local.yml `
  stop
```

No usar `down -v`, no borrar `backups/local-test-runtime` y no ejecutar el
script de reset total sobre este entorno si se desea conservar la referencia.

## Flujo de versiones desde esta fecha

1. Crear una rama `feature/...` o `fix/...` desde `main`.
2. Implementar y ejecutar pruebas automáticas.
3. Construir y probar la rama en `calidad-test` sobre la copia histórica.
4. Hacer commits pequeños y descriptivos y publicar la rama en GitHub.
5. Integrar en `main` solo después de la validación local.
6. Crear una etiqueta de versión para cada despliegue aprobado.
7. Desplegar por hash de commit y ejecutar un backup previo de producción.

La base y los archivos reales o de prueba nunca se incorporan al repositorio.
