export type GuidedTourStep = {
  selector: string;
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
      { selector: ".dashboard-summary-grid", title: "Tarjetas de resumen", content: "Cada tarjeta muestra el total de un proceso y su distribución por estados. Los registros históricos y terminales forman parte de los cálculos definidos." },
      { selector: ".dashboard-summary-card", title: "Leer una tarjeta", content: "Revisa el total principal y el desglose compacto. Usa Ver detalle por usuario para identificar la distribución individual y el total general." },
      { selector: ".dashboard-detail-toggle", title: "Detalle por usuario y seguimiento", content: "Al finalizar el recorrido, selecciona Ver detalle por usuario para comparar totales y estados de cada persona. Si necesitas investigar una anomalía concreta, abre Seguimiento de anomalías desde el panel lateral y consulta allí su detalle, responsable e historial." },
    ],
  },
  newAnomaly: {
    id: "new-anomaly",
    title: "Registrar una anomalía",
    description: "Recorre la carga inicial, el contexto y la confirmación del registro.",
    steps: [
      { selector: ".form-hero", title: "Nueva anomalía", content: "Aquí comienza el registro. El código visible se reserva automáticamente y acompañará al caso durante todo su ciclo." },
      { selector: ".anomaly-form .form-section:nth-of-type(1)", title: "Paso 1 — Datos de inicio", content: "Completa los procesos relacionados, la fecha de detección y el tipo de anomalía. Los campos marcados son obligatorios." },
      { selector: '[name="area"]', title: "Elaborado por", content: "Selecciona el área o proceso donde se origina el registro." },
      { selector: '[name="imputed_area"]', title: "Asignado a", content: "Selecciona el área o proceso relacionado con la anomalía." },
      { selector: '[name="anomaly_type"]', title: "Tipo de anomalía", content: "Elige el tipo de desvío que mejor representa el hallazgo." },
      { selector: ".anomaly-form .form-section:nth-of-type(2)", title: "Paso 2 — Contexto", content: "Describe el hecho con claridad y agrega órdenes afectadas o evidencias cuando correspondan." },
      { selector: ".affected-orders-editor", title: "Órdenes afectadas", content: "Esta sección es opcional. Cada fila utilizada requiere tipo, número y cantidad mayor que cero." },
      { selector: '[name="description"]', title: "Observación", content: "Explica qué ocurrió, dónde se detectó y cualquier dato necesario para comprender el hallazgo." },
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
      { selector: ".anomaly-classification-control", title: "Revisión de hallazgos", content: "Los perfiles globales utilizan este control para seleccionar el criterio, asignar responsable y confirmar el circuito correspondiente." },
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
      { selector: ".treatment-layout > article:last-child", title: "Detalle operativo", content: "El panel derecho muestra el paso disponible: carga de Observación, acciones tomadas o verificación de eficacia." },
      { selector: ".treatment-layout form", title: "Formulario actual", content: "Completa los campos obligatorios y confirma. Las siguientes etapas se habilitan según el avance guardado." },
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
      { selector: ".treatment-layout > article:last-child", title: "Panel de gestión", content: "Aquí se encuentran las vistas Convocatoria y Análisis del tratamiento seleccionado." },
      { selector: ".treatment-tab-row", title: "Cambiar de vista", content: "Convocatoria organiza agenda y participantes. Análisis reúne método, evidencias, causas, acciones y eficacia." },
      { selector: ".treatment-tab-content", title: "Contenido de la vista", content: "Completa el contenido visible en orden. El sistema conserva el avance y aplica los bloqueos correspondientes." },
    ],
  },
  actions: {
    id: "actions",
    title: "Realizar acciones",
    description: "Consulta acciones asignadas, registra el avance y adjunta evidencia.",
    steps: [
      { selector: ".page-header", title: "Acciones", content: "Aquí se muestran las acciones de tratamientos asignadas al usuario de la sesión." },
      { selector: ".tabbed-filters", title: "Filtros", content: "Busca por tratamiento, anomalía, estado, fecha o usuario según los controles disponibles." },
      { selector: ".action-card", title: "Trabajo pendiente", content: "Selecciona una acción del listado y revisa su definición antes de actualizarla." },
      { selector: ".action-detail-fixed form", title: "Detalle y estado", content: "Cambia el estado según el avance y registra la nota requerida para mantener la trazabilidad." },
      { selector: ".action-detail-fixed section.form-section", title: "Evidencias", content: "Adjunta archivos y notas que demuestren la ejecución de la acción." },
      { selector: ".completed-disclosure", title: "Acciones completadas", content: "El historial de completadas se mantiene separado del trabajo pendiente." },
    ],
  },
  validation: {
    id: "validation",
    title: "Verificar eficacia",
    description: "Revisa el tratamiento asignado y registra el resultado de eficacia.",
    steps: [
      { selector: ".user-management-grid > section:first-child", title: "Tratamientos disponibles", content: "Selecciona el tratamiento que debes verificar. Solo aparecen casos visibles para tu usuario." },
      { selector: ".user-management-grid > section:last-child", title: "Detalle de validación", content: "Revisa fechas, responsable, resultado actual y toda condición informada por el sistema." },
      { selector: ".user-management-grid > section:last-child .panel.warning", title: "Condiciones pendientes", content: "Si existen bloqueos, esta tarjeta indica qué debe completarse antes de validar." },
      { selector: ".user-management-grid > section:last-child .form-grid", title: "Resultado", content: "Selecciona Eficaz o No eficaz y documenta la observación que justifica tu decisión." },
      { selector: ".user-management-grid > section:last-child .form-actions", title: "Confirmar", content: "Registra la validación únicamente después de revisar las acciones y sus evidencias." },
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
    description: "Documenta el aprendizaje obtenido de tratamientos eficaces.",
    steps: [
      { selector: ".page-header", title: "Lecciones aprendidas", content: "Esta pantalla reúne tratamientos eficaces disponibles para documentar o consultar su aprendizaje." },
      { selector: ".tabbed-filters", title: "Buscar", content: "Utiliza los filtros para localizar el tratamiento o la anomalía correspondiente." },
      { selector: ".learned-lesson-card", title: "Tratamiento eficaz", content: "Cada tarjeta resume el tratamiento y muestra la información de aprendizaje guardada." },
      { selector: ".learned-lesson-form", title: "Documentar aprendizaje", content: "Indica si hubo aprendizaje, describe el resultado, informa cambios de procedimiento y adjunta evidencia cuando corresponda." },
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
    description: "Selecciona un indicador y utiliza sus filtros, gráficos, datos e informes.",
    steps: [
      { selector: ".page-header", title: "Indicadores", content: "El catálogo reúne los dashboards disponibles para Administrador y Desarrollador." },
      { selector: ".indicator-catalog-grid", title: "Seleccionar indicador", content: "Cada tarjeta abre un análisis específico del Sistema de Gestión de Calidad." },
      { selector: ".inline-filter-fields", title: "Período y proceso", content: "En el dashboard, aplica fechas y proceso para recalcular métricas, gráficos y detalle." },
      { selector: ".indicator-metrics-grid", title: "Resultados", content: "Las tarjetas resumen cantidades y porcentajes calculados para los filtros vigentes." },
      { selector: ".indicator-dashboard-grid", title: "Gráficos", content: "Consulta evolución mensual y distribución del indicador." },
      { selector: ".indicator-data-table", title: "Datos de respaldo", content: "La tabla permite revisar los registros que sostienen el resultado calculado." },
      { selector: ".page-header .form-actions", title: "Exportar e informar", content: "Exporta el CSV filtrado o envía el informe PDF a usuarios habilitados." },
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
  if (pathname === "/learned-lessons" && access.isManagement) return TOURS.learnedLessons;
  if (pathname === "/treatments/tracking") return TOURS.treatmentTracking;
  if (pathname === "/notifications/inbox") return TOURS.inbox;
  if ((pathname === "/indicators" || pathname.startsWith("/indicators/")) && access.isAdmin) return TOURS.indicators;
  if (pathname === "/management/users" && access.isAdmin) return TOURS.users;
  if (pathname === "/management/catalogs" && access.isAdmin) return TOURS.catalogs;
  return null;
}
