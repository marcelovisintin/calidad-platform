import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchUsers } from "../../../api/accounts";
import { classifyAnomalyBySeverity, fetchMyAnomalies, unlockAnomalyClassificationChange } from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import { fetchOpenTreatmentOptions } from "../../../api/treatments";
import type { CatalogSummary, TreatmentSummary, UserDirectoryItem } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type PendingClassification = {
  anomalyId: string;
  severityId: string;
  severityName: string;
  requiresResponsible: boolean;
  closesAsInvalid: boolean;
  responsibleId: string;
  reason: string;
  isNonconformity: boolean;
  isObservation: boolean;
  observationDueDate: string;
  observationComment: string;
  treatmentDeadline: string;
  treatmentComment: string;
};

type PendingAssociation = {
  anomalyId: string;
  anomalyCode: string;
  treatmentId: string;
};

function buildUserLabel(user: UserDirectoryItem) {
  const fullName = `${user.first_name || ""} ${user.last_name || ""}`.trim();
  const base = fullName || user.username || user.email;
  return user.employee_code ? `${base} (${user.employee_code})` : base;
}

function criterionClosesAsInvalid(criterion: CatalogSummary) {
  const normalized = `${criterion.code} ${criterion.name}`
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return Boolean(criterion.closes_anomaly_as_invalid) || normalized.includes("invalida") || normalized.includes("invalid");
}

function criterionIsNonconformity(criterion: CatalogSummary) {
  const normalized = `${criterion.code} ${criterion.name}`
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return criterion.code.trim().toUpperCase() === "NC" || normalized.includes("no conformidad");
}

function criterionIsObservation(criterion: CatalogSummary) {
  const normalized = `${criterion.code} ${criterion.name}`
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return criterion.code.trim().toUpperCase() === "OBS" || normalized.includes("observacion");
}

