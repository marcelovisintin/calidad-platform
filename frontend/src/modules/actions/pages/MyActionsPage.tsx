import { FormEvent, KeyboardEvent, MouseEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { fetchUsers } from "../../../api/accounts";
import { fetchActionWorkItems } from "../../../api/actions";
import { completeObservationAction } from "../../../api/anomalies";
import { normalizeProtectedFileUrl, openAuthenticatedFile } from "../../../api/files";
import { addTreatmentTaskEvidence, updateTreatmentTask } from "../../../api/treatments";
import type { ActionWorkItem, ActionWorkItemSource } from "../../../api/types";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { resolveTaskHelpWorkContext, usePublishHelpWorkContext } from "../../help/workContext";

type TaskDraft = {
  title: string;
  description: string;
  responsible: string;
  execution_date: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  anomaly_ids: string[];
};

const TASK_STATUS_OPTIONS = [
  { value: "pending", label: "Pendiente" },
  { value: "in_progress", label: "En curso" },
  { value: "completed", label: "Completada" },
  { value: "cancelled", label: "Cancelada" },
] as const;

const EVIDENCE_ACCEPT = "image/*,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf,.odt,.ods,.zip";
const EMPTY_TASK_DRAFT: TaskDraft = {
  title: "",
  description: "",
  responsible: "",
  execution_date: "",
  status: "pending",
  anomaly_ids: [],
};

function getUserLabel(user: { full_name?: string; username: string }) {
  return user.full_name?.trim() || user.username;
}

function getWorkItemKey(item: Pick<ActionWorkItem, "id" | "source">) {
  return `${item.source}:${item.id}`;
}

function getTodayInputValue() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function SourceBadge({ source }: { source: ActionWorkItemSource }) {
  return (
    <span className={`action-source-badge ${source}`}>
      {source === "treatment" ? "Tratamiento" : "Observacion"}
    </span>
  );
}

export function MyActionsPage() {
  usePageTitle("Acciones");

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [anomalyFilter, setAnomalyFilter] = useState("");
  const [treatmentFilter, setTreatmentFilter] = useState("");
  const [completedOn, setCompletedOn] = useState("");
  const [responsibleFilter, setResponsibleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showTreatmentActions, setShowTreatmentActions] = useState(true);
  const [showObservationActions, setShowObservationActions] = useState(true);
  const [selectedWorkItemKey, setSelectedWorkItemKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [statusEvidenceError, setStatusEvidenceError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK_DRAFT);
  const [taskEvidenceFile, setTaskEvidenceFile] = useState<File | null>(null);
  const [taskEvidenceNote, setTaskEvidenceNote] = useState("");
  const [taskStatusEvidenceNote, setTaskStatusEvidenceNote] = useState("");
  const [taskEvidenceInputKey, setTaskEvidenceInputKey] = useState(0);
  const [observationCompletedAt, setObservationCompletedAt] = useState(getTodayInputValue());

  const deferredQuery = useDeferredValue(query);
  const deferredAnomalyFilter = useDeferredValue(anomalyFilter);
  const deferredTreatmentFilter = useDeferredValue(treatmentFilter);
  const selectedSources = useMemo<ActionWorkItemSource[]>(() => {
    const sources: ActionWorkItemSource[] = [];
    if (showTreatmentActions) sources.push("treatment");
    if (showObservationActions) sources.push("observation");
    return sources;
  }, [showObservationActions, showTreatmentActions]);

  const {
    data: usersData,
    loading: usersLoading,
    error: usersError,
    reload: reloadUsers,
  } = useAsyncTask(() => fetchUsers({ page: 1, pageSize: 100 }), []);

  const { data, loading, error, reload } = useAsyncTask(
    () => fetchActionWorkItems({
      page,
      q: deferredQuery,
      anomaly: deferredAnomalyFilter,
      treatment: deferredTreatmentFilter,
      completedOn,
      responsible: responsibleFilter,
      status: statusFilter,
      sources: selectedSources,
    }),
    [page, deferredQuery, deferredAnomalyFilter, deferredTreatmentFilter, completedOn, responsibleFilter, statusFilter, selectedSources],
  );

  const selectedWorkItem = useMemo(
    () => data?.results.find((item) => getWorkItemKey(item) === selectedWorkItemKey) ?? null,
    [data?.results, selectedWorkItemKey],
  );
  usePublishHelpWorkContext(selectedWorkItem ? resolveTaskHelpWorkContext(selectedWorkItem) : null);

  useEffect(() => {
    const firstKey = data?.results?.[0] ? getWorkItemKey(data.results[0]) : "";
    if (!data?.results?.length) {
      setSelectedWorkItemKey("");
      return;
    }
    if (!selectedWorkItemKey || !data.results.some((item) => getWorkItemKey(item) === selectedWorkItemKey)) {
      setSelectedWorkItemKey(firstKey);
    }
  }, [data?.results, selectedWorkItemKey]);

  useEffect(() => {
    if (!selectedWorkItem) {
      setTaskDraft(EMPTY_TASK_DRAFT);
      return;
    }
    setTaskDraft({
      title: selectedWorkItem.title,
      description: selectedWorkItem.description || "",
      responsible: selectedWorkItem.responsible?.id || "",
      execution_date: selectedWorkItem.due_date || "",
      status: selectedWorkItem.status,
      anomaly_ids: selectedWorkItem.anomalies.map((item) => item.id),
    });
    setTaskEvidenceFile(null);
    setTaskEvidenceNote("");
    setTaskStatusEvidenceNote("");
    setStatusEvidenceError(null);
    setTaskEvidenceInputKey((current) => current + 1);
    setObservationCompletedAt(selectedWorkItem.completed_on || getTodayInputValue());
  }, [selectedWorkItem?.id, selectedWorkItem?.source, selectedWorkItem?.updated_at]);

  const handleTaskDraftChange = <K extends keyof TaskDraft>(field: K, value: TaskDraft[K]) => {
    setTaskDraft((current) => ({ ...current, [field]: value }));
  };

  const runMutation = async (task: () => Promise<void>, successMessage: string) => {
    setBusy(true);
    setFormError(null);
    setMessage(null);
    try {
      await task();
      setMessage(successMessage);
      setStatusEvidenceError(null);
      await reload();
    } catch (mutationError) {
      const mutationMessage = mutationError instanceof Error ? mutationError.message : "No se pudo guardar la accion.";
      if (mutationMessage.toLowerCase().startsWith("evidence_note:")) {
        setStatusEvidenceError(mutationMessage.replace(/^evidence_note:\s*/i, ""));
      } else {
        setFormError(mutationMessage);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleUpdateTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorkItem || selectedWorkItem.source !== "treatment") return;
    if (!selectedWorkItem.can_update_status) {
      setFormError("No tienes permisos para actualizar esta tarea.");
      return;
    }
    if (!selectedWorkItem.treatment?.id) {
      setFormError("No se encontro el tratamiento asociado a la tarea.");
      return;
    }
    if (selectedWorkItem.can_manage && !taskDraft.title.trim()) {
      setFormError("El titulo de la tarea es obligatorio.");
      return;
    }
    const statusChanged = taskDraft.status !== selectedWorkItem.status;
    if (statusChanged && !taskStatusEvidenceNote.trim()) {
      setFormError(null);
      setStatusEvidenceError("Debes cargar una nota de evidencia para cambiar el estado de la tarea.");
      return;
    }

    await runMutation(async () => {
      await updateTreatmentTask(
        selectedWorkItem.treatment!.id,
        selectedWorkItem.id,
        selectedWorkItem.can_manage
          ? {
              title: taskDraft.title.trim(),
              description: taskDraft.description.trim(),
              responsible: taskDraft.responsible || null,
              execution_date: taskDraft.execution_date || null,
              status: taskDraft.status,
              evidence_note: statusChanged ? taskStatusEvidenceNote.trim() : undefined,
              root_cause_ids: selectedWorkItem.root_causes.map((cause) => cause.id),
              anomaly_ids: taskDraft.anomaly_ids,
            }
          : {
              status: taskDraft.status,
              evidence_note: statusChanged ? taskStatusEvidenceNote.trim() : undefined,
            },
      );
      setTaskStatusEvidenceNote("");
    }, "Tarea actualizada.");
  };

  const handleCompleteObservation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorkItem || selectedWorkItem.source !== "observation") return;
    if (!selectedWorkItem.can_update_status) {
      setFormError("No tienes permisos para finalizar esta accion de Observacion.");
      return;
    }
    const anomalyId = selectedWorkItem.anomalies[0]?.id;
    if (!anomalyId || !observationCompletedAt) {
      setFormError("Debe indicar la fecha real de finalizacion.");
      return;
    }
    await runMutation(
      () => completeObservationAction(anomalyId, selectedWorkItem.id, observationCompletedAt).then(() => undefined),
      "Accion de Observacion finalizada.",
    );
  };

  const handleOpenEvidence = async (event: MouseEvent<HTMLAnchorElement>, fileUrl: string, fallbackName: string) => {
    event.preventDefault();
    try {
      await openAuthenticatedFile(fileUrl, fallbackName);
    } catch (openError) {
      setFormError(openError instanceof Error ? openError.message : "No se pudo abrir la evidencia.");
    }
  };

  const handleAddTaskEvidence = async () => {
    if (!selectedWorkItem || selectedWorkItem.source !== "treatment") return;
    if (!selectedWorkItem.can_add_evidence || !selectedWorkItem.treatment?.id) {
      setFormError("No tienes permisos para cargar evidencias en esta tarea.");
      return;
    }
    if (!taskEvidenceFile) {
      setFormError("Debes seleccionar una evidencia para cargar en la tarea.");
      return;
    }
    await runMutation(async () => {
      await addTreatmentTaskEvidence(selectedWorkItem.treatment!.id, selectedWorkItem.id, {
        file: taskEvidenceFile,
        note: taskEvidenceNote,
      });
      setTaskEvidenceFile(null);
      setTaskEvidenceNote("");
      setTaskEvidenceInputKey((current) => current + 1);
    }, "Evidencia cargada en la tarea.");
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>, item: ActionWorkItem) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelectedWorkItemKey(getWorkItemKey(item));
    }
  };

  const clearFilters = () => {
    setQuery("");
    setAnomalyFilter("");
    setTreatmentFilter("");
    setStatusFilter("");
    setCompletedOn("");
    setResponsibleFilter("");
    setShowTreatmentActions(true);
    setShowObservationActions(true);
    setPage(1);
  };

  const totalCount = data?.count ?? 0;
  const noSourcesSelected = !showTreatmentActions && !showObservationActions;
  const selectedIsTerminal = selectedWorkItem?.status === "completed" || selectedWorkItem?.status === "cancelled";

  return (
    <section className="page-shell">
      <PageHeader title="Acciones" description="Acciones de Tratamientos y Observaciones, en cualquier estado, segun tu nivel de acceso." />

      <section className="panel action-source-selector" aria-label="Origen de las acciones">
        <div>
          <p className="eyebrow">Mostrar acciones provenientes de</p>
          <p className="muted-copy">Activa o desactiva cada origen de manera independiente.</p>
        </div>
        <div className="action-source-options">
          <label className="checkbox-inline">
            <input
              checked={showTreatmentActions}
              onChange={(event) => {
                setShowTreatmentActions(event.target.checked);
                if (!event.target.checked) setTreatmentFilter("");
                setPage(1);
              }}
              type="checkbox"
            />
            Tratamientos
          </label>
          <label className="checkbox-inline">
            <input checked={showObservationActions} onChange={(event) => { setShowObservationActions(event.target.checked); setPage(1); }} type="checkbox" />
            Observaciones
          </label>
        </div>
      </section>

      <TabbedFilters
        ariaLabel="Filtros de acciones"
        onClear={clearFilters}
        items={[
          { id: "search", label: "Buscar", active: Boolean(query), content: <input aria-label="Buscar" onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Codigo, detalle, anomalia o usuario" type="search" value={query} /> },
          { id: "anomaly", label: "Anomalia", active: Boolean(anomalyFilter), content: <input aria-label="Anomalia" onChange={(event) => { setAnomalyFilter(event.target.value); setPage(1); }} placeholder="Codigo o titulo de anomalia" type="text" value={anomalyFilter} /> },
          { id: "treatment", label: "Tratamiento", active: Boolean(treatmentFilter), content: <input aria-label="Tratamiento" disabled={!showTreatmentActions} onChange={(event) => { setTreatmentFilter(event.target.value); setPage(1); }} placeholder="Codigo de tratamiento" type="text" value={treatmentFilter} /> },
          {
            id: "status",
            label: "Estado",
            active: Boolean(statusFilter),
            content: (
              <select aria-label="Estado" onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} value={statusFilter}>
                <option value="">Todos los estados</option>
                <option value="pending">Pendiente</option>
                <option value="in_progress">En curso</option>
                <option value="completed">Completada</option>
                <option value="cancelled">Cancelada</option>
                <option value="overdue">Vencida</option>
              </select>
            ),
          },
          { id: "completed", label: "Fecha terminada", active: Boolean(completedOn), content: <input aria-label="Fecha terminada" onChange={(event) => { setCompletedOn(event.target.value); setPage(1); }} type="date" value={completedOn} /> },
          {
            id: "responsible",
            label: "Responsable",
            active: Boolean(responsibleFilter),
            content: (
              <select aria-label="Responsable" onChange={(event) => { setResponsibleFilter(event.target.value); setPage(1); }} value={responsibleFilter}>
                <option value="">Todos</option>
                {(usersData?.results ?? []).map((item) => <option key={item.id} value={item.id}>{getUserLabel(item)}</option>)}
              </select>
            ),
          },
        ]}
      />

      {usersError ? <div className="panel warning compact-inline-panel"><p>No se pudo cargar el listado de usuarios para filtrar.</p><button className="button button-secondary" onClick={() => void reloadUsers()} type="button">Reintentar</button></div> : null}
      {message ? <div className="panel">{message}</div> : null}
      {formError ? <div className="panel danger">{formError}</div> : null}

      <DataState
        loading={loading || usersLoading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle={noSourcesSelected ? "No hay origenes seleccionados" : "No hay acciones visibles"}
        emptyDescription={noSourcesSelected ? "Selecciona Tratamientos, Observaciones o ambos para mostrar acciones." : "No se encontraron acciones con los filtros seleccionados."}
      >
        <div className="user-management-grid actions-two-column">
        {selectedWorkItem?.source === "observation" ? (
          <section className="panel action-detail-fixed">
            <div className="section-head compact"><div><SourceBadge source={selectedWorkItem.source} /><h2>{selectedWorkItem.code}</h2></div><StatusBadge value={selectedWorkItem.is_overdue ? "overdue" : selectedWorkItem.status} /></div>
            <p>{selectedWorkItem.description}</p>
            <dl className="key-grid compact">
              <div><dt>Anomalia</dt><dd>{selectedWorkItem.anomalies.map((item) => item.code).join(", ")}</dd></div>
              <div><dt>Responsable</dt><dd>{selectedWorkItem.responsible ? getUserLabel(selectedWorkItem.responsible) : "Sin asignar"}</dd></div>
              <div><dt>Fecha estimada</dt><dd>{formatDate(selectedWorkItem.due_date)}</dd></div>
              <div><dt>Verificacion estimada</dt><dd>{formatDate(selectedWorkItem.effectiveness_due_date)}</dd></div>
              <div><dt>Fecha terminada</dt><dd>{formatDate(selectedWorkItem.completed_on)}</dd></div>
              <div><dt>Finalizada por</dt><dd>{selectedWorkItem.completed_by ? getUserLabel(selectedWorkItem.completed_by) : "-"}</dd></div>
            </dl>
            {!selectedIsTerminal && selectedWorkItem.can_update_status ? (
              <form className="form-section nested-form" onSubmit={handleCompleteObservation}>
                <div className="section-head compact"><h3>Finalizar accion</h3><button className="button button-primary" disabled={busy || !observationCompletedAt} type="submit">Marcar como finalizada</button></div>
                <label className="field"><span>Fecha real de finalizacion</span><input onChange={(event) => setObservationCompletedAt(event.target.value)} required type="date" value={observationCompletedAt} /></label>
              </form>
            ) : !selectedIsTerminal ? <div className="panel info compact-inline-panel"><p>Esta accion se muestra en modo consulta. Solo el responsable autorizado puede finalizarla.</p></div> : null}
          </section>
        ) : null}

        {selectedWorkItem?.source === "treatment" ? (
          <section className="panel action-detail-fixed">
            <div className="section-head compact"><div><SourceBadge source={selectedWorkItem.source} /><h2>{`${selectedIsTerminal ? "Detalle" : "Editar tarea"} | ${selectedWorkItem.code || selectedWorkItem.title}`}</h2></div><StatusBadge value={selectedWorkItem.is_overdue ? "overdue" : selectedWorkItem.status} /></div>
            <p className="muted-copy">Tratamiento: {selectedWorkItem.treatment?.code || "Sin tratamiento"} | Anomalias: {selectedWorkItem.anomalies.map((item) => item.code).join(", ") || "Sin asociar"}</p>
            <dl className="key-grid compact">
              <div><dt>Estado tratamiento</dt><dd>{selectedWorkItem.treatment?.status || "-"}</dd></div>
              <div><dt>Fecha de ejecucion</dt><dd>{formatDate(selectedWorkItem.due_date)}</dd></div>
              <div><dt>Causas raiz</dt><dd>{selectedWorkItem.root_causes.length ? selectedWorkItem.root_causes.map((cause) => `Causa ${cause.sequence}: ${cause.description}`).join(" | ") : "Sin causa raiz"}</dd></div>
              <div><dt>Responsable actual</dt><dd>{selectedWorkItem.responsible ? getUserLabel(selectedWorkItem.responsible) : "Sin asignar"}</dd></div>
              <div><dt>Fecha terminada</dt><dd>{formatDate(selectedWorkItem.completed_on)}</dd></div>
            </dl>
            {!selectedIsTerminal ? (
              <form className="form-section nested-form" onSubmit={handleUpdateTask}>
                <div className="section-head compact"><h3>Datos de la tarea</h3><div className="task-save-controls">{statusEvidenceError ? <span className="inline-form-alert" role="alert">{statusEvidenceError}</span> : null}<button className="button button-primary" disabled={busy || !selectedWorkItem.can_update_status} type="submit">Guardar tarea</button></div></div>
                <div className="form-grid">
                  <label className="field"><span>Titulo</span><input disabled={!selectedWorkItem.can_manage || !selectedWorkItem.can_update_status} onChange={(event) => handleTaskDraftChange("title", event.target.value)} required type="text" value={taskDraft.title} /></label>
                  <label className="field"><span>Estado</span><select disabled={!selectedWorkItem.can_update_status} onChange={(event) => handleTaskDraftChange("status", event.target.value as TaskDraft["status"])} value={taskDraft.status}>{TASK_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                  <label className="field"><span>Responsable</span><select disabled={!selectedWorkItem.can_manage || !selectedWorkItem.can_update_status} onChange={(event) => handleTaskDraftChange("responsible", event.target.value)} value={taskDraft.responsible}><option value="">Sin asignar</option>{(usersData?.results ?? []).map((user) => <option key={user.id} value={user.id}>{getUserLabel(user)}</option>)}</select></label>
                  <label className="field"><span>Fecha ejecucion</span><input disabled={!selectedWorkItem.can_manage || !selectedWorkItem.can_update_status} onChange={(event) => handleTaskDraftChange("execution_date", event.target.value)} type="date" value={taskDraft.execution_date} /></label>
                </div>
                <label className="field"><span>Descripcion</span><textarea disabled={!selectedWorkItem.can_manage || !selectedWorkItem.can_update_status} onChange={(event) => handleTaskDraftChange("description", event.target.value)} rows={3} value={taskDraft.description} /></label>
                {taskDraft.status !== selectedWorkItem.status ? <label className="field"><span>Nota de evidencia del cambio de estado</span><textarea onChange={(event) => setTaskStatusEvidenceNote(event.target.value)} required rows={3} value={taskStatusEvidenceNote} /></label> : null}
              </form>
            ) : null}
            <section className="form-section nested-form">
              <div className="section-head compact"><h3>Evidencias de la tarea</h3>{!selectedIsTerminal ? <button className="button button-primary" disabled={busy || !selectedWorkItem.can_add_evidence || !taskEvidenceFile} onClick={() => void handleAddTaskEvidence()} type="button">Cargar evidencia</button> : null}</div>
              {!selectedIsTerminal ? <div className="form-grid"><label className="field field-span-2"><span>Archivo</span><input accept={EVIDENCE_ACCEPT} disabled={!selectedWorkItem.can_add_evidence} key={taskEvidenceInputKey} onChange={(event) => setTaskEvidenceFile(event.target.files?.[0] ?? null)} type="file" /></label><label className="field field-span-2"><span>Nota de evidencia (opcional)</span><textarea disabled={!selectedWorkItem.can_add_evidence} onChange={(event) => setTaskEvidenceNote(event.target.value)} rows={3} value={taskEvidenceNote} /></label></div> : null}
              <div className="stack-list compact">
                {selectedWorkItem.evidences.length ? selectedWorkItem.evidences.map((evidence) => <div className="list-card compact" key={evidence.id}><div className="evidence-block"><a href={normalizeProtectedFileUrl(evidence.file_url)} onClick={(event) => void handleOpenEvidence(event, evidence.file_url, evidence.original_name)} rel="noopener noreferrer" target="_blank">{evidence.original_name}</a><small>{formatDateTime(evidence.created_at)}</small><p>{evidence.note || "Sin nota"}</p></div></div>) : <p className="muted-copy">Todavia no hay evidencias cargadas en esta tarea.</p>}
              </div>
            </section>
          </section>
        ) : null}

        <section className="panel action-list-column">
          <div className="section-head compact">
            <div><p className="eyebrow">Acciones</p><h2>Todos los estados</h2></div>
          </div>
        <div className="stack-list action-work-list">
          {data?.results.map((item) => {
            const key = getWorkItemKey(item);
            return (
              <article className={`panel action-card work-list-card${selectedWorkItemKey === key ? " active" : ""}`} key={key} onClick={() => setSelectedWorkItemKey(key)} onKeyDown={(event) => handleCardKeyDown(event, item)} role="button" tabIndex={0}>
                <div className="section-head compact work-card-header"><div className="work-card-main"><div className="work-card-heading"><SourceBadge source={item.source} /><strong>{item.code || item.title}</strong><span>{item.title}</span></div><small>{item.description || "Sin descripcion."}</small><div className="work-card-meta"><small>Fecha prevista: {formatDate(item.due_date)}</small><small>Responsable: {item.responsible ? getUserLabel(item.responsible) : "Sin asignar"}</small></div></div><StatusBadge value={item.is_overdue ? "overdue" : item.status} /></div>
              </article>
            );
          })}
        </div>
        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading || busy} />
        </section>
        </div>
      </DataState>
    </section>
  );
}
