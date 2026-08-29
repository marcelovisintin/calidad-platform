import { FormEvent, useEffect, useMemo, useState } from "react";
import { fetchTreatmentDetail, fetchTreatments, validateTreatmentEffectiveness } from "../../../api/treatments";
import type { TreatmentDetail } from "../../../api/types";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDate, formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { resolveTreatmentHelpWorkContext, usePublishHelpWorkContext } from "../../help/workContext";

type ValidationResult = "effective" | "not_effective" | "";

function resultLabel(value?: string) {
  if (value === "effective") {
    return "Eficaz";
  }
  if (value === "not_effective") {
    return "No eficaz";
  }
  return "Sin validar";
}

export function TreatmentValidationPage() {
  usePageTitle("Validacion");
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [selectedTreatmentId, setSelectedTreatmentId] = useState("");
  const [validationResult, setValidationResult] = useState<ValidationResult>("");
  const [validationComment, setValidationComment] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data, loading, error, reload } = useAsyncTask(() => fetchTreatments(page, "", { validationReady: true }), [page]);
  const treatments = data?.results ?? [];

  useEffect(() => {
    if (!treatments.length) {
      setSelectedTreatmentId("");
      return;
    }
    if (!selectedTreatmentId || !treatments.some((item) => item.id === selectedTreatmentId)) {
      setSelectedTreatmentId(treatments[0].id);
    }
  }, [selectedTreatmentId, treatments]);

  const {
    data: selectedTreatment,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncTask(async () => {
    if (!selectedTreatmentId) {
      return null;
    }
    return fetchTreatmentDetail(selectedTreatmentId);
  }, [selectedTreatmentId]);

  useEffect(() => {
    setValidationResult("");
    setValidationComment("");
    setFormError(null);
    setMessage(null);
  }, [selectedTreatmentId]);

  const canCurrentUserValidate = useMemo(() => {
    if (!selectedTreatment || !user) {
      return false;
    }
    return selectedTreatment.effectiveness_responsible?.id === user.id;
  }, [selectedTreatment, user]);

  const blockers = selectedTreatment?.validation_state?.blockers ?? [];
  const validationAvailable = Boolean(selectedTreatment?.validation_state?.available);
  usePublishHelpWorkContext(selectedTreatment ? resolveTreatmentHelpWorkContext(selectedTreatment) : null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTreatment || !validationResult) {
      setFormError("Debe seleccionar si el tratamiento fue eficaz o no eficaz.");
      return;
    }
    if (!validationAvailable) {
      setFormError("El tratamiento todavia no cumple las condiciones para validacion.");
      return;
    }
    if (!canCurrentUserValidate) {
      setFormError("Solo el responsable designado puede validar la eficacia del tratamiento.");
      return;
    }

    setBusy(true);
    setFormError(null);
    setMessage(null);
    try {
      await validateTreatmentEffectiveness(selectedTreatment.id, {
        result: validationResult,
        comment: validationComment.trim(),
      });
      setMessage("Validacion registrada correctamente.");
      setValidationResult("");
      setValidationComment("");
      await reload();
      await reloadDetail();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo registrar la validacion.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Validacion"
        description="Evaluacion de eficacia de tratamientos por el responsable designado."
      />

      {message ? <div className="panel">{message}</div> : null}
      {formError ? <div className="panel danger">{formError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid">
          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Tratamientos</p>
                <h2>Disponibles y pendientes</h2>
              </div>
            </div>
            <div className="stack-list user-list-scroll">
              {treatments.map((item) => (
                <button
                  className={`list-card selectable-card${selectedTreatmentId === item.id ? " active" : ""}`}
                  key={item.id}
                  onClick={() => setSelectedTreatmentId(item.id)}
                  type="button"
                >
                  <div>
                    <strong>{item.code}</strong>
                    <p>{item.primary_anomaly.title}</p>
                    <small>
                      Evaluacion: {item.effectiveness_evaluation_date ? formatDate(item.effectiveness_evaluation_date) : "Sin fecha"}
                    </small>
                    <small>Responsable: {item.effectiveness_responsible?.full_name || "Sin responsable"}</small>
                  </div>
                  <div className="badge-stack align-end">
                    <StatusBadge value={item.status} compact />
                    <StatusBadge value="active" compact />
                  </div>
                </button>
              ))}
              {!treatments.length ? <p className="muted-copy">No hay tratamientos visibles para validar.</p> : null}
            </div>
            <PaginationControls page={page} totalCount={data?.count ?? 0} onPageChange={setPage} disabled={loading || busy} />
          </section>

          <section className="panel">
            <DataState loading={detailLoading} error={detailError} onRetry={reloadDetail}>
              {selectedTreatment ? (
                <form className="form-section" onSubmit={handleSubmit}>
                  <div className="section-head compact">
                    <div>
                      <p className="eyebrow">{selectedTreatment.code}</p>
                      <h2>{selectedTreatment.primary_anomaly.title}</h2>
                    </div>
                    <StatusBadge value={selectedTreatment.status} />
                  </div>

                  <dl className="key-grid compact">
                    <div>
                      <dt>Fecha tratamiento</dt>
                      <dd>{selectedTreatment.scheduled_for ? formatDateTime(selectedTreatment.scheduled_for) : "Sin agenda"}</dd>
                    </div>
                    <div>
                      <dt>Fecha evaluacion</dt>
                      <dd>{selectedTreatment.effectiveness_evaluation_date ? formatDate(selectedTreatment.effectiveness_evaluation_date) : "Sin fecha"}</dd>
                    </div>
                    <div>
                      <dt>Responsable designado</dt>
                      <dd>{selectedTreatment.effectiveness_responsible?.full_name || "Sin responsable"}</dd>
                    </div>
                    <div>
                      <dt>Resultado actual</dt>
                      <dd>{resultLabel(selectedTreatment.effectiveness_validation_result)}</dd>
                    </div>
                  </dl>

                  {!canCurrentUserValidate ? (
                    <div className="panel warning compact-inline-panel">
                      <p>Solo el responsable designado puede validar la eficacia del tratamiento.</p>
                    </div>
                  ) : null}

                  {blockers.length ? (
                    <div className="panel warning">
                      <h3>Falta completar</h3>
                      <ul className="help-list">
                        {blockers.map((blocker) => (
                          <li key={blocker}>{blocker}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="panel info">El tratamiento cumple las condiciones para validacion.</div>
                  )}

                  <div className="form-grid">
                    <label className="field">
                      <span>Resultado de validacion</span>
                      <select
                        disabled={!validationAvailable || !canCurrentUserValidate || busy}
                        onChange={(event) => setValidationResult(event.target.value as ValidationResult)}
                        required
                        value={validationResult}
                      >
                        <option value="">Seleccionar...</option>
                        <option value="effective">Eficaz</option>
                        <option value="not_effective">No eficaz</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Observacion</span>
                      <textarea
                        disabled={!validationAvailable || !canCurrentUserValidate || busy}
                        onChange={(event) => setValidationComment(event.target.value)}
                        rows={3}
                        value={validationComment}
                      />
                    </label>
                  </div>

                  <div className="form-actions">
                    <button
                      className="button button-primary"
                      disabled={busy || !validationResult || !validationAvailable || !canCurrentUserValidate}
                      type="submit"
                    >
                      Registrar validacion
                    </button>
                  </div>
                </form>
              ) : (
                <p className="muted-copy">Selecciona un tratamiento para revisar su validacion.</p>
              )}
            </DataState>
          </section>
        </div>
      </DataState>
    </section>
  );
}
