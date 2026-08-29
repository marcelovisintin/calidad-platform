# Guía de funcionamiento del Sistema de Gestión de Calidad

## 1. Alcance y criterio de esta guía

Esta guía describe el comportamiento comprobado en el código del Sistema de Gestión de Calidad y Anomalías. Su propósito es capacitar a quienes registran anomalías, responsables de procesos, responsables de tratamientos y acciones, personal de Calidad y administradores.

El sistema conserva el registro de una anomalía desde su alta hasta su resolución, vincula observaciones, no conformidades, tratamientos, acciones, verificaciones de eficacia, evidencias y lecciones aprendidas, y mantiene trazabilidad mediante historiales y eventos de auditoría.

En esta guía se usan tres criterios:

- **Disponible en la interfaz:** existe una pantalla o botón utilizable en la aplicación web.
- **Disponible solo en backend:** el modelo y la API existen, pero no se encontró una pantalla de usuario que permita operar la función.
- **Pendiente / no verificado en código:** la política esperada no está implementada o no pudo comprobarse como parte del flujo visible.

La alineación con PDCA e ISO 9001 es funcional, no una certificación: el sistema registra problema, análisis, acciones, verificación y aprendizaje, pero algunas transiciones esperadas no coinciden exactamente con la política de referencia; se detallan al final.

## 2. Perfiles de usuario reales

El sistema no utiliza un “rol de usuario” general para autorizar la operación diaria. Utiliza el campo **Nivel de acceso**:

| Nivel | Alcance comprobado |
| --- | --- |
| Usuario activo | Puede registrar anomalías y consultar aquellas con las que tiene relación. Puede realizar las acciones de tratamiento y verificaciones que le fueron asignadas. |
| Mando medio activo | Tiene las capacidades de Usuario activo y puede gestionar el proceso que le fue asignado como responsable: observaciones, tratamiento, convocatoria, análisis, causas y acciones. |
| Administrador | Acceso global funcional, revisión de hallazgos, conformación de tratamientos, panel general, indicadores, órdenes afectadas, usuarios y maestros. |
| Desarrollador | Acceso global equivalente al Administrador y condición técnica de superusuario. Solo otro superusuario puede asignar este nivel. |

Reglas importantes:

- El **Sector principal** del usuario es un dato descriptivo. No limita por sí solo las anomalías visibles ni reemplaza una asignación.
- La relación con un caso determina la visibilidad de usuarios no globales: registrador, responsable, participante, responsable de una acción, convocado o verificador.
- Los permisos de **Alcances de usuario** siguen existiendo como permisos específicos. Sin embargo, los flujos principales también aplican reglas directas por nivel y por asignación. Por eso los dos mecanismos no son equivalentes; esta mezcla se documenta como inconsistencia.
- “Facilitador”, “Responsable” y “Convocado” existen como roles internos de participantes de tratamiento. En la interfaz actual solo se agregan participantes como **Convocado**; el responsable se agrega automáticamente.

## 3. Ingreso, contraseña y sesión

### 3.1 Iniciar sesión

1. Abrir la dirección del sistema proporcionada por la empresa.
2. Ingresar usuario o correo y la contraseña.
3. Seleccionar **Ingresar**.

La cuenta debe estar activa. Si las credenciales no coinciden, el sistema informa “Credenciales inválidas”. La sesión utilizada por la aplicación pertenece al navegador actual; abrir otro usuario en la misma sesión del navegador reemplaza la sesión anterior. Para probar dos usuarios simultáneamente se deben usar perfiles de navegador distintos o una ventana de incógnito.

### 3.2 Primer ingreso o contraseña provisoria

Cuando un administrador crea un usuario o asigna una contraseña provisoria, el usuario queda obligado a cambiarla:

1. Ingresar con la contraseña provisoria, de al menos 8 caracteres; puede ser sencilla o numérica.
2. El sistema redirige a **Cambiar contraseña** y restringe el resto de las API hasta completar el cambio.
3. Informar contraseña actual, nueva contraseña y confirmación.

La contraseña definitiva debe:

- tener al menos 8 caracteres;
- incluir mayúscula, minúscula, número y carácter especial;
- ser distinta de la provisoria;
- no contener el usuario ni la parte local del correo;
- no ser una contraseña común según las validaciones configuradas.

### 3.3 Cerrar sesión

El botón **Cerrar sesión** está disponible en la barra superior, en la barra lateral y en el menú móvil. Debe usarse en equipos compartidos.

## 4. Orientación y navegación

### 4.1 Inicio por nivel

- Administrador y Desarrollador ingresan por defecto a **Inicio / Panel de gestión**.
- Usuario activo y Mando medio activo ingresan por defecto a **Nueva anomalía**.
- En equipos angostos o tablet, la navegación se abre desde el botón **Menú**; ya no se presenta como una barra fija inferior.

### 4.2 Menú lateral real

El orden implementado es:

1. Inicio — solo visible para Administrador y Desarrollador.
2. Nueva anomalía.
3. Seguimiento de anomalías.
4. Observaciones.
5. Tratamientos.
6. Acciones.
7. Validaciones.
8. Lecciones aprendidas.
9. Seguimiento de tratamientos.
10. Bandeja.
11. Indicadores — solo visible para Administrador y Desarrollador.
12. Órdenes afectadas — solo visible para Administrador y Desarrollador.

Las rutas frontend no tienen un segundo bloqueo visual común por módulo; la protección definitiva está en las API y servicios. Por eso una URL conocida puede mostrar una pantalla y luego rechazar la carga o edición si el usuario no tiene autorización.

## 5. Inicio / Panel de gestión

### Objetivo

Concentrar accesos, resumen operativo, seguimiento e ingreso a configuración.

### Acceso normal

