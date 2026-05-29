import { MouseEvent, useState } from "react";
import { normalizeProtectedFileUrl, openAuthenticatedFile } from "../api/files";
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
  const [error, setError] = useState<string | null>(null);

  const handleOpenEvidence = async (event: MouseEvent<HTMLAnchorElement>, fileUrl: string, fallbackName: string) => {
    event.preventDefault();
    setError(null);
    try {
      await openAuthenticatedFile(fileUrl, fallbackName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo abrir la evidencia.");
    }
  };

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
          {error ? <p className="form-error">{error}</p> : null}
          {evidences.length ? (
            <div className="stack-list compact learned-lesson-evidence-list">
              {evidences.map((evidence) => (
                <a
                  className="list-card compact"
                  href={normalizeProtectedFileUrl(evidence.file_url)}
                  key={evidence.id}
                  onClick={(event) => void handleOpenEvidence(event, evidence.file_url, evidence.original_name)}
                  rel="noopener noreferrer"
                  target="_blank"
                >
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
