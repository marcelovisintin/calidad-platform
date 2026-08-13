import { ChangeEvent, FormEvent, MouseEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  fetchTreatmentParticipantOptions,
  fetchOpenTreatmentOptions,
  fetchTreatments,
  updateTreatment,
  updateTreatmentTask,
} from "../../../api/treatments";
import type { TreatmentParticipantOption, TreatmentTask } from "../../../api/types";
import { readStoredSession } from "../../../api/http";
import { formatDate, toDateTimeLocalValue, toOffsetIso } from "../../../app/utils";
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
  anomaly_ids: string[];
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
  anomaly_ids: [],
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
  const requestedAnomalyId = (searchParams.get("anomaly") || "").trim();

  const [selectedTreatmentId, setSelectedTreatmentId] = useState(() => requestedTreatmentId);
  const [selectedTab, setSelectedTab] = useState<TreatmentTab>("agenda");

  const [selectedCandidateId, setSelectedCandidateId] = useState(() => requestedAnomalyId);
  const [selectedOpenTreatmentId, setSelectedOpenTreatmentId] = useState("");
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

  const [linkAnomalyIds, setLinkAnomalyIds] = useState<string[]>([]);
  const [linkCandidatePage, setLinkCandidatePage] = useState(1);
  const [linkCandidateAnomalyDraft, setLinkCandidateAnomalyDraft] = useState("");
  const [linkCandidateSectorDraft, setLinkCandidateSectorDraft] = useState("");
  const [linkCandidateAreaDraft, setLinkCandidateAreaDraft] = useState("");
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
      fetchTreatmentCandidates({
        page: 1,
        pageSize: 100,
        anomaly: requestedAnomalyId,
      }),
      linkCandidatesPromise,
      selectedTreatmentId ? fetchTreatmentParticipantOptions(selectedTreatmentId) : Promise.resolve([]),
    ]);

    return {
      treatments: treatments.results,
      treatmentsTotal: treatments.count,
      createCandidates: createCandidates.results,
      linkCandidates: linkCandidates.results,
      linkCandidatesTotal: linkCandidates.count,
      users,
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
    requestedAnomalyId,
  ]);

  useEffect(() => {
    if (requestedAnomalyId) {
      setSelectedCandidateId(requestedAnomalyId);
    }
  }, [requestedAnomalyId]);

  const {
    data: openTreatmentOptions,
    reload: reloadOpenTreatmentOptions,
  } = useAsyncTask(async () => {
    if (!selectedCandidateId) {
      return [];
    }
    return fetchOpenTreatmentOptions(selectedCandidateId);
  }, [selectedCandidateId]);

  const openTreatments = openTreatmentOptions ?? [];

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
      if (linkAnomalyIds.length) {
        setLinkAnomalyIds([]);
      }
      return;
    }

    const available = (supportData?.linkCandidates ?? []).filter(
      (candidate) => !selectedTreatment.anomaly_links.some((link) => link.anomaly.id === candidate.id),
    );

    if (!available.length) {
      if (linkAnomalyIds.length) {
        setLinkAnomalyIds([]);
      }
      return;
    }

    const stillAvailable = linkAnomalyIds.filter((id) => available.some((item) => item.id === id));
    if (stillAvailable.length === linkAnomalyIds.length && stillAvailable.length > 0) {
      return;
    }

    setLinkAnomalyIds(stillAvailable.length ? stillAvailable : [available[0].id]);
  }, [linkAnomalyIds, selectedTreatment, supportData?.linkCandidates]);

  useEffect(() => {
    if (!openTreatments.length) {
      setSelectedOpenTreatmentId("");
      return;
    }
    if (selectedOpenTreatmentId && openTreatments.some((treatment) => treatment.id === selectedOpenTreatmentId)) {
      return;
    }
    setSelectedOpenTreatmentId(openTreatments[0].id);
  }, [openTreatments, selectedOpenTreatmentId]);

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
  const participantOptions = useMemo(
    () => (selectedTreatment?.participants ?? []).filter((participant) => participant.user),
    [selectedTreatment?.participants],
  );
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
    Boolean(taskDraft.execution_date) &&
    taskDraft.anomaly_ids.length > 0;
  const selectedTask: TreatmentTask | null = useMemo(
    () => selectedTreatment?.tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, selectedTreatment?.tasks],
  );
  const treatmentClosed = Boolean(selectedTreatment?.is_locked);
  const treatmentLocked = treatmentClosed || !selectedTreatment?.can_manage;

  const handleApplyLinkCandidateFilters = () => {
    setLinkCandidateAnomalyFilter(linkCandidateAnomalyDraft.trim());
    setLinkCandidateSectorFilter(linkCandidateSectorDraft.trim());
    setLinkCandidateAreaFilter(linkCandidateAreaDraft.trim());
    setLinkCandidatePage(1);
  };

  const clearLinkCandidateFilters = () => {
    setLinkCandidateAnomalyDraft("");
    setLinkCandidateSectorDraft("");
    setLinkCandidateAreaDraft("");
    setLinkCandidateAnomalyFilter("");
    setLinkCandidateSectorFilter("");
    setLinkCandidateAreaFilter("");
    setLinkCandidateUserFilter("");
    setLinkCandidateDateFrom("");
    setLinkCandidateDateTo("");
    setLinkCandidatePage(1);
  };

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

  const handleCreateTreatment = async (forceCreateNew = false) => {
    if (!selectedCandidateId) {
      setFormError("Selecciona una anomalia disponible para tratamiento.");
      return;
    }

    setBusy(true);
    setFormError(null);
    setMessage(null);

    try {
      if (openTreatments.length && !forceCreateNew) {
        if (!selectedOpenTreatmentId) {
          setFormError("Selecciona el tratamiento abierto al que se asociara la anomalia.");
          return;
        }
        await addTreatmentAnomaly(selectedOpenTreatmentId, selectedCandidateId);
        setSelectedTreatmentId(selectedOpenTreatmentId);
        setSelectedTab("agenda");
        setSelectedTaskId("");
        await reloadSupport();
        await reloadOpenTreatmentOptions();
        setMessage("Anomalia asociada a tratamiento abierto. No se creo un tratamiento nuevo.");
        return;
      }

      const created = await createTreatment({
        primary_anomaly: selectedCandidateId,
        status: "pending",
        force_create_new: forceCreateNew,
      });
      setSelectedTreatmentId(created.id);
      setSelectedTab("agenda");
      setSelectedTaskId("");
      await reloadSupport();
      await reloadOpenTreatmentOptions();
      setMessage("Tratamiento creado correctamente. Revisa la seccion de anomalias asociadas para vincular otras anomalias compatibles.");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo completar el tratamiento.");
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

    await runMutation(async () => {
      await updateTreatment(selectedTreatment.id, {
        scheduled_for: scheduledFor ? toOffsetIso(scheduledFor) : null,
        treatment_location: treatmentLocation.trim(),
      });
    }, "Agenda del tratamiento actualizada.");
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

    await runMutation(async () => {
      await addTreatmentParticipant(selectedTreatment.id, {
        user: participantUserId,
        role: "convoked",
        note: participantNote.trim(),
      });
      setParticipantNote("");
    }, "Participante convocado al tratamiento.");
  };

  const handleAddAnomaly = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !linkAnomalyIds.length) {
      return;
    }
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
      return;
    }

    await runMutation(async () => {
      for (const anomalyId of linkAnomalyIds) {
        await addTreatmentAnomaly(selectedTreatment.id, anomalyId);
      }
      setLinkAnomalyIds([]);
    }, linkAnomalyIds.length === 1 ? "Anomalia vinculada al tratamiento." : "Anomalias vinculadas al tratamiento.");
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
      setFormError("Debes registrar al menos una tarea surgida del tratamiento antes de guardar el analisis.");
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

  const handleTaskDraftChange = (field: Exclude<keyof TaskDraft, "root_cause_ids" | "anomaly_ids">, value: string) => {
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
    if (treatmentLocked) {
      setFormError("El tratamiento esta cerrado por validacion eficaz y no admite modificaciones.");
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
    if (!taskDraft.anomaly_ids.length) {
      setFormError("Debes vincular al menos una anomalia a la tarea.");
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
      root_cause_ids: task.root_causes?.length
        ? task.root_causes.map((cause) => cause.id)
        : task.root_cause
          ? [task.root_cause]
          : [],
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
      description="Gestion de tratamientos por anomalia con Revisión de hallazgos: convocatoria, analisis de causa y tareas asociadas."
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

      <section className="panel treatment-create-panel">
        <div className="treatment-toolbar-actions">
          <select onChange={(event) => setSelectedCandidateId(event.target.value)} value={selectedCandidateId}>
                    <option value="">Seleccionar anomalia con Revisión de hallazgos...</option>
            {(supportData?.createCandidates ?? []).map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{`${candidate.code} - ${candidate.title}`}</option>
            ))}
          </select>
          {openTreatments.length ? (
            <select onChange={(event) => setSelectedOpenTreatmentId(event.target.value)} value={selectedOpenTreatmentId}>
              {openTreatments.map((treatment) => (
                <option key={treatment.id} value={treatment.id}>
                  {`${treatment.code} - ${treatment.primary_anomaly.code} | ${treatment.primary_anomaly.title}`}
                </option>
              ))}
            </select>
          ) : null}
          {openTreatments.length ? (
            <>
              <button className="button button-primary" disabled={busy || !selectedCandidateId || !selectedOpenTreatmentId} onClick={() => void handleCreateTreatment()} type="button">
                Asociar a tratamiento abierto
              </button>
              <button className="button button-secondary" disabled={busy || !selectedCandidateId} onClick={() => void handleCreateTreatment(true)} type="button">
                Crear nuevo tratamiento
              </button>
            </>
          ) : (
            <button className="button button-primary" disabled={busy || !selectedCandidateId} onClick={() => void handleCreateTreatment(true)} type="button">
              Crear tratamiento
            </button>
          )}
        </div>
        {selectedCandidateId && openTreatments.length ? (
          <p className="muted-copy">Hay tratamientos abiertos disponibles. Podes asociar la anomalia a uno existente o crear un tratamiento nuevo con esta anomalia.</p>
        ) : null}
      </section>

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
                          <button className="button button-primary" disabled={busy || treatmentLocked} type="submit">
                            Guardar agenda
                          </button>
                        </div>
                        <label className="field">
                          <span>Fecha y hora programada</span>
                          <input
                            name="scheduled_for"
                            disabled={treatmentLocked}
                            onChange={(event) => setScheduledFor(event.target.value)}
                            type="datetime-local"
                            value={scheduledFor}
                          />
                        </label>
                        <label className="field">
                          <span>Lugar de tratamiento</span>
                          <input
                            name="treatment_location"
                            disabled={treatmentLocked}
                            maxLength={200}
                            onChange={(event) => setTreatmentLocation(event.target.value)}
                            placeholder="Ej: Sala de reuniones, linea 1, sector pintura"
                            type="text"
                            value={treatmentLocation}
                          />
                        </label>
                      </form>

                      <form className="form-section" onSubmit={handleAddParticipant}>
                        <div className="section-head compact">
                          <h3>Usuarios convocados</h3>
                          <button className="button button-primary" disabled={busy || treatmentLocked || !participantUserId} type="submit">
                            Convocar
                          </button>
                        </div>
                        <div className="form-grid">
                          <label className="field">
                            <span>Area</span>
                            <select disabled={treatmentLocked} onChange={(event) => setParticipantAreaId(event.target.value)} value={participantAreaId}>
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
                            <select disabled={treatmentLocked} onChange={(event) => setParticipantUserId(event.target.value)} value={participantUserId}>
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
                            disabled={treatmentLocked}
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
                          <button className="button button-primary" disabled={busy || treatmentLocked || !linkAnomalyIds.length} type="submit">
                            Asociar anomalias
                          </button>
                        </div>
                        <TabbedFilters
                          actions={(
                            <button className="button button-secondary" disabled={loading || busy} onClick={handleApplyLinkCandidateFilters} type="button">
                              Buscar
                            </button>
                          )}
                          ariaLabel="Filtros de anomalias disponibles"
                          onClear={clearLinkCandidateFilters}
                          items={[
                            {
                              id: "anomaly",
                              label: "Anomalia",
                              active: Boolean(linkCandidateAnomalyDraft),
                              content: (
                                <input
                                  aria-label="Anomalia"
                                  onChange={(event) => setLinkCandidateAnomalyDraft(event.target.value)}
                                  onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); handleApplyLinkCandidateFilters(); } }}
                                  placeholder="ID, codigo o titulo"
                                  type="search"
                                  value={linkCandidateAnomalyDraft}
                                />
                              ),
                            },
                            {
                              id: "sector",
                              label: "Sector",
                              active: Boolean(linkCandidateSectorDraft),
                              content: <input aria-label="Sector" onChange={(event) => setLinkCandidateSectorDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); handleApplyLinkCandidateFilters(); } }} placeholder="Codigo o nombre de sector" type="search" value={linkCandidateSectorDraft} />,
                            },
                            {
                              id: "area",
                              label: "Area",
                              active: Boolean(linkCandidateAreaDraft),
                              content: <input aria-label="Area" onChange={(event) => setLinkCandidateAreaDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); handleApplyLinkCandidateFilters(); } }} placeholder="Codigo o nombre de area" type="search" value={linkCandidateAreaDraft} />,
                            },
                            {
                              id: "user",
                              label: "Usuario reporta",
                              active: Boolean(linkCandidateUserFilter),
                              content: (
                                <select aria-label="Usuario que reporta" onChange={(event) => { setLinkCandidateUserFilter(event.target.value); setLinkCandidatePage(1); }} value={linkCandidateUserFilter}>
                                  <option value="">Todos los usuarios</option>
                                  {(supportData?.users ?? []).map((user) => <option key={user.id} value={user.id}>{buildUsersLabel(user)}</option>)}
                                </select>
                              ),
                            },
                            {
                              id: "date-from",
                              label: "Fecha desde",
                              active: Boolean(linkCandidateDateFrom),
                              content: <input aria-label="Fecha desde" onChange={(event) => { setLinkCandidateDateFrom(event.target.value); setLinkCandidatePage(1); }} type="date" value={linkCandidateDateFrom} />,
                            },
                            {
                              id: "date-to",
                              label: "Fecha hasta",
                              active: Boolean(linkCandidateDateTo),
                              content: <input aria-label="Fecha hasta" onChange={(event) => { setLinkCandidateDateTo(event.target.value); setLinkCandidatePage(1); }} type="date" value={linkCandidateDateTo} />,
                            },
                          ]}
                        />
                        <label className="field">
                  <span>Anomalias con Revisión de hallazgos disponibles</span>
                          <select
                            disabled={treatmentLocked}
                            multiple
                            onChange={(event) => {
                              setLinkAnomalyIds(Array.from(event.target.selectedOptions, (option) => option.value));
                            }}
                            value={linkAnomalyIds}
                          >
                            {unlinkedCandidates.map((candidate) => (
                              <option key={candidate.id} value={candidate.id}>
                                {`${candidate.code} - ${candidate.title} | Area: ${candidate.area?.name || "-"} | Usuario: ${candidate.reporter?.full_name || candidate.reporter?.username || "-"} | Fecha: ${formatDate(candidate.detected_at)}`}
                              </option>
                            ))}
                          </select>
                          <small className="muted-copy">Mantene Ctrl presionado para seleccionar mas de una anomalia.</small>
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
                                  Area: {link.anomaly.area?.name || "-"} | Asignado a: {link.anomaly.imputed_area?.name || link.anomaly.anomaly_origin?.name || "-"}
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
                          <h3>Tareas surgidas del tratamiento</h3>
                          <button className="button button-primary" disabled={busy || treatmentLocked || !canCreateTask} type="submit">
                            Crear tarea
                          </button>
                        </div>

                        <div className="form-grid">
                          <label className="field">
                            <span>Tarea</span>
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
                              disabled={treatmentLocked || !participantOptions.length}
                              onChange={(event) => handleTaskDraftChange("responsible", event.target.value)}
                              required
                              value={taskDraft.responsible}
                            >
                              <option value="">Seleccionar responsable...</option>
                              {participantOptions.map((participant) => (
                                <option key={participant.id} value={participant.user?.id}>
                                  {participant.user?.full_name || participant.user?.username}
                                </option>
                              ))}
                            </select>
                            {!participantOptions.length ? <small className="muted-copy">Primero convoca usuarios al tratamiento.</small> : null}
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

                        <div className="treatment-checkbox-grid">
                          {anomalyOptions.map((link) => {
                            const checked = taskDraft.anomaly_ids.includes(link.anomaly.id);
                            return (
                              <label className="checkbox-inline" key={link.id}>
                                <input
                                  checked={checked}
                                  disabled={treatmentLocked}
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
                          {!selectedTreatment.tasks.length ? <p className="muted-copy">No hay tareas registradas para este tratamiento.</p> : null}
                        </div>

                        <p className="muted-copy">
                          La edicion de tareas y carga de evidencias ahora se realiza desde la pagina Acciones.
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
                        {!participantOptions.length ? (
                          <div className="panel warning compact-inline-panel">
                            <p>Primero deben convocarse responsables al tratamiento antes de asignar el responsable de evaluacion de eficacia.</p>
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
                                <option value="">Seleccionar convocado...</option>
                                {participantOptions.map((participant) => (
                                  <option key={participant.id} value={participant.user?.id}>
                                    {participant.user?.full_name || participant.user?.username}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                        )}
                        {hasTreatmentTasks ? (
                          <p className="muted-copy">{`Tareas registradas para este tratamiento: ${treatmentTaskCount}.`}</p>
                        ) : (
                          <p className="muted-copy">Registra al menos una tarea antes de guardar el analisis.</p>
                        )}
                      </form>
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





