export function MyAnomaliesPage() {
  usePageTitle("Seguimiento de anomalias");
  const { user } = useAuth();
  const adminUser = useMemo(() => isAdminUser(user), [user]);
  const strictAdminUser = user?.access_level === "administrador" || user?.access_level === "desarrollador";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [classificationError, setClassificationError] = useState<string | null>(null);
  const [classificationMessage, setClassificationMessage] = useState<string | null>(null);
  const [updatingAnomalyId, setUpdatingAnomalyId] = useState<string | null>(null);
  const [pendingClassification, setPendingClassification] = useState<PendingClassification | null>(null);
  const [pendingAssociation, setPendingAssociation] = useState<PendingAssociation | null>(null);
  const [associationOptions, setAssociationOptions] = useState<TreatmentSummary[]>([]);
  const [associationSearch, setAssociationSearch] = useState("");
  const [associationLoading, setAssociationLoading] = useState(false);
  const [associationError, setAssociationError] = useState<string | null>(null);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    if (!user) {
      throw new Error("No hay usuario autenticado.");
    }

    const [anomalies, catalogs, users] = await Promise.all([
      fetchMyAnomalies(adminUser ? undefined : user.id, search, page),
      fetchCatalogBootstrap(),
      adminUser ? fetchUsers({ active: true, pageSize: 200 }) : Promise.resolve({ count: 0, next: null, previous: null, results: [] as UserDirectoryItem[] }),
    ]);

    return {
      anomalies,
      criteria: catalogs.severities,
      users: users.results.filter((candidate) =>
        ["mando_medio_activo", "administrador", "desarrollador"].includes(candidate.access_level),
      ),
    };
  }, [user?.id, search, adminUser, page]);

  const criteria: CatalogSummary[] = data?.criteria ?? [];
  const users: UserDirectoryItem[] = data?.users ?? [];
  const totalCount = data?.anomalies.count ?? 0;
  const visibleAssociationOptions = useMemo(() => {
    const normalizedSearch = associationSearch.trim().toLowerCase();
    return associationOptions.filter((treatment) => {
      if (!normalizedSearch) {
        return true;
      }
      return [
        treatment.code,
        treatment.primary_anomaly.code,
        treatment.primary_anomaly.title,
        treatment.responsible?.full_name,
        treatment.responsible?.username,
        treatment.status,
      ].some((value) => (value || "").toLowerCase().includes(normalizedSearch));
    });
  }, [associationOptions, associationSearch]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleClassificationChange = (anomalyId: string, severityId: string, canModifyClassification: boolean) => {
    if (!severityId || !adminUser) {
      return;
    }

    if (!canModifyClassification) {
      setClassificationMessage(null);
      setClassificationError("No se puede modificar la Revision de hallazgos.");
      return;
    }

    const criterion = criteria.find((item) => item.id === severityId);
    if (!criterion) {
      setClassificationMessage(null);
      setClassificationError("Selecciona una Revision de hallazgos valida.");
      return;
    }

    const closesAsInvalid = criterionClosesAsInvalid(criterion);
    const isNonconformity = criterionIsNonconformity(criterion);
    const isObservation = criterionIsObservation(criterion);
    setClassificationError(null);
    setClassificationMessage(null);
    setPendingAssociation(null);
    setPendingClassification({
      anomalyId,
      severityId,
      severityName: criterion.name,
      closesAsInvalid,
      requiresResponsible: !closesAsInvalid && (criterion.requires_classification_responsible ?? true),
      responsibleId: "",
      reason: "",
      isNonconformity,
      isObservation,
      observationDueDate: "",
      observationComment: "",
      treatmentDeadline: "",
      treatmentComment: "",
    });
  };

  const handleOpenAssociation = async (anomalyId: string, anomalyCode: string, canModifyClassification: boolean) => {
    if (!canModifyClassification || !adminUser) {
      return;
    }
    if (pendingAssociation?.anomalyId === anomalyId) {
      setPendingAssociation(null);
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setPendingClassification(null);
    setPendingAssociation({ anomalyId, anomalyCode, treatmentId: "" });
    setAssociationOptions([]);
    setAssociationSearch("");
    setAssociationError(null);
    setAssociationLoading(true);
    try {
      setAssociationOptions(await fetchOpenTreatmentOptions(anomalyId));
    } catch (err) {
      setAssociationError(err instanceof Error ? err.message : "No se pudieron consultar los tratamientos disponibles.");
    } finally {
      setAssociationLoading(false);
    }
  };

  const handleConfirmAssociation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pendingAssociation?.treatmentId) {
      setClassificationError("Debe seleccionar un tratamiento.");
      return;
    }
    const nonconformityCriterion = criteria.find(criterionIsNonconformity);
    const selectedTreatment = associationOptions.find((item) => item.id === pendingAssociation.treatmentId);
    if (!nonconformityCriterion || !selectedTreatment) {
      setClassificationError("No se pudo validar la No Conformidad o el tratamiento seleccionado.");
      return;
    }
    const responsibleLabel = selectedTreatment.responsible?.full_name || selectedTreatment.responsible?.username || "su responsable";
    if (!window.confirm(
      `¿Está seguro de asociar la anomalía ${pendingAssociation.anomalyCode} al tratamiento ${selectedTreatment.code}? `
      + `Se clasificará automáticamente como No Conformidad y quedará a cargo de ${responsibleLabel}.`,
    )) {
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setUpdatingAnomalyId(pendingAssociation.anomalyId);
    try {
      await classifyAnomalyBySeverity(pendingAssociation.anomalyId, {
        severity: nonconformityCriterion.id,
        treatment_target: selectedTreatment.id,
      });
      setClassificationMessage(`Anomalía asociada al tratamiento ${selectedTreatment.code} y clasificada como No Conformidad.`);
      setPendingAssociation(null);
      await reload();
    } catch (err) {
      setClassificationError(err instanceof Error ? err.message : "No se pudo asociar la anomalía.");
    } finally {
      setUpdatingAnomalyId(null);
    }
  };

  const handleConfirmClassification = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pendingClassification) {
      return;
    }

    if (pendingClassification.closesAsInvalid && !pendingClassification.reason.trim()) {
      setClassificationError("Debe registrar una observacion o motivo para clasificar como Invalida.");
      return;
    }

    if (pendingClassification.requiresResponsible && !pendingClassification.responsibleId) {
      setClassificationError("Debe seleccionar un responsable para continuar el flujo.");
      return;
    }

    if (pendingClassification.isNonconformity && !pendingClassification.treatmentDeadline) {
      setClassificationError("Debe indicar la fecha límite del tratamiento.");
      return;
    }

    if (pendingClassification.isObservation && !pendingClassification.observationDueDate) {
      setClassificationError("Debe indicar la fecha de realización de la Observación.");
      return;
    }
    if (pendingClassification.isObservation && !pendingClassification.observationComment.trim()) {
      setClassificationError("Debe registrar la causa asignada.");
      return;
    }

    if (
      pendingClassification.isNonconformity
      && !window.confirm(
        "¿Está seguro de confirmar la No Conformidad? Esta acción generará un tratamiento.",
      )
    ) {
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setUpdatingAnomalyId(pendingClassification.anomalyId);

    try {
      await classifyAnomalyBySeverity(pendingClassification.anomalyId, {
        severity: pendingClassification.severityId,
        classification_responsible: pendingClassification.closesAsInvalid ? undefined : pendingClassification.responsibleId || undefined,
        classification_reason: pendingClassification.closesAsInvalid ? pendingClassification.reason.trim() : undefined,
        observation_due_date: pendingClassification.isObservation
          ? pendingClassification.observationDueDate
          : undefined,
        observation_comment: pendingClassification.isObservation
          ? pendingClassification.observationComment.trim()
          : undefined,
        treatment_deadline: pendingClassification.isNonconformity
          ? pendingClassification.treatmentDeadline
          : undefined,
        treatment_comment: pendingClassification.isNonconformity
          ? pendingClassification.treatmentComment.trim()
          : undefined,
      });
      setClassificationMessage("Revision de hallazgos actualizada.");
      setPendingClassification(null);
      await reload();
    } catch (err) {
      setClassificationError(err instanceof Error ? err.message : "No se pudo actualizar la Revision de hallazgos.");
    } finally {
      setUpdatingAnomalyId(null);
    }
  };

  const handleUnlockClassification = async (anomalyId: string) => {
    if (!adminUser) {
      return;
    }

    setClassificationError(null);
    setClassificationMessage(null);
    setUpdatingAnomalyId(anomalyId);

    try {
      await unlockAnomalyClassificationChange(anomalyId);
      setClassificationMessage("Se habilita el cambio de Revision de hallazgos.");
      await reload();
    } catch (err) {
      setClassificationError(err instanceof Error ? err.message : "No se pudo habilitar el cambio de Revision de hallazgos.");
    } finally {
      setUpdatingAnomalyId(null);
    }
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Seguimiento de anomalias"
        description={adminUser ? "Listado completo de seguimiento para administracion." : "Listado filtrado por tus anomalias."}
        actionLabel="Nueva"
        actionTo="/anomalies/new"
      />

      <TabbedFilters
        actions={strictAdminUser ? (
          <Link className="button button-secondary" to="/anomalies/repetition-study">
            Estudio de repitencia
          </Link>
        ) : null}
        ariaLabel="Filtros de seguimiento de anomalias"
        onClear={() => { setSearch(""); setPage(1); }}
        items={[{
          id: "search",
          label: "Buscar",
          active: Boolean(search),
          content: <input aria-label="Buscar anomalias" onChange={handleSearchChange} placeholder="Codigo, titulo, area o estado de hallazgo" type="search" value={search} />,
        }]}
      />

      {classificationError ? <div className="panel danger">{classificationError}</div> : null}
      {classificationMessage ? <div className="panel info">{classificationMessage}</div> : null}

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={totalCount === 0}
        emptyTitle={adminUser ? "No hay anomalias registradas" : "Todavia no reportaste anomalias"}
        emptyDescription="Cuando registres una nueva anomalia, aparecera en este listado."
      >
        <div className="stack-list">
          {data?.anomalies.results.map((item) => {
            const canModifyClassification = item.can_modify_classification ?? true;
            const canUnlockClassification = item.can_unlock_classification ?? false;
            const pendingForItem = pendingClassification?.anomalyId === item.id ? pendingClassification : null;
            const associationForItem = pendingAssociation?.anomalyId === item.id ? pendingAssociation : null;
            const disableClassificationSelect =
              updatingAnomalyId === item.id || criteria.length === 0 || !canModifyClassification;

            return (
              <article className="list-card anomaly-row" key={item.id}>
                <Link className="anomaly-row-main" to={`/anomalies/${item.id}`}>
                  <strong>{item.code}</strong>
                  <p>{item.title}</p>
                  <small>{`Tipo de desvio: ${item.anomaly_type?.name || "Sin tipo de desvio"}`}</small>
                  <small>{`Reportada por: ${item.reporter?.full_name || item.reporter?.username || "Sin dato"}`}</small>
                  <small>
                    {item.site?.name || "Sin sitio"} | {item.area?.name || "Sin area"} | {formatDateTime(item.detected_at)}
                  </small>
                </Link>

                <div className="badge-stack align-end anomaly-row-actions">
                  <StatusBadge value={item.current_status} overdue={item.is_overdue} compact />

                  {adminUser ? (
                    <div className="anomaly-classification-control">
                      <span>Revision de hallazgos</span>
                      <select
                        aria-label={`Revision de hallazgos de ${item.code}`}
                        disabled={disableClassificationSelect}
                        onChange={(event) => handleClassificationChange(item.id, event.target.value, canModifyClassification)}
                        value={pendingForItem?.severityId || item.severity?.id || ""}
                      >
                        <option value="">Seleccionar...</option>
                        {criteria.map((criterion) => (
                          <option key={criterion.id} value={criterion.id}>
                            {criterion.name}
                          </option>
                        ))}
                      </select>

                      {pendingForItem ? (
                        <form className="form-section compact" onSubmit={handleConfirmClassification}>
                          <div className="section-head compact">
                            <h3>{`Confirmar ${pendingForItem.severityName}`}</h3>
                          </div>

                          {pendingForItem.closesAsInvalid ? (
                            <label className="field">
                              <span>Observacion / Motivo</span>
                              <textarea
                                onChange={(event) =>
                                  setPendingClassification((current) => current && current.anomalyId === item.id ? { ...current, reason: event.target.value } : current)
                                }
                                required
                                rows={3}
                                value={pendingForItem.reason}
                              />
                            </label>
                          ) : (
                            <>
                              {pendingForItem.requiresResponsible ? (
                                <label className="field">
                                  <span>Responsable único del tratamiento</span>
                                  <select
                                    onChange={(event) =>
                                      setPendingClassification((current) => current && current.anomalyId === item.id ? { ...current, responsibleId: event.target.value } : current)
                                    }
                                    required
                                    value={pendingForItem.responsibleId}
                                  >
                                    <option value="">Seleccionar responsable...</option>
                                    {users.map((option) => (
                                      <option key={option.id} value={option.id}>
                                        {buildUserLabel(option)}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              ) : null}

                              {pendingForItem.isObservation ? (
                                <section className="form-section compact">
                                  <label className="field">
                                    <span>Fecha de realización</span>
                                    <input
                                      onChange={(event) =>
                                        setPendingClassification((current) => current && current.anomalyId === item.id
                                          ? { ...current, observationDueDate: event.target.value }
                                          : current)
                                      }
                                      required
                                      type="date"
                                      value={pendingForItem.observationDueDate}
                                    />
                                  </label>
                                  <label className="field">
                                    <span>Causa asignada</span>
                                    <textarea
                                      onChange={(event) =>
                                        setPendingClassification((current) => current && current.anomalyId === item.id
                                          ? { ...current, observationComment: event.target.value }
                                          : current)
                                      }
                                      required
                                      rows={3}
                                      value={pendingForItem.observationComment}
                                    />
                                  </label>
                                </section>
                              ) : null}

                              {pendingForItem.isNonconformity ? (
                                <section className="classification-new-treatment-fields">
                                  <label className="field">
                                    <span>Fecha límite del tratamiento</span>
                                    <input
                                      onChange={(event) =>
                                        setPendingClassification((current) => current && current.anomalyId === item.id
                                          ? { ...current, treatmentDeadline: event.target.value }
                                          : current)
                                      }
                                      required
                                      type="date"
                                      value={pendingForItem.treatmentDeadline}
                                    />
                                  </label>
                                  <label className="field">
                                    <span>Comentario (opcional)</span>
                                    <textarea
                                      onChange={(event) =>
                                        setPendingClassification((current) => current && current.anomalyId === item.id
                                          ? { ...current, treatmentComment: event.target.value }
                                          : current)
                                      }
                                      rows={3}
                                      value={pendingForItem.treatmentComment}
                                    />
                                  </label>
                                </section>
                              ) : null}
                            </>
                          )}

                          <div className="form-actions">
                            <button className="button button-primary" disabled={updatingAnomalyId === item.id} type="submit">
                              {updatingAnomalyId === item.id ? "Confirmando..." : "Confirmar"}
                            </button>
                            <button className="button button-secondary" onClick={() => setPendingClassification(null)} type="button">
                              Cancelar
                            </button>
                          </div>
                        </form>
                      ) : null}

                      {canModifyClassification ? (
                        <button
                          className="button button-secondary associate-anomalies-button"
                          disabled={updatingAnomalyId === item.id}
                          onClick={() => void handleOpenAssociation(item.id, item.code, canModifyClassification)}
                          type="button"
                        >
                          {associationForItem ? "Cerrar asociación" : "Asociar anomalías"}
                        </button>
                      ) : null}

                      {associationForItem ? (
                        <form className="form-section compact association-treatment-panel" onSubmit={handleConfirmAssociation}>
                          <div className="section-head compact">
                            <div>
                              <h3>Asociar a un tratamiento existente</h3>
                              <small>La anomalía se clasificará como No Conformidad y heredará el responsable del tratamiento.</small>
                            </div>
                          </div>
                          <input
                            aria-label="Buscar tratamientos disponibles"
                            onChange={(event) => setAssociationSearch(event.target.value)}
                            placeholder="Buscar por tratamiento, anomalía, responsable o estado"
                            type="search"
                            value={associationSearch}
                          />
                          {associationLoading ? <p className="muted-copy">Consultando tratamientos disponibles...</p> : null}
                          {associationError ? <div className="panel warning">{associationError}</div> : null}
                          {!associationLoading && !associationError ? (
                            <div className="stack-list compact association-treatment-list">
                              {visibleAssociationOptions.map((treatment) => (
                                <label className="list-card compact association-treatment-option" key={treatment.id}>
                                  <input
                                    checked={associationForItem.treatmentId === treatment.id}
                                    onChange={(event) =>
                                      setPendingAssociation((current) => current && current.anomalyId === item.id
                                        ? { ...current, treatmentId: event.target.checked ? treatment.id : "" }
                                        : current)
                                    }
                                    type="checkbox"
                                  />
                                  <span>
                                    <strong>{treatment.code}</strong>
                                    <small>{treatment.primary_anomaly.code} | {treatment.primary_anomaly.title}</small>
                                    <small>
                                      Responsable: {treatment.responsible?.full_name || treatment.responsible?.username || "Sin responsable"}
                                    </small>
                                    <small>Acciones completadas: {treatment.tasks_completed ?? 0} de {treatment.tasks_total ?? 0}</small>
                                  </span>
                                  <StatusBadge value={treatment.status} overdue={treatment.is_overdue} compact />
                                </label>
                              ))}
                              {!visibleAssociationOptions.length ? (
                                <p className="muted-copy">No hay tratamientos disponibles para asociar.</p>
                              ) : null}
                            </div>
                          ) : null}
                          <div className="form-actions association-confirm-actions">
                            <button
                              className="button button-primary"
                              disabled={!associationForItem.treatmentId || updatingAnomalyId === item.id}
                              type="submit"
                            >
                              {updatingAnomalyId === item.id ? "Asociando..." : "Confirmar asociación"}
                            </button>
                            <button className="button button-secondary" onClick={() => setPendingAssociation(null)} type="button">
                              Cancelar
                            </button>
                          </div>
                        </form>
                      ) : null}

                      {canUnlockClassification ? (
                        <button
                          className="button button-secondary"
                          disabled={updatingAnomalyId === item.id}
                          onClick={() => void handleUnlockClassification(item.id)}
                          type="button"
                        >
                          Habilitar cambio
                        </button>
                      ) : null}
                      {!canModifyClassification && !canUnlockClassification ? (
                        <small className="muted-copy">No se puede modificar la Revision de hallazgos.</small>
                      ) : null}
                    </div>
                  ) : (
                    <span className="status-badge info compact">{item.severity?.name || "Sin Revision de hallazgos"}</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>

        <PaginationControls page={page} totalCount={totalCount} onPageChange={setPage} disabled={loading} />
      </DataState>
    </section>
  );
}
