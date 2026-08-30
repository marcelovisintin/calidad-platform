export type ReleaseStatus = "preparation" | "versioned" | "production";

export type ReleaseHistoryEntry = {
  version: string;
  date: string;
  status: ReleaseStatus;
  statusLabel: string;
  summary: string[];
  commit: string;
  responsible: string;
};

export const RELEASE_HISTORY: ReleaseHistoryEntry[] = [
  {
    version: "release-2026-08-30.1",
    date: "2026-08-30",
    status: "preparation",
    statusLabel: "En preparación local",
    summary: [
      "Incorporación del Centro de Ayuda, ayuda contextual, recorridos interactivos y progreso personal.",
      "Indicadores, reportes por correo y Resumen rápido con orientación específica.",
      "Simplificación del Panel de gestión y alineación de sus accesos con el menú lateral.",
      "Incorporación de Acerca de y del historial controlado de versiones.",
    ],
    commit: "d2d52b2 + cambios locales",
    responsible: "Marcelo",
  },
  {
    version: "release-2026-08-28.2",
    date: "2026-08-28",
    status: "versioned",
    statusLabel: "Versionada en Git",
    summary: ["Unificación de Bandeja y pendientes, con navegación ajustada por nivel de acceso."],
    commit: "4b4b1b2",
    responsible: "Marcelo",
  },
  {
    version: "release-2026-08-28.1",
    date: "2026-08-28",
    status: "versioned",
    statusLabel: "Versionada en Git",
    summary: ["Ajuste de visibilidad de navegación y filtros de usuarios."],
    commit: "e0ea9ff",
    responsible: "Marcelo",
  },
  {
    version: "release-2026-08-27.1",
    date: "2026-08-27",
    status: "versioned",
    statusLabel: "Versionada en Git",
    summary: ["Mejoras en acciones de tratamientos y presentación compacta de catálogos."],
    commit: "f5983e3",
    responsible: "Marcelo",
  },
  {
    version: "release-2026-08-26.2",
    date: "2026-08-26",
    status: "versioned",
    statusLabel: "Versionada en Git",
    summary: ["Restauración y verificación de la ejecución del sistema de backups."],
    commit: "1ccafd3",
    responsible: "Marcelo",
  },
  {
    version: "release-2026-08-26.1",
    date: "2026-08-26",
    status: "versioned",
    statusLabel: "Versionada en Git",
    summary: ["Finalización del flujo de tratamientos y de la política de notificaciones por correo."],
    commit: "da7794a",
    responsible: "Marcelo",
  },
];

export const CURRENT_RELEASE = RELEASE_HISTORY[0];
