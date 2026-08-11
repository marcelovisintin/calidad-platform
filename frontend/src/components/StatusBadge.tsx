import { humanizeToken } from "../app/utils";

type StatusBadgeProps = {
  value?: string | null;
  compact?: boolean;
};

const toneMap: Record<string, string> = {
  registered: "neutral",
  in_evaluation: "info",
  in_analysis: "accent",
  in_treatment: "warning",
  pending_verification: "info",
  scheduled: "info",
  closed: "success",
  cancelled: "danger",
  reopened: "accent",
  pending: "warning",
  in_progress: "info",
  overdue: "danger",
  completed: "success",
  validated_effective: "success",
  not_effective: "warning",
  active: "success",
  inactive: "danger",
  staff: "accent",
  convoked: "info",
  facilitator: "accent",
  owner: "success",
  operativo: "neutral",
  usuario_activo: "success",
  mando_medio_activo: "accent",
  administrador: "info",
  desarrollador: "warning",
  email_notifications_enabled: "success",
  email_notifications_disabled: "neutral",
  draft: "neutral",
  containment: "warning",
  treatment_created: "info",
  cause_analysis: "accent",
  action_plan: "info",
  execution_follow_up: "accent",
  effectiveness_verification: "warning",
  closure: "success",
  standardization_learning: "neutral",
};

const labelMap: Record<string, string> = {
  classification: "Revisión de hallazgos",
  validated_effective: "Validado eficaz",
  not_effective: "No eficaz",
  email_notifications_enabled: "Correo activado",
  email_notifications_disabled: "Correo desactivado",
};

export function StatusBadge({ value, compact = false }: StatusBadgeProps) {
  if (!value) {
    return <span className="status-badge neutral">Sin dato</span>;
  }

  const tone = toneMap[value] ?? "neutral";
  return (
    <span className={`status-badge ${tone}${compact ? " compact" : ""}`}>
      {labelMap[value] ?? humanizeToken(value)}
    </span>
  );
}




