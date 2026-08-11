# Datos operativos y backups

## Estado inicial de la prueba productiva

El 27 de julio de 2026 se eliminaron los datos operativos usados durante el
desarrollo. Se conservaron usuarios, fotos de perfil, roles, permisos, alcances,
plantillas de notificacion y catalogos maestros.

La numeracion visible se reinicio. Para 2026, los primeros codigos esperados son:

- anomalia: `20260001`;
- tratamiento: `TRT-2026-0001`.

## Limpieza selectiva

El comando seguro muestra una simulacion si no se informa `--confirm`:

```powershell
docker compose --env-file deploy/docker/.env.server.local `
  -f deploy/docker/docker-compose.local.yml `
  exec -T backend python manage.py clear_operational_data
```

Solo despues de verificar un backup se puede confirmar:

```powershell
docker compose --env-file deploy/docker/.env.server.local `
  -f deploy/docker/docker-compose.local.yml `
  exec -T backend python manage.py clear_operational_data --confirm
```

El comando:

- elimina anomalias, acciones, tratamientos y todos sus registros dependientes;
- elimina notificaciones, pendientes, auditoria y reservas de codigos;
- elimina las evidencias fisicas referenciadas;
- conserva y verifica usuarios, roles, alcances y catalogos;
- no elimina fotos de usuarios;
- aborta y revierte la transaccion si cambia algun conjunto protegido.

No debe utilizarse `reset_test_data.ps1` para esta tarea porque reinicia toda la
base, incluidos usuarios y maestros.

## Politica durante la prueba productiva

Los datos cargados desde esta fecha deben tratarse como datos reales:

1. Ejecutar un backup diario de PostgreSQL y media.
2. Conservar al menos 30 copias diarias y 12 copias mensuales.
3. Mantener una copia adicional fuera del equipo que ejecuta Docker.
4. Cifrar el medio externo y limitar el acceso a administradores.
5. Probar una restauracion al menos una vez por mes en un entorno separado.
6. No usar la base real para pruebas destructivas; usar una copia restaurada.

El destino configurado actualmente es `HOST_BACKUP_ROOT`, definido en el archivo
local de entorno. Los backups contienen:

- `postgres.sql.gz`: base de datos completa;
- `media.tar.gz`: evidencias y fotos;
- `metadata.txt`: fecha, base y ruta de almacenamiento.

## Paso a produccion definitiva

No sera necesario volver a cargar la informacion. El lanzamiento debe hacerse
mediante migracion controlada:

1. detener temporalmente nuevas cargas;
2. generar y validar un backup final;
3. desplegar la misma version o una version compatible de la aplicacion;
4. restaurar PostgreSQL y media en el servidor definitivo;
5. ejecutar migraciones;
6. verificar usuarios, cantidades, ultimos codigos y archivos;
7. habilitar el nuevo acceso;
8. conservar el servidor anterior sin modificaciones durante el periodo de
   validacion.

La base y la carpeta media forman una sola unidad logica. Restaurar una sin la
otra puede dejar evidencias faltantes o archivos sin registros asociados.
