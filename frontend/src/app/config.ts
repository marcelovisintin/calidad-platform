export const appConfig = {
  appName: "Calidad Platform",
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, ""),
  catalogBootstrapUrl: import.meta.env.VITE_CATALOG_BOOTSTRAP_URL ?? "/catalog.bootstrap.json",
  sessionStorageKey: "calidad-platform.session",
};