Visible en el menú para Administrador y Desarrollador. El backend puede calcular un resumen limitado para otros usuarios, pero esa vista no está expuesta en su menú ni es su inicio normal.

### Menú contextual

La pantalla comienza en **Vista compacta**. El botón **Menú contextual** permite abrir:

- **Bienvenida y ayuda:** guía rápida de registrar, seguir, ejecutar y administrar.
- **Resumen rápido:** tarjetas históricas de anomalías, acciones, tratamientos y verificaciones.
- **Secciones principales:** accesos a módulos operativos.
- **Pasos del flujo:** registro y contención; revisión y causa; plan y ejecución; verificación y cierre.
- **Seguimiento operativo:** últimas anomalías, tratamientos en gestión y acciones pendientes.
- **Indicadores:** disponible para Administrador y Desarrollador.
- **Configuración admin:** usuarios, alcances y maestros; disponible para Administrador y Desarrollador.

### Resumen rápido

Las tarjetas consideran registros históricos, no solo activos:

- **Anomalías:** registradas, en evaluación, en análisis, en tratamiento, pendientes de verificación, cerradas, anuladas, reabiertas y vencidas.
- **Acciones:** integra acciones directas del modelo `ActionItem` y acciones de tratamiento del modelo `TreatmentTask`, separadas por estado y vencimiento.
- **Tratamientos:** pendientes, programados, en tratamiento, completados y cancelados.
- **Verificaciones:** pendientes, vencidas y completadas.

Para Administrador/Desarrollador el resumen es global y permite **Ver detalle por usuario**, con fila de total general. Para un resumen no global, el backend limita la información a casos relacionados con el usuario.

### Configuración y maestros

Incluye accesos a Usuarios, Importación de usuarios, Alcances de usuario, Áreas, Procesos/Sectores, Líneas, Tipos de desvío, Asignado a, Criterios de Revisión de hallazgos, Orden operativo, Tipos de acción, Tipos de órdenes afectadas y Panel admin Django.

El acceso **Roles y alcances** apunta a `/admin/accounts/role/`, pero el modelo `Role` ya no existe en los modelos actuales. Se considera **pendiente / no verificado en código** y probablemente obsoleto.

## 6. Nueva anomalía

### Objetivo

Registrar rápidamente un desvío desde planta, con código anual único y evidencia opcional.

### Quién puede usarla

Cualquier usuario autenticado y activo.

### Código visible

Al abrir el formulario, el sistema reserva un código con formato `AAAA####`, por ejemplo `20260001`. La reserva es individual, evita que dos usuarios usen el mismo número y vence, por defecto, a los 30 minutos. Si vence o ya fue consumida, se debe seleccionar **Reintentar reserva**. Una observación clasificada posteriormente recibe el sufijo `-OBS`.

### Paso 1 — Datos de inicio

Campos visibles y comportamiento real:

| Campo visible | Obligatorio | Comportamiento real |
| --- | --- | --- |
| Elaborado por: | Sí | Es un selector de **Área/Proceso afectado**, no de usuario. El registrador real se toma de la sesión. Esta etiqueta es inconsistente. |
| Fecha y hora | Sí | Fecha y hora de detección; se propone la hora actual. |
| Asignado a | Sí | Es otro selector del catálogo de áreas/procesos (`imputed_area`), no un usuario responsable. |
| Tipo de desvío | Sí | Selección desde el maestro activo. |

El sitio se deduce del área elegida. El origen de anomalía y el orden operativo se inicializan con el primer registro activo de sus catálogos y no se muestran como campos editables en esta pantalla.

### Paso 2 — Contexto

- **Título:** obligatorio.
- **Órdenes afectadas:** opcionales. Se pueden agregar varias. Cuando una fila se utiliza, Tipo de orden, número y cantidad son obligatorios. La cantidad debe ser un entero mayor que cero. No se permite repetir el mismo tipo y número dentro de una anomalía.
- **Observación:** descripción obligatoria del hecho.
- **Evidencia objetiva:** opcional y múltiple.

Formatos admitidos para evidencia: imágenes, PDF, Word, Excel, texto, CSV, RTF, ODT/ODS y ZIP. El máximo configurado por defecto es 20 MB por archivo. No se admiten ejecutables. Las fotos de usuario aceptan JPG, PNG o WEBP, hasta 5 MB por defecto.

### Confirmación y resultado

Al guardar:

1. Se crea la anomalía como **Registrada / Registro**.
2. El registrador es el usuario autenticado.
3. Se consumen el código reservado y sus órdenes afectadas.
4. Se crean participantes iniciales y un evento de historial.
5. Se genera una notificación interna y, si corresponde, correo al registrador.
6. Se abre la pantalla de confirmación.

Las evidencias se cargan después de crear la anomalía. Por eso puede ocurrir que la anomalía se registre correctamente y uno o más archivos fallen; la confirmación muestra esa advertencia y el caso no se pierde.

### Ejemplo

Un operario detecta 25 piezas rayadas de la OP 000123 en Lijado. Selecciona Lijado en “Elaborado por”, el proceso imputado en “Asignado a”, el tipo Rayado, carga título y descripción, agrega OP 000123 / 25 y una foto. El sistema registra `20260001` como Registrada.

## 7. Seguimiento de anomalías

### Objetivo

Consultar los casos visibles, abrir su detalle y, para Calidad, realizar la **Revisión de hallazgos**.

### Visibilidad

- Administrador/Desarrollador: todas las anomalías.
- Otros niveles: anomalías en las que el usuario sea registrador, responsable, creador, participante, responsable de observación, acción, tratamiento o verificación.

El filtro visible **Buscar** coincide por código, título, área y términos de estado/clasificación. Sin filtros, el listado prioriza registradas, luego abiertas y finalmente cerradas.

### Revisión de hallazgos

