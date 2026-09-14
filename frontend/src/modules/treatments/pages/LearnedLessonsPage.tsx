import { ChangeEvent, FormEvent, MouseEvent, useEffect, useState } from "react";
import { normalizeProtectedFileUrl, openAuthenticatedFile } from "../../../api/files";
import { fetchObservationLearnedLessons, saveObservationLearnedLesson } from "../../../api/anomalies";
import { fetchLearnedLessons, saveTreatmentLearnedLesson } from "../../../api/treatments";
import type { ObservationLearnedLessonItem, TreatmentSummary } from "../../../api/types";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type LessonFormState = {
  hasLearning: "" | "yes" | "no";
  learnedText: string;
  noLearningReason: string;
  procedureModified: "" | "yes" | "no";
  procedureModificationNotes: string;
  evidences: File[];
};

const emptyForm: LessonFormState = {
  hasLearning: "",
  learnedText: "",
  noLearningReason: "",
  procedureModified: "",
  procedureModificationNotes: "",
  evidences: [],
};

const learnedLessonFieldLabels: Record<string, string> = {
  has_learning: "Existencia de aprendizaje",
  learned_text: "Aprendizaje registrado",
  no_learning_reason: "Motivo sin aprendizaje",
  procedure_modified: "Modificación de procedimiento",
  procedure_modification_notes: "Detalle de modificación del procedimiento",
};

function formFromTreatment(treatment: TreatmentSummary): LessonFormState {
  const lesson = treatment.learned_lesson;
  if (!lesson) {
    return emptyForm;
  }
  return {
    hasLearning: lesson.has_learning === true ? "yes" : lesson.has_learning === false ? "no" : "",
    learnedText: lesson.learned_text || "",
    noLearningReason: lesson.no_learning_reason || "",
    procedureModified: lesson.procedure_modified === true ? "yes" : lesson.procedure_modified === false ? "no" : "",
    procedureModificationNotes: lesson.procedure_modification_notes || "",
    evidences: [],
  };
}

