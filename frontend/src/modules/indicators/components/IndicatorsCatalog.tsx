import { Link } from "react-router-dom";
import { fetchIndicatorCatalog } from "../../../api/indicators";
import { DataState } from "../../../components/DataState";
import { useAsyncTask } from "../../../hooks/useAsyncTask";


const DATE_LABELS: Record<string, string> = {
  classified_at: "Fecha de clasificacion",
  created_at: "Fecha de creacion",
  detected_at: "Fecha de deteccion",
  saved_at: "Fecha de registro",
  validated_at: "Fecha de validacion",
};

export function IndicatorsCatalog() {
  const { data, loading, error, reload } = useAsyncTask(fetchIndicatorCatalog, []);

  return (
    <DataState loading={loading} error={error} onRetry={reload}>
      {data ? (
        <div className="management-grid indicator-catalog-grid">
          {data.indicators.map((indicator) => (
            <Link className="management-card indicator-catalog-card" key={indicator.key} to={indicator.dashboard_url}>
              <span className="section-sequence-badge">{indicator.sequence}</span>
              <p className="eyebrow">Indicador</p>
              <h3>{indicator.title}</h3>
              <p>{indicator.description}</p>
              <small>{DATE_LABELS[indicator.primary_date] ?? indicator.primary_date}</small>
              <span className="management-card-link">Abrir dashboard</span>
            </Link>
          ))}
        </div>
      ) : null}
    </DataState>
  );
}
