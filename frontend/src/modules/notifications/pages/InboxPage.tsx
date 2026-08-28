import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  fetchInbox,
  fetchInboxSummary,
  fetchInboxTasks,
  markInboxItemRead,
  resolveInboxTask,
} from "../../../api/notifications";
import type { NotificationInboxItem } from "../../../api/types";
import { formatDateTime, humanizeToken } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatCard } from "../../../components/StatCard";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type InboxTab = "pending" | "notices" | "history";

const MANUALLY_CONFIRMABLE_TASK_TYPES = new Set([
  "analysis_participation",
  "treatment_participation",
]);

function resolveInboxTab(value: string | null): InboxTab {
  if (value === "notices" || value === "history") {
    return value;
  }
  return "pending";
}

function resolveContextPath(item: NotificationInboxItem) {
  const configuredPath = (item.action_url || "").trim();
  if (configuredPath.startsWith("/api/v1/anomalies/")) {
    return configuredPath.replace(/^\/api\/v1/, "").replace(/\/$/, "");
  }
  if (configuredPath.startsWith("/")) {
    return configuredPath;
  }
  if (item.source_type?.includes("anomal") && item.source_id) {
    return `/anomalies/${item.source_id}`;
  }
  if (item.task_type === "action_assignment") {
    return "/actions/mine";
  }
  return "";
}

type InboxCardProps = {
  item: NotificationInboxItem;
  busy: boolean;
  history?: boolean;
  onConfirm: (item: NotificationInboxItem) => void;
  onOpen: (item: NotificationInboxItem) => void;
  onRead: (item: NotificationInboxItem) => void;
};

function InboxCard({ item, busy, history = false, onConfirm, onOpen, onRead }: InboxCardProps) {
  const contextPath = resolveContextPath(item);
  const canConfirm =
    !history &&
    item.is_task &&
    MANUALLY_CONFIRMABLE_TASK_TYPES.has(item.task_type || "") &&
    ["pending", "in_progress"].includes(item.task_status || "");

  return (
    <article className={`panel notification-card${item.read_at ? "" : " unread"}`}>
      <div className="section-head compact">
        <div>
          <strong>{item.title}</strong>
          <p>{item.body}</p>
        </div>
        <StatusBadge compact value={item.task_status || item.delivery_status} />
      </div>

      <dl className="key-grid compact notification-card-meta">
        <div>
          <dt>{item.is_task ? "Tipo" : "Categoria"}</dt>
          <dd>{humanizeToken(item.task_type || item.category)}</dd>
        </div>
        {item.is_task ? (
          <div>
            <dt>Vencimiento</dt>
            <dd>{item.due_at ? formatDateTime(item.due_at) : "Sin fecha"}</dd>
          </div>
        ) : null}
        <div>
          <dt>Recibida</dt>
          <dd>{formatDateTime(item.created_at)}</dd>
        </div>
        {item.resolved_at ? (
          <div>
            <dt>Finalizada</dt>
            <dd>{formatDateTime(item.resolved_at)}</dd>
          </div>
        ) : null}
      </dl>

      <div className="form-actions notification-card-actions">
        {contextPath ? (
          <button className="button button-secondary" disabled={busy} onClick={() => onOpen(item)} type="button">
            Abrir contexto
          </button>
        ) : null}
        {!item.read_at && !contextPath ? (
          <button className="button button-secondary" disabled={busy} onClick={() => onRead(item)} type="button">
            Marcar leida
          </button>
        ) : null}
        {canConfirm ? (
          <button className="button button-primary" disabled={busy} onClick={() => onConfirm(item)} type="button">
            Confirmar visto
          </button>
        ) : null}
        {item.read_at ? <span className="muted-copy">Leida {formatDateTime(item.read_at)}</span> : null}
      </div>
    </article>
  );
}

