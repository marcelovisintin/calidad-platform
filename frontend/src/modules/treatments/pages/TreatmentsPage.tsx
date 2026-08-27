import { ChangeEvent, FormEvent, MouseEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  addTreatmentParticipant,
  addTreatmentRootCause,
  addTreatmentTask,
  addTreatmentEvidence,
  addTreatmentTaskEvidence,
  confirmTreatmentConvocation,
  fetchTreatmentCandidates,
  fetchTreatmentDetail,
  fetchTreatmentParticipantOptions,
  fetchTreatments,
  reconfigureTreatment,
  updateTreatment,
  updateTreatmentTask,
} from "../../../api/treatments";
import type { TreatmentCandidate, TreatmentParticipantOption, TreatmentTask } from "../../../api/types";
import { readStoredSession } from "../../../api/http";
import { formatDate, formatDateTime, toDateTimeLocalValue, toOffsetIso } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type TreatmentTab = "agenda" | "analysis";

type TaskDraft = {
  title: string;
  description: string;
  root_cause_ids: string[];
  responsible: string;
  execution_date: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
};

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
  root_cause_ids: [],
  responsible: "",
  execution_date: "",
  status: "pending",
};

function buildUsersLabel(user: TreatmentParticipantOption) {
  const name = user.full_name || user.username;
  const sector = user.sector?.name ? ` - ${user.sector.name}` : "";
  return `${name} (${user.username})${sector}`;
}

