import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { fetchValidationWorkItems } from "../../../api/actions";
import { fetchAnomalyDetail, verifyObservationEffectiveness } from "../../../api/anomalies";
import { fetchTreatmentDetail, validateTreatmentEffectiveness } from "../../../api/treatments";
import type { ActionWorkItemSource, ValidationWorkItem } from "../../../api/types";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import {
  resolveAnomalyHelpWorkContext,
  resolveTreatmentHelpWorkContext,
  usePublishHelpWorkContext,
} from "../../help/workContext";

type ValidationResult = "effective" | "not_effective" | "";

function nowAsLocalDateTime() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function toOffsetIso(value: string) {
  return new Date(value).toISOString();
}

function resultLabel(value?: string) {
  if (value === "effective") return "Eficaz";
  if (value === "not_effective") return "No eficaz";
  return "Sin validar";
}

function statusLabel(value: ValidationWorkItem["status"]) {
  if (value === "completed") return "Realizada";
  if (value === "blocked") return "Bloqueada";
  return "Pendiente";
}

function itemKey(item: Pick<ValidationWorkItem, "id" | "source">) {
  return `${item.source}:${item.id}`;
}

function SourceBadge({ source }: { source: ActionWorkItemSource }) {
  return (
    <span className={`action-source-badge ${source}`}>
      {source === "treatment" ? "Tratamiento" : "Observacion"}
    </span>
  );
}

