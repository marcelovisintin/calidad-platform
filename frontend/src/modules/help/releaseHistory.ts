export type ReleaseStatus = "preparation" | "versioned" | "production";

export type ReleaseHistoryEntry = {
  version: string;
  date: string;
  status: ReleaseStatus;
  statusLabel: string;
  summary: string[];
  commit: string;
  responsible: string;
  branch?: string;
};

const HISTORICAL_RELEASES: ReleaseHistoryEntry[] = [
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

function currentStatus(): Pick<ReleaseHistoryEntry, "status" | "statusLabel"> {
  if (__APP_BUILD_INFO__.dirty) {
    return { status: "preparation", statusLabel: "En preparación local" };
  }
  if (__APP_BUILD_INFO__.environment === "production") {
    return { status: "production", statusLabel: "Desplegada en producción" };
  }
  return { status: "versioned", statusLabel: "Versionada en Git" };
}

function releaseTag(decorations: string) {
  return decorations.match(/(?:^|, )tag: (release-[^,]+)/)?.[1];
}

const automatedHistory: ReleaseHistoryEntry[] = __APP_BUILD_INFO__.history.map((entry, index) => {
  const status = index === 0
    ? currentStatus()
    : { status: "versioned" as const, statusLabel: "Versionada en Git" };
  return {
    version: releaseTag(entry.decorations) ?? `commit-${entry.shortCommit}`,
    date: entry.date.slice(0, 10),
    ...status,
    summary: [entry.subject],
    commit: entry.shortCommit,
    responsible: entry.author,
    branch: index === 0 ? __APP_BUILD_INFO__.branch : undefined,
  };
});

const knownCommits = new Set(automatedHistory.map((entry) => entry.commit));

export const RELEASE_HISTORY: ReleaseHistoryEntry[] = [
  ...automatedHistory,
  ...HISTORICAL_RELEASES.filter((entry) => !knownCommits.has(entry.commit)),
];

export const CURRENT_RELEASE = RELEASE_HISTORY[0] ?? {
  version: "compilación-sin-git",
  date: __APP_BUILD_INFO__.buildDate.slice(0, 10),
  ...currentStatus(),
  summary: ["No se pudo obtener el historial de Git durante la compilación."],
  commit: __APP_BUILD_INFO__.shortCommit,
  responsible: "Sistema",
  branch: __APP_BUILD_INFO__.branch,
};
