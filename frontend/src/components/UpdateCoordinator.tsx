import { useEffect, useRef, useState } from "react";

type UpdatePhase = "idle" | "updating" | "updated" | "waiting";

type VersionPayload = {
  version?: string;
};

type DeploymentStatusPayload = {
  status?: "updating" | "ready" | "failed";
};

const POLL_INTERVAL_MS = 5_000;
const UPDATED_MESSAGE_MS = 2_000;
const MUTATION_SETTLE_MS = 800;

function isEditableControl(target: EventTarget | null): target is HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement {
  return target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${path}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function activateLatestServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const registrations = await navigator.serviceWorker.getRegistrations();
  await Promise.all(
    registrations.map(async (registration) => {
      await registration.update();
      registration.waiting?.postMessage({ type: "SKIP_WAITING" });
    }),
  );
}

export function UpdateCoordinator() {
  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const dirtyFormsRef = useRef(new Set<HTMLFormElement>());
  const submittedFormsRef = useRef(new Set<HTMLFormElement>());
  const activeMutationsRef = useRef(0);
  const mutationFailedRef = useRef(false);
  const settleTimerRef = useRef<number | null>(null);
  const reloadTimerRef = useRef<number | null>(null);
  const consecutiveFailuresRef = useRef(0);
  const updateDetectedRef = useRef(false);
  const unsavedRef = useRef(false);

  useEffect(() => {
    unsavedRef.current = hasUnsavedChanges;
  }, [hasUnsavedChanges]);

  useEffect(() => {
    const updateDirtyState = () => {
      for (const form of dirtyFormsRef.current) {
        if (!form.isConnected) {
          dirtyFormsRef.current.delete(form);
          submittedFormsRef.current.delete(form);
        }
      }
      setHasUnsavedChanges(dirtyFormsRef.current.size > 0 || activeMutationsRef.current > 0);
    };

    const handleEdit = (event: Event) => {
      if (!isEditableControl(event.target) || event.target.disabled) {
        return;
      }
      const form = event.target.form;
      if (!form || form.dataset.updateIgnore === "true") {
        return;
      }
      dirtyFormsRef.current.add(form);
      updateDirtyState();
    };

    const handleSubmit = (event: Event) => {
      if (event.target instanceof HTMLFormElement && dirtyFormsRef.current.has(event.target)) {
        submittedFormsRef.current.add(event.target);
      }
    };

    const handleReset = (event: Event) => {
      if (!(event.target instanceof HTMLFormElement)) {
        return;
      }
      const form = event.target;
      window.setTimeout(() => {
        dirtyFormsRef.current.delete(form);
        submittedFormsRef.current.delete(form);
        updateDirtyState();
      }, 0);
    };

    const handleMutationStart = () => {
      if (settleTimerRef.current !== null) {
        window.clearTimeout(settleTimerRef.current);
        settleTimerRef.current = null;
      }
      activeMutationsRef.current += 1;
      updateDirtyState();
    };

    const handleMutationEnd = (event: Event) => {
      const succeeded = (event as CustomEvent<{ succeeded?: boolean }>).detail?.succeeded === true;
      mutationFailedRef.current ||= !succeeded;
      activeMutationsRef.current = Math.max(0, activeMutationsRef.current - 1);

      if (activeMutationsRef.current > 0) {
        updateDirtyState();
        return;
      }

      settleTimerRef.current = window.setTimeout(() => {
        if (!mutationFailedRef.current) {
          for (const form of submittedFormsRef.current) {
            dirtyFormsRef.current.delete(form);
          }
          submittedFormsRef.current.clear();
        }
        mutationFailedRef.current = false;
        settleTimerRef.current = null;
        updateDirtyState();
      }, MUTATION_SETTLE_MS);
    };

    document.addEventListener("input", handleEdit, true);
    document.addEventListener("change", handleEdit, true);
    document.addEventListener("submit", handleSubmit, true);
    document.addEventListener("reset", handleReset, true);
    window.addEventListener("calidad:mutation-start", handleMutationStart);
    window.addEventListener("calidad:mutation-end", handleMutationEnd);

    const observer = new MutationObserver(updateDirtyState);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      document.removeEventListener("input", handleEdit, true);
      document.removeEventListener("change", handleEdit, true);
      document.removeEventListener("submit", handleSubmit, true);
      document.removeEventListener("reset", handleReset, true);
      window.removeEventListener("calidad:mutation-start", handleMutationStart);
      window.removeEventListener("calidad:mutation-end", handleMutationEnd);
      observer.disconnect();
      if (settleTimerRef.current !== null) {
        window.clearTimeout(settleTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | null = null;

    const finishDetection = () => {
      setPhase(unsavedRef.current ? "waiting" : "updated");
    };

    const poll = async () => {
      const [deployment, version] = await Promise.all([
        fetchJson<DeploymentStatusPayload>("/update-status.json"),
        fetchJson<VersionPayload>("/version.json"),
      ]);
      if (cancelled) {
        return;
      }

      if (deployment?.status === "updating") {
        updateDetectedRef.current = true;
        consecutiveFailuresRef.current = 0;
        setPhase("updating");
      } else if (version?.version && version.version !== __APP_VERSION__) {
        consecutiveFailuresRef.current = 0;
        if (!updateDetectedRef.current) {
          updateDetectedRef.current = true;
          setPhase("updating");
          window.setTimeout(() => {
            if (!cancelled) {
              finishDetection();
            }
          }, 500);
        } else {
          finishDetection();
        }
      } else if (!version) {
        consecutiveFailuresRef.current += 1;
        if (consecutiveFailuresRef.current >= 2) {
          updateDetectedRef.current = true;
          setPhase("updating");
        }
      } else {
        consecutiveFailuresRef.current = 0;
      }

      pollTimer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      if (pollTimer !== null) {
        window.clearTimeout(pollTimer);
      }
    };
  }, []);

  useEffect(() => {
    if (phase === "waiting" && !hasUnsavedChanges) {
      setPhase("updated");
      return;
    }
    if (phase !== "updated" || hasUnsavedChanges) {
      return;
    }

    reloadTimerRef.current = window.setTimeout(() => {
      void activateLatestServiceWorker().finally(() => {
        window.location.reload();
      });
    }, UPDATED_MESSAGE_MS);

    return () => {
      if (reloadTimerRef.current !== null) {
        window.clearTimeout(reloadTimerRef.current);
        reloadTimerRef.current = null;
      }
    };
  }, [hasUnsavedChanges, phase]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  if (phase === "idle") {
    return null;
  }

  if (phase === "updating") {
    return (
      <div aria-live="assertive" className="update-overlay" role="status">
        <div className="update-dialog">
          <span aria-hidden="true" className="update-spinner" />
          <strong>Actualización en curso</strong>
          <p>Espere por favor. La información que está editando se conservará.</p>
        </div>
      </div>
    );
  }

  if (phase === "waiting") {
    return (
      <div aria-live="polite" className="update-banner update-banner-waiting" role="status">
        <strong>Actualización lista.</strong>
        <span>Guarde los datos que está editando. La página se actualizará automáticamente después.</span>
      </div>
    );
  }

  return (
    <div aria-live="assertive" className="update-overlay update-overlay-complete" role="status">
      <div className="update-dialog">
        <span aria-hidden="true" className="update-check">✓</span>
        <strong>Actualizado</strong>
        <p>El sistema se recargará automáticamente.</p>
      </div>
    </div>
  );
}
