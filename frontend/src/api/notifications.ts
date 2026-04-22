import { apiRequest } from "./http";
import type { NotificationInboxItem, NotificationInboxSummary, PagedResponse } from "./types";

export function fetchInboxSummary() {
  return apiRequest<NotificationInboxSummary>("/notifications/inbox/summary/");
}

export function fetchInbox(page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  return apiRequest<PagedResponse<NotificationInboxItem>>(`/notifications/inbox/?${params.toString()}`);
}

export function fetchInboxTasks(page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  return apiRequest<PagedResponse<NotificationInboxItem>>(`/notifications/inbox/tasks/?${params.toString()}`);
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