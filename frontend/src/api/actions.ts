import { apiRequest } from "./http";
import type { ActionItemDetail, PagedResponse } from "./types";

export type ActionItemsFilters = {
  page?: number;
  q?: string;
  anomaly?: string;
  treatment?: string;
  completedOn?: string;
  performedBy?: string;
  status?: string;
};

export function fetchActionItems(filters: ActionItemsFilters = {}) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: "10",
  });

  if (filters.q?.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.anomaly?.trim()) {
    params.set("anomaly", filters.anomaly.trim());
  }
  if (filters.treatment?.trim()) {
    params.set("treatment", filters.treatment.trim());
  }
  if (filters.completedOn?.trim()) {
    params.set("completed_on", filters.completedOn.trim());
  }
  if (filters.performedBy?.trim()) {
    params.set("performed_by", filters.performedBy.trim());
  }
  if (filters.status?.trim()) {
    params.set("status", filters.status.trim());
  }

  return apiRequest<PagedResponse<ActionItemDetail>>(`/actions/items/?${params.toString()}`);
}

export function fetchActionItemDetail(actionItemId: string) {
  return apiRequest<ActionItemDetail>(`/actions/items/${actionItemId}/`);
}

export function fetchMyActions(page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  return apiRequest<PagedResponse<ActionItemDetail>>(`/actions/items/my-actions/?${params.toString()}`);
}

export function fetchPendingActions(page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  return apiRequest<PagedResponse<ActionItemDetail>>(`/actions/items/pending/?${params.toString()}`);
}

export function transitionActionItem(actionItemId: string, targetStatus: string, comment: string, closureComment = "") {
  return apiRequest<ActionItemDetail>(`/actions/items/${actionItemId}/transition/`, {
    method: "POST",
    body: {
      target_status: targetStatus,
      comment,
      closure_comment: closureComment,
    },
  });
}
