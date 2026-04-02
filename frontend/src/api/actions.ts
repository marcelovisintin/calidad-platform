import { apiRequest } from "./http";
import type { ActionItemDetail, PagedResponse } from "./types";

export function fetchMyActions() {
  return apiRequest<PagedResponse<ActionItemDetail>>("/actions/items/my-actions/");
}

export function fetchPendingActions() {
  return apiRequest<PagedResponse<ActionItemDetail>>("/actions/items/pending/");
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
