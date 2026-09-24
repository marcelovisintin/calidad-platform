import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createAnomaly, uploadAnomalyAttachment } from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import type { AffectedOrderInput, CatalogBootstrap } from "../../../api/types";
import { newAnomalyDraftKey } from "../../../app/sessionDrafts";
import { useAuth } from "../../../app/providers/AuthProvider";
import { toOffsetIso } from "../../../app/utils";
import { SearchableSelect } from "../../../components/SearchableSelect";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

const CREATED_ANOMALY_KEY = "calidad-platform.last-created-anomaly";
const EVIDENCE_ACCEPT =
  "image/*,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf,.odt,.ods,.zip";

type AffectedOrderFormRow = {
  id: string;
  order_type: string;
  number: string;
  quantity: string;
};

type NewAnomalyFormState = {
  title: string;
  description: string;
  site: string;
  area: string;
  imputed_area: string;
  anomaly_type: string;
  anomaly_origin: string;
  priority: string;
  detected_at: string;
};

type NewAnomalyDraft = {
  form: NewAnomalyFormState;
  affectedOrders: AffectedOrderFormRow[];
};

type SelectedEvidenceFileProps = {
  file: File;
  index: number;
  onRemove: (index: number) => void;
};

function SelectedEvidenceFile({ file, index, onRemove }: SelectedEvidenceFileProps) {
  const previewUrl = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => () => URL.revokeObjectURL(previewUrl), [previewUrl]);

  return (
    <div className="list-card compact evidence-file-row">
      <a className="evidence-file-link" href={previewUrl} rel="noreferrer" target="_blank">
        <strong>{file.name}</strong>
        <small>{`${Math.max(1, Math.round(file.size / 1024))} KB`}</small>
      </a>
      <button className="button button-ghost" onClick={() => onRemove(index)} type="button">
        Quitar
      </button>
    </div>
  );
}

function createAffectedOrderRow(): AffectedOrderFormRow {
  return {
    id: typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `order-${Date.now()}-${Math.random()}`,
    order_type: "",
    number: "",
    quantity: "",
  };
}

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

function createInitialForm(bootstrap?: CatalogBootstrap | null): NewAnomalyFormState {
  return {
    title: "",
    description: "",
    site: "",
    area: "",
    imputed_area: "",
    anomaly_type: "",
    anomaly_origin: bootstrap?.anomalyOrigins[0]?.id || "",
    priority: bootstrap?.priorities[0]?.id || "",
    detected_at: nowAsLocalDateTime(),
  };
}

function readNewAnomalyDraft(userId: string): NewAnomalyDraft | null {
  try {
    const raw = window.sessionStorage.getItem(newAnomalyDraftKey(userId));
    if (!raw) {
      return null;
    }
    const candidate = JSON.parse(raw) as Partial<NewAnomalyDraft>;
    const form = candidate.form;
    const affectedOrders = candidate.affectedOrders;
    if (
      !form
      || Object.values(form).some((value) => typeof value !== "string")
      || !Array.isArray(affectedOrders)
      || affectedOrders.some((row) =>
        !row
        || typeof row.id !== "string"
        || typeof row.order_type !== "string"
        || typeof row.number !== "string"
        || typeof row.quantity !== "string"
      )
    ) {
      window.sessionStorage.removeItem(newAnomalyDraftKey(userId));
      return null;
    }
    return { form: form as NewAnomalyFormState, affectedOrders };
  } catch {
    window.sessionStorage.removeItem(newAnomalyDraftKey(userId));
    return null;
  }
}

