const NEW_ANOMALY_DRAFT_PREFIX = "calidad-platform.new-anomaly-draft.";

export function newAnomalyDraftKey(userId: string) {
  return `${NEW_ANOMALY_DRAFT_PREFIX}${userId}`;
}

export function clearSessionDrafts() {
  for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = window.sessionStorage.key(index);
    if (key?.startsWith(NEW_ANOMALY_DRAFT_PREFIX)) {
      window.sessionStorage.removeItem(key);
    }
  }
}