Solo Administrador y Desarrollador ven el selector. Las opciones provienen del maestro **Criterios de Revisión de hallazgos**, no de una lista fija en código.

Al confirmar una clasificación:

- se registra o actualiza la verificación inicial y la clasificación;
- se mueve el caso a **En evaluación / Revisión de hallazgos**, salvo cierre por inválida;
- si el criterio requiere responsable, se debe seleccionar un usuario activo con nivel Mando medio, Administrador o Desarrollador;
- el usuario seleccionado pasa a ser responsable de la anomalía;
- se genera notificación de gestión del hallazgo;
- si es Observación, el código recibe `-OBS`;
- si el criterio está configurado para cerrar como inválida, exige **Observación / Motivo** y cierra la anomalía de inmediato.

La primera clasificación puede modificarse una vez mientras la etapa siga entre Registro, Contención, Verificación inicial o Revisión de hallazgos. Después se bloquea. Un Administrador/Desarrollador puede seleccionar **Habilitar cambio** para habilitar otra modificación, siempre que la etapa todavía lo permita. Una anomalía ya incluida en un tratamiento no puede reclasificarse desde este selector.

### No conformidad y conformación del tratamiento

Cuando el criterio es reconocido como No conformidad (`NC` o texto equivalente):

1. El Administrador selecciona el **Responsable único del tratamiento**.
2. Puede seleccionar opcionalmente **Anomalías relacionadas**.
3. Las candidatas deben estar clasificadas para tratamiento, no estar cerradas/anuladas y no integrar ya otro tratamiento. Pueden ser otras NC u Observaciones marcadas como **Observación TRT (con tratamiento)**.
4. La vista **Sugeridas por repitencia** prioriza coincidencias; **Todas las elegibles** muestra el conjunto disponible.
5. Al confirmar, Calidad crea o consolida un único tratamiento. El responsable no puede agregar o quitar anomalías.

La numeración `TRT-AAAA-####` se reserva solo al crear un tratamiento. La consolidación de tratamientos pendientes preserva el código cancelado en auditoría y no pisa códigos existentes.

### Estudio de repitencia

Disponible desde Seguimiento para Administrador/Desarrollador. Exige fecha **Desde**, que no puede ser futura. Calcula repeticiones desde esa fecha hasta el momento actual:

- por tipo de desvío;
- por combinación de tipo, proceso asignado y clasificación;
- con listado de anomalías que integran cada grupo.

## 8. Detalle de anomalía

### Objetivo

Mostrar una vista consolidada y principalmente de solo lectura.

### Información visible

- Número de anomalía, título, tipo, estado y etapa.
- Descripción, fecha, responsable actual, órdenes y cantidades, proceso asignado, criticidad, resultados y resolución.
- Planes de acción del modelo general y acciones de tratamiento relacionadas.
- Verificación inicial, clasificación, tratamiento, análisis de causa, eficacia, aprendizaje y participantes.
- Evidencias descargables.
- Lecciones aprendidas asociadas a tratamientos.
- Historial de estados, etapas, comentarios y evidencias de transición.

La etiqueta **Elaborado por** vuelve a mostrar el área/proceso (`area.name`), no al usuario registrador. El registrador sí existe en el modelo y se muestra en Seguimiento, pero no en ese campo del detalle.

Si un tratamiento fue validado eficaz y cerró la anomalía, el detalle informa que está bloqueada para edición.

No se encontraron controles visibles en esta pantalla para transición genérica, comentarios, participantes, análisis genérico, propuestas, eficacia genérica o aprendizaje genérico, aunque las API correspondientes existen. Para el usuario web deben considerarse **disponibles solo en backend**.

## 9. Observaciones

### Objetivo

Gestionar anomalías clasificadas como Observación por uno de dos caminos: resolución directa o derivación a tratamiento.

### Acceso y visibilidad

- Administrador/Desarrollador: observaciones visibles globalmente.
- Responsable asignado: sus observaciones.
- Otros relacionados pueden ver la anomalía en Seguimiento, pero la gestión exige ser responsable o acceso global.

Filtros: búsqueda por código, título, área o usuario, e **Incluir observaciones cerradas**.

### 9.1 Carga de Observación directa

Campos obligatorios:

- **Responsable:** queda fijado al responsable asignado en Revisión de hallazgos; no puede cambiarse.
- **Fecha límite de ejecución**.
- **Observación**.

Al seleccionar **Cargar observación**, se conserva el caso abierto y se habilita **Acciones tomadas**.

### 9.2 Observación TRT

Antes de confirmar acciones, se puede marcar **Clasificar como Observación TRT (con tratamiento)**. En ese caso:

- el caso sigue clasificado como Observación;
- el camino queda `TREATMENT_PENDING`;
- la etapa vuelve a Revisión de hallazgos y el estado a En evaluación;
- no se deben cargar acciones tomadas en Observaciones;
- queda disponible para ser incluida por Calidad en un tratamiento;
- al vincularla, el camino cambia a `TREATMENT` y sale del circuito directo.

Si ya se confirmaron acciones tomadas, la casilla TRT queda bloqueada.

### 9.3 Acciones tomadas

Campos obligatorios:

- **Fecha de realizado**.
- **Fecha de verificación de eficacia**.
- **Detalle de la acción**.

Las evidencias objetivas son opcionales y múltiples. Al confirmar, la anomalía pasa a **Pendiente de verificación / Verificación de eficacia**, se crea el pendiente del responsable y se envía la notificación correspondiente.

### 9.4 Verificación de eficacia de Observación

Solo el responsable asignado puede confirmar:

- fecha de verificación;
- resultado **Eficaz: Sí/No**;
- observación opcional.

Resultado real:

- **Eficaz:** la anomalía pasa directamente a **Cerrada / Cierre** y se notifica al registrador.
- **No eficaz:** permanece **Pendiente de verificación**, abierta para registrar una nueva acción tomada. No cambia al estado Reabierta.

