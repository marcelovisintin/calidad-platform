import { ChangeEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { classifyAnomalyBySeverity, fetchMyAnomalies, unlockAnomalyClassificationChange } from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import type { CatalogSummary } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function MyAnomaliesPage() {
  usePageTitle("Seguimiento de anomalias");
  const { user } = useAuth();
  const adminUser = useMemo(() => isAdminUser(user), [user]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [classificationError, setClassificationError] = useState<string | null>(null);
  const [classificationMessage, setClassificationMessage] = useState<string | null>(null);
  const [updatingAnomalyId, setUpdatingAnomalyId] = useState<string | null>(null);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    if (!user) {
      throw new Error("No hay usuario autenticado.");
    }

    const [anomalies, catalogs] = await Promise.all([
      fetchMyAnomalies(adminUser ? undefined : user.id, search, page),
      fetchCatalogBootstrap(),
    ]);

    return {
      anomalies,
      criteria: catalogs.severities,
    };
  }, [user?.id, search, adminUser, page]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleClassificationChange = async (anomalyId: string, severityId: string, canModifyClassification: boolean) => {
    if (!severityId || !adminUser) {
      return;
    }

    if (!canModifyClassification) {
      setClassificationMessage(null);
      setClassificationError("No se puede modificar la clasificacion.");
      return;
    }

    if (!window.confirm("Esta seguro de la clasificacion?")) {
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setUpdatingAnomalyId(anomalyId);

    try {
      await classifyAnomalyBySeverity(anomalyId, severityId);
      setClassificationMessage("Clasificacion actualizada.");
      await reload();
    } catch (err) {
      setClassificationError(err instanceof Error ? err.message : "No se pudo actualizar la clasificacion.");
    } finally {
      setUpdatingAnomalyId(null);
    }
  };

  const handleUnlockClassification = async (anomalyId: string) => {
    if (!adminUser) {
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setUpdatingAnomalyId(anomalyId);

    try {
      await unlockAnomalyClassificationChange(anomalyId);
      setClassificationMessage("Se habilita el cambio de clasificacion.");
      await reload();
    } catch (err) {
      setClassificationError(err instanceof Error ? err.message : "No se pudo habilitar el cambio de clasificacion.");
    } finally {
      setUpdatingAnomalyId(null);
    }
  };

  const criteria: CatalogSummary[] = data?.criteria ?? [];
  const totalCount = data?.anomalies.count ?? 0;

  return (
    <section className="page-shell">
      <PageHeader
        title="Seguimiento de anomalias"
        description={adminUser ? "Listado completo de seguimiento para administracion." : "Listado filtrado por usuario reportante."}
        actionLabel="Nueva"
        actionTo="/anomalies/new"
      />

      <div className="toolbar-card">
        <input onChange={handleSearchChange} placeholder="Buscar por codigo, titulo, proceso o usuario reportante" type="search" value={search} />
      </div>

      {classificationError ? <div className="panel danger">{classificationError}</div> : null}
      {classificationMessage ? <div className="panel info">{classificationMessage}</div> : null}

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle={adminUser ? "No hay anomalias registradas" : "Todavia no reportaste anomalias"}
        emptyDescription="Cuando registres una nueva anomalia, aparecera en este listado."
      >
        <div className="stack-list">
          {data?.anomalies.results.map((item) => {
            const canModifyClassification = item.can_modify_classification ?? true;
            const canUnlockClassification = item.can_unlock_classification ?? false;
            const disableClassificationSelect =
              updatingAnomalyId === item.id || criteria.length === 0 || !canModifyClassification;

            return (
              <article className="list-card anomaly-row" key={item.id}>
                <Link className="anomaly-row-main" to={`/anomalies/${item.id}`}>
                  <strong>{item.code}</strong>
                  <p>{item.title}</p>
                  <small>{`Reportada por: ${item.reporter?.full_name || item.reporter?.username || "Sin dato"}`}</small>
                  <small>
                    {item.site?.name || "Sin area"} | {item.area?.name || "Sin proceso"} | {formatDateTime(item.detected_at)}
                  </small>
                </Link>

                <div className="badge-stack align-end anomaly-row-actions">
                  <StatusBadge value={item.current_status} compact />

                  {adminUser ? (
                    <label className="anomaly-classification-control">
                      <span>Clasificacion</span>
                      <select
                        aria-label={`Clasificacion de ${item.code}`}
                        disabled={disableClassificationSelect}
                        onChange={(event) => void handleClassificationChange(item.id, event.target.value, canModifyClassification)}
                        value={item.severity?.id || ""}
                      >
                        <option value="">Seleccionar...</option>
                        {criteria.map((criterion) => (
                          <option key={criterion.id} value={criterion.id}>
                            {criterion.name}
                          </option>
                        ))}
                      </select>
                      {canUnlockClassification ? (
                        <button
                          className="button button-secondary"
                          disabled={updatingAnomalyId === item.id}
                          onClick={() => void handleUnlockClassification(item.id)}
                          type="button"
                        >
                          Habilitar cambio
                        </button>
                      ) : null}
                      {!canModifyClassification && !canUnlockClassification ? (
                        <small className="muted-copy">No se puede modificar la clasificacion.</small>
                      ) : null}
                    </label>
                  ) : (
                    <span className="status-badge info compact">{item.severity?.name || "Sin clasificar"}</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
      </DataState>
    </section>
  );
}
