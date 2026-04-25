import { apiRequest } from "./http";
import type {
  CurrentUser,
  LoginResponse,
  PagedResponse,
  UserAccessOptions,
  UserAccessProfile,
  UserAccessProfilePayload,
  UserDirectoryItem,
  UserWritePayload,
} from "./types";

export function login(identifier: string, password: string) {
  return apiRequest<LoginResponse>("/accounts/login/", {
    method: "POST",
    skipAuth: true,
    body: { identifier, password },
  });
}

export function fetchCurrentUser() {
  return apiRequest<CurrentUser>("/accounts/me/");
}

export function logout(refresh: string) {
  return apiRequest<void>("/accounts/logout/", {
    method: "POST",
    body: { refresh },
  });
}

export function changeOwnPassword(payload: { current_password: string; new_password: string; confirm_password: string }) {
  return apiRequest<CurrentUser>("/accounts/change-password/", {
    method: "POST",
    body: payload,
  });
}

export function fetchUsers(params: { active?: boolean; q?: string; page?: number; pageSize?: number } = {}) {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.pageSize ?? 100));

  if (typeof params.active === "boolean") {
    query.set("active", String(params.active));
  }
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }

  return apiRequest<PagedResponse<UserDirectoryItem>>(`/accounts/users/?${query.toString()}`);
}

export function createUser(payload: UserWritePayload) {
  return apiRequest<UserDirectoryItem>("/accounts/users/", {
    method: "POST",
    body: payload,
  });
}

export function updateUser(userId: string, payload: UserWritePayload) {
  return apiRequest<UserDirectoryItem>(`/accounts/users/${userId}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteUser(userId: string) {
  return apiRequest<void>(`/accounts/users/${userId}/`, {
    method: "DELETE",
  });
}

export function fetchUserAccessOptions() {
  return apiRequest<UserAccessOptions>("/accounts/users/access-options/");
}

export function fetchUserAccessProfile(userId: string) {
  return apiRequest<UserAccessProfile>(`/accounts/users/${userId}/access-profile/`);
}

export function updateUserAccessProfile(userId: string, payload: UserAccessProfilePayload) {
  return apiRequest<UserAccessProfile>(`/accounts/users/${userId}/access-profile/`, {
    method: "PATCH",
    body: payload,
  });
}
