import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createAnomaly } from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import type { CatalogBootstrap } from "../../../api/types";
import { toOffsetIso } from "../../../app/utils";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

const CREATED_ANOMALY_KEY = "calidad-platform.last-created-anomaly";

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
  const [form, setForm] = useState({
    title: "",
    description: "",
    site: "",
    area: "",
    anomaly_type: "",
    anomaly_origin: "",
    priority: "",
    manufacturing_order_number: "",
    affected_quantity: "",
    affected_process: "",
    origin_process: "",
    detected_at: nowAsLocalDateTime(),
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!bootstrap) {
      return;
    }
    setForm((current) => ({
      ...current,
      site: current.site || bootstrap.sites[0]?.id || "",
      anomaly_type: current.anomaly_type || bootstrap.anomalyTypes[0]?.id || "",
      anomaly_origin: current.anomaly_origin || bootstrap.anomalyOrigins[0]?.id || "",
      priority: current.priority || bootstrap.priorities[0]?.id || "",
    }));
  }, [bootstrap]);

  const availableAreas = useMemo(() => {
    if (!bootstrap) {
      return [];
    }
    return bootstrap.areas.filter((area) => !form.site || area.site?.id === form.site);
  }, [bootstrap, form.site]);

  useEffect(() => {
    if (!availableAreas.length) {
      return;
    }
    setForm((current) => {
      const nextArea = availableAreas.some((area) => area.id === current.area) ? current.area : availableAreas[0]?.id || "";
      if (nextArea === current.area) {
        return current;
      }
      return { ...current, area: nextArea };
    });
  }, [availableAreas]);

  useEffect(() => {
    if (!availableAreas.length) {
      return;
    }
    setForm((current) => {
      const processNames = availableAreas.map((item) => item.name);
      const nextAffectedProcess = processNames.includes(current.affected_process)
        ? current.affected_process
        : processNames[0] || "";
      const nextOriginProcess = processNames.includes(current.origin_process)
        ? current.origin_process
        : processNames[0] || "";

      if (nextAffectedProcess === current.affected_process && nextOriginProcess === current.origin_process) {
        return current;
      }

      return {
        ...current,
        affected_process: nextAffectedProcess,
        origin_process: nextOriginProcess,
      };
    });
  }, [availableAreas]);

  const catalogsReady = Boolean(
    bootstrap &&
      bootstrap.sites.length &&
      bootstrap.areas.length &&
      bootstrap.anomalyTypes.length &&
      bootstrap.anomalyOrigins.length &&
      bootstrap.priorities.length,
  );

  const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
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
        anomaly_type: form.anomaly_type,
        anomaly_origin: form.anomaly_origin,
        priority: form.priority,
        detected_at: toOffsetIso(form.detected_at),
        manufacturing_order_number: form.manufacturing_order_number.trim() || undefined,
        affected_quantity: form.affected_quantity ? Number(form.affected_quantity) : undefined,
        affected_process: form.affected_process.trim() || undefined,
      });
      window.sessionStorage.setItem(CREATED_ANOMALY_KEY, JSON.stringify(response));
      navigate("/anomalies/created", { state: { anomaly: response } });
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
          <strong>{`${new Date().getFullYear()}0001`}</strong>
          <p>Se genera automaticamente con el anio actual y correlativo interno.</p>
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
          <p>Carga `catalog.bootstrap.json` con sitios, procesos, tipos, origenes y prioridades para habilitar el alta.</p>
        </div>
      ) : null}

      <form className="panel form-grid anomaly-form" onSubmit={handleSubmit}>
        <section className="form-section field-span-2">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Paso 1</p>
              <h2>Datos del evento</h2>
            </div>
            <span className="status-badge info compact">Carga inicial</span>
          </div>

          <div className="form-grid compact-form-grid">
            <label className="field field-span-2">
              <span>Titulo breve</span>
              <input
                autoFocus
                name="title"
                onChange={handleChange}
                placeholder="Ej. Rayado en pieza final"
                required
                type="text"
                value={form.title}
              />
            </label>
            <label className="field field-span-2">
              <span>Descripcion detallada</span>
              <textarea
                name="description"
                onChange={handleChange}
                placeholder="Describi lo observado, donde ocurrio y cualquier dato util para analizar despues."
                required
                rows={5}
                value={form.description}
              />
            </label>
            <label className="field">
              <span>Fecha y hora</span>
              <input name="detected_at" onChange={handleChange} required type="datetime-local" value={form.detected_at} />
            </label>
            <label className="field">
              <span>Proceso afectado</span>
              <select disabled={!catalogsReady} name="affected_process" onChange={handleChange} value={form.affected_process}>
                <option value="">Seleccionar</option>
                {availableAreas.map((item) => (
                  <option key={`affected-process-${item.id}`} value={item.name}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Numero de OF</span>
              <input name="manufacturing_order_number" onChange={handleChange} placeholder="Ej. 212EDFC" type="text" value={form.manufacturing_order_number} />
            </label>
            <label className="field">
              <span>Cantidad de piezas afectadas</span>
              <input inputMode="numeric" min="1" name="affected_quantity" onChange={handleChange} placeholder="Ej. 12" type="number" value={form.affected_quantity} />
            </label>
          </div>
        </section>

        <section className="form-section field-span-2">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Paso 2</p>
              <h2>Contexto operativo</h2>
            </div>
            <span className="status-badge accent compact">Obligatorio</span>
          </div>

          <div className="form-grid compact-form-grid">
            <label className="field">
              <span>Sitio</span>
              <select disabled={!catalogsReady} name="site" onChange={handleChange} required value={form.site}>
                <option value="">Seleccionar</option>
                {bootstrap?.sites.map((item) => (
                  <option key={item.id} value={item.id}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Proceso</span>
              <select disabled={!catalogsReady} name="area" onChange={handleChange} required value={form.area}>
                <option value="">Seleccionar</option>
                {availableAreas.map((item) => (
                  <option key={item.id} value={item.id}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Tipo de anomalia</span>
              <select disabled={!catalogsReady} name="anomaly_type" onChange={handleChange} required value={form.anomaly_type}>
                <option value="">Seleccionar</option>
                {bootstrap?.anomalyTypes.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Origen</span>
              <select disabled={!catalogsReady} name="origin_process" onChange={handleChange} required value={form.origin_process}>
                <option value="">Seleccionar</option>
                {availableAreas.map((item) => (
                  <option key={`origin-process-${item.id}`} value={item.name}>{`${item.code} - ${item.name}`}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Prioridad</span>
              <select disabled={!catalogsReady} name="priority" onChange={handleChange} required value={form.priority}>
                <option value="">Seleccionar</option>
                {bootstrap?.priorities.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
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
            <button className="button button-primary button-large" disabled={submitting || !catalogsReady} type="submit">
              {submitting ? "Registrando..." : "Registrar anomalia"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}
