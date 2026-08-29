export type HelpProgress = {
  readTopicIds: string[];
  completedTourIds: string[];
  updatedAt: string | null;
};

const STORAGE_PREFIX = "quality-help-progress";

function emptyProgress(): HelpProgress {
  return { readTopicIds: [], completedTourIds: [], updatedAt: null };
}

function storageKey(userId?: string | null) {
  return `${STORAGE_PREFIX}:${userId || "anonymous"}`;
}

function uniqueStrings(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return [...new Set(value.filter((item): item is string => typeof item === "string" && item.length > 0))];
}

export function readHelpProgress(userId?: string | null): HelpProgress {
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    if (!raw) {
      return emptyProgress();
    }
    const parsed = JSON.parse(raw) as Partial<HelpProgress>;
    return {
      readTopicIds: uniqueStrings(parsed.readTopicIds),
      completedTourIds: uniqueStrings(parsed.completedTourIds),
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : null,
    };
  } catch {
    return emptyProgress();
  }
}

function writeHelpProgress(userId: string | null | undefined, progress: HelpProgress) {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(progress));
  } catch {
    // La ayuda sigue funcionando aunque el navegador no permita almacenamiento local.
  }
  return progress;
}

export function markHelpTopicRead(userId: string | null | undefined, topicId: string) {
  const current = readHelpProgress(userId);
  if (current.readTopicIds.includes(topicId)) {
    return current;
  }
  return writeHelpProgress(userId, {
    ...current,
    readTopicIds: [...current.readTopicIds, topicId],
    updatedAt: new Date().toISOString(),
  });
}

export function markHelpTourCompleted(userId: string | null | undefined, tourId: string) {
  const current = readHelpProgress(userId);
  if (current.completedTourIds.includes(tourId)) {
    return current;
  }
  return writeHelpProgress(userId, {
    ...current,
    completedTourIds: [...current.completedTourIds, tourId],
    updatedAt: new Date().toISOString(),
  });
}

export function clearHelpProgress(userId?: string | null) {
  try {
    window.localStorage.removeItem(storageKey(userId));
  } catch {
    // Sin efecto si el navegador bloquea el almacenamiento local.
  }
  return emptyProgress();
}
