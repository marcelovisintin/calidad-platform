# Plataforma Corporativa de Calidad

Sistema corporativo para gestion de anomalias, acciones, tareas y trazabilidad operativa.

La solucion esta construida como monolito modular con backend Django + Django REST Framework, base de datos PostgreSQL, frontend React + TypeScript y despliegue inicial local preparado para evolucionar a nube sin redisenos mayores.

## Estado actual del sistema

Hoy el sistema ya tiene implementado y validado:

- Autenticacion JWT con login, refresh, logout y usuario actual
- Roles, permisos y scopes por usuario
- Catalogos maestros para sitios, areas, tipos de anomalia, origenes, severidad, prioridad y tipos de accion
- Modulo completo de anomalias con workflow de 12 etapas
- Verificacion inicial con enfoque 6M
- Clasificacion, analisis de causa, propuestas, planes de accion, ejecucion, resultados, verificacion de eficacia, cierre y aprendizaje
- Planes de accion, acciones, evidencias y trazabilidad de cambios
- Bandeja interna, tareas pendientes y notificaciones por usuario
- Auditoria transversal de eventos
- Frontend web responsive y liviano, preparado como PWA
- Despliegue local con Docker Compose, frontend Nginx, backend Gunicorn y PostgreSQL
- Descarga protegida de adjuntos y evidencias por API autenticada

## Workflow de anomalias

El modulo principal contempla estas etapas:

1. Registro
2. Contencion
3. Verificacion inicial
4. Clasificacion
5. Analisis de causa
6. Propuestas
7. Plan de accion
8. Ejecucion y seguimiento
9. Resultados
10. Verificacion de eficacia
11. Cierre
12. Estandarizacion y aprendizaje

Estados principales soportados:

- registered
- in_evaluation
- in_analysis
- in_treatment
- pending_verification
- closed
- cancelled
- reopened

Toda transicion relevante registra usuario, fecha y hora, comentario, estado anterior, estado nuevo, etapa anterior y etapa nueva.

## Modulos implementados

### Backend

- `backend/apps/accounts`
  Autenticacion, usuario actual, roles, scopes y permisos.

- `backend/apps/catalog`
  Catalogos reutilizables de negocio.

- `backend/apps/anomalies`
  Entidad principal de anomalia, workflow, verificacion inicial, clasificacion, analisis de causa, propuestas, verificaciones de eficacia, aprendizaje, comentarios, adjuntos, participantes e historial.

- `backend/apps/actions`
  Planes de accion, acciones individuales, prioridades, evidencia esperada, evidencia cargada, comentario de cierre e historial de acciones.

- `backend/apps/notifications`
  Bandeja interna, tareas por usuario, marcacion de lectura y resolucion.

- `backend/apps/audit`
  Consulta de eventos de auditoria y resumen.

### Frontend

- `frontend/src/modules/accounts`
  Login y manejo de sesion.

- `frontend/src/modules/dashboard`
  Dashboard inicial con resumen de anomalias, acciones, pendientes e inbox.

- `frontend/src/modules/anomalies`
  Alta de anomalia, confirmacion de carga, listado propio y detalle con timeline.

- `frontend/src/modules/actions`
  Mis acciones y seguimiento rapido.

- `frontend/src/modules/notifications`
  Pendientes e inbox interno.

### Despliegue

- `deploy/docker`
  Dockerfiles, Compose local y variables de entorno para despliegue cloud-ready.

- `deploy/nginx`
  Configuracion de Nginx para frontend, proxy de API, static y bloqueo de media publica.

- `deploy/backups`
  Scripts de backup y restore.

- `docs/deployment`
  Documentacion operativa y estrategia de despliegue.

## Frontend operativo actual

El frontend inicial ya se encuentra conectado al backend y validado manualmente en estos flujos:

- Login
- Dashboard
- Nueva anomalia
- Confirmacion de carga
- Mis anomalias
- Detalle de anomalia
- Timeline / historial
- Mis acciones
- Tareas pendientes
- Bandeja interna
- Marcado de notificaciones como leidas

Caracteristicas implementadas en frontend:

- React + TypeScript
- Cliente HTTP unico con refresh automatico de token
- Rutas protegidas
- Manejo de estados de carga, error y expiracion de sesion
- Diseno responsive para Windows y Android
- Base PWA con `manifest.webmanifest` y service worker controlado

