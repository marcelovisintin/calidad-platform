import { MouseEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchAnomalyDetail } from "../../../api/anomalies";
import { readStoredSession } from "../../../api/http";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { Timeline } from "../../../components/Timeline";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function AnomalyDetailPage() {
  const { anomalyId = "" } = useParams();
  const navigate = useNavigate();
  const [attachmentError, setAttachmentError] = useState<string | null>(null);

  usePageTitle("Detalle de anomalia");
  const { data, loading, error, reload } = useAsyncTask(() => fetchAnomalyDetail(anomalyId), [anomalyId]);

  const initialVerificationLabel = data?.initial_verification
    ? `Verificada ${formatDateTime(data.initial_verification.verified_at)}${data.initial_verification.verified_by?.full_name ? ` por ${data.initial_verification.verified_by.full_name}` : ""}`
    : "No registrada";

  const classificationLabel = data?.classification?.summary || (data?.severity?.name ? `Criterio aplicado: ${data.severity.name}` : "No registrada");

  const treatmentCreatedEntry = data?.status_history.find((item) => item.to_stage === "treatment_created");
  const treatmentCreatedLabel = treatmentCreatedEntry
    ? `Creado ${formatDateTime(treatmentCreatedEntry.changed_at)}${treatmentCreatedEntry.changed_by?.full_name ? ` por ${treatmentCreatedEntry.changed_by.full_name}` : ""}`
    : data?.current_stage === "treatment_created"
      ? "En curso"
      : "No registrado";

  const causeAnalysisLabel = data?.cause_analysis
    ? `Analizado${data.cause_analysis.analyzed_at ? ` ${formatDateTime(data.cause_analysis.analyzed_at)}` : ""}${data.cause_analysis.analyzed_by?.full_name ? ` por ${data.cause_analysis.analyzed_by.full_name}` : ""}`
    : data?.current_stage === "cause_analysis"
      ? "En curso"
      : "No registrado";

  const normalizeAttachmentUrl = (fileUrl: string) => {
    if (!fileUrl) {
      return "#";
    }

    const trimmed = fileUrl.trim();
    if (!trimmed) {
      return "#";
    }

    if (trimmed.startsWith("/")) {
      return trimmed;
    }

    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
      try {
        const parsed = new URL(trimmed);
        const hostname = parsed.hostname.toLowerCase();
        const isLoopbackHost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
        const mediaPath = `${parsed.pathname}${parsed.search}${parsed.hash}`;

        if (isLoopbackHost || parsed.pathname.startsWith("/media/") || parsed.pathname.startsWith("/api/")) {
          return mediaPath;
        }

        return parsed.toString();
      } catch {
        return trimmed;
      }
    }

    return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  };

  const extractFilename = (contentDisposition: string | null, fallback = "evidencia") => {
    if (!contentDisposition) {
      return fallback;
    }

    const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
      try {
        return decodeURIComponent(utf8Match[1]);
      } catch {
        return utf8Match[1];
      }
    }

    const regularMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
    if (regularMatch?.[1]) {
      return regularMatch[1];
    }

    return fallback;
  };

  const handleOpenTreatment = (treatmentId?: string | null) => {
    if (!treatmentId) {
      return;
    }
    navigate(`/treatments?treatment=${encodeURIComponent(treatmentId)}`);
  };

  const handleOpenAttachment = async (event: MouseEvent<HTMLAnchorElement>, rawFileUrl: string) => {
    event.preventDefault();

    const fileUrl = normalizeAttachmentUrl(rawFileUrl);
    if (!fileUrl || fileUrl === "#") {
      setAttachmentError("La evidencia no tiene una URL valida.");
      return;
    }

    setAttachmentError(null);

    const session = readStoredSession();
    if (!session?.access) {
      setAttachmentError("Tu sesion vencio. Inicia sesion nuevamente para abrir evidencias.");
      return;
    }

    try {
      const response = await fetch(fileUrl, {
        method: "GET",
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${session.access}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Error HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const contentType = (response.headers.get("content-type") || blob.type || "").toLowerCase();
      const canPreview = contentType.startsWith("image/") || contentType.includes("pdf") || contentType.startsWith("text/");

      if (canPreview) {
        window.open(blobUrl, "_blank", "noopener,noreferrer");
      } else {
        const tempLink = document.createElement("a");
        tempLink.href = blobUrl;
        tempLink.download = extractFilename(response.headers.get("content-disposition"));
        document.body.appendChild(tempLink);
        tempLink.click();
        tempLink.remove();
      }

      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch {
      setAttachmentError("No se pudo abrir la evidencia. Verifica que tu sesion siga activa e intenta nuevamente.");
    }
  };

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
                {data.action_plans.length ? (
                  <div className="nested-card">
                    <div className="section-head compact">
                      <div>
                        <strong>Planes de accion</strong>
                        <p>Planes historicos asociados directamente a la anomalia.</p>
                      </div>
                    </div>
                    <div className="stack-list compact">
                      {data.action_plans.map((plan) => (
                        <div className="list-card compact" key={plan.id}>
                          <div>
                            <strong>Plan {plan.id.slice(0, 8)}</strong>
                            <p>Responsable: {plan.owner?.full_name || "Sin responsable"}</p>
                            <small>Aprobado: {formatDateTime(plan.approved_at)}</small>
                          </div>
                          <div className="badge-stack align-end">
                            <StatusBadge value={plan.status} compact />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {data.treatment_tasks.length ? (
                  <div className="nested-card">
                    <div className="section-head compact">
                      <div>
                        <strong>Acciones asignadas</strong>
                        <p>Tareas de tratamientos vinculados a esta anomalia.</p>
                      </div>
                    </div>
                    <div className="stack-list compact">
                      {data.treatment_tasks.map((task) => (
                        <div className="list-card compact" key={task.id}>
                          <div>
                            <strong>{task.title}</strong>
                            <p>{task.description || "Sin descripcion"}</p>
                            <small>
                              Tratamiento: {task.treatment?.code || "Sin tratamiento"}
                              {" - "}
                              Responsable: {task.responsible?.full_name || "Sin asignar"}
                              {" - "}
                              Compromiso: {formatDate(task.execution_date)}
                            </small>
                            {task.root_cause_description ? <small>Causa raiz: {task.root_cause_description}</small> : null}
                          </div>
                          <div className="badge-stack align-end">
                            <StatusBadge value={task.status} compact />
                            {task.is_overdue ? <StatusBadge value="overdue" compact /> : null}
                            {task.treatment?.id ? (
                              <button
                                className="button button-secondary"
                                onClick={() => handleOpenTreatment(task.treatment?.id)}
                                type="button"
                              >
                                Ver tratamiento
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {!data.action_plans.length && !data.treatment_tasks.length ? (
                  <p className="muted-copy">Esta anomalia todavia no tiene planes ni acciones asociadas.</p>
                ) : null}
              </div>
            </article>

            <article className="panel">
              <div className="section-head"><h2>Participacion y verificaciones</h2></div>
              <dl className="key-grid">
                <div><dt>Verificacion inicial</dt><dd>{initialVerificationLabel}</dd></div>
                <div><dt>Clasificacion</dt><dd>{classificationLabel}</dd></div>
                <div><dt>Tratamiento creado</dt><dd>{treatmentCreatedLabel}</dd></div>
                <div><dt>Analisis de causa</dt><dd>{causeAnalysisLabel}</dd></div>
                <div><dt>Eficacia</dt><dd>{data.effectiveness_summary || "Sin verificacion de eficacia"}</dd></div>
                <div><dt>Aprendizaje</dt><dd>{data.learning?.lessons_learned || "Sin aprendizaje registrado"}</dd></div>
                <div><dt>Participantes</dt><dd>{data.participants.length ? data.participants.map((item) => item.user?.full_name || item.role).join(", ") : "Sin participantes"}</dd></div>
              </dl>
            </article>

            <article className="panel">
              <div className="section-head"><h2>Evidencias cargadas</h2></div>
              {attachmentError ? <div className="panel danger">{attachmentError}</div> : null}
              <div className="stack-list compact">
                {data.attachments.length ? data.attachments.map((attachment) => (
                  <div className="list-card compact" key={attachment.id}>
                    <div>
                      <a
                        className="text-link"
                        href={normalizeAttachmentUrl(attachment.file_url)}
                        onClick={(event) => void handleOpenAttachment(event, attachment.file_url)}
                        rel="noopener noreferrer"
                        target="_blank"
                      >
                        {attachment.original_name}
                      </a>
                      <p>{attachment.content_type}</p>
                      <small>
                        Cargado {formatDateTime(attachment.created_at)}
                        {attachment.uploaded_by?.full_name ? ` por ${attachment.uploaded_by.full_name}` : ""}
                      </small>
                    </div>
                  </div>
                )) : <p className="muted-copy">No hay evidencias cargadas en esta anomalia.</p>}
              </div>
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