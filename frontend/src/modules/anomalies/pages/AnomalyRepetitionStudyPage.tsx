import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAnomalyRepetitionStudy } from "../../../api/anomalies";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatCard } from "../../../components/StatCard";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function AnomalyRepetitionStudyPage() {
  usePageTitle("Estudio de repitencia");
  const { user } = useAuth();
  const adminUser = user?.access_level === "administrador" || user?.access_level === "desarrollador";
  const [dateFrom, setDateFrom] = useState("");
  const [analysisDateFrom, setAnalysisDateFrom] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    if (!analysisDateFrom) {
      return null;
    }
    return fetchAnomalyRepetitionStudy(analysisDateFrom);
  }, [analysisDateFrom]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!dateFrom) {
      setValidationError("Completa el filtro Desde fecha antes de ejecutar el analisis.");
      return;
    }

    setValidationError(null);
    setAnalysisDateFrom(dateFrom);
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Estudio de repitencia"
        description="Consulta de repeticion de anomalias por tipo de desvio y sector."
        actionLabel="Volver"
        actionTo="/anomalies"
      />

      {!adminUser ? (
        <div className="panel danger">Esta consulta esta disponible solo para usuarios administradores.</div>
      ) : (
        <>
      <form className="toolbar-card repetition-study-toolbar" onSubmit={handleSubmit}>
        <label>
          <span>Desde fecha</span>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </label>
        <button className="button button-primary" type="submit">
          Ejecutar busqueda
        </button>
      </form>

      {validationError ? <div className="panel warning">{validationError}</div> : null}

      {!analysisDateFrom ? (
        <div className="panel muted">Selecciona Desde fecha y ejecuta la busqueda para ver el analisis.</div>
      ) : (
        <DataState loading={loading} error={error} onRetry={reload} empty={false}>
          {data ? (
            <>
              {data.total === 0 ? <div className="panel warning">No se encontraron anomalias para el periodo seleccionado.</div> : null}

              <section className="stats-grid">
                <StatCard label="Periodo analizado" value={`${formatDate(data.date_from)} a ${formatDate(data.date_to)}`} />
                <StatCard label="Total general" value={data.total} hint="Anomalias encontradas" tone="accent" />
                <StatCard label="Tipos de desvio" value={data.by_type.length} hint="Con registros en el periodo" tone="success" />
                <StatCard label="Sectores" value={new Set(data.by_type_sector.map((item) => item.sector_id)).size} hint="Con registros en el periodo" />
              </section>

              <section className="detail-layout">
                <article className="panel">
                  <div className="section-head">
                    <div>
                      <span className="eyebrow">Resumen</span>
                      <h2>Cantidad por tipo de desvio</h2>
                    </div>
                  </div>
                  {data.by_type.length ? (
                    <div className="stack-list">
                      {data.by_type.map((item) => (
                        <div className="list-card compact repetition-study-row" key={item.type_id}>
                          <strong>{item.type_name}</strong>
                          <span className="status-badge info compact">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted-copy">Sin tipos de desvio para el periodo.</p>
                  )}
                </article>

                <article className="panel">
                  <div className="section-head">
                    <div>
                      <span className="eyebrow">Detalle</span>
                      <h2>Tipo de desvio por sector</h2>
                    </div>
                  </div>
                  {data.by_type_sector.length ? (
                    <div className="stack-list">
                      {data.by_type_sector.map((item) => (
                        <div className="list-card compact repetition-study-row" key={`${item.type_id}-${item.sector_id}`}>
                          <div>
                            <strong>{item.type_name}</strong>
                            <small>{item.sector_name}</small>
                          </div>
                          <span className="status-badge success compact">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted-copy">Sin sectores para el periodo.</p>
                  )}
                </article>
              </section>

              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="eyebrow">Trazabilidad</span>
                    <h2>Anomalias intervinientes</h2>
                  </div>
                </div>
                {data.anomalies.length ? (
                  <div className="data-table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Titulo</th>
                          <th>Observaciones</th>
                          <th>Tipo de desvio</th>
                          <th>Sector</th>
                          <th>Fecha de registro</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.anomalies.map((item) => (
                          <tr key={item.id}>
                            <td>
                              <Link className="text-link" to={`/anomalies/${item.id}`}>
                                {item.code}
                              </Link>
                            </td>
                            <td>{item.title}</td>
                            <td>{item.observations}</td>
                            <td>{item.anomaly_type.name}</td>
                            <td>{item.sector.name}</td>
                            <td>{formatDateTime(item.registered_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted-copy">No se encontraron anomalias para el periodo seleccionado.</p>
                )}
              </section>
            </>
          ) : null}
        </DataState>
      )}
        </>
      )}
    </section>
  );
}
