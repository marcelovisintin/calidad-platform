# ADR 0001 - Arquitectura Base de la Plataforma

- Estado: Accepted
- Fecha: 2026-03-21

## Contexto

Se debe construir una plataforma corporativa propia, iniciando por el modulo de gestion de anomalias, pero preparada para evolucionar hacia otros modulos de calidad y operacion. Las decisiones ya tomadas son:

- Backend en Python con Django
- API con Django REST Framework
- Base de datos PostgreSQL
- Frontend React + TypeScript
- Frontend liviano, responsive y preferentemente PWA
- Despliegue inicial local en servidor de fabrica
- Preparacion para migracion futura a nube sin cambios mayores
- Centralizacion de la logica de negocio en backend
- La PC de Calidad no actua como servidor principal

El sistema debe soportar operacion multiusuario, workflow, trazabilidad, adjuntos, auditoria y futuras extensiones funcionales.

## Decision

Se adopta una arquitectura de **monolito modular** con las siguientes decisiones:

1. **Backend unico en Django + DRF**
   - Un solo servicio desplegable.
   - API REST versionada bajo `/api/v1/`.
   - Organizacion interna por apps de dominio.

2. **Frontend desacoplado en React + TypeScript**
   - Aplicacion SPA/PWA que consume la API.
   - Sin logica de negocio autoritativa.
   - Enfocada en UX, navegacion, formularios y visualizacion.

3. **PostgreSQL como fuente central de verdad**
   - Persistencia transaccional unica.
   - Integridad referencial y constraints en base.

4. **Storage de adjuntos desacoplado**
   - Inicialmente filesystem local en servidor.
   - Acceso encapsulado mediante adapter para permitir migracion posterior a storage cloud.

5. **Despliegue local cloud-ready**
   - Servidor central local en planta/fabrica.
   - Reverse proxy delante de backend y frontend.
   - Configuracion por variables de entorno y separacion entre codigo, datos y adjuntos.

6. **Backend centraliza workflow, permisos y trazabilidad**
   - Transiciones de estado, reglas de cierre, auditoria y validaciones residen en backend.
   - El frontend solo solicita acciones y presenta resultados.

## Justificacion

### Por que monolito modular

Conviene porque el primer modulo necesita fuerte consistencia entre:

- anomalias
- acciones correctivas
- notificaciones
- auditoria
- catalogos maestros
- seguridad y permisos

Separar tempranamente en microservicios agregaria complejidad operacional, necesidad de integracion distribuida, mas puntos de fallo y mas esfuerzo de despliegue sin aportar valor proporcional. Un monolito modular permite:

- transacciones consistentes
- menor costo de operacion local
- mayor velocidad de desarrollo
- limites de dominio claros
- posibilidad de extraccion futura si un modulo madura lo suficiente

### Por que backend centralizado

En un sistema corporativo multiusuario, reglas de negocio y trazabilidad deben ser uniformes. Si parte del workflow vive en frontend:

- aparecen inconsistencias entre clientes
- se debilita la auditoria
- aumenta el riesgo de cierres o transiciones invalidas
- se duplica logica

### Por que PWA y no apps nativas

La PWA minimiza mantenimiento y facilita despliegue en terminals de planta:

- una sola base de codigo cliente
- instalacion ligera
- actualizaciones centralizadas
- experiencia responsive
- menor costo de soporte

Se descarta offline transaccional en fase inicial para no comprometer consistencia y trazabilidad.

### Por que local pero listo para nube

El contexto inicial justifica operacion local, pero la arquitectura no debe depender de:

- rutas fijas del servidor
- sesiones locales acopladas al host
- almacenamiento embebido en el frontend
- integraciones imposibles de externalizar

El sistema debe poder migrar a infraestructura cloud con cambios de configuracion y despliegue, no con rediseño funcional.

## Consecuencias

### Positivas

- Base simple de operar en entorno de fabrica
- Alta consistencia transaccional
- Trazabilidad centralizada
- Crecimiento ordenado por apps de dominio
- Mejor punto de partida para controles de seguridad y auditoria

### Negativas o costos asumidos

- El monolito exige disciplina para no mezclar dominios
- Algunas dependencias entre modulos seran internas al proceso
- El backend requiere una capa de servicios clara para no caer en logica dispersa entre modelos, serializers y vistas

## Reglas de diseño derivadas

- Ninguna transicion de workflow se actualiza directamente por `save()` desde la API.
- Toda operacion relevante debe disparar auditoria.
- Las apps se comunican por servicios/selectors, no por acceso arbitrario entre capas.
- No se permite hard delete en entidades transaccionales.
- Los catalogos se inactivan; no se eliminan si tienen uso historico.