No existe una segunda aprobación de Calidad/Administrador después de que el responsable confirma eficacia. Por lo tanto, la política “el responsable cierra a su nivel y Calidad realiza cierre definitivo” está **pendiente / no verificada en código**.

## 10. Tratamientos

### Objetivo

Gestionar el tratamiento de una o varias anomalías conformadas por Calidad, convocar participantes, analizar causas, crear acciones y preparar la verificación de eficacia.

### Creación y visibilidad

- Los tratamientos se crean exclusivamente al confirmar una No conformidad en Revisión de hallazgos. La API de creación directa rechaza el alta manual.
- Administrador/Desarrollador ve todos.
- Otros usuarios ven tratamientos en los que sean creador, registrador o responsable de la anomalía principal, responsable del tratamiento, participante, responsable de acción o verificador.
- Solo el responsable con nivel de gestión o un usuario global puede editar el tratamiento. Ser convocado no concede edición del análisis.

Filtro: tratamiento, anomalía, responsable o sector.

Estados reales: **Pendiente**, **Programado**, **En tratamiento**, **Completado**, **Cancelado**.

### 10.1 Vista 1 — Convocatoria

#### Fecha de tratamiento

- **Fecha y hora programada:** obligatoria para confirmar.
- **Lugar de tratamiento:** opcional.
- **Guardar agenda:** solicita confirmación al usuario para comprobar que convocó a todos los necesarios.

Al confirmar:

- el estado Pendiente pasa a Programado;
- fecha, lugar y lista de convocados quedan bloqueados;
- se notifican los convocados, excepto el participante interno con rol Responsable;
- ya no se pueden agregar usuarios.

No existe un campo de duración de la reunión. La política de registrar duración está **pendiente / no verificada en código**.

#### Usuarios convocados

Antes de confirmar se puede filtrar por Área y elegir cualquier usuario activo. La participación creada desde la interfaz es **Convocado** y admite una nota opcional. El responsable se incorpora automáticamente como participante interno con rol Responsable.

#### Anomalías incluidas por Calidad

El responsable las ve, pero no puede modificar la composición. Administrador/Desarrollador puede abrir una corrección solo mientras el tratamiento sea Pendiente y no tenga datos de trabajo. Debe elegir responsable, composición y un **Motivo obligatorio**. Los códigos de tratamientos consolidados se conservan en auditoría.

#### Evidencias de anomalías vinculadas

La vista permite consultar las evidencias que ya pertenecen a las anomalías asociadas.

### 10.2 Vista 2 — Análisis

#### Método y observaciones

Métodos disponibles: 5 Why, 6M, Ishikawa, A3, 8D y Otro. Se registra el método elegido y un texto libre de observaciones. Seleccionar Ishikawa o 5 Why no abre un diagrama ni una secuencia estructurada de preguntas; el análisis detallado se documenta mediante observaciones y causas raíz. Por eso el soporte de esas metodologías es **parcial**.

Guardar método u observaciones inicia automáticamente el tratamiento si estaba Pendiente/Programado y mueve las anomalías a **En análisis / Análisis de causa**.

#### Evidencias del tratamiento

El responsable puede cargar archivo obligatorio y nota opcional. Se aplican las validaciones generales de evidencia.

#### Causas raíz encontradas

Se exige una descripción no vacía. Se pueden agregar varias causas, numeradas secuencialmente. Agregar la primera causa inicia el tratamiento y actualiza la etapa de las anomalías.

#### Acciones surgidas del tratamiento

Para crear una acción se exige:

- **Acción** o título;
- estado inicial;
- responsable, que puede ser cualquier usuario activo;
- fecha de ejecución;
- al menos una causa raíz asociada;
- descripción/observaciones.

Al crearla se asigna un código derivado del tratamiento, se genera un pendiente y se notifica al responsable. Las anomalías del tratamiento se relacionan a nivel de tratamiento; la interfaz ya no permite elegir anomalías distintas para cada acción, aunque el modelo histórico `TreatmentTaskAnomaly` continúa existiendo.

La edición operativa y la evidencia de la acción se realizan desde **Acciones**.

#### Evaluación de eficacia

Se debe indicar fecha y responsable. Son elegibles:

- usuarios convocados al tratamiento;
- todos los usuarios activos con nivel Mando medio activo.

Administrador y Desarrollador no aparecen por su nivel salvo que estén convocados; esta es la regla literal implementada.

Para que el tratamiento aparezca en Validaciones se exige:

- fecha de tratamiento ya transcurrida;
- al menos una causa raíz, todas con descripción;
- fecha y responsable de eficacia;
- todas las acciones de tratamiento en estado Completada.

No se exige explícitamente convocatoria confirmada, método seleccionado, observaciones, evidencia del tratamiento ni al menos una acción. Si no hay acciones, la condición “todas completadas” se cumple. Esta validación es **parcial** respecto del proceso esperado.

## 11. Acciones

### Objetivo real de la pantalla

La pantalla **Acciones y pendientes** muestra únicamente acciones surgidas de tratamientos (`TreatmentTask`) asignadas al usuario autenticado. Las acciones generales (`ActionItem`) existen en modelos/API y se cuentan en el Panel, pero no se encontró una pantalla para crearlas o gestionarlas. Esta diferencia es importante.

### Filtros

- Buscar por código, título, descripción, anomalía o usuario.
- Anomalía.
- Tratamiento.
- Estado: Pendiente, En curso o Vencida.
- Fecha terminada.
- Usuario que la realizó.

El backend limita siempre la consulta al usuario responsable actual; por eso el filtro de usuario no permite a un Administrador consultar acciones ajenas desde esta pantalla. El control global de pendientes está en el Resumen del Panel y el detalle histórico en Seguimiento de tratamientos.

