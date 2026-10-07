import { useEffect, useMemo, useState } from "react";
import type { AnomalyStatusHistory } from "../api/types";
import { formatDateTime } from "../app/utils";
import { PaginationControls } from "./PaginationControls";
import { StatusBadge } from "./StatusBadge";
import { PublishedLessonSnapshot } from "./PublishedLessonSnapshot";

type TimelineProps = {
  items: AnomalyStatusHistory[];
};

const PAGE_SIZE = 10;

const ACTION_STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente", in_progress: "En curso", completed: "Completada", cancelled: "Cancelada",
};
const TREATMENT_STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente", scheduled: "Programado", in_progress: "En tratamiento",
  completed: "Completado", cancelled: "Cancelado",
};
const ANOMALY_STATUS_LABELS: Record<string, string> = {
  registered: "Registrada", in_evaluation: "En evaluación", in_analysis: "En análisis",
  in_treatment: "En tratamiento", pending_verification: "Pendiente de verificación",
  closed: "Cerrada", cancelled: "Anulada", reopened: "Reabierta",
};
const ANOMALY_STAGE_LABELS: Record<string, string> = {
  registration: "Registro", containment: "Contención", initial_verification: "Verificación inicial",
  classification: "Revisión de hallazgos", treatment_created: "Tratamiento creado",
  cause_analysis: "Análisis de causa", proposals: "Propuestas", action_plan: "Plan de acción",
  execution_follow_up: "Ejecución y seguimiento", results: "Resultados",
  effectiveness_verification: "Verificación de eficacia", closure: "Cierre",
  standardization_learning: "Estandarización y aprendizaje",
};
const OBSERVATION_PATH_LABELS: Record<string, string> = {
  observation: "Observación", treatment_pending: "Observación TRT (con tratamiento)",
  treatment: "Tratamiento",
};

function historyLabel(value: string, labels: Record<string, string>) {
  return labels[value.toLowerCase()] ?? value;
}

function isTaskStatusHistory(item: AnomalyStatusHistory) {
  const comment = item.comment.toLowerCase();
  return (/se actualiza la (acci[oó]n|tarea)/i.test(comment)) && comment.includes("estado");
}

function displayHistoryComment(comment: string) {
  const labels = /se actualiza la (acci[oó]n|tarea)/i.test(comment)
    ? ACTION_STATUS_LABELS : TREATMENT_STATUS_LABELS;
  return comment
    .replace(/\bTareas\b/g, "Acciones")
    .replace(/\btareas\b/g, "acciones")
    .replace(/\bTarea\b/g, "Acción")
    .replace(/\btarea\b/g, "acción")
    .replace(/(de estado )([a-z_]+)( a estado )([a-z_]+)/gi,
      (_, start: string, previous: string, middle: string, next: string) =>
        `${start}${historyLabel(previous, labels)}${middle}${historyLabel(next, labels)}`)
    .replace(/(cambia a estado )([a-z_]+)/gi,
      (_, start: string, status: string) => `${start}${historyLabel(status, TREATMENT_STATUS_LABELS)}`);
}

function displayHistoryEvidence(note: string) {
  return note
    .replace(/^(Estado anterior|Estado nuevo):[ \t]*([a-z_]+)$/gim,
      (_, field: string, status: string) => `${field}: ${historyLabel(status, ANOMALY_STATUS_LABELS)}`)
    .replace(/^(Etapa anterior|Etapa nueva):[ \t]*([a-z_]+)$/gim,
      (_, field: string, stage: string) => `${field}: ${historyLabel(stage, ANOMALY_STAGE_LABELS)}`)
    .replace(/^(Camino anterior|Camino nuevo):[ \t]*([a-z_]+)$/gim,
      (_, field: string, path: string) => `${field}: ${historyLabel(path, OBSERVATION_PATH_LABELS)}`);
}

function getEvidenceText(item: AnomalyStatusHistory) {
  const evidenceNote = item.evidence_note?.trim();
  if (evidenceNote) {
    return displayHistoryEvidence(evidenceNote);
  }
  return isTaskStatusHistory(item) ? "Sin evidencia registrada" : "";
}

export function Timeline({ items }: TimelineProps) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [items.length]);

  const pagedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  if (!items.length) {
    return <p className="muted-copy">No hay registros en el historial.</p>;
  }

  return (
    <>
      <ol className="timeline">
        {pagedItems.map((item) => {
          const evidenceText = getEvidenceText(item);
          return (
            <li key={item.id} className="timeline-item">
              <div className="timeline-dot" />
              <div className="timeline-content">
                <div className="timeline-row">
                  <StatusBadge value={item.from_stage} compact />
                  <span className="timeline-arrow">a</span>
                  <StatusBadge value={item.to_stage} compact />
                </div>
                <p className="timeline-comment">{displayHistoryComment(item.comment)}</p>
                <PublishedLessonSnapshot data={item.document_snapshot} />
                {evidenceText ? (
                  <p className="timeline-evidence" style={{ whiteSpace: "pre-line" }}>
                    <strong>Evidencia:</strong> {evidenceText}
                  </p>
                ) : null}
                <small>
                  {formatDateTime(item.changed_at)}
                  {item.changed_by?.full_name ? ` - ${item.changed_by.full_name}` : ""}
                </small>
              </div>
            </li>
          );
        })}
      </ol>

      <PaginationControls page={page} totalCount={items.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
    </>
  );
}
