import { formatDate } from "../app/utils";

export function TreatmentStartDeadline({ date }: { date?: string | null }) {
  const now = new Date();
  const today = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  const overdue = Boolean(date && date < today);
  return <span className={overdue ? "treatment-start-deadline-overdue" : undefined}>{formatDate(date)}{overdue ? " · Vencido" : ""}</span>;
}
