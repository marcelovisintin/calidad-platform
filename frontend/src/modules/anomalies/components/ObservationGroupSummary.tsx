import { Link } from "react-router-dom";
import { useState } from "react";
import type { AnomalyListItem } from "../../../api/types";
import { detachAnomalyFromObservation } from "../../../api/anomalies";
import { useAuth } from "../../../app/providers/AuthProvider";
import { isAdminUser } from "../../../app/access";
import { AutoResizeTextarea } from "../../../components/AutoResizeTextarea";

export function ObservationGroupSummary({ anomaly, onChanged }: { anomaly: AnomalyListItem; onChanged?: () => Promise<unknown> }) {
  const { user } = useAuth();
  const [separating, setSeparating] = useState(false);
  const [reason, setReason] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const parent = anomaly.observation_parent;
  const members = anomaly.observation_anomalies ?? [];
  const canManage = isAdminUser(user) || anomaly.owner?.id === user?.id || anomaly.current_responsible?.id === user?.id;
  if (!parent && !members.length) return null;
  return <div className="panel info compact">
    <h3>Observación compartida</h3>
    {parent ? <p>Esta anomalía se gestiona en {canManage ? <Link to={`/anomalies/observations?anomaly=${parent.id}`}>{parent.code}</Link> : <strong>{parent.code}</strong>}. Comparte sus acciones, responsable y verificación de eficacia.</p> : <p>Las acciones y su verificación de eficacia deben cubrir también estos hallazgos.</p>}
    <ul>{members.map((member) => <li key={member.id}>{canManage || member.id === anomaly.id ? <Link to={`/anomalies/${member.id}`}>{member.code}</Link> : <strong>{member.code}</strong>} — {member.title}</li>)}</ul>
    {parent && isAdminUser(user) && onChanged && !["closed", "cancelled"].includes(anomaly.current_status) ? <>
      <button className="button button-secondary" type="button" onClick={() => setSeparating(!separating)}>Separar para gestión independiente</button>
      {separating ? <div className="form-section">
        <p>Conserva el historial del vínculo. Las acciones y evidencias compartidas permanecen en la observación original.</p>
        <label className="field"><span>Motivo obligatorio</span><AutoResizeTextarea minHeightPx={70} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <label className="field"><span>Fecha límite para la gestión independiente</span><input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <button className="button button-primary" disabled={busy || !reason.trim() || !dueDate} type="button" onClick={() => {
          if (!window.confirm("¿Separar esta anomalía y gestionar sus acciones y eficacia de forma independiente?")) return;
          setBusy(true);
          setError(null);
          void detachAnomalyFromObservation(anomaly.id, reason.trim(), dueDate).then(onChanged).then(() => setSeparating(false)).catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudo separar.")).finally(() => setBusy(false));
        }}>Confirmar separación</button>
      </div> : null}
    </> : null}
  </div>;
}
