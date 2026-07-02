import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchUsers } from "../../../api/accounts";
import { fetchAnomalyDetail, fetchImmediateActionAnomalies, saveImmediateAction } from "../../../api/anomalies";
import type { UserDirectoryItem } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime, toOffsetIso } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

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

function buildUserLabel(user: UserDirectoryItem) {
  const displayName = user.full_name || user.username;
  return `${displayName} (${user.username})`;
}

export function ImmediateActionsPage() {
  usePageTitle("Accion inmediata");
  const { user } = useAuth();
  const adminUser = useMemo(() => isAdminUser(user), [user]);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [includeClosed, setIncludeClosed] = useState(false);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState("");

  const [responsibleId, setResponsibleId] = useState("");
  const [actionDate, setActionDate] = useState(nowAsDate());
  const [observation, setObservation] = useState("");
  const [actionsTaken, setActionsTaken] = useState("");
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
    if (!adminUser) {
      throw new Error("Solo usuarios administradores pueden gestionar accion inmediata.");
    }

    const [anomalies, users] = await Promise.all([
      fetchImmediateActionAnomalies(search, page, includeClosed),
      fetchUsers({ active: true, page: 1, pageSize: 200 }),
    ]);

    return {
      anomalies,
      users: users.results,
    };
  }, [adminUser, search, page, includeClosed]);

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
    setActionsTaken(existing?.actions_taken || selectedAnomaly.resolution_summary || "");
    setEffectivenessVerifiedAt(existing?.effectiveness_verified_at ? existing.effectiveness_verified_at.slice(0, 16) : nowAsLocalDateTime());
    setEffectivenessResult(
      existing?.effectiveness_is_effective === true
        ? "effective"
        : existing?.effectiveness_is_effective === false
          ? "not_effective"
          : "",
    );
    setEffectivenessComment(existing?.effectiveness_comment || selectedAnomaly.effectiveness_summary || "");
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
      setFormError("Selecciona una anomalia para registrar accion inmediata.");
      return;
    }

    if (!responsibleId || !actionDate || !observation.trim() || !actionsTaken.trim()) {
      setFormError("Completa responsable, fecha de carga, observacion y acciones tomadas.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    try {
      await saveImmediateAction(selectedAnomalyId, {
        responsible: responsibleId,
        action_date: actionDate,
        observation: observation.trim(),
        actions_taken: actionsTaken.trim(),
      });

      setMessage("Accion inmediata cargada. Ahora registra la verificacion de eficacia.");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo cargar la accion inmediata.");
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

    if (!responsibleId || !actionDate || !observation.trim() || !actionsTaken.trim()) {
      setFormError("Primero carga la accion inmediata.");
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
      await saveImmediateAction(selectedAnomalyId, {
        responsible: responsibleId,
        action_date: actionDate,
        observation: observation.trim(),
        actions_taken: actionsTaken.trim(),
        effectiveness_verified_at: toOffsetIso(effectivenessVerifiedAt),
        effectiveness_is_effective: isEffective,
        effectiveness_comment: effectivenessComment.trim() || undefined,
      });

      setMessage(isEffective ? "Accion inmediata eficaz. Anomalia cerrada definitivamente." : "No eficaz reveer acciones tomadas");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo verificar la eficacia.");
    } finally {
      setSubmitting(false);
    }
  };

  const users = listData?.users ?? [];
  const anomalies = listData?.anomalies.results ?? [];
  const totalCount = listData?.anomalies.count ?? 0;
  const hasLoadedAction = Boolean(selectedAnomaly?.immediate_action);
  const notEffective = selectedAnomaly?.immediate_action?.effectiveness_is_effective === false || effectivenessResult === "not_effective";

  return (
    <section className="page-shell">
      <PageHeader
        title="Accion inmediata"
      description="Gestion directa para anomalias con Revisión de hallazgos como accion inmediata. No generan tratamiento: se ejecuta, verifica eficacia y se cierra en este flujo."
      />

      <div className="toolbar-card">
        <input
          onChange={handleSearch}
          placeholder="Buscar por codigo, titulo, area o usuario"
          type="search"
          value={search}
        />
        <label className="checkbox-inline">
          <input checked={includeClosed} onChange={(event) => setIncludeClosed(event.target.checked)} type="checkbox" />
          <span>Incluir cerradas</span>
        </label>
      </div>

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay anomalias de accion inmediata"
        emptyDescription="Realiza Revisión de hallazgos de una anomalia con criterio de accion inmediata para gestionarla desde aqui."
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
                      <h3>Carga de accion inmediata</h3>
                    </div>

                    <div className="form-grid">
                      <label className="field">
                        <span>Responsable</span>
                        <select onChange={(event) => setResponsibleId(event.target.value)} required value={responsibleId}>
                          <option value="">Seleccionar responsable...</option>
                          {users.map((candidate) => (
                            <option key={candidate.id} value={candidate.id}>
                              {buildUserLabel(candidate)}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="field">
                        <span>Fecha de carga</span>
                        <input onChange={(event) => setActionDate(event.target.value)} required type="date" value={actionDate} />
                      </label>

                      <label className="field field-span-2">
                        <span>Observacion</span>
                        <textarea onChange={(event) => setObservation(event.target.value)} required rows={3} value={observation} />
                      </label>

                      <label className="field field-span-2">
                        <span>Acciones tomadas</span>
                        <textarea onChange={(event) => setActionsTaken(event.target.value)} required rows={3} value={actionsTaken} />
                      </label>
                    </div>

                    <div className="form-actions">
                      <button className="button button-primary" disabled={submitting || selectedAnomaly.current_status === "closed"} type="submit">
                        {submitting ? "Guardando..." : "Cargar accion"}
                      </button>
                    </div>
                  </form>

                  {!hasLoadedAction && formError ? <div className="panel danger">{formError}</div> : null}
                  {!hasLoadedAction && message ? <div className="panel success">{message}</div> : null}

                  {hasLoadedAction ? (
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
                      <p>Primero carga la accion inmediata para habilitar la verificacion de eficacia.</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="panel muted">
                  <h2>Selecciona una anomalia</h2>
                        <p>Elige una anomalia con Revisión de hallazgos como accion inmediata para cargar ejecucion, eficacia y cierre directo.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}
