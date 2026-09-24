import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  addObservationActionEvidence,
  completeObservationAction,
  createObservationAction,
  fetchAnomalyDetail,
  fetchImmediateActionAnomalies,
  saveObservationActionTaken,
  saveObservationLoad,
  uploadAnomalyAttachment,
  verifyObservationEffectiveness,
} from "../../../api/anomalies";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime, toOffsetIso } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { SearchableSelect } from "../../../components/SearchableSelect";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { isAdminUser } from "../../../app/access";
import { resolveAnomalyHelpWorkContext, usePublishHelpWorkContext } from "../../help/workContext";

function nowAsLocalDateTime() {
  const date = new Date();
  date.setSeconds(0, 0);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hh}:${mm}`;
}

function nowAsDate() {
  return nowAsLocalDateTime().slice(0, 10);
}

type ResponsibleSummary = {
  id: string;
  full_name?: string;
  username?: string;
  email?: string;
};

function buildResponsibleLabel(user?: ResponsibleSummary | null) {
  if (!user) {
    return "Sin responsable asignado";
  }
  const displayName = user.full_name || user.username || user.email || "Usuario";
  return user.username && user.username !== displayName ? `${displayName} (${user.username})` : displayName;
}

export function ImmediateActionsPage() {
  usePageTitle("Observacion");
  const { user } = useAuth();

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [includeClosed, setIncludeClosed] = useState(false);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState("");

  const [responsibleId, setResponsibleId] = useState("");
  const [actionDate, setActionDate] = useState(nowAsDate());
  const [observation, setObservation] = useState("");
  const [requiresTreatment, setRequiresTreatment] = useState(false);
  const [generalStepConfirmed, setGeneralStepConfirmed] = useState(false);
  const [actionDetail, setActionDetail] = useState("");
  const [estimatedCompletionDate, setEstimatedCompletionDate] = useState(nowAsDate());
  const [actionEffectivenessDueDate, setActionEffectivenessDueDate] = useState(nowAsDate());
  const [completionDates, setCompletionDates] = useState<Record<string, string>>({});
  const [actionEvidenceFiles, setActionEvidenceFiles] = useState<Record<string, File[]>>({});
  const [actionEvidenceInputKeys, setActionEvidenceInputKeys] = useState<Record<string, number>>({});
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});
  const [actionCompletedAt, setActionCompletedAt] = useState(nowAsDate());
  const [actionsTaken, setActionsTaken] = useState("");
  const [effectivenessDueAt, setEffectivenessDueAt] = useState(nowAsDate());
  const [objectiveEvidenceFiles, setObjectiveEvidenceFiles] = useState<File[]>([]);
  const [objectiveEvidenceInputKey, setObjectiveEvidenceInputKey] = useState(0);
  const [effectivenessVerifiedAt, setEffectivenessVerifiedAt] = useState(nowAsLocalDateTime());
  const [effectivenessResult, setEffectivenessResult] = useState<"" | "effective" | "not_effective">("");
  const [effectivenessComment, setEffectivenessComment] = useState("");
  const [effectivenessEvidenceFiles, setEffectivenessEvidenceFiles] = useState<File[]>([]);
  const [effectivenessEvidenceInputKey, setEffectivenessEvidenceInputKey] = useState(0);

  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    data: listData,
    loading,
    error,
    reload,
  } = useAsyncTask(async () => {
    if (!user) {
      throw new Error("No hay usuario autenticado.");
    }

    const anomalies = await fetchImmediateActionAnomalies(search, page, includeClosed);

    return {
      anomalies,
    };
  }, [user?.id, search, page, includeClosed]);

  useEffect(() => {
    if (!listData) {
      return;
    }

    if (!listData.anomalies.results.length) {
      setSelectedAnomalyId("");
      return;
    }

    if (selectedAnomalyId && listData.anomalies.results.some((item) => item.id === selectedAnomalyId)) {
      return;
    }

    setSelectedAnomalyId(listData.anomalies.results[0].id);
  }, [listData?.anomalies.results, selectedAnomalyId]);

  const {
    data: selectedAnomaly,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncTask(async () => {
    if (!selectedAnomalyId) {
      return null;
    }
    return fetchAnomalyDetail(selectedAnomalyId);
  }, [selectedAnomalyId]);

  useEffect(() => {
    if (!selectedAnomaly) {
      return;
    }

    const existing = selectedAnomaly.immediate_action;
    setResponsibleId(existing?.responsible?.id || selectedAnomaly.owner?.id || selectedAnomaly.current_responsible?.id || "");
    setActionDate(existing?.action_date || nowAsDate());
    setObservation(existing?.observation || selectedAnomaly.containment_summary || "");
    setRequiresTreatment(selectedAnomaly.observation_resolution_path === "TREATMENT_PENDING");
    setActionCompletedAt(existing?.action_completed_at || nowAsDate());
    setActionsTaken(existing?.actions_taken || selectedAnomaly.resolution_summary || "");
    setEffectivenessDueAt(existing?.effectiveness_due_at || nowAsDate());
    setEffectivenessVerifiedAt(existing?.effectiveness_verified_at ? existing.effectiveness_verified_at.slice(0, 16) : nowAsLocalDateTime());
    setEffectivenessResult(
      existing?.effectiveness_is_effective === true
        ? "effective"
        : existing?.effectiveness_is_effective === false
          ? "not_effective"
          : "",
    );
    setEffectivenessComment(existing?.effectiveness_comment || selectedAnomaly.effectiveness_summary || "");
    setEffectivenessEvidenceFiles([]);
    setEffectivenessEvidenceInputKey((current) => current + 1);
    setObjectiveEvidenceFiles([]);
    setObjectiveEvidenceInputKey((current) => current + 1);
    setFormError(null);
    setMessage(null);
    setActionDetail("");
    setEstimatedCompletionDate(nowAsDate());
    setActionEffectivenessDueDate(nowAsDate());
    setCompletionDates({});
  }, [selectedAnomalyId, selectedAnomaly]);

  useEffect(() => {
    setGeneralStepConfirmed(false);
    setActionEvidenceFiles({});
    setActionEvidenceInputKeys({});
    setActionErrors({});
  }, [selectedAnomalyId]);

  const handleSearch = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleLoadAction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAnomalyId) {
      setFormError("Selecciona una anomalia para registrar Observacion.");
      return;
    }

    if (selectedAnomaly?.immediate_action?.observation?.trim() && !requiresTreatment) {
      setGeneralStepConfirmed(true);
      setFormError(null);
      return;
    }

    if (!responsibleId || !actionDate || !observation.trim()) {
      setFormError("Completa responsable, fecha limite de ejecucion y causa asignada.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    try {
      await saveObservationLoad(selectedAnomalyId, {
        responsible: responsibleId,
        action_date: actionDate,
        observation: observation.trim(),
        requires_treatment: requiresTreatment,
      });

      setMessage(
        requiresTreatment
          ? "Observacion clasificada como TRT. El tratamiento fue creado correctamente."
          : "Observacion cargada. Ahora registra las acciones tomadas.",
      );
      await Promise.all([reload(), reloadDetail()]);
      setGeneralStepConfirmed(!requiresTreatment);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo cargar la Observacion.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateObservationAction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAnomalyId || !actionDetail.trim() || !estimatedCompletionDate || !actionEffectivenessDueDate) {
      setFormError("Completa el detalle y las dos fechas estimadas de la accion.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);
    try {
      const createdAction = await createObservationAction(selectedAnomalyId, {
        detail: actionDetail.trim(),
        estimated_completion_date: estimatedCompletionDate,
        effectiveness_due_date: actionEffectivenessDueDate,
      });
      setActionDetail("");
      for (const file of objectiveEvidenceFiles) {
        await addObservationActionEvidence(selectedAnomalyId, createdAction.id, { file });
      }
      setObjectiveEvidenceFiles([]);
      setObjectiveEvidenceInputKey((current) => current + 1);
      await Promise.all([reload(), reloadDetail()]);
      setGeneralStepConfirmed(true);
      setMessage("La accion fue guardada correctamente y no podra editarse.");
    } catch (err) {
      await Promise.all([reload(), reloadDetail()]);
      setGeneralStepConfirmed(true);
      setFormError(err instanceof Error ? err.message : "No se pudo guardar la accion.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCompleteObservationAction = async (actionId: string) => {
    if (!selectedAnomalyId) {
      return;
    }
    const completedAt = completionDates[actionId] || nowAsDate();
    if (!window.confirm("¿Está seguro de marcar esta acción como finalizada?")) {
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);
    setActionErrors((current) => ({ ...current, [actionId]: "" }));
    try {
      const files = actionEvidenceFiles[actionId] ?? [];
      const hasSavedEvidence = selectedAnomaly?.attachments.some((attachment) => attachment.observation_action === actionId);
      if (!hasSavedEvidence && files.length === 0) {
        setActionErrors((current) => ({ ...current, [actionId]: "Selecciona una evidencia objetiva para finalizar esta accion." }));
        return;
      }
      for (const file of files) {
        await addObservationActionEvidence(selectedAnomalyId, actionId, { file });
      }
      setActionEvidenceFiles((current) => ({ ...current, [actionId]: [] }));
      setActionEvidenceInputKeys((current) => ({ ...current, [actionId]: (current[actionId] ?? 0) + 1 }));
      await completeObservationAction(selectedAnomalyId, actionId, completedAt);
      await Promise.all([reload(), reloadDetail()]);
      setGeneralStepConfirmed(true);
      setMessage("Accion finalizada correctamente.");
    } catch (err) {
      await reloadDetail();
      setActionErrors((current) => ({ ...current, [actionId]: err instanceof Error ? err.message : "No se pudo finalizar la accion." }));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddActionEvidence = async (actionId: string) => {
    if (!selectedAnomalyId || !actionEvidenceFiles[actionId]?.length) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    setMessage(null);
    setActionErrors((current) => ({ ...current, [actionId]: "" }));
    try {
      for (const file of actionEvidenceFiles[actionId]) {
        await addObservationActionEvidence(selectedAnomalyId, actionId, { file });
      }
      setActionEvidenceFiles((current) => ({ ...current, [actionId]: [] }));
      setActionEvidenceInputKeys((current) => ({ ...current, [actionId]: (current[actionId] ?? 0) + 1 }));
      await reloadDetail();
      setMessage("Evidencia vinculada a la accion.");
    } catch (err) {
      await reloadDetail();
      setActionErrors((current) => ({ ...current, [actionId]: err instanceof Error ? err.message : "No se pudo cargar la evidencia de la accion." }));
    } finally {
      setSubmitting(false);
    }
  };

  const handleObjectiveEvidenceChange = (event: ChangeEvent<HTMLInputElement>) => {
    setObjectiveEvidenceFiles(Array.from(event.target.files ?? []));
  };

  const handleSaveActionsTaken = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAnomalyId) {
      setFormError("Selecciona una anomalia para registrar acciones tomadas.");
      return;
    }

    if (!selectedAnomaly?.immediate_action) {
      setFormError("Primero confirma la carga de Observacion.");
      return;
    }

    if (!actionCompletedAt || !actionsTaken.trim() || !effectivenessDueAt) {
      setFormError("Completa fecha de realizado, detalle de la accion y fecha de validacion.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    try {
      await saveObservationActionTaken(selectedAnomalyId, {
        action_completed_at: actionCompletedAt,
        actions_taken: actionsTaken.trim(),
        effectiveness_due_at: effectivenessDueAt,
      });

      for (const file of objectiveEvidenceFiles) {
        await uploadAnomalyAttachment(selectedAnomalyId, {
          file,
          originalName: file.name,
        });
      }

      setObjectiveEvidenceFiles([]);
      setObjectiveEvidenceInputKey((current) => current + 1);
      setMessage("Acciones tomadas confirmadas.");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudieron cargar las acciones tomadas.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyEffectiveness = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAnomalyId) {
      setFormError("Selecciona una anomalia para verificar eficacia.");
      return;
    }

    if (!hasConfirmedActions) {
      setFormError("Debe cargar al menos una accion antes de verificar eficacia.");
      return;
    }

    if (!canVerifyEffectiveness) {
      setFormError(hasPendingObservationActions ? "Debe completar todas las acciones antes de verificar eficacia." : `La verificacion de eficacia se habilitara el ${effectivenessDueDate}.`);
      return;
    }

    if (!effectivenessVerifiedAt || !effectivenessResult || !effectivenessComment.trim()) {
      setFormError("Completa la fecha de realizacion de la validacion, el resultado y el fundamento de eficacia.");
      return;
    }
    if (!effectivenessEvidenceFiles.length) {
      setFormError("Adjunta al menos una evidencia objetiva de la verificacion de eficacia.");
      return;
    }
    if (effectivenessVerifiedAt.slice(0, 10) < effectivenessDueDate) {
      setFormError("La fecha de realizacion no puede ser anterior a la fecha de validacion.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    const isEffective = effectivenessResult === "effective";

    try {
      const updatedAnomaly = await verifyObservationEffectiveness(selectedAnomalyId, {
        effectiveness_verified_at: toOffsetIso(effectivenessVerifiedAt),
        effectiveness_is_effective: isEffective,
        effectiveness_comment: effectivenessComment.trim(),
        evidences: effectivenessEvidenceFiles,
      });

      await Promise.all([reload(), reloadDetail()]);
      setMessage(
        isEffective
          ? updatedAnomaly.current_status === "closed"
            ? "La observacion fue cerrada correctamente."
            : "La observacion no puede cerrarse porque existen acciones pendientes."
          : "La verificacion resulto no eficaz. Deben cargarse nuevas acciones.",
      );
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo verificar la eficacia.");
    } finally {
      setSubmitting(false);
    }
  };

  const anomalies = listData?.anomalies.results ?? [];
  const totalCount = listData?.anomalies.count ?? 0;
  const hasLoadedAction = Boolean(selectedAnomaly?.immediate_action?.observation?.trim());
  const hasAssignedObservation = Boolean(selectedAnomaly?.immediate_action);
  const observationActions = selectedAnomaly?.observation_actions ?? [];
  const hasObservationActions = observationActions.length > 0;
  const hasConfirmedActions = hasObservationActions || Boolean(selectedAnomaly?.immediate_action?.actions_taken);
  const effectivenessReferenceAction = observationActions.reduce<(typeof observationActions)[number] | null>(
    (current, action) => {
      if (!current || action.effectiveness_due_date > current.effectiveness_due_date) {
        return action;
      }
      if (action.effectiveness_due_date === current.effectiveness_due_date && action.sequence > current.sequence) {
        return action;
      }
      return current;
    },
    null,
  );
  const hasPendingObservationActions = observationActions.some((action) => action.status !== "completed");
  const effectivenessDueDate = effectivenessReferenceAction?.effectiveness_due_date || selectedAnomaly?.immediate_action?.effectiveness_due_at || "";
  const canVerifyEffectiveness = Boolean(!hasPendingObservationActions && effectivenessDueDate && nowAsDate() >= effectivenessDueDate);
  const notEffective = selectedAnomaly?.immediate_action?.effectiveness_is_effective === false || effectivenessResult === "not_effective";
  const assignedResponsible = selectedAnomaly?.immediate_action?.responsible || selectedAnomaly?.owner || selectedAnomaly?.current_responsible || null;
  usePublishHelpWorkContext(selectedAnomaly ? resolveAnomalyHelpWorkContext(selectedAnomaly, isAdminUser(user)) : null);

  return (
    <section className="page-shell">
      <PageHeader
        title="Observacion"
      description="Gestion directa para anomalias con Revisión de hallazgos como Observacion. Si el caso lo requiere, puede marcarse como Observacion TRT para derivarlo a tratamiento."
      />

      <TabbedFilters
        ariaLabel="Filtros de observaciones"
        onClear={() => { setSearch(""); setIncludeClosed(false); setPage(1); }}
        items={[
          {
            id: "search",
            label: "Buscar",
            active: Boolean(search),
            content: <input aria-label="Buscar observaciones" onChange={handleSearch} placeholder="Codigo, titulo, area o usuario" type="search" value={search} />,
          },
          {
            id: "closed",
            label: "Cerradas",
            active: includeClosed,
            content: (
              <div className="tabbed-filter-toggle">
                <label className="checkbox-inline">
                  <input checked={includeClosed} onChange={(event) => { setIncludeClosed(event.target.checked); setPage(1); }} type="checkbox" />
                  <span>Incluir observaciones cerradas</span>
                </label>
              </div>
            ),
          },
        ]}
      />

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay anomalias de Observacion"
        emptyDescription="Realiza Revisión de hallazgos de una anomalia con criterio de Observacion para gestionarla desde aqui."
      >
        <div className="treatment-layout">
          <article className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Listado</p>
                <h2>{`Anomalias (${totalCount})`}</h2>
              </div>
            </div>
            <div className="stack-list compact" style={{ maxHeight: "70vh", overflowY: "auto" }}>
              {anomalies.map((anomaly) => (
                <button
                  className={`list-card compact treatment-card${selectedAnomalyId === anomaly.id ? " active" : ""}`}
                  key={anomaly.id}
                  onClick={() => setSelectedAnomalyId(anomaly.id)}
                  type="button"
                >
                  <div>
                    <strong>{anomaly.code}</strong>
                    <p>{anomaly.title}</p>
                    <small>
                      Reportada por: {anomaly.reporter?.full_name || anomaly.reporter?.username || "Sin dato"}
                      {" | "}
                      Area: {anomaly.area?.name || "Sin area"}
                    </small>
                  </div>
                  <div className="badge-stack align-end">
                    <StatusBadge value={anomaly.current_status} overdue={anomaly.is_overdue} compact />
                    <StatusBadge value={anomaly.current_stage} compact />
                  </div>
                </button>
              ))}
            </div>
            <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading || submitting} />
          </article>

          <article className="panel">
            <DataState loading={detailLoading} error={detailError} onRetry={reloadDetail}>
              {selectedAnomaly ? (
                <>
                  <div className="section-head compact" data-tour="observation-summary">
                    <div>
                      <p className="eyebrow">Detalle de anomalia</p>
                      <h2>{selectedAnomaly.code}</h2>
                    </div>
                    <div className="badge-stack align-end">
                      <StatusBadge value={selectedAnomaly.current_status} overdue={selectedAnomaly.is_overdue} compact />
                      <StatusBadge value={selectedAnomaly.current_stage} compact />
                    </div>
                  </div>

                  <p>{selectedAnomaly.title}</p>
                  <p className="muted-copy">
                    {selectedAnomaly.description}
                    <br />
                    Reportada por: {selectedAnomaly.reporter?.full_name || selectedAnomaly.reporter?.username || "Sin dato"}
                    {" | "}
                    Detectada: {formatDateTime(selectedAnomaly.detected_at)}
                  </p>

                  <Link className="text-link" to={`/anomalies/${selectedAnomaly.id}`}>
                    Ver detalle completo de la anomalia
                  </Link>

                  <form className="form-section" data-tour="observation-general" onSubmit={handleLoadAction}>
                    <div className="section-head compact">
                      <div>
                        <p className="eyebrow">Primera tarjeta</p>
                        <h3>Datos generales de la Observacion</h3>
                      </div>
                    </div>

                    <div className="form-grid">
                      <label className="field">
                        <span>Responsable</span>
                        <input readOnly value={buildResponsibleLabel(assignedResponsible)} />
                      </label>

                      <label className="field">
                        <span>Fecha limite de ejecucion</span>
                        <input disabled={hasAssignedObservation} onChange={(event) => setActionDate(event.target.value)} required type="date" value={actionDate} />
                      </label>

                      <label className="field field-span-2" data-tour="observation-cause">
                        <span>Causa asignada</span>
                        <textarea disabled={hasLoadedAction} onChange={(event) => setObservation(event.target.value)} required rows={3} value={observation} />
                      </label>

                      <label className="checkbox-inline field-span-2" data-tour="observation-treatment-path">
                        <input
                          checked={requiresTreatment}
                          disabled={hasConfirmedActions || selectedAnomaly.current_status === "closed"}
                          onChange={(event) => setRequiresTreatment(event.target.checked)}
                          type="checkbox"
                        />
                        <span>Clasificar como Observacion TRT (con tratamiento)</span>
                      </label>
                    </div>

                    <div className="form-actions" data-tour="observation-general-confirm">
                      <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                        {submitting ? "Guardando..." : "Siguiente"}
                      </button>
                    </div>
                  </form>

                  {!hasLoadedAction && formError ? <div className="panel danger">{formError}</div> : null}
                  {!hasLoadedAction && message ? <div className="panel success">{message}</div> : null}

                  {(generalStepConfirmed || selectedAnomaly.observation_resolution_path === "OBSERVATION") && hasLoadedAction ? (
                    <form className="form-section" data-tour="observation-actions" onSubmit={handleCreateObservationAction}>
                      <div className="section-head compact">
                        <div>
                          <p className="eyebrow">Segunda tarjeta</p>
                          <h3>Acciones tomadas</h3>
                        </div>
                      </div>

                      <div className="form-grid">
                        <label className="field">
                          <span>Fecha estimada de realizacion</span>
                          <input onChange={(event) => setEstimatedCompletionDate(event.target.value)} required type="date" value={estimatedCompletionDate} />
                        </label>

                        <label className="field">
                          <span>Fecha de validacion</span>
                          <input onChange={(event) => setActionEffectivenessDueDate(event.target.value)} required type="date" value={actionEffectivenessDueDate} />
                        </label>

                        <label className="field field-span-2">
                          <span>Detalle de la accion</span>
                          <textarea onChange={(event) => setActionDetail(event.target.value)} required rows={3} value={actionDetail} />
                        </label>

                        <label className="field field-span-2" data-tour="observation-evidence">
                          <span>Evidencias objetivas</span>
                          <input key={objectiveEvidenceInputKey} multiple onChange={handleObjectiveEvidenceChange} type="file" />
                        </label>
                      </div>

                      {objectiveEvidenceFiles.length ? (
                        <p className="muted-copy">
                          {objectiveEvidenceFiles.length} archivo(s) seleccionado(s)
                        </p>
                      ) : null}

                      <div className="form-actions">
                        <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                          {submitting ? "Guardando..." : "Guardar"}
                        </button>
                      </div>

                      <div className="stack-list compact" data-tour="observation-action-list">
                        {observationActions.map((action) => (
                          <article className="list-card compact" key={action.id}>
                            <div>
                              <strong>{`Accion ${action.sequence}`}</strong>
                              <p>{action.detail}</p>
                              <small>
                                Realizacion estimada: {action.estimated_completion_date} | Fecha de validacion: {action.effectiveness_due_date}
                              </small>
                              {action.completed_at ? <small>Finalizada: {action.completed_at}</small> : null}
                              {selectedAnomaly.attachments.filter((attachment) => attachment.observation_action === action.id).map((attachment) => (
                                <a className="text-link" href={attachment.file_url} key={attachment.id} rel="noopener noreferrer" target="_blank">
                                  {attachment.original_name}
                                </a>
                              ))}
                              {actionErrors[action.id] ? <div className="panel danger" role="alert">{actionErrors[action.id]}</div> : null}
                              {action.status === "pending" ? (
                                <div className="form-actions">
                                  <input
                                    aria-label={`Evidencia objetiva de accion ${action.sequence}`}
                                    accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.rtf,.odt,.ods,.zip,.jpg,.jpeg,.png,.webp,.gif,.bmp,.tif,.tiff,.heic,.heif"
                                    key={`${action.id}-${actionEvidenceInputKeys[action.id] ?? 0}`}
                                    multiple
                                    onChange={(event) => setActionEvidenceFiles((current) => ({ ...current, [action.id]: Array.from(event.target.files ?? []) }))}
                                    type="file"
                                  />
                                  {actionEvidenceFiles[action.id]?.length ? <small>{actionEvidenceFiles[action.id].length} archivo(s) seleccionado(s)</small> : null}
                                  <button
                                    className="button button-secondary"
                                    disabled={submitting || !actionEvidenceFiles[action.id]?.length}
                                    onClick={() => void handleAddActionEvidence(action.id)}
                                    type="button"
                                  >
                                    Adjuntar evidencia
                                  </button>
                                </div>
                              ) : null}
                            </div>
                            <div className="badge-stack align-end">
                              <StatusBadge compact value={action.status} overdue={action.is_overdue} />
                              {action.status === "pending" ? (
                                <>
                                  <input
                                    aria-label={`Fecha real de finalizacion de accion ${action.sequence}`}
                                    onChange={(event) => setCompletionDates((current) => ({ ...current, [action.id]: event.target.value }))}
                                    type="date"
                                    value={completionDates[action.id] || nowAsDate()}
                                  />
                                  <button
                                    className="button button-secondary"
                                    disabled={submitting || selectedAnomaly.current_status === "closed"}
                                    onClick={() => void handleCompleteObservationAction(action.id)}
                                    type="button"
                                  >
                                    Marcar finalizada
                                  </button>
                                </>
                              ) : null}
                            </div>
                          </article>
                        ))}
                        {!observationActions.length ? <p className="muted-copy">Todavia no hay acciones cargadas.</p> : null}
                      </div>
                    </form>
                  ) : (
                    <div className="panel muted" data-tour="observation-actions">
                      <p>Primero confirma la carga de Observacion para habilitar acciones tomadas.</p>
                    </div>
                  )}

                  {hasConfirmedActions ? (
                    <form className="form-section" data-tour="observation-effectiveness" onSubmit={handleVerifyEffectiveness}>
                      <div className="section-head compact">
                        <h3>Verificacion de eficacia</h3>
                        <StatusBadge
                          compact
                          value={selectedAnomaly.immediate_action?.effectiveness_verified_at ? "completed" : ["closed", "cancelled"].includes(selectedAnomaly.current_status) ? selectedAnomaly.current_status : "pending"}
                          dueDate={effectivenessReferenceAction?.effectiveness_due_date || selectedAnomaly.immediate_action?.effectiveness_due_at}
                        />
                      </div>

                      {hasPendingObservationActions ? (
                        <div className="panel warning">
                          Debe completar todas las acciones antes de registrar la verificación de eficacia.
                        </div>
                      ) : null}
                      {notEffective ? <div className="panel warning">La ultima verificacion no fue eficaz; puede cargar nuevas acciones.</div> : null}
                      {!canVerifyEffectiveness ? (
                        <div className="panel warning">
                          La verificacion permanecera bloqueada hasta la fecha de validacion: {effectivenessDueDate || "sin fecha definida"}.
                        </div>
                      ) : null}

                      <div className="form-grid">
                        <label className="field">
                          <span>Fecha de validacion</span>
                          <input
                            disabled
                            type="date"
                            value={effectivenessReferenceAction?.effectiveness_due_date || selectedAnomaly.immediate_action?.effectiveness_due_at || ""}
                          />
                        </label>

                        <div className="field">
                          <span>Acción/s tomadas</span>
                          <div className="readonly-block">
                            {observationActions.length
                              ? observationActions.map((action) => (
                                  <p key={action.id}>Acción {action.sequence}: {action.detail}</p>
                                ))
                              : selectedAnomaly.immediate_action?.actions_taken || "Sin acciones tomadas"}
                          </div>
                        </div>

                        <label className="field">
                          <span>Fecha de realizacion de la validacion</span>
                          <input
                            disabled={!canVerifyEffectiveness}
                            onChange={(event) => setEffectivenessVerifiedAt(event.target.value)}
                            required
                            type="datetime-local"
                            value={effectivenessVerifiedAt}
                          />
                        </label>

                        <SearchableSelect
                          className="field"
                          disabled={!canVerifyEffectiveness}
                          label="Resultado"
                          onChange={(value) => setEffectivenessResult(value as "" | "effective" | "not_effective")}
                          options={[{ value: "effective", label: "Eficaz" }, { value: "not_effective", label: "No eficaz" }]}
                          placeholder="Seleccionar..."
                          required
                          value={effectivenessResult}
                        />

                        <label className="field field-span-2" data-tour="observation-effectiveness-reason">
                          <span>Fundamento de eficacia</span>
                          <textarea disabled={!canVerifyEffectiveness} onChange={(event) => setEffectivenessComment(event.target.value)} required rows={3} value={effectivenessComment} />
                        </label>
                        <label className="field field-span-2">
                          <span>Evidencia objetiva de la verificacion (obligatoria)</span>
                          <input
                            accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.rtf,.odt,.ods,.zip,.jpg,.jpeg,.png,.webp,.gif,.bmp,.tif,.tiff,.heic,.heif"
                            disabled={!canVerifyEffectiveness}
                            key={effectivenessEvidenceInputKey}
                            multiple
                            onChange={(event) => setEffectivenessEvidenceFiles(Array.from(event.target.files ?? []))}
                            required
                            type="file"
                          />
                        </label>
                      </div>

                    {formError ? <div className="panel danger">{formError}</div> : null}
                    {message ? <div className="panel success">{message}</div> : null}

                    <div className="form-actions" data-tour="observation-effectiveness-confirm">
                      <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed" || !canVerifyEffectiveness || !effectivenessComment.trim() || !effectivenessEvidenceFiles.length} type="submit">
                        {submitting ? "Guardando..." : "Guardar verificacion"}
                      </button>
                    </div>
                  </form>
                  ) : (
                    <div className="panel muted" data-tour="observation-effectiveness">
                      <p>Primero carga al menos una accion para habilitar la verificacion de eficacia.</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="panel muted">
                  <h2>Selecciona una anomalia</h2>
                        <p>Elige una anomalia con Revisión de hallazgos como Observacion para cargar ejecucion, eficacia y cierre directo.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}
