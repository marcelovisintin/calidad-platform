import { useParams } from "react-router-dom";
import { fetchAnomalyDetail } from "../../../api/anomalies";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { Timeline } from "../../../components/Timeline";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function AnomalyDetailPage() {
  const { anomalyId = "" } = useParams();
  usePageTitle("Detalle de anomalia");
  const { data, loading, error, reload } = useAsyncTask(() => fetchAnomalyDetail(anomalyId), [anomalyId]);

  const initialVerificationLabel = data?.initial_verification
    ? `Verificada ${formatDateTime(data.initial_verification.verified_at)}${data.initial_verification.verified_by?.full_name ? ` por ${data.initial_verification.verified_by.full_name}` : ""}`
    : "No registrada";

  const classificationLabel = data?.classification?.summary || (data?.severity?.name ? `Criterio aplicado: ${data.severity.name}` : "No registrada");

  return (
    <section className="page-shell">
      <PageHeader title="Detalle de anomalia" description="Vista consolidada de trazabilidad, acciones e historial." />

      <DataState loading={loading} error={error} onRetry={reload}>
        {data ? (
          <div className="detail-layout">
            <article className="panel">
              <div className="section-head">
                <div>
                  <p className="eyebrow">{data.code}</p>
                  <h2>{data.title}</h2>
                </div>
                <div className="badge-stack align-end">
                  <StatusBadge value={data.current_status} />
                  <StatusBadge value={data.current_stage} />
                </div>
              </div>
              <p>{data.description}</p>
              <dl className="key-grid">
                <div><dt>Fecha y hora</dt><dd>{formatDateTime(data.detected_at)}</dd></div>
                <div><dt>Responsable actual</dt><dd>{data.current_responsible?.full_name || "Sin asignar"}</dd></div>
                <div><dt>Numero de OF</dt><dd>{data.manufacturing_order_number || "No informada"}</dd></div>
                <div><dt>Piezas afectadas</dt><dd>{data.affected_quantity ?? "No informada"}</dd></div>
                <div><dt>Proceso afectado</dt><dd>{data.affected_process || "-"}</dd></div>
                <div><dt>Criticidad</dt><dd>{data.severity?.name || "-"}</dd></div>
                <div><dt>Prioridad</dt><dd>{data.priority?.name || "-"}</dd></div>
                <div><dt>Proceso</dt><dd>{data.area?.name || "-"}</dd></div>
                <div><dt>Resultados</dt><dd>{data.result_summary || "Sin resumen de resultados."}</dd></div>
                <div><dt>Resolucion</dt><dd>{data.resolution_summary || "Sin resumen de resolucion."}</dd></div>
              </dl>
            </article>

            <article className="panel">
              <div className="section-head"><h2>Planes y acciones</h2></div>
              <div className="stack-list">
                {data.action_plans.length ? data.action_plans.map((plan) => (
                  <div className="nested-card" key={plan.id}>
                    <div className="section-head compact">
                      <div>
                        <strong>Plan {plan.id.slice(0, 8)}</strong>
                        <p>Responsable: {plan.owner?.full_name || "Sin responsable"}</p>
                      </div>
                      <StatusBadge value={plan.status} compact />
                    </div>
                    <div className="stack-list compact">
                      {plan.items?.map((item) => (
                        <div className="list-card compact" key={item.id}>
                          <div>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <small>Compromiso: {formatDate(item.due_date)}</small>
                          </div>
                          <div className="badge-stack align-end">
                            <StatusBadge value={item.effective_status || item.status} compact />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )) : <p className="muted-copy">Esta anomalia todavia no tiene planes de accion asociados.</p>}
              </div>
            </article>

            <article className="panel">
              <div className="section-head"><h2>Participacion y verificaciones</h2></div>
              <dl className="key-grid">
                <div><dt>Verificacion inicial</dt><dd>{initialVerificationLabel}</dd></div>
                <div><dt>Clasificacion</dt><dd>{classificationLabel}</dd></div>
                <div><dt>Analisis de causa</dt><dd>{data.cause_analysis?.summary || "No registrado"}</dd></div>
                <div><dt>Eficacia</dt><dd>{data.effectiveness_summary || "Sin verificacion de eficacia"}</dd></div>
                <div><dt>Aprendizaje</dt><dd>{data.learning?.lessons_learned || "Sin aprendizaje registrado"}</dd></div>
                <div><dt>Participantes</dt><dd>{data.participants.length ? data.participants.map((item) => item.user?.full_name || item.role).join(", ") : "Sin participantes"}</dd></div>
              </dl>
            </article>

            <article className="panel detail-span-2">
              <div className="section-head"><h2>Historial</h2></div>
              <Timeline items={data.status_history} />
            </article>
          </div>
        ) : null}
      </DataState>
    </section>
  );
}
