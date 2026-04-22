import { ChangeEvent, MouseEvent, useDeferredValue, useEffect, useState } from "react";
import { fetchUsers } from "../../../api/accounts";
import { fetchTreatmentTasksHistory } from "../../../api/treatments";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

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

  const handleCardClick = (event: MouseEvent<HTMLElement>, taskId: string) => {
    const target = event.target as HTMLElement;
    if (target.closest("button") || target.closest("a")) {
      return;
    }
    setSelectedTaskId(taskId);
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

      <DataState
        loading={loading || usersLoading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay acciones para mostrar"
        emptyDescription="Ajusta los filtros para revisar el historico de tareas."
      >
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
                onClick={(event) => handleCardClick(event, item.id)}
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

                {isSelected ? (
                  <div className="action-detail-inline">
                    <dl className="key-grid compact">
                      <div>
                        <dt>Tratamiento</dt>
                        <dd>{item.treatment?.code || "-"}</dd>
                      </div>
                      <div>
                        <dt>Estado tratamiento</dt>
                        <dd>{item.treatment?.status || "-"}</dd>
                      </div>
                      <div>
                        <dt>Fecha de ejecucion</dt>
                        <dd>{formatDate(item.execution_date)}</dd>
                      </div>
                      <div>
                        <dt>Causa raiz</dt>
                        <dd>{item.root_cause?.description || "Sin causa raiz"}</dd>
                      </div>
                    </dl>

                    {item.evidences.length ? (
                      <section className="form-section">
                        <div className="section-head compact">
                          <h3>Evidencias de la tarea</h3>
                        </div>
                        <div className="stack-list compact">
                          {item.evidences.map((evidence) => (
                            <div className="list-card compact" key={evidence.id}>
                              <div>
                                <a href={getEvidenceUrl(evidence.file_url)} rel="noopener noreferrer" target="_blank">
                                  {evidence.note || evidence.original_name || "Abrir evidencia"}
                                </a>
                                <small>{formatDateTime(evidence.created_at)}</small>
                              </div>
                            </div>
                          ))}
                        </div>
                      </section>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
      </DataState>
    </section>
  );
}
