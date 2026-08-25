import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createAnomaly, reserveAnomalyCode, uploadAnomalyAttachment } from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import type { AnomalyCodeReservation, CatalogBootstrap } from "../../../api/types";
import { toOffsetIso } from "../../../app/utils";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

const CREATED_ANOMALY_KEY = "calidad-platform.last-created-anomaly";
const EVIDENCE_ACCEPT =
  "image/*,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf,.odt,.ods,.zip";

function nowAsLocalDateTime() {
  const date = new Date();
  date.setSeconds(0, 0);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hh}:${mm}`;
}

export function NewAnomalyPage() {
  usePageTitle("Nueva anomalia");
  const navigate = useNavigate();
  const { data: bootstrap, loading, error, reload } = useAsyncTask<CatalogBootstrap>(fetchCatalogBootstrap, []);
  const {
    data: codeReservation,
    loading: codeReservationLoading,
    error: codeReservationError,
    reload: reloadCodeReservation,
  } = useAsyncTask<AnomalyCodeReservation>(reserveAnomalyCode, []);
  const [form, setForm] = useState({
    title: "",
    description: "",
    site: "",
    area: "",
    imputed_area: "",
    anomaly_type: "",
    anomaly_origin: "",
    priority: "",
    manufacturing_order_number: "",
    affected_quantity: "",
    detected_at: nowAsLocalDateTime(),
  });
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!bootstrap) {
      return;
    }
    setForm((current) => ({
      ...current,
      site: current.site || bootstrap.sites[0]?.id || "",
      imputed_area: current.imputed_area || bootstrap.areas[0]?.id || "",
      anomaly_type: current.anomaly_type || bootstrap.anomalyTypes[0]?.id || "",
      anomaly_origin: current.anomaly_origin || bootstrap.anomalyOrigins[0]?.id || "",
      priority: current.priority || bootstrap.priorities[0]?.id || "",
    }));
  }, [bootstrap]);

  const availableAreas = useMemo(() => {
    if (!bootstrap) {
      return [];
    }
    return bootstrap.areas;
  }, [bootstrap]);

  useEffect(() => {
    if (!availableAreas.length) {
      return;
    }
    setForm((current) => {
      const nextArea = availableAreas.some((area) => area.id === current.area) ? current.area : availableAreas[0]?.id || "";
      const selectedArea = availableAreas.find((area) => area.id === nextArea);
      if (nextArea === current.area) {
        const nextSite = selectedArea?.site?.id || current.site;
        return nextSite === current.site ? current : { ...current, site: nextSite };
      }
      return { ...current, area: nextArea, site: selectedArea?.site?.id || current.site };
    });
  }, [availableAreas]);

  const catalogsReady = Boolean(
    bootstrap &&
      bootstrap.sites.length &&
      bootstrap.areas.length &&
      bootstrap.anomalyTypes.length &&
      bootstrap.anomalyOrigins.length,
  );

  const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
    setForm((current) => {
      if (name === "area") {
        const selectedArea = availableAreas.find((item) => item.id === value);
        return {
          ...current,
          area: value,
          site: selectedArea?.site?.id || current.site,
        };
      }
      return { ...current, [name]: value };
    });
  };

  const handleEvidenceChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) {
      return;
    }
    setEvidenceFiles((current) => {
      const byKey = new Map(current.map((file) => [`${file.name}-${file.size}-${file.lastModified}`, file]));
      for (const file of files) {
        byKey.set(`${file.name}-${file.size}-${file.lastModified}`, file);
      }
      return Array.from(byKey.values());
    });
    event.target.value = "";
  };

  const handleRemoveEvidence = (index: number) => {
    setEvidenceFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
  };

  const handleClearEvidence = () => {
    setEvidenceFiles([]);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await createAnomaly({
        title: form.title,
        description: form.description,
        site: form.site,
        area: form.area,
        imputed_area: form.imputed_area || undefined,
        anomaly_type: form.anomaly_type,
        anomaly_origin: form.anomaly_origin,
        priority: form.priority || undefined,
        detected_at: toOffsetIso(form.detected_at),
        manufacturing_order_number: form.manufacturing_order_number.trim() || undefined,
        affected_quantity: form.affected_quantity ? Number(form.affected_quantity) : undefined,
        code_reservation_id: codeReservation?.id,
      });

      let attachmentWarning: string | null = null;
      if (evidenceFiles.length) {
        try {
          await Promise.all(
            evidenceFiles.map((file) =>
              uploadAnomalyAttachment(response.id, {
                file,
                originalName: file.name,
              }),
            ),
          );
        } catch (attachmentError) {
          attachmentWarning =
            attachmentError instanceof Error
              ? `La anomalia se registro, pero fallo la carga de evidencias: ${attachmentError.message}`
              : "La anomalia se registro, pero fallo la carga de evidencias.";
        }
      }

      window.sessionStorage.setItem(CREATED_ANOMALY_KEY, JSON.stringify(response));
      navigate("/anomalies/created", { state: { anomaly: response, attachmentWarning } });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo registrar la anomalia.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="page-shell page-shell-form">
      <header className="form-hero">
        <div>
          <p className="eyebrow">Registro de planta</p>
          <h1>Nueva anomalia</h1>
          <p className="page-description">Carga rapida para tablet y puesto operativo. El backend asigna codigo, estado inicial y trazabilidad.</p>
        </div>
        <div className="form-hero-card">
          <span className="stat-label">Codigo visible</span>
          <strong>{codeReservationLoading ? "Reservando..." : codeReservation?.code || "Sin reserva"}</strong>
          <p>
            {codeReservation
              ? "Codigo reservado para esta carga. No se comparte con otros usuarios mientras completas el registro."
              : "No se pudo reservar el codigo automaticamente. Reintenta para continuar."}
          </p>
        </div>
      </header>

      {error ? (
        <div className="panel warning">
          <strong>No se pudo leer el bootstrap de catalogos.</strong>
          <p>Hoy el backend no expone catalogos por API. Este formulario usa `public/catalog.bootstrap.json` como fuente de opciones.</p>
          <button className="button button-secondary" onClick={() => void reload()} type="button">
            Reintentar
          </button>
        </div>
      ) : null}

      {!loading && !catalogsReady ? (
        <div className="panel warning">
          <strong>Catalogos incompletos.</strong>
          <p>Carga `catalog.bootstrap.json` con sitios, sectores, tipos e imputaciones para habilitar el alta.</p>
        </div>
      ) : null}

      {codeReservationError ? (
        <div className="panel warning">
          <strong>No se pudo reservar el codigo visible.</strong>
          <p>{codeReservationError}</p>
          <button className="button button-secondary" onClick={() => void reloadCodeReservation()} type="button">
            Reintentar reserva
          </button>
        </div>
      ) : null}

      <form className="panel form-grid anomaly-form anomaly-form-compact" onSubmit={handleSubmit}>
        <section className="form-section field-span-2">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Paso 1</p>
              <h2>Datos de inicio</h2>
            </div>
            <span className="status-badge info compact">Carga inicial</span>
          </div>

          <div className="form-grid compact-form-grid">
            <label className="field">
              <span>Elaborado por:</span>
              <select autoFocus disabled={!catalogsReady} name="area" onChange={handleChange} required value={form.area}>
                <option value="">Seleccionar</option>
                {availableAreas.map((item) => (
                  <option key={`affected-area-${item.id}`} value={item.id}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Fecha y hora</span>
              <input name="detected_at" onChange={handleChange} required type="datetime-local" value={form.detected_at} />
            </label>
            <label className="field">
              <span>Asignado a</span>
              <select disabled={!catalogsReady} name="imputed_area" onChange={handleChange} required value={form.imputed_area}>
                <option value="">Seleccionar</option>
                {availableAreas.map((item) => (
                  <option key={`imputed-area-${item.id}`} value={item.id}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Tipo de desvio</span>
              <select disabled={!catalogsReady} name="anomaly_type" onChange={handleChange} required value={form.anomaly_type}>
                <option value="">Seleccionar</option>
                {bootstrap?.anomalyTypes.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
          </div>
        </section>

        <section className="form-section field-span-2">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Paso 2</p>
              <h2>Contexto</h2>
            </div>
            <span className="status-badge accent compact">Obligatorio</span>
          </div>

          <div className="form-grid compact-form-grid">
            <label className="field field-span-2">
              <span>Titulo</span>
              <input
                name="title"
                onChange={handleChange}
                placeholder="Ej. Rayado en pieza final"
                required
                type="text"
                value={form.title}
              />
            </label>
            <label className="field field-span-2">
              <span>Observacion</span>
              <textarea
                name="description"
                onChange={handleChange}
                placeholder="Describi lo observado, donde ocurrio y cualquier dato util para analizar despues."
                required
                rows={3}
                value={form.description}
              />
            </label>
            <label className="field field-span-2">
              <span>Evidencia objetiva</span>
              <input accept={EVIDENCE_ACCEPT} multiple onChange={handleEvidenceChange} type="file" />
              <small className="muted-copy">
                {evidenceFiles.length
                  ? `${evidenceFiles.length} archivo(s) listo(s) para adjuntar. Podes seleccionar mas de una vez para acumular archivos.`
                  : "Opcional: imagenes, PDF, Word, Excel o texto."}
              </small>
              {evidenceFiles.length ? (
                <div className="stack-list compact">
                  {evidenceFiles.map((file, index) => (
                    <div className="list-card compact" key={`${file.name}-${file.size}-${file.lastModified}`}>
                      <div>
                        <strong>{file.name}</strong>
                        <small>{`${Math.max(1, Math.round(file.size / 1024))} KB`}</small>
                      </div>
                      <button className="button button-ghost" onClick={() => handleRemoveEvidence(index)} type="button">
                        Quitar
                      </button>
                    </div>
                  ))}
                  <button className="button button-secondary" onClick={handleClearEvidence} type="button">
                    Quitar todo
                  </button>
                </div>
              ) : null}
            </label>
          </div>
        </section>

        {submitError ? <div className="panel danger field-span-2">{submitError}</div> : null}

        <div className="field-span-2 submit-bar">
          <div className="submit-bar-copy">
            <strong>Registrar anomalia</strong>
            <span>Se guardara con codigo, estado inicial y confirmacion inmediata.</span>
          </div>
          <div className="form-actions">
            <button className="button button-primary button-large" disabled={submitting || !catalogsReady || codeReservationLoading || !codeReservation} type="submit">
              {submitting ? "Registrando..." : "Registrar anomalia"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}

