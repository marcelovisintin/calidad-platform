import { FormEvent, useMemo, useState } from "react";
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
  const [selectedDetail, setSelectedDetail] = useState<{ typeId: string; sectorId: string; findingTypeId: string } | null>(null);
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
    setSelectedDetail(null);
    setAnalysisDateFrom(dateFrom);
  };

  const selectedDetailBucket = useMemo(() => {
    if (!data || !selectedDetail) {
      return null;
    }
    return data.by_type_sector.find(
      (item) =>
        item.type_id === selectedDetail.typeId &&
        item.sector_id === selectedDetail.sectorId &&
        item.finding_type_id === selectedDetail.findingTypeId,
    ) ?? null;
  }, [data, selectedDetail]);

  const visibleAnomalies = useMemo(() => {
    if (!data) {
      return [];
    }
    if (!selectedDetail) {
      return data.anomalies;
    }
    return data.anomalies.filter(
      (item) =>
        item.anomaly_type.id === selectedDetail.typeId &&
        item.sector.id === selectedDetail.sectorId &&
        item.finding_type.id === selectedDetail.findingTypeId,
    );
  }, [data, selectedDetail]);

  return (
    <section className="page-shell">
      <PageHeader
        title="Estudio de repitencia"
        description="Consulta de repeticion de anomalias por tipo de desvio, asignacion y tipo de hallazgo."
        actionLabel="Volver"
        actionTo="/anomalies"
      />

      {!adminUser ? (
        <div className="panel danger">Esta consulta esta disponible solo para usuarios administradores.</div>
      ) : (
        <>
      <form className="toolbar-card repetition-study-toolbar" data-update-ignore="true" onSubmit={handleSubmit}>
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
                <StatCard label="Asignados a" value={new Set(data.by_type_sector.map((item) => item.sector_id)).size} hint="Con registros en el periodo" />
                <StatCard label="Tipos de hallazgo" value={new Set(data.by_type_sector.map((item) => item.finding_type_id)).size} hint="Con registros en el periodo" />
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
                      <h2>Tipo de desvio por asignado a y tipo de hallazgo</h2>
                    </div>
                  </div>
                  {data.by_type_sector.length ? (
                    <div className="stack-list">
                      {data.by_type_sector.map((item) => {
                        const isSelected =
                          selectedDetail?.typeId === item.type_id &&
                          selectedDetail?.sectorId === item.sector_id &&
                          selectedDetail?.findingTypeId === item.finding_type_id;
                        return (
                        <button
                          className={`list-card compact repetition-study-row repetition-study-button${isSelected ? " selected" : ""}`}
                          data-desvio-id={item.type_id}
                          data-proceso-id={item.sector_id}
                          data-tipo-hallazgo-id={item.finding_type_id}
                          key={`${item.type_id}-${item.sector_id}-${item.finding_type_id}`}
                          onClick={() =>
                            setSelectedDetail({
                              typeId: item.type_id,
                              sectorId: item.sector_id,
                              findingTypeId: item.finding_type_id,
                            })
                          }
                          type="button"
                        >
                          <div>
                            <strong>{item.type_name}</strong>
                            <small>{item.sector_name}</small>
                            <small>{`Tipo de hallazgo: ${item.finding_type_name}`}</small>
                          </div>
                          <span className="status-badge success compact">{item.count}</span>
                        </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="muted-copy">Sin asignaciones para el periodo.</p>
                  )}
                </article>
              </section>

              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="eyebrow">Trazabilidad</span>
                    <h2>
                      {selectedDetailBucket
                        ? `Anomalias intervinientes: ${selectedDetailBucket.type_name} / ${selectedDetailBucket.sector_name} / ${selectedDetailBucket.finding_type_name}`
                        : "Anomalias intervinientes"}
                    </h2>
                  </div>
                  {selectedDetail ? (
                    <button className="button button-secondary" onClick={() => setSelectedDetail(null)} type="button">
                      Ver todas
                    </button>
                  ) : null}
                </div>
                {visibleAnomalies.length ? (
                  <div className="data-table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Titulo</th>
                          <th>Observaciones</th>
                          <th>Tipo de desvio</th>
                          <th>Asignado a</th>
                          <th>Tipo de hallazgo</th>
                          <th>Fecha de registro</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleAnomalies.map((item) => (
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
                            <td>{item.finding_type.name}</td>
                            <td>{formatDateTime(item.registered_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted-copy">No se encontraron anomalias para la combinacion seleccionada.</p>
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
