import { appConfig } from "../app/config";
import type { LoginResponse } from "./types";

const SESSION_KEY = appConfig.sessionStorageKey;

type StoredSession = {
  access: string;
  refresh: string;
};

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | object | null;
  skipAuth?: boolean;
};

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

let unauthorizedHandler: (() => void) | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export function readStoredSession(): StoredSession | null {
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed.access || !parsed.refresh) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeStoredSession(session: StoredSession) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearStoredSession() {
  window.localStorage.removeItem(SESSION_KEY);
}

function isFormData(value: unknown): value is FormData {
  return typeof FormData !== "undefined" && value instanceof FormData;
}

function buildUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (path.startsWith("/")) {
    return `${appConfig.apiBaseUrl}${path}`;
  }
  return `${appConfig.apiBaseUrl}/${path}`;
}

function generateRequestId() {
  if (typeof crypto !== "undefined") {
    if (typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }

    if (typeof crypto.getRandomValues === "function") {
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
  }

  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function stringifyValidationValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => stringifyValidationValue(item)).filter(Boolean).join(", ");
  }
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object" && "detail" in value) {
    return String((value as { detail?: unknown }).detail ?? "");
  }
  return "";
}

function extractErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "object" && payload && "detail" in payload) {
    return String((payload as { detail?: unknown }).detail ?? `Error HTTP ${status}`);
  }

  if (typeof payload === "object" && payload && !Array.isArray(payload)) {
    const messages = Object.entries(payload as Record<string, unknown>)
      .map(([field, value]) => {
        const detail = stringifyValidationValue(value);
        return detail ? `${field}: ${detail}` : "";
      })
      .filter(Boolean);

    if (messages.length) {
      return messages.join(" | ");
    }
  }

  if (typeof payload === "string" && payload) {
    return payload;
  }

  return `Error HTTP ${status}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload, response.status), response.status, payload);
  }

  return payload as T;
}

async function refreshAccessToken(): Promise<string | null> {
  const session = readStoredSession();
  if (!session?.refresh) {
    clearStoredSession();
    return null;
  }

  const response = await fetch(buildUrl("/accounts/refresh/"), {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ refresh: session.refresh }),
  });

  if (!response.ok) {
    clearStoredSession();
    return null;
  }

  const payload = (await response.json()) as Partial<LoginResponse> & { access: string; refresh?: string };
  const nextSession = {
    access: payload.access,
    refresh: payload.refresh ?? session.refresh,
  };
  writeStoredSession(nextSession);
  return nextSession.access;
}

async function authorizedFetch<T>(path: string, options: RequestOptions, retryOnUnauthorized = true): Promise<T> {
  const session = readStoredSession();
  const headers = new Headers(options.headers ?? {});
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", generateRequestId());

  if (!options.skipAuth && session?.access) {
    headers.set("Authorization", `Bearer ${session.access}`);
  }

  let body: BodyInit | undefined;
  if (typeof options.body !== "undefined" && options.body !== null) {
    if (isFormData(options.body)) {
      body = options.body;
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    cache: options.cache ?? "no-store",
    headers,
    body,
  });

  if (response.status === 401 && !options.skipAuth && retryOnUnauthorized && session?.refresh) {
    refreshInFlight ??= refreshAccessToken().finally(() => {
      refreshInFlight = null;
    });

    const nextAccess = await refreshInFlight;
    if (nextAccess) {
      return authorizedFetch<T>(path, options, false);
    }
    unauthorizedHandler?.();
  }

  if (response.status === 401) {
    unauthorizedHandler?.();
  }

  return parseResponse<T>(response);
}

export function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return authorizedFetch<T>(path, options);
}
