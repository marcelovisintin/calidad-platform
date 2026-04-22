import { Link } from "react-router-dom";
import { fetchInboxTasks, resolveInboxTask } from "../../../api/notifications";
import type { NotificationInboxItem } from "../../../api/types";
import { formatDateTime, humanizeToken } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { useState } from "react";

function resolveTaskLink(item: NotificationInboxItem) {
  if (item.source_type === "anomaly" && item.source_id) {
    return `/anomalies/${item.source_id}`;
  }
  if (item.task_type?.includes("action")) {
    return "/actions/mine";
  }
  return "/notifications/inbox";
}

export function PendingTasksPage() {
  usePageTitle("Tareas pendientes");
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useAsyncTask(() => fetchInboxTasks(page), [page]);

  const handleResolve = async (id: string, taskStatus: string) => {
    try {
      await resolveInboxTask(id, taskStatus, "Actualizado desde frontend.");
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo actualizar la tarea.");
    }
  };

  const totalCount = data?.count ?? 0;

  return (
    <section className="page-shell">
      <PageHeader title="Tareas pendientes" description="Pendientes operativos y solicitudes de participacion del usuario." />

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle="No hay tareas pendientes"
        emptyDescription="Las solicitudes de participacion y acciones pendientes apareceran aca."
      >
        <div className="stack-list">
          {data?.results.map((item) => (
            <article className="panel" key={item.id}>
              <div className="section-head compact">
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.body}</p>
                </div>
                <StatusBadge value={item.task_status || item.delivery_status} />
              </div>
              <dl className="key-grid compact">
                <div><dt>Tipo</dt><dd>{humanizeToken(item.task_type || item.category)}</dd></div>
                <div><dt>Vencimiento</dt><dd>{formatDateTime(item.due_at)}</dd></div>
              </dl>
              <div className="form-actions">
                <Link className="button button-secondary" to={resolveTaskLink(item)}>Ver contexto</Link>
                <button className="button button-ghost" onClick={() => void handleResolve(item.id, "in_progress")} type="button">En curso</button>
                <button className="button button-primary" onClick={() => void handleResolve(item.id, "completed")} type="button">Resolver</button>
              </div>
            </article>
          ))}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
      </DataState>
    </section>
  );
}