import { useEffect } from "react";
import type { CurrentUser, AnomalyDetail, TreatmentDetail, TreatmentTaskHistory } from "../../api/types";
import { humanizeToken } from "../../app/utils";

export type HelpWorkContext = {
  recordLabel?: string;
  status: string;
  stage: string;
  responsible: string;
  nextAction: string;
  blockers: string[];
  tone?: "info" | "success" | "warning";
};

type HelpWorkContextEventDetail = {
  pathname: string;
  context: HelpWorkContext | null;
};

export const HELP_WORK_CONTEXT_EVENT = "calidad:help-work-context";
let latestHelpWorkContext: HelpWorkContextEventDetail | null = null;

function publishHelpWorkContext(detail: HelpWorkContextEventDetail) {
  latestHelpWorkContext = detail;
  window.dispatchEvent(new CustomEvent<HelpWorkContextEventDetail>(HELP_WORK_CONTEXT_EVENT, { detail }));
}

function userLabel(user?: { full_name?: string; username?: string; email?: string } | null) {
  return user?.full_name || user?.username || user?.email || "Sin responsable asignado";
}

export function usePublishHelpWorkContext(context: HelpWorkContext | null) {
  const serialized = JSON.stringify(context);

  useEffect(() => {
    const detail: HelpWorkContextEventDetail = { pathname: window.location.pathname, context };
    publishHelpWorkContext(detail);
    return () => {
      if (latestHelpWorkContext?.pathname === detail.pathname) {
        publishHelpWorkContext({ pathname: detail.pathname, context: null });
      }
    };
  }, [serialized]);
}

export function readHelpWorkContextEvent(event: Event): HelpWorkContextEventDetail | null {
  return (event as CustomEvent<HelpWorkContextEventDetail>).detail ?? null;
}

export function subscribeHelpWorkContext(listener: (detail: HelpWorkContextEventDetail | null) => void) {
  const handleEvent = (event: Event) => listener(readHelpWorkContextEvent(event));
  window.addEventListener(HELP_WORK_CONTEXT_EVENT, handleEvent);
  listener(latestHelpWorkContext);
  return () => window.removeEventListener(HELP_WORK_CONTEXT_EVENT, handleEvent);
}

