import { ChangeEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { fetchUsers } from "../../../api/accounts";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import { fetchTreatmentTracking, fetchTreatmentTrackingDetail } from "../../../api/treatments";
import type { TreatmentDetail, TreatmentSummary } from "../../../api/types";
import { formatDate, formatDateTime, humanizeToken } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

function treatmentDisplayStatus(treatment?: TreatmentSummary | TreatmentDetail | null) {
  if (!treatment) {
    return "";
  }
  if (treatment.effectiveness_validation_result === "effective") {
    return "validated_effective";
  }
  if (treatment.effectiveness_validation_result === "not_effective") {
    return "not_effective";
  }
  return treatment.status;
}

function relevantDate(treatment: TreatmentSummary) {
  return treatment.effectiveness_validated_at || treatment.scheduled_for || treatment.created_at;
}

function userLabel(user: { full_name?: string; username: string }) {
  return user.full_name?.trim() || user.username;
}

function evidenceUrl(fileUrl: string) {
  if (!fileUrl) {
    return "#";
  }
  if (fileUrl.startsWith("/")) {
    return fileUrl;
  }
  if (fileUrl.startsWith("http://") || fileUrl.startsWith("https://")) {
    try {
      const parsed = new URL(fileUrl);
      const host = parsed.hostname.toLowerCase();
      if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
      }
    } catch {
      return fileUrl;
    }
  }
  return fileUrl.startsWith("/") ? fileUrl : `/${fileUrl}`;
}

const TREATMENT_AUDIT_ACTION_LABELS: Record<string, string> = {
  "treatment.created": "Tratamiento creado",
  "treatment.updated": "Tratamiento actualizado",
  "treatment.effectiveness_validated": "Validacion de eficacia registrada",
  "treatment.anomaly_added": "Anomalia asociada",
  "treatment.participant_added": "Convocado agregado",
  "treatment.participant_updated": "Convocado actualizado",
  "treatment.root_cause_added": "Causa raiz registrada",
  "treatment.task_added": "Tarea generada",
  "treatment.task_updated": "Tarea actualizada",
  "treatment.evidence_added": "Evidencia del tratamiento agregada",
  "treatment.task_evidence_added": "Evidencia de tarea agregada",
  "treatment.learned_lesson.saved": "Leccion aprendida guardada",
};

function treatmentAuditActionLabel(action: string) {
  return TREATMENT_AUDIT_ACTION_LABELS[action] || humanizeToken(action.replace(/^treatment\./, ""));
}

function yesNo(value: boolean | null) {
  if (value === true) {
    return "Si";
  }
  if (value === false) {
    return "No";
  }
  return "-";
}

