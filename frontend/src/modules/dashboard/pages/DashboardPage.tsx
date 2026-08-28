import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchDashboardSummary, fetchPendingActions } from "../../../api/actions";
import { fetchMyAnomalies } from "../../../api/anomalies";
import { fetchTreatments } from "../../../api/treatments";
import type { ActionItemSummary, AnomalyListItem, DashboardSummaryCard, DashboardSummaryResponse, PagedResponse, TreatmentSummary } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDate, formatDateTime } from "../../../app/utils";
import { CompanyLogo } from "../../../components/CompanyLogo";
import { DataState } from "../../../components/DataState";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

const primarySectionsBase = [
  {
    sequence: 1,
    title: "Registrar anomalia",
    description: "Carga inicial desde planta con datos rapidos, multiples ordenes afectadas y confirmacion inmediata.",
    to: "/anomalies/new",
    label: "Ir a nueva anomalia",
  },
  {
    sequence: 2,
    title: "Seguimiento de anomalias",
    description: "Consulta estado, etapa, responsables y trazabilidad de cada caso reportado.",
    to: "/anomalies",
    label: "Ver mis anomalias",
  },
  {
    sequence: 3,
    title: "Tratamientos",
    description: "Gestiona convocatorias, analisis de causa raiz y tareas surgidas de anomalias con Revisión de hallazgos para tratamiento.",
    to: "/treatments",
    label: "Ver tratamientos",
  },
  {
    sequence: 4,
    title: "Observacion",
    description: "Cierre directo de anomalias con Revisión de hallazgos como Observacion, con responsable, evidencia y verificacion de eficacia.",
    to: "/anomalies/observations",
    label: "Gestionar Observacion",
  },
  {
    sequence: 5,
    title: "Seguimiento de tratamientos",
    description: "Consulta solo lectura de procedimientos, tareas, responsables, evidencias y validaciones.",
    to: "/treatments/tracking",
    label: "Auditar tratamientos",
  },
  {
    sequence: 6,
    title: "Acciones",
    description: "Accede a las acciones asignadas y gestiona su ejecucion y evidencia.",
    to: "/actions/mine",
    label: "Ver acciones",
  },
  {
    sequence: 7,
    title: "Validacion",
    description: "Evalua si los tratamientos completados fueron eficaces o deben reabrirse.",
    to: "/validation",
    label: "Validar eficacia",
  },
  {
    sequence: 8,
    title: "Lecciones aprendidas",
    description: "Registra aprendizajes y evidencias de tratamientos validados como eficaces.",
    to: "/learned-lessons",
    label: "Registrar aprendizajes",
  },
  {
    sequence: 9,
    title: "Bandeja y pendientes",
    description: "Revisa pendientes, avisos, participaciones e historial sin informacion duplicada.",
    to: "/notifications/inbox",
    label: "Abrir bandeja",
  },
  {
    sequence: 10,
    title: "Ordenes afectadas",
    description: "Consulta ordenes vinculadas con anomalias, cantidades, procesos y totalizadores.",
    to: "/affected-orders",
    label: "Ver ordenes afectadas",
  },
];

const workflowSections = [
  {
    title: "Registro y contencion",
    description: "Inicio del caso, contencion operativa y confirmacion inicial del evento.",
    helper: "Se trabaja desde Nueva anomalia y el detalle del caso.",
  },
  {
    title: "Revisión de hallazgos y causa",
    description: "Analisis tecnico, criterio de Revisión de hallazgos, origen y determinacion de causa raiz.",
    helper: "Ideal para perfiles de calidad, supervision e ingenieria.",
  },
  {
    title: "Plan y ejecucion",
    description: "Definicion de propuestas, acciones, responsables, evidencia y seguimiento.",
    helper: "Se apoya en Acciones y en la Bandeja unificada.",
  },
  {
    title: "Verificacion y cierre",
    description: "Control de eficacia, cierre formal y aprendizaje documentado.",
    helper: "La trazabilidad completa queda disponible en el detalle.",
  },
];

