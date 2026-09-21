export type GuidedTourStep = {
  selector: string;
  activateSelector?: string;
  title: string;
  content: string;
};

export type GuidedTourDefinition = {
  id: string;
  title: string;
  description: string;
  steps: GuidedTourStep[];
};

const TOURS: Record<string, GuidedTourDefinition> = {
  quickSummary: {
    id: "quick-summary",
    title: "Consultar el Resumen rápido",
    description: "Interpreta los totales históricos, los estados y el detalle por usuario.",
    steps: [
      { selector: ".contextual-toolbar", title: "Resumen rápido", content: "Esta vista concentra el estado general del sistema para Administrador y Desarrollador. Los datos se obtienen del resumen histórico vigente." },
      { selector: ".contextual-current", title: "Vista activa", content: "El encabezado confirma que estás consultando Resumen rápido. Desde el Menú contextual puedes abrir otros bloques o el Centro de Ayuda." },
      ...[
        { key: "anomalies", title: "Seguimiento de anomalías", content: "El total histórico incluye los casos y su distribución por estados, también los terminales. El desglose compacto puede omitir estados: consulta el detalle para verlos todos." },
        { key: "actions", title: "Acciones", content: "Este total reúne acciones de observaciones y de tratamientos, con su distribución por estados. Es un resumen histórico, no solo una lista de pendientes." },
        { key: "treatments", title: "Tratamientos", content: "Consulta el total histórico y sus estados. Acciones completas, eficacia verificada y cierre formal son hitos distintos: revisa el estado informado, no únicamente la cantidad de acciones." },
        { key: "validations", title: "Verificaciones de eficacia", content: "Esta tarjeta resume las verificaciones de tratamientos por responsable. No debe confundirse con el listado de Validaciones, que permite consultar también observaciones." },
      ].flatMap((card) => [
        { selector: `[data-tour="summary-${card.key}"]`, title: card.title, content: `${card.content} El recorrido señala esta tarjeta y bloquea el resto de la pantalla.` },
        { selector: `[data-tour="summary-detail-${card.key}"]`, activateSelector: `[data-tour="summary-${card.key}"] .dashboard-detail-toggle[aria-expanded="false"]`, title: `${card.title}: detalle por usuario`, content: "El recorrido abre este detalle automáticamente, sin modificar registros. Revisa el total y los estados de cada usuario activo y la fila Total general. Un caso puede estar vinculado a varias personas; no interpretes la suma de filas como un total de casos únicos. Si no hay datos, se muestra el aviso correspondiente." },
      ]),
      { selector: ".contextual-current", title: "Continuar la gestión", content: "Resumen rápido es una consulta, no cambia estados ni habilita permisos de edición. Al terminar, abre la sección correspondiente desde el menú para investigar casos concretos, evidencias e historiales." },
    ],
  },
  newAnomaly: {
    id: "new-anomaly",
    title: "Registrar una anomalía",
    description: "Recorre la carga inicial, el contexto y la confirmación del registro.",
    steps: [
      { selector: ".form-hero", title: "Nueva anomalía", content: "Aquí comienza el registro. El código visible se reserva automáticamente y acompañará al caso durante todo su ciclo." },
      { selector: ".anomaly-form .form-section:nth-of-type(1)", title: "Paso 1 — Datos de inicio", content: "Completa los procesos relacionados, la fecha de detección y el tipo de desvío. Los campos marcados son obligatorios." },
      { selector: '[name="area"]', title: "Elaborado por", content: "Selecciona el área o proceso donde se origina el registro." },
      { selector: '[name="imputed_area"]', title: "Asignado a", content: "Selecciona el área o proceso relacionado con la anomalía." },
      { selector: '[name="anomaly_type"]', title: "Tipo de Desvío", content: "Falla, defecto o evento detectado." },
      { selector: ".anomaly-form .form-section:nth-of-type(2)", title: "Paso 2 — Contexto", content: "Escribe un título breve, describe el hecho y agrega órdenes afectadas o evidencias cuando correspondan." },
      { selector: ".affected-orders-editor", title: "Órdenes afectadas", content: "Esta sección es opcional. Cada fila utilizada requiere tipo, número y cantidad mayor que cero." },
      { selector: '[data-tour="anomaly-observation"]', title: "Observación", content: "Explica qué ocurrió, dónde se detectó y cualquier dato necesario para comprender el hallazgo." },
      { selector: '[data-tour="anomaly-objective-evidence"]', title: "Evidencia objetiva", content: "Este campo es opcional. Adjunta archivos que respalden la anomalía, por ejemplo fotos, PDF, Word, Excel o texto. Puedes seleccionar archivos más de una vez para incorporarlos todos antes de confirmar." },
      { selector: ".submit-bar", title: "Confirmar registro", content: "Revisa la información y confirma. La anomalía quedará Registrada y disponible para seguimiento." },
    ],
  },
  anomalyTracking: {
    id: "anomaly-tracking",
    title: "Seguimiento de anomalías",
    description: "Aprende a buscar, abrir y revisar el estado de los casos visibles.",
    steps: [
      { selector: ".page-header", title: "Seguimiento", content: "Esta pantalla reúne las anomalías disponibles según tu nivel y relación con cada caso." },
      { selector: ".tabbed-filters", title: "Buscar y filtrar", content: "Escribe código, título, área o estado para reducir el listado. Puedes limpiar el filtro cuando quieras." },
      { selector: ".anomaly-row", title: "Tarjeta de anomalía", content: "La tarjeta resume código, título, tipo, generador, proceso, fecha y estado. Pulsa sobre sus datos para abrir el detalle." },
      { selector: ".anomaly-classification-control", title: "Revisión de hallazgos", content: "Selecciona Inválida, No conformidad u Observación. Oportunidad de mejora está temporalmente deshabilitada. Si eliges No conformidad, define responsable, fecha límite y un comentario opcional para crear un tratamiento nuevo." },
      { selector: ".associate-anomalies-button", title: "Asociar anomalías", content: "Usa este camino para incorporar el caso a un tratamiento existente. La anomalía se clasificará automáticamente como No Conformidad y heredará el responsable del tratamiento." },
      { selector: ".association-treatment-panel", title: "Seleccionar tratamiento", content: "Busca y marca un único tratamiento. Se incluyen tratamientos en preparación o ejecución y aquellos con todas las acciones completadas que todavía no fueron validados como eficaces." },
      { selector: ".association-treatment-option", title: "Revisar el avance", content: "Cada tarjeta muestra el tratamiento, su anomalía principal, responsable, estado y cantidad de acciones completadas." },
      { selector: ".association-confirm-actions", title: "Confirmar asociación", content: "La confirmación vuelve a validar el estado del tratamiento, registra el vínculo y conserva su agenda, análisis, acciones y avance." },
      { selector: ".pagination-controls", title: "Cambiar de página", content: "Utiliza la paginación para consultar todos los resultados sin perder los filtros aplicados." },
    ],
  },
  observations: {
    id: "observations",
    title: "Gestionar Observaciones",
    description: "Recorre la selección del caso, la carga de acciones y la verificación.",
    steps: [
      { selector: ".page-header", title: "Observaciones", content: "Aquí se gestionan las anomalías clasificadas como Observación que están dentro de tu alcance." },
      { selector: ".tabbed-filters", title: "Localizar un caso", content: "Busca por código, título, área o usuario. También puedes incluir los casos cerrados." },
      { selector: ".treatment-layout > article:first-child", title: "Listado", content: "Selecciona una anomalía para consultar y trabajar su detalle." },
      { selector: '[data-tour="observation-summary"]', title: "Observación seleccionada", content: "Revisa el código y estado del caso abierto. El recorrido mantiene esta observación seleccionada y señala sus subsecciones, con el resto de la pantalla grisado y bloqueado." },
      { selector: '[data-tour="observation-general"]', title: "Datos generales", content: "Calidad designa al responsable y la fecha límite en Revisión de hallazgos. El responsable analiza la causa y decide si puede resolver el caso directamente o necesita investigar la causa raíz mediante un tratamiento." },
      { selector: '[data-tour="observation-cause"]', title: "Identificar la causa", content: "El responsable registra lo encontrado. Si necesita investigar la causa raíz, documenta esa necesidad y elige Observación TRT antes de confirmar. Este campo es obligatorio y queda en solo lectura después de la carga." },
      { selector: '[data-tour="observation-treatment-path"]', title: "Observación TRT", content: "Si el caso requiere tratamiento, marca esta opción antes de confirmar acciones. El caso se deriva al flujo de tratamiento; con acciones ya confirmadas no puede cambiarse este camino." },
      { selector: '[data-tour="observation-general-confirm"]', title: "Confirmar datos generales", content: "Pulsa Siguiente para confirmar los datos y habilitar Acciones tomadas. Durante el recorrido usa los botones de la ayuda; al finalizar podrás operar el formulario." },
      { selector: '[data-tour="observation-actions"]', title: "Acciones tomadas", content: "Después de confirmar los datos generales, registra cada acción con detalle, fecha estimada de realización y fecha de validación. Guarda las acciones de forma individual." },
      { selector: '[data-tour="observation-evidence"]', title: "Evidencias objetivas", content: "Adjunta archivos que respalden las acciones tomadas. Para finalizar cada acción debes cargar su evidencia propia desde Acciones antes de marcarla como finalizada." },
      { selector: '[data-tour="observation-action-list"]', title: "Acciones registradas", content: "Consulta las acciones guardadas, sus estados y fechas. Al finalizar una acción registra su fecha real; todas deben estar completadas antes de verificar eficacia." },
      { selector: '[data-tour="observation-effectiveness"]', title: "Verificación de eficacia", content: "Se habilita con acciones registradas y solo permite verificar cuando todas están completadas y se alcanzó la fecha de validación más lejana. Lista todas las acciones tomadas como referencia." },
      { selector: '[data-tour="observation-effectiveness-reason"]', title: "Fundamento de eficacia", content: "Selecciona Eficaz o No eficaz, registra la fecha de realización y explica obligatoriamente el fundamento de tu decisión." },
      { selector: '[data-tour="observation-effectiveness-confirm"]', title: "Guardar verificación", content: "El responsable registra la verificación. Si resulta eficaz se cierra la observación y continúa Lecciones aprendidas; si no es eficaz deben registrarse nuevas acciones." },
    ],
  },
  treatments: {
    id: "treatments",
    title: "Gestionar Tratamientos",
    description: "Conoce la selección, convocatoria, análisis y preparación de eficacia.",
    steps: [
      { selector: ".page-header", title: "Tratamientos", content: "La pantalla muestra los tratamientos relacionados con tu usuario y permite gestionarlos cuando eres responsable." },
      { selector: ".tabbed-filters", title: "Buscar tratamiento", content: "Utiliza los filtros para localizar por código, anomalía u otros datos disponibles." },
      { selector: ".treatment-layout > article:first-child", title: "Seleccionar tratamiento", content: "Elige una tarjeta para cargar su información en el panel de trabajo." },
      { selector: '[data-tour="treatment-summary"]', title: "Tratamiento seleccionado", content: "Revisa el código, la anomalía principal y el estado. El recorrido mantiene este tratamiento abierto y bloquea el resto de la pantalla mientras señala cada subsección." },
      { selector: ".treatment-origin-data", title: "Datos de creación", content: "Consulta la fecha límite de inicio del tratamiento y el comentario registrado al confirmar la No Conformidad. La fecha límite indica hasta cuándo debe iniciarse el tratamiento. Si aparece en rojo con Vencido, el plazo ya pasó: aun así, debe iniciarse a la brevedad." },
      { selector: ".treatment-tab-row", title: "Vistas del tratamiento", content: "Convocatoria organiza agenda y participantes. Análisis reúne método, causas, acciones y eficacia. El recorrido abrirá automáticamente la vista que explica cada tarjeta." },
      { selector: ".treatment-linked-anomalies", activateSelector: ".treatment-tab-agenda", title: "Vista 1 — Anomalías asociadas", content: "Consulta la anomalía de origen y las asociadas. Las nuevas asociaciones se realizan desde Seguimiento de anomalías por Administrador o Desarrollador." },
      { selector: '[data-tour="treatment-participants"]', activateSelector: ".treatment-tab-agenda", title: "Usuarios convocados", content: "Agrega las personas que deben participar del tratamiento. Consulta sus datos y registra una nota cuando corresponda. Debe existir al menos un convocado antes de confirmar la agenda." },
      { selector: '[data-tour="treatment-agenda"]', activateSelector: ".treatment-tab-agenda", title: "Fecha de tratamiento", content: "Completa fecha y hora programadas y el lugar del tratamiento. Confirma la convocatoria una vez revisados los participantes; la agenda confirmada queda en solo lectura." },
      { selector: '[data-tour="treatment-anomaly-evidence"]', activateSelector: ".treatment-tab-agenda", title: "Evidencias de las anomalías", content: "Consulta los archivos objetivos de las anomalías vinculadas para preparar el análisis. Estos documentos permiten revisar los hechos que dieron origen al tratamiento." },
      { selector: '[data-tour="treatment-method"]', activateSelector: ".treatment-tab-analysis", title: "Vista 2 — Método y detalle de análisis", content: "Selecciona 5 WHY, 6M o Sin definir y describe el análisis realizado. Documenta lo investigado y los factores que explican el desvío." },
      { selector: '[data-tour="treatment-method"]', activateSelector: ".treatment-tab-analysis", title: "Métodos de análisis", content: "5 Porqués pregunta repetidamente por qué ocurrió el problema hasta identificar su causa raíz. 6M ordena las posibles causas en Mano de obra, Máquina, Método, Materiales, Medición y Medio ambiente. Usa Sin definir si todavía no elegiste el enfoque." },
      { selector: '[data-tour="treatment-causes"]', activateSelector: ".treatment-tab-analysis", title: "Causas raíz encontradas", content: "Registra cada causa raíz identificada. Las acciones deberán vincularse a estas causas para explicar qué factor corrige cada una." },
      { selector: '[data-tour="treatment-actions"]', activateSelector: ".treatment-tab-analysis", title: "Acciones surgidas del tratamiento", content: "Crea cada acción con detalle, al menos una causa raíz asociada, responsable y fecha límite de ejecución. El responsable registra el avance y la evidencia desde Acciones." },
      { selector: '[data-tour="treatment-action-detail"]', activateSelector: ".treatment-tab-analysis", title: "Detalle de acciones", content: "Revisa las acciones registradas, sus responsables, fechas y estados. Las acciones deben estar completadas antes de validar la eficacia del tratamiento." },
      { selector: '[data-tour="treatment-effectiveness"]', activateSelector: ".treatment-tab-analysis", title: "Evaluación de eficacia", content: "Indica la fecha de validación y el responsable de medir la eficacia. Guarda el análisis y, cuando todas las acciones estén completas y se alcance esa fecha, el responsable registra el fundamento y resultado desde Validaciones." },
    ],
  },
  actions: {
    id: "actions",
    title: "Realizar acciones",
    description: "Consulta acciones asignadas, registra el avance y adjunta evidencia.",
    steps: [
      { selector: ".page-header", title: "Acciones", content: "Aquí se reúnen las acciones de Tratamientos y Observaciones visibles para tu perfil, en cualquier estado." },
      { selector: ".action-source-selector", title: "Origen de las acciones", content: "Usa los checks para mostrar u ocultar acciones de Tratamientos y Observaciones." },
      { selector: ".tabbed-filters", title: "Filtros", content: "Busca por tratamiento, anomalía, estado, fecha o responsable según los controles disponibles." },
      { selector: ".action-list-column", title: "Listado de acciones", content: "Selecciona una tarjeta para revisar su código, definición, responsable, fechas y estado. El recorrido mantiene la acción abierta mientras explica sus subsecciones." },
      { selector: ".action-detail-fixed > .section-head", title: "Acción seleccionada", content: "Aquí se identifica la acción y su origen: Tratamiento u Observación. Durante el recorrido el resto queda grisado y bloqueado; usa Siguiente y Anterior para consultar cada bloque." },
      { selector: ".action-detail-fixed > .key-grid", title: "Información de la acción", content: "Revisa el responsable, las fechas y la anomalía o tratamiento relacionado. Las acciones finalizadas quedan disponibles para consulta." },
      { selector: '[data-tour="action-evidence"]', title: "Evidencia de la acción", content: "Selecciona el archivo que respalda la ejecución y agrega una nota si corresponde. Debes cargar evidencia propia de esta acción para habilitar sus datos o su finalización." },
      { selector: '[data-tour="action-evidence"] > .section-head', title: "Cargar evidencia", content: "Seleccionar un archivo todavía no lo guarda. Pulsa Cargar evidencia para registrarlo y habilitar los datos. Esta operación por sí sola no completa ni finaliza la acción." },
      { selector: '[data-tour="action-status-history"]', title: "Notas de cambios de estado", content: "Cada cambio conserva su propia nota, el estado anterior y nuevo, la fecha y quién lo realizó. Consulta aquí el historial completo del avance." },
      { selector: '[data-tour="action-files"]', title: "Archivos cargados", content: "Aquí quedan listados los archivos de evidencia, sus fechas y notas. Puedes abrirlos para revisar el respaldo de la acción." },
      { selector: '[data-tour="action-data"]', title: "Datos de la acción", content: "Esta tarjeta permanece bloqueada hasta cargar evidencia. Los campos de definición se editan según tus permisos; el responsable registra el avance de su acción." },
      { selector: '[data-tour="action-state"]', title: "Cambiar el estado", content: "Desde Pendiente puedes pasar a En curso o directamente a Completada. Desde En curso solo puedes avanzar a Completada. No se permite retroceder; cancelar solo está disponible antes del primer cambio de estado, según las condiciones de la acción. Cada cambio exige su propia nota obligatoria de evidencia, que queda en el historial." },
      { selector: '[data-tour="action-state-note"]', title: "Nota del cambio de estado", content: "Al elegir un estado diferente aparece la nota obligatoria de evidencia del cambio. Explica el avance y guarda la acción; la nota quedará en el historial de estados." },
      { selector: '[data-tour="action-data"] .task-save-controls', title: "Guardar acción", content: "Confirma los cambios con Guardar acción. Si cambiaste el estado, completa su nota obligatoria antes de guardar." },
      { selector: '[data-tour="action-observation-completion"]', title: "Finalizar acción de Observación", content: "Después de cargar su evidencia, indica la fecha real de finalización y pulsa Marcar como finalizada. Todas las acciones de la observación deben estar completas para continuar con la eficacia en la fecha de validación." },
    ],
  },
  validation: {
    id: "validation",
    title: "Verificar eficacia",
    description: "Revisa validaciones de tratamientos y observaciones y registra el resultado de eficacia.",
    steps: [
      { selector: ".action-source-selector", title: "Origen de las validaciones", content: "Usa los checks para mostrar u ocultar las validaciones de tratamientos y de observaciones." },
      { selector: ".user-management-grid > section:first-child", title: "Validaciones visibles", content: "Selecciona el caso antes de iniciar el recorrido. TRT identifica tratamientos y OBS observaciones. Los casos bloqueados y realizados también se pueden consultar." },
      { selector: '[data-tour="validation-summary"]', title: "Validación seleccionada", content: "Revisa el código, título, origen y estado del caso abierto. El recorrido mantiene esta selección, enfoca cada subsección y deja el resto grisado y bloqueado." },
      { selector: '[data-tour="validation-dates"]', title: "Fecha y responsable", content: "No se puede validar antes de la fecha de validación, aunque las acciones ya estén completas. Solo el responsable designado registra la eficacia. Aquí también se consulta el resultado y la fecha de una validación realizada." },
      { selector: '[data-tour="validation-recorded-reason"]', title: "Fundamento registrado", content: "Este texto conserva la explicación del resultado de eficacia registrado. No debe confundirse con la evidencia de ejecución de cada acción." },
      { selector: '[data-tour="validation-conditions"]', title: "Condiciones para validar", content: "Revisa los requisitos del caso: acciones completas, fecha de validación alcanzada y demás condiciones informadas aquí. Si hay bloqueos, deben resolverse antes de registrar la eficacia; el recorrido no los omite." },
      { selector: '[data-tour="validation-permissions"]', title: "Permisos y campos bloqueados", content: "Consultar el caso no habilita su edición. Si no eres el responsable designado o faltan condiciones, los campos y la confirmación permanecen bloqueados." },
      { selector: '[data-tour="validation-completed"]', title: "Validación realizada", content: "Este caso se muestra en modo consulta. El recorrido no vuelve a habilitar ni modifica una validación ya realizada." },
      { selector: '[data-tour="validation-real-date"]', title: "Fecha de realización", content: "En observaciones indica cuándo realizaste la verificación. Este dato no reemplaza la fecha de validación ni permite validar anticipadamente." },
      { selector: '[data-tour="validation-result"]', title: "Resultado de eficacia", content: "Selecciona Eficaz si las acciones resolvieron el problema, o No eficaz si se necesita continuar con medidas correctivas. Evalúa los resultados, no solamente que las acciones estén completas." },
      { selector: '[data-tour="validation-reason"]', title: "Fundamento de eficacia obligatorio", content: "Explica por qué el resultado es Eficaz o No eficaz, indicando qué se verificó y qué se observó. Este campo es obligatorio tanto para tratamientos como para observaciones." },
      { selector: '[data-tour="validation-evidence"]', title: "Evidencia objetiva de eficacia", content: "Adjunta los archivos que respaldan la verificación: JPG, JPEG, PNG, PDF o TXT. Puedes seleccionar varios. Se guardan al registrar la validación; seleccionar archivos por sí solo no los carga ni confirma el resultado." },
      { selector: '[data-tour="validation-confirm"]', title: "Registrar validación", content: "Revisa resultado, fundamento y archivos antes de confirmar. Solo se permite registrar cuando se cumplen fecha, permisos y requisitos. Si el caso es eficaz, continúa con sus lecciones aprendidas; si no, debe continuar la gestión correctiva." },
    ],
  },
  inbox: {
    id: "inbox",
    title: "Bandeja y pendientes",
    description: "Revisa trabajo pendiente, avisos e historial de notificaciones.",
    steps: [
      { selector: ".page-header", title: "Bandeja", content: "La Bandeja concentra las comunicaciones y actividades relacionadas con tu usuario." },
      { selector: ".stats-grid", title: "Resumen", content: "Las tarjetas superiores muestran cantidades para ubicar rápidamente el trabajo actual." },
      { selector: ".inbox-tabs", title: "Secciones", content: "Cambia entre Pendientes, Avisos e Historial sin duplicar información." },
      { selector: ".notification-card", title: "Notificación", content: "Cada tarjeta describe el evento y ofrece las acciones disponibles, como abrir el contexto, marcar leído o confirmar participación." },
    ],
  },
  learnedLessons: {
    id: "learned-lessons",
    title: "Registrar lecciones aprendidas",
    description: "Documenta aprendizajes de tratamientos y observaciones eficaces y conoce sus respectivos pasos de cierre.",
    steps: [
      { selector: ".page-header", title: "Lecciones aprendidas", content: "Esta pantalla reúne tratamientos y observaciones validados como eficaces para documentar o consultar su aprendizaje." },
      { selector: ".treatment-tab-row", title: "Origen de la lección", content: "Antes de iniciar el recorrido elige Tratamientos u Observaciones. Cada origen tiene su propio flujo; el recorrido explica únicamente los bloques disponibles en el caso abierto." },
      { selector: ".tabbed-filters", title: "Buscar", content: "Utiliza los filtros para localizar el tratamiento o la anomalía correspondiente." },
      { selector: ".lessons-directory", title: "Listado de lecciones", content: "A la izquierda se listan los tratamientos u observaciones eficaces. Elegí una tarjeta para abrir una sola lección a la vez." },
      { selector: ".lesson-directory-card.active", title: "Estado del caso seleccionado", content: "Esta es la lección abierta a la derecha. Tratamientos muestra Pendiente de carga, Borrador, Lista para publicar o Publicada; Observaciones muestra Pendiente de carga o Registrada. La selección se mantiene durante el recorrido." },
      { selector: '[data-tour="lesson-treatment-summary"]', title: "Tratamiento: responsable y plazo", content: "Solo el responsable de eficacia completa el borrador. El sistema asigna automáticamente cinco días hábiles, de lunes a viernes, desde la validación eficaz para completar y enviar la lección. Consulta la fecha límite en el aviso de Bandeja. Aquí se informa su estado y cierre formal." },
      { selector: '[data-tour="lesson-observation-summary"]', title: "Observación: datos y responsable", content: "Revisa el código, la fecha de verificación eficaz, el responsable y la última carga. La gestión corresponde al responsable autorizado de la observación o al Administrador. Este flujo registra el aprendizaje sin los botones de envío y publicación de tratamientos." },
      { selector: '[data-tour="lesson-learning-choice"]', title: "¿Hubo aprendizaje?", content: "Debes elegir Sí o No. Si eliges Sí, se habilitan Qué se aprendió y Evidencia objetiva, y el aprendizaje es obligatorio. Si eliges No, debes justificar por qué no se aprendió. El recorrido no cambia esta respuesta para mostrar campos ocultos." },
      { selector: '[data-tour="lesson-learning-text"]', title: "¿Qué se aprendió?", content: "Describe de forma concreta qué aprendieron y cómo ayudará a evitar que el problema se repita. Este texto es obligatorio cuando hubo aprendizaje." },
      { selector: '[data-tour="lesson-evidence"]', title: "Evidencia objetiva del aprendizaje", content: "Adjunta los archivos que respaldan lo aprendido. Puedes seleccionar varios; se incorporan al pulsar Guardar cambios, no al seleccionarlos. Estos archivos corresponden a la lección, no reemplazan las evidencias de las acciones ni de eficacia." },
      { selector: '[data-tour="lesson-no-learning"]', title: "Motivo de no aprendizaje", content: "Si respondiste No, este fundamento es obligatorio. Explica por qué el caso no produjo un aprendizaje nuevo; no basta con dejar el campo vacío." },
      { selector: '[data-tour="lesson-procedure-choice"]', title: "¿Modifica procedimiento?", content: "Debes indicar Sí o No en ambos orígenes. Si eliges Sí, detalla obligatoriamente la modificación. En tratamientos, después de guardar se exige crear una acción derivada: su tarjeta bloquea el resto hasta crearla, aunque puedes consultar Ayuda." },
      { selector: '[data-tour="lesson-procedure-detail"]', title: "Detalle de la modificación", content: "Indica qué procedimiento cambia y en qué consiste el ajuste. Este detalle es obligatorio cuando respondiste que se modifica un procedimiento." },
      { selector: '[data-tour="lesson-files"]', title: "Evidencias guardadas", content: "Aquí se listan los archivos ya incorporados con su nombre y fecha. Fuera del recorrido puedes abrirlos para consultar el respaldo del aprendizaje." },
      { selector: '[data-tour="lesson-save"]', title: "Guardar borrador del tratamiento", content: "Guardar conserva una versión completa con fecha, autor y evidencias en el historial; no envía ni publica. Completa las respuestas y textos obligatorios. Si se modifica un procedimiento, continúa con la acción derivada requerida." },
      { selector: '[data-tour="lesson-observation-save"]', title: "Guardar aprendizaje de la observación", content: "Guarda las respuestas, fundamentos y archivos. Si la lección ya estaba registrada, se solicita confirmar su modificación. Este botón no inicia el flujo de publicación administrativa de tratamientos." },
      { selector: ".learned-lesson-derived-action", title: "Crear acción derivada", content: "Completa acción, descripción, responsable y fecha límite de realización y pulsa Crear acción derivada. Mientras falta crearla, el resto queda bloqueado salvo Ayuda. El recorrido solo explica la tarjeta; no crea la acción por ti." },
      { selector: '[data-tour="lesson-derived-list"]', title: "Acciones derivadas registradas", content: "Consulta el código, responsable, fecha límite y estado de cada acción derivada. Su ejecución se gestiona en Acciones y puede seguir pendiente tras publicar la lección." },
      { selector: '[data-tour="lesson-send"]', title: "Enviar para publicación", content: "Después de guardar y crear la acción derivada si corresponde, el responsable de eficacia envía la lección para revisión administrativa. Queda Lista para publicar y ya no se edita como borrador. Guardar por sí solo no cumple este paso." },
      { selector: '[data-tour="lesson-publish"]', title: "Publicación y cierre formal", content: "Solo el Administrador publica una lección Lista para publicar. Si modifica un procedimiento debe existir una acción derivada válida. La publicación consolida el historial, cierra formalmente el tratamiento, notifica a los involucrados y bloquea la edición." },
      { selector: ".learned-lesson-history > summary", title: "Historial de versiones", content: "Este desplegable permite consultar las versiones guardadas con fecha, autor, cambios y evidencias. Las anteriores no se reemplazan. Puedes abrirlo cuando termines el recorrido." },
    ],
  },
  treatmentTracking: {
    id: "treatment-tracking",
    title: "Seguimiento de tratamientos",
    description: "Consulta en modo lectura toda la trazabilidad del tratamiento.",
    steps: [
      { selector: ".page-header", title: "Seguimiento", content: "Esta vista permite auditar tratamientos sin modificar su información." },
      { selector: ".tabbed-filters", title: "Filtros", content: "Localiza procedimientos por código, usuario, proceso y los demás criterios disponibles." },
      { selector: ".treatment-list-panel", title: "Procedimientos", content: "Selecciona un tratamiento para cargar su detalle completo." },
      { selector: ".treatment-detail-panel", title: "Detalle solo lectura", content: "Consulta datos generales, usuarios, anomalías, convocados, causas, acciones, eficacia, evidencias e historial." },
    ],
  },
  indicators: {
    id: "indicators",
    title: "Consultar indicadores",
    description: "Conoce el catálogo y elige el análisis que necesitas consultar.",
    steps: [
      { selector: ".page-header", title: "Indicadores", content: "El catálogo reúne los dashboards disponibles para Administrador y Desarrollador." },
      ...[
        { key: "anomalies-treated", title: "Anomalías tratadas", content: "Consulta la gestión de los casos y sus estados." },
        { key: "treatments", title: "Tratamientos", content: "Analiza el avance de los tratamientos." },
        { key: "anomalies-by-process", title: "Anomalías por proceso", content: "Compara la distribución de anomalías entre procesos." },
        { key: "finding-classification", title: "Clasificación de hallazgos", content: "Analiza cómo se clasificaron los hallazgos." },
        { key: "repetition-pareto", title: "Repeticiones y Pareto", content: "Identifica los grupos con mayor recurrencia y su peso acumulado." },
        { key: "actions", title: "Acciones", content: "Consulta el cumplimiento de acciones de ambos circuitos." },
        { key: "effectiveness", title: "Eficacia", content: "Analiza verificaciones y resultados de eficacia." },
        { key: "affected-orders", title: "Órdenes afectadas", content: "Revisa órdenes y cantidades afectadas por anomalías." },
        { key: "learned-lessons", title: "Lecciones aprendidas", content: "Consulta aprendizajes registrados y modificaciones de procedimiento." },
      ].map((indicator) => ({ selector: `[data-tour="indicator-catalog-${indicator.key}"]`, title: indicator.title, content: `${indicator.content} La tarjeta informa la fecha que utiliza este análisis. Al terminar el recorrido, ábrela para consultar su tablero y su recorrido específico; aquí no se navega ni se cambian registros.` })),
    ],
  },
  indicatorDashboard: {
    id: "indicator-dashboard",
    title: "Consultar el tablero del indicador",
    description: "Recorre filtros, resultados, gráficos, criterios de cálculo y opciones de informe del indicador abierto.",
    steps: [
      { selector: ".page-header", title: "Indicador seleccionado", content: "El recorrido permanece en este indicador, enfoca cada subsección y grisa y bloquea el resto. La consulta está disponible para Administrador y Desarrollador; no cambia registros." },
      { selector: ".tabbed-filters-tabs", title: "Filtros del análisis", content: "Los filtros recalculan resultados, gráficos y datos de respaldo. El recorrido abre sus pestañas para explicarlas, sin cambiar los valores ni limpiar los filtros existentes." },
      { selector: ".tabbed-filter-control", activateSelector: '.tabbed-filter-tab[data-filter-id="period"]', title: "Período", content: "Selecciona Desde y Hasta para delimitar el análisis. El rango inicial va desde el inicio del año hasta hoy. La fecha usada depende de este indicador; consulta sus criterios de cálculo antes de comparar resultados." },
      { selector: ".tabbed-filter-control", activateSelector: '.tabbed-filter-tab[data-filter-id="process"]', title: "Proceso", content: "Limita el análisis a un proceso o consulta Todos los procesos. Cambiar un filtro vuelve a la primera página de los datos; el recorrido no cambia esta selección." },
      { selector: 'select[aria-label="Agrupacion de Pareto"]', activateSelector: '.tabbed-filter-tab[data-filter-id="grouping"]', title: "Agrupación de Pareto", content: "Solo en Repeticiones y Pareto puedes agrupar por proceso y tipo, proceso, tipo, origen, clasificación u orden afectada. Cambia la agrupación del análisis, no los registros originales." },
      { selector: ".tabbed-filter-clear", title: "Restablecer filtros", content: "Limpiar filtros restaura el período inicial, todos los procesos y la agrupación predeterminada. El recorrido no pulsa este botón para conservar tu consulta." },
      { selector: ".indicator-metrics-grid", title: "Resultados", content: "Las tarjetas resumen cantidades y porcentajes calculados para los filtros vigentes." },
      { selector: '[data-tour="indicator-trend"]', title: "Evolución mensual", content: "Revisa cómo cambia el resultado mes a mes dentro del período seleccionado. Las series visibles dependen del indicador; usa la leyenda y los criterios de cálculo para interpretarlas." },
      { selector: '[data-tour="indicator-breakdown"]', title: "Distribución del período", content: "Este gráfico muestra la composición del resultado. En Pareto ayuda a identificar los grupos principales y su participación acumulada. No confundir distribución con evolución mensual." },
      { selector: ".indicator-formula-panel", title: "Criterios de cálculo", content: "Aquí se explica qué se cuenta, qué fechas se usan y cómo se calculan los resultados de este indicador. Revisa estas reglas antes de interpretar porcentajes o compararlos con otros tableros." },
      { selector: ".indicator-data-table", title: "Datos de respaldo", content: "La tabla muestra los registros o grupos que sostienen el cálculo. Fuera del recorrido, los códigos con enlace permiten abrir el contexto del caso. Si no hay resultados para los filtros, se informa sin inventar datos." },
      { selector: ".pagination-controls", title: "Páginas de datos", content: "Recorre los datos de respaldo de veinte en veinte, manteniendo período, proceso y agrupación. La paginación de la tabla no cambia el alcance de las métricas y gráficos." },
      { selector: '[data-tour="indicator-export"]', title: "Exportar CSV", content: "Descarga los datos de respaldo del indicador con los filtros vigentes. El recorrido solo señala este botón: no inicia una descarga." },
      { selector: '[data-tour="indicator-report"]', title: "Enviar informe PDF", content: "Al terminar puedes abrir el envío de informe. Selecciona usuarios activos con correo habilitado y confirma los destinatarios antes de encolar. Se usan los filtros vigentes; el generador recibe copia si tiene correo habilitado. El recorrido no abre ni confirma un envío." },
    ],
  },
  affectedOrders: {
    id: "affected-orders",
    title: "Consultar órdenes afectadas",
    description: "Recorre filtros, totales, cantidades y trazabilidad de las órdenes vinculadas a anomalías.",
    steps: [
      { selector: ".page-header", title: "Órdenes afectadas", content: "Consulta consolidada para Administrador y Desarrollador. El recorrido mantiene esta pantalla, enfoca cada subsección y bloquea y grisa el resto. Aquí se consulta y exporta; no se editan órdenes ni anomalías." },
      { selector: ".tabbed-filters-tabs", title: "Filtros disponibles", content: "Combina filtros para localizar las afectaciones. El recorrido abre cada pestaña sin cambiar valores ni resultados. Cambiar un valor fuera del recorrido vuelve a la primera página." },
      ...[
        { key: "search", title: "Buscar", content: "Busca por tipo, número, anomalía o proceso." },
        { key: "type", title: "Tipo de orden", content: "Selecciona un tipo del catálogo o consulta Todos." },
        { key: "number", title: "Número de orden", content: "Busca una coincidencia parcial del número de orden." },
        { key: "anomaly", title: "Anomalía vinculada", content: "Busca por código o título de la anomalía relacionada." },
        { key: "process", title: "Proceso", content: "Filtra por el proceso relacionado o consulta Todos." },
        { key: "quantity", title: "Cantidad afectada", content: "Usa mínima y máxima para acotar la cantidad registrada en las afectaciones. Estas cantidades no son el total original de la orden." },
        { key: "status", title: "Estado de la anomalía", content: "Este filtro corresponde al estado del caso de calidad, no al estado de producción de la orden." },
        { key: "dates", title: "Fechas de detección", content: "Delimita Desde y Hasta según la fecha de detección de las anomalías, no la fecha de emisión de las órdenes." },
      ].map((filter) => ({ selector: ".tabbed-filter-control", activateSelector: `.tabbed-filter-tab[data-filter-id="${filter.key}"]`, title: filter.title, content: filter.content })),
      { selector: ".tabbed-filter-clear", title: "Limpiar filtros", content: "Este botón elimina los filtros aplicados y vuelve a la primera página con el orden predeterminado. El recorrido no lo pulsa, para conservar tu consulta." },
      { selector: '[data-tour="affected-orders-sort"]', title: "Ordenar resultados", content: "Ordena por fecha de detección, tipo, número, cantidad o proceso. Cambia la presentación del listado, no las cantidades ni los registros originales." },
      { selector: ".affected-orders-stats", title: "Totales de la consulta", content: "Órdenes diferentes cuenta combinaciones únicas de tipo y número. Registros cuenta afectaciones y Anomalías los casos involucrados; no son la misma medida. Cantidad total suma las cantidades registradas según los filtros, no solo la página visible." },
      { selector: ".affected-orders-breakdown", title: "Totales por tipo", content: "Consulta la cantidad de registros y piezas afectadas por cada tipo de orden dentro de los filtros vigentes." },
      { selector: ".affected-orders-table", title: "Listado de afectaciones", content: "Cada fila informa tipo, número, cantidad afectada, anomalía, proceso, fecha de detección y estado del caso. Una orden puede tener varias afectaciones; revisa sus vínculos antes de interpretar la suma como piezas únicas." },
      { selector: ".affected-orders-table tbody tr:first-child td:nth-child(4)", title: "Abrir la anomalía", content: "Fuera del recorrido, pulsa el código para consultar el caso, sus responsables, evidencias e historial. El recorrido no navega a otro caso ni pierde tus filtros." },
      { selector: ".pagination-controls", title: "Recorrer resultados", content: "El listado muestra veinte registros por página. Cambia de página sin perder los filtros; los totales corresponden a la consulta completa." },
      { selector: '[data-tour="affected-orders-export"]', title: "Exportar CSV", content: "Exporta las afectaciones según los filtros vigentes. El recorrido solo explica el botón, sin descargar archivos ni alterar registros." },
    ],
  },
  users: {
    id: "users",
    title: "Administrar usuarios",
    description: "Recorre el directorio, el formulario, los niveles y las credenciales provisorias.",
    steps: [
      { selector: ".user-sticky-shell", title: "Usuarios", content: "Desde el encabezado puedes iniciar un alta o acceder a la importación masiva." },
      { selector: ".tabbed-filters", title: "Buscar usuarios", content: "Busca por usuario, correo, nombre o legajo y decide si necesitas incluir inactivos." },
      { selector: ".directory-form-panel", title: "Formulario", content: "Crea o edita los datos personales, internos y de acceso del usuario." },
      { selector: '[name="access_level"]', title: "Nivel de acceso", content: "Selecciona el nivel correspondiente a las responsabilidades que tendrá la persona." },
      { selector: ".temporary-password-card", title: "Contraseña provisoria", content: "Puedes definir o generar una contraseña inicial. En el siguiente ingreso deberá reemplazarse por una clave personal segura." },
      { selector: ".user-checkbox-group", title: "Estado y correo", content: "Controla si el usuario está activo y si recibirá los correos de eventos configurados." },
      { selector: ".directory-panel", title: "Directorio", content: "Aquí se muestran las cuentas existentes y las acciones Editar o Eliminar disponibles." },
    ],
  },
  catalogs: {
    id: "catalogs",
    title: "Administrar catálogos",
    description: "Selecciona un maestro, busca registros y mantén sus datos operativos.",
    steps: [
      { selector: ".page-header", title: "Catálogo actual", content: "El encabezado identifica el maestro seleccionado y su finalidad en el sistema." },
      { selector: ".tabbed-filters", title: "Catálogo y filtros", content: "Cambia de maestro, busca por código o nombre y filtra por estado." },
      { selector: ".directory-form-panel", title: "Formulario", content: "Crea o edita código, nombre, orden, relaciones y estado activo." },
      { selector: ".directory-panel", title: "Directorio", content: "El listado se ordena por código para facilitar el control contra la documentación vigente." },
      { selector: ".pagination-controls", title: "Paginación", content: "Recorre el directorio completo manteniendo el catálogo y los filtros seleccionados." },
    ],
  },
};

