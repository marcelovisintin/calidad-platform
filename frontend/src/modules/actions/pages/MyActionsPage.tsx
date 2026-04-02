import { useState } from "react";
import { fetchMyActions, transitionActionItem } from "../../../api/actions";
import { formatDate } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function MyActionsPage() {
  usePageTitle("Mis acciones");
  const [busyId, setBusyId] = useState<string | null>(null);
  const { data, loading, error, reload } = useAsyncTask(fetchMyActions, []);

  const handleTransition = async (actionId: string, targetStatus: string, defaultComment: string) => {
    setBusyId(actionId);
    try {
      const closureComment =
        targetStatus === "completed"
          ? window.prompt("Comentario de cierre (opcional)", "Accion completada desde frontend.") || ""
          : "";
      await transitionActionItem(actionId, targetStatus, defaultComment, closureComment);
      await reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "No se pudo actualizar la accion.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="page-shell">
      <PageHeader title="Mis acciones" description="Seguimiento rapido de acciones asignadas al usuario." />

      <DataState loading={loading} error={error} onRetry={reload} empty={!data?.results.length} emptyTitle="No hay acciones asignadas" emptyDescription="Cuando una anomalia te asigne una accion, aparecera aca.">
        <div className="stack-list">
          {data?.results.map((item) => (
            <article className="panel action-card" key={item.id}>
              <div className="section-head compact">
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.description || "Sin descripcion."}</p>
                </div>
                <StatusBadge value={item.effective_status || item.status} />
              </div>
              <dl className="key-grid compact">
                <div><dt>Tipo</dt><dd>{item.action_type?.name || "-"}</dd></div>
                <div><dt>Prioridad</dt><dd>{item.priority?.name || "-"}</dd></div>
                <div><dt>Compromiso</dt><dd>{formatDate(item.due_date)}</dd></div>
                <div><dt>Evidencia esperada</dt><dd>{item.expected_evidence || "Sin definir"}</dd></div>
              </dl>
              <div className="form-actions">
                {item.status === "pending" ? (
                  <button className="button button-secondary" disabled={busyId === item.id} onClick={() => void handleTransition(item.id, "in_progress", "Se inicia la ejecucion de la accion.")} type="button">Iniciar</button>
                ) : null}
                {item.status === "in_progress" ? (
                  <button className="button button-primary" disabled={busyId === item.id} onClick={() => void handleTransition(item.id, "completed", "La accion fue ejecutada y completada.")} type="button">Completar</button>
                ) : null}
                {!["completed", "cancelled"].includes(item.status) ? (
                  <button className="button button-ghost" disabled={busyId === item.id} onClick={() => void handleTransition(item.id, "cancelled", "La accion fue cancelada desde el frontend.")} type="button">Cancelar</button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </DataState>
    </section>
  );
}
