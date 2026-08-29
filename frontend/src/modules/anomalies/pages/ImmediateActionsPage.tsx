import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
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
  const [actionCompletedAt, setActionCompletedAt] = useState(nowAsDate());
  const [actionsTaken, setActionsTaken] = useState("");
  const [effectivenessDueAt, setEffectivenessDueAt] = useState(nowAsDate());
  const [objectiveEvidenceFiles, setObjectiveEvidenceFiles] = useState<File[]>([]);
  const [objectiveEvidenceInputKey, setObjectiveEvidenceInputKey] = useState(0);
  const [effectivenessVerifiedAt, setEffectivenessVerifiedAt] = useState(nowAsLocalDateTime());
  const [effectivenessResult, setEffectivenessResult] = useState<"" | "effective" | "not_effective">("");
  const [effectivenessComment, setEffectivenessComment] = useState("");

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
    if (!listData?.anomalies.results.length) {
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
    setObjectiveEvidenceFiles([]);
    setObjectiveEvidenceInputKey((current) => current + 1);
    setFormError(null);
    setMessage(null);
  }, [selectedAnomalyId, selectedAnomaly]);

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

    if (!responsibleId || !actionDate || !observation.trim()) {
      setFormError("Completa responsable, fecha limite de ejecucion y observacion.");
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
          ? "Observacion TRT registrada. Ya esta disponible para crear o asociar a un tratamiento."
          : "Observacion cargada. Ahora registra las acciones tomadas.",
      );
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo cargar la Observacion.");
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
      setFormError("Completa fecha de realizado, detalle de la accion y fecha de verificacion de eficacia.");
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

    if (!selectedAnomaly?.immediate_action?.actions_taken) {
      setFormError("Primero confirma una accion tomada.");
      return;
    }

    if (!effectivenessVerifiedAt || !effectivenessResult) {
      setFormError("Completa fecha de verificacion y selecciona si fue eficaz.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    const isEffective = effectivenessResult === "effective";

    try {
      await verifyObservationEffectiveness(selectedAnomalyId, {
        effectiveness_verified_at: toOffsetIso(effectivenessVerifiedAt),
        effectiveness_is_effective: isEffective,
        effectiveness_comment: effectivenessComment.trim() || undefined,
      });

      setMessage(isEffective ? "Observacion eficaz. Anomalia cerrada definitivamente." : "No eficaz reveer acciones tomadas");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo verificar la eficacia.");
    } finally {
      setSubmitting(false);
    }
  };

  const anomalies = listData?.anomalies.results ?? [];
  const totalCount = listData?.anomalies.count ?? 0;
  const hasLoadedAction = Boolean(selectedAnomaly?.immediate_action);
  const hasConfirmedActions = Boolean(selectedAnomaly?.immediate_action?.actions_taken);
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
                    <StatusBadge value={anomaly.current_status} compact />
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
                  <div className="section-head compact">
                    <div>
                      <p className="eyebrow">Detalle de anomalia</p>
                      <h2>{selectedAnomaly.code}</h2>
                    </div>
                    <div className="badge-stack align-end">
                      <StatusBadge value={selectedAnomaly.current_status} compact />
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

                  <form className="form-section" onSubmit={handleLoadAction}>
                    <div className="section-head compact">
                      <h3>Carga de Observacion</h3>
                    </div>

                    <div className="form-grid">
                      <label className="checkbox-inline field-span-2">
                        <input
                          checked={requiresTreatment}
                          disabled={submitting || selectedAnomaly.current_status === "closed" || hasConfirmedActions}
                          onChange={(event) => setRequiresTreatment(event.target.checked)}
                          type="checkbox"
                        />
                        <span>Clasificar como Observacion TRT (con tratamiento)</span>
                      </label>

                      {requiresTreatment ? (
                        <p className="muted-copy field-span-2">
                          La anomalia seguira siendo una Observacion, saldra de este circuito y quedara disponible para crear o asociar a un tratamiento.
                        </p>
                      ) : null}

                      {hasConfirmedActions ? (
                        <p className="muted-copy field-span-2">
                          La opcion TRT esta bloqueada porque las acciones tomadas ya fueron confirmadas.
                        </p>
                      ) : null}

                      <label className="field">
                        <span>Responsable</span>
                        <input readOnly value={buildResponsibleLabel(assignedResponsible)} />
                      </label>

                      <label className="field">
                        <span>Fecha limite de ejecucion</span>
                        <input onChange={(event) => setActionDate(event.target.value)} required type="date" value={actionDate} />
                      </label>

                      <label className="field field-span-2">
                        <span>{requiresTreatment ? "Motivo para derivar a tratamiento" : "Observacion"}</span>
                        <textarea onChange={(event) => setObservation(event.target.value)} required rows={3} value={observation} />
                      </label>
                    </div>

                    <div className="form-actions">
                      <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                        {submitting ? "Guardando..." : requiresTreatment ? "Confirmar Observacion TRT" : "Cargar observacion"}
                      </button>
                    </div>
                  </form>

                  {!hasLoadedAction && formError ? <div className="panel danger">{formError}</div> : null}
                  {!hasLoadedAction && message ? <div className="panel success">{message}</div> : null}

                  {requiresTreatment ? null : hasLoadedAction ? (
                    <form className="form-section" onSubmit={handleSaveActionsTaken}>
                      <div className="section-head compact">
                        <h3>Acciones tomadas</h3>
                      </div>

                      <div className="form-grid">
                        <label className="field">
                          <span>Fecha de realizado</span>
                          <input onChange={(event) => setActionCompletedAt(event.target.value)} required type="date" value={actionCompletedAt} />
                        </label>

                        <label className="field">
                          <span>Fecha de verificacion de eficacia</span>
                          <input onChange={(event) => setEffectivenessDueAt(event.target.value)} required type="date" value={effectivenessDueAt} />
                        </label>

                        <label className="field field-span-2">
                          <span>Detalle de la accion</span>
                          <textarea onChange={(event) => setActionsTaken(event.target.value)} required rows={3} value={actionsTaken} />
                        </label>

                        <label className="field field-span-2">
                          <span>Evidencias objetivas</span>
                          <input key={objectiveEvidenceInputKey} multiple onChange={handleObjectiveEvidenceChange} type="file" />
                        </label>
                      </div>

                      {objectiveEvidenceFiles.length ? (
                        <p className="muted-copy">
                          {objectiveEvidenceFiles.length} archivo(s) seleccionado(s)
                        </p>
                      ) : null}

                      {selectedAnomaly.attachments.length ? (
                        <div className="stack-list compact">
                          {selectedAnomaly.attachments.map((attachment) => (
                            <a className="text-link" href={attachment.file_url} key={attachment.id} rel="noopener noreferrer" target="_blank">
                              {attachment.original_name}
                            </a>
                          ))}
                        </div>
                      ) : null}

                      {!hasConfirmedActions && formError ? <div className="panel danger">{formError}</div> : null}
                      {!hasConfirmedActions && message ? <div className="panel success">{message}</div> : null}

                      <div className="form-actions">
                        <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                          {submitting ? "Guardando..." : "Confirmar acciones tomadas"}
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="panel muted">
                      <p>Primero confirma la carga de Observacion para habilitar acciones tomadas.</p>
                    </div>
                  )}

                  {requiresTreatment ? null : hasConfirmedActions ? (
                    <form className="form-section" onSubmit={handleVerifyEffectiveness}>
                      <div className="section-head compact">
                        <h3>Verificacion de eficacia</h3>
                      </div>

                      {notEffective ? <div className="panel warning">No eficaz reveer acciones tomadas</div> : null}

                      <div className="form-grid">
                      <label className="field">
                        <span>Fecha verificacion de eficacia</span>
                        <input
                          onChange={(event) => setEffectivenessVerifiedAt(event.target.value)}
                          required
                          type="datetime-local"
                          value={effectivenessVerifiedAt}
                        />
                      </label>

                      <label className="field">
                        <span>Eficaz</span>
                        <select onChange={(event) => setEffectivenessResult(event.target.value as "" | "effective" | "not_effective")} required value={effectivenessResult}>
                          <option value="">Seleccionar...</option>
                          <option value="effective">Si</option>
                          <option value="not_effective">No</option>
                        </select>
                      </label>

                        <label className="field field-span-2">
                          <span>Observacion</span>
                          <textarea onChange={(event) => setEffectivenessComment(event.target.value)} rows={3} value={effectivenessComment} />
                        </label>
                    </div>

                    {formError ? <div className="panel danger">{formError}</div> : null}
                    {message ? <div className="panel success">{message}</div> : null}

                    <div className="form-actions">
                      <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                        {submitting ? "Guardando..." : "Guardar verificacion"}
                      </button>
                    </div>
                  </form>
                  ) : (
                    <div className="panel muted">
                      <p>Primero confirma acciones tomadas para habilitar la verificacion de eficacia.</p>
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
