import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { GuidedTourDefinition, GuidedTourStep } from "../guidedTours";

type GuidedTourOverlayProps = {
  open: boolean;
  tour: GuidedTourDefinition;
  onFinish: (completed: boolean) => void;
};

type TargetRect = {
  top: number;
  left: number;
  width: number;
  height: number;
  bottom: number;
};

const HIGHLIGHT_MARGIN = 6;
const TOOLTIP_WIDTH = 390;
const TOOLTIP_GAP = 14;

function findAvailableSteps(steps: GuidedTourStep[]) {
  return steps.filter((step) => document.querySelector(step.selector));
}

export function GuidedTourOverlay({ open, tour, onFinish }: GuidedTourOverlayProps) {
  const [steps, setSteps] = useState<GuidedTourStep[]>([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const nextButtonRef = useRef<HTMLButtonElement>(null);
  const currentStep = steps[stepIndex];

  useEffect(() => {
    if (!open) {
      setSteps([]);
      setStepIndex(0);
      setTargetRect(null);
      return;
    }

    const available = findAvailableSteps(tour.steps);
    if (!available.length) {
      onFinish(false);
      return;
    }
    setSteps(available);
    setStepIndex(0);
  }, [onFinish, open, tour]);

  useEffect(() => {
    if (!open || !currentStep) {
      return;
    }

    const target = document.querySelector<HTMLElement>(currentStep.selector);
    if (!target) {
      return;
    }

    const updateRect = () => {
      const rect = target.getBoundingClientRect();
      setTargetRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height, bottom: rect.bottom });
    };

    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    updateRect();
    const settleTimer = window.setTimeout(updateRect, 320);
    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);
    nextButtonRef.current?.focus();

    return () => {
      window.clearTimeout(settleTimer);
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [currentStep, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onFinish(false);
      }
      if (event.key === "ArrowRight" && stepIndex < steps.length - 1) {
        setStepIndex((current) => current + 1);
      }
      if (event.key === "ArrowLeft" && stepIndex > 0) {
        setStepIndex((current) => current - 1);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onFinish, open, stepIndex, steps.length]);

  const tooltipStyle = useMemo<CSSProperties>(() => {
    if (!targetRect) {
      return { visibility: "hidden" };
    }
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(TOOLTIP_WIDTH, viewportWidth - 24);
    const left = Math.max(12, Math.min(targetRect.left, viewportWidth - width - 12));
    const estimatedHeight = 245;
    const canPlaceBelow = targetRect.bottom + TOOLTIP_GAP + estimatedHeight < viewportHeight;
    const top = canPlaceBelow
      ? targetRect.bottom + TOOLTIP_GAP
      : Math.max(12, targetRect.top - estimatedHeight - TOOLTIP_GAP);
    return { left, top, width };
  }, [targetRect]);

  if (!open || !currentStep || !targetRect) {
    return null;
  }

  const lastStep = stepIndex === steps.length - 1;

  return (
    <div className="guided-tour-layer" role="presentation">
      <div className="guided-tour-interaction-guard" />
      <div
        aria-hidden="true"
        className="guided-tour-highlight"
        style={{
          top: targetRect.top - HIGHLIGHT_MARGIN,
          left: targetRect.left - HIGHLIGHT_MARGIN,
          width: targetRect.width + HIGHLIGHT_MARGIN * 2,
          height: targetRect.height + HIGHLIGHT_MARGIN * 2,
        }}
      />
      <section
        aria-label={`Recorrido ${tour.title}`}
        aria-live="polite"
        aria-modal="true"
        className="guided-tour-tooltip"
        role="dialog"
        style={tooltipStyle}
      >
        <div className="guided-tour-progress">
          <span>{tour.title}</span>
          <strong>{stepIndex + 1} / {steps.length}</strong>
        </div>
        <h2>{currentStep.title}</h2>
        <p>{currentStep.content}</p>
        <div aria-hidden="true" className="guided-tour-progress-bar">
          <span style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }} />
        </div>
        <div className="guided-tour-actions">
          <button className="button button-ghost" onClick={() => onFinish(false)} type="button">Salir</button>
          <div>
            {stepIndex > 0 ? (
              <button className="button button-secondary" onClick={() => setStepIndex((current) => current - 1)} type="button">
                Anterior
              </button>
            ) : null}
            <button
              className="button button-primary"
              onClick={() => lastStep ? onFinish(true) : setStepIndex((current) => current + 1)}
              ref={nextButtonRef}
              type="button"
            >
              {lastStep ? "Finalizar" : "Siguiente"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
