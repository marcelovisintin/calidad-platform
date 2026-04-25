import { ChangeEvent, FormEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { fetchUsers } from "../../../api/accounts";
import { addTreatmentTaskEvidence, fetchTreatmentTasksHistory, updateTreatmentTask } from "../../../api/treatments";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

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

function getEvidenceUrl(fileUrl?: string) {
  if (!fileUrl) {
    return "#";
  }
  if (fileUrl.startsWith("http://") || fileUrl.startsWith("https://") || fileUrl.startsWith("/")) {
    return fileUrl;
  }
  return `/${fileUrl}`;
}

export function MyActionsPage() {
  usePageTitle("Acciones y pendientes");

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [anomalyFilter, setAnomalyFilter] = useState("");
  const [treatmentFilter, setTreatmentFilter] = useState("");
  const [completedOn, setCompletedOn] = useState("");
  const [performedBy, setPerformedBy] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK_DRAFT);
  const [taskEvidenceFile, setTaskEvidenceFile] = useState<File | null>(null);
  const [taskEvidenceNote, setTaskEvidenceNote] = useState("");
  const [taskEvidenceInputKey, setTaskEvidenceInputKey] = useState(0);

  const deferredQuery = useDeferredValue(query);
  const deferredAnomalyFilter = useDeferredValue(anomalyFilter);
  const deferredTreatmentFilter = useDeferredValue(treatmentFilter);

  const {
    data: usersData,
    loading: usersLoading,
    error: usersError,
    reload: reloadUsers,
  } = useAsyncTask(() => fetchUsers({ page: 1, pageSize: 100 }), []);

  const {
    data,
    loading,
    error,
    reload,
  } = useAsyncTask(
    () =>
      fetchTreatmentTasksHistory({
        page,
        q: deferredQuery,
        anomaly: deferredAnomalyFilter,
        treatment: deferredTreatmentFilter,
        completedOn,
        performedBy,
        status: statusFilter,
      }),
    [page, deferredQuery, deferredAnomalyFilter, deferredTreatmentFilter, completedOn, performedBy, statusFilter],
  );

  const selectedTask = useMemo(
    () => data?.results.find((item) => item.id === selectedTaskId) ?? null,
    [data?.results, selectedTaskId],
  );

  useEffect(() => {
    const firstId = data?.results?.[0]?.id || "";
    if (!data?.results?.length) {
      setSelectedTaskId("");
      return;
    }

    if (!selectedTaskId) {
      setSelectedTaskId(firstId);
      return;
    }

    if (!data.results.some((item) => item.id === selectedTaskId)) {
      setSelectedTaskId(firstId);
    }
  }, [data?.results, selectedTaskId]);

  useEffect(() => {
    if (!selectedTask) {
      setTaskDraft(EMPTY_TASK_DRAFT);
      setTaskEvidenceFile(null);
      setTaskEvidenceNote("");
      setTaskEvidenceInputKey((current) => current + 1);
      return;
    }

    setTaskDraft({
      title: selectedTask.title,
      description: selectedTask.description || "",
      responsible: selectedTask.responsible?.id || "",
      execution_date: selectedTask.execution_date || "",
      status: selectedTask.status as TaskDraft["status"],
      anomaly_ids: selectedTask.anomalies.map((item) => item.id),
    });
    setTaskEvidenceFile(null);
    setTaskEvidenceNote("");
    setTaskEvidenceInputKey((current) => current + 1);
  }, [selectedTask?.id, selectedTask?.updated_at]);

  const handleTaskDraftChange = <K extends keyof TaskDraft>(field: K, value: TaskDraft[K]) => {
    setTaskDraft((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const runMutation = async (task: () => Promise<void>, successMessage: string) => {
    setBusy(true);
    setFormError(null);
    setMessage(null);
    try {
      await task();
      setMessage(successMessage);
      await reload();
    } catch (mutationError) {
      const mutationMessage = mutationError instanceof Error ? mutationError.message : "No se pudo guardar la tarea.";
      setFormError(mutationMessage);
    } finally {
      setBusy(false);
    }
  };

  const handleUpdateTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTask) {
      return;
    }

    if (!selectedTask.treatment?.id) {
      setFormError("No se encontro el tratamiento asociado a la tarea.");
      return;
    }

    if (!taskDraft.title.trim()) {
      setFormError("El titulo de la tarea es obligatorio.");
      return;
    }

    await runMutation(
      async () => {
        await updateTreatmentTask(selectedTask.treatment.id, selectedTask.id, {
          title: taskDraft.title.trim(),
          description: taskDraft.description.trim(),
          responsible: taskDraft.responsible || null,
          execution_date: taskDraft.execution_date || null,
          status: taskDraft.status,
          root_cause: selectedTask.root_cause?.id || null,
          anomaly_ids: taskDraft.anomaly_ids,
        });
      },
      "Tarea actualizada.",
    );
  };

  const handleTaskEvidenceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null;
    setTaskEvidenceFile(selectedFile);
  };

  const handleAddTaskEvidence = async () => {
    if (!selectedTask) {
      return;
    }

    if (!selectedTask.treatment?.id) {
      setFormError("No se encontro el tratamiento asociado a la tarea.");
      return;
    }

    if (!taskEvidenceFile) {
      setFormError("Debes seleccionar una evidencia para cargar en la tarea.");
      return;
    }

    await runMutation(
      async () => {
        await addTreatmentTaskEvidence(selectedTask.treatment.id, selectedTask.id, {
          file: taskEvidenceFile,
          note: taskEvidenceNote,
        });
        setTaskEvidenceFile(null);
        setTaskEvidenceNote("");
        setTaskEvidenceInputKey((current) => current + 1);
      },
      "Evidencia cargada en la tarea.",
    );
  };

  const totalCount = data?.count ?? 0;

  return (
    <section className="page-shell">
      <PageHeader
        title="Acciones y pendientes"
        description="Listado historico de tareas con filtros por anomalia, tratamiento, estado, fecha terminada y usuario que la realizo."
      />

      <section className="toolbar-card">
        <div className="form-grid actions-filters-grid">
          <label className="field">
            <span>Buscar</span>
            <input
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder="Codigo, titulo, descripcion, anomalia o usuario"
              type="search"
              value={query}
            />
          </label>

          <label className="field">
            <span>Anomalia</span>
            <input
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setAnomalyFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Codigo o titulo de anomalia"
              type="text"
              value={anomalyFilter}
            />
          </label>

          <label className="field">
            <span>Tratamiento</span>
            <input
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setTreatmentFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Codigo de tratamiento (ej. TRT-2026-0001)"
              type="text"
              value={treatmentFilter}
            />
          </label>

          <label className="field">
            <span>Estado</span>
            <select
              onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
              value={statusFilter}
            >
              <option value="">Todos</option>
              <option value="pending">Pendiente</option>
              <option value="in_progress">En curso</option>
              <option value="completed">Terminada</option>
              <option value="cancelled">Cancelada</option>
              <option value="overdue">Vencida</option>
            </select>
          </label>

          <label className="field">
            <span>Fecha terminada</span>
            <input
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setCompletedOn(event.target.value);
                setPage(1);
              }}
              type="date"
              value={completedOn}
            />
          </label>

          <label className="field">
            <span>Usuario que la realizo</span>
            <select
              onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                setPerformedBy(event.target.value);
                setPage(1);
              }}
              value={performedBy}
            >
              <option value="">Todos</option>
              {(usersData?.results ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {getUserLabel(item)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {usersError ? (
          <div className="panel warning compact-inline-panel">
            <p>No se pudo cargar el listado de usuarios para filtrar.</p>
            <button className="button button-secondary" onClick={() => void reloadUsers()} type="button">
              Reintentar
            </button>
          </div>
        ) : null}
      </section>

      {message ? <div className="panel">{message}</div> : null}
      {formError ? <div className="panel danger">{formError}</div> : null}

      <DataState
        loading={loading || usersLoading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay acciones para mostrar"
        emptyDescription="Ajusta los filtros para revisar el historico de tareas."
      >
        {selectedTask ? (
          <section className="panel action-detail-fixed">
            <div className="section-head compact">
              <h2>{`Editar tarea | ${selectedTask.code || selectedTask.title}`}</h2>
              <StatusBadge value={selectedTask.is_overdue ? "overdue" : selectedTask.status} />
            </div>

            <p className="muted-copy">
              Tratamiento: {selectedTask.treatment?.code || "Sin tratamiento"} | Anomalias asociadas: {selectedTask.anomalies.map((anomaly) => anomaly.code).join(", ") || "Sin asociar"}
            </p>

            <dl className="key-grid compact">
              <div>
                <dt>Estado tratamiento</dt>
                <dd>{selectedTask.treatment?.status || "-"}</dd>
              </div>
              <div>
                <dt>Fecha de ejecucion</dt>
                <dd>{formatDate(selectedTask.execution_date)}</dd>
              </div>
              <div>
                <dt>Causa raiz</dt>
                <dd>{selectedTask.root_cause?.description || "Sin causa raiz"}</dd>
              </div>
              <div>
                <dt>Responsable actual</dt>
                <dd>{selectedTask.responsible?.full_name || selectedTask.responsible?.username || "Sin asignar"}</dd>
              </div>
            </dl>

            <form className="form-section nested-form" onSubmit={handleUpdateTask}>
              <div className="section-head compact">
                <h3>Datos de la tarea</h3>
                <button className="button button-primary" disabled={busy} type="submit">
                  Guardar tarea
                </button>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>Titulo</span>
                  <input
                    onChange={(event) => handleTaskDraftChange("title", event.target.value)}
                    required
                    type="text"
                    value={taskDraft.title}
                  />
                </label>
                <label className="field">
                  <span>Estado</span>
                  <select
                    onChange={(event) => handleTaskDraftChange("status", event.target.value as TaskDraft["status"])}
                    value={taskDraft.status}
                  >
                    {TASK_STATUS_OPTIONS.map((status) => (
                      <option key={status.value} value={status.value}>
                        {status.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Responsable</span>
                  <select
                    onChange={(event) => handleTaskDraftChange("responsible", event.target.value)}
                    value={taskDraft.responsible}
                  >
                    <option value="">Sin asignar</option>
                    {(usersData?.results ?? []).map((user) => (
                      <option key={user.id} value={user.id}>
                        {getUserLabel(user)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Fecha ejecucion</span>
                  <input
                    onChange={(event) => handleTaskDraftChange("execution_date", event.target.value)}
                    type="date"
                    value={taskDraft.execution_date}
                  />
                </label>
              </div>
              <label className="field">
                <span>Descripcion</span>
                <textarea
                  onChange={(event) => handleTaskDraftChange("description", event.target.value)}
                  rows={3}
                  value={taskDraft.description}
                />
              </label>
            </form>

            <section className="form-section nested-form">
              <div className="section-head compact">
                <h3>Evidencias de la tarea</h3>
                <button
                  className="button button-primary"
                  disabled={busy || !taskEvidenceFile}
                  onClick={() => void handleAddTaskEvidence()}
                  type="button"
                >
                  Cargar evidencia
                </button>
              </div>
              <div className="form-grid">
                <label className="field field-span-2">
                  <span>Archivo (imagen, PDF, Word, Excel, texto o ZIP)</span>
                  <input
                    accept={EVIDENCE_ACCEPT}
                    key={taskEvidenceInputKey}
                    onChange={handleTaskEvidenceFileChange}
                    type="file"
                  />
                </label>
                <label className="field field-span-2">
                  <span>Nota de evidencia (opcional)</span>
                  <textarea
                    onChange={(event) => setTaskEvidenceNote(event.target.value)}
                    rows={3}
                    value={taskEvidenceNote}
                  />
                </label>
              </div>
              <div className="stack-list compact">
                {selectedTask.evidences.length ? (
                  selectedTask.evidences.map((evidence) => (
                    <div className="list-card compact" key={evidence.id}>
                      <div className="evidence-block">
                        <a href={getEvidenceUrl(evidence.file_url)} rel="noopener noreferrer" target="_blank">
                          {evidence.original_name}
                        </a>
                        <small>{formatDateTime(evidence.created_at)}</small>
                        <p>{evidence.note || "Sin nota"}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="muted-copy">Todavia no hay evidencias cargadas en esta tarea.</p>
                )}
              </div>
            </section>
          </section>
        ) : null}

        <div className="stack-list">
          {data?.results.map((item) => {
            const isSelected = selectedTaskId === item.id;
            const anomalySummary = item.anomalies?.length
              ? item.anomalies.map((anomaly) => `${anomaly.code} - ${anomaly.title}`).join(" | ")
              : "Sin anomalia asociada";

            return (
              <article
                className={`panel action-card${isSelected ? " active" : ""}`}
                key={item.id}
                onClick={() => setSelectedTaskId(item.id)}
                role="button"
                tabIndex={0}
              >
                <div className="section-head compact">
                  <div>
                    <strong>{item.code || item.title}</strong>
                    <p>{item.title}</p>
                    <small>{item.description || "Sin descripcion."}</small>
                  </div>
                  <StatusBadge value={item.is_overdue ? "overdue" : item.status} />
                </div>

                <dl className="key-grid compact">
                  <div>
                    <dt>Anomalia</dt>
                    <dd>{anomalySummary}</dd>
                  </div>
                  <div>
                    <dt>Tratamiento</dt>
                    <dd>{item.treatment?.code || "Sin tratamiento"}</dd>
                  </div>
                  <div>
                    <dt>Usuario que la realizo</dt>
                    <dd>{item.responsible?.full_name || item.responsible?.username || "Sin asignar"}</dd>
                  </div>
                  <div>
                    <dt>Fecha terminada</dt>
                    <dd>{item.status === "completed" ? formatDate(item.execution_date) : "-"}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading || busy} />
      </DataState>
    </section>
  );
}