### Ejecutar una acción

El responsable asignado puede:

- cambiar el estado;
- registrar una nota de evidencia obligatoria para cada cambio de estado;
- cargar archivos de evidencia con nota opcional.

El gestor del tratamiento puede modificar título, descripción, responsable y fecha, pero solo el responsable asignado puede cambiar el estado o cargar evidencia.

La interfaz ofrece Pendiente, En curso, Completada y Cancelada. Para acciones de tratamiento no se encontró una tabla que limite las transiciones; incluso una completada podría seleccionarse nuevamente como pendiente/en curso mientras el tratamiento no esté cerrado eficazmente. Esto es **inconsistente** con las acciones generales, que tienen estados terminales.

Las completadas se excluyen del listado operativo y aparecen en el desplegable **Completadas** con paginación.

### Acciones generales disponibles solo en backend

Existe un segundo flujo:

- plan Borrador → Activo → Completado/Cancelado;
- acciones Pendiente → En curso/Completada/Cancelada;
- comentario obligatorio en transiciones;
- activación requiere al menos una acción;
- cierre del plan requiere acciones obligatorias completadas o canceladas;
- evidencia mediante archivo o nota;
- estados Completada y Cancelada son terminales.

No se encontró una pantalla para crear planes, acciones generales, activarlos ni transitarlos. No debe presentarse a usuarios como función disponible en la interfaz.

## 12. Validaciones

### Objetivo

Permitir que el responsable designado evalúe la eficacia de un tratamiento listo.

### Quién puede validar

Exclusivamente el usuario guardado como **Responsable de evaluación de eficacia**. Ni siquiera Administrador/Desarrollador puede sustituirlo en la confirmación, salvo que sea el asignado.

### Pantalla

Muestra **Disponibles y pendientes**. Al elegir un tratamiento se ven sus anomalías, responsable, fecha y los faltantes. Cuando está listo, se informa:

- **Resultado de validación:** Eficaz o No eficaz, obligatorio.
- **Observación:** opcional.

### Resultado

- **Eficaz:** el tratamiento pasa a Completado; todas sus anomalías abiertas pasan directamente a Cerrada / Cierre; se bloquean tratamiento y anomalías; se notifican participantes y registradores.
- **No eficaz:** el tratamiento vuelve o permanece En tratamiento y sigue editable; sus anomalías no cambian automáticamente a Reabierta. Se notifica a los involucrados para revisar acciones.

No existe un estado intermedio “Cerrada por responsable”. La validación eficaz realiza el cierre definitivo de tratamiento y anomalías.

## 13. Lecciones aprendidas

### Objetivo

Registrar el aprendizaje de tratamientos validados como eficaces.

### Visibilidad y edición

La lista muestra tratamientos eficaces visibles para el usuario. Solo el responsable gestor del tratamiento o un usuario global puede guardar. La interfaz muestra el formulario también a participantes que solo tienen lectura; al intentar guardar, el backend lo rechazará. Esta diferencia de interfaz es **inconsistente**.

### Campos y validaciones

- **¿Hubo un aprendizaje?** obligatorio.
  - Sí: **¿Qué se aprendió?** obligatorio.
  - No: **¿Por qué no se aprendió?** obligatorio.
- **¿Modifica procedimiento?** obligatorio.
  - Sí: observaciones sobre la modificación obligatorias.
- Evidencias: opcionales y múltiples.

La primera publicación notifica a los usuarios involucrados. Actualizaciones posteriores se auditan pero no vuelven a disparar esa notificación de primera publicación.

## 14. Seguimiento de tratamientos

### Objetivo

Consulta histórica de solo lectura para revisar tratamiento, participantes, anomalías, causas, acciones, eficacia, evidencias e historial.

### Acceso

Administrador/Desarrollador ve todos. Otros usuarios ven tratamientos relacionados con ellos.

### Filtros

- código de procedimiento/tratamiento;
- usuario relacionado;
- proceso/área.

### Detalle

Incluye datos generales, responsable, convocatoria, anomalías vinculadas, convocados, causas raíz, acciones —algunos textos internos aún dicen “Tareas generadas”—, evaluación de eficacia, evidencias y eventos de auditoría. Los tratamientos cancelados por consolidación permanecen consultables para preservar sus códigos y la trazabilidad.

## 15. Bandeja

### Objetivo

Unificar avisos y pendientes del usuario sin eliminar el modelo de Bandeja.

### Tarjetas de resumen

Pendientes, En curso, Vencidas y Avisos no leídos.

### Pestañas

- **Pendientes:** asignaciones, verificaciones e invitaciones abiertas.
- **Avisos:** comunicaciones informativas, priorizando no leídas.
- **Historial:** pendientes completados o descartados.

### Acciones

- **Abrir contexto:** marca la notificación como leída y navega al caso cuando existe una ruta válida.
- **Marcar leída:** para avisos sin contexto.
- **Confirmar visto:** disponible manualmente para participaciones de análisis o tratamiento; las marca completadas, no ejecuta la acción de negocio.

Los pendientes de acciones y verificaciones se sincronizan automáticamente con el estado real. La ruta antigua `/tasks` redirige a la pestaña Pendientes; la Bandeja y su modelo no fueron eliminados.

## 16. Indicadores

### Acceso

Administrador y Desarrollador. Tanto catálogo, dashboards, CSV e informes PDF usan esa restricción en backend.

### Indicadores disponibles

