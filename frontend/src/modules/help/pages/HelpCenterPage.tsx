import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isAdminUser, isManagementUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { PageHeader } from "../../../components/PageHeader";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { ABOUT_SYSTEM } from "../aboutInfo";
import { DocumentedInformationGuidePanel } from "../components/DocumentedInformationGuidePanel";
import { RELEASE_HISTORY } from "../releaseHistory";
import {
  HELP_CATEGORY_ORDER,
  HELP_TOPICS,
  HELP_TOPICS_BY_ID,
  type HelpTopic,
} from "../helpContent";
import {
  clearHelpProgress,
  markHelpTopicRead,
  readHelpProgress,
  type HelpProgress,
} from "../helpProgress";

const ALL_CATEGORIES = "Todos los temas";

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function topicSearchText(topic: HelpTopic) {
  return normalizeSearch(
    [
      topic.title,
      topic.summary,
      topic.category,
      ...topic.keywords,
      ...topic.sections.flatMap((section) => [
        section.title,
        ...(section.paragraphs ?? []),
        ...(section.bullets ?? []),
        ...(section.steps ?? []),
        section.note ?? "",
      ]),
    ].join(" "),
  );
}

function HelpTopicCard({
  topic,
  onOpen,
  read,
}: {
  topic: HelpTopic;
  onOpen: (id: string) => void;
  read: boolean;
}) {
  return (
    <button className="help-topic-card" onClick={() => onOpen(topic.id)} type="button">
      <span className="help-topic-card-meta">
        <span className="help-topic-category">{topic.category}</span>
        {read ? <span className="help-topic-read">Consultada</span> : null}
      </span>
      <strong>{topic.title}</strong>
      <span>{topic.summary}</span>
      <span className="help-topic-open">Abrir guía <span aria-hidden="true">→</span></span>
    </button>
  );
}