const adminSections = [
  { title: "Usuarios", description: "Alta, baja y edicion de usuarios del sistema.", to: "/management/users" },
  { title: "Importacion de usuarios", description: "Carga masiva desde CSV o Excel con datos basicos.", to: "/management/users/import" },
  { title: "Roles y alcances", description: "Roles, permisos y alcance por sitio o sector.", href: "/admin/accounts/role/" },
  { title: "Alcances de usuario", description: "Nivel, rol y checklist de permisos por usuario.", to: "/management/user-scopes" },
  { title: "Areas", description: "Areas principales de la empresa donde opera el sistema.", to: "/management/catalogs?entity=sites" },
  { title: "Procesos", description: "Procesos o subsectores de trabajo disponibles para el registro.", to: "/management/catalogs?entity=areas" },
  { title: "Lineas", description: "Lineas o puestos productivos, si el sector las utiliza.", to: "/management/catalogs?entity=lines" },
  { title: "Tipos de desvio", description: "Catalogo de defectos, desvios o eventos de calidad.", to: "/management/catalogs?entity=anomaly-types" },
  { title: "Asignado a", description: "Catalogo de asignaciones asociadas a la anomalia.", to: "/management/catalogs?entity=anomaly-origins" },
  { title: "Criterios de Revisión de hallazgos", description: "Criterios usados para la Revisión de hallazgos de cada anomalia.", to: "/management/catalogs?entity=severities" },
  { title: "Orden operativo", description: "Criterios internos de ordenamiento operativo y tratamiento.", to: "/management/catalogs?entity=priorities" },
  { title: "Tipos de accion", description: "Contencion, correctiva, preventiva o mejora.", to: "/management/catalogs?entity=action-types" },
  { title: "Tipos de ordenes afectadas", description: "Maestro de OP, OF, OM y otros tipos de orden.", to: "/management/catalogs?entity=order-types" },
  { title: "Panel admin Django", description: "Acceso completo al panel tecnico y maestros.", href: "/admin/" },
];

type DashboardView = "none" | "welcome" | "overview" | "sections" | "workflow" | "tracking" | "admin";

type ViewOption = {
  id: DashboardView;
  label: string;
};

const baseOptions: ViewOption[] = [
  { id: "welcome", label: "Bienvenida y ayuda" },
  { id: "overview", label: "Resumen rapido" },
  { id: "sections", label: "Secciones principales" },
  { id: "workflow", label: "Pasos del flujo" },
  { id: "tracking", label: "Seguimiento operativo" },
];

const viewLabels: Record<DashboardView, string> = {
  none: "Vista compacta",
  welcome: "Bienvenida y ayuda",
  overview: "Resumen rapido",
  sections: "Secciones principales",
  workflow: "Pasos del flujo",
  tracking: "Seguimiento operativo",
  admin: "Configuracion y maestros",
};

const EMPTY_SUMMARY: DashboardSummaryResponse = {
  scope: "user",
  cards: [],
};

function emptyPagedResponse<T>(): PagedResponse<T> {
  return {
    count: 0,
    next: null,
    previous: null,
    results: [],
  };
}

function viewNeedsDashboardData(view: DashboardView) {
  return view === "overview" || view === "tracking";
}

function compactStatuses(card: DashboardSummaryCard) {
  const visible = card.statuses.filter((item) => item.count > 0).slice(0, 4);
  const source = visible.length ? visible : card.statuses.slice(0, 4);
  return source;
}

