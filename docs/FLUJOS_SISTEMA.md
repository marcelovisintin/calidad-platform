# Flujos del Sistema de Gestión de Calidad

## Convenciones

- Los diagramas representan el comportamiento comprobado en código.
- Un nodo con “solo backend” no tiene control de usuario comprobado en la interfaz React.
- Los nombres de estado se muestran con su etiqueta funcional real.
- La clasificación concreta depende del maestro **Criterios de Revisión de hallazgos**. Los diagramas muestran los caminos que el código reconoce específicamente.

## 1. Flujo completo de una anomalía

```mermaid
flowchart TD
    A[Usuario activo abre Nueva anomalía] --> B[Reserva código AAAA####]
    B --> C[Completa proceso, fecha, imputación, tipo, título y observación]
    C --> D{¿Informó órdenes?}
    D -- Sí --> E[Validar tipo, número, cantidad > 0 y no duplicada]
    D -- No --> F[Guardar]
    E --> F
    F --> G[Estado: Registrada<br/>Etapa: Registro]
    G --> H[Historial + auditoría + aviso al registrador]
    H --> I[Calidad realiza Revisión de hallazgos]
    I --> J{Criterio aplicado}

    J -- Cierra como inválida --> K[Exigir Observación / Motivo]
    K --> L[Estado: Cerrada<br/>Etapa: Cierre]
    L --> M[Notificar al registrador]

    J -- Observación --> N[Asignar responsable de gestión]
    N --> O[Estado: En evaluación<br/>Etapa: Revisión de hallazgos<br/>Código con -OBS]
    O --> P{Camino elegido en Observaciones}
    P -- Directo --> Q[Acciones tomadas]
    Q --> R[Estado: Pendiente de verificación<br/>Etapa: Verificación de eficacia]
    R --> S{Resultado}
    S -- Eficaz --> T[Estado: Cerrada<br/>Etapa: Cierre]
    S -- No eficaz --> U[Permanece Pendiente de verificación]
    U --> Q
    T --> M

    P -- Observación TRT --> V[Camino TREATMENT_PENDING]
    V --> W[Calidad la asocia a tratamiento]
    W --> X[Camino TREATMENT]

    J -- No conformidad --> Y[Asignar responsable y seleccionar relacionadas]
    Y --> Z[Crear o consolidar un tratamiento]
    Z --> AA[Estado anomalía: En análisis<br/>Etapa: Tratamiento creado]
    X --> AA
    AA --> AB[Convocatoria + análisis + causas raíz]
    AB --> AC[Estado: En análisis<br/>Etapa: Análisis de causa]
    AC --> AD[Crear y ejecutar acciones]
    AD --> AE[Estado: En tratamiento<br/>Etapas de plan, ejecución y resultados]
    AE --> AF[Asignar fecha y responsable de eficacia]
    AF --> AG{Verificación del tratamiento}
    AG -- Eficaz --> AH[Tratamiento: Completado]
    AH --> AI[Anomalías: Cerradas / Cierre]
    AI --> AJ[Notificar involucrados y registradores]
    AJ --> AK[Lecciones aprendidas]
    AG -- No eficaz --> AL[Tratamiento: En tratamiento]
    AL --> AM[Revisar acciones]
    AM --> AD

    R -. API genérica, solo Admin .-> AR[Reapertura manual a etapa de análisis/tratamiento]
    AI -. API genérica, solo Admin .-> AR
    AR --> AS[Estado: Reabierta]
```

### Nota sobre la secuencia funcional esperada

La secuencia de referencia `Registrada → Clasificada → Asignada → En tratamiento → Cerrada por responsable → Verificación → Cerrada definitiva` no existe como una sucesión de estados separados. “Clasificada”, “Asignada” y “Cerrada por responsable” son eventos o responsabilidades, no estados del modelo.

## 2. Flujo de una Observación

