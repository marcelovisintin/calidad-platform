# Árbol de navegación del Sistema de Gestión de Calidad

## Convenciones

- `[Todos]`: visible normalmente para cualquier usuario activo.
- `[Admin]`: visible normalmente para Administrador y Desarrollador.
- `[Asignado]`: operación limitada al usuario responsable o relacionado.
- `[Solo lectura]`: pantalla de consulta.
- `[Backend]`: modelo/API implementado sin pantalla React comprobada.
- `→`: la acción navega o habilita el nodo indicado.

## Árbol principal

```text
Sistema de Gestión de Calidad
├── Acceso público
│   └── Iniciar sesión
│       ├── Credenciales válidas y cambio pendiente
│       │   → Cambiar contraseña
│       ├── Credenciales válidas: Administrador / Desarrollador
│       │   → Inicio / Panel de gestión
│       └── Credenciales válidas: Usuario activo / Mando medio
│           → Nueva anomalía
│
├── Barra superior y menú adaptable [Todos]
│   ├── Volver
│   ├── Usuario y foto
│   ├── Cerrar sesión
│   └── Menú móvil
│
├── Inicio / Panel de gestión [Admin]
│   ├── Vista compacta
│   └── Menú contextual
│       ├── Centro de ayuda → Ayuda
│       ├── Resumen rápido
│       │   ├── Anomalías
│       │   │   └── Ver detalle por usuario [Admin]
│       │   ├── Acciones
│       │   │   └── Ver detalle por usuario [Admin]
│       │   ├── Tratamientos
│       │   │   └── Ver detalle por usuario [Admin]
│       │   └── Verificaciones de eficacia
│       │       └── Ver detalle por usuario [Admin]
│       ├── Secciones principales
│       │   ├── 1. Nueva anomalía
│       │   ├── 2. Seguimiento de anomalías
│       │   ├── 3. Observaciones
│       │   ├── 4. Tratamientos
│       │   ├── 5. Acciones
│       │   ├── 6. Validaciones
│       │   ├── 7. Lecciones aprendidas
│       │   ├── 8. Seguimiento de tratamientos
│       │   ├── 9. Bandeja
│       │   ├── 10. Resumen rápido
│       │   ├── 11. Indicadores
│       │   ├── 12. Órdenes afectadas
│       │   └── 13. Ayuda
│       ├── Seguimiento operativo
│       │   ├── Últimas anomalías → Detalle de anomalía
│       │   ├── Tratamientos en gestión → Tratamientos
│       │   └── Acciones pendientes → Acciones
│       ├── Indicadores [Admin]
│       │   └── Catálogo de nueve indicadores → Dashboard de indicador
│       └── Configuración admin [Admin]
│           ├── Usuarios
│           ├── Importación de usuarios
│           ├── Roles y alcances → enlace Django obsoleto/no verificado
│           ├── Alcances de usuario
│           ├── Áreas
│           ├── Procesos
│           ├── Líneas
│           ├── Tipos de desvío
│           ├── Asignado a
│           ├── Criterios de Revisión de hallazgos
│           ├── Orden operativo
│           ├── Tipos de acción
│           ├── Tipos de órdenes afectadas
│           └── Panel admin Django
│
├── Nueva anomalía [Todos]
│   ├── Reserva de código
│   │   └── Reintentar reserva
│   ├── Paso 1: Datos de inicio
│   │   ├── Elaborado por: → selector Área/Proceso
│   │   ├── Fecha y hora
│   │   ├── Asignado a → selector Área/Proceso imputado
│   │   └── Tipo de desvío
│   ├── Paso 2: Contexto
│   │   ├── Título
│   │   ├── Órdenes afectadas
│   │   │   ├── Agregar orden
│   │   │   └── Quitar orden
│   │   ├── Observación
│   │   └── Evidencia objetiva múltiple
│   └── Guardar anomalía
│       → Confirmación de anomalía creada
│       ├── Ver detalle → Detalle de anomalía
│       └── Registrar otra → Nueva anomalía
│
├── Seguimiento de anomalías [Todos, datos por alcance]
│   ├── Buscar
│   ├── Listado paginado
│   │   └── Seleccionar anomalía → Detalle de anomalía
│   ├── Revisión de hallazgos [Admin]
│   │   ├── Criterio inválido
│   │   │   ├── Observación / Motivo
│   │   │   └── Confirmar → Cierre de anomalía
│   │   ├── Observación / mejora / otro criterio con responsable
│   │   │   ├── Responsable
│   │   │   └── Confirmar → Observaciones o gestión asignada
│   │   ├── No conformidad
│   │   │   ├── Responsable único del tratamiento
│   │   │   ├── Anomalías relacionadas
│   │   │   │   ├── Sugeridas por repitencia
│   │   │   │   ├── Todas las elegibles
│   │   │   │   └── Buscar candidatas
│   │   │   └── Confirmar → Tratamiento conformado
│   │   └── Habilitar cambio de clasificación
│   └── Estudio de repitencia [Admin]
│       ├── Fecha Desde
│       ├── Resumen por tipo
│       ├── Resumen por tipo + proceso + hallazgo
│       └── Detalle de anomalías
│
├── Detalle de anomalía [Todos, datos por alcance] [Solo lectura]
│   ├── Datos principales
│   ├── Planes y acciones
│   │   ├── Planes de acción generales [Backend origin]
│   │   └── Acciones de tratamiento
│   │       └── Ir al tratamiento → Tratamientos
│   ├── Participación y verificaciones
│   ├── Evidencias cargadas
│   │   └── Abrir/descargar evidencia
│   ├── Lecciones aprendidas
│   └── Historial
│
├── Observaciones [Todos, gestión por responsable]
│   ├── Buscar
│   ├── Incluir observaciones cerradas
│   ├── Seleccionar observación
│   ├── Carga de Observación
│   │   ├── Clasificar como Observación TRT
│   │   │   └── Confirmar → Candidata para Tratamientos
│   │   ├── Responsable fijado
│   │   ├── Fecha límite de ejecución
│   │   ├── Observación
│   │   └── Cargar observación → Acciones tomadas
│   ├── Acciones tomadas
│   │   ├── Fecha de realizado
│   │   ├── Fecha de verificación de eficacia
│   │   ├── Detalle de la acción
│   │   ├── Evidencias objetivas
│   │   └── Confirmar → Verificación de eficacia
│   └── Verificación de eficacia [Asignado]
│       ├── Fecha
│       ├── Eficaz: Sí
│       │   → Cierre definitivo directo
│       └── Eficaz: No
│           → Nueva carga de acciones; permanece pendiente
│
├── Tratamientos [Todos, datos por relación]
│   ├── Buscar tratamiento
│   ├── Seleccionar tratamiento
│   ├── Vista 1 - Convocatoria [Responsable/Admin]
│   │   ├── Fecha de tratamiento
│   │   │   ├── Fecha y hora programada
│   │   │   ├── Lugar
│   │   │   └── Guardar agenda
│   │   │       ├── Confirmación de usuarios convocados
│   │   │       └── Bloqueo de agenda/participantes + notificaciones
│   │   ├── Usuarios convocados
│   │   │   ├── Filtro Área
│   │   │   ├── Usuario
│   │   │   ├── Participación: Convocado
│   │   │   └── Nota
│   │   ├── Anomalías incluidas por Calidad [Solo lectura]
│   │   │   └── Corregir conformación [Admin, antes de iniciar]
│   │   └── Evidencias de anomalías vinculadas
│   └── Vista 2 - Análisis [Responsable/Admin]
│       ├── Método y observaciones
│       ├── Evidencias del tratamiento
│       ├── Causas raíz encontradas
│       ├── Acciones surgidas del tratamiento
│       │   ├── Crear acción
│       │   ├── Detalle de acciones
│       │   └── Editar/ejecutar → Acciones
│       └── Evaluación de eficacia
│           ├── Fecha
│           ├── Responsable
│           └── Guardar análisis → Validaciones cuando no hay bloqueos
│
├── Acciones [Asignado]
│   ├── Filtros
│   │   ├── Buscar
│   │   ├── Anomalía
│   │   ├── Tratamiento
│   │   ├── Estado
│   │   ├── Fecha terminada
│   │   └── Usuario que la realizó
│   ├── Pendientes / En curso / Vencidas
│   │   └── Seleccionar acción
│   │       ├── Ver causas y evidencias
│   │       ├── Cambiar estado + nota obligatoria
│   │       └── Cargar evidencia
│   └── Completadas
│       └── Historial desplegable paginado
│
├── Validaciones [Asignado]
│   ├── Disponibles y pendientes
│   ├── Seleccionar tratamiento
│   ├── Ver bloqueadores
│   └── Confirmar eficacia
│       ├── Eficaz → Tratamiento completado + anomalías cerradas
│       └── No eficaz → Tratamiento en curso
│
├── Lecciones aprendidas [Todos, tratamientos visibles]
│   ├── Buscar tratamiento
│   ├── Seleccionar tratamiento eficaz
│   ├── ¿Hubo aprendizaje?
│   ├── ¿Qué se aprendió? / ¿Por qué no se aprendió?
│   ├── ¿Modifica procedimiento?
│   ├── Observaciones de modificación
│   ├── Evidencias
│   └── Guardar [Responsable/Admin]
│
├── Seguimiento de tratamientos [Todos, datos por relación] [Solo lectura]
│   ├── Filtros: código, usuario, proceso
│   ├── Listado histórico
│   └── Detalle
│       ├── Datos generales
│       ├── Usuarios/convocados
│       ├── Anomalías
│       ├── Causas raíz
│       ├── Acciones/tareas
│       ├── Evaluación de eficacia
│       ├── Evidencias
│       └── Historial y auditoría
│
├── Bandeja [Todos]
│   ├── Resumen: Pendientes, En curso, Vencidas, Avisos no leídos
│   ├── Pendientes
│   │   ├── Abrir contexto → módulo relacionado
│   │   └── Confirmar visto → completar participación manual
│   ├── Avisos
│   │   ├── Abrir contexto → módulo relacionado
│   │   └── Marcar leída
│   └── Historial
│       └── Pendientes completados/descartados
│
├── Resumen rápido [Admin]
│   └── Abre el resumen histórico del Panel de gestión
│
├── Indicadores [Admin]
│   ├── Catálogo
│   │   ├── Anomalías generadas y tratadas
│   │   ├── Tratamientos
│   │   ├── Anomalías por proceso
│   │   ├── Clasificación de hallazgos
│   │   ├── Repetitividad y Pareto
│   │   ├── Acciones
│   │   ├── Eficacia
│   │   ├── Órdenes afectadas
│   │   └── Lecciones aprendidas
│   └── Dashboard de indicador
│       ├── Filtros de período y proceso
│       ├── Agrupación de Pareto, cuando corresponde
│       ├── Métricas
│       ├── Evolución mensual
│       ├── Distribución/Pareto
│       ├── Notas de fórmula
│       ├── Tabla paginada
│       ├── Exportar CSV
│       └── Enviar informe PDF
│           ├── Buscar destinatario habilitado
│           ├── Seleccionar uno o más
│           └── Generar y encolar correo
│
├── Órdenes afectadas [Admin]
│   ├── Filtros
│   │   ├── Buscar
│   │   ├── Tipo
│   │   ├── Número
│   │   ├── Anomalía
│   │   ├── Proceso
│   │   ├── Cantidad
│   │   ├── Estado
│   │   └── Fechas
│   ├── Totalizadores
│   ├── Desglose por tipo
│   ├── Tabla paginada
│   │   └── Abrir anomalía → Detalle de anomalía
│   └── Exportar CSV
│
├── Centro de Ayuda [Todos]
│   ├── Búsqueda y filtros por categoría
│   ├── Guías según el nivel de acceso
│   ├── Progreso personal
│   ├── Ayuda contextual y recorridos guiados
│   ├── Guía de información documentada
│   │   ├── Finalidad, soportes y responsabilidades
│   │   ├── Documentos y registros como evidencia
│   │   ├── Evidencia de no conformidades
│   │   └── Criterios recomendados para el sistema
│   └── Acerca de
│       ├── Información del sistema y tecnologías
│       ├── Historial controlado de cambios
│       └── Ayuda de trazabilidad ISO 9001
│
└── Configuración y maestros [Admin]
    ├── Usuarios
    │   ├── Buscar / Incluir inactivos
    │   ├── Nuevo usuario
    │   ├── Editar usuario
    │   ├── Generar/asignar contraseña provisoria
    │   ├── Activar/desactivar correo
    │   ├── Activar/desactivar usuario
    │   ├── Eliminar
    │   └── Importación masiva
    │       ├── Elegir CSV/XLSX y modo
    │       ├── Analizar
    │       ├── Confirmar
    │       └── Descargar reporte confidencial
    ├── Alcances de usuario
    │   ├── Buscar usuario
    │   ├── Nivel de acceso
    │   ├── Checklist de permisos específicos
    │   └── Guardar
    ├── Catálogos
    │   ├── Seleccionar catálogo
    │   ├── Buscar / incluir inactivos
    │   ├── Nuevo registro
    │   ├── Editar
    │   ├── Activar/desactivar
    │   └── Eliminar
    └── Panel admin Django
```

## Funciones implementadas sin navegación de usuario comprobada

```text
Backend / API
├── Flujo genérico de anomalía
│   ├── Transición manual de etapa/estado
│   ├── Anulación
│   ├── Reapertura
│   ├── Comentarios
│   ├── Participantes
│   ├── Verificación inicial 6M detallada
│   ├── Clasificación genérica
│   ├── Análisis de causa genérico
│   ├── Propuestas
│   ├── Verificaciones de eficacia genéricas
│   └── Estandarización y aprendizaje genéricos
├── Planes y acciones generales
│   ├── Crear/editar/transitar plan
│   ├── Crear/editar/transitar acción
│   └── Cargar evidencia
└── Auditoría transversal
    ├── Listar eventos
    ├── Filtrar
    ├── Ver detalle
    └── Resumen
```

Estas ramas no deben incorporarse a una capacitación como operación disponible hasta que exista una pantalla validada o se decida operar mediante el Panel admin Django.
