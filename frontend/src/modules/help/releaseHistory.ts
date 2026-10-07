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
    version: "1.0.0",
    date: "2026-09-24",
    status: "production",
    statusLabel: "Despliegue autorizado del sistema",
    summary: ["Despliegue autorizado del sistema el 24/09/2026."],
    commit: "0919ca3",
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

const RELEASE_SUMMARIES: Record<string, string[]> = {
  "release-1.8.0": [
    "Los archivos adjuntos son opcionales para finalizar acciones de Observación y validar su eficacia.",
    "Las acciones de Tratamiento pueden editarse y cambiar de estado sin archivos; la nota de cada cambio sigue siendo obligatoria.",
    "Se actualizaron formularios y ayudas. La importación masiva conserva su archivo de datos obligatorio.",
  ],
  "release-1.7.3": [
    "Se corrigieron los tipos del frontend en usuarios, filtros, navegación, confirmación de anomalías y métodos de tratamiento.",
    "La comprobación del frontend ahora revisa realmente los archivos de la aplicación y detecta errores de TypeScript durante la compilación.",
  ],
  "release-1.7.2": [
    "Se corrigió la carga de Lecciones aprendidas de Observaciones al quitar una referencia a un filtro inexistente.",
  ],
  "release-1.7.1": [
    "Las áreas de texto de tratamientos, anomalías, acciones, validaciones y lecciones aprendidas comienzan compactas y crecen con el contenido.",
    "Revisión de hallazgos muestra Observación / Motivo en todas las clasificaciones y conserva el texto en el historial.",
    "Se compactó el comentario al confirmar una No Conformidad y se quitaron rótulos redundantes en Observación.",
  ],
  "release-1.7.0": [
    "Los vencimientos comienzan al día siguiente de la fecha límite y dejan de mostrarse al cambiar de estado.",
    "Los correos de vencimiento se dirigen al responsable actual de cada tratamiento, acción o verificación.",
    "El historial usa una frase única cuando una actividad deja de figurar como vencida.",
  ],
};

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
  return decorations.match(/(?:^|, )tag: (release-\d+\.\d+\.\d+)(?=,|$)/)?.[1];
}

const automatedHistory: ReleaseHistoryEntry[] = __APP_BUILD_INFO__.history.map((entry, index) => {
  const status = index === 0
    ? currentStatus()
    : { status: "versioned" as const, statusLabel: "Versionada en Git" };
  const version = releaseTag(entry.decorations) ?? `commit-${entry.shortCommit}`;
  return {
    version,
    date: entry.date.slice(0, 10),
    ...status,
    summary: RELEASE_SUMMARIES[version] ?? [entry.subject],
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