```mermaid
flowchart TD
    A[Calidad clasifica como Observación] --> B[Exige responsable de nivel de gestión]
    B --> C[Agrega sufijo -OBS]
    C --> D[Responsable abre Observaciones]
    D --> E[Completa responsable fijado, fecha límite y observación]
    E --> F{¿Marca Observación TRT?}

    F -- Sí --> G{¿Ya hay acciones confirmadas?}
    G -- Sí --> H[Rechazar: la casilla TRT está bloqueada]
    G -- No --> I[Guardar camino TREATMENT_PENDING]
    I --> J[Estado: En evaluación<br/>Etapa: Revisión de hallazgos]
    J --> K[Queda elegible para tratamiento]
    K --> L[Calidad la asocia a una NC/tratamiento]
    L --> M[Camino TREATMENT]
    M --> N[Continúa por flujo de tratamiento]

    F -- No --> O[Guardar camino OBSERVATION]
    O --> P[Habilitar Acciones tomadas]
    P --> Q[Fecha realizada + acción + fecha de eficacia]
    Q --> R[Cargar evidencias opcionales]
    R --> S[Confirmar acciones]
    S --> T[Pendiente de verificación / Verificación de eficacia]
    T --> U[Notificar al responsable]
    U --> V[Responsable indica fecha y resultado]
    V --> W{¿Eficaz?}
    W -- Sí --> X[Cerrar anomalía directamente]
    X --> Y[Notificar al registrador]
    W -- No --> Z[Mantener Pendiente de verificación]
    Z --> AA[Notificar al responsable]
    AA --> P
```

### Brechas representadas

- No hay cierre intermedio del responsable seguido de cierre definitivo de Calidad.
- “No eficaz” no asigna el estado Reabierta.
- El verificador de la Observación es el mismo responsable de la gestión.

## 3. Flujo de una No conformidad y su tratamiento

```mermaid
flowchart TD
    A[Administrador/Desarrollador clasifica NC] --> B[Selecciona responsable único]
    B --> C{¿Relaciona otras anomalías?}
    C -- Sí --> D[Elegir NC u OBS-TRT elegibles sin tratamiento]
    C -- No --> E[Confirmar clasificación]
    D --> E
    E --> F[Crear o consolidar un único TRT-AAAA-####]
    F --> G[Composición bloqueada para el responsable]
    G --> H[Vista 1 - Convocatoria]
    H --> I[Agregar convocados activos y notas]
    I --> J[Ingresar fecha/hora y lugar]
    J --> K{Confirmar Guardar agenda}
    K -- Cancelar --> H
    K -- Confirmar --> L[Estado tratamiento: Programado]
    L --> M[Bloquear agenda y convocados]
    M --> N[Notificar convocados]
    N --> O[Vista 2 - Análisis]
    O --> P[Elegir método y escribir observaciones]
    P --> Q[Estado tratamiento: En tratamiento]
    Q --> R[Cargar una o más causas raíz]
    R --> S[Crear acciones]
    S --> T[Responsable activo + fecha + descripción + causas]
    T --> U[Notificar responsable de cada acción]
    U --> V[Responsables ejecutan desde Acciones]
    V --> W[Cambio de estado con nota de evidencia]
    W --> X{¿Todas están Completadas?}
    X -- No --> V
    X -- Sí --> Y[Definir fecha y responsable de eficacia]
    Y --> Z{Validaciones: ¿cumple bloqueadores?}
    Z -- No --> ZA[Mostrar faltantes]
    ZA --> O
    Z -- Sí --> ZB[Responsable designado valida]
    ZB --> ZC{Resultado}
    ZC -- Eficaz --> ZD[Tratamiento Completado]
    ZD --> ZE[Cerrar todas las anomalías asociadas]
    ZE --> ZF[Bloquear edición]
    ZF --> ZG[Notificar involucrados y registradores]
    ZG --> ZH[Registrar lecciones aprendidas]
    ZC -- No eficaz --> ZI[Tratamiento En tratamiento]
    ZI --> ZJ[Notificar involucrados]
    ZJ --> V
```

### Bloqueadores reales de Validaciones

```mermaid
flowchart LR
    A[Tratamiento] --> B{Fecha agendada existe y ya pasó}
    B -- No --> X[No disponible]
    B -- Sí --> C{Hay causa raíz y ninguna está vacía}
    C -- No --> X
    C -- Sí --> D{Fecha y responsable de eficacia informados}
    D -- No --> X
    D -- Sí --> E{Todas las acciones están Completadas}
    E -- No --> X
    E -- Sí --> F[Disponible para el responsable designado]
```