function getTreatmentTaskCount(treatment: { tasks: TreatmentTask[]; root_causes: Array<{ tasks?: TreatmentTask[] }> } | null) {
  if (!treatment) {
    return 0;
  }

  const taskIds = new Set<string>();
  for (const task of treatment.tasks ?? []) {
    taskIds.add(task.id);
  }
  for (const cause of treatment.root_causes ?? []) {
    for (const task of cause.tasks ?? []) {
      taskIds.add(task.id);
    }
  }
  return taskIds.size;
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

  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [scheduledFor, setScheduledFor] = useState("");
  const [treatmentLocation, setTreatmentLocation] = useState("");
  const [methodUsed, setMethodUsed] = useState("");
  const [observations, setObservations] = useState("");
  const [effectivenessEvaluationDate, setEffectivenessEvaluationDate] = useState("");
  const [effectivenessResponsibleId, setEffectivenessResponsibleId] = useState("");

  const [participantUserId, setParticipantUserId] = useState("");
  const [participantAreaId, setParticipantAreaId] = useState("");
  const [participantNote, setParticipantNote] = useState("");

  const [rootCauseDescription, setRootCauseDescription] = useState("");

  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK_DRAFT);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [treatmentEvidenceFile, setTreatmentEvidenceFile] = useState<File | null>(null);
  const [treatmentEvidenceNote, setTreatmentEvidenceNote] = useState("");
  const [taskEvidenceFile, setTaskEvidenceFile] = useState<File | null>(null);
  const [taskEvidenceNote, setTaskEvidenceNote] = useState("");
  const [treatmentEvidenceInputKey, setTreatmentEvidenceInputKey] = useState(0);
  const [taskEvidenceInputKey, setTaskEvidenceInputKey] = useState(0);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionResponsibleId, setCorrectionResponsibleId] = useState("");
  const [correctionRelatedIds, setCorrectionRelatedIds] = useState<string[]>([]);
  const [correctionCandidates, setCorrectionCandidates] = useState<TreatmentCandidate[]>([]);
  const [correctionLoading, setCorrectionLoading] = useState(false);

  const {
    data: supportData,
    loading,
    error,
    reload: reloadSupport,
  } = useAsyncTask(async () => {
    const [treatments, users] = await Promise.all([
      fetchTreatments(page, deferredSearch),
      selectedTreatmentId ? fetchTreatmentParticipantOptions(selectedTreatmentId) : Promise.resolve([]),
    ]);

    return {
      treatments: treatments.results,
      treatmentsTotal: treatments.count,
      users,
    };
  }, [
    page,
    deferredSearch,
    selectedTreatmentId,
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
      setTreatmentLocation("");
      setMethodUsed("");
      setObservations("");
      setEffectivenessEvaluationDate("");
      setEffectivenessResponsibleId("");
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
    setTreatmentLocation(selectedTreatment.treatment_location || "");
    setMethodUsed(selectedTreatment.method_used || "");
    setObservations(selectedTreatment.observations || "");
    setEffectivenessEvaluationDate(selectedTreatment.effectiveness_evaluation_date || "");
    setEffectivenessResponsibleId(selectedTreatment.effectiveness_responsible?.id || "");
  }, [selectedTreatment]);

  const rootCauseOptions = selectedTreatment?.root_causes ?? [];
  const participantOptions = useMemo(
    () => (selectedTreatment?.participants ?? []).filter((participant) => participant.user),
    [selectedTreatment?.participants],
  );
  const effectivenessResponsibleOptions = useMemo(() => {
    const participantUserIds = new Set(
      participantOptions
        .map((participant) => participant.user?.id)
        .filter((userId): userId is string => Boolean(userId)),
    );

    return (supportData?.users ?? [])
      .filter(
        (user) =>
          participantUserIds.has(user.id) || user.access_level === "mando_medio_activo",
      )
      .map((user) => ({
        ...user,
        isParticipant: participantUserIds.has(user.id),
      }));
  }, [participantOptions, supportData?.users]);
  const participantAreaOptions = useMemo(() => {
    const areaMap = new Map<string, { id: string; name: string }>();
    for (const user of supportData?.users ?? []) {
      if (user.sector?.id) {
        areaMap.set(user.sector.id, { id: user.sector.id, name: user.sector.name });
      }
    }
    return Array.from(areaMap.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [supportData?.users]);
  const participantUserOptions = useMemo(() => {
    const users = supportData?.users ?? [];
    if (!participantAreaId) {
      return users;
    }
    return users.filter((user) => user.sector?.id === participantAreaId);
  }, [participantAreaId, supportData?.users]);

  useEffect(() => {
    if (!participantUserOptions.length) {
      setParticipantUserId("");
      return;
    }

    if (participantUserId && participantUserOptions.some((user) => user.id === participantUserId)) {
      return;
    }

    setParticipantUserId(participantUserOptions[0].id);
  }, [participantUserId, participantUserOptions]);

  const hasEffectivenessAssignment = Boolean(effectivenessEvaluationDate) && Boolean(effectivenessResponsibleId);
  const savedEffectivenessDate = selectedTreatment?.effectiveness_evaluation_date || "";
  const savedEffectivenessResponsibleId = selectedTreatment?.effectiveness_responsible?.id || "";
  const hasSavedEffectivenessAssignment = Boolean(savedEffectivenessDate) && Boolean(savedEffectivenessResponsibleId);
  const hasPendingEffectivenessChanges =
    Boolean(selectedTreatment) &&
    (effectivenessEvaluationDate !== savedEffectivenessDate || effectivenessResponsibleId !== savedEffectivenessResponsibleId);
  const treatmentTaskCount = getTreatmentTaskCount(selectedTreatment);
  const hasTreatmentTasks = treatmentTaskCount > 0;
  const canCreateTask =
    Boolean(taskDraft.title.trim()) &&
    Boolean(taskDraft.description.trim()) &&
    taskDraft.root_cause_ids.length > 0 &&
    Boolean(taskDraft.responsible) &&
    Boolean(taskDraft.execution_date);
  const selectedTask: TreatmentTask | null = useMemo(
    () => selectedTreatment?.tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, selectedTreatment?.tasks],
  );
  const treatmentClosed = Boolean(selectedTreatment?.is_locked);
  const treatmentLocked = treatmentClosed || !selectedTreatment?.can_manage;
  const convocationConfirmed = Boolean(selectedTreatment?.convocation_confirmed_at);

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
      root_cause_ids: selectedTask.root_causes?.length
        ? selectedTask.root_causes.map((cause) => cause.id)
        : selectedTask.root_cause
          ? [selectedTask.root_cause]
          : [],
      responsible: selectedTask.responsible?.id || "",
      execution_date: selectedTask.execution_date || "",
      status: selectedTask.status as TaskDraft["status"],
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

  const saveAnalysisDraftIfChanged = async () => {
    if (!selectedTreatment) {
      return;
    }

    const nextMethodUsed = methodUsed;
    const nextObservations = observations.trim();
    const savedMethodUsed = selectedTreatment.method_used || "";
    const savedObservations = selectedTreatment.observations || "";

    if (nextMethodUsed === savedMethodUsed && nextObservations === savedObservations) {
      return;
    }

    await updateTreatment(selectedTreatment.id, {
      method_used: nextMethodUsed,
      observations: nextObservations,
    });
  };

  const handleSaveAgenda = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }
    if (convocationConfirmed) {
      setFormError("La convocatoria ya fue confirmada y no admite modificaciones.");
      return;
    }
    if (!scheduledFor) {
      setFormError("Debe indicar la fecha y hora programada.");
      return;
    }
    const confirmed = window.confirm(
      "¿Está seguro? ¿Convocó a los usuarios necesarios? Una vez confirmada la agenda no podrá convocar más usuarios.",
    );
    if (!confirmed) {
      return;
    }

    await runMutation(async () => {
      await confirmTreatmentConvocation(selectedTreatment.id, {
        scheduled_for: toOffsetIso(scheduledFor),
        treatment_location: treatmentLocation.trim(),
      });
    }, "Convocatoria confirmada. Se enviaron los avisos a los usuarios habilitados para recibir notificaciones.");
  };

  const handleAddParticipant = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !participantUserId) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }
    if (convocationConfirmed) {
      setFormError("La convocatoria ya fue confirmada y no admite nuevos usuarios.");
      return;
    }

    await runMutation(async () => {
      await addTreatmentParticipant(selectedTreatment.id, {
        user: participantUserId,
        role: "convoked",
        note: participantNote.trim(),
      });
      setParticipantNote("");
    }, "Participante convocado al tratamiento.");
  };

  const handleOpenCompositionCorrection = async () => {
    if (!selectedTreatment?.can_reconfigure) {
      return;
    }
    setCorrectionOpen(true);
    setCorrectionReason("");
    setCorrectionResponsibleId(selectedTreatment.responsible?.id || "");
    setCorrectionRelatedIds(
      selectedTreatment.anomaly_links.filter((link) => !link.is_primary).map((link) => link.anomaly.id),
    );
    setCorrectionLoading(true);
    setFormError(null);
    try {
      const response = await fetchTreatmentCandidates({
        anchorId: selectedTreatment.primary_anomaly.id,
        pageSize: 200,
      });
      const combined = new Map<string, TreatmentCandidate>();
      for (const link of selectedTreatment.anomaly_links.filter((item) => !item.is_primary)) {
        combined.set(link.anomaly.id, link.anomaly as TreatmentCandidate);
      }
      for (const candidate of response.results) {
        combined.set(candidate.id, candidate);
      }
      setCorrectionCandidates(Array.from(combined.values()));
    } catch (candidateError) {
      setFormError(candidateError instanceof Error ? candidateError.message : "No se pudieron cargar las anomalías elegibles.");
      setCorrectionOpen(false);
    } finally {
      setCorrectionLoading(false);
    }
  };

  const toggleCorrectionAnomaly = (anomalyId: string) => {
    setCorrectionRelatedIds((current) => current.includes(anomalyId)
      ? current.filter((value) => value !== anomalyId)
      : [...current, anomalyId]);
  };

  const handleCorrectComposition = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !correctionResponsibleId || !correctionReason.trim()) {
      setFormError("Selecciona el responsable e indica el motivo de la corrección.");
      return;
    }
    await runMutation(async () => {
      await reconfigureTreatment(selectedTreatment.id, {
        related_anomalies: correctionRelatedIds,
        responsible: correctionResponsibleId,
        reason: correctionReason.trim(),
      });
      setCorrectionOpen(false);
      setCorrectionReason("");
    }, "Conformación del tratamiento corregida y auditada.");
  };

  const handleSaveAnalysis = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }
    const freshTreatment = await fetchTreatmentDetail(selectedTreatment.id);
    if (getTreatmentTaskCount(freshTreatment) === 0) {
      setFormError("Debes registrar al menos una accion surgida del tratamiento antes de guardar el analisis.");
      return;
    }
    if (!effectivenessEvaluationDate) {
      setFormError("Debes indicar la fecha de evaluacion de eficacia.");
      return;
    }
    if (!effectivenessResponsibleId) {
      setFormError("Debes seleccionar el responsable de evaluacion de eficacia.");
      return;
    }

    const confirmSave = window.confirm(
      "Confirmas guardar la evaluacion de eficacia y los datos de analisis cargados? Esto impactara en el seguimiento de la anomalia.",
    );
    if (!confirmSave) {
      return;
    }

    await runMutation(async () => {
      await updateTreatment(selectedTreatment.id, {
        method_used: methodUsed,
        observations: observations.trim(),
        effectiveness_evaluation_date: effectivenessEvaluationDate,
        effectiveness_responsible: effectivenessResponsibleId,
      });
    }, "Analisis de tratamiento guardado.");
  };

  const handleAddRootCause = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !rootCauseDescription.trim()) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }

    await runMutation(async () => {
      await saveAnalysisDraftIfChanged();
      await addTreatmentRootCause(selectedTreatment.id, rootCauseDescription.trim());
      setRootCauseDescription("");
    }, "Causa raiz registrada.");
  };

  const handleTaskDraftChange = (field: Exclude<keyof TaskDraft, "root_cause_ids">, value: string) => {
    setTaskDraft((current) => ({ ...current, [field]: value }));
  };

  const toggleTaskRootCause = (rootCauseId: string) => {
    setTaskDraft((current) => {
      const selected = current.root_cause_ids.includes(rootCauseId);
      return {
        ...current,
        root_cause_ids: selected
          ? current.root_cause_ids.filter((id) => id !== rootCauseId)
          : [...current.root_cause_ids, rootCauseId],
      };
    });
  };

  const handleTreatmentEvidenceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setTreatmentEvidenceFile(file);
  };

  const handleTaskEvidenceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setTaskEvidenceFile(file);
  };

  const handleAddTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) {
      return;
    }
    if (!selectedTreatment) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }

    if (!taskDraft.title.trim()) {
      setFormError("La accion es obligatoria.");
      return;
    }
    if (!taskDraft.description.trim()) {
      setFormError("La descripcion de la accion es obligatoria.");
      return;
    }
    if (!taskDraft.root_cause_ids.length) {
      setFormError("Debes seleccionar al menos una causa raiz asociada.");
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
    await runMutation(async () => {
      await addTreatmentTask(selectedTreatment.id, {
        title: taskDraft.title.trim(),
        description: taskDraft.description.trim(),
        root_cause_ids: taskDraft.root_cause_ids,
        responsible: taskDraft.responsible || null,
        execution_date: taskDraft.execution_date || null,
        status: taskDraft.status,
      });
      setTaskDraft(EMPTY_TASK_DRAFT);
    }, "Accion de tratamiento creada.");
  };

  const handleSelectTask = (task: TreatmentTask) => {
    setSelectedTaskId(task.id);
    setTaskDraft({
      title: task.title,
      description: task.description || "",
      root_cause_ids: task.root_causes?.length
        ? task.root_causes.map((cause) => cause.id)
        : task.root_cause
          ? [task.root_cause]
          : [],
      responsible: task.responsible?.id || "",
      execution_date: task.execution_date || "",
      status: task.status as TaskDraft["status"],
    });
  };

  const handleUpdateTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !selectedTask || !taskDraft.title.trim()) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }

    await runMutation(
      async () => {
        await updateTreatmentTask(selectedTreatment.id, selectedTask.id, {
          title: taskDraft.title.trim(),
          description: taskDraft.description.trim(),
          root_cause_ids: taskDraft.root_cause_ids,
          responsible: taskDraft.responsible || null,
          execution_date: taskDraft.execution_date || null,
          status: taskDraft.status,
        });
      },
      "Accion actualizada.",
      true,
    );
  };

  const handleAddTreatmentEvidence = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }
    if (!treatmentEvidenceFile) {
      setFormError("Debes seleccionar una evidencia (imagen o PDF) para cargar al tratamiento.");
      return;
    }

    await runMutation(async () => {
      await saveAnalysisDraftIfChanged();
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
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }
    if (!taskEvidenceFile) {
      setFormError("Debes seleccionar una evidencia (imagen o PDF) para cargar en la accion.");
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
      "Evidencia cargada en la accion.",
      true,
    );
  };