export function getDefaultHelpWorkContext(pathname: string, user?: CurrentUser | null): HelpWorkContext | null {
  const currentUser = userLabel(user);

  if (pathname === "/dashboard/summary") {
    return {
      status: "Resumen global",
      stage: "Control y seguimiento",
      responsible: currentUser,
      nextAction: "Revisa los totales y estados; abre el detalle por usuario cuando necesites identificar responsables o pendientes.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/anomalies/new") {
    return {
      status: "Nuevo registro",
      stage: "Carga inicial",
      responsible: currentUser,
      nextAction: "Completa los datos obligatorios, revisa las evidencias y confirma el registro.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/anomalies" || pathname.startsWith("/anomalies/")) {
    return {
      status: "Consulta",
      stage: "Seguimiento",
      responsible: "Según la anomalía seleccionada",
      nextAction: "Busca y abre una anomalía para revisar su estado, responsable e historial.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/treatments") {
    return {
      status: "Consulta",
      stage: "Tratamiento",
      responsible: "Según el tratamiento seleccionado",
      nextAction: "Selecciona un tratamiento para conocer el trabajo requerido y sus condiciones pendientes.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/actions/mine") {
    return {
      status: "Pendiente de selección",
      stage: "Ejecución de acciones",
      responsible: currentUser,
      nextAction: "Selecciona una acción, revisa su fecha y actualiza el avance con la evidencia correspondiente.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/validation") {
    return {
      status: "Pendiente de selección",
      stage: "Verificación de eficacia",
      responsible: currentUser,
      nextAction: "Selecciona un tratamiento disponible y revisa las condiciones antes de registrar el resultado.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/learned-lessons") {
    return {
      status: "Tratamientos eficaces",
      stage: "Aprendizaje",
      responsible: "Responsable del tratamiento o perfil global",
      nextAction: "Busca el tratamiento eficaz y documenta el aprendizaje y los cambios de procedimiento.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/notifications/inbox") {
    return {
      status: "Bandeja personal",
      stage: "Seguimiento diario",
      responsible: currentUser,
      nextAction: "Revisa primero Pendientes y luego los Avisos sin leer.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/treatments/tracking") {
    return {
      status: "Solo lectura",
      stage: "Seguimiento",
      responsible: "Según el tratamiento",
      nextAction: "Selecciona un tratamiento para consultar su trazabilidad completa.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname === "/indicators" || pathname.startsWith("/indicators/")) {
    return {
      status: "Análisis",
      stage: "Indicadores",
      responsible: currentUser,
      nextAction: "Selecciona un indicador y aplica el período y proceso que deseas analizar.",
      blockers: [],
      tone: "info",
    };
  }
  if (pathname.startsWith("/management/")) {
    return {
      status: "Administración",
      stage: "Configuración",
      responsible: currentUser,
      nextAction: "Busca el registro, revisa su información y guarda solamente los cambios necesarios.",
      blockers: [],
      tone: "info",
    };
  }
  return null;
}

export function resolveAnomalyHelpWorkContext(anomaly: AnomalyDetail, isAdmin: boolean): HelpWorkContext {
  const immediateAction = anomaly.immediate_action;
  const status = humanizeToken(anomaly.current_status);
  const stage = humanizeToken(anomaly.current_stage);
  const responsible = userLabel(immediateAction?.responsible || anomaly.current_responsible || anomaly.owner);
  let nextAction = "Consulta el historial y continúa desde el módulo relacionado con la etapa actual.";
  let tone: HelpWorkContext["tone"] = "info";

  if (["closed", "cancelled"].includes(anomaly.current_status)) {
    nextAction = "El caso está finalizado. Consulta su trazabilidad y evidencias cuando lo necesites.";
    tone = "success";
  } else if (!anomaly.classification && isAdmin) {
    nextAction = "Realiza la Revisión de hallazgos desde Seguimiento de anomalías.";
  } else if (!anomaly.classification) {
    nextAction = "El hallazgo espera la Revisión de Calidad. Puedes consultar su evolución en Seguimiento.";
  } else if (anomaly.observation_resolution_path === "TREATMENT_PENDING") {
    nextAction = "La Observación TRT está disponible para que Calidad la asocie a un tratamiento elegible.";
  } else if (immediateAction && !immediateAction.actions_taken) {
    nextAction = "Registra y confirma las acciones tomadas en el módulo Observaciones.";
  } else if (immediateAction?.effectiveness_is_effective === false) {
    nextAction = "Revisa el resultado no eficaz y registra nuevas acciones tomadas.";
    tone = "warning";
  } else if (immediateAction?.actions_taken && immediateAction.effectiveness_is_effective == null) {
    nextAction = "El responsable asignado debe verificar la eficacia en la fecha prevista.";
  } else if (anomaly.current_stage === "effectiveness_verification") {
    nextAction = "Consulta Validaciones y espera la evaluación del responsable designado.";
  } else if (["treatment_created", "cause_analysis", "action_plan", "execution_follow_up"].includes(anomaly.current_stage)) {
    nextAction = "Continúa el trabajo desde el tratamiento asociado y sus acciones.";
  }

  return {
    recordLabel: `${anomaly.code} — ${anomaly.title}`,
    status,
    stage,
    responsible,
    nextAction,
    blockers: [],
    tone,
  };
}

export function resolveTreatmentHelpWorkContext(treatment: TreatmentDetail): HelpWorkContext {
  const blockers = treatment.validation_state?.blockers ?? [];
  const incompleteTasks = treatment.tasks.filter((task) => task.status !== "completed").length;
  const responsible = userLabel(treatment.responsible);
  let stage = "Convocatoria";
  let nextAction = "Completa la fecha, el lugar y todos los convocados antes de confirmar la agenda.";
  let tone: HelpWorkContext["tone"] = "info";

  if (treatment.is_locked || treatment.status === "completed") {
    stage = "Tratamiento finalizado";
    nextAction = "Consulta el resultado y registra la lección aprendida cuando corresponda.";
    tone = "success";
  } else if (!treatment.can_manage) {
    stage = treatment.validation_state?.available ? "Verificación de eficacia" : "Seguimiento";
    nextAction = treatment.can_validate_effectiveness && treatment.validation_state?.available
      ? "Ingresa a Validaciones y registra el resultado de eficacia."
      : "Consulta el tratamiento y atiende únicamente las acciones o validaciones que te hayan asignado.";
  } else if (!treatment.convocation_confirmed_at) {
    stage = "Convocatoria";
  } else if (!treatment.root_causes.length) {
    stage = "Análisis de causas";
    nextAction = "Abre Vista 2 — Análisis y registra al menos una causa raíz con detalle.";
  } else if (incompleteTasks > 0) {
    stage = "Ejecución de acciones";
    nextAction = `Realiza el seguimiento de las ${incompleteTasks} acciones que todavía no están completadas.`;
  } else if (blockers.length > 0) {
    stage = "Preparación de eficacia";
    nextAction = "Completa las condiciones indicadas por el sistema para habilitar la validación.";
    tone = "warning";
  } else if (treatment.validation_state?.available) {
    stage = "Verificación de eficacia";
    nextAction = treatment.can_validate_effectiveness
      ? "Ingresa a Validaciones y registra el resultado de eficacia."
      : "El tratamiento está listo. El responsable designado debe verificar la eficacia.";
  }

  return {
    recordLabel: `${treatment.code} — ${treatment.primary_anomaly.title}`,
    status: humanizeToken(treatment.status),
    stage,
    responsible,
    nextAction,
    blockers,
    tone,
  };
}

export function resolveTaskHelpWorkContext(task: TreatmentTaskHistory): HelpWorkContext {
  const complete = task.status === "completed";
  const canWork = task.can_update_status || task.can_add_evidence;
  return {
    recordLabel: `${task.code || "Acción"} — ${task.title}`,
    status: humanizeToken(task.is_overdue && !complete ? "overdue" : task.status),
    stage: complete ? "Acción completada" : "Ejecución de acción",
    responsible: userLabel(task.responsible),
    nextAction: complete
      ? "La acción está completada y permanece disponible en el historial."
      : canWork
        ? "Actualiza el estado, registra la nota del cambio y adjunta la evidencia necesaria."
        : "Consulta la definición. Solo el responsable asignado puede actualizar el estado y cargar evidencia.",
    blockers: task.is_overdue && !complete ? ["La fecha prevista de ejecución está vencida."] : [],
    tone: complete ? "success" : task.is_overdue ? "warning" : "info",
  };
}
