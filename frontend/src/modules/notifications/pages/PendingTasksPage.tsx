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
  if (item.source_type.includes("anomal") && item.source_id) {
    return `/anomalies/${item.source_id}`;
  }
  if (item.task_type?.includes("action")) {
    return "/actions/mine";
  }
  return "/notifications/inbox";
}

type TaskCardProps = {
  item: NotificationInboxItem;
  onResolve?: (id: string, taskStatus: string) => void;
};

function TaskCard({ item, onResolve }: TaskCardProps) {
  return (
    <article className="panel">
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
        {onResolve ? (
          <>
            <button className="button button-ghost" onClick={() => onResolve(item.id, "in_progress")} type="button">En curso</button>
            <button className="button button-primary" onClick={() => onResolve(item.id, "completed")} type="button">Resolver</button>
          </>
        ) : null}
      </div>
    </article>
  );
}

export function PendingTasksPage() {
  usePageTitle("Tareas pendientes");
  const [page, setPage] = useState(1);
  const [completedPage, setCompletedPage] = useState(1);
  const { data, loading, error, reload } = useAsyncTask(() => fetchInboxTasks(page), [page]);
  const {
    data: completedData,
    loading: completedLoading,
    error: completedError,
    reload: reloadCompleted,
  } = useAsyncTask(() => fetchInboxTasks(completedPage, "completed"), [completedPage]);

  const handleResolve = async (id: string, taskStatus: string) => {
    try {
      await resolveInboxTask(id, taskStatus, "Actualizado desde frontend.");
      await Promise.all([reload(), reloadCompleted()]);
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
            <TaskCard item={item} key={item.id} onResolve={(id, taskStatus) => void handleResolve(id, taskStatus)} />
          ))}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
      </DataState>

      <details className="panel completed-disclosure">
        <summary>
          <span>Completadas</span>
          <span className="completed-disclosure-count">{completedData?.count ?? 0}</span>
        </summary>
        <div className="completed-disclosure-content">
          <DataState
            loading={completedLoading}
            error={completedError}
            onRetry={reloadCompleted}
            empty={(completedData?.count ?? 0) === 0}
            emptyTitle="No hay tareas completadas"
            emptyDescription="Las tareas resueltas apareceran en este historial."
          >
            <div className="stack-list">
              {completedData?.results.map((item) => <TaskCard item={item} key={item.id} />)}
            </div>
            <PaginationControls
              page={completedPage}
              totalCount={completedData?.count ?? 0}
              onPageChange={setCompletedPage}
              disabled={completedLoading}
            />
          </DataState>
        </div>
      </details>
    </section>
  );
}