1. **Anomalías generadas y tratadas:** altas, cierres, cohorte tratada, pendientes, inválidas, anuladas y reabiertas.
2. **Tratamientos:** creados, completados eficazmente, cohorte completada y abiertos.
3. **Anomalías por proceso:** cantidad, porcentaje, evolución y proceso de mayor incidencia.
4. **Clasificación de hallazgos:** clasificados, sin clasificar y distribución; separa Observación TRT sin perder la clasificación original.
5. **Repetitividad y Pareto:** por proceso+tipo, proceso, tipo, origen, clasificación u orden afectada; muestra acumulado.
6. **Acciones:** integra acciones generales y de tratamiento, estados, vencidas y cumplimiento en término.
7. **Eficacia:** integra verificaciones de tratamientos y observaciones, eficaces, no eficaces, pendientes, vencidas y conteo de reaperturas.
8. **Órdenes afectadas:** órdenes únicas, registros, cantidad de piezas y anomalías involucradas.
9. **Lecciones aprendidas:** tratamientos eficaces, cobertura de aprendizaje, pendientes y procedimientos modificados.

### Uso del dashboard

Cada indicador muestra tarjetas, evolución mensual, distribución, notas de fórmula y tabla paginada. Filtros comunes:

- Desde y Hasta.
- Proceso.
- Agrupación adicional en Repetitividad y Pareto.

El sistema compara el período elegido con el período inmediatamente anterior de igual duración. Los porcentajes y fechas base se explican en la propia tarjeta.

### Exportar CSV

**Exportar CSV** genera el detalle completo del conjunto filtrado, no solo la página visible. Usa `;` como separador y codificación compatible con Excel.

### Enviar informe PDF

1. Seleccionar **Enviar informe**.
2. Buscar y elegir al menos un destinatario.
3. Solo aparecen usuarios activos con correo y **Notificación por correo** habilitada.
4. Confirmar. Se genera el PDF con período, filtros, métricas y muestra de datos, y se encola el envío.

El generador recibe una copia si también tiene el correo habilitado. No se incluye enlace de sesión. El archivo PDF temporal se elimina del servidor cuando se completan los envíos o al vencer; se conserva el registro de auditoría, filtros, destinatarios, estado y checksum. No existe descarga local del PDF desde la interfaz.

## 17. Órdenes afectadas

### Acceso normal

Visible para Administrador y Desarrollador. El backend aplica la visibilidad de anomalías, por lo que técnicamente puede devolver un subconjunto a otros usuarios si acceden por URL; no es un acceso normal de menú.

### Filtros

Buscar, Tipo de orden, Número, Anomalía, Proceso, cantidad mínima/máxima, Estado y fechas Desde/Hasta. Las cantidades deben ser enteros no negativos y el máximo no puede ser menor que el mínimo. La fecha Hasta no puede ser anterior a Desde.

### Totalizadores

- Órdenes diferentes: combinación normalizada de tipo y número.
- Registros de afectación.
- Anomalías involucradas.
- Cantidad total afectada.
- Desglose por tipo.

La tabla muestra Tipo, Número, Cantidad, Anomalía, Proceso, Fecha y Estado. **Exportar CSV** descarga el conjunto filtrado completo.

## 18. Administración de usuarios

### Acceso

La pantalla web está restringida a Administrador/Desarrollador. El backend permite que Mando medio consulte el directorio, pero no crear, editar ni eliminar.

### Listado y filtros

Busca por usuario, correo, nombre, apellido o legajo. Por defecto muestra solo activos; **Incluir usuarios inactivos** amplía el listado. Se muestran 30 registros por página.

### Alta y edición

Campos:

- Usuario y email obligatorios y únicos.
- Nombre, apellido, legajo y celular.
- Foto.
- Nivel de acceso.
- Sector principal descriptivo.
- Contraseña provisoria y confirmación.
- Activo.
- **Notificación por correo**.

Si no se informa contraseña, el backend genera una clave numérica de 8 dígitos y la devuelve una sola vez. La interfaz también puede generar una clave provisoria más compleja. Al asignar una nueva provisoria a un usuario existente, la contraseña anterior deja de funcionar y se fuerza el cambio en el próximo ingreso.

Solo un Desarrollador/superusuario puede asignar el nivel Desarrollador.

### Notificación por correo

Está desactivada por defecto. Las notificaciones internas se generan igualmente; la casilla controla la creación del destinatario de canal Email. Además debe estar habilitado el envío global del servidor y existir una dirección válida.

Eventos de correo comprobados:

- anomalía registrada, al registrador;
- gestión de hallazgo / responsable asignado;
- acción general o acción de tratamiento asignada o reasignada;
- convocatoria de tratamiento al confirmar agenda;
- verificación de eficacia de tratamiento u observación;
- cierre de observación o anomalía inválida al registrador;
- cierre eficaz del tratamiento a involucrados y registradores;
- resultado no eficaz a involucrados;
- primera publicación de lección aprendida a involucrados;
- resumen diario de vencidos/próximos, cuando se ejecuta el proceso programado;
- informe de indicador solicitado.

La participación genérica de anomalía creada por la API genera notificación interna, pero no habilita correo en esa función. Se considera comportamiento diferente respecto de la convocatoria de tratamiento.

### Eliminar usuario

La API intenta una eliminación física y prohíbe eliminar la propia cuenta. Como muchas relaciones usan protección de integridad, un usuario con registros vinculados no podrá eliminarse; no se encontró manejo específico y amigable de ese error en esta vista. Para preservar trazabilidad se recomienda desactivar usuarios en lugar de eliminarlos.

## 19. Importación masiva de usuarios

Admite CSV o Excel `.xlsx` y tres modos:

- Crear nuevos y actualizar existentes.
- Crear solo usuarios nuevos.
- Actualizar usuarios existentes.

Primero realiza una vista previa con altas, actualizaciones, omisiones, errores y duplicados. Campos reconocidos: legajo, nombre, apellido, email/correo, usuario y celular. Email, nombre y apellido son obligatorios. Detecta duplicados por email, legajo y usuario.