return (
    <section className="page-shell">
      <PageHeader
        title="Tratamientos"
      description="Gestion de tratamientos por anomalia con Revisión de hallazgos: convocatoria, analisis de causa y acciones asociadas."
      />

      <TabbedFilters
        ariaLabel="Filtros de tratamientos"
        onClear={() => { setSearch(""); setPage(1); }}
        items={[{
          id: "search",
          label: "Buscar tratamiento",
          active: Boolean(search),
          content: <input aria-label="Buscar tratamiento" onChange={(event: ChangeEvent<HTMLInputElement>) => { setSearch(event.target.value); setPage(1); }} placeholder="Tratamiento, anomalia, responsable o sector" type="search" value={search} />,
        }]}
      />

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
                      Generada por: {anomaly.reporter?.full_name || anomaly.reporter?.username || "Sin dato"} | Area: {anomaly.area?.name || "-"} | Asignado a: {anomaly.imputed_area?.name || anomaly.anomaly_origin?.name || "-"}
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
                  {treatmentClosed ? (
                    <div className="panel info compact-inline-panel">
                      <p>Tratamiento cerrado por validacion eficaz. Los datos quedan solo lectura y las anomalias asociadas fueron cerradas automaticamente.</p>
                    </div>
                  ) : !selectedTreatment.can_manage ? (
                    <div className="panel info compact-inline-panel">
                      <p>Acceso de solo lectura. Solo Calidad, administradores y el responsable del tratamiento pueden modificar sus datos.</p>
                    </div>
                  ) : null}

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
                          <button className="button button-primary" disabled={busy || treatmentLocked || convocationConfirmed} type="submit">
                            {convocationConfirmed ? "Agenda confirmada" : "Guardar agenda"}
                          </button>
                        </div>
                        <label className="field">
                          <span>Fecha y hora programada</span>
                          <input
                            name="scheduled_for"
                            disabled={treatmentLocked || convocationConfirmed}
                            onChange={(event) => setScheduledFor(event.target.value)}
                            type="datetime-local"
                            required
                            value={scheduledFor}
                          />
                        </label>
                        <label className="field">
                          <span>Lugar de tratamiento</span>
                          <input
                            name="treatment_location"
                            disabled={treatmentLocked || convocationConfirmed}
                            maxLength={200}
                            onChange={(event) => setTreatmentLocation(event.target.value)}
                            placeholder="Ej: Sala de reuniones, linea 1, sector pintura"
                            type="text"
                            value={treatmentLocation}
                          />
                        </label>
                        {convocationConfirmed ? (
                          <div className="panel info compact-inline-panel">
                            <p>
                              Convocatoria confirmada el {formatDateTime(selectedTreatment.convocation_confirmed_at)}
                              {selectedTreatment.convocation_confirmed_by
                                ? ` por ${selectedTreatment.convocation_confirmed_by.full_name || selectedTreatment.convocation_confirmed_by.username}`
                                : ""}. La fecha, el lugar y los usuarios convocados quedan en solo lectura.
                            </p>
                          </div>
                        ) : null}
                      </form>

                      <form className="form-section" onSubmit={handleAddParticipant}>
                        <div className="section-head compact">
                          <h3>Usuarios convocados</h3>
                          <button className="button button-primary" disabled={busy || treatmentLocked || convocationConfirmed || !participantUserId} type="submit">
                            Convocar
                          </button>
                        </div>
                        <div className="form-grid">
                          <label className="field">
                            <span>Area</span>
                            <select disabled={treatmentLocked || convocationConfirmed} onChange={(event) => setParticipantAreaId(event.target.value)} value={participantAreaId}>
                              <option value="">Todas las areas</option>
                              {participantAreaOptions.map((area) => (
                                <option key={area.id} value={area.id}>
                                  {area.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span>Usuario</span>
                            <select disabled={treatmentLocked || convocationConfirmed} onChange={(event) => setParticipantUserId(event.target.value)} value={participantUserId}>
                              {participantUserOptions.map((user) => (
                                <option key={user.id} value={user.id}>
                                  {buildUsersLabel(user)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <div className="field">
                            <span>Participacion</span>
                            <strong>Convocado</strong>
                          </div>
                        </div>
                        <label className="field">
                          <span>Nota</span>
                          <textarea
                            name="participant_note"
                            disabled={treatmentLocked || convocationConfirmed}
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

                      <section className="form-section">
                        <div className="section-head compact">
                          <div>
                            <h3>Anomalías incluidas por Calidad</h3>
                            <small>La composición es de solo lectura para el responsable del tratamiento.</small>
                          </div>
                          {selectedTreatment.can_reconfigure ? (
                            <button
                              className="button button-secondary"
                              disabled={busy || correctionLoading}
                              onClick={() => void handleOpenCompositionCorrection()}
                              type="button"
                            >
                              Corregir conformación
                            </button>
                          ) : null}
                        </div>

                        <div className="stack-list compact">
                          {selectedTreatment.anomaly_links.map((link) => (
                            <div className="list-card compact" key={`locked-${link.id}`}>
                              <div>
                                <strong>{link.anomaly.code}</strong>
                                <p>{link.anomaly.title}</p>
                                <small>
                                  Proceso: {link.anomaly.imputed_area?.name || link.anomaly.area?.name || "-"} | Estado: {link.anomaly.current_status}
                                </small>
                              </div>
                              <span className={`status-badge ${link.is_primary ? "info" : "success"} compact`}>
                                {link.is_primary ? "Principal" : "Relacionada"}
                              </span>
                            </div>
                          ))}
                        </div>

                        {correctionOpen ? (
                          <form className="nested-card" onSubmit={handleCorrectComposition}>
                            <div className="section-head compact">
                              <div>
                                <h4>Corrección administrativa</h4>
                                <small>Disponible solamente antes de iniciar convocatoria, agenda, análisis o carga de evidencias.</small>
                              </div>
                            </div>
                            <label className="field">
                              <span>Responsable único</span>
                              <select
                                onChange={(event) => setCorrectionResponsibleId(event.target.value)}
                                required
                                value={correctionResponsibleId}
                              >
                                <option value="">Seleccionar responsable...</option>
                                {(supportData?.users ?? [])
                                  .filter((option) => ["mando_medio_activo", "administrador", "desarrollador"].includes(option.access_level))
                                  .map((option) => (
                                    <option key={option.id} value={option.id}>{buildUsersLabel(option)}</option>
                                  ))}
                              </select>
                            </label>
                            <div className="stack-list compact classification-candidate-list">
                              {correctionCandidates.map((candidate) => (
                                <label className="list-card compact classification-candidate" key={`correct-${candidate.id}`}>
                                  <input
                                    checked={correctionRelatedIds.includes(candidate.id)}
                                    onChange={() => toggleCorrectionAnomaly(candidate.id)}
                                    type="checkbox"
                                  />
                                  <span>
                                    <strong>{candidate.code}</strong>
                                    <small>{candidate.title}</small>
                                  </span>
                                </label>
                              ))}
                            </div>
                            <label className="field">
                              <span>Motivo obligatorio</span>
                              <textarea
                                onChange={(event) => setCorrectionReason(event.target.value)}
                                required
                                rows={3}
                                value={correctionReason}
                              />
                            </label>
                            <div className="form-actions">
                              <button className="button button-primary" disabled={busy} type="submit">Guardar corrección</button>
                              <button className="button button-secondary" onClick={() => setCorrectionOpen(false)} type="button">Cancelar</button>
                            </div>
                          </form>
                        ) : null}
                      </section>

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
                      <div className="form-section">
                        <div className="section-head compact">
                          <h3>Metodo y observaciones</h3>
                        </div>
                        <label className="field">
                          <span>Metodo usado</span>
                          <select disabled={treatmentLocked} onChange={(event) => setMethodUsed(event.target.value)} value={methodUsed}>
                            {METHOD_OPTIONS.map((method) => (
                              <option key={method.value || "none"} value={method.value}>
                                {method.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>Observaciones de tratamiento</span>
                          <textarea disabled={treatmentLocked} onChange={(event) => setObservations(event.target.value)} rows={4} value={observations} />
                        </label>
                      </div>

                      <form className="form-section" onSubmit={handleAddTreatmentEvidence}>
                        <div className="section-head compact">
                          <h3>Evidencias del tratamiento</h3>
                          <button className="button button-primary" disabled={busy || treatmentLocked || !treatmentEvidenceFile} type="submit">
                            Cargar evidencia
                          </button>
                        </div>
                        <div className="form-grid">
                          <label className="field field-span-2">
                            <span>Archivo (imagen, PDF, Word, Excel, texto o ZIP)</span>
                            <input
                              accept={EVIDENCE_ACCEPT}
                              disabled={treatmentLocked}
                              key={treatmentEvidenceInputKey}
                              onChange={handleTreatmentEvidenceFileChange}
                              type="file"
                            />
                          </label>
                          <label className="field field-span-2">
                            <span>Nota de evidencia (opcional)</span>
                            <textarea
                              disabled={treatmentLocked}
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
                          <button className="button button-primary" disabled={busy || treatmentLocked || !rootCauseDescription.trim()} type="submit">
                            Agregar causa
                          </button>
                        </div>
                        <label className="field">
                          <span>Descripcion de la causa raiz</span>
                          <textarea
                            disabled={treatmentLocked}
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
                          <h3>Acciones surgidas del tratamiento</h3>
                          <button className="button button-primary" disabled={busy || treatmentLocked || !canCreateTask} type="submit">
                            Crear accion
                          </button>
                        </div>

                        <div className="form-grid">
                          <label className="field">
                            <span>Accion</span>
                            <input
                              name="task_title"
                              disabled={treatmentLocked}
                              onChange={(event) => handleTaskDraftChange("title", event.target.value)}
                              placeholder="Ej. Verificar ajuste de sector"
                              required
                              type="text"
                              value={taskDraft.title}
                            />
                          </label>

                          <label className="field">
                            <span>Estado</span>
                            <select
                              disabled={treatmentLocked}
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
                              disabled={treatmentLocked || !(supportData?.users.length)}
                              onChange={(event) => handleTaskDraftChange("responsible", event.target.value)}
                              required
                              value={taskDraft.responsible}
                            >
                              <option value="">Seleccionar responsable...</option>
                              {(supportData?.users ?? []).map((user) => (
                                <option key={user.id} value={user.id}>
                                  {user.full_name || user.username}
                                </option>
                              ))}
                            </select>
                            {!(supportData?.users.length) ? <small className="muted-copy">No hay usuarios activos disponibles.</small> : null}
                          </label>

                          <label className="field">
                            <span>Fecha de ejecucion</span>
                            <input
                              disabled={treatmentLocked}
                              onChange={(event) => handleTaskDraftChange("execution_date", event.target.value)}
                              required
                              type="date"
                              value={taskDraft.execution_date}
                            />
                          </label>

                          <div className="field field-span-2">
                            <span>Causas raiz asociadas</span>
                            <div className="treatment-checkbox-grid">
                              {rootCauseOptions.map((cause) => (
                                <label className="checkbox-inline" key={cause.id}>
                                  <input
                                    checked={taskDraft.root_cause_ids.includes(cause.id)}
                                    disabled={treatmentLocked}
                                    onChange={() => toggleTaskRootCause(cause.id)}
                                    type="checkbox"
                                  />
                                  <span>{`Causa ${cause.sequence}: ${cause.description}`}</span>
                                </label>
                              ))}
                            </div>
                            {!rootCauseOptions.length ? <p className="muted-copy">Primero registra al menos una causa raiz.</p> : null}
                          </div>

                          <label className="field field-span-2">
                            <span>Descripcion / observaciones</span>
                            <textarea
                              disabled={treatmentLocked}
                              onChange={(event) => handleTaskDraftChange("description", event.target.value)}
                              required
                              rows={3}
                              value={taskDraft.description}
                            />
                          </label>
                        </div>

                      </form>

                      <div className="form-section">
                        <div className="section-head compact">
                          <h3>Detalle de acciones</h3>
                        </div>

                        <div className="stack-list compact">
                          {selectedTreatment.tasks.map((task) => (
                            <div className="list-card compact" key={task.id}>
                              <div>
                                <strong>{task.title}</strong>
                                <p>{task.description || "Sin descripcion"}</p>
                                <small>
                                  Responsable: {task.responsible?.full_name || "Sin asignar"} | Ejecucion: {task.execution_date ? formatDate(task.execution_date) : "Sin fecha"}
                                </small>
                                <small>
                                  Causas:{" "}
                                  {task.root_causes?.length
                                    ? task.root_causes.map((cause) => `Causa ${cause.sequence}`).join(", ")
                                    : task.root_cause
                                      ? "Causa asociada"
                                      : "Sin causas"}
                                </small>
                              </div>
                              <StatusBadge compact value={task.status} />
                            </div>
                          ))}
                          {!selectedTreatment.tasks.length ? <p className="muted-copy">No hay acciones registradas para este tratamiento.</p> : null}
                        </div>

                        <p className="muted-copy">
                          La edicion y carga de evidencias se realiza desde la pagina Acciones.
                        </p>
                      </div>

                      <form className="form-section" onSubmit={handleSaveAnalysis}>
                        <div className="section-head compact">
                          <div>
                            <p className="eyebrow">Paso final</p>
                            <h3>Evaluacion de eficacia</h3>
                          </div>
                          <button
                            className="button button-primary"
                            disabled={
                              busy ||
                              treatmentLocked ||
                              !hasEffectivenessAssignment
                            }
                            type="submit"
                          >
                            Guardar analisis
                          </button>
                        </div>
                        <div className={`panel ${hasPendingEffectivenessChanges ? "warning" : "info"} compact-inline-panel`}>
                          {hasSavedEffectivenessAssignment && !hasPendingEffectivenessChanges ? (
                            <p>
                              Guardado: {formatDate(savedEffectivenessDate)} | Responsable:{" "}
                              {selectedTreatment.effectiveness_responsible?.full_name || selectedTreatment.effectiveness_responsible?.username}
                            </p>
                          ) : (
                            <p>
                              Completa la fecha y responsable de evaluacion. Si metodo y observaciones estan cargados, tambien se guardaran.
                            </p>
                          )}
                        </div>
                        {!effectivenessResponsibleOptions.length ? (
                          <div className="panel warning compact-inline-panel">
                            <p>No hay usuarios convocados ni usuarios con nivel Mando medio activo disponibles.</p>
                          </div>
                        ) : (
                          <div className="form-grid">
                            <label className="field">
                              <span>Fecha de evaluacion de eficacia</span>
                              <input
                                onChange={(event) => setEffectivenessEvaluationDate(event.target.value)}
                                disabled={treatmentLocked}
                                required
                                type="date"
                                value={effectivenessEvaluationDate}
                              />
                            </label>
                            <label className="field">
                              <span>Responsable</span>
                              <select
                                onChange={(event) => setEffectivenessResponsibleId(event.target.value)}
                                disabled={treatmentLocked}
                                required
                                value={effectivenessResponsibleId}
                              >
                                <option value="">Seleccionar responsable...</option>
                                {effectivenessResponsibleOptions.map((user) => (
                                  <option key={user.id} value={user.id}>
                                    {user.full_name || user.username}
                                    {user.isParticipant ? " - Convocado" : " - Mando medio"}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                        )}
                        {hasTreatmentTasks ? (
                          <p className="muted-copy">{`Acciones registradas para este tratamiento: ${treatmentTaskCount}.`}</p>
                        ) : (
                          <p className="muted-copy">Registra al menos una accion antes de guardar el analisis.</p>
                        )}
                      </form>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="panel muted">
                  <h2>Sin tratamiento seleccionado</h2>
                  <p>Selecciona un tratamiento del listado para gestionar convocatoria, analisis, causas y acciones.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}





