function DashboardSummaryCardView({
  card,
  adminScope,
  expanded,
  onToggle,
}: {
  card: DashboardSummaryCard;
  adminScope: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const compact = compactStatuses(card);
  const hiddenCount = Math.max(0, card.statuses.length - compact.length);

  return (
    <article className="stat-card dashboard-summary-card">
      <span className="stat-label">{card.title}</span>
      <strong className="stat-value">{card.total}</strong>
      <span className="stat-hint">{card.description}</span>
      <div className="dashboard-status-line">
        {compact.map((status) => (
          <span key={status.key}>{`${status.label}: ${status.count}`}</span>
        ))}
        {hiddenCount ? <span>{`+ ${hiddenCount} estados mas`}</span> : null}
      </div>
      {adminScope ? (
        <button className="button button-secondary dashboard-detail-toggle" onClick={onToggle} type="button">
          {expanded ? "Ocultar detalle por usuario" : "Ver detalle por usuario"}
        </button>
      ) : null}
    </article>
  );
}

function DashboardSummaryDetail({ card }: { card: DashboardSummaryCard }) {
  const rows = card.detail_rows ?? [];
  if (!rows.length) {
    return (
      <section className="panel muted dashboard-detail-panel">
        <strong>{card.title}</strong>
        <p>No hay datos por usuario para mostrar.</p>
      </section>
    );
  }

  return (
    <section className="panel dashboard-detail-panel">
      <div className="section-head compact">
        <div>
          <p className="eyebrow">Detalle por usuario</p>
          <h3>{card.title}</h3>
        </div>
      </div>
      <div className="table-scroll dashboard-summary-table">
        <table>
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Total</th>
              {card.statuses.map((status) => (
                <th key={status.key}>{status.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.user.id}>
                <td>{row.user.name}</td>
                <td>{row.total}</td>
                {card.statuses.map((status) => (
                  <td key={`${row.user.id}-${status.key}`}>{row.statuses.find((item) => item.key === status.key)?.count ?? 0}</td>
                ))}
              </tr>
            ))}
            <tr className="dashboard-summary-total-row">
              <td>Total general</td>
              <td>{card.total}</td>
              {card.statuses.map((status) => (
                <td key={`total-${status.key}`}>{status.count}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function resolveDashboardView(value: string | null, adminUser: boolean): DashboardView {
  if (!value) {
    return "none";
  }

  const normalized = value.toLowerCase() as DashboardView;
  const allowedBase: DashboardView[] = ["welcome", "overview", "sections", "workflow", "tracking", "none"];
  if (allowedBase.includes(normalized)) {
    return normalized;
  }

  if (normalized === "admin" && adminUser) {
    return "admin";
  }

  return "none";
}

export function DashboardPage() {
  usePageTitle("Inicio");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);
  const [searchParams, setSearchParams] = useSearchParams();
  const [menuOpen, setMenuOpen] = useState(false);
  const [expandedSummary, setExpandedSummary] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<DashboardView>(() => resolveDashboardView(searchParams.get("view"), adminUser));

  useEffect(() => {
    setActiveView(resolveDashboardView(searchParams.get("view"), adminUser));
  }, [adminUser, searchParams]);

  const contextualOptions = useMemo(
    () => (adminUser ? [...baseOptions, { id: "admin", label: "Configuracion admin" }] : baseOptions),
    [adminUser],
  );

  const primarySections = primarySectionsBase;
  const needsDashboardData = viewNeedsDashboardData(activeView);
  const { data, loading, error, reload } = useAsyncTask(async () => {
    if (!needsDashboardData) {
      return {
        summary: EMPTY_SUMMARY,
        anomalies: emptyPagedResponse<AnomalyListItem>(),
        treatments: emptyPagedResponse<TreatmentSummary>(),
        pendingActions: emptyPagedResponse<ActionItemSummary>(),
      };
    }

    if (!user) {
      throw new Error("No hay usuario autenticado.");
    }

    const [summary, anomalies, treatments, pendingActions] = await Promise.all([
      fetchDashboardSummary(),
      fetchMyAnomalies(user.id),
      fetchTreatments(),
      fetchPendingActions(),
    ]);

    return { summary, anomalies, treatments, pendingActions };
  }, [user?.id, needsDashboardData]);

  const selectView = (viewId: DashboardView) => {
    setActiveView(viewId);
    setMenuOpen(false);
    if (viewId === "none") {
      setSearchParams({});
      return;
    }
    setSearchParams({ view: viewId });
  };

  return (
    <section className="page-shell page-shell-management">
      <section className="panel contextual-toolbar">
        <div>
          <p className="eyebrow">Centro principal</p>
          <h1>Panel de gestion</h1>
          <p className="page-description">
            Vista simplificada para no sobrecargar la pantalla. Usa el menu contextual para abrir cada bloque cuando lo necesites.
          </p>
        </div>

        <div className="context-menu">
          <button
            className="button button-primary context-menu-toggle"
            onClick={() => setMenuOpen((prev) => !prev)}
            type="button"
          >
            Menu contextual
          </button>

          {menuOpen ? (
            <div className="context-menu-popover">
              {contextualOptions.map((option) => (
                <button
                  className={`context-menu-option${activeView === option.id ? " active" : ""}`}
                  key={option.id}
                  onClick={() => selectView(option.id)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
              <button className="context-menu-option" onClick={() => selectView("none")} type="button">
                Cerrar paneles
              </button>
            </div>
          ) : null}
        </div>
      </section>

      {activeView !== "none" ? (
        <section className="panel contextual-current">
          <p className="eyebrow">Vista activa</p>
          <h2>{viewLabels[activeView]}</h2>
        </section>
      ) : (
        <section className="panel muted compact-empty-state">
          <h2>Vista compacta activa</h2>
          <p>Ahora no se muestran tarjetas de contenido. Abri el menu contextual para ver la seccion que quieras.</p>
        </section>
      )}

      <DataState loading={loading} error={error} onRetry={reload}>
        {data ? (
          <>
            {activeView === "welcome" ? (
              <section className="panel control-hero">
                <div className="control-hero-copy">
                  <CompanyLogo />
                  <div>
                    <p className="eyebrow">Centro principal</p>
                    <h2>Bienvenido al espacio de gestion</h2>
                    <p className="page-description">
                      Desde esta pantalla podes orientar el trabajo diario, abrir nuevas anomalias, seguir acciones y entrar rapido a las
                      secciones clave del flujo.
                    </p>
                  </div>
                </div>

                <div className="control-hero-help">
                  <p className="eyebrow">Ayuda rapida</p>
                  <h2>Como usar el sistema</h2>
                  <ul className="help-list">
                    <li>
                      <strong>1. Registrar:</strong> usa <span>Nueva anomalia</span> para iniciar un caso con datos operativos.
                    </li>
                    <li>
                      <strong>2. Seguir:</strong> entra a <span>Seguimiento de anomalias</span> para ver estado, etapa e historial.
                    </li>
                    <li>
                      <strong>3. Ejecutar:</strong> usa <span>Acciones</span> y la <span>Bandeja</span> unificada para resolver tareas.
                    </li>
                    <li>
                      <strong>4. Administrar:</strong> si sos admin, usa el menu contextual para entrar a configuracion y catalogos.
                    </li>
                  </ul>
                </div>
              </section>
            ) : null}

            {activeView === "overview" ? (
              <section className="panel">
                <div className="section-head compact">
                  <div>
                    <p className="eyebrow">Resumen</p>
                    <h2>Indicadores actuales</h2>
                  </div>
                </div>
                <div className="stats-grid compact-grid dashboard-summary-grid">
                  {data.summary.cards.map((card) => (
                    <DashboardSummaryCardView
                      adminScope={data.summary.scope === "admin"}
                      card={card}
                      expanded={expandedSummary === card.key}
                      key={card.key}
                      onToggle={() => setExpandedSummary((current) => (current === card.key ? null : card.key))}
                    />
                  ))}
                </div>
                {data.summary.scope === "admin" && expandedSummary ? (
                  <DashboardSummaryDetail card={data.summary.cards.find((card) => card.key === expandedSummary) ?? data.summary.cards[0]} />
                ) : null}
              </section>
            ) : null}

            {activeView === "sections" ? (
              <section className="panel">
                <div className="section-head">
                  <div>
                    <p className="eyebrow">Accesos</p>
                    <h2>Secciones principales</h2>
                  </div>
                </div>
                <div className="management-grid">
                  {primarySections.map((section) => (
                    <Link className="management-card" key={section.title} to={section.to}>
                      <span className="section-sequence-badge">{section.sequence}</span>
                      <p className="eyebrow">Operacion</p>
                      <h3>{section.title}</h3>
                      <p>{section.description}</p>
                      <span className="management-card-link">{section.label}</span>
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}

            {activeView === "workflow" ? (
              <section className="panel">
                <div className="section-head">
                  <div>
                    <p className="eyebrow">Flujo</p>
                    <h2>Pasos clave del proceso</h2>
                  </div>
                </div>
                <div className="workflow-grid">
                  {workflowSections.map((step, index) => (
                    <article className="workflow-card" key={step.title}>
                      <span className="workflow-step">0{index + 1}</span>
                      <h3>{step.title}</h3>
                      <p>{step.description}</p>
                      <small>{step.helper}</small>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {activeView === "tracking" ? (
              <div className="dashboard-grid">
                <article className="panel">
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Seguimiento</p>
                      <h2>Ultimas anomalias</h2>
                    </div>
                    <Link className="text-link" to="/anomalies">
                      Ver todas
                    </Link>
                  </div>
                  <div className="stack-list">
                    {data.anomalies.results.slice(0, 5).map((item) => (
                      <Link className="list-card" key={item.id} to={`/anomalies/${item.id}`}>
                        <div>
                          <strong>{item.code}</strong>
                          <p>{item.title}</p>
                          <small>{formatDateTime(item.detected_at)}</small>
                        </div>
                        <div className="badge-stack">
                          <StatusBadge value={item.current_status} compact />
                          <StatusBadge value={item.current_stage} compact />
                        </div>
                      </Link>
                    ))}
                    {data.anomalies.results.length === 0 ? <p className="muted-copy">No hay anomalias registradas todavia.</p> : null}
                  </div>
                </article>

                <article className="panel">
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Tratamientos</p>
                      <h2>En gestion</h2>
                    </div>
                    <Link className="text-link" to="/treatments">
                      Ver tratamientos
                    </Link>
                  </div>
                  <div className="stack-list">
                    {data.treatments.results.slice(0, 5).map((item) => (
                      <Link className="list-card" key={item.id} to="/treatments">
                        <div>
                          <strong>{item.code}</strong>
                          <p>{item.primary_anomaly.title}</p>
                          <small>{item.scheduled_for ? `Programado: ${formatDateTime(item.scheduled_for)}` : "Sin fecha programada"}</small>
                        </div>
                        <div className="badge-stack align-end">
                          <StatusBadge value={item.status} compact />
                        </div>
                      </Link>
                    ))}
                    {data.treatments.results.length === 0 ? <p className="muted-copy">No hay tratamientos creados ahora.</p> : null}
                  </div>
                </article>

                <article className="panel">
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Ejecucion</p>
                      <h2>Acciones pendientes</h2>
                    </div>
                    <Link className="text-link" to="/actions/mine">
                      Ver acciones
                    </Link>
                  </div>
                  <div className="stack-list">
                    {data.pendingActions.results.slice(0, 5).map((item) => (
                      <div className="list-card" key={item.id}>
                        <div>
                          <strong>{item.title}</strong>
                          <p>{item.description || "Sin descripcion."}</p>
                          <small>Compromiso: {item.due_date ? formatDate(item.due_date) : "Sin fecha"}</small>
                        </div>
                        <div className="badge-stack">
                          <StatusBadge value={item.effective_status || item.status} compact />
                        </div>
                      </div>
                    ))}
                    {data.pendingActions.results.length === 0 ? <p className="muted-copy">No hay acciones pendientes ahora.</p> : null}
                  </div>
                </article>
              </div>
            ) : null}

            {activeView === "admin" ? (
              adminUser ? (
                <section className="panel admin-panel">
                  <div className="section-head">
                    <div>
                      <p className="eyebrow">Administrador</p>
                      <h2>Configuracion y maestros</h2>
                    </div>
                    <span className="status-badge info">Acceso restringido</span>
                  </div>
                  <p className="page-description admin-panel-copy">
                    Estos accesos abren formularios internos de gestion y, cuando corresponde, el admin de Django para tareas avanzadas.
                  </p>
                  <div className="admin-grid">
                    {adminSections.map((section) => {
                      if ("to" in section) {
                        return (
                          <Link className="admin-card" key={section.title} to={section.to}>
                            <h3>{section.title}</h3>
                            <p>{section.description}</p>
                            <span className="management-card-link">Abrir gestion</span>
                          </Link>
                        );
                      }

                      return (
                        <a className="admin-card" href={section.href} key={section.title}>
                          <h3>{section.title}</h3>
                          <p>{section.description}</p>
                          <span className="management-card-link">Abrir gestion</span>
                        </a>
                      );
                    })}
                  </div>
                </section>
              ) : (
                <section className="panel warning">
                  <h2>Sin permisos de administracion</h2>
                  <p>Esta seccion solo esta disponible para usuarios con perfil administrador.</p>
                </section>
              )
            ) : null}
          </>
        ) : null}
      </DataState>
    </section>
  );
}




















