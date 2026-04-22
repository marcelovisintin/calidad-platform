const TOKEN_LABELS: Record<string, string> = {
  registered: "registrado",
  in_evaluation: "en evaluacion",
  in_analysis: "en analisis",
  in_treatment: "en tratamiento",
  pending_verification: "pendiente de verificacion",
  scheduled: "programado",
  closed: "cerrado",
  cancelled: "cancelado",
  reopened: "reabierto",
  pending: "pendiente",
  in_progress: "en curso",
  overdue: "vencido",
  completed: "completado",
  active: "activo",
  inactive: "inactivo",
  staff: "equipo",
  operativo: "operativo",
  usuario_activo: "usuario activo",
  mando_medio_activo: "mando medio activo",
  administrador: "administrador",
  desarrollador: "desarrollador",
  draft: "borrador",
  registration: "registro",
  containment: "contencion",
  treatment_created: "tratamiento creado",
  cause_analysis: "analisis de causa",
  action_plan: "plan de accion",
  execution_follow_up: "ejecucion y seguimiento",
  effectiveness_verification: "verificacion de eficacia",
  closure: "cierre",
  standardization_learning: "estandarizacion y aprendizaje",
  convoked: "convocado",
  facilitator: "facilitador",
  owner: "responsable",
  delivery_sent: "entregada",
  delivered: "entregada",
  unread: "no leida",
  read: "leida",
  none: "sin estado",
  sent: "enviada",
  failed: "fallida",
  anomaly: "anomalia",
};

function parseDateValue(value: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
  }
  return new Date(value);
}

export function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parseDateValue(value));
}

export function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
  }).format(parseDateValue(value));
}

export function toOffsetIso(localDateTime: string) {
  const date = new Date(localDateTime);
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absMinutes / 60)).padStart(2, "0");
  const minutes = String(absMinutes % 60).padStart(2, "0");
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day}T${hh}:${mm}:${ss}${sign}${hours}:${minutes}`;
}

export function toDateTimeLocalValue(isoDateTime?: string | null) {
  if (!isoDateTime) {
    return "";
  }
  const date = new Date(isoDateTime);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hh}:${mm}`;
}

export function humanizeToken(value: string) {
  const normalized = value.trim().toLowerCase();
  return TOKEN_LABELS[normalized] || normalized.replace(/_/g, " ");
}




