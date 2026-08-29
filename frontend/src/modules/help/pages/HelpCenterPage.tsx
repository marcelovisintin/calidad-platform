import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isAdminUser, isManagementUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { PageHeader } from "../../../components/PageHeader";
import { usePageTitle } from "../../../hooks/usePageTitle";
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
      />

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
