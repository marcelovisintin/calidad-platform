import { FormEvent, useState } from "react";
import { associateAnomalyToObservation, fetchOpenObservationOptions } from "../../../api/anomalies";
import { AutoResizeTextarea } from "../../../components/AutoResizeTextarea";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";

export function ObservationAssociationPanel({ anomalyId, onAssociated, onCancel }: {
  anomalyId: string;
  onAssociated: () => Promise<void>;
  onCancel: () => void;
}) {
  const { data, loading, error, reload } = useAsyncTask(() => fetchOpenObservationOptions(anomalyId), [anomalyId]);
  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const options = (data ?? []).filter((item) =>
    `${item.code} ${item.title} ${item.responsible?.full_name ?? ""} ${item.responsible?.username ?? ""} ${item.current_status}`.toLowerCase().includes(search.trim().toLowerCase()),
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const observation = data?.find((item) => item.id === selected);
    if (!observation || !reason.trim()) return;
    if (!window.confirm(`La anomalía se clasificará como OBS y compartirá la gestión de ${observation.code}, a cargo de ${observation.responsible?.full_name || observation.responsible?.username}. Fecha límite vigente: ${observation.deadline || "sin fecha"}.${observation.is_overdue ? " La gestión está vencida." : ""} ¿Confirmar asociación?`)) return;
    setBusy(true);
    setFormError(null);
    try {
      await associateAnomalyToObservation(anomalyId, selected, reason.trim());
      await onAssociated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo asociar la anomalía.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form-section compact association-treatment-panel" onSubmit={(event) => void submit(event)}>
      <div className="section-head compact">
        <div>
          <h3>Asociar a una observación existente</h3>
          <small>La anomalía se clasificará como Observación y heredará el responsable y los plazos de la observación.</small>
        </div>
      </div>
      <input
        aria-label="Buscar observaciones disponibles"
        disabled={busy}
        placeholder="Buscar por observación, anomalía, responsable o estado"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        type="search"
      />
      {loading ? <p className="muted-copy">Consultando observaciones disponibles...</p> : null}
      {error ? <div className="panel warning">{error}<button className="button button-secondary" onClick={() => void reload()} type="button">Reintentar</button></div> : null}
      {!loading && !error ? (
        <div className="stack-list compact association-treatment-list">
          {options.map((item) => (
            <label className="list-card compact association-treatment-option" key={item.id}>
              <input
                type="checkbox"
                disabled={busy}
                checked={selected === item.id}
                onChange={(event) => setSelected(event.target.checked ? item.id : "")}
              />
              <span>
                <strong>{item.code}</strong>
                <small>{item.title}</small>
                <small>Responsable: {item.responsible?.full_name || item.responsible?.username || "Sin responsable"}</small>
                <small>Fecha límite: {item.deadline || "Sin fecha"}</small>
              </span>
              <StatusBadge value={item.current_status} overdue={item.is_overdue} compact />
            </label>
          ))}
          {!options.length ? <p className="muted-copy">No hay observaciones disponibles para asociar.</p> : null}
        </div>
      ) : null}
      <label className="field">
        <span>Motivo de asociación (obligatorio)</span>
        <AutoResizeTextarea minHeightPx={70} disabled={busy} required value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explique por qué las acciones de esta observación cubren el nuevo hallazgo." />
      </label>
      {formError ? <div className="panel danger" role="alert">{formError}</div> : null}
      <div className="form-actions association-confirm-actions">
        <button className="button button-primary" disabled={!selected || !reason.trim() || busy || loading || Boolean(error)} type="submit">{busy ? "Asociando..." : "Confirmar asociación"}</button>
        <button className="button button-secondary" disabled={busy} onClick={onCancel} type="button">Cancelar</button>
      </div>
    </form>
  );
}