No son bloqueadores explícitos: convocatoria confirmada, lugar, método, observaciones, evidencia, existencia de al menos una acción y duración de reunión.

## 4. Verificación de eficacia y reapertura

```mermaid
flowchart TD
    A{Origen de la verificación} --> B[Observación directa]
    A --> C[Tratamiento]
    A --> D[Flujo genérico solo backend]

    B --> E[Responsable de Observación]
    E --> F{Resultado}
    F -- Eficaz --> G[Anomalía Cerrada]
    F -- No eficaz --> H[Anomalía Pendiente de verificación]
    H --> I[Nueva acción tomada]
    I --> E

    C --> J[Responsable de eficacia del tratamiento]
    J --> K{Resultado}
    K -- Eficaz --> L[Tratamiento Completado]
    L --> M[Anomalías Cerradas]
    K -- No eficaz --> N[Tratamiento En tratamiento]
    N --> O[Revisar acciones]
    O --> J

    D --> P{Estado actual Cerrada o Pendiente de verificación}
    P -- No --> Q[Rechazar reapertura]
    P -- Sí --> R{Usuario global y etapa destino reabrible}
    R -- No --> Q
    R -- Sí --> S[Exigir comentario]
    S --> T[Estado Reabierta + contador de reaperturas]
    T --> U[Etapa de análisis/tratamiento elegida]
```

### Interpretación

El estado Reabierta existe y el indicador de Eficacia contabiliza `reopened_count`, pero los dos flujos visibles de no eficacia no lo utilizan. La reapertura es una transición administrativa genérica sin botón comprobado.

## 5. Responsabilidades y permisos por nivel

```mermaid
flowchart TD
    A[Usuario autenticado y activo] --> B{Nivel de acceso}

    B --> U[Usuario activo]
    U --> U1[Registrar anomalía]
    U --> U2[Consultar anomalías relacionadas]
    U --> U3[Ejecutar acción si es responsable]
    U --> U4[Verificar eficacia si es responsable designado]
    U --> U5[Consultar tratamiento si está relacionado]

    B --> M[Mando medio activo]
    M --> M1[Todo lo asignable a Usuario activo]
    M --> M2[Gestionar Observación si es responsable]
    M --> M3[Gestionar Tratamiento si es responsable]
    M --> M4[Convocar, analizar, cargar causas y crear acciones]
    M --> M5[Delegar acciones a usuarios activos]

    B --> AD[Administrador]
    AD --> AD1[Acceso global a datos]
    AD --> AD2[Revisión de hallazgos]
    AD --> AD3[Conformar/corregir tratamientos]
    AD --> AD4[Panel, indicadores y órdenes afectadas]
    AD --> AD5[Usuarios, alcances y catálogos]
    AD --> AD6[No puede validar eficacia ajena]

    B --> DEV[Desarrollador]
    DEV --> DEV1[Capacidades de Administrador]
    DEV --> DEV2[Superusuario y panel técnico]
    DEV --> DEV3[Puede asignar nivel Desarrollador]

    A --> R{¿Existe asignación exacta?}
    R -- Responsable de acción --> RA[Cambiar estado y cargar evidencia]
    R -- Responsable de eficacia --> RV[Confirmar eficacia]
    R -- Solo convocado --> RC[Consultar y confirmar participación; no editar análisis]
    R -- Sin relación y no global --> RX[No ver el caso]
```

## 6. Notificaciones y correo

```mermaid
flowchart TD
    A[Evento de negocio] --> B[Crear notificación interna para usuarios activos]
    B --> C[Bandeja: aviso o pendiente]
    A --> D{¿El evento tiene correo habilitado?}
    D -- No --> E[Sin destinatario Email]
    D -- Sí --> F{¿Envío global activo?}
    F -- No --> E
    F -- Sí --> G{¿Usuario activo, email válido y casilla Notificación por correo?}
    G -- No --> E
    G -- Sí --> H[Crear destinatario Email pendiente]
    H --> I[Despachador periódico]
    I --> J{Resultado}
    J -- Entregado --> K[Guardar fecha/estado de entrega]
    J -- Fallido --> L[Guardar error e intentos para reintento]
```

La Bandeja no depende de la casilla de correo. La casilla solo controla el canal Email.
