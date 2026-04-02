import { Link, useLocation } from "react-router-dom";
import type { AnomalyDetail } from "../../../api/types";
import { formatDateTime, humanizeToken } from "../../../app/utils";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { usePageTitle } from "../../../hooks/usePageTitle";

const CREATED_ANOMALY_KEY = "calidad-platform.last-created-anomaly";

export function AnomalyCreatedPage() {
  usePageTitle("Confirmacion de carga");
  const location = useLocation();
  const fromState = (location.state as { anomaly?: AnomalyDetail } | null)?.anomaly;
  const fromStorage = window.sessionStorage.getItem(CREATED_ANOMALY_KEY);
  const anomaly = fromState ?? (fromStorage ? (JSON.parse(fromStorage) as AnomalyDetail) : null);

  return (
    <section className="page-shell narrow">
      <PageHeader title="Confirmacion de carga" description="La anomalia fue registrada correctamente en backend." />

      {anomaly ? (
        <article className="panel confirmation-card">
          <div className="confirmation-head">
            <strong>{anomaly.code}</strong>
            <StatusBadge value={anomaly.current_status} />
          </div>
          <h2>{anomaly.title}</h2>
          <p>{anomaly.description}</p>
          <dl className="key-grid">
            <div><dt>ID generado</dt><dd>{anomaly.code}</dd></div>
            <div><dt>Estado inicial</dt><dd>{humanizeToken(anomaly.current_status)}</dd></div>
            <div><dt>Etapa actual</dt><dd>{humanizeToken(anomaly.current_stage)}</dd></div>
            <div><dt>Fecha y hora</dt><dd>{formatDateTime(anomaly.detected_at)}</dd></div>
            <div><dt>Responsable actual</dt><dd>{anomaly.current_responsible?.full_name || "Sin asignar"}</dd></div>
            <div><dt>Numero de OF</dt><dd>{anomaly.manufacturing_order_number || "No informada"}</dd></div>
            <div><dt>Piezas afectadas</dt><dd>{anomaly.affected_quantity ?? "No informada"}</dd></div>
          </dl>
          <div className="form-actions">
            <Link className="button button-primary" to={`/anomalies/${anomaly.id}`}>Ver detalle</Link>
            <Link className="button button-secondary" to="/anomalies/new">Cargar otra</Link>
          </div>
        </article>
      ) : (
        <div className="panel muted">No hay una anomalia reciente para mostrar. Volve al alta para generar una nueva confirmacion.</div>
      )}
    </section>
  );
}
