import { ChangeEvent, FormEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { fetchUsers } from "../../../api/accounts";
import {
  addTreatmentAnomaly,
  addTreatmentParticipant,
  addTreatmentRootCause,
  addTreatmentTask,
  createTreatment,
  fetchTreatmentCandidates,
  fetchTreatmentDetail,
  fetchTreatments,
  updateTreatment,
  updateTreatmentTask,
} from "../../../api/treatments";
import type { TreatmentTask, UserDirectoryItem } from "../../../api/types";
import { formatDate, toDateTimeLocalValue, toOffsetIso } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type TreatmentTab = "agenda" | "analysis";

type TaskDraft = {
  title: string;
  description: string;
  root_cause: string;
  responsible: string;
  execution_date: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  anomaly_ids: string[];
};

const PARTICIPANT_ROLES = [
  { value: "convoked", label: "Convocado" },
  { value: "facilitator", label: "Facilitador" },
  { value: "owner", label: "Responsable" },
] as const;

const METHOD_OPTIONS = [
  { value: "", label: "Sin definir" },
  { value: "five_whys", label: "5 Why" },
  { value: "6m", label: "6M" },
  { value: "ishikawa", label: "Ishikawa" },
  { value: "a3", label: "A3" },
  { value: "8d", label: "8D" },
  { value: "other", label: "Otro" },
] as const;

const TASK_STATUS_OPTIONS = [
  { value: "pending", label: "Pendiente" },
  { value: "in_progress", label: "En curso" },
  { value: "completed", label: "Completada" },
  { value: "cancelled", label: "Cancelada" },
] as const;

const EMPTY_TASK_DRAFT: TaskDraft = {
  title: "",
  description: "",
  root_cause: "",
  responsible: "",
  execution_date: "",
  status: "pending",
  anomaly_ids: [],
};

function buildUsersLabel(user: UserDirectoryItem) {
  const name = user.full_name || user.username;
  return `${name} (${user.username})`;
}

export function TreatmentsPage() {
  usePageTitle("Tratamientos");

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);

  const [selectedTreatmentId, setSelectedTreatmentId] = useState("");
  const [selectedTab, setSelectedTab] = useState<TreatmentTab>("agenda");

  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [scheduledFor, setScheduledFor] = useState("");
  const [methodUsed, setMethodUsed] = useState("");
  const [observations, setObservations] = useState("");

  const [participantUserId, setParticipantUserId] = useState("");
  const [participantRole, setParticipantRole] = useState("convoked");
  const [participantNote, setParticipantNote] = useState("");

  const [linkAnomalyId, setLinkAnomalyId] = useState("");
  const [rootCauseDescription, setRootCauseDescription] = useState("");

  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK_DRAFT);
  const [selectedTaskId, setSelectedTaskId] = useState("");

  const {
    data: supportData,
    loading,
    error,
    reload: reloadSupport,
  } = useAsyncTask(async () => {
    const [treatments, candidates, users] = await Promise.all([
      fetchTreatments(),
      fetchTreatmentCandidates(),
      fetchUsers({ active: true }),
    ]);

    return {
      treatments: treatments.results,
      candidates: candidates.results,
      users: users.results,
    };
  }, []);

  const filteredTreatments = useMemo(() => {
    const list = supportData?.treatments ?? [];
    const term = deferredSearch.trim().toLowerCase();

    if (!term) {
      return list;
    }

    return list.filter((item) => {
      const values = [
        item.code,
        item.primary_anomaly.code,
        item.primary_anomaly.title,
        item.primary_anomaly.description,
        item.primary_anomaly.reporter?.full_name || "",
        item.primary_anomaly.area?.name || "",
        item.primary_anomaly.anomaly_origin?.name || "",
      ];
      return values.some((value) => value.toLowerCase().includes(term));
    });
  }, [deferredSearch, supportData?.treatments]);

  const {
    data: selectedTreatment,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncTask(async () => {
    if (!selectedTreatmentId) {
      return null;
    }
    return fetchTreatmentDetail(selectedTreatmentId);
  }, [selectedTreatmentId]);

  useEffect(() => {
    if (!filteredTreatments.length) {
      setSelectedTreatmentId("");
      return;
    }

    if (!selectedTreatmentId) {
      setSelectedTreatmentId(filteredTreatments[0].id);
      return;
    }

    if (!filteredTreatments.some((item) => item.id === selectedTreatmentId)) {
      setSelectedTreatmentId(filteredTreatments[0].id);
    }
  }, [filteredTreatments, selectedTreatmentId]);

  useEffect(() => {
    if (!selectedTreatment) {
      setScheduledFor("");
      setMethodUsed("");
      setObservations("");
      setTaskDraft(EMPTY_TASK_DRAFT);
      setSelectedTaskId("");
      return;
    }

    setScheduledFor(toDateTimeLocalValue(selectedTreatment.scheduled_for));
    setMethodUsed(selectedTreatment.method_used || "");
    setObservations(selectedTreatment.observations || "");
  }, [selectedTreatment]);

  useEffect(() => {
    if (!supportData?.candidates.length) {
      setSelectedCandidateId("");
      return;
    }

    if (selectedCandidateId && supportData.candidates.some((item) => item.id === selectedCandidateId)) {
      return;
    }

    setSelectedCandidateId(supportData.candidates[0].id);
  }, [selectedCandidateId, supportData?.candidates]);

  useEffect(() => {
    if (!selectedTreatment) {
      setLinkAnomalyId("");
      return;
    }

    const available = (supportData?.candidates ?? []).filter(
      (candidate) => !selectedTreatment.anomaly_links.some((link) => link.anomaly.id === candidate.id),
    );

    if (!available.length) {
      setLinkAnomalyId("");
      return;
    }

    if (linkAnomalyId && available.some((item) => item.id === linkAnomalyId)) {
      return;
    }

    setLinkAnomalyId(available[0].id);
  }, [linkAnomalyId, selectedTreatment, supportData?.candidates]);

  useEffect(() => {
    if (!supportData?.users.length) {
      setParticipantUserId("");
      return;
    }

    if (participantUserId && supportData.users.some((user) => user.id === participantUserId)) {
      return;
    }

    setParticipantUserId(supportData.users[0].id);
  }, [participantUserId, supportData?.users]);

  const unlinkedCandidates = useMemo(() => {
    if (!selectedTreatment) {
      return [];
    }

    return (supportData?.candidates ?? []).filter(
      (candidate) => !selectedTreatment.anomaly_links.some((link) => link.anomaly.id === candidate.id),
    );
  }, [selectedTreatment, supportData?.candidates]);

  const rootCauseOptions = selectedTreatment?.root_causes ?? [];
  const anomalyOptions = selectedTreatment?.anomaly_links ?? [];
  const selectedTask: TreatmentTask | null = useMemo(
    () => selectedTreatment?.tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, selectedTreatment?.tasks],
  );

  useEffect(() => {
    if (!selectedTask) {
      return;
    }

    setTaskDraft({
      title: selectedTask.title,
      description: selectedTask.description || "",
      root_cause: selectedTask.root_cause || "",
      responsible: selectedTask.responsible?.id || "",
      execution_date: selectedTask.execution_date || "",
      status: selectedTask.status as TaskDraft["status"],
      anomaly_ids: selectedTask.anomaly_links.map((item) => item.anomaly.id),
    });
  }, [selectedTask]);

  const runMutation = async (fn: () => Promise<void>, successMessage: string, keepTaskSelection = false) => {
    setBusy(true);
    setFormError(null);
    setMessage(null);

    try {
      await fn();
      await reloadSupport();
      if (selectedTreatmentId) {
        await reloadDetail();
      }
      if (!keepTaskSelection) {
        setSelectedTaskId("");
      }
      setMessage(successMessage);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo completar la accion.");
    } finally {
      setBusy(false);
    }
  };

  const handleCreateTreatment = async () => {
    if (!selectedCandidateId) {
      setFormError("Selecciona una anomalia para crear el tratamiento.");
      return;
    }

    await runMutation(async () => {
      const created = await createTreatment({ primary_anomaly: selectedCandidateId, status: "pending" });
      setSelectedTreatmentId(created.id);
      setSelectedTab("agenda");
    }, "Tratamiento creado correctamente.");
  };

  const handleSaveAgenda = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }

    await runMutation(async () => {
      await updateTreatment(selectedTreatment.id, {
        scheduled_for: scheduledFor ? toOffsetIso(scheduledFor) : null,
      });
    }, "Agenda del tratamiento actualizada.");
  };

  const handleAddParticipant = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !participantUserId) {
      return;
    }

    await runMutation(async () => {
      await addTreatmentParticipant(selectedTreatment.id, {
        user: participantUserId,
        role: participantRole,
        note: participantNote.trim(),
      });
      setParticipantNote("");
    }, "Participante convocado al tratamiento.");
  };

  const handleAddAnomaly = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !linkAnomalyId) {
      return;
    }

    await runMutation(async () => {
      await addTreatmentAnomaly(selectedTreatment.id, linkAnomalyId);
    }, "Anomalia vinculada al tratamiento.");
  };

  const handleSaveAnalysis = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }

    await runMutation(async () => {
      await updateTreatment(selectedTreatment.id, {
        method_used: methodUsed,
        observations: observations.trim(),
      });
    }, "Analisis de tratamiento guardado.");
  };

  const handleAddRootCause = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !rootCauseDescription.trim()) {
      return;
    }

    await runMutation(async () => {
      await addTreatmentRootCause(selectedTreatment.id, rootCauseDescription.trim());
      setRootCauseDescription("");
    }, "Causa raiz registrada.");
  };

  const handleTaskDraftChange = (field: keyof TaskDraft, value: string) => {
    setTaskDraft((current) => ({ ...current, [field]: value }));
  };

  const toggleTaskAnomaly = (anomalyId: string) => {
    setTaskDraft((current) => {
      const exists = current.anomaly_ids.includes(anomalyId);
      return {
        ...current,
        anomaly_ids: exists
          ? current.anomaly_ids.filter((id) => id !== anomalyId)
          : [...current.anomaly_ids, anomalyId],
      };
    });
  };

  const handleAddTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !taskDraft.title.trim()) {
      setFormError("La tarea necesita al menos un titulo.");
      return;
    }

    await runMutation(async () => {
      await addTreatmentTask(selectedTreatment.id, {
        title: taskDraft.title.trim(),
        description: taskDraft.description.trim(),
        root_cause: taskDraft.root_cause || null,
        responsible: taskDraft.responsible || null,
        execution_date: taskDraft.execution_date || null,
        status: taskDraft.status,
        anomaly_ids: taskDraft.anomaly_ids,
      });
      setTaskDraft(EMPTY_TASK_DRAFT);
    }, "Tarea de tratamiento creada.");
  };

  const handleSelectTask = (task: TreatmentTask) => {
    setSelectedTaskId(task.id);
    setTaskDraft({
      title: task.title,
      description: task.description || "",
      root_cause: task.root_cause || "",
      responsible: task.responsible?.id || "",
      execution_date: task.execution_date || "",
      status: task.status as TaskDraft["status"],
      anomaly_ids: task.anomaly_links.map((item) => item.anomaly.id),
    });
  };

  const handleUpdateTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !selectedTask || !taskDraft.title.trim()) {
      return;
    }

    await runMutation(
      async () => {
        await updateTreatmentTask(selectedTreatment.id, selectedTask.id, {
          title: taskDraft.title.trim(),
          description: taskDraft.description.trim(),
          root_cause: taskDraft.root_cause || null,
          responsible: taskDraft.responsible || null,
          execution_date: taskDraft.execution_date || null,
          status: taskDraft.status,
          anomaly_ids: taskDraft.anomaly_ids,
        });
      },
      "Tarea actualizada.",
      true,
    );
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Tratamientos"
        description="Gestion de tratamientos por anomalia clasificada: convocatoria, analisis de causa y tareas asociadas."
      />

      <div className="toolbar-card treatment-toolbar">
        <input
          onChange={(event: ChangeEvent<HTMLInputElement>) => setSearch(event.target.value)}
          placeholder="Buscar por tratamiento, anomalia, responsable o sector"
          type="search"
          value={search}
        />
        <div className="treatment-toolbar-actions">
          <select onChange={(event) => setSelectedCandidateId(event.target.value)} value={selectedCandidateId}>
            <option value="">Seleccionar anomalia clasificada...</option>
            {(supportData?.candidates ?? []).map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{`${candidate.code} - ${candidate.title}`}</option>
            ))}
          </select>
          <button className="button button-primary" disabled={busy || !selectedCandidateId} onClick={() => void handleCreateTreatment()} type="button">
            Crear tratamiento
          </button>
        </div>
      </div>

      {message ? <div className="panel">{message}</div> : null}
      {formError ? <div className="panel danger">{formError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reloadSupport}>
        <div className="treatment-layout">
          <article className="panel treatment-list-panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Listado</p>
                <h2>Tratamientos ({filteredTreatments.length})</h2>
              </div>
            </div>

            <div className="stack-list treatment-list">
              {filteredTreatments.map((treatment) => {
                const anomaly = treatment.primary_anomaly;
                const isActive = selectedTreatmentId === treatment.id;
                return (
                  <button
                    className={`treatment-list-item${isActive ? " active" : ""}`}
                    key={treatment.id}
                    onClick={() => setSelectedTreatmentId(treatment.id)}
                    type="button"
                  >
                    <div className="section-head compact">
                      <strong>{treatment.code}</strong>
                      <StatusBadge compact value={treatment.status} />
                    </div>
                    <p className="treatment-title">{anomaly.code}</p>
                    <p>{anomaly.title}</p>
                    <small>
                      Generada por: {anomaly.reporter?.full_name || anomaly.reporter?.username || "Sin dato"} � Proceso afectado: {anomaly.area?.name || "-"} � Proceso origen: {anomaly.anomaly_origin?.name || "-"}
                    </small>
                  </button>
                );
              })}
              {!filteredTreatments.length ? <p className="muted-copy">No hay tratamientos disponibles para mostrar.</p> : null}
            </div>
          </article>

          <article className="panel treatment-detail-panel">
            <DataState loading={detailLoading} error={detailError} onRetry={reloadDetail}>
              {selectedTreatment ? (
                <>
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Detalle de tratamiento</p>
                      <h2>{selectedTreatment.code}</h2>
                      <p className="page-description">
                        Anomalia principal: <strong>{selectedTreatment.primary_anomaly.code}</strong> � {selectedTreatment.primary_anomaly.title}
                      </p>
                    </div>
                    <StatusBadge value={selectedTreatment.status} />
                  </div>

                  <div className="treatment-tab-row">
                    <button
                      className={`button button-secondary${selectedTab === "agenda" ? " active" : ""}`}
                      onClick={() => setSelectedTab("agenda")}
                      type="button"
                    >
                      Vista 1 � Convocatoria
                    </button>
                    <button
                      className={`button button-secondary${selectedTab === "analysis" ? " active" : ""}`}
                      onClick={() => setSelectedTab("analysis")}
                      type="button"
                    >
                      Vista 2 � Analisis
                    </button>
                  </div>

                  {selectedTab === "agenda" ? (
                    <div className="treatment-tab-content">
                      <form className="form-section" onSubmit={handleSaveAgenda}>
                        <div className="section-head compact">
                          <h3>Fecha de tratamiento</h3>
                          <button className="button button-primary" disabled={busy} type="submit">
                            Guardar agenda
                          </button>
                        </div>
                        <label className="field">
                          <span>Fecha y hora programada</span>
                          <input
                            name="scheduled_for"
                            onChange={(event) => setScheduledFor(event.target.value)}
                            type="datetime-local"
                            value={scheduledFor}
                          />
                        </label>
                      </form>

                      <form className="form-section" onSubmit={handleAddParticipant}>
                        <div className="section-head compact">
                          <h3>Usuarios convocados</h3>
                          <button className="button button-primary" disabled={busy || !participantUserId} type="submit">
                            Convocar
                          </button>
                        </div>
                        <div className="form-grid">
                          <label className="field">
                            <span>Usuario</span>
                            <select onChange={(event) => setParticipantUserId(event.target.value)} value={participantUserId}>
                              {(supportData?.users ?? []).map((user) => (
                                <option key={user.id} value={user.id}>
                                  {buildUsersLabel(user)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span>Rol</span>
                            <select onChange={(event) => setParticipantRole(event.target.value)} value={participantRole}>
                              {PARTICIPANT_ROLES.map((role) => (
                                <option key={role.value} value={role.value}>
                                  {role.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <label className="field">
                          <span>Nota</span>
                          <textarea
                            name="participant_note"
                            onChange={(event) => setParticipantNote(event.target.value)}
                            rows={3}
                            value={participantNote}
                          />
                        </label>

                        <div className="stack-list compact">
                          {selectedTreatment.participants.map((participant) => (
                            <div className="list-card compact" key={participant.id}>
                              <div>
                                <strong>{participant.user?.full_name || participant.user?.username || "Usuario"}</strong>
                                <p>{participant.note || "Sin observaciones"}</p>
                              </div>
                              <StatusBadge compact value={participant.role} />
                            </div>
                          ))}
                          {!selectedTreatment.participants.length ? <p className="muted-copy">Todavia no hay convocados.</p> : null}
                        </div>
                      </form>

                      <form className="form-section" onSubmit={handleAddAnomaly}>
                        <div className="section-head compact">
                          <h3>Anomalias asociadas al tratamiento</h3>
                          <button className="button button-primary" disabled={busy || !linkAnomalyId} type="submit">
                            Asociar anomalia
                          </button>
                        </div>
                        <label className="field">
                          <span>Anomalias clasificadas disponibles</span>
                          <select onChange={(event) => setLinkAnomalyId(event.target.value)} value={linkAnomalyId}>
                            <option value="">Seleccionar...</option>
                            {unlinkedCandidates.map((candidate) => (
                              <option key={candidate.id} value={candidate.id}>{`${candidate.code} - ${candidate.title}`}</option>
                            ))}
                          </select>
                        </label>
                        <div className="stack-list compact">
                          {selectedTreatment.anomaly_links.map((link) => (
                            <div className="list-card compact" key={link.id}>
                              <div>
                                <strong>{link.anomaly.code}</strong>
                                <p>{link.anomaly.title}</p>
                                <small>
                                  Sector afectado: {link.anomaly.area?.name || "-"} � Sector origen: {link.anomaly.anomaly_origin?.name || "-"}
                                </small>
                              </div>
                              {link.is_primary ? <span className="status-badge info compact">Principal</span> : null}
                            </div>
                          ))}
                        </div>
                      </form>
                    </div>
                  ) : null}

                  {selectedTab === "analysis" ? (
                    <div className="treatment-tab-content">
                      <form className="form-section" onSubmit={handleSaveAnalysis}>
                        <div className="section-head compact">
                          <h3>Metodo y observaciones</h3>
                          <button className="button button-primary" disabled={busy} type="submit">
                            Guardar analisis
                          </button>
                        </div>
                        <label className="field">
                          <span>Metodo usado</span>
                          <select onChange={(event) => setMethodUsed(event.target.value)} value={methodUsed}>
                            {METHOD_OPTIONS.map((method) => (
                              <option key={method.value || "none"} value={method.value}>
                                {method.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>Observaciones de tratamiento</span>
                          <textarea onChange={(event) => setObservations(event.target.value)} rows={4} value={observations} />
                        </label>
                      </form>

                      <form className="form-section" onSubmit={handleAddRootCause}>
                        <div className="section-head compact">
                          <h3>Causas raiz encontradas</h3>
                          <button className="button button-primary" disabled={busy || !rootCauseDescription.trim()} type="submit">
                            Agregar causa
                          </button>
                        </div>
                        <label className="field">
                          <span>Descripcion de la causa raiz</span>
                          <textarea
                            onChange={(event) => setRootCauseDescription(event.target.value)}
                            rows={3}
                            value={rootCauseDescription}
                          />
                        </label>

                        <div className="stack-list compact">
                          {selectedTreatment.root_causes.map((cause) => (
                            <div className="nested-card" key={cause.id}>
                              <div>
                                <strong>{`Causa ${cause.sequence}`}</strong>
                                <p>{cause.description}</p>
                              </div>
                            </div>
                          ))}
                          {!selectedTreatment.root_causes.length ? <p className="muted-copy">No hay causas cargadas aun.</p> : null}
                        </div>
                      </form>

                      <form className="form-section" onSubmit={handleAddTask}>
                        <div className="section-head compact">
                          <h3>Tareas surgidas del tratamiento</h3>
                          <button className="button button-primary" disabled={busy || !taskDraft.title.trim()} type="submit">
                            Crear tarea
                          </button>
                        </div>

                        <div className="form-grid">
                          <label className="field">
                            <span>Tarea</span>
                            <input
                              name="task_title"
                              onChange={(event) => handleTaskDraftChange("title", event.target.value)}
                              placeholder="Ej. Verificar ajuste de proceso"
                              required
                              type="text"
                              value={taskDraft.title}
                            />
                          </label>

                          <label className="field">
                            <span>Estado</span>
                            <select
                              onChange={(event) => handleTaskDraftChange("status", event.target.value)}
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
                              {(supportData?.users ?? []).map((user) => (
                                <option key={user.id} value={user.id}>
                                  {buildUsersLabel(user)}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="field">
                            <span>Fecha de ejecucion</span>
                            <input
                              onChange={(event) => handleTaskDraftChange("execution_date", event.target.value)}
                              type="date"
                              value={taskDraft.execution_date}
                            />
                          </label>

                          <label className="field field-span-2">
                            <span>Causa raiz asociada</span>
                            <select onChange={(event) => handleTaskDraftChange("root_cause", event.target.value)} value={taskDraft.root_cause}>
                              <option value="">Sin causa especifica</option>
                              {rootCauseOptions.map((cause) => (
                                <option key={cause.id} value={cause.id}>{`Causa ${cause.sequence}: ${cause.description}`}</option>
                              ))}
                            </select>
                          </label>

                          <label className="field field-span-2">
                            <span>Descripcion / observaciones</span>
                            <textarea
                              onChange={(event) => handleTaskDraftChange("description", event.target.value)}
                              rows={3}
                              value={taskDraft.description}
                            />
                          </label>
                        </div>

                        <div className="treatment-checkbox-grid">
                          {anomalyOptions.map((link) => {
                            const checked = taskDraft.anomaly_ids.includes(link.anomaly.id);
                            return (
                              <label className="checkbox-inline" key={link.id}>
                                <input
                                  checked={checked}
                                  onChange={() => toggleTaskAnomaly(link.anomaly.id)}
                                  type="checkbox"
                                />
                                <span>{`${link.anomaly.code} - ${link.anomaly.title}`}</span>
                              </label>
                            );
                          })}
                        </div>
                      </form>

                      <div className="form-section">
                        <div className="section-head compact">
                          <h3>Detalle de tareas</h3>
                        </div>

                        <div className="stack-list compact">
                          {selectedTreatment.tasks.map((task) => (
                            <button className="list-card compact treatment-task-item" key={task.id} onClick={() => handleSelectTask(task)} type="button">
                              <div>
                                <strong>{task.title}</strong>
                                <p>{task.description || "Sin descripcion"}</p>
                                <small>
                                  Responsable: {task.responsible?.full_name || "Sin asignar"} � Ejecucion: {task.execution_date ? formatDate(task.execution_date) : "Sin fecha"}
                                </small>
                              </div>
                              <StatusBadge compact value={task.status} />
                            </button>
                          ))}
                          {!selectedTreatment.tasks.length ? <p className="muted-copy">No hay tareas registradas para este tratamiento.</p> : null}
                        </div>

                        {selectedTask ? (
                          <form className="form-section nested-form" onSubmit={handleUpdateTask}>
                            <div className="section-head compact">
                              <h3>{`Editar tarea � ${selectedTask.code || selectedTask.title}`}</h3>
                              <button className="button button-primary" disabled={busy} type="submit">
                                Guardar tarea
                              </button>
                            </div>

                            <p className="muted-copy">
                              Tratamiento: {selectedTreatment.code} � Anomalias asociadas: {selectedTask.anomaly_links.map((item) => item.anomaly.code).join(", ") || "Sin asociar"}
                            </p>

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
                                  onChange={(event) => handleTaskDraftChange("status", event.target.value)}
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
                                  {(supportData?.users ?? []).map((user) => (
                                    <option key={user.id} value={user.id}>
                                      {buildUsersLabel(user)}
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
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="panel muted">
                  <h2>Sin tratamiento seleccionado</h2>
                  <p>Selecciona un tratamiento del listado para gestionar convocatoria, analisis, causas y tareas.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}