Los nuevos usuarios reciben contraseña numérica temporal de 8 dígitos y cambio obligatorio. El resultado puede descargarse como reporte, incluyendo credenciales generadas; ese archivo debe tratarse como confidencial.

## 20. Alcances de usuario

### Acceso

Administrador/Desarrollador en la interfaz. Permite buscar un usuario activo, elegir Nivel de acceso y marcar permisos específicos.

### Permisos específicos disponibles

Menú contextual, Nueva anomalía, Seguimiento de anomalía, Observación, Tratamientos, Creación de tratamientos, Convocatoria, Análisis, Acciones, Pendientes y Verificación de eficacia.

El guardado reemplaza los permisos manuales del usuario. El perfil muestra también los permisos efectivos de Django.

### Limitación real

No todos los servicios consultan estas casillas. Por ejemplo, crear anomalías depende de estar activo; clasificar depende del nivel Administrador/Desarrollador; gestionar un tratamiento depende de ser Mando medio responsable o global; ejecutar y verificar dependen de la asignación exacta. Por eso una casilla puede no conceder una función si falta la condición de nivel/asignación, y quitarla puede no revocar un flujo que usa una regla directa. Se considera una arquitectura de permisos **inconsistente** y debe simplificarse antes de usar las casillas como matriz contractual.

## 21. Catálogos y maestros

### Acceso

Administrador/Desarrollador.

### Catálogos

- Áreas principales (`Site`).
- Sectores/Procesos (`Area`), dependientes de Área principal.
- Líneas, dependientes de Sector/Proceso.
- Tipos de desvío.
- Asignado a / orígenes de anomalía.
- Criterios de Revisión de hallazgos.
- Orden operativo / prioridad.
- Tipos de acción.
- Tipos de órdenes afectadas.

### Operación

Cada registro posee Código, Nombre, Orden de visualización y Activo; los catálogos jerárquicos exigen padre. Los criterios de Revisión de hallazgos agregan:

- **Requiere responsable de clasificación**.
- **Cierra anomalía como inválida**.

Se puede buscar por código/nombre y mostrar/ocultar inactivos. Los directorios administrativos se ordenan por código y muestran 30 por página. En los selectores operativos, las opciones activas se ordenan alfabéticamente por nombre para facilitar la búsqueda.

La eliminación es física. Si existen registros relacionados, el backend devuelve “No se puede eliminar porque tiene registros relacionados”. Para conservar historia, conviene desactivar.

Inconsistencia: el catálogo **Asignado a** se guarda como `AnomalyOrigin`, pero en Nueva anomalía el campo visible “Asignado a” usa `imputed_area`; el origen se selecciona automáticamente y no es visible.

## 22. Históricos, auditoría y trazabilidad

Se comprobó:

- historial de estado/etapa de anomalía, con usuario, fecha, comentario y nota de evidencia;
- historial de acciones generales;
- eventos transversales `AuditEvent` con entidad, acción, actor, estado anterior/posterior y request ID;
- evidencias protegidas por visibilidad y sesión;
- registros de clasificación, verificación inicial, causa, eficacia, aprendizaje y participantes;
- auditoría de tratamientos mostrada en Seguimiento de tratamientos;
- auditoría de informes de indicadores.

Existe API global de auditoría con filtros, detalle y resumen para Administrador/Desarrollador, pero no se encontró una pantalla React ni un acceso de menú a una auditoría transversal. El Panel admin Django puede exponer parte de esta información técnica.

## 23. Ciclo de vida real de una anomalía

Los estados y etapas son conceptos distintos. El flujo más habitual es:

| Evento | Estado real | Etapa real |
| --- | --- | --- |
| Alta | Registrada | Registro |
| Clasificación válida y asignación | En evaluación | Revisión de hallazgos |
| Tratamiento creado | En análisis | Tratamiento creado |
| Método/causas | En análisis | Análisis de causa |
| Plan/acciones en ejecución | En tratamiento | Plan de acción / Ejecución y seguimiento / Resultados |
| Acciones de observación confirmadas o tratamiento listo | Pendiente de verificación | Verificación de eficacia |
| Verificación eficaz | Cerrada | Cierre |
| Reapertura administrativa genérica | Reabierta | Una etapa seleccionada de análisis/tratamiento |

Variantes:

- **Inválida:** Registrada/En evaluación → Cerrada en Revisión de hallazgos.
- **Observación directa eficaz:** En evaluación → Pendiente de verificación → Cerrada.
- **Observación directa no eficaz:** permanece Pendiente de verificación y vuelve a acciones, sin estado Reabierta.
- **NC/tratamiento eficaz:** En análisis/En tratamiento → Cerrada directamente al validar eficacia.
- **Tratamiento no eficaz:** tratamiento En tratamiento; la anomalía no se marca automáticamente Reabierta.

La API genérica permite Reabrir desde Cerrada o Pendiente de verificación hacia Tratamiento creado, Análisis de causa, Propuestas, Plan de acción, Ejecución y seguimiento o Resultados, solo por usuario global y con comentario. No se encontró botón de reapertura en la interfaz actual.

## 24. Guías rápidas paso a paso

### 24.1 Registrar

1. Abrir **Nueva anomalía**.
2. Confirmar que exista código reservado.
3. Elegir proceso afectado en “Elaborado por”, fecha, proceso en “Asignado a” y tipo de desvío.
4. Escribir título y observación.
5. Agregar órdenes y evidencias si corresponden.
6. Guardar y conservar el número mostrado.

### 24.2 Clasificar y asignar

1. Calidad abre **Seguimiento de anomalías**.
2. Busca el caso y selecciona Revisión de hallazgos.
3. Si es inválida, documenta motivo.
4. Si requiere gestión, elige responsable Mando medio/Admin/Desarrollador.
5. Si es NC, revisa candidatas relacionadas.
6. Confirma. El sistema registra clasificación, responsable, historial y notificación.