export function getGuidedTour(pathname: string, access: { isAdmin: boolean; isManagement: boolean }) {
  if (pathname === "/dashboard/summary" && access.isAdmin) return TOURS.quickSummary;
  if (pathname === "/anomalies/new") return TOURS.newAnomaly;
  if (pathname === "/anomalies") return TOURS.anomalyTracking;
  if (pathname === "/anomalies/observations" || pathname === "/anomalies/immediate-actions") return TOURS.observations;
  if (pathname === "/treatments" && access.isManagement) return TOURS.treatments;
  if (pathname === "/actions/mine") return TOURS.actions;
  if (pathname === "/validation") return TOURS.validation;
  if (pathname === "/learned-lessons") return TOURS.learnedLessons;
  if (pathname === "/treatments/tracking") return TOURS.treatmentTracking;
  if (pathname === "/notifications/inbox") return TOURS.inbox;
  if (pathname === "/indicators" && access.isAdmin) return TOURS.indicators;
  if (pathname.startsWith("/indicators/") && access.isAdmin) return TOURS.indicatorDashboard;
  if (pathname === "/affected-orders" && access.isAdmin) return TOURS.affectedOrders;
  if (pathname === "/management/users" && access.isAdmin) return TOURS.users;
  if (pathname === "/management/catalogs" && access.isAdmin) return TOURS.catalogs;
  return null;
}
