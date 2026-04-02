import { apiRequest } from "./http";
import type { NotificationInboxItem, NotificationInboxSummary, PagedResponse } from "./types";

export function fetchInboxSummary() {
  return apiRequest<NotificationInboxSummary>("/notifications/inbox/summary/");
}

export function fetchInbox() {
  return apiRequest<PagedResponse<NotificationInboxItem>>("/notifications/inbox/");
}

export function fetchInboxTasks() {
  return apiRequest<PagedResponse<NotificationInboxItem>>("/notifications/inbox/tasks/");
}

export function markInboxItemRead(id: string) {
  return apiRequest<NotificationInboxItem>(`/notifications/inbox/${id}/read/`, {
    method: "POST",
  });
}

export function resolveInboxTask(id: string, taskStatus: string, comment = "") {
  return apiRequest<NotificationInboxItem>(`/notifications/inbox/${id}/resolve/`, {
    method: "POST",
    body: {
      task_status: taskStatus,
      comment,
    },
  });
}