export function InboxPage() {
  usePageTitle("Bandeja y pendientes");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = resolveInboxTab(searchParams.get("tab"));
  const [pages, setPages] = useState<Record<InboxTab, number>>({ pending: 1, notices: 1, history: 1 });
  const [busyItemId, setBusyItemId] = useState("");
  const currentPage = pages[activeTab];

  const { data, loading, error, reload } = useAsyncTask(async () => {
    const inboxRequest = activeTab === "pending"
      ? fetchInboxTasks(currentPage)
      : activeTab === "history"
        ? fetchInboxTasks(currentPage, "closed")
        : fetchInbox(currentPage, { isTask: false, unreadFirst: true });
    const [summary, items] = await Promise.all([fetchInboxSummary(), inboxRequest]);
    return { summary, items };
  }, [activeTab, currentPage]);

  const changeTab = (tab: InboxTab) => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", tab);
    setSearchParams(nextParams, { replace: true });
  };

  const changePage = (page: number) => {
    setPages((current) => ({ ...current, [activeTab]: page }));
  };

  const handleRead = async (item: NotificationInboxItem) => {
    setBusyItemId(item.id);
    try {
      await markInboxItemRead(item.id);
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo actualizar la bandeja.");
    } finally {
      setBusyItemId("");
    }
  };

  const handleOpen = async (item: NotificationInboxItem) => {
    const contextPath = resolveContextPath(item);
    setBusyItemId(item.id);
    try {
      if (!item.read_at) {
        await markInboxItemRead(item.id);
      }
      if (contextPath) {
        navigate(contextPath);
        return;
      }
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo abrir el contexto.");
    } finally {
      setBusyItemId("");
    }
  };

  const handleConfirm = async (item: NotificationInboxItem) => {
    setBusyItemId(item.id);
    try {
      await resolveInboxTask(item.id, "completed", "Participacion confirmada desde la Bandeja.");
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo confirmar la participacion.");
    } finally {
      setBusyItemId("");
    }
  };

  const pendingCount = (data?.summary.tasks_pending ?? 0) + (data?.summary.tasks_in_progress ?? 0);
  const historyCount = Math.max((data?.summary.tasks_total ?? 0) - pendingCount, 0);
  const totalCount = data?.items.count ?? 0;
  const emptyCopy = {
    pending: {
      title: "No hay pendientes",
      description: "Las acciones, verificaciones e invitaciones que requieran atencion apareceran aca.",
    },
    notices: {
      title: "No hay avisos",
      description: "Las confirmaciones y comunicaciones informativas apareceran aca.",
    },
    history: {
      title: "No hay historial",
      description: "Los pendientes completados o descartados apareceran aca.",
    },
  }[activeTab];

  return (
    <section className="page-shell">
      <PageHeader
        title="Bandeja y pendientes"
        description="Centro unico de avisos, asignaciones y participaciones del usuario."
      />

      <DataState loading={loading} error={error} onRetry={reload}>
        {data ? (
          <>
            <div className="stats-grid compact-grid">
              <StatCard label="Pendientes" value={data.summary.tasks_pending} tone="warning" />
              <StatCard label="En curso" value={data.summary.tasks_in_progress} tone="accent" />
              <StatCard label="Vencidas" value={data.summary.tasks_overdue} tone="success" />
              <StatCard label="Avisos no leidos" value={data.summary.notices_unread} />
            </div>

            <div aria-label="Secciones de la bandeja" className="inbox-tabs" role="tablist">
              <button aria-selected={activeTab === "pending"} className="inbox-tab" onClick={() => changeTab("pending")} role="tab" type="button">
                Pendientes <span>{pendingCount}</span>
              </button>
              <button aria-selected={activeTab === "notices"} className="inbox-tab" onClick={() => changeTab("notices")} role="tab" type="button">
                Avisos <span>{data.summary.notices_unread}</span>
              </button>
              <button aria-selected={activeTab === "history"} className="inbox-tab" onClick={() => changeTab("history")} role="tab" type="button">
                Historial <span>{historyCount}</span>
              </button>
            </div>

            <DataState loading={false} empty={totalCount === 0} emptyTitle={emptyCopy.title} emptyDescription={emptyCopy.description}>
              <div className="stack-list notification-list">
                {data.items.results.map((item) => (
                  <InboxCard
                    busy={busyItemId === item.id}
                    history={activeTab === "history"}
                    item={item}
                    key={item.id}
                    onConfirm={(selected) => void handleConfirm(selected)}
                    onOpen={(selected) => void handleOpen(selected)}
                    onRead={(selected) => void handleRead(selected)}
                  />
                ))}
              </div>
              <PaginationControls page={currentPage} totalCount={totalCount} onPageChange={changePage} disabled={loading} />
            </DataState>
          </>
        ) : null}
      </DataState>
    </section>
  );
}
