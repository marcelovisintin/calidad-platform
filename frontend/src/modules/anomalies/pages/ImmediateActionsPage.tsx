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
  const [effectivenessVerifiedAt, setEffectivenessVerifiedAt] = useState(nowAsLocalDateTime());
  const [observation, setObservation] = useState("");
  const [actionsTaken, setActionsTaken] = useState("");
  const [effectivenessComment, setEffectivenessComment] = useState("");
  const [closureComment, setClosureComment] = useState("");

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
    setEffectivenessVerifiedAt(existing?.effectiveness_verified_at ? existing.effectiveness_verified_at.slice(0, 16) : nowAsLocalDateTime());
    setObservation(existing?.observation || selectedAnomaly.containment_summary || "");
    setActionsTaken(existing?.actions_taken || selectedAnomaly.resolution_summary || "");
    setEffectivenessComment(existing?.effectiveness_comment || selectedAnomaly.effectiveness_summary || "");
    setClosureComment(existing?.closure_comment || selectedAnomaly.closure_comment || "");
    setFormError(null);
    setMessage(null);
  }, [selectedAnomalyId, selectedAnomaly]);

  const handleSearch = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAnomalyId) {
      setFormError("Selecciona una anomalia para registrar accion inmediata.");
      return;
    }

    if (!responsibleId || !actionDate || !effectivenessVerifiedAt || !observation.trim() || !actionsTaken.trim()) {
      setFormError("Completa todos los campos obligatorios para cerrar la anomalia por accion inmediata.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setMessage(null);

    try {
      await saveImmediateAction(selectedAnomalyId, {
        responsible: responsibleId,
        action_date: actionDate,
        effectiveness_verified_at: toOffsetIso(effectivenessVerifiedAt),
        observation: observation.trim(),
        actions_taken: actionsTaken.trim(),
        effectiveness_comment: effectivenessComment.trim() || undefined,
        closure_comment: closureComment.trim() || undefined,
      });

      setMessage("Accion inmediata registrada y anomalia cerrada correctamente.");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo registrar la accion inmediata.");
    } finally {
      setSubmitting(false);
    }
  };

  const users = listData?.users ?? [];
  const anomalies = listData?.anomalies.results ?? [];
  const totalCount = listData?.anomalies.count ?? 0;

  return (
    <section className="page-shell">
      <PageHeader
        title="Accion inmediata"
        description="Gestion directa para anomalias clasificadas como accion inmediata. No generan tratamiento: se ejecuta, verifica eficacia y se cierra en este flujo."
      />

      <div className="toolbar-card">
        <input
          onChange={handleSearch}
          placeholder="Buscar por codigo, titulo, proceso o usuario"
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
        emptyDescription="Clasifica una anomalia con criterio de accion inmediata para gestionarla desde aqui."
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
                      {anomaly.area?.name || "Sin proceso"}
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

                  <form className="form-section" onSubmit={handleSubmit}>
                    <div className="section-head compact">
                      <h3>Registro de accion inmediata</h3>
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
                        <span>Fecha de accion</span>
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
                        <span>Comentario de eficacia</span>
                        <textarea onChange={(event) => setEffectivenessComment(event.target.value)} rows={2} value={effectivenessComment} />
                      </label>

                      <label className="field field-span-2">
                        <span>Comentario de cierre</span>
                        <textarea onChange={(event) => setClosureComment(event.target.value)} rows={2} value={closureComment} />
                      </label>
                    </div>

                    {formError ? <div className="panel danger">{formError}</div> : null}
                    {message ? <div className="panel success">{message}</div> : null}

                    <div className="form-actions">
                      <button className="button button-primary" disabled={submitting} type="submit">
                        {submitting ? "Guardando..." : "Guardar accion inmediata y cerrar"}
                      </button>
                    </div>
                  </form>
                </>
              ) : (
                <div className="panel muted">
                  <h2>Selecciona una anomalia</h2>
                  <p>Elige una anomalia clasificada como accion inmediata para cargar ejecucion, eficacia y cierre directo.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}
