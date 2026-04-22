import { appConfig } from "../app/config";
import { apiRequest } from "./http";
import type { CatalogBootstrap, CatalogEntity, CatalogManagementItem, PagedResponse } from "./types";

const EMPTY_BOOTSTRAP: CatalogBootstrap = {
  sites: [],
  areas: [],
  anomalyTypes: [],
  anomalyOrigins: [],
  severities: [],
  priorities: [],
  actionTypes: [],
};

function normalizeBootstrap(payload: Partial<CatalogBootstrap>): CatalogBootstrap {
  return {
    ...EMPTY_BOOTSTRAP,
    ...payload,
    sites: payload.sites ?? [],
    areas: payload.areas ?? [],
    anomalyTypes: payload.anomalyTypes ?? [],
    anomalyOrigins: payload.anomalyOrigins ?? [],
    severities: payload.severities ?? [],
    priorities: payload.priorities ?? [],
    actionTypes: payload.actionTypes ?? [],
  };
}

async function fetchStaticBootstrap(): Promise<CatalogBootstrap> {
  try {
    const response = await fetch(appConfig.catalogBootstrapUrl, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return EMPTY_BOOTSTRAP;
    }

    const payload = (await response.json()) as Partial<CatalogBootstrap>;
    return normalizeBootstrap(payload);
  } catch {
    return EMPTY_BOOTSTRAP;
  }
}

export async function fetchCatalogBootstrap(): Promise<CatalogBootstrap> {
  try {
    const payload = await apiRequest<Partial<CatalogBootstrap>>("/catalog/bootstrap/", { skipAuth: true });
    return normalizeBootstrap(payload);
  } catch {
    return fetchStaticBootstrap();
  }
}

export function fetchCatalogItems(
  entity: CatalogEntity,
  params: { active?: boolean; q?: string; page?: number; pageSize?: number } = {},
) {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.pageSize ?? 100));

  if (typeof params.active === "boolean") {
    query.set("active", String(params.active));
  }
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }

  return apiRequest<PagedResponse<CatalogManagementItem>>(`/catalog/${entity}/?${query.toString()}`);
}

export function createCatalogItem(entity: CatalogEntity, payload: Record<string, unknown>) {
  return apiRequest<CatalogManagementItem>(`/catalog/${entity}/`, {
    method: "POST",
    body: payload,
  });
}

export function updateCatalogItem(entity: CatalogEntity, itemId: string, payload: Record<string, unknown>) {
  return apiRequest<CatalogManagementItem>(`/catalog/${entity}/${itemId}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteCatalogItem(entity: CatalogEntity, itemId: string) {
  return apiRequest<void>(`/catalog/${entity}/${itemId}/`, {
    method: "DELETE",
  });
}