import type { CurrentUser } from "../api/types";

const ADMIN_ACCESS_LEVELS = new Set(["administrador", "desarrollador"]);
const MANAGEMENT_ACCESS_LEVELS = new Set(["mando_medio_activo", "administrador", "desarrollador"]);

export function isAdminUser(user: CurrentUser | null | undefined) {
  if (!user) {
    return false;
  }

  return ADMIN_ACCESS_LEVELS.has(user.access_level);
}

export function isManagementUser(user: CurrentUser | null | undefined) {
  if (!user) {
    return false;
  }

  return MANAGEMENT_ACCESS_LEVELS.has(user.access_level);
}

export function getDefaultLandingPath(user: CurrentUser | null | undefined) {
  return isAdminUser(user) ? "/dashboard" : "/anomalies/new";
}