function LearnedLessonCard({
  treatment,
  onSaved,
}: {
  treatment: TreatmentSummary;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState<LessonFormState>(() => formFromTreatment(treatment));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lesson = treatment.learned_lesson;

  useEffect(() => {
    setForm(formFromTreatment(treatment));
    setMessage(null);
    setError(null);
  }, [treatment]);

  const updateForm = (patch: Partial<LessonFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const validate = () => {
    if (!form.hasLearning) {
      return "Debe indicar si hubo un aprendizaje.";
    }
    if (form.hasLearning === "yes" && !form.learnedText.trim()) {
      return "Debe completar que se aprendio.";
    }
    if (form.hasLearning === "no" && !form.noLearningReason.trim()) {
      return "Debe indicar por que no se aprendio.";
    }
    if (!form.procedureModified) {
      return "Debe indicar si modifica procedimiento.";
    }
    if (form.procedureModified === "yes" && !form.procedureModificationNotes.trim()) {
      return "Debe completar las observaciones sobre modificacion de procedimiento.";
    }
    return "";
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationMessage = validate();
    if (validationMessage) {
      setError(validationMessage);
      setMessage(null);
      return;
    }

    if (lesson && !window.confirm("¿Está seguro de modificar la lección aprendida?")) {
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await saveTreatmentLearnedLesson(treatment.id, {
        has_learning: form.hasLearning === "yes",
        learned_text: form.learnedText,
        no_learning_reason: form.noLearningReason,
        procedure_modified: form.procedureModified === "yes",
        procedure_modification_notes: form.procedureModificationNotes,
        evidences: form.evidences,
        confirm_modification: Boolean(lesson),
      });
      setMessage("Leccion aprendida guardada.");
      await onSaved();
      setForm((current) => ({ ...current, evidences: [] }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la leccion aprendida.");
    } finally {
      setSaving(false);
    }
  };

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    updateForm({ evidences: Array.from(event.target.files ?? []) });
  };

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
    <article className="panel learned-lesson-card">
      <div className="learned-lesson-summary">
        <div className="section-head compact">
          <div>
            <strong>{treatment.code}</strong>
            <p>{treatment.primary_anomaly.title}</p>
          </div>
          <StatusBadge compact value="validated_effective" />
        </div>
        <dl className="key-grid compact">
          <div><dt>Anomalia</dt><dd>{treatment.primary_anomaly.code}</dd></div>
          <div><dt>Area</dt><dd>{treatment.primary_anomaly.area?.name || "-"}</dd></div>
          <div><dt>Validado</dt><dd>{formatDate(treatment.effectiveness_validated_at)}</dd></div>
          <div><dt>Responsable</dt><dd>{treatment.effectiveness_responsible?.full_name || treatment.effectiveness_responsible?.username || "-"}</dd></div>
        </dl>
        {lesson?.saved_at ? (
          <p className="muted-copy">
            Ultima carga: {formatDateTime(lesson.saved_at)} por {lesson.saved_by?.full_name || lesson.saved_by?.username || "-"}
          </p>
        ) : (
          <p className="muted-copy">Sin leccion aprendida registrada.</p>
        )}
      </div>

      <form className="learned-lesson-form" onSubmit={handleSubmit}>
        {message ? <div className="panel info compact-inline-panel">{message}</div> : null}
        {error ? <div className="panel danger compact-inline-panel">{error}</div> : null}

        <label className="field">
          <span>Hubo un aprendizaje?</span>
          <select value={form.hasLearning} onChange={(event) => updateForm({ hasLearning: event.target.value as LessonFormState["hasLearning"] })}>
            <option value="">Seleccionar...</option>
            <option value="yes">Si</option>
            <option value="no">No</option>
          </select>
        </label>

        {form.hasLearning === "yes" ? (
          <>
            <label className="field">
              <span>Que se aprendio?</span>
              <textarea value={form.learnedText} onChange={(event) => updateForm({ learnedText: event.target.value })} />
            </label>
            <label className="field">
              <span>Evidencia objetiva</span>
              <input multiple type="file" onChange={handleFiles} />
            </label>
          </>
        ) : null}

        {form.hasLearning === "no" ? (
          <label className="field">
            <span>Por que no se aprendio?</span>
            <textarea value={form.noLearningReason} onChange={(event) => updateForm({ noLearningReason: event.target.value })} />
          </label>
        ) : null}

        <label className="field">
          <span>Modifica procedimiento?</span>
          <select value={form.procedureModified} onChange={(event) => updateForm({ procedureModified: event.target.value as LessonFormState["procedureModified"] })}>
            <option value="">Seleccionar...</option>
            <option value="yes">Si</option>
            <option value="no">No</option>
          </select>
        </label>

        {form.procedureModified === "yes" ? (
          <label className="field">
            <span>Observaciones sobre modificacion de procedimiento</span>
            <textarea value={form.procedureModificationNotes} onChange={(event) => updateForm({ procedureModificationNotes: event.target.value })} />
          </label>
        ) : null}

        {lesson?.evidences.length ? (
          <div className="form-section">
            <strong>Evidencias cargadas</strong>
            <div className="stack-list compact">
              {lesson.evidences.map((evidence) => (
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
          </div>
        ) : null}

        <div className="form-actions">
          <button className="button button-primary" disabled={saving} type="submit">
            Guardar cambios
          </button>
        </div>
      </form>

      {lesson?.revisions?.length ? (
        <details className="learned-lesson-history">
          <summary>Historial de modificaciones ({lesson.revisions.length})</summary>
          <div className="learned-lesson-revision-list">
            {lesson.revisions.map((revision) => (
              <article className="learned-lesson-revision" key={revision.id}>
                <div className="learned-lesson-revision-head">
                  <div>
                    <strong>Revisión {revision.revision_number}</strong>
                    <small>
                      {formatDateTime(revision.changed_at)} · {revision.changed_by?.full_name || revision.changed_by?.username || "-"}
                    </small>
                  </div>
                  <span className="status-pill">
                    {revision.revision_number === 1 ? "Registro inicial" : "Modificación"}
                  </span>
                </div>

                <div className="learned-lesson-change-list">
                  {(revision.changed_fields?.length ? revision.changed_fields : ["Sin cambios de contenido"]).map((field) => (
                    <span className="learned-lesson-change" key={field}>
                      {learnedLessonFieldLabels[field] || field}
                    </span>
                  ))}
                </div>

                <dl className="learned-lesson-snapshot">
                  <div><dt>¿Hubo aprendizaje?</dt><dd>{revision.has_learning === true ? "Sí" : revision.has_learning === false ? "No" : "-"}</dd></div>
                  <div><dt>¿Modifica procedimiento?</dt><dd>{revision.procedure_modified === true ? "Sí" : revision.procedure_modified === false ? "No" : "-"}</dd></div>
                  {revision.has_learning ? <div><dt>Aprendizaje</dt><dd>{revision.learned_text || "-"}</dd></div> : null}
                  {revision.has_learning === false ? <div><dt>Motivo</dt><dd>{revision.no_learning_reason || "-"}</dd></div> : null}
                  {revision.procedure_modified ? <div><dt>Detalle del procedimiento</dt><dd>{revision.procedure_modification_notes || "-"}</dd></div> : null}
                </dl>

                {revision.evidences?.length ? (
                  <div className="learned-lesson-revision-evidence">
                    <strong>Evidencias conservadas en esta revisión</strong>
                    {revision.evidences.map((evidence) => (
                      <a
                        href={normalizeProtectedFileUrl(evidence.file_url)}
                        key={evidence.id}
                        onClick={(event) => void handleOpenEvidence(event, evidence.file_url, evidence.original_name)}
                        rel="noopener noreferrer"
                        target="_blank"
                      >
                        {evidence.original_name}
                      </a>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}

function observationFormFromItem(item: ObservationLearnedLessonItem): LessonFormState {
  const lesson = item.learning;
  if (!lesson) {
    return emptyForm;
  }
  return {
    hasLearning: lesson.has_learning === true ? "yes" : lesson.has_learning === false ? "no" : "",
    learnedText: lesson.learned_text || "",
    noLearningReason: lesson.no_learning_reason || "",
    procedureModified: lesson.procedure_modified === true ? "yes" : lesson.procedure_modified === false ? "no" : "",
    procedureModificationNotes: lesson.procedure_modification_notes || "",
    evidences: [],
  };
}

function ObservationLearnedLessonCard({
  item,
  onSaved,
}: {
  item: ObservationLearnedLessonItem;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState<LessonFormState>(() => observationFormFromItem(item));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(observationFormFromItem(item));
    setMessage(null);
    setError(null);
  }, [item]);

  const updateForm = (patch: Partial<LessonFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const validate = () => {
    if (!form.hasLearning) {
      return "Debe indicar si hubo un aprendizaje.";
    }
    if (form.hasLearning === "yes" && !form.learnedText.trim()) {
      return "Debe completar que se aprendio.";
    }
    if (form.hasLearning === "no" && !form.noLearningReason.trim()) {
      return "Debe indicar por que no se aprendio.";
    }
    if (!form.procedureModified) {
      return "Debe indicar si modifica procedimiento.";
    }
    if (form.procedureModified === "yes" && !form.procedureModificationNotes.trim()) {
      return "Debe completar las observaciones sobre modificacion de procedimiento.";
    }
    return "";
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationMessage = validate();
    if (validationMessage) {
      setError(validationMessage);
      setMessage(null);
      return;
    }
    if (item.learning && !window.confirm("¿Está seguro de modificar la lección aprendida de esta Observación?")) {
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await saveObservationLearnedLesson(item.id, {
        has_learning: form.hasLearning === "yes",
        learned_text: form.learnedText,
        no_learning_reason: form.noLearningReason,
        procedure_modified: form.procedureModified === "yes",
        procedure_modification_notes: form.procedureModificationNotes,
        evidences: form.evidences,
        confirm_modification: Boolean(item.learning),
      });
      setMessage("Leccion aprendida de la Observacion guardada.");
      await onSaved();
      setForm((current) => ({ ...current, evidences: [] }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la leccion aprendida de la Observacion.");
    } finally {
      setSaving(false);
    }
  };

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    updateForm({ evidences: Array.from(event.target.files ?? []) });
  };

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
    <article className="panel learned-lesson-card">
      <div className="learned-lesson-summary">
        <div className="section-head compact">
          <div>
            <strong>{item.code}</strong>
            <p>{item.title}</p>
          </div>
          <StatusBadge compact value="validated_effective" />
        </div>
        <dl className="key-grid compact">
          <div><dt>Origen</dt><dd>Observacion</dd></div>
          <div><dt>Area</dt><dd>{item.area?.name || "-"}</dd></div>
          <div><dt>Validado</dt><dd>{formatDate(item.effectiveness_verified_at)}</dd></div>
          <div><dt>Responsable</dt><dd>{item.responsible?.full_name || item.responsible?.username || "-"}</dd></div>
        </dl>
        {item.learning?.recorded_at ? (
          <p className="muted-copy">
            Ultima carga: {formatDateTime(item.learning.recorded_at)} por {item.learning.recorded_by?.full_name || item.learning.recorded_by?.username || "-"}
          </p>
        ) : (
          <p className="muted-copy">Sin leccion aprendida registrada.</p>
        )}
      </div>

      <form className="learned-lesson-form" onSubmit={handleSubmit}>
        {message ? <div className="panel info compact-inline-panel">{message}</div> : null}
        {error ? <div className="panel danger compact-inline-panel">{error}</div> : null}

        <label className="field">
          <span>Hubo un aprendizaje?</span>
          <select value={form.hasLearning} onChange={(event) => updateForm({ hasLearning: event.target.value as LessonFormState["hasLearning"] })}>
            <option value="">Seleccionar...</option>
            <option value="yes">Si</option>
            <option value="no">No</option>
          </select>
        </label>

        {form.hasLearning === "yes" ? (
          <>
            <label className="field">
              <span>Que se aprendio?</span>
              <textarea value={form.learnedText} onChange={(event) => updateForm({ learnedText: event.target.value })} />
            </label>
            <label className="field">
              <span>Evidencia objetiva</span>
              <input multiple type="file" onChange={handleFiles} />
            </label>
          </>
        ) : null}

        {form.hasLearning === "no" ? (
          <label className="field">
            <span>Por que no se aprendio?</span>
            <textarea value={form.noLearningReason} onChange={(event) => updateForm({ noLearningReason: event.target.value })} />
          </label>
        ) : null}

        <label className="field">
          <span>Modifica procedimiento?</span>
          <select value={form.procedureModified} onChange={(event) => updateForm({ procedureModified: event.target.value as LessonFormState["procedureModified"] })}>
            <option value="">Seleccionar...</option>
            <option value="yes">Si</option>
            <option value="no">No</option>
          </select>
        </label>

        {form.procedureModified === "yes" ? (
          <label className="field">
            <span>Observaciones sobre modificacion de procedimiento</span>
            <textarea value={form.procedureModificationNotes} onChange={(event) => updateForm({ procedureModificationNotes: event.target.value })} />
          </label>
        ) : null}

        {item.learning?.evidences.length ? (
          <div className="form-section">
            <strong>Evidencias cargadas</strong>
            <div className="stack-list compact">
              {item.learning.evidences.map((evidence) => (
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
          </div>
        ) : null}
        <div className="form-actions">
          <button className="button button-primary" disabled={saving} type="submit">
            Guardar cambios
          </button>
        </div>
      </form>
    </article>
  );
}

export function LearnedLessonsPage() {
  usePageTitle("Lecciones aprendidas");
  const [source, setSource] = useState<"treatments" | "observations">("treatments");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const treatmentTask = useAsyncTask(() => fetchLearnedLessons(page, search), [page, search]);
  const observationTask = useAsyncTask(() => fetchObservationLearnedLessons(page, search), [page, search]);
  const treatments = treatmentTask.data?.results ?? [];
  const observations = observationTask.data?.results ?? [];

  const changeSource = (nextSource: "treatments" | "observations") => {
    setSource(nextSource);
    setPage(1);
  };

  const handleSearch = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  return (
    <section className="page-shell">
      <PageHeader title="Lecciones aprendidas" description="Registro de aprendizajes de tratamientos y Observaciones validados como eficaces." />

      <div className="treatment-tab-row">
        <button
          className={`button button-secondary${source === "treatments" ? " active" : ""}`}
          onClick={() => changeSource("treatments")}
          type="button"
        >
          Tratamientos
        </button>
        <button
          className={`button button-secondary${source === "observations" ? " active" : ""}`}
          onClick={() => changeSource("observations")}
          type="button"
        >
          Observaciones
        </button>
      </div>

      <TabbedFilters
        ariaLabel="Filtros de lecciones aprendidas"
        onClear={() => { setSearch(""); setPage(1); }}
        items={[{
          id: "search",
          label: source === "treatments" ? "Buscar tratamiento" : "Buscar Observacion",
          active: Boolean(search),
          content: <input aria-label="Buscar aprendizaje" onChange={handleSearch} placeholder="Codigo, anomalia o area" type="search" value={search} />,
        }]}
      />

      {source === "treatments" ? (
        <DataState
          loading={treatmentTask.loading}
          error={treatmentTask.error}
          onRetry={treatmentTask.reload}
          empty={(treatmentTask.data?.count ?? 0) === 0}
          emptyTitle="No hay tratamientos eficaces para mostrar"
          emptyDescription="Cuando un tratamiento sea validado como eficaz aparecera automaticamente en esta seccion."
        >
          <div className="stack-list">
            {treatments.map((treatment) => (
              <LearnedLessonCard key={treatment.id} treatment={treatment} onSaved={treatmentTask.reload} />
            ))}
          </div>
          <PaginationControls page={page} totalCount={treatmentTask.data?.count ?? 0} onPageChange={setPage} disabled={treatmentTask.loading} />
        </DataState>
      ) : (
        <DataState
          loading={observationTask.loading}
          error={observationTask.error}
          onRetry={observationTask.reload}
          empty={(observationTask.data?.count ?? 0) === 0}
          emptyTitle="No hay Observaciones eficaces para mostrar"
          emptyDescription="Cuando una Observacion sea verificada como eficaz aparecera automaticamente en esta seccion."
        >
          <div className="stack-list">
            {observations.map((item) => (
              <ObservationLearnedLessonCard item={item} key={item.id} onSaved={observationTask.reload} />
            ))}
          </div>
          <PaginationControls page={page} totalCount={observationTask.data?.count ?? 0} onPageChange={setPage} disabled={observationTask.loading} />
        </DataState>
      )}
    </section>
  );
}
