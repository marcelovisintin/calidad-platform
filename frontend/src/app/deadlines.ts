const terminalStatuses = new Set([
  "completed", "closed", "cancelled", "effective", "validated_effective", "resolved",
]);

export function isDeadlineOverdue(
  dueDate: string | null | undefined,
  status: string | null | undefined,
  now = new Date(),
): boolean {
  if (!dueDate || !status || terminalStatuses.has(status)) return false;
  // Calendar dates are valid through the end of the business day in Argentina.
  const businessDate = (date: Date) => new Intl.DateTimeFormat("en-CA", {
    timeZone: import.meta.env.VITE_BUSINESS_TIME_ZONE || "America/Argentina/Buenos_Aires", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(date);
  if (Number.isNaN(new Date(dueDate).getTime())) return false;
  const date = dueDate.length === 10 ? dueDate : businessDate(new Date(dueDate));
  return date < businessDate(now);
}

export function canShowOverdue(status?: string | null): boolean {
  return !!status && !terminalStatuses.has(status);
}