export function HelpCenterPage() {
  usePageTitle("Ayuda");
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isoHelpOpen, setIsoHelpOpen] = useState(false);
  const [documentGuideOpen, setDocumentGuideOpen] = useState(false);
  const [progress, setProgress] = useState<HelpProgress>(() => readHelpProgress(user?.id));
  const query = searchParams.get("q") ?? "";
  const selectedTopicId = searchParams.get("topic");

  const availableTopics = useMemo(
    () =>
      HELP_TOPICS.filter((topic) => {
        if (topic.audience === "admin") {
          return isAdminUser(user);
        }
        if (topic.audience === "management") {
          return isManagementUser(user);
        }
        return true;
      }),
    [user],
  );
  const availableTopicIds = useMemo(() => new Set(availableTopics.map((topic) => topic.id)), [availableTopics]);
  const selectedTopic = selectedTopicId && availableTopicIds.has(selectedTopicId)
    ? HELP_TOPICS_BY_ID.get(selectedTopicId)
    : undefined;
  const visibleCategories = HELP_CATEGORY_ORDER.filter((item) =>
    availableTopics.some((topic) => topic.category === item),
  );

  const filteredTopics = useMemo(() => {
    const terms = normalizeSearch(query).split(/\s+/).filter(Boolean);
    return availableTopics.filter((topic) => {
      if (category !== ALL_CATEGORIES && topic.category !== category) {
        return false;
      }
      const searchable = topicSearchText(topic);
      return terms.every((term) => searchable.includes(term));
    });
  }, [availableTopics, category, query]);

  const quickTopics = availableTopics.filter((topic) => topic.quick).slice(0, 8);
  const readTopicIds = useMemo(() => new Set(progress.readTopicIds), [progress.readTopicIds]);
  const readTopicCount = availableTopics.filter((topic) => readTopicIds.has(topic.id)).length;
  const progressPercentage = availableTopics.length
    ? Math.round((readTopicCount / availableTopics.length) * 100)
    : 0;
  const continueTopic = availableTopics.find((topic) => topic.quick && !readTopicIds.has(topic.id))
    ?? availableTopics.find((topic) => !readTopicIds.has(topic.id));
  const buildDate = useMemo(() => {
    const date = new Date(ABOUT_SYSTEM.buildDate);
    return Number.isNaN(date.getTime())
      ? ABOUT_SYSTEM.buildDate
      : new Intl.DateTimeFormat("es-AR", { dateStyle: "long", timeStyle: "short" }).format(date);
  }, []);

  useEffect(() => {
    setProgress(readHelpProgress(user?.id));
  }, [user?.id]);

  useEffect(() => {
    if (selectedTopic) {
      setProgress(markHelpTopicRead(user?.id, selectedTopic.id));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [selectedTopic, user?.id]);

  const updateQuery = (value: string) => {
    const next = new URLSearchParams(searchParams);
    next.delete("topic");
    if (value) {
      next.set("q", value);
    } else {
      next.delete("q");
    }
    setSearchParams(next, { replace: true });
  };

  const openTopic = (id: string) => {
    const next = new URLSearchParams();
    next.set("topic", id);
    setSearchParams(next);
  };

  const closeTopic = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("topic");
    setSearchParams(next);
  };

  if (selectedTopic) {
    const relatedTopics = selectedTopic.related
      .filter((id) => availableTopicIds.has(id))
      .map((id) => HELP_TOPICS_BY_ID.get(id))
      .filter((topic): topic is HelpTopic => Boolean(topic));

    return (
      <section className="page-shell help-center-shell">
        <div className="help-article-toolbar">
          <button className="button button-secondary" onClick={closeTopic} type="button">
            ← Volver al Centro de Ayuda
          </button>
          {selectedTopic.route ? (
            <Link className="button button-primary" to={selectedTopic.route}>
              {selectedTopic.routeLabel ?? "Ir a la sección"}
            </Link>
          ) : null}
        </div>

        <article className="help-article">
          <header className="help-article-header">
            <span className="help-topic-category">{selectedTopic.category}</span>
            <h1>{selectedTopic.title}</h1>
            <p>{selectedTopic.summary}</p>
          </header>

          <div className="help-article-content">
            {selectedTopic.sections.map((section) => (
              <section className="help-article-section" key={section.title}>
                <h2>{section.title}</h2>
                {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                {section.bullets ? (
                  <ul>
                    {section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                  </ul>
                ) : null}
                {section.steps ? (
                  <ol className="help-step-list">
                    {section.steps.map((step) => <li key={step}>{step}</li>)}
                  </ol>
                ) : null}
                {section.note ? <div className="help-note"><strong>Importante:</strong> {section.note}</div> : null}
              </section>
            ))}
          </div>
        </article>

        {relatedTopics.length ? (
          <section className="help-related panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Continuar aprendiendo</p>
                <h2>Temas relacionados</h2>
              </div>
            </div>
            <div className="help-related-grid">
              {relatedTopics.map((topic) => (
                <HelpTopicCard key={topic.id} onOpen={openTopic} read={readTopicIds.has(topic.id)} topic={topic} />
              ))}
            </div>
          </section>
        ) : null}
      </section>
    );
  }

  return (
    <section className="page-shell help-center-shell">
      <PageHeader
        title="Centro de Ayuda"
        description="Guías de uso del Sistema de Gestión de Calidad, organizadas según tu nivel de acceso."
        action={(
          <div className="help-header-actions">
            <button
              aria-controls="documented-information-guide"
              aria-expanded={documentGuideOpen}
              className="button button-secondary"
              onClick={() => {
                setDocumentGuideOpen((current) => !current);
                setAboutOpen(false);
                setHistoryOpen(false);
                setIsoHelpOpen(false);
              }}
              type="button"
            >
              {documentGuideOpen ? "Ocultar guía documental" : "Guía de información documentada"}
            </button>
            <button
              aria-controls="about-system-card"
              aria-expanded={aboutOpen}
              className="button button-secondary help-about-toggle"
              onClick={() => {
                setAboutOpen((current) => !current);
                setDocumentGuideOpen(false);
              }}
              type="button"
            >
              Acerca de
            </button>
          </div>
        )}
      />

      {documentGuideOpen ? <DocumentedInformationGuidePanel /> : null}

      {aboutOpen ? (
        <section className="help-about-card" id="about-system-card">
          <div className="help-about-main">
            <p className="eyebrow">Información del sistema</p>
            <h2>{ABOUT_SYSTEM.name}</h2>
            <p>{ABOUT_SYSTEM.description}</p>
            <strong>Creado por {ABOUT_SYSTEM.createdBy}</strong>
          </div>
          <dl className="help-about-meta">
            <div>
              <dt>Versión</dt>
              <dd>{ABOUT_SYSTEM.version}</dd>
              <small>{ABOUT_SYSTEM.versionStatus} · versión técnica {ABOUT_SYSTEM.technicalVersion}</small>
              <button
                aria-controls="release-history-panel"
                aria-expanded={historyOpen}
                className="button button-secondary help-history-toggle"
                onClick={() => setHistoryOpen((current) => !current)}
                type="button"
              >
                {historyOpen ? "Ocultar historial" : "Historial de cambios"}
              </button>
            </div>
            <div><dt>Fecha de compilación</dt><dd>{buildDate}</dd></div>
          </dl>
          <div className="help-about-technologies">
            <h3>Tecnologías utilizadas</h3>
            <div>
              {ABOUT_SYSTEM.technologies.map((technology) => <span key={technology}>{technology}</span>)}
            </div>
          </div>

          {historyOpen ? (
            <section className="help-release-history" id="release-history-panel">
              <div className="help-release-heading">
                <div>
                  <p className="eyebrow">Trazabilidad de revisiones</p>
                  <h3>Historial de cambios</h3>
                  <p>Versiones ordenadas desde la más reciente. Cada registro identifica fecha, estado, resumen, referencia Git y responsable.</p>
                </div>
                <button
                  aria-controls="iso-version-help"
                  aria-expanded={isoHelpOpen}
                  className="button button-secondary"
                  onClick={() => setIsoHelpOpen((current) => !current)}
                  type="button"
                >
                  {isoHelpOpen ? "Ocultar ayuda ISO 9001" : "¿Cómo aporta a ISO 9001?"}
                </button>
              </div>

              {isoHelpOpen ? (
                <aside className="help-iso-version-guide" id="iso-version-help">
                  <h4>Control de cambios e información documentada</h4>
                  <p>
                    ISO 9001 requiere controlar la información documentada y gestionar los cambios de manera planificada. Este historial ayuda a identificar la revisión vigente, qué cambió, cuándo, quién la registró y qué evidencia Git la respalda.
                  </p>
                  <p>
                    Para una trazabilidad completa debe complementarse con prueba, aprobación, tag o commit definitivo, respaldo y registro del despliegue. La existencia de esta pantalla por sí sola no certifica el cumplimiento de la norma.
                  </p>
                  <ul>
                    <li>Una versión en preparación no debe presentarse como liberada o productiva.</li>
                    <li>Al aprobar una versión deben completarse su commit/tag, responsable y estado real.</li>
                    <li>Las versiones obsoletas se conservan como historial, pero se identifica claramente cuál está vigente.</li>
                  </ul>
                  <div className="help-iso-links">
                    <a href="https://www.iso.org/files/live/sites/isoorg/files/archive/pdf/en/documented_information.pdf" rel="noreferrer" target="_blank">Guía oficial sobre información documentada</a>
                    <a href="https://www.iso.org/standard/75736.html" rel="noreferrer" target="_blank">ISO 10013:2021</a>
                  </div>
                </aside>
              ) : null}

              <div className="help-release-list">
                {RELEASE_HISTORY.map((release) => (
                  <article className={`help-release-entry ${release.status}`} key={release.version}>
                    <div className="help-release-entry-head">
                      <div>
                        <strong>{release.version}</strong>
                        <time dateTime={release.date}>{new Intl.DateTimeFormat("es-AR", { dateStyle: "long" }).format(new Date(`${release.date}T12:00:00`))}</time>
                      </div>
                      <span>{release.statusLabel}</span>
                    </div>
                    <ul>
                      {release.summary.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                    <footer>
                      <span>Git: <strong>{release.commit}</strong></span>
                      <span>Responsable: <strong>{release.responsible}</strong></span>
                    </footer>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </section>
      ) : null}

      <section className="help-progress-panel" aria-labelledby="help-progress-title">
        <div className="help-progress-summary">
          <div>
            <p className="eyebrow">Mi aprendizaje</p>
            <h2 id="help-progress-title">Tu avance en la ayuda</h2>
            <p>{readTopicCount} de {availableTopics.length} guías consultadas · {progress.completedTourIds.length} recorridos completados</p>
          </div>
          <strong className="help-progress-percentage">{progressPercentage}%</strong>
        </div>
        <div
          aria-label={`${progressPercentage}% de las guías consultadas`}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={progressPercentage}
          className="help-progress-track"
          role="progressbar"
        >
          <span style={{ width: `${progressPercentage}%` }} />
        </div>
        <div className="help-progress-actions">
          {continueTopic ? (
            <button className="button button-primary" onClick={() => openTopic(continueTopic.id)} type="button">
              Continuar con: {continueTopic.title}
            </button>
          ) : (
            <span className="help-progress-complete">Has consultado todas las guías disponibles para tu perfil.</span>
          )}
          {(progress.readTopicIds.length || progress.completedTourIds.length) ? (
            <button
              className="button button-ghost"
              onClick={() => {
                if (window.confirm("¿Deseas reiniciar solamente tu progreso de aprendizaje en este dispositivo?")) {
                  setProgress(clearHelpProgress(user?.id));
                }
              }}
              type="button"
            >
              Reiniciar progreso
            </button>
          ) : null}
        </div>
        <small>El avance se guarda en este dispositivo para tu usuario y no modifica información del sistema.</small>
      </section>

      <section className="help-search-panel">
        <div className="help-search-copy">
          <p className="eyebrow">¿Qué necesitas hacer?</p>
          <h2>Encuentra una respuesta rápida</h2>
          <p>Busca por pantalla, tarea o concepto: por ejemplo, anomalía, convocatoria, acción o eficacia.</p>
        </div>
        <div className="help-search-control">
          <label htmlFor="help-search">Buscar en la ayuda</label>
          <div className="help-search-row">
            <input
              autoComplete="off"
              id="help-search"
              onChange={(event) => updateQuery(event.target.value)}
              placeholder="Escribe una palabra o una pregunta"
              type="search"
              value={query}
            />
            {query ? (
              <button className="button button-secondary" onClick={() => updateQuery("")} type="button">
                Limpiar
              </button>
            ) : null}
          </div>
          <small>{availableTopics.length} guías disponibles para tu perfil.</small>
        </div>
      </section>

      {!query ? (
        <section className="help-section-block">
          <div className="section-head compact">
            <div>
              <p className="eyebrow">Guías rápidas</p>
              <h2>Procesos más utilizados</h2>
            </div>
          </div>
          <div className="help-topic-grid">
            {quickTopics.map((topic) => (
              <HelpTopicCard key={topic.id} onOpen={openTopic} read={readTopicIds.has(topic.id)} topic={topic} />
            ))}
          </div>
        </section>
      ) : null}

      <section className="help-section-block">
        <div className="section-head compact help-results-head">
          <div>
            <p className="eyebrow">Biblioteca de ayuda</p>
            <h2>{query ? `Resultados para “${query}”` : "Explorar todos los temas"}</h2>
          </div>
          <span className="help-result-count">{filteredTopics.length} {filteredTopics.length === 1 ? "resultado" : "resultados"}</span>
        </div>

        <div aria-label="Filtrar ayuda por categoría" className="help-category-tabs">
          {[ALL_CATEGORIES, ...visibleCategories].map((item) => (
            <button
              aria-pressed={category === item}
              className={`help-category-button${category === item ? " active" : ""}`}
              key={item}
              onClick={() => setCategory(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>

        {filteredTopics.length ? (
          <div className="help-topic-grid">
            {filteredTopics.map((topic) => (
              <HelpTopicCard key={topic.id} onOpen={openTopic} read={readTopicIds.has(topic.id)} topic={topic} />
            ))}
          </div>
        ) : (
          <div className="help-empty-state">
            <strong>No encontramos una guía con esos términos.</strong>
            <p>Prueba con menos palabras o selecciona Todos los temas.</p>
            <button
              className="button button-secondary"
              onClick={() => {
                updateQuery("");
                setCategory(ALL_CATEGORIES);
              }}
              type="button"
            >
              Ver toda la ayuda
            </button>
          </div>
        )}
      </section>
    </section>
  );
}
