import { ChangeEvent, FormEvent, MouseEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchUsers } from "../../../api/accounts";
import {
  addTreatmentAnomaly,
  addTreatmentParticipant,
  addTreatmentRootCause,
  addTreatmentTask,
  addTreatmentEvidence,
  addTreatmentTaskEvidence,
  createTreatment,
  fetchTreatmentCandidates,
  fetchTreatmentDetail,
  fetchTreatments,
  updateTreatment,
  updateTreatmentTask,
} from "../../../api/treatments";
import type { TreatmentTask, UserDirectoryItem } from "../../../api/types";
import { readStoredSession } from "../../../api/http";
import { formatDate, toDateTimeLocalValue, toOffsetIso } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
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

const EVIDENCE_ACCEPT = "image/*,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf,.odt,.ods,.zip";

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

function normalizeEvidenceType(contentType: string) {
  if (!contentType) {
    return "Archivo";
  }
  if (contentType.includes("pdf")) {
    return "PDF";
  }
  if (contentType.includes("image")) {
    return "Imagen";
  }
  return contentType;
}

function normalizeEvidenceUrl(fileUrl: string) {
  if (!fileUrl) {
    return "#";
  }

  const trimmed = fileUrl.trim();
  if (!trimmed) {
    return "#";
  }

  if (trimmed.startsWith("/")) {
    return trimmed;
  }

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    try {
      const parsed = new URL(trimmed);
      const hostname = parsed.hostname.toLowerCase();
      const isLoopbackHost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
      const mediaPath = `${parsed.pathname}${parsed.search}${parsed.hash}`;

      if (isLoopbackHost || parsed.pathname.startsWith("/media/") || parsed.pathname.startsWith("/api/")) {
        return mediaPath;
      }

      return parsed.toString();
    } catch {
      return trimmed;
    }
  }

  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