## Estructura del repositorio

```text
/
|- backend/
|  |- apps/
|  |- config/
|  |- requirements/
|  \- manage.py
|- frontend/
|  |- public/
|  |- src/
|  |- package.json
|  \- vite.config.ts
|- deploy/
|  |- backups/
|  |- docker/
|  |- nginx/
|  \- scripts/
|- docs/
|  |- architecture/
|  |- deployment/
|  |- workflows/
|  \- ...
|- storage/
|  |- media/
|  \- tmp/
|- .env.example
\- README.md
```

## Desarrollo local

### Backend

Ejemplo basico:

```powershell
cd backend
python manage.py migrate
python manage.py runserver
```

API root de desarrollo:

```text
http://127.0.0.1:8000/api/v1/
```

### Frontend

Ejemplo basico:

```powershell
cd frontend
npm install
npm run dev
```

Frontend de desarrollo:

```text
http://localhost:5173/
```

## Despliegue local cloud-ready

Se definio una arquitectura inicial para servidor local de planta con estas piezas separadas:

- Frontend Nginx
- Backend Django + Gunicorn
- Base de datos PostgreSQL
- Archivos adjuntos persistentes
- Logs persistentes
- Backups separados
- Configuracion por variables de entorno y secretos fuera del repo

Documentacion principal de despliegue:

- `docs/deployment/local-cloud-ready.md`
- `deploy/docker/docker-compose.local.yml`
- `deploy/docker/.env.server.example`
- archivo real: `deploy/docker/.env.server.local` (excluido del repo por `.gitignore`)

Objetivo de esta estrategia:

- no hardcodear IPs
- mantener frontend y backend desacoplados por configuracion
- dejar base de datos y archivos fuera del codigo
- facilitar futura migracion a nube como cambio de infraestructura y configuracion

## Validacion realizada

### Backend

- `python manage.py check`
- tests de `anomalies`, `actions`, `notifications` y `audit`
- validacion funcional real del workflow completo de anomalias

### Frontend

- `npm install`
- `npm run check`
- `npm run build`
- validacion manual de flujos principales contra backend real

### Despliegue local

- Stack Docker levantado con:
  - `db` (PostgreSQL 17, healthcheck pg_isready)
  - `backend` (Django + Gunicorn, healthcheck HTTP)
  - `frontend` (React + Nginx, espera backend healthy)
- acceso validado por:
  - `http://localhost:8088/`
  - `http://localhost:8088/api/v1/`
  - `https://localhost:8443/` (TLS autofirmado)

## Documentacion principal

- `docs/adr/0001-platform-architecture.md`
- `docs/architecture/system-overview.md`
- `docs/architecture/backend-domains.md`
- `docs/data-model/erd-initial.md`
- `docs/workflows/anomalies-workflow.md`
- `docs/deployment/local-cloud-ready.md`

## Proximos pasos sugeridos

- Conectar catalogos del frontend contra API real en vez de bootstrap estatico
- Preparar carga de datos base (fixtures) para el stack Docker productivo local
- Definir estrategia de restore y prueba de backups
- Publicar acceso interno por nombre de host de red
- Incorporar monitoreo y endurecimiento de seguridad para entorno productivo
- Agregar usuario no-root en `backend.Dockerfile` con entrypoint que fije ownership de volumenes montados

## Arranque automatico en Windows (recomendado)

Para dejar el sistema operativo en cualquier red Wi-Fi con un solo comando:

```powershell
cd D:\SCHNEIDER\2026\CALIDAD
powershell -ExecutionPolicy Bypass -File deploy/scripts/start_local_stack.ps1
```

Que hace este script:

- carga `deploy/docker/.env.server` (o `.env.server.local` si existe)
- crea carpetas requeridas en `D:/calidad-platform`
- levanta/reconstruye stack Docker
- intenta crear reglas de firewall para acceso LAN (si se ejecuta como administrador)
- muestra las URLs listas para usar en PC y movil

URL recomendada en dispositivos de red interna:

- `http://<IP_LAN_DEL_SERVIDOR>:8088/login`
- `https://<IP_LAN_DEL_SERVIDOR>:8443/login` (TLS local, mostrara advertencia por certificado autofirmado)


