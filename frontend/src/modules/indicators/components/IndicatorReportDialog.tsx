import { useEffect, useMemo, useState } from "react";
import { createIndicatorReport, fetchIndicatorReport, fetchIndicatorReportRecipients, type IndicatorDashboardFilters } from "../../../api/indicators";
import type { IndicatorReportResponse } from "../../../api/types";
import { useAsyncTask } from "../../../hooks/useAsyncTask";


export function IndicatorReportDialog({
  indicatorKey,
  filters,
  onClose,
}: {
  indicatorKey: string;
  filters: IndicatorDashboardFilters;
  onClose: () => void;
}) {
  const { data: recipients, loading, error, reload } = useAsyncTask(fetchIndicatorReportRecipients, []);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [report, setReport] = useState<IndicatorReportResponse | null>(null);
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es");
    if (!term) return recipients ?? [];
    return (recipients ?? []).filter((item) => `${item.name} ${item.email}`.toLocaleLowerCase("es").includes(term));
  }, [recipients, search]);
  const selectedRecipients = (recipients ?? []).filter((item) => selected.includes(item.id));

  useEffect(() => {
    if (!report || !["queued", "pending"].includes(report.status)) return;
    const timer = window.setTimeout(() => {
      fetchIndicatorReport(report.id).then(setReport).catch(() => undefined);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [report]);

  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const submit = async () => {
    setSending(true);
    setSendError("");
    try {
      setReport(await createIndicatorReport(indicatorKey, filters, selected));
      setConfirming(false);
    } catch (reason) {
      setSendError(reason instanceof Error ? reason.message : "No se pudo generar el informe.");
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="indicator-report-overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-modal="true" className="panel indicator-report-dialog" role="dialog" aria-labelledby="indicator-report-title">
        <div className="section-head compact">
          <div><p className="eyebrow">Informe PDF</p><h2 id="indicator-report-title">Enviar indicador por correo</h2></div>
          <button className="button button-secondary" onClick={onClose} type="button">Cerrar</button>
        </div>

        {report ? (
          <div className="indicator-report-result">
            <strong>{report.status === "completed" ? "Informe entregado" : report.status === "failed" ? "El envío finalizó con errores" : "Informe generado y encolado"}</strong>
            <p>{`${report.recipients.length} destinatario(s) · ${report.row_count} registro(s).`}</p>
            <ul className="indicator-delivery-list">
              {report.recipients.map((item) => <li key={item.id}>{`${item.name}: ${item.delivery_status ?? "pending"}${item.delivery_error ? ` · ${item.delivery_error}` : ""}`}</li>)}
            </ul>
            <p className="muted-copy">El generador recibe una copia si tiene habilitadas las notificaciones por correo. El PDF se elimina del servidor al completar todos los envíos.</p>
          </div>
        ) : confirming ? (
          <div className="indicator-report-confirmation">
            <strong>{`¿Confirma el envío a ${selectedRecipients.length} usuario(s)?`}</strong>
            <ul>{selectedRecipients.map((item) => <li key={item.id}>{`${item.name} · ${item.email}`}</li>)}</ul>
            <p className="muted-copy">Se utilizarán el período y los filtros actualmente visibles. El generador recibirá una copia si tiene habilitado el correo. No se incluirán enlaces de sesión.</p>
            {sendError ? <p className="form-error">{sendError}</p> : null}
            <div className="form-actions">
              <button className="button button-primary" disabled={sending} onClick={submit} type="button">{sending ? "Generando..." : "Confirmar y encolar"}</button>
              <button className="button button-secondary" disabled={sending} onClick={() => setConfirming(false)} type="button">Volver</button>
            </div>
          </div>
        ) : (
          <>
            <label className="field"><span>Buscar usuario</span><input autoFocus onChange={(event) => setSearch(event.target.value)} placeholder="Nombre o correo" value={search} /></label>
            {loading ? <p className="muted-copy">Cargando destinatarios habilitados...</p> : null}
            {error ? <div><p className="form-error">{error}</p><button className="button button-secondary" onClick={reload} type="button">Reintentar</button></div> : null}
            {!loading && !error && !(recipients?.length) ? <p className="muted-copy">No hay usuarios activos con Notificación por correo habilitada.</p> : null}
            <div className="indicator-recipient-list">
              {filtered.map((item) => (
                <label className="indicator-recipient-row" key={item.id}>
                  <input checked={selected.includes(item.id)} onChange={() => toggle(item.id)} type="checkbox" />
                  <span><strong>{item.name}</strong><small>{item.email}</small></span>
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button className="button button-primary" disabled={!selected.length} onClick={() => setConfirming(true)} type="button">{`Continuar (${selected.length})`}</button>
            </div>
          </>
        )}
        {sendError && report ? <p className="form-error">{sendError}</p> : null}
      </section>
    </div>
  );
}