function extractFilenameFromDisposition(contentDisposition: string | null, fallback = "evidencia") {
  if (!contentDisposition) {
    return fallback;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const regularMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  if (regularMatch?.[1]) {
    return regularMatch[1];
  }

  return fallback;
}

export function TreatmentsPage() {
  usePageTitle("Tratamientos");

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const deferredSearch = useDeferredValue(search);

  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTreatmentId = (searchParams.get("treatment") || "").trim();

  const [selectedTreatmentId, setSelectedTreatmentId] = useState(() => requestedTreatmentId);
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
  const [linkCandidatePage, setLinkCandidatePage] = useState(1);
  const [linkCandidateAnomalyFilter, setLinkCandidateAnomalyFilter] = useState("");
  const [linkCandidateSectorFilter, setLinkCandidateSectorFilter] = useState("");
  const [linkCandidateAreaFilter, setLinkCandidateAreaFilter] = useState("");
  const [linkCandidateUserFilter, setLinkCandidateUserFilter] = useState("");
  const [linkCandidateDateFrom, setLinkCandidateDateFrom] = useState("");
  const [linkCandidateDateTo, setLinkCandidateDateTo] = useState("");
  const deferredLinkCandidateAnomalyFilter = useDeferredValue(linkCandidateAnomalyFilter);
  const deferredLinkCandidateSectorFilter = useDeferredValue(linkCandidateSectorFilter);
  const deferredLinkCandidateAreaFilter = useDeferredValue(linkCandidateAreaFilter);
  const deferredLinkCandidateUserFilter = useDeferredValue(linkCandidateUserFilter);
  const [rootCauseDescription, setRootCauseDescription] = useState("");

  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK_DRAFT);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [treatmentEvidenceFile, setTreatmentEvidenceFile] = useState<File | null>(null);
  const [treatmentEvidenceNote, setTreatmentEvidenceNote] = useState("");
  const [taskEvidenceFile, setTaskEvidenceFile] = useState<File | null>(null);
  const [taskEvidenceNote, setTaskEvidenceNote] = useState("");
  const [treatmentEvidenceInputKey, setTreatmentEvidenceInputKey] = useState(0);
  const [taskEvidenceInputKey, setTaskEvidenceInputKey] = useState(0);

  const {
    data: supportData,
    loading,
    error,
    reload: reloadSupport,
  } = useAsyncTask(async () => {
    const linkCandidatesPromise = selectedTreatmentId
      ? fetchTreatmentCandidates({
          page: linkCandidatePage,
          pageSize: 10,
          treatmentId: selectedTreatmentId,
          anomaly: deferredLinkCandidateAnomalyFilter,
          sector: deferredLinkCandidateSectorFilter,
          area: deferredLinkCandidateAreaFilter,
          user: deferredLinkCandidateUserFilter,
          dateFrom: linkCandidateDateFrom,
          dateTo: linkCandidateDateTo,
        })
      : Promise.resolve({ count: 0, next: null, previous: null, results: [] });

    const [treatments, createCandidates, linkCandidates, users] = await Promise.all([
      fetchTreatments(page, deferredSearch),
      fetchTreatmentCandidates({ page: 1, pageSize: 100 }),
      linkCandidatesPromise,
      fetchUsers({ active: true }),
    ]);

    return {
      treatments: treatments.results,
      treatmentsTotal: treatments.count,
      createCandidates: createCandidates.results,
      linkCandidates: linkCandidates.results,
      linkCandidatesTotal: linkCandidates.count,
      users: users.results,
    };
  }, [
    page,
    deferredSearch,
    selectedTreatmentId,
    linkCandidatePage,
    deferredLinkCandidateAnomalyFilter,
    deferredLinkCandidateSectorFilter,
    deferredLinkCandidateAreaFilter,
    deferredLinkCandidateUserFilter,
    linkCandidateDateFrom,
    linkCandidateDateTo,
  ]);

  const filteredTreatments = useMemo(() => supportData?.treatments ?? [], [supportData?.treatments]);

  useEffect(() => {
    const currentTreatmentInQuery = (searchParams.get("treatment") || "").trim();
    if (selectedTreatmentId === currentTreatmentInQuery) {
      return;
    }

    const nextParams = new URLSearchParams(searchParams);
    if (selectedTreatmentId) {
      nextParams.set("treatment", selectedTreatmentId);
    } else {
      nextParams.delete("treatment");
    }
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, selectedTreatmentId, setSearchParams]);

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
      return;
    }

    if (!selectedTreatmentId) {
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
      setTreatmentEvidenceFile(null);
      setTreatmentEvidenceNote("");
      setTaskEvidenceFile(null);
      setTaskEvidenceNote("");
      setTreatmentEvidenceInputKey((current) => current + 1);
      setTaskEvidenceInputKey((current) => current + 1);
      return;
    }

    setScheduledFor(toDateTimeLocalValue(selectedTreatment.scheduled_for));
    setMethodUsed(selectedTreatment.method_used || "");
    setObservations(selectedTreatment.observations || "");
  }, [selectedTreatment]);

  useEffect(() => {
    if (!supportData?.createCandidates.length) {
      setSelectedCandidateId("");
      return;
    }

    if (selectedCandidateId && supportData.createCandidates.some((item) => item.id === selectedCandidateId)) {
      return;
    }

    setSelectedCandidateId(supportData.createCandidates[0].id);
  }, [selectedCandidateId, supportData?.createCandidates]);

  useEffect(() => {
    setLinkCandidatePage(1);
  }, [selectedTreatmentId]);

  useEffect(() => {
    if (!selectedTreatment) {
      setLinkAnomalyId("");
      return;
    }

    const available = (supportData?.linkCandidates ?? []).filter(
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
  }, [linkAnomalyId, selectedTreatment, supportData?.linkCandidates]);

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

    return (supportData?.linkCandidates ?? []).filter(
      (candidate) => !selectedTreatment.anomaly_links.some((link) => link.anomaly.id === candidate.id),
    );
  }, [selectedTreatment, supportData?.linkCandidates]);

  const rootCauseOptions = selectedTreatment?.root_causes ?? [];
  const anomalyOptions = selectedTreatment?.anomaly_links ?? [];
  const canCreateTask =
    Boolean(taskDraft.title.trim()) &&
    Boolean(taskDraft.description.trim()) &&
    Boolean(taskDraft.root_cause) &&
    Boolean(taskDraft.responsible) &&
    Boolean(taskDraft.execution_date) &&
    taskDraft.anomaly_ids.length > 0;
  const selectedTask: TreatmentTask | null = useMemo(
    () => selectedTreatment?.tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, selectedTreatment?.tasks],
  );

  useEffect(() => {
    if (!selectedTask) {
      setTaskEvidenceFile(null);
      setTaskEvidenceNote("");
      setTaskEvidenceInputKey((current) => current + 1);
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
    setTaskEvidenceFile(null);
    setTaskEvidenceNote("");
    setTaskEvidenceInputKey((current) => current + 1);
  }, [selectedTask]);
  const handleOpenEvidence = async (event: MouseEvent<HTMLAnchorElement>, rawFileUrl: string, fallbackName = "evidencia") => {
    event.preventDefault();

    const fileUrl = normalizeEvidenceUrl(rawFileUrl);
    if (!fileUrl || fileUrl === "#") {
      setFormError("La evidencia no tiene una URL valida.");
      return;
    }

    setFormError(null);

    const session = readStoredSession();
    if (!session?.access) {
      setFormError("Tu sesion vencio. Inicia sesion nuevamente para abrir evidencias.");
      return;
    }

    try {
      const response = await fetch(fileUrl, {
        method: "GET",
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${session.access}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Error HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const contentType = (response.headers.get("content-type") || blob.type || "").toLowerCase();
      const canPreview = contentType.startsWith("image/") || contentType.includes("pdf") || contentType.startsWith("text/");

      if (canPreview) {
        window.open(blobUrl, "_blank", "noopener,noreferrer");
      } else {
        const tempLink = document.createElement("a");
        tempLink.href = blobUrl;
        tempLink.download = extractFilenameFromDisposition(response.headers.get("content-disposition"), fallbackName);
        document.body.appendChild(tempLink);
        tempLink.click();
        tempLink.remove();
      }

      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch {
      setFormError("No se pudo abrir la evidencia. Verifica que tu sesion siga activa e intenta nuevamente.");
    }
  };

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
    if (!methodUsed) {
      setFormError("Debes seleccionar un metodo de analisis.");
      return;
    }
    if (!observations.trim()) {
      setFormError("Debes registrar observaciones para guardar el analisis.");
      return;
    }

    const confirmSave = window.confirm(
      "Confirmas guardar el analisis de tratamiento? Esto impactara en el seguimiento de la anomalia.",
    );
    if (!confirmSave) {
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

  const handleTreatmentEvidenceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setTreatmentEvidenceFile(file);
  };

  const handleTaskEvidenceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setTaskEvidenceFile(file);
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
    if (busy) {
      return;
    }
    if (!selectedTreatment) {
      return;
    }

    if (!taskDraft.title.trim()) {
      setFormError("La tarea es obligatoria.");
      return;
    }
    if (!taskDraft.description.trim()) {
      setFormError("La descripcion de la tarea es obligatoria.");
      return;
    }
    if (!taskDraft.root_cause) {
      setFormError("Debes seleccionar la causa raiz asociada.");
      return;
    }
    if (!taskDraft.responsible) {
      setFormError("Debes seleccionar un responsable.");
      return;
    }
    if (!taskDraft.execution_date) {
      setFormError("Debes indicar la fecha de ejecucion.");
      return;
    }
    if (!taskDraft.anomaly_ids.length) {
      setFormError("Debes vincular al menos una anomalia a la tarea.");
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

  const handleAddTreatmentEvidence = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }
    if (!treatmentEvidenceFile) {
      setFormError("Debes seleccionar una evidencia (imagen o PDF) para cargar al tratamiento.");
      return;
    }

    await runMutation(async () => {
      await addTreatmentEvidence(selectedTreatment.id, {
        file: treatmentEvidenceFile,
        note: treatmentEvidenceNote,
      });
      setTreatmentEvidenceFile(null);
      setTreatmentEvidenceNote("");
      setTreatmentEvidenceInputKey((current) => current + 1);
    }, "Evidencia cargada en el tratamiento.");
  };

  const handleAddTaskEvidence = async () => {
    if (!selectedTreatment || !selectedTask) {
      return;
    }
    if (!taskEvidenceFile) {
      setFormError("Debes seleccionar una evidencia (imagen o PDF) para cargar en la tarea.");
      return;
    }

    await runMutation(
      async () => {
        await addTreatmentTaskEvidence(selectedTreatment.id, selectedTask.id, {
          file: taskEvidenceFile,
          note: taskEvidenceNote,
        });
        setTaskEvidenceFile(null);
        setTaskEvidenceNote("");
        setTaskEvidenceInputKey((current) => current + 1);
      },
      "Evidencia cargada en la tarea.",
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
          onChange={(event: ChangeEvent<HTMLInputElement>) => { setSearch(event.target.value); setPage(1); }}
          placeholder="Buscar por tratamiento, anomalia, responsable o sector"
          type="search"
          value={search}
        />
        <div className="treatment-toolbar-actions">
          <select onChange={(event) => setSelectedCandidateId(event.target.value)} value={selectedCandidateId}>
            <option value="">Seleccionar anomalia clasificada...</option>
            {(supportData?.createCandidates ?? []).map((candidate) => (
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
                <h2>Tratamientos ({supportData?.treatmentsTotal ?? filteredTreatments.length})</h2>
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
                      Generada por: {anomaly.reporter?.full_name || anomaly.reporter?.username || "Sin dato"} | Proceso afectado: {anomaly.area?.name || "-"} | Proceso origen: {anomaly.anomaly_origin?.name || "-"}
                    </small>
                  </button>
                );
              })}
              {!filteredTreatments.length ? <p className="muted-copy">No hay tratamientos disponibles para mostrar.</p> : null}
            </div>
            <PaginationControls
              page={page}
              totalCount={supportData?.treatmentsTotal ?? 0}
              onPageChange={setPage}
              disabled={loading}
            />
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
                        Anomalia principal: <strong>{selectedTreatment.primary_anomaly.code}</strong> | {selectedTreatment.primary_anomaly.title}
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
                      Vista 1 - Convocatoria
                    </button>
                    <button
                      className={`button button-secondary${selectedTab === "analysis" ? " active" : ""}`}
                      onClick={() => setSelectedTab("analysis")}
                      type="button"
                    >
                      Vista 2 - Analisis
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
                        <div className="form-grid">
                          <label className="field field-span-2">
                            <span>ID / codigo / titulo</span>
                            <input
                              onChange={(event) => {
                                setLinkCandidateAnomalyFilter(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              placeholder="Buscar anomalia"
                              type="search"
                              value={linkCandidateAnomalyFilter}
                            />
                          </label>
                          <label className="field">
                            <span>Sector</span>
                            <input
                              onChange={(event) => {
                                setLinkCandidateSectorFilter(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              placeholder="Codigo o nombre de sector"
                              type="search"
                              value={linkCandidateSectorFilter}
                            />
                          </label>
                          <label className="field">
                            <span>Area</span>
                            <input
                              onChange={(event) => {
                                setLinkCandidateAreaFilter(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              placeholder="Codigo o nombre de area"
                              type="search"
                              value={linkCandidateAreaFilter}
                            />
                          </label>
                          <label className="field">
                            <span>Usuario reporta</span>
                            <select
                              onChange={(event) => {
                                setLinkCandidateUserFilter(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              value={linkCandidateUserFilter}
                            >
                              <option value="">Todos</option>
                              {(supportData?.users ?? []).map((user) => (
                                <option key={user.id} value={user.id}>
                                  {buildUsersLabel(user)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span>Fecha desde</span>
                            <input
                              onChange={(event) => {
                                setLinkCandidateDateFrom(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              type="date"
                              value={linkCandidateDateFrom}
                            />
                          </label>
                          <label className="field">
                            <span>Fecha hasta</span>
                            <input
                              onChange={(event) => {
                                setLinkCandidateDateTo(event.target.value);
                                setLinkCandidatePage(1);
                              }}
                              type="date"
                              value={linkCandidateDateTo}
                            />
                          </label>
                        </div>
                        <button
                          className="button button-secondary"
                          onClick={() => {
                            setLinkCandidateAnomalyFilter("");
                            setLinkCandidateSectorFilter("");
                            setLinkCandidateAreaFilter("");
                            setLinkCandidateUserFilter("");
                            setLinkCandidateDateFrom("");
                            setLinkCandidateDateTo("");
                            setLinkCandidatePage(1);
                          }}
                          type="button"
                        >
                          Limpiar filtros
                        </button>
                        <label className="field">
                          <span>Anomalias clasificadas disponibles</span>
                          <select onChange={(event) => setLinkAnomalyId(event.target.value)} value={linkAnomalyId}>
                            <option value="">Seleccionar...</option>
                            {unlinkedCandidates.map((candidate) => (
                              <option key={candidate.id} value={candidate.id}>
                                {`${candidate.code} - ${candidate.title} | Area: ${candidate.area?.name || "-"} | Usuario: ${candidate.reporter?.full_name || candidate.reporter?.username || "-"} | Fecha: ${formatDate(candidate.detected_at)}`}
                              </option>
                            ))}
                          </select>
                        </label>
                        <PaginationControls
                          page={linkCandidatePage}
                          totalCount={supportData?.linkCandidatesTotal ?? 0}
                          pageSize={10}
                          onPageChange={setLinkCandidatePage}
                          disabled={loading || busy}
                        />
                        <div className="stack-list compact">
                          {selectedTreatment.anomaly_links.map((link) => (
                            <div className="list-card compact" key={link.id}>
                              <div>
                                <strong>{link.anomaly.code}</strong>
                                <p>{link.anomaly.title}</p>
                                <small>
                                  Sector afectado: {link.anomaly.area?.name || "-"} | Sector origen: {link.anomaly.anomaly_origin?.name || "-"}
                                </small>
                              </div>
                              {link.is_primary ? <span className="status-badge info compact">Principal</span> : null}
                            </div>
                          ))}
                        </div>
                      </form>

                      <section className="form-section">
                        <div className="section-head compact">
                          <h3>Evidencias objetivas de anomalias vinculadas</h3>
                        </div>
                        <div className="stack-list compact">
                          {selectedTreatment.anomaly_links.map((link) => (
                            <div className="nested-card" key={`anomaly-evidence-${link.id}`}>
                              <div className="evidence-block">
                                <strong>{`${link.anomaly.code} - ${link.anomaly.title}`}</strong>
                                {link.anomaly.attachments.length ? (
                                  <ul className="evidence-list">
                                    {link.anomaly.attachments.map((attachment) => (
                                      <li className="evidence-item" key={attachment.id}>
                                        <a href={normalizeEvidenceUrl(attachment.file_url)} onClick={(event) => void handleOpenEvidence(event, attachment.file_url, attachment.original_name)} rel="noopener noreferrer" target="_blank">
                                          {attachment.original_name}
                                        </a>
                                        <small>
                                          {normalizeEvidenceType(attachment.content_type)} | {formatDate(attachment.created_at)}
                                        </small>
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="muted-copy">Sin evidencias objetivas en esta anomalia.</p>
                                )}
                              </div>
                            </div>
                          ))}
                          {!selectedTreatment.anomaly_links.length ? (
                            <p className="muted-copy">No hay anomalias vinculadas para mostrar evidencias.</p>
                          ) : null}
                        </div>
                      </section>
                    </div>
                  ) : null}

                  {selectedTab === "analysis" ? (
                    <div className="treatment-tab-content">
                      <form className="form-section" onSubmit={handleSaveAnalysis}>
                        <div className="section-head compact">
                          <h3>Metodo y observaciones</h3>
                          <button className="button button-primary" disabled={busy || !methodUsed || !observations.trim()} type="submit">
                            Guardar analisis
                          </button>
                        </div>
                        <label className="field">
                          <span>Metodo usado</span>
                          <select onChange={(event) => setMethodUsed(event.target.value)} required value={methodUsed}>
                            {METHOD_OPTIONS.map((method) => (
                              <option key={method.value || "none"} value={method.value}>
                                {method.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>Observaciones de tratamiento</span>
                          <textarea onChange={(event) => setObservations(event.target.value)} required rows={4} value={observations} />
                        </label>
                      </form>

                      <form className="form-section" onSubmit={handleAddTreatmentEvidence}>
                        <div className="section-head compact">
                          <h3>Evidencias del tratamiento</h3>
                          <button className="button button-primary" disabled={busy || !treatmentEvidenceFile} type="submit">
                            Cargar evidencia
                          </button>
                        </div>
                        <div className="form-grid">
                          <label className="field field-span-2">
                            <span>Archivo (imagen, PDF, Word, Excel, texto o ZIP)</span>
                            <input
                              accept={EVIDENCE_ACCEPT}
                              key={treatmentEvidenceInputKey}
                              onChange={handleTreatmentEvidenceFileChange}
                              type="file"
                            />
                          </label>
                          <label className="field field-span-2">
                            <span>Nota de evidencia (opcional)</span>
                            <textarea
                              onChange={(event) => setTreatmentEvidenceNote(event.target.value)}
                              rows={3}
                              value={treatmentEvidenceNote}
                            />
                          </label>
                        </div>
                        <div className="stack-list compact">
                          {selectedTreatment.evidences.length ? (
                            selectedTreatment.evidences.map((evidence) => (
                              <div className="list-card compact" key={evidence.id}>
                                <div className="evidence-block">
                                  <a className="text-link" href={normalizeEvidenceUrl(evidence.file_url)} onClick={(event) => void handleOpenEvidence(event, evidence.file_url, evidence.original_name)} rel="noopener noreferrer" target="_blank">{evidence.original_name}</a>
                                  <small>
                                    {normalizeEvidenceType(evidence.content_type)} | {formatDate(evidence.created_at)}
                                  </small>
                                  <p>{evidence.note || "Sin nota"}</p>
                                </div>
                              </div>
                            ))
                          ) : (
                            <p className="muted-copy">Todavia no hay evidencias cargadas en este tratamiento.</p>
                          )}
                        </div>
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
                          <button className="button button-primary" disabled={busy || !canCreateTask} type="submit">
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
                              required
                              value={taskDraft.responsible}
                            >
                              <option value="">Seleccionar responsable...</option>
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
                              required
                              type="date"
                              value={taskDraft.execution_date}
                            />
                          </label>

                          <label className="field field-span-2">
                            <span>Causa raiz asociada</span>
                            <select
                              onChange={(event) => handleTaskDraftChange("root_cause", event.target.value)}
                              required
                              value={taskDraft.root_cause}
                            >
                              <option value="">Seleccionar causa raiz...</option>
                              {rootCauseOptions.map((cause) => (
                                <option key={cause.id} value={cause.id}>{`Causa ${cause.sequence}: ${cause.description}`}</option>
                              ))}
                            </select>
                          </label>

                          <label className="field field-span-2">
                            <span>Descripcion / observaciones</span>
                            <textarea
                              onChange={(event) => handleTaskDraftChange("description", event.target.value)}
                              required
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
                                  Responsable: {task.responsible?.full_name || "Sin asignar"} | Ejecucion: {task.execution_date ? formatDate(task.execution_date) : "Sin fecha"}
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
                              <h3>{`Editar tarea | ${selectedTask.code || selectedTask.title}`}</h3>
                              <button className="button button-primary" disabled={busy} type="submit">
                                Guardar tarea
                              </button>
                            </div>

                            <p className="muted-copy">
                              Tratamiento: {selectedTreatment.code} | Anomalias asociadas: {selectedTask.anomaly_links.map((item) => item.anomaly.code).join(", ") || "Sin asociar"}
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
                                        <a href={normalizeEvidenceUrl(evidence.file_url)} onClick={(event) => void handleOpenEvidence(event, evidence.file_url, evidence.original_name)} rel="noopener noreferrer" target="_blank">
                                          {evidence.original_name}
                                        </a>
                                        <small>
                                          {normalizeEvidenceType(evidence.content_type)} | {formatDate(evidence.created_at)}
                                        </small>
                                        <p>{evidence.note || "Sin nota"}</p>
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <p className="muted-copy">Todavia no hay evidencias cargadas en esta tarea.</p>
                                )}
                              </div>
                            </section>
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



