export function NewAnomalyPage() {
  usePageTitle("Nueva anomalia");
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: bootstrap, loading, error, reload } = useAsyncTask<CatalogBootstrap>(fetchCatalogBootstrap, []);
  const initialDraft = useMemo(() => (user ? readNewAnomalyDraft(user.id) : null), [user?.id]);
  const [form, setForm] = useState<NewAnomalyFormState>(() => initialDraft?.form ?? createInitialForm());
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
  const [affectedOrders, setAffectedOrders] = useState<AffectedOrderFormRow[]>(
    () => initialDraft?.affectedOrders.length ? initialDraft.affectedOrders : [createAffectedOrderRow()],
  );
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    const draft: NewAnomalyDraft = { form, affectedOrders };
    window.sessionStorage.setItem(newAnomalyDraftKey(user.id), JSON.stringify(draft));
  }, [affectedOrders, form, user?.id]);

  useEffect(() => {
    if (!bootstrap) {
      return;
    }
    setForm((current) => ({
      ...current,
      imputed_area: bootstrap.areas.some((area) => area.id === current.imputed_area) ? current.imputed_area : "",
      anomaly_type: bootstrap.anomalyTypes.some((type) => type.id === current.anomaly_type) ? current.anomaly_type : "",
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
      if (!current.area) {
        return current.site ? { ...current, site: "" } : current;
      }
      const selectedArea = availableAreas.find((area) => area.id === current.area);
      if (!selectedArea) {
        return { ...current, area: "", site: "" };
      }
      const nextSite = selectedArea.site?.id || "";
      return nextSite === current.site ? current : { ...current, site: nextSite };
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
    handleFieldValueChange(name as keyof NewAnomalyFormState, value);
  };

  const handleFieldValueChange = (name: keyof NewAnomalyFormState, value: string) => {
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

  const handleDiscardDraft = () => {
    if (!window.confirm("Se eliminaran los datos y archivos cargados en este formulario.")) {
      return;
    }
    if (user) {
      window.sessionStorage.removeItem(newAnomalyDraftKey(user.id));
    }
    setForm(createInitialForm(bootstrap));
    setAffectedOrders([createAffectedOrderRow()]);
    setEvidenceFiles([]);
    setSubmitError(null);
  };

  const handleAffectedOrderChange = (rowId: string, field: "order_type" | "number" | "quantity", value: string) => {
    setAffectedOrders((current) => current.map((row) => (row.id === rowId ? { ...row, [field]: value } : row)));
  };

  const handleAddAffectedOrder = () => {
    setAffectedOrders((current) => [...current, createAffectedOrderRow()]);
  };

  const handleRemoveAffectedOrder = (rowId: string) => {
    setAffectedOrders((current) => {
      const next = current.filter((row) => row.id !== rowId);
      return next.length ? next : [createAffectedOrderRow()];
    });
  };

  const buildAffectedOrdersPayload = (): AffectedOrderInput[] => {
    const activeRows = affectedOrders.filter((row) => row.order_type || row.number.trim() || row.quantity);
    const seen = new Set<string>();
    return activeRows.map((row, index) => {
      if (!row.order_type || !row.number.trim() || !row.quantity) {
        throw new Error(`Completa tipo, numero y cantidad en la orden afectada ${index + 1}.`);
      }
      const quantity = Number(row.quantity);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        throw new Error(`La cantidad de la orden afectada ${index + 1} debe ser un numero entero mayor que cero.`);
      }
      const key = `${row.order_type}:${row.number.trim().toLocaleLowerCase()}`;
      if (seen.has(key)) {
        throw new Error(`La orden afectada ${index + 1} esta repetida.`);
      }
      seen.add(key);
      return { order_type: row.order_type, number: row.number.trim(), quantity };
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const missingSelection = [
      [form.area, "Elaborado por"],
      [form.imputed_area, "Asignado a"],
      [form.anomaly_type, "Tipo de desvio"],
    ].find(([value]) => !value);
    if (missingSelection) {
      setSubmitError(`Debe seleccionar una opcion en ${missingSelection[1]}.`);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const affectedOrdersPayload = buildAffectedOrdersPayload();
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
        affected_orders: affectedOrdersPayload,
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

      if (user) {
        window.sessionStorage.removeItem(newAnomalyDraftKey(user.id));
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
          <strong>Se asignara al registrar</strong>
          <p>Podes completar la carga sin limite de tiempo. Los campos quedan guardados en esta pestaña mientras la sesion este abierta.</p>
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

      <form className="panel form-grid anomaly-form anomaly-form-compact" onSubmit={handleSubmit}>
        <section className="form-section field-span-2">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Paso 1</p>
              <h2>Datos de inicio</h2>
            </div>
            <span className="status-badge accent compact">Obligatorio</span>
          </div>

          <div className="form-grid compact-form-grid">
            <SearchableSelect
              autoFocus
              className="field"
              disabled={!catalogsReady}
              dataTour="anomaly-area"
              label="Elaborado por:"
              onChange={(value) => handleFieldValueChange("area", value)}
              options={availableAreas.map((item) => ({ value: item.id, label: `${item.code} - ${item.name}`, searchTerms: [item.code, item.name] }))}
              required
              value={form.area}
            />
            <label className="field">
              <span>Fecha y hora</span>
              <input name="detected_at" onChange={handleChange} required type="datetime-local" value={form.detected_at} />
            </label>
            <SearchableSelect
              className="field"
              disabled={!catalogsReady}
              dataTour="anomaly-imputed-area"
              label="Asignado a"
              onChange={(value) => handleFieldValueChange("imputed_area", value)}
              options={availableAreas.map((item) => ({ value: item.id, label: `${item.code} - ${item.name}`, searchTerms: [item.code, item.name] }))}
              required
              value={form.imputed_area}
            />
            <SearchableSelect
              className="field"
              disabled={!catalogsReady}
              dataTour="anomaly-type"
              label="Tipo de desvio"
              onChange={(value) => handleFieldValueChange("anomaly_type", value)}
              options={(bootstrap?.anomalyTypes ?? []).map((item) => ({ value: item.id, label: item.name }))}
              required
              value={form.anomaly_type}
            />
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
            <div className="field field-span-2 affected-orders-editor">
              <div className="section-head compact">
                <div>
                  <span>Ordenes afectadas</span>
                  <small className="muted-copy">Opcional. Agrega una o varias ordenes relacionadas con la anomalia.</small>
                </div>
                <button className="button button-secondary" onClick={handleAddAffectedOrder} type="button">
                  Agregar otra orden
                </button>
              </div>
              <div className="affected-orders-form-list">
                {affectedOrders.map((row, index) => {
                  const selectedType = bootstrap?.orderTypes.find((item) => item.id === row.order_type);
                  const rowActive = Boolean(row.order_type || row.number.trim() || row.quantity);
                  return (
                    <div className="affected-order-form-row" key={row.id}>
                      <SearchableSelect
                        ariaLabel={`Tipo de orden ${index + 1}`}
                        className="field"
                        disabled={!bootstrap?.orderTypes.length}
                        label="Tipo de orden"
                        onChange={(value) => handleAffectedOrderChange(row.id, "order_type", value)}
                        options={(bootstrap?.orderTypes ?? []).map((item) => ({ value: item.id, label: `${item.code} - ${item.name}`, searchTerms: [item.code, item.name] }))}
                        placeholder="No aplica / Sin orden"
                        required={rowActive}
                        value={row.order_type}
                      />
                      <label className="field">
                        <span>{selectedType ? `Nro. de ${selectedType.code}` : "Nro. de orden"}</span>
                        <input
                          maxLength={50}
                          onChange={(event) => handleAffectedOrderChange(row.id, "number", event.target.value)}
                          placeholder="Ej. 000123"
                          required={rowActive}
                          type="text"
                          value={row.number}
                        />
                      </label>
                      <label className="field">
                        <span>Cantidad de piezas/productos</span>
                        <input
                          min="1"
                          onChange={(event) => handleAffectedOrderChange(row.id, "quantity", event.target.value)}
                          placeholder="Ej. 25"
                          required={rowActive}
                          step="1"
                          type="number"
                          value={row.quantity}
                        />
                      </label>
                      <button
                        aria-label={`Quitar orden ${index + 1}`}
                        className="button button-ghost affected-order-remove"
                        onClick={() => handleRemoveAffectedOrder(row.id)}
                        type="button"
                      >
                        Quitar
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
            <label className="field field-span-2" data-tour="anomaly-observation">
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
            <div className="field field-span-2" data-tour="anomaly-objective-evidence">
              <label htmlFor="anomaly-objective-evidence-input">Evidencia objetiva</label>
              <input
                accept={EVIDENCE_ACCEPT}
                id="anomaly-objective-evidence-input"
                multiple
                onChange={handleEvidenceChange}
                type="file"
              />
              <small className="muted-copy">
                {evidenceFiles.length
                  ? `${evidenceFiles.length} archivo(s) listo(s) para adjuntar. Podes seleccionar mas de una vez para acumular archivos.`
                  : "Opcional: imagenes, PDF, Word, Excel o texto."}
              </small>
              <small className="muted-copy">Los archivos seleccionados permanecen mientras no recargues ni cierres esta pantalla.</small>
              {evidenceFiles.length ? (
                <div className="stack-list compact">
                  {evidenceFiles.map((file, index) => (
                    <SelectedEvidenceFile
                      file={file}
                      index={index}
                      key={`${file.name}-${file.size}-${file.lastModified}`}
                      onRemove={handleRemoveEvidence}
                    />
                  ))}
                  <button className="button button-secondary" onClick={handleClearEvidence} type="button">
                    Quitar todo
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </section>

        {submitError ? <div className="panel danger field-span-2">{submitError}</div> : null}

        <div className="field-span-2 submit-bar">
          <div className="submit-bar-copy">
            <strong>Registrar anomalia</strong>
            <span>Se guardara con codigo, estado inicial y confirmacion inmediata.</span>
          </div>
          <div className="form-actions">
            <button className="button button-secondary" disabled={submitting} onClick={handleDiscardDraft} type="button">
              Descartar carga
            </button>
            <button className="button button-primary button-large" disabled={submitting || !catalogsReady} type="submit">
              {submitting ? "Registrando..." : "Registrar anomalia"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}

