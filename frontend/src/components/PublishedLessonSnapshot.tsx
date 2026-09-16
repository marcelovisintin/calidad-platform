import { formatDateTime } from "../app/utils";

type LessonSnapshot = {
  event?: string;
  treatment_code?: string;
  published_at?: string;
  formally_closed_at?: string;
  lesson?: {
    has_learning?: boolean | null;
    learned_text?: string;
    no_learning_reason?: string;
    procedure_modified?: boolean | null;
    procedure_modification_notes?: string;
  };
  versions?: Array<{
    number: number;
    changed_at: string;
    learned_text?: string;
    no_learning_reason?: string;
    procedure_modification_notes?: string;
    evidences?: string[];
  }>;
  derived_actions?: Array<{ code: string; title: string; execution_date?: string }>;
};

export function PublishedLessonSnapshot({ data }: { data?: Record<string, unknown> }) {
  const snapshot = data as LessonSnapshot | undefined;
  if (snapshot?.event !== "treatment.learned_lesson.published") return null;
  return (
    <details className="published-lesson-snapshot">
      <summary>Documento de cierre: lección publicada y versiones</summary>
      <p>Tratamiento {snapshot.treatment_code} · publicación {formatDateTime(snapshot.published_at)} · cierre formal {formatDateTime(snapshot.formally_closed_at)}</p>
      <p>{snapshot.lesson?.has_learning ? `Aprendizaje: ${snapshot.lesson.learned_text || "-"}` : `Sin aprendizaje: ${snapshot.lesson?.no_learning_reason || "-"}`}</p>
      <p>Modifica procedimiento: {snapshot.lesson?.procedure_modified ? "Sí" : "No"}. {snapshot.lesson?.procedure_modification_notes || ""}</p>
      {snapshot.derived_actions?.length ? <div><strong>Acciones derivadas</strong>{snapshot.derived_actions.map((action) => <p key={action.code}>{action.code}: {action.title} · límite {action.execution_date || "-"}</p>)}</div> : null}
      {snapshot.versions?.length ? <div><strong>Versiones conservadas</strong>{snapshot.versions.map((version) => <div key={version.number}><p>Versión {version.number} · {formatDateTime(version.changed_at)}</p><p>{version.learned_text || version.no_learning_reason || "-"}</p>{version.procedure_modification_notes ? <p>Procedimiento: {version.procedure_modification_notes}</p> : null}{version.evidences?.length ? <p>Evidencias: {version.evidences.join(", ")}</p> : null}</div>)}</div> : null}
    </details>
  );
}