### 24.3 Resolver una Observación directa

1. Responsable abre **Observaciones**.
2. Selecciona caso, fecha límite y observación; no marca TRT.
3. Confirma carga.
4. Registra fecha realizada, acción, fecha de eficacia y evidencias.
5. Confirma acciones.
6. En la fecha prevista, confirma Eficaz o No eficaz.
7. Si no eficaz, revisa y vuelve a cargar acciones.

### 24.4 Derivar una Observación a tratamiento

1. Antes de acciones, marcar **Observación TRT** y documentar motivo.
2. Calidad la incluye al clasificar una NC o corrige un tratamiento pendiente elegible.
3. Desde entonces se gestiona dentro del tratamiento; no desde Acciones tomadas de Observaciones.

### 24.5 Realizar un tratamiento de NC

1. Calidad clasifica NC, asigna responsable y conforma anomalías.
2. Responsable abre **Tratamientos / Vista 1**.
3. Convoca usuarios, fija fecha y lugar, y confirma agenda.
4. Abre **Vista 2**, elige método y documenta análisis.
5. Carga una o más causas raíz.
6. Crea acciones para causas, con responsable y fecha.
7. Los responsables ejecutan en **Acciones**, documentan cambios y evidencias.
8. Cuando estén completas, el responsable del tratamiento fija fecha y responsable de eficacia.
9. El verificador abre **Validaciones** y confirma resultado.
10. Si eficaz, se cierran tratamiento y anomalías; luego el gestor registra **Lecciones aprendidas**.

### 24.6 Reabrir

No hay acción visible. La reapertura solo está implementada en la API genérica para Administrador/Desarrollador, exige comentario y etapa destino válida. Los resultados “No eficaz” de Observación y Tratamiento no usan el estado Reabierta automáticamente.

## 25. Reglas clave del sistema

1. Toda operación utiliza al usuario autenticado; los enlaces de correo no deben transferir una sesión ajena.
2. Todos los usuarios activos pueden registrar anomalías.
3. Solo Administrador/Desarrollador clasifica hallazgos y conforma tratamientos.
4. El responsable de clasificación debe ser Mando medio, Administrador o Desarrollador.
5. Las anomalías de un tratamiento las define Calidad; el responsable no cambia la composición.
6. Una Observación debe elegir resolución directa o TRT antes de confirmar acciones.
7. Confirmar convocatoria bloquea agenda y convocados.
8. Solo el responsable asignado cambia el estado de su acción y carga su evidencia.
9. Solo el verificador designado confirma eficacia.
10. La eficacia positiva cierra y bloquea; la negativa mantiene el trabajo abierto.
11. Las evidencias tienen formatos y tamaños controlados y requieren sesión para abrirse.
12. La casilla de correo no controla la notificación interna; solo el canal Email.
13. Desactivar catálogos y usuarios preserva mejor la trazabilidad que eliminarlos.
14. El historial y la auditoría no sustituyen la evidencia objetiva, pero documentan quién, cuándo y qué cambió.

## 26. Funciones detectadas pero incompletas, inconsistentes o pendientes

### Prioridad alta

1. **Flujo de estados esperado:** no existen estados explícitos Clasificada, Asignada ni Cerrada por responsable. La política completa es parcial.
2. **Reapertura por no eficacia:** Observación no eficaz queda Pendiente de verificación; tratamiento no eficaz queda En tratamiento. Ninguno marca automáticamente la anomalía Reabierta.
3. **Cierre de Observación por Calidad:** el responsable eficaz cierra definitivamente; no existe revisión final separada de Calidad/Admin.
4. **Elaborado por:** en alta y detalle muestra Área/Proceso, no el usuario elaborador. El registrador real existe, pero la etiqueta induce a error.
5. **Dos modelos de acciones:** el Panel integra `ActionItem` y `TreatmentTask`, pero la pantalla Acciones solo opera `TreatmentTask`; planes/acciones generales no tienen interfaz.
6. **Permisos mixtos:** nivel, permisos manuales y asignación se superponen sin una única matriz coherente.

### Prioridad media

7. **Métodos de causa:** 5 Why e Ishikawa son selección + texto/causas; no hay herramienta estructurada específica.
8. **Convocatoria:** fecha y lugar implementados; duración no implementada.
9. **Bloqueadores de eficacia:** no exigen convocatoria confirmada, método, observación, evidencia ni al menos una acción.
10. **Acciones de tratamiento:** no se validan transiciones terminales como en acciones generales; una completada puede volver a otro estado antes del cierre eficaz.
11. **Lecciones aprendidas:** participantes con lectura ven un formulario editable que el backend rechazará.
12. **Auditoría transversal:** API implementada, sin pantalla de usuario.
13. **Roles y alcances:** enlace administrativo apunta a un modelo de rol inexistente; textos de Alcances aún mencionan rol.
14. **Asignado a/origen:** el nombre del catálogo y el campo visible no representan la misma relación.
15. **Eliminación de usuarios:** es física y puede fallar por relaciones protegidas sin mensaje específico; debería privilegiarse desactivación.

### Prioridad baja / terminología

16. **Tarea/Acción:** el modelo y algunos históricos dicen Tarea, mientras la interfaz principal usa Acción.
17. **Vencidas en Bandeja:** la tarjeta utiliza un tono visual de éxito para vencidas; el dato es correcto, el color puede confundir.
18. **Rutas frontend:** módulos administrativos ocultos no tienen un guard común de ruta; la API rechaza, pero la pantalla puede abrir antes del error.
19. **Participación genérica:** las invitaciones de anomalía generan aviso interno sin correo, a diferencia de convocatoria de tratamiento.

Estas observaciones no modifican el sistema. Son recomendaciones para una etapa posterior de simplificación y cierre de brechas.
