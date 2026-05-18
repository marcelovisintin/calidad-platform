import type { TreatmentLearnedLessonEvidence, UserSummary } from "../api/types";
import { formatDateTime } from "../app/utils";

type LearnedLessonReadOnlyProps = {
  treatmentCode?: string;
  savedBy?: UserSummary | null;
  savedAt?: string | null;
  hasLearning: boolean | null;
  learnedText?: string;
  noLearningReason?: string;
  procedureModified: boolean | null;
  procedureModificationNotes?: string;
  evidences?: TreatmentLearnedLessonEvidence[];
};

function evidenceUrl(fileUrl: string) {
  if (!fileUrl) {
    return "#";
  }
  if (fileUrl.startsWith("/")) {
    return fileUrl;
  }
  if (fileUrl.startsWith("http://") || fileUrl.startsWith("https://")) {
    try {
      const parsed = new URL(fileUrl);
      const host = parsed.hostname.toLowerCase();
      if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
      }
    } catch {
      return fileUrl;
    }
  }
  return fileUrl.startsWith("/") ? fileUrl : `/${fileUrl}`;
}

function yesNo(value: boolean | null) {
  if (value === true) {
    return "Si";
  }
  if (value === false) {
    return "No";
  }
  return "-";
}

export function LearnedLessonReadOnly({
  treatmentCode,
  savedBy,
  savedAt,
  hasLearning,
  learnedText,
  noLearningReason,
  procedureModified,
  procedureModificationNotes,
  evidences = [],
}: LearnedLessonReadOnlyProps) {
  return (
    <div className="nested-card learned-lesson-readonly">
      <div className="learned-lesson-readonly-grid">
        <div className="learned-lesson-readonly-column">
          <div className="learned-lesson-title-row">
            {treatmentCode ? <strong>{treatmentCode}</strong> : <strong>Tratamiento</strong>}
            <span>Leccion aprendida</span>
          </div>
          <div>
            <small>Responsable carga</small>
            <p>{savedBy?.full_name || savedBy?.username || "-"}</p>
          </div>
          <div>
            <small>Hubo aprendizaje</small>
            <p>{yesNo(hasLearning)}</p>
          </div>
        </div>

        <div className="learned-lesson-readonly-column">
          <div>
            <small>Fecha</small>
            <p>{formatDateTime(savedAt)}</p>
          </div>
          <div>
            <small>Modifica procedimiento/tratamiento</small>
            <p>{yesNo(procedureModified)}</p>
          </div>
        </div>

        <div className="learned-lesson-readonly-column">
          <div>
            <small>{hasLearning === false ? "Por que no se aprendio" : "Que se aprendio"}</small>
            <p>{hasLearning === false ? noLearningReason || "-" : learnedText || "-"}</p>
          </div>
          <div>
            <small>Detalle de modificacion</small>
            <p>{procedureModified ? procedureModificationNotes || "-" : "-"}</p>
          </div>
        </div>

        <div className="learned-lesson-readonly-column">
          <small>Evidencia objetiva</small>
          {evidences.length ? (
            <div className="stack-list compact learned-lesson-evidence-list">
              {evidences.map((evidence) => (
                <a className="list-card compact" href={evidenceUrl(evidence.file_url)} key={evidence.id} rel="noopener noreferrer" target="_blank">
                  <span>{evidence.original_name}</span>
                  <small>{formatDateTime(evidence.created_at)}</small>
                </a>
              ))}
            </div>
          ) : (
            <p>Sin evidencia objetiva cargada.</p>
          )}
        </div>
      </div>
    </div>
  );
}
