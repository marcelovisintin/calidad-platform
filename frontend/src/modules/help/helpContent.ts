export type HelpAudience = "all" | "management" | "admin";

export type HelpSection = {
  title: string;
  paragraphs?: string[];
  bullets?: string[];
  steps?: string[];
  note?: string;
};

export type HelpTopic = {
  id: string;
  category: string;
  title: string;
  summary: string;
  audience: HelpAudience;
  keywords: string[];
  route?: string;
  routeLabel?: string;
  quick?: boolean;
  sections: HelpSection[];
  related: string[];
};

export const HELP_CATEGORY_ORDER = [
  "Primeros pasos",
  "Anomalías y hallazgos",
  "Tratamientos y mejora",
  "Seguimiento personal",
  "Análisis y control",
  "Administración",
];

export const HELP_TOPICS: HelpTopic[] = [
  {
    id: "orientarse-en-el-sistema",
    category: "Primeros pasos",
    title: "Ingresar y orientarse en el sistema",
    summary: "Conoce la pantalla inicial, el menú lateral, el encabezado y el cierre de sesión.",
    audience: "all",
    keywords: ["inicio", "panel", "menu", "navegacion", "sesion", "ingresar"],
    quick: true,
    sections: [
      {
        title: "Pantalla inicial",
        paragraphs: [
          "Administrador y Desarrollador ingresan al Panel principal. Usuario activo y Mando medio activo comienzan en Nueva anomalía para facilitar el registro operativo.",
          "El menú lateral muestra únicamente las secciones habilitadas para el nivel del usuario. En pantallas pequeñas se abre desde el botón Menú del encabezado.",
        ],
      },
      {
        title: "Elementos de navegación",
        bullets: [
          "Volver: regresa a la pantalla anterior; si no existe historial, lleva a la pantalla inicial correspondiente.",
          "Título superior: identifica la sección actual.",
          "Usuario: muestra la persona que tiene la sesión abierta.",
          "Cerrar sesión: finaliza el acceso actual y vuelve al ingreso.",
        ],
      },
      {
        title: "Recomendación de uso",
        paragraphs: [
          "Cada persona debe trabajar con su propia sesión. Si se prueban dos usuarios en el mismo equipo, utiliza una ventana de incógnito para la segunda cuenta.",
        ],
      },
    ],
    related: ["cambiar-contrasena", "usar-bandeja", "registrar-anomalia"],
  },
  {
    id: "cambiar-contrasena",
    category: "Primeros pasos",
    title: "Primer ingreso y cambio de contraseña",
    summary: "Utiliza la contraseña provisoria y define una clave personal segura.",
    audience: "all",
    keywords: ["clave", "password", "credencial", "provisoria", "primer ingreso"],
    sections: [
      {
        title: "Primer ingreso",
        steps: [
          "Escribe el usuario o correo informado por el Administrador.",
          "Ingresa la contraseña provisoria.",
          "Cuando el sistema lo solicite, escribe nuevamente la clave actual.",
          "Define y confirma una contraseña personal.",
        ],
      },
      {
        title: "Requisitos de la contraseña personal",
        bullets: [
          "Mínimo de 8 caracteres.",
          "Al menos una mayúscula y una minúscula.",
          "Al menos un número y un carácter especial.",
          "No debe coincidir con el usuario o el correo ni ser una contraseña común.",
        ],
      },
      {
        title: "Contraseña provisoria renovada",
        paragraphs: [
          "Si el Administrador restablece la contraseña, el procedimiento vuelve a ser el mismo: ingresar con la provisoria y reemplazarla por una contraseña personal.",
        ],
      },
    ],
    related: ["orientarse-en-el-sistema", "administrar-usuarios"],
  },
  {
    id: "registrar-anomalia",
    category: "Anomalías y hallazgos",
    title: "Registrar una nueva anomalía",
    summary: "Carga el hallazgo, su contexto, órdenes afectadas y evidencias desde planta.",
    audience: "all",
    keywords: ["nueva", "anomalia", "registrar", "evidencia", "adjunto", "orden afectada"],
    route: "/anomalies/new",
    routeLabel: "Ir a Nueva anomalía",
    quick: true,
    sections: [
      {
        title: "Antes de comenzar",
        paragraphs: [
          "El sistema reserva automáticamente un código visible. Completa el registro mientras la reserva está vigente; si vence o falla, utiliza Reintentar reserva.",
        ],
      },
      {
        title: "Paso 1 — Datos de inicio",
        bullets: [
          "Fecha: día en que se detectó el hecho.",
          "Elaborado por: área o proceso donde se origina el registro.",
          "Asignado a: área o proceso relacionado con la anomalía.",
          "Tipo de anomalía: defecto, desvío o evento correspondiente.",
          "Título: identificación breve y concreta.",
        ],
      },
      {
        title: "Paso 2 — Contexto",
        bullets: [
          "Observación: describe qué ocurrió, dónde y cómo se detectó.",
          "Órdenes afectadas: son opcionales. Si agregas una fila, completa tipo, número y cantidad entera mayor que cero.",
          "No repitas la misma combinación de tipo y número de orden.",
          "Evidencias: puedes adjuntar fotografías y documentos permitidos.",
        ],
      },
      {
        title: "Confirmar",
        paragraphs: [
          "Al confirmar se crea la anomalía en estado Registrada, se registra al usuario generador y queda disponible para seguimiento. Si tu usuario tiene correo habilitado, puedes recibir la confirmación correspondiente.",
        ],
        note: "Si algún adjunto no logra cargarse, revisa el mensaje final: la anomalía puede haberse registrado correctamente aunque una evidencia haya fallado.",
      },
    ],
    related: ["consultar-anomalias", "ordenes-afectadas", "usar-bandeja"],
  },
  {
    id: "consultar-anomalias",
    category: "Anomalías y hallazgos",
    title: "Consultar y seguir anomalías",
    summary: "Busca casos, revisa su estado y abre la trazabilidad completa.",
    audience: "all",
    keywords: ["seguimiento", "buscar", "estado", "detalle", "historial", "trazabilidad"],
    route: "/anomalies",
    routeLabel: "Ir a Seguimiento de anomalías",
    quick: true,
    sections: [
      {
        title: "Qué muestra",
        paragraphs: [
          "El listado reúne las anomalías que el usuario puede consultar según su nivel y relación con cada caso. Permite localizar registros y abrir su detalle.",
        ],
      },
      {
        title: "Cómo buscar",
        bullets: [
          "Utiliza el texto libre para buscar por los datos mostrados en el listado.",
          "Combina los filtros disponibles para reducir resultados.",
          "Limpia los filtros para recuperar el listado completo de tu alcance.",
        ],
      },
      {
        title: "Detalle de anomalía",
        bullets: [
          "Código, fecha, título, descripción y procesos relacionados.",
          "Clasificación y responsable, cuando ya fueron definidos.",
          "Órdenes y evidencias vinculadas.",
          "Etapa, estado, historial y relaciones con observaciones o tratamientos.",
        ],
      },
    ],
    related: ["registrar-anomalia", "clasificar-hallazgo", "gestionar-observacion", "gestionar-tratamiento"],
  },
  {
    id: "clasificar-hallazgo",
    category: "Anomalías y hallazgos",
    title: "Revisar y clasificar un hallazgo",
    summary: "Define el criterio, el responsable y el circuito que seguirá la anomalía.",
    audience: "admin",
    keywords: ["clasificar", "revision", "hallazgo", "responsable", "invalida", "no conformidad", "observacion"],
    route: "/anomalies",
    routeLabel: "Ir a Seguimiento de anomalías",
    quick: true,
    sections: [
      {
        title: "Responsabilidad",
        paragraphs: [
          "La Revisión de hallazgos corresponde a Administrador o Desarrollador. El criterio seleccionado determina si debe asignarse un responsable o si el hallazgo se cierra como inválido.",
        ],
      },
      {
        title: "Clasificar",
        steps: [
          "Abre la anomalía pendiente de revisión.",
          "Selecciona el criterio aplicable.",
          "Si el criterio lo requiere, elige un responsable activo de la lista habilitada.",
          "Completa el motivo cuando el criterio cierre el hallazgo como inválido.",
          "Confirma la revisión.",
        ],
      },
      {
        title: "Resultado",
        bullets: [
          "Observación: queda disponible en el módulo Observaciones.",
          "No conformidad: se define responsable único y se conforma el tratamiento.",
          "Inválida: se cierra con el motivo registrado y se informa al generador.",
        ],
      },
      {
        title: "No conformidad y anomalías relacionadas",
        paragraphs: [
          "Antes de confirmar el tratamiento, Calidad puede seleccionar otras no conformidades u Observaciones TRT elegibles que todavía no integren un tratamiento. La composición queda bloqueada para el responsable asignado.",
        ],
      },
    ],
    related: ["consultar-anomalias", "gestionar-observacion", "gestionar-tratamiento"],
  },
  {
    id: "gestionar-observacion",
    category: "Anomalías y hallazgos",
    title: "Gestionar una Observación",
    summary: "Resuelve una observación directamente o derívala al circuito de tratamiento.",
    audience: "management",
    keywords: ["observacion", "trt", "acciones tomadas", "eficacia", "responsable"],
    route: "/anomalies/observations",
    routeLabel: "Ir a Observaciones",
    quick: true,
    sections: [
      {
        title: "Elegir el camino",
        paragraphs: [
          "La Observación puede resolverse mediante acciones directas o marcarse como Observación TRT para incorporarla posteriormente a un tratamiento. La decisión TRT debe tomarse antes de confirmar acciones.",
        ],
      },
      {
        title: "Resolución directa",
        steps: [
          "Completa la observación o descripción del tratamiento y las fechas solicitadas.",
          "Registra las acciones tomadas, su fecha de realización y la fecha prevista para verificar eficacia.",
          "Adjunta evidencia cuando corresponda.",
          "Espera la fecha y la asignación de verificación.",
        ],
      },
      {
        title: "Observación TRT",
        paragraphs: [
          "Marca Clasificar como Observación TRT y confirma antes de registrar acciones directas. La anomalía conserva su clasificación de Observación y queda elegible para que Calidad la asocie a un tratamiento.",
        ],
      },
      {
        title: "Verificación",
        paragraphs: [
          "El responsable de eficacia asignado registra el resultado. Si es eficaz, la anomalía se cierra. Si no es eficaz, vuelve al trabajo de acciones para continuar la mejora.",
        ],
      },
    ],
    related: ["clasificar-hallazgo", "ejecutar-acciones", "verificar-eficacia"],
  },
  {
    id: "gestionar-tratamiento",
    category: "Tratamientos y mejora",
    title: "Gestionar un tratamiento",
    summary: "Programa la convocatoria, analiza causas, define acciones y prepara la eficacia.",
    audience: "management",
    keywords: ["tratamiento", "convocatoria", "agenda", "causa raiz", "metodo", "acciones"],
    route: "/treatments",
    routeLabel: "Ir a Tratamientos",
    quick: true,
    sections: [
      {
        title: "Quién puede gestionarlo",
        paragraphs: [
          "El Mando medio activo designado como responsable único gestiona el tratamiento. Administrador y Desarrollador pueden gestionarlo de forma global. Los demás usuarios relacionados lo consultan o actúan solo en las tareas que les fueron asignadas.",
        ],
      },
      {
        title: "Vista 1 — Convocatoria",
        steps: [
          "Revisa las anomalías asociadas por Calidad.",
          "Define fecha y hora programada y, si corresponde, el lugar.",
          "Agrega todos los usuarios convocados necesarios.",
          "Pulsa Guardar agenda y confirma la pregunta de seguridad.",
        ],
        note: "Después de confirmar se bloquean la agenda y los convocados, y se generan los avisos de convocatoria.",
      },
      {
        title: "Vista 2 — Análisis",
        bullets: [
          "Selecciona el método de análisis utilizado.",
          "Documenta las observaciones del análisis.",
          "Registra una o más causas raíz.",
          "Adjunta evidencias del tratamiento cuando corresponda.",
          "Crea las acciones surgidas del tratamiento y vincúlalas con sus causas.",
          "Asigna fecha y responsable para la evaluación de eficacia.",
        ],
      },
      {
        title: "Preparar la validación",
        paragraphs: [
          "Para habilitar la eficacia deben existir una fecha programada ya transcurrida, al menos una causa raíz, fecha y responsable de eficacia, y todas las acciones del tratamiento deben estar completadas.",
        ],
      },
    ],
    related: ["ejecutar-acciones", "verificar-eficacia", "consultar-tratamientos", "registrar-leccion"],
  },
  {
    id: "ejecutar-acciones",
    category: "Tratamientos y mejora",
    title: "Realizar acciones asignadas",
    summary: "Consulta tus acciones, actualiza su avance y registra la evidencia de ejecución.",
    audience: "all",
    keywords: ["acciones", "tareas", "asignada", "completar", "evidencia", "fecha"],
    route: "/actions/mine",
    routeLabel: "Ir a Acciones",
    quick: true,
    sections: [
      {
        title: "Qué acciones aparecen",
        paragraphs: [
          "La pantalla muestra las acciones de tratamientos asignadas al usuario de la sesión. Los filtros permiten localizar por tratamiento, anomalía, estado y otros datos disponibles.",
        ],
      },
      {
        title: "Actualizar una acción",
        steps: [
          "Abre la acción asignada.",
          "Revisa descripción, causa relacionada y fecha prevista.",
          "Cambia el estado según el avance.",
          "Registra el comentario solicitado para dejar trazabilidad.",
          "Carga evidencia cuando corresponda y confirma.",
        ],
      },
      {
        title: "Completadas",
        paragraphs: [
          "Las acciones finalizadas se muestran separadas de las pendientes para conservar el historial sin mezclarlas con el trabajo actual.",
        ],
      },
    ],
    related: ["gestionar-tratamiento", "verificar-eficacia", "usar-bandeja"],
  },
  {
    id: "verificar-eficacia",
    category: "Tratamientos y mejora",
    title: "Verificar la eficacia",
    summary: "Evalúa el resultado del tratamiento u observación cuando fuiste designado responsable.",
    audience: "all",
    keywords: ["validacion", "eficacia", "eficaz", "no eficaz", "verificar", "cerrar"],
    route: "/validation",
    routeLabel: "Ir a Validaciones",
    quick: true,
    sections: [
      {
        title: "Responsabilidad",
        paragraphs: [
          "Solo el usuario específicamente asignado a la evaluación puede confirmar el resultado. La validación aparece cuando el caso reúne las condiciones necesarias.",
        ],
      },
      {
        title: "Cómo validar",
        steps: [
          "Abre la validación asignada.",
          "Revisa el tratamiento, las causas, las acciones y sus evidencias.",
          "Selecciona Eficaz o No eficaz.",
          "Registra la observación que justifica el resultado.",
          "Confirma la evaluación.",
        ],
      },
      {
        title: "Resultado",
        bullets: [
          "Eficaz: completa el tratamiento y cierra las anomalías vinculadas; en una Observación directa, cierra la anomalía.",
          "No eficaz: devuelve el caso al trabajo para que se definan o ejecuten nuevas acciones.",
        ],
      },
    ],
    related: ["ejecutar-acciones", "gestionar-tratamiento", "registrar-leccion"],
  },
  {
    id: "registrar-leccion",
    category: "Tratamientos y mejora",
    title: "Registrar una lección aprendida",
    summary: "Documenta el aprendizaje obtenido después de un tratamiento eficaz.",
    audience: "management",
    keywords: ["leccion", "aprendida", "procedimiento", "estandarizacion", "evidencia"],
    route: "/learned-lessons",
    routeLabel: "Ir a Lecciones aprendidas",
    sections: [
      {
        title: "Cuándo se registra",
        paragraphs: [
          "La lección se habilita para tratamientos completados con resultado eficaz. El responsable del tratamiento o un perfil global puede guardar la información.",
        ],
      },
      {
        title: "Campos principales",
        bullets: [
          "Indica si existe una lección aprendida.",
          "Si existe, describe el aprendizaje; si no, explica el motivo.",
          "Indica si fue necesario modificar un procedimiento.",
          "Si hubo modificación, registra las observaciones correspondientes.",
          "Adjunta evidencia cuando resulte útil.",
        ],
      },
      {
        title: "Resultado",
        paragraphs: [
          "El aprendizaje queda relacionado con el tratamiento y disponible para consulta y seguimiento. La primera publicación genera las notificaciones configuradas.",
        ],
      },
    ],
    related: ["gestionar-tratamiento", "verificar-eficacia", "consultar-tratamientos"],
  },
  {
    id: "consultar-tratamientos",
    category: "Seguimiento personal",
    title: "Consultar el seguimiento de tratamientos",
    summary: "Revisa en modo consulta la convocatoria, causas, acciones, eficacia e historial.",
    audience: "all",
    keywords: ["seguimiento", "tratamiento", "historico", "auditar", "consulta"],
    route: "/treatments/tracking",
    routeLabel: "Ir a Seguimiento de tratamientos",
    sections: [
      {
        title: "Objetivo",
        paragraphs: [
          "Esta sección ofrece una vista de consulta para seguir el tratamiento sin modificarlo. La información disponible depende de la relación del usuario con el caso.",
        ],
      },
      {
        title: "Filtros",
        bullets: ["Código de tratamiento.", "Usuario relacionado.", "Proceso o área.", "Otros criterios disponibles en la pantalla."],
      },
      {
        title: "Información consultable",
        bullets: [
          "Datos generales y anomalías incluidas.",
          "Responsable y usuarios convocados.",
          "Causas raíz y acciones.",
          "Evaluación de eficacia y evidencias.",
          "Historial y eventos de trazabilidad mostrados.",
        ],
      },
    ],
    related: ["gestionar-tratamiento", "ejecutar-acciones", "usar-bandeja"],
  },
  {
    id: "usar-bandeja",
    category: "Seguimiento personal",
    title: "Usar la Bandeja y los pendientes",
    summary: "Reúne avisos, trabajo pendiente, participaciones e historial personal.",
    audience: "all",
    keywords: ["bandeja", "pendiente", "aviso", "notificacion", "historial", "correo"],
    route: "/notifications/inbox",
    routeLabel: "Ir a Bandeja",
    quick: true,
    sections: [
      {
        title: "Pestañas",
        bullets: [
          "Pendientes: actividades que requieren atención del usuario.",
          "Avisos: comunicaciones informativas del sistema.",
          "Historial: notificaciones ya gestionadas o leídas.",
        ],
      },
      {
        title: "Acciones disponibles",
        paragraphs: [
          "Abre el contexto de una notificación para ir al registro relacionado. La apertura actualiza su lectura. Algunas participaciones permiten además confirmar que fueron vistas.",
        ],
      },
      {
        title: "Bandeja y correo",
        paragraphs: [
          "La Bandeja funciona aunque el usuario no tenga habilitado el correo. La casilla Notificación por correo controla únicamente el envío por email de los eventos configurados.",
        ],
      },
    ],
    related: ["orientarse-en-el-sistema", "ejecutar-acciones", "consultar-anomalias"],
  },
  {
    id: "consultar-indicadores",
    category: "Análisis y control",
    title: "Consultar indicadores",
    summary: "Analiza resultados, aplica filtros, exporta CSV y envía informes por correo.",
    audience: "admin",
    keywords: ["indicadores", "dashboard", "grafico", "csv", "informe", "pdf", "correo"],
    route: "/indicators",
    routeLabel: "Ir a Indicadores",
    sections: [
      {
        title: "Indicadores disponibles",
        bullets: [
          "Anomalías generadas y tratadas.",
          "Tratamientos creados y completados.",
          "Anomalías por proceso.",
          "Clasificación de hallazgos y Pareto de repetición.",
          "Acciones, eficacia, órdenes afectadas y lecciones aprendidas.",
        ],
      },
      {
        title: "Analizar",
        steps: [
          "Selecciona una tarjeta de indicador.",
          "Define el período y los filtros disponibles.",
          "Revisa totalizadores, porcentajes, gráficos y detalle.",
          "Ajusta los filtros para comparar el conjunto requerido.",
        ],
      },
      {
        title: "Exportar o informar",
        bullets: [
          "Exportar CSV descarga el detalle completo correspondiente a los filtros aplicados.",
          "Enviar informe genera un PDF temporal y lo envía a uno o más usuarios activos con correo habilitado.",
          "El informe enviado queda registrado en la auditoría de reportes.",
        ],
      },
    ],
    related: ["ordenes-afectadas", "consultar-anomalias", "consultar-tratamientos"],
  },
  {
    id: "ordenes-afectadas",
    category: "Análisis y control",
    title: "Analizar órdenes afectadas",
    summary: "Consulta órdenes vinculadas a anomalías y totaliza registros, casos y cantidades.",
    audience: "admin",
    keywords: ["orden", "op", "of", "om", "cantidad", "piezas", "totalizador"],
    route: "/affected-orders",
    routeLabel: "Ir a Órdenes afectadas",
    sections: [
      {
        title: "Búsqueda y filtros",
        bullets: [
          "Texto, tipo y número de orden.",
          "Anomalía, área o proceso y estado.",
          "Cantidad mínima o máxima.",
          "Rango de fechas y ordenamiento.",
        ],
      },
      {
        title: "Totalizadores",
        bullets: [
          "Órdenes únicas.",
          "Registros de afectación.",
          "Anomalías involucradas.",
          "Cantidad total de piezas o productos.",
          "Desglose por tipo de orden.",
        ],
      },
      {
        title: "Exportación",
        paragraphs: ["El CSV conserva los filtros aplicados y permite trabajar el detalle en una planilla."],
      },
    ],
    related: ["registrar-anomalia", "consultar-indicadores"],
  },
  {
    id: "administrar-usuarios",
    category: "Administración",
    title: "Administrar usuarios",
    summary: "Crea cuentas, asigna nivel, restablece credenciales y configura el correo.",
    audience: "admin",
    keywords: ["usuario", "alta", "editar", "nivel", "correo", "notificacion", "contraseña"],
    route: "/management/users",
    routeLabel: "Ir a Usuarios",
    sections: [
      {
        title: "Directorio",
        paragraphs: [
          "El listado muestra usuarios activos por defecto, permite incluir inactivos y pagina 30 registros. La búsqueda ayuda a localizar por los datos personales mostrados.",
        ],
      },
      {
        title: "Alta y edición",
        bullets: [
          "Completa usuario, correo, nombre, apellido y los datos internos requeridos.",
          "Asigna el nivel de acceso y el sector descriptivo.",
          "Activa o desactiva Notificación por correo según corresponda.",
          "Define una contraseña provisoria de al menos 8 caracteres o deja que el sistema genere una.",
          "Entrega la provisoria de forma segura: se muestra para su comunicación controlada.",
        ],
      },
      {
        title: "Restablecer acceso",
        paragraphs: [
          "Al cargar una nueva contraseña provisoria se obliga al usuario a reemplazarla en el siguiente ingreso.",
        ],
      },
      {
        title: "Conservar historial",
        paragraphs: [
          "Para una persona que ya tiene registros asociados, utiliza la desactivación en lugar de eliminarla. Así se conserva la trazabilidad histórica.",
        ],
      },
    ],
    related: ["cambiar-contrasena", "importar-usuarios", "configurar-alcances"],
  },
  {
    id: "importar-usuarios",
    category: "Administración",
    title: "Importar usuarios desde una planilla",
    summary: "Previsualiza un CSV o Excel y crea o actualiza cuentas de forma masiva.",
    audience: "admin",
    keywords: ["importar", "excel", "csv", "masivo", "usuarios", "credenciales"],
    route: "/management/users/import",
    routeLabel: "Ir a Importación de usuarios",
    sections: [
      {
        title: "Preparar el archivo",
        paragraphs: [
          "Utiliza las columnas admitidas para legajo, nombre, apellido, correo, usuario y celular. Revisa duplicados y datos faltantes antes de confirmar.",
        ],
      },
      {
        title: "Proceso",
        steps: [
          "Selecciona el archivo CSV o XLSX.",
          "Elige el modo: crear, actualizar o crear/actualizar.",
          "Ejecuta la vista previa.",
          "Revisa filas válidas, advertencias, errores y duplicados.",
          "Confirma la importación.",
          "Descarga y resguarda el informe confidencial de credenciales cuando se generen usuarios nuevos.",
        ],
      },
    ],
    related: ["administrar-usuarios", "cambiar-contrasena"],
  },
  {
    id: "configurar-alcances",
    category: "Administración",
    title: "Configurar alcances de usuario",
    summary: "Consulta el nivel y habilita permisos específicos disponibles para una persona.",
    audience: "admin",
    keywords: ["alcance", "permiso", "nivel", "checklist", "habilitar"],
    route: "/management/user-scopes",
    routeLabel: "Ir a Alcances de usuario",
    sections: [
      {
        title: "Uso",
        steps: [
          "Busca y selecciona el usuario.",
          "Revisa su nivel de acceso y situación.",
          "Marca únicamente los permisos específicos necesarios.",
          "Guarda los cambios.",
        ],
      },
      {
        title: "Permisos disponibles",
        paragraphs: [
          "La pantalla reúne accesos relacionados con menú contextual, anomalías, observaciones, tratamientos, convocatoria, análisis, acciones, pendientes y verificación de eficacia.",
        ],
      },
      {
        title: "Criterio operativo",
        paragraphs: [
          "El nivel de acceso y la asignación concreta como responsable continúan determinando las operaciones disponibles dentro de cada caso.",
        ],
      },
    ],
    related: ["administrar-usuarios", "administrar-catalogos"],
  },
  {
    id: "administrar-catalogos",
    category: "Administración",
    title: "Administrar catálogos y maestros",
    summary: "Mantiene los datos utilizados por formularios, filtros y reglas de clasificación.",
    audience: "admin",
    keywords: ["catalogo", "maestro", "area", "sector", "proceso", "severidad", "tipo"],
    route: "/management/catalogs",
    routeLabel: "Ir a Catálogos",
    sections: [
      {
        title: "Catálogos disponibles",
        bullets: [
          "Áreas, procesos o sectores y líneas.",
          "Tipos y asignaciones de anomalía.",
          "Criterios de Revisión de hallazgos.",
          "Orden operativo y tipos de acción.",
          "Tipos de órdenes afectadas.",
        ],
      },
      {
        title: "Crear o editar",
        steps: [
          "Selecciona el catálogo.",
          "Pulsa Nuevo registro o Editar.",
          "Completa código, nombre, orden y relaciones solicitadas.",
          "Define si el registro está activo.",
          "Guarda y comprueba su ubicación en el directorio.",
        ],
      },
      {
        title: "Orden y uso",
        paragraphs: [
          "El directorio administrativo prioriza el código para facilitar el control documental. En los formularios operativos, las opciones activas se presentan alfabéticamente para simplificar la selección.",
        ],
      },
      {
        title: "Desactivar antes de eliminar",
        paragraphs: [
          "Si un maestro ya fue utilizado, desactívalo para impedir nuevas selecciones sin perder referencias históricas.",
        ],
      },
    ],
    related: ["administrar-usuarios", "configurar-alcances", "clasificar-hallazgo"],
  },
];

export const HELP_TOPICS_BY_ID = new Map(HELP_TOPICS.map((topic) => [topic.id, topic]));
