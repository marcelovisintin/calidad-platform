import { readStoredSession } from "./http";

export function normalizeProtectedFileUrl(fileUrl: string) {
  if (!fileUrl) {
    return "#";
  }

  const trimmed = fileUrl.trim();
  if (!trimmed) {
    return "#";
  }

  if (trimmed.startsWith("/")) {
    return trimmed;
  }

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    try {
      const parsed = new URL(trimmed);
      const hostname = parsed.hostname.toLowerCase();
      if (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1") {
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
      }
      return parsed.toString();
    } catch {
      return trimmed;
    }
  }

  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

function extractFilename(contentDisposition: string | null, fallback: string) {
  if (!contentDisposition) {
    return fallback;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const regularMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return regularMatch?.[1] || fallback;
}

export async function openAuthenticatedFile(rawFileUrl: string, fallbackName = "evidencia") {
  const fileUrl = normalizeProtectedFileUrl(rawFileUrl);
  if (!fileUrl || fileUrl === "#") {
    throw new Error("La evidencia no tiene una URL valida.");
  }

  const session = readStoredSession();
  if (!session?.access) {
    throw new Error("Tu sesion vencio. Inicia sesion nuevamente para abrir evidencias.");
  }

  const response = await fetch(fileUrl, {
    method: "GET",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${session.access}`,
    },
  });

  if (!response.ok) {
    throw new Error(`No se pudo abrir la evidencia. HTTP ${response.status}.`);
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const contentType = (response.headers.get("content-type") || blob.type || "").toLowerCase();
  const canPreview = contentType.startsWith("image/") || contentType.includes("pdf") || contentType.startsWith("text/");

  if (canPreview) {
    window.open(blobUrl, "_blank", "noopener,noreferrer");
  } else {
    const tempLink = document.createElement("a");
    tempLink.href = blobUrl;
    tempLink.download = extractFilename(response.headers.get("content-disposition"), fallbackName);
    document.body.appendChild(tempLink);
    tempLink.click();
    tempLink.remove();
  }

  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

export async function createAuthenticatedObjectUrl(rawFileUrl: string) {
  const fileUrl = normalizeProtectedFileUrl(rawFileUrl);
  if (!fileUrl || fileUrl === "#") {
    return "";
  }

  const session = readStoredSession();
  if (!session?.access) {
    return "";
  }

  const response = await fetch(fileUrl, {
    method: "GET",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${session.access}`,
    },
  });

  if (!response.ok) {
    return "";
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
