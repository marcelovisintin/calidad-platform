import { ChangeEvent, FormEvent, KeyboardEvent, MouseEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { normalizeProtectedFileUrl, openAuthenticatedFile } from "../../../api/files";
import { fetchObservationLearnedLessons, saveObservationLearnedLesson } from "../../../api/anomalies";
import { createLessonDerivedAction, fetchLearnedLessons, fetchTreatmentParticipantOptions, publishTreatmentLesson, saveTreatmentLearnedLesson, sendTreatmentLessonForPublication } from "../../../api/treatments";
import type { ObservationLearnedLessonItem, TreatmentParticipantOption, TreatmentSummary } from "../../../api/types";
import { formatDate, formatDateTime } from "../../../app/utils";
import { useAuth } from "../../../app/providers/AuthProvider";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { SearchableSelect } from "../../../components/SearchableSelect";
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
  focusDerived,
}: {
  treatment: TreatmentSummary;
  onSaved: () => Promise<void>;
  focusDerived: boolean;
}) {
  const [form, setForm] = useState<LessonFormState>(() => formFromTreatment(treatment));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionCreated, setActionCreated] = useState(false);
  const lesson = treatment.learned_lesson;
  const { user } = useAuth();
  const canEdit = Boolean(user && treatment.effectiveness_responsible?.id === user.id && (!lesson || lesson.status === "draft"));
  const canCreateDerived = Boolean(user && treatment.effectiveness_responsible?.id === user.id && lesson?.status !== "published" && lesson?.procedure_modified && !actionCreated && !lesson?.derived_actions.some((action) => action.status !== "cancelled"));
  const canPublish = Boolean(user?.access_level === "administrador" && lesson?.status === "ready");
  const [participantOptions, setParticipantOptions] = useState<TreatmentParticipantOption[]>([]);
  const [actionForm, setActionForm] = useState({ title: "", description: "", responsible: "", execution_date: "" });
  const derivedActionRequired = focusDerived && canCreateDerived;

  useEffect(() => {
    if (derivedActionRequired) {
      void fetchTreatmentParticipantOptions(treatment.id).then(setParticipantOptions).catch(() => setParticipantOptions([]));
    }
  }, [derivedActionRequired, treatment.id]);

  useEffect(() => {
    if (!derivedActionRequired) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [derivedActionRequired]);

  const keepDialogFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab") return;
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("input, textarea, select, button:not([disabled])"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  useEffect(() => {
    setForm(formFromTreatment(treatment));
    setActionCreated(Boolean(treatment.learned_lesson?.derived_actions.some((action) => action.status !== "cancelled")));
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
      await onSaved();
      setMessage("Leccion aprendida guardada.");
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

  const runLessonAction = async (kind: "send" | "publish" | "derived") => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (kind === "derived") {
        if (!actionForm.title.trim() || !actionForm.responsible || !actionForm.execution_date) {
          throw new Error("La accion, el responsable y la fecha limite son obligatorios.");
        }
        await createLessonDerivedAction(treatment.id, actionForm);
        setActionCreated(true);
      } else if (kind === "send") {
        await sendTreatmentLessonForPublication(treatment.id);
      } else {
        if (!window.confirm("¿Publicar la leccion y cerrar formalmente el tratamiento?")) return;
        await publishTreatmentLesson(treatment.id);
      }
      await onSaved();
      setMessage(kind === "derived" ? "Accion derivada creada." : kind === "send" ? "Leccion enviada para publicacion." : "Leccion publicada y tratamiento cerrado formalmente.");
      if (kind === "derived") setActionForm({ title: "", description: "", responsible: "", execution_date: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la operacion.");
    } finally {
      setSaving(false);
    }
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
      <div className="learned-lesson-summary" data-tour="lesson-treatment-summary">
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
        <p className="muted-copy">Estado de la leccion: {lesson?.status === "published" ? "Publicada" : lesson?.status === "ready" ? "Lista para publicar" : "Borrador"}. {treatment.formally_closed_at ? `Cierre formal: ${formatDateTime(treatment.formally_closed_at)}` : "Pendiente de cierre formal."}</p>
      </div>

      <form className="learned-lesson-form" onSubmit={handleSubmit}>
        {message ? <div className="panel info compact-inline-panel">{message}</div> : null}
        {error ? <div className="panel danger compact-inline-panel">{error}</div> : null}

        <fieldset disabled={!canEdit || saving}>
        <SearchableSelect className="field" dataTour="lesson-learning-choice" label="Hubo un aprendizaje?" onChange={(value) => updateForm({ hasLearning: value as LessonFormState["hasLearning"] })} options={[{ value: "yes", label: "Si" }, { value: "no", label: "No" }]} placeholder="Seleccionar..." value={form.hasLearning} />

        {form.hasLearning === "yes" ? (
          <>
            <label className="field" data-tour="lesson-learning-text">
              <span>Que se aprendio?</span>
              <textarea value={form.learnedText} onChange={(event) => updateForm({ learnedText: event.target.value })} />
            </label>
            <label className="field" data-tour="lesson-evidence">
              <span>Evidencia objetiva</span>
              <input multiple type="file" onChange={handleFiles} />
            </label>
          </>
        ) : null}

        {form.hasLearning === "no" ? (
          <label className="field" data-tour="lesson-no-learning">
            <span>Por que no se aprendio?</span>
            <textarea value={form.noLearningReason} onChange={(event) => updateForm({ noLearningReason: event.target.value })} />
          </label>
        ) : null}

        <SearchableSelect className="field" dataTour="lesson-procedure-choice" label="Modifica procedimiento?" onChange={(value) => updateForm({ procedureModified: value as LessonFormState["procedureModified"] })} options={[{ value: "yes", label: "Si" }, { value: "no", label: "No" }]} placeholder="Seleccionar..." value={form.procedureModified} />

        {form.procedureModified === "yes" ? (
          <label className="field" data-tour="lesson-procedure-detail">
            <span>Observaciones sobre modificacion de procedimiento</span>
            <textarea value={form.procedureModificationNotes} onChange={(event) => updateForm({ procedureModificationNotes: event.target.value })} />
          </label>
        ) : null}

        {lesson?.evidences.length ? (
          <div className="form-section" data-tour="lesson-files">
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

        <div className="form-actions" data-tour="lesson-save">
          <button className="button button-primary" type="submit">
            Guardar cambios
          </button>
        </div>
        </fieldset>
      </form>

      {derivedActionRequired ? createPortal(
        <div className="learned-lesson-action-overlay">
        <div aria-describedby="derived-action-instructions" aria-labelledby="derived-action-title" aria-modal="true" className="panel form-section learned-lesson-derived-action learned-lesson-action-dialog" onKeyDown={keepDialogFocus} role="dialog">
          <strong id="derived-action-title">Accion derivada de Leccion Aprendida · {treatment.code}</strong>
          <p className="muted-copy" id="derived-action-instructions">Se modifico un procedimiento. Cree la accion derivada para continuar. Mientras tanto, el resto de la pantalla esta bloqueado; puede consultar la ayuda.</p>
          {error ? <div className="panel danger compact-inline-panel">{error}</div> : null}
          <label className="field"><span>Accion</span><input autoFocus value={actionForm.title} onChange={(event) => setActionForm((current) => ({ ...current, title: event.target.value }))} /></label>
          <label className="field"><span>Descripcion</span><textarea value={actionForm.description} onChange={(event) => setActionForm((current) => ({ ...current, description: event.target.value }))} /></label>
          <SearchableSelect className="field" label="Responsable" onChange={(value) => setActionForm((current) => ({ ...current, responsible: value }))} options={participantOptions.map((option) => ({ value: option.id, label: option.full_name || option.username }))} placeholder="Seleccionar..." value={actionForm.responsible} />
          <label className="field"><span>Fecha limite de realizacion</span><input type="date" value={actionForm.execution_date} onChange={(event) => setActionForm((current) => ({ ...current, execution_date: event.target.value }))} /></label>
          <div className="form-actions">
            <button className="button button-secondary" onClick={() => window.dispatchEvent(new Event("calidad:open-context-help"))} type="button">Ayuda</button>
            <button className="button button-primary" disabled={saving} onClick={() => void runLessonAction("derived")} type="button">Crear accion derivada</button>
          </div>
        </div>
        </div>, document.body,
      ) : null}
      {lesson?.derived_actions?.length ? <div className="form-section" data-tour="lesson-derived-list"><strong>Acciones derivadas</strong>{lesson.derived_actions.map((action) => <div className="list-card compact" key={action.id}>{action.code} · {action.title} · {action.responsible?.full_name || "-"} · fecha limite {formatDate(action.execution_date)} · {action.status}</div>)}</div> : null}
      {canEdit && lesson ? <button className="button button-secondary" data-tour="lesson-send" disabled={saving} onClick={() => void runLessonAction("send")} type="button">Enviar para publicacion</button> : null}
      {canPublish ? <button className="button button-primary" data-tour="lesson-publish" disabled={saving} onClick={() => void runLessonAction("publish")} type="button">PUBLICAR</button> : null}

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
      <div className="learned-lesson-summary" data-tour="lesson-observation-summary">
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

        <SearchableSelect className="field" dataTour="lesson-learning-choice" label="Hubo un aprendizaje?" onChange={(value) => updateForm({ hasLearning: value as LessonFormState["hasLearning"] })} options={[{ value: "yes", label: "Si" }, { value: "no", label: "No" }]} placeholder="Seleccionar..." value={form.hasLearning} />

        {form.hasLearning === "yes" ? (
          <>
            <label className="field" data-tour="lesson-learning-text">
              <span>Que se aprendio?</span>
              <textarea value={form.learnedText} onChange={(event) => updateForm({ learnedText: event.target.value })} />
            </label>
            <label className="field" data-tour="lesson-evidence">
              <span>Evidencia objetiva</span>
              <input multiple type="file" onChange={handleFiles} />
            </label>
          </>
        ) : null}

        {form.hasLearning === "no" ? (
          <label className="field" data-tour="lesson-no-learning">
            <span>Por que no se aprendio?</span>
            <textarea value={form.noLearningReason} onChange={(event) => updateForm({ noLearningReason: event.target.value })} />
          </label>
        ) : null}

        <SearchableSelect className="field" dataTour="lesson-procedure-choice" label="Modifica procedimiento?" onChange={(value) => updateForm({ procedureModified: value as LessonFormState["procedureModified"] })} options={[{ value: "yes", label: "Si" }, { value: "no", label: "No" }]} placeholder="Seleccionar..." value={form.procedureModified} />

        {form.procedureModified === "yes" ? (
          <label className="field" data-tour="lesson-procedure-detail">
            <span>Observaciones sobre modificacion de procedimiento</span>
            <textarea value={form.procedureModificationNotes} onChange={(event) => updateForm({ procedureModificationNotes: event.target.value })} />
          </label>
        ) : null}

        {item.learning?.evidences.length ? (
          <div className="form-section" data-tour="lesson-files">
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
        <div className="form-actions" data-tour="lesson-observation-save">
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
  const { user } = useAuth();
  const [source, setSource] = useState<"treatments" | "observations">("treatments");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedTreatmentId, setSelectedTreatmentId] = useState("");
  const [selectedObservationId, setSelectedObservationId] = useState("");

  const treatmentTask = useAsyncTask(() => fetchLearnedLessons(page, search), [page, search]);
  const observationTask = useAsyncTask(() => fetchObservationLearnedLessons(page, search), [page, search]);
  const treatments = treatmentTask.data?.results ?? [];
  const observations = observationTask.data?.results ?? [];
  const selectedTreatment = treatments.find((item) => item.id === selectedTreatmentId) ?? treatments[0] ?? null;
  const selectedObservation = observations.find((item) => item.id === selectedObservationId) ?? observations[0] ?? null;
  const focusDerivedTreatmentId = treatments.find((treatment) =>
    user?.id === treatment.effectiveness_responsible?.id &&
    treatment.learned_lesson?.procedure_modified &&
    treatment.learned_lesson.status !== "published" &&
    !treatment.learned_lesson.derived_actions.some((action) => action.status !== "cancelled")
  )?.id;

  const changeSource = (nextSource: "treatments" | "observations") => {
    setSource(nextSource);
    setPage(1);
  };

  useEffect(() => {
    if (treatments.length && !treatments.some((item) => item.id === selectedTreatmentId)) {
      setSelectedTreatmentId(treatments[0].id);
    }
  }, [treatments, selectedTreatmentId]);

  useEffect(() => {
    if (observations.length && !observations.some((item) => item.id === selectedObservationId)) {
      setSelectedObservationId(observations[0].id);
    }
  }, [observations, selectedObservationId]);

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
          <div className="lessons-workspace">
            <section className="panel lessons-directory">
              <div className="section-head compact"><div><p className="eyebrow">Tratamientos</p><h2>Lecciones</h2></div></div>
              <div className="stack-list lessons-directory-list">
                {treatments.map((treatment) => {
                  const lesson = treatment.learned_lesson;
                  const status = lesson?.status === "published" ? "Publicada" : lesson?.status === "ready" ? "Lista para publicar" : lesson ? "Borrador" : "Pendiente de carga";
                  return <button className={`list-card selectable-card lesson-directory-card${selectedTreatment?.id === treatment.id ? " active" : ""}`} key={treatment.id} onClick={() => setSelectedTreatmentId(treatment.id)} type="button"><div><strong>{treatment.code}</strong><span>{treatment.primary_anomaly.code} · {treatment.primary_anomaly.title}</span><small>{treatment.effectiveness_responsible?.full_name || treatment.effectiveness_responsible?.username || "Sin responsable"}</small></div><span className={`status-pill lesson-status ${lesson?.status || "pending"}`}>{status}</span></button>;
                })}
              </div>
            </section>
            <section className="lessons-detail">
              {selectedTreatment ? <LearnedLessonCard focusDerived={selectedTreatment.id === focusDerivedTreatmentId} treatment={selectedTreatment} onSaved={treatmentTask.reload} /> : <div className="panel muted">Selecciona una lección para revisar su detalle.</div>}
            </section>
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
          <div className="lessons-workspace">
            <section className="panel lessons-directory">
              <div className="section-head compact"><div><p className="eyebrow">Observaciones</p><h2>Lecciones</h2></div></div>
              <div className="stack-list lessons-directory-list">
                {observations.map((item) => <button className={`list-card selectable-card lesson-directory-card${selectedObservation?.id === item.id ? " active" : ""}`} key={item.id} onClick={() => setSelectedObservationId(item.id)} type="button"><div><strong>{item.code}</strong><span>{item.title}</span><small>{item.responsible?.full_name || item.responsible?.username || "Sin responsable"}</small></div><span className={`status-pill lesson-status ${item.learning ? "draft" : "pending"}`}>{item.learning ? "Registrada" : "Pendiente de carga"}</span></button>)}
              </div>
            </section>
            <section className="lessons-detail">
              {selectedObservation ? <ObservationLearnedLessonCard item={selectedObservation} onSaved={observationTask.reload} /> : <div className="panel muted">Selecciona una lección para revisar su detalle.</div>}
            </section>
          </div>
          <PaginationControls page={page} totalCount={observationTask.data?.count ?? 0} onPageChange={setPage} disabled={observationTask.loading} />
        </DataState>
      )}
    </section>
  );
}