export function TreatmentTrackingPage() {
  usePageTitle("Seguimiento de tratamientos");
  const [page, setPage] = useState(1);
  const [codeFilter, setCodeFilter] = useState("");
  const [userFilter, setUserFilter] = useState("");
  const [processFilter, setProcessFilter] = useState("");
  const [selectedTreatmentId, setSelectedTreatmentId] = useState("");
  const deferredCode = useDeferredValue(codeFilter);

  const { data: usersData } = useAsyncTask(() => fetchUsers({ active: true, pageSize: 100 }), []);
  const { data: catalogData } = useAsyncTask(fetchCatalogBootstrap, []);

  const { data, loading, error, reload } = useAsyncTask(
    () =>
      fetchTreatmentTracking({
        page,
        code: deferredCode,
        user: userFilter,
        process: processFilter,
      }),
    [page, deferredCode, userFilter, processFilter],
  );

  const treatments = data?.results ?? [];
  const totalCount = data?.count ?? 0;

  useEffect(() => {
    if (!treatments.length) {
      setSelectedTreatmentId("");
      return;
    }
    if (!selectedTreatmentId || !treatments.some((item) => item.id === selectedTreatmentId)) {
      setSelectedTreatmentId(treatments[0].id);
    }
  }, [selectedTreatmentId, treatments]);

  const {
    data: detail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncTask(() => {
    if (!selectedTreatmentId) {
      return Promise.resolve(null);
    }
    return fetchTreatmentTrackingDetail(selectedTreatmentId);
  }, [selectedTreatmentId]);

  const selectedProcess = detail?.primary_anomaly.area?.name || detail?.primary_anomaly.imputed_area?.name || detail?.primary_anomaly.anomaly_origin?.name || "-";
  const relatedUsers = useMemo(() => {
    if (!detail) {
      return [];
    }
    const names = new Set<string>();
    if (detail.primary_anomaly.reporter) {
      names.add(detail.primary_anomaly.reporter.full_name || detail.primary_anomaly.reporter.username);
    }
    detail.participants.forEach((participant) => {
      if (participant.user) {
        names.add(participant.user.full_name || participant.user.username);
      }
    });
    detail.tasks.forEach((task) => {
      if (task.responsible) {
        names.add(task.responsible.full_name || task.responsible.username);
      }
    });
    if (detail.effectiveness_responsible) {
      names.add(detail.effectiveness_responsible.full_name || detail.effectiveness_responsible.username);
    }
    return Array.from(names);
  }, [detail]);

  const handleFilterChange = (setter: (value: string) => void) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setter(event.target.value);
    setPage(1);
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Seguimiento de tratamientos"
        description="Consulta y auditoria solo lectura de tratamientos, procedimientos, tareas y validaciones."
      />

      <section className="toolbar-card">
        <div className="form-grid">
          <label className="field">
            <span>Codigo de procedimiento</span>
            <input
              onChange={handleFilterChange(setCodeFilter)}
              placeholder="Ej. TRT-2026-0001"
              type="search"
              value={codeFilter}
            />
          </label>
          <label className="field">
            <span>Usuario</span>
            <select onChange={handleFilterChange(setUserFilter)} value={userFilter}>
              <option value="">Todos</option>
              {(usersData?.results ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {userLabel(user)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Area</span>
            <select onChange={handleFilterChange(setProcessFilter)} value={processFilter}>
              <option value="">Todos</option>
              {(catalogData?.areas ?? []).map((area) => (
                <option key={area.id} value={area.id}>
                  {area.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay tratamientos para mostrar"
        emptyDescription="Ajusta los filtros para consultar la trazabilidad disponible."
      >
        <div className="treatment-layout">
          <article className="panel treatment-list-panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Procedimientos</p>
                <h2>Resultados ({totalCount})</h2>
              </div>
            </div>
            <div className="stack-list treatment-list">
              {treatments.map((treatment) => (
                <button
                  className={`treatment-list-item${selectedTreatmentId === treatment.id ? " active" : ""}`}
                  key={treatment.id}
                  onClick={() => setSelectedTreatmentId(treatment.id)}
                  type="button"
                >
                  <div className="section-head compact">
                    <strong>{treatment.code}</strong>
                    <StatusBadge compact value={treatmentDisplayStatus(treatment)} />
                  </div>
                  <p className="treatment-title">{treatment.primary_anomaly.title}</p>
                  <small>
                    Usuario: {treatment.effectiveness_responsible?.full_name || treatment.primary_anomaly.reporter?.full_name || treatment.primary_anomaly.reporter?.username || "-"}
                  </small>
                  <small>
                    Area: {treatment.primary_anomaly.area?.name || "-"} | Fecha: {formatDate(relevantDate(treatment))}
                  </small>
                </button>
              ))}
            </div>
            <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
          </article>

          <article className="panel treatment-detail-panel">
            <DataState loading={detailLoading} error={detailError} onRetry={reloadDetail}>
              {detail ? (
                <>
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Detalle solo lectura</p>
                      <h2>{detail.code}</h2>
                      <p className="page-description">
                        Anomalia asociada: <strong>{detail.primary_anomaly.code}</strong> | {detail.primary_anomaly.title}
                      </p>
                    </div>
                    <StatusBadge value={treatmentDisplayStatus(detail)} />
                  </div>

                  <div className="panel info compact-inline-panel">
                    <p>Vista de auditoria. Esta pantalla es solo lectura y no modifica tratamientos, tareas ni historial.</p>
                  </div>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Datos generales</h3></div>
                    <dl className="key-grid compact">
                      <div><dt>Codigo</dt><dd>{detail.code}</dd></div>
                      <div><dt>Estado</dt><dd>{humanizeToken(treatmentDisplayStatus(detail))}</dd></div>
                      <div><dt>Area</dt><dd>{detail.primary_anomaly.area?.name || selectedProcess}</dd></div>
                      <div><dt>Programado</dt><dd>{formatDateTime(detail.scheduled_for)}</dd></div>
                      <div><dt>Creado</dt><dd>{formatDateTime(detail.created_at)}</dd></div>
                      <div><dt>Actualizado</dt><dd>{formatDateTime(detail.updated_at)}</dd></div>
                    </dl>
                    <div className="readonly-block">
                      <strong>Metodo</strong>
                      <p>{detail.method_used ? humanizeToken(detail.method_used) : "Sin metodo cargado"}</p>
                    </div>
                    <div className="readonly-block">
                      <strong>Observaciones</strong>
                      <p>{detail.observations || "Sin observaciones cargadas"}</p>
                    </div>
                    <div className="readonly-block treatment-detail-lesson">
                      <div className="section-head compact">
                        <strong>Lecciones aprendidas</strong>
                        {detail.learned_lesson?.saved_at ? <small>{formatDateTime(detail.learned_lesson.saved_at)}</small> : null}
                      </div>
                      {detail.learned_lesson ? (
                        <div className="treatment-detail-lesson-grid">
                          <div>
                            <small>Responsable carga</small>
                            <p>{detail.learned_lesson.saved_by?.full_name || detail.learned_lesson.saved_by?.username || "-"}</p>
                            <small>Hubo aprendizaje</small>
                            <p>{yesNo(detail.learned_lesson.has_learning)}</p>
                          </div>
                          <div>
                            <small>{detail.learned_lesson.has_learning === false ? "Por que no se aprendio" : "Que se aprendio"}</small>
                            <p>{detail.learned_lesson.has_learning === false ? detail.learned_lesson.no_learning_reason || "-" : detail.learned_lesson.learned_text || "-"}</p>
                            <small>Modifica procedimiento</small>
                            <p>{yesNo(detail.learned_lesson.procedure_modified)}</p>
                          </div>
                          <div>
                            <small>Detalle de modificacion</small>
                            <p>{detail.learned_lesson.procedure_modified ? detail.learned_lesson.procedure_modification_notes || "-" : "-"}</p>
                            <small>Evidencia objetiva</small>
                            {detail.learned_lesson.evidences.length ? (
                              <div className="stack-list compact treatment-detail-lesson-evidence">
                                {detail.learned_lesson.evidences.map((evidence) => (
                                  <a className="text-link" href={evidenceUrl(evidence.file_url)} key={evidence.id} rel="noopener noreferrer" target="_blank">
                                    {evidence.original_name}
                                  </a>
                                ))}
                              </div>
                            ) : (
                              <p>Sin evidencia objetiva cargada.</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <p>Sin leccion aprendida registrada para este tratamiento.</p>
                      )}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Usuarios relacionados</h3></div>
                    <div className="stack-list compact">
                      {relatedUsers.length ? relatedUsers.map((name) => <div className="list-card compact" key={name}><strong>{name}</strong></div>) : <p className="muted-copy">Sin usuarios relacionados.</p>}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Anomalias asociadas</h3></div>
                    <div className="stack-list compact">
                      {detail.anomaly_links.map((link) => (
                        <div className="list-card compact" key={link.id}>
                          <div>
                            <strong>{link.anomaly.code}</strong>
                            <p>{link.anomaly.title}</p>
                            <small>{link.anomaly.area?.name || "-"} | {link.anomaly.reporter?.full_name || link.anomaly.reporter?.username || "-"}</small>
                          </div>
                          <StatusBadge compact value={link.anomaly.current_status} />
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Convocados</h3></div>
                    <div className="stack-list compact">
                      {detail.participants.length ? detail.participants.map((participant) => (
                        <div className="list-card compact" key={participant.id}>
                          <div>
                            <strong>{participant.user?.full_name || participant.user?.username || "Sin usuario"}</strong>
                            <p>{participant.note || "Sin nota"}</p>
                          </div>
                          <StatusBadge compact value={participant.role} />
                        </div>
                      )) : <p className="muted-copy">Sin convocados.</p>}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Causas raiz</h3></div>
                    <div className="stack-list compact">
                      {detail.root_causes.length ? detail.root_causes.map((cause) => (
                        <div className="nested-card" key={cause.id}>
                          <strong>{`Causa ${cause.sequence}`}</strong>
                          <p>{cause.description}</p>
                        </div>
                      )) : <p className="muted-copy">Sin causas raiz cargadas.</p>}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Tareas generadas</h3></div>
                    <div className="stack-list compact">
                      {detail.tasks.length ? detail.tasks.map((task) => (
                        <div className="list-card compact" key={task.id}>
                          <div>
                            <strong>{task.code || task.title}</strong>
                            <p>{task.title}</p>
                            <small>Responsable: {task.responsible?.full_name || task.responsible?.username || "-"} | Ejecucion: {formatDate(task.execution_date)}</small>
                            <small>
                              Causas: {task.root_causes?.length ? task.root_causes.map((cause) => `Causa ${cause.sequence}`).join(", ") : "Sin causas"}
                            </small>
                            {task.evidences.length ? (
                              <ul className="evidence-list">
                                {task.evidences.map((evidence) => (
                                  <li className="evidence-item" key={evidence.id}>
                                    <a href={evidenceUrl(evidence.file_url)} rel="noopener noreferrer" target="_blank">{evidence.original_name}</a>
                                    <small>{formatDateTime(evidence.created_at)} | {evidence.note || "Sin nota"}</small>
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </div>
                          <StatusBadge compact value={task.status} />
                        </div>
                      )) : <p className="muted-copy">Sin tareas registradas.</p>}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Evaluacion y validacion</h3></div>
                    <dl className="key-grid compact">
                      <div><dt>Fecha evaluacion</dt><dd>{formatDate(detail.effectiveness_evaluation_date)}</dd></div>
                      <div><dt>Responsable evaluacion</dt><dd>{detail.effectiveness_responsible?.full_name || detail.effectiveness_responsible?.username || "-"}</dd></div>
                      <div><dt>Resultado</dt><dd>{detail.effectiveness_validation_result ? humanizeToken(detail.effectiveness_validation_result) : "-"}</dd></div>
                      <div><dt>Validado por</dt><dd>{detail.effectiveness_validated_by?.full_name || detail.effectiveness_validated_by?.username || "-"}</dd></div>
                      <div><dt>Fecha validacion</dt><dd>{formatDateTime(detail.effectiveness_validated_at)}</dd></div>
                    </dl>
                    <div className="readonly-block">
                      <strong>Comentario de validacion</strong>
                      <p>{detail.effectiveness_validation_comment || "Sin comentario de validacion"}</p>
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Evidencias del tratamiento</h3></div>
                    <div className="stack-list compact">
                      {detail.evidences.length ? detail.evidences.map((evidence) => (
                        <div className="list-card compact" key={evidence.id}>
                          <div className="evidence-block">
                            <a href={evidenceUrl(evidence.file_url)} rel="noopener noreferrer" target="_blank">{evidence.original_name}</a>
                            <small>{formatDateTime(evidence.created_at)} | {evidence.uploaded_by?.full_name || "-"}</small>
                            <p>{evidence.note || "Sin nota"}</p>
                          </div>
                        </div>
                      )) : <p className="muted-copy">Sin evidencias del tratamiento.</p>}
                    </div>
                  </section>

                  <section className="form-section">
                    <div className="section-head compact"><h3>Historial de tratamiento</h3></div>
                    <div className="stack-list compact">
                      {detail.audit_events?.length ? detail.audit_events.map((event) => (
                        <div className="list-card compact" key={event.id}>
                          <div>
                            <strong>{treatmentAuditActionLabel(event.action)}</strong>
                            <small>{formatDateTime(event.created_at)} | {event.actor?.full_name || event.actor?.username || "-"}</small>
                          </div>
                        </div>
                      )) : <p className="muted-copy">Sin historial registrado para este tratamiento.</p>}
                    </div>
                  </section>
                </>
              ) : (
                <div className="panel muted">
                  <h2>Sin tratamiento seleccionado</h2>
                  <p>Selecciona un tratamiento para consultar su espejo solo lectura.</p>
                </div>
              )}
            </DataState>
          </article>
        </div>
      </DataState>
    </section>
  );
}