export function TreatmentValidationPage() {
  usePageTitle("Validacion");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showTreatments, setShowTreatments] = useState(true);
  const [showObservations, setShowObservations] = useState(true);
  const [selectedKey, setSelectedKey] = useState("");
  const [validationResult, setValidationResult] = useState<ValidationResult>("");
  const [validationComment, setValidationComment] = useState("");
  const [verifiedAt, setVerifiedAt] = useState(nowAsLocalDateTime());
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selectedSources = useMemo<ActionWorkItemSource[]>(() => {
    const sources: ActionWorkItemSource[] = [];
    if (showTreatments) sources.push("treatment");
    if (showObservations) sources.push("observation");
    return sources;
  }, [showTreatments, showObservations]);

  const { data, loading, error, reload } = useAsyncTask(
    () => fetchValidationWorkItems({ page, q: search, sources: selectedSources }),
    [page, search, showTreatments, showObservations],
  );
  const items = data?.results ?? [];

  useEffect(() => {
    if (!items.length) {
      setSelectedKey("");
      return;
    }
    if (!selectedKey || !items.some((item) => itemKey(item) === selectedKey)) {
      setSelectedKey(itemKey(items[0]));
    }
  }, [items, selectedKey]);

  const selectedItem = items.find((item) => itemKey(item) === selectedKey) ?? null;
  const {
    data: selectedDetail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncTask(async () => {
    if (!selectedItem) return null;
    if (selectedItem.source === "treatment") {
      return { source: "treatment" as const, detail: await fetchTreatmentDetail(selectedItem.id) };
    }
    return { source: "observation" as const, detail: await fetchAnomalyDetail(selectedItem.id) };
  }, [selectedKey]);

  useEffect(() => {
    setValidationResult("");
    setValidationComment("");
    setVerifiedAt(nowAsLocalDateTime());
    setFormError(null);
    setMessage(null);
  }, [selectedKey]);

  const treatmentContext = selectedDetail?.source === "treatment"
    ? resolveTreatmentHelpWorkContext(selectedDetail.detail)
    : null;
  const anomalyContext = selectedDetail?.source === "observation"
    ? resolveAnomalyHelpWorkContext(selectedDetail.detail, false)
    : null;
  usePublishHelpWorkContext(treatmentContext ?? anomalyContext);

  const handleSourceChange = (source: ActionWorkItemSource) => (event: ChangeEvent<HTMLInputElement>) => {
    if (source === "treatment") setShowTreatments(event.target.checked);
    else setShowObservations(event.target.checked);
    setPage(1);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedItem || !validationResult) {
      setFormError("Debe seleccionar si la validacion fue eficaz o no eficaz.");
      return;
    }
    if (!selectedItem.can_validate) {
      setFormError("La validacion no esta disponible para el usuario actual.");
      return;
    }

    setBusy(true);
    setFormError(null);
    setMessage(null);
    try {
      if (selectedItem.source === "treatment") {
        await validateTreatmentEffectiveness(selectedItem.id, {
          result: validationResult,
          comment: validationComment.trim(),
        });
      } else {
        await verifyObservationEffectiveness(selectedItem.id, {
          effectiveness_verified_at: toOffsetIso(verifiedAt),
          effectiveness_is_effective: validationResult === "effective",
          effectiveness_comment: validationComment.trim() || undefined,
        });
      }
      setMessage("Validacion registrada correctamente.");
      setValidationResult("");
      setValidationComment("");
      await Promise.all([reload(), reloadDetail()]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo registrar la validacion.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-shell">
      <PageHeader title="Validacion" description="Verificacion de eficacia de tratamientos y observaciones." />

      <section className="panel action-source-selector" aria-label="Origen de las validaciones">
        <div><p className="eyebrow">Origen</p><h2>Mostrar validaciones de</h2></div>
        <div className="action-source-options">
          <label className="checkbox-line">
            <input checked={showTreatments} onChange={handleSourceChange("treatment")} type="checkbox" />
            <span>Tratamientos</span>
          </label>
          <label className="checkbox-line">
            <input checked={showObservations} onChange={handleSourceChange("observation")} type="checkbox" />
            <span>Observaciones</span>
          </label>
        </div>
      </section>

      {message ? <div className="panel success">{message}</div> : null}
      {formError ? <div className="panel danger">{formError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid">
          <section className="panel">
            <div className="section-head compact">
              <div><p className="eyebrow">Validaciones</p><h2>Todos los estados</h2></div>
            </div>
            <label className="field">
              <span>Buscar</span>
              <input
                onChange={(event) => { setSearch(event.target.value); setPage(1); }}
                placeholder="Codigo, titulo o responsable"
                type="search"
                value={search}
              />
            </label>
            <div className="stack-list user-list-scroll validation-work-list">
              {items.map((item) => (
                <button
                  className={`list-card selectable-card work-list-card${selectedKey === itemKey(item) ? " active" : ""}`}
                  key={itemKey(item)}
                  onClick={() => setSelectedKey(itemKey(item))}
                  type="button"
                >
                  <div className="work-card-main">
                    <div className="work-card-heading"><SourceBadge source={item.source} /><strong>{item.code}</strong><span>{item.title}</span></div>
                    <div className="work-card-meta"><small>Evaluacion: {item.due_date ? formatDate(item.due_date) : "Sin fecha"}</small><small>Responsable: {item.responsible?.full_name || item.responsible?.username || "Sin responsable"}</small></div>
                  </div>
                  <div className="badge-stack align-end">
                    <StatusBadge value={item.status} overdue={item.is_overdue} compact />
                    <small>{statusLabel(item.status)}</small>
                  </div>
                </button>
              ))}
              {!items.length ? <p className="muted-copy">No hay validaciones para los origenes seleccionados.</p> : null}
            </div>
            <PaginationControls page={page} totalCount={data?.count ?? 0} onPageChange={setPage} disabled={loading || busy} />
          </section>

          <section className="panel">
            <DataState loading={detailLoading} error={detailError} onRetry={reloadDetail}>
              {selectedItem && selectedDetail ? (
                <form className="form-section" onSubmit={handleSubmit}>
                  <div className="section-head compact">
                    <div>
                      <div className="badge-stack"><SourceBadge source={selectedItem.source} /></div>
                      <p className="eyebrow">{selectedItem.code}</p>
                      <h2>{selectedItem.title}</h2>
                    </div>
                    <StatusBadge value={selectedItem.status} overdue={selectedItem.is_overdue} />
                  </div>

                  <dl className="key-grid compact">
                    <div><dt>Fecha estimada</dt><dd>{selectedItem.due_date ? formatDate(selectedItem.due_date) : "Sin fecha"}</dd></div>
                    <div><dt>Responsable</dt><dd>{selectedItem.responsible?.full_name || selectedItem.responsible?.username || "Sin responsable"}</dd></div>
                    <div><dt>Resultado actual</dt><dd>{resultLabel(selectedItem.result)}</dd></div>
                    <div><dt>Fecha de validacion</dt><dd>{selectedItem.validated_at ? formatDateTime(selectedItem.validated_at) : "Sin validar"}</dd></div>
                  </dl>

                  {selectedItem.validation_comment ? (
                    <div className="readonly-block"><strong>Comentario registrado</strong><p>{selectedItem.validation_comment}</p></div>
                  ) : null}

                  {selectedItem.blockers.length ? (
                    <div className="panel warning">
                      <h3>Falta completar</h3>
                      <ul className="help-list">
                        {selectedItem.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
                      </ul>
                    </div>
                  ) : selectedItem.status === "pending" ? (
                    <div className="panel info">El caso cumple las condiciones para validar.</div>
                  ) : null}

                  {!selectedItem.can_validate && selectedItem.status !== "completed" ? (
                    <div className="panel warning compact-inline-panel">
                      <p>Solo el responsable designado puede registrar esta validacion.</p>
                    </div>
                  ) : null}

                  {selectedItem.status === "completed" ? (
                    <div className="panel muted">Esta validacion ya fue realizada y se muestra en modo consulta.</div>
                  ) : (
                    <>
                      <div className="form-grid">
                        {selectedItem.source === "observation" ? (
                          <label className="field">
                            <span>Fecha de realizacion</span>
                            <input disabled={!selectedItem.can_validate || busy} onChange={(event) => setVerifiedAt(event.target.value)} required type="datetime-local" value={verifiedAt} />
                          </label>
                        ) : null}
                        <label className="field">
                          <span>Resultado</span>
                          <select disabled={!selectedItem.can_validate || busy} onChange={(event) => setValidationResult(event.target.value as ValidationResult)} required value={validationResult}>
                            <option value="">Seleccionar...</option>
                            <option value="effective">Eficaz</option>
                            <option value="not_effective">No eficaz</option>
                          </select>
                        </label>
                        <label className="field field-span-2">
                          <span>Observacion</span>
                          <textarea disabled={!selectedItem.can_validate || busy} onChange={(event) => setValidationComment(event.target.value)} rows={3} value={validationComment} />
                        </label>
                      </div>
                      <div className="form-actions">
                        <button className="button button-primary" disabled={busy || !validationResult || !selectedItem.can_validate} type="submit">
                          {busy ? "Guardando..." : "Registrar validacion"}
                        </button>
                      </div>
                    </>
                  )}
                </form>
              ) : (
                <p className="muted-copy">Selecciona una validacion para revisar el detalle.</p>
              )}
            </DataState>
          </section>
        </div>
      </DataState>
    </section>
  );
}
