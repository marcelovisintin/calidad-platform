import { useEffect, useRef } from "react";
import type { HelpTopic } from "../helpContent";
import type { HelpWorkContext } from "../workContext";

type ContextualHelpDrawerProps = {
  contextLabel: string;
  open: boolean;
  topic: HelpTopic;
  onClose: () => void;
  onStartTour?: () => void;
  workContext?: HelpWorkContext | null;
};

export function ContextualHelpDrawer({ contextLabel, open, topic, onClose, onStartTour, workContext }: ContextualHelpDrawerProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="context-help-layer open"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      role="presentation"
    >
      <aside
        aria-labelledby="context-help-title"
        aria-modal="true"
        className="context-help-drawer"
        id="contextual-help-drawer"
        role="dialog"
      >
        <header className="context-help-header">
          <div>
            <span className="context-help-kicker">Ayuda de esta pantalla</span>
            <strong>{contextLabel}</strong>
          </div>
          <button
            aria-label="Cerrar ayuda"
            className="button button-secondary context-help-close"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            Cerrar
          </button>
        </header>

        <div className="context-help-body">
          <div className="context-help-intro">
            <span className="help-topic-category">{topic.category}</span>
            <h2 id="context-help-title">{topic.title}</h2>
            <p>{topic.summary}</p>
          </div>

          {workContext ? (
            <section className={`help-work-context ${workContext.tone ?? "info"}`}>
              <div className="help-work-context-heading">
                <div>
                  <span className="context-help-kicker">Orientación operativa</span>
                  <h3>¿Qué debo hacer ahora?</h3>
                </div>
                <span className="help-work-live">Contexto actual</span>
              </div>
              {workContext.recordLabel ? <strong className="help-work-record">{workContext.recordLabel}</strong> : null}
              <dl className="help-work-grid">
                <div><dt>Estado</dt><dd>{workContext.status}</dd></div>
                <div><dt>Etapa</dt><dd>{workContext.stage}</dd></div>
                <div className="help-work-responsible"><dt>Responsable</dt><dd>{workContext.responsible}</dd></div>
              </dl>
              <div className="help-work-next">
                <span>Próximo paso</span>
                <p>{workContext.nextAction}</p>
              </div>
              {workContext.blockers.length ? (
                <div className="help-work-blockers">
                  <strong>Condiciones pendientes</strong>
                  <ul>
                    {workContext.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
                  </ul>
                </div>
              ) : (
                <p className="help-work-clear">No hay bloqueos informados para este contexto.</p>
              )}
            </section>
          ) : null}

          {topic.sections.map((section) => (
            <section className="context-help-section" key={section.title}>
              <h3>{section.title}</h3>
              {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              {section.bullets ? (
                <ul>
                  {section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                </ul>
              ) : null}
              {section.steps ? (
                <ol>
                  {section.steps.map((step) => <li key={step}>{step}</li>)}
                </ol>
              ) : null}
              {section.note ? <div className="help-note"><strong>Importante:</strong> {section.note}</div> : null}
            </section>
          ))}
        </div>

        <footer className="context-help-footer">
          {onStartTour ? (
            <button className="button button-primary" onClick={onStartTour} type="button">
              Iniciar recorrido
            </button>
          ) : null}
          <a
            className="button button-secondary"
            href={`/help?topic=${encodeURIComponent(topic.id)}`}
            rel="noreferrer"
            target="_blank"
          >
            Abrir guía en otra pestaña
          </a>
          <button className="button button-ghost" onClick={onClose} type="button">
            Continuar trabajando
          </button>
        </footer>
      </aside>
    </div>
  );
}
