import type { CurrentUser } from "../api/types";

const MANAGEMENT_ROLES = new Set(["ADMINISTRADOR", "SUPERVISOR", "CALIDAD", "INGENIERIA"]);
const ADMIN_PERMISSIONS = new Set(["accounts.add_user", "accounts.change_user", "audit.view_auditevent"]);
const ADMIN_ACCESS_LEVELS = new Set(["administrador", "desarrollador"]);

export function isAdminUser(user: CurrentUser | null | undefined) {
  if (!user) {
    return false;
  }

  if (ADMIN_ACCESS_LEVELS.has(user.access_level)) {
    return true;
  }

  return user.role_codes.some((role) => role.toUpperCase() === "ADMINISTRADOR") || user.permissions.some((permission) => ADMIN_PERMISSIONS.has(permission));
}

export function isManagementUser(user: CurrentUser | null | undefined) {
  if (!user) {
    return false;
  }

  if (isAdminUser(user)) {
    return true;
  }

  return user.role_codes.some((role) => MANAGEMENT_ROLES.has(role.toUpperCase()));
}
