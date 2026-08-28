import { apiRequest } from "./http";
import type { NotificationInboxItem, NotificationInboxSummary, PagedResponse } from "./types";

export function fetchInboxSummary() {
  return apiRequest<NotificationInboxSummary>("/notifications/inbox/summary/");
}

export function fetchInbox(
  page = 1,
  filters: { isTask?: boolean; unread?: boolean; unreadFirst?: boolean; search?: string } = {},
) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (filters.isTask !== undefined) {
    params.set("is_task", String(filters.isTask));
  }
  if (filters.unread !== undefined) {
    params.set("unread", String(filters.unread));
  }
  if (filters.unreadFirst) {
    params.set("unread_first", "true");
  }
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  return apiRequest<PagedResponse<NotificationInboxItem>>(`/notifications/inbox/?${params.toString()}`);
}

export function fetchInboxTasks(page = 1, taskStatus?: string) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (taskStatus?.trim()) {
    params.set("task_status", taskStatus.trim());
  }
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
