const CACHE_NAME = "calidad-platform-shell-v3";
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-maskable.svg"
];
const APP_SHELL_PATHS = new Set(APP_SHELL);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  if (
    requestUrl.pathname.startsWith("/api/") ||
    requestUrl.pathname.startsWith("/media/") ||
    requestUrl.pathname === "/version.json" ||
    requestUrl.pathname === "/update-status.json"
  ) {
    return;
  }

  const isHtmlNavigation = event.request.mode === "navigate";
  const isPublicAsset =
    APP_SHELL_PATHS.has(requestUrl.pathname) ||
    requestUrl.pathname.startsWith("/assets/") ||
    requestUrl.pathname.startsWith("/icons/");

  if (!isHtmlNavigation && !isPublicAsset) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && isPublicAsset) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then(async (cached) => {
          if (cached) {
            return cached;
          }
          if (isHtmlNavigation) {
            return (await caches.match("/")) || Response.error();
          }
          return Response.error();
        })
      )
  );
});
