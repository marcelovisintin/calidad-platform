import { useState } from "react";
import { fetchInbox, fetchInboxSummary, markInboxItemRead } from "../../../api/notifications";
import { formatDateTime, humanizeToken } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatCard } from "../../../components/StatCard";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function InboxPage() {
  usePageTitle("Bandeja interna");
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useAsyncTask(async () => {
    const [summary, inbox] = await Promise.all([fetchInboxSummary(), fetchInbox(page)]);
    return { summary, inbox };
  }, [page]);

  const handleRead = async (id: string) => {
    try {
      await markInboxItemRead(id);
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo actualizar la bandeja.");
    }
  };

  const totalCount = data?.inbox.count ?? 0;

  return (
    <section className="page-shell">
      <PageHeader title="Bandeja interna" description="Notificaciones operativas e indicadores de pendientes por usuario." />

      <DataState loading={loading} error={error} onRetry={reload}>
        {data ? (
          <>
            <div className="stats-grid compact-grid">
              <StatCard label="Total" value={data.summary.total} />
              <StatCard label="No leidas" value={data.summary.unread} tone="warning" />
              <StatCard label="Tareas" value={data.summary.tasks_total} tone="accent" />
              <StatCard label="Vencidas" value={data.summary.tasks_overdue} tone="success" />
            </div>

            <div className="stack-list">
              {data.inbox.results.map((item) => (
                <article className="panel" key={item.id}>
                  <div className="section-head compact">
                    <div>
                      <strong>{item.title}</strong>
                      <p>{item.body}</p>
                    </div>
                    <StatusBadge value={item.task_status || item.delivery_status} />
                  </div>
                  <small>{humanizeToken(item.category)} · {formatDateTime(item.created_at)}</small>
                  <div className="form-actions">
                    {!item.read_at ? (
                      <button className="button button-secondary" onClick={() => void handleRead(item.id)} type="button">Marcar leida</button>
                    ) : (
                      <span className="muted-copy">Leida {formatDateTime(item.read_at)}</span>
                    )}
                  </div>
                </article>
              ))}
            </div>

            <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
          </>
        ) : null}
      </DataState>
    </section>
  );
}