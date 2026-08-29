import { useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import { downloadIndicatorCsv, fetchIndicatorDashboard, type IndicatorDashboardFilters } from "../../../api/indicators";
import type { IndicatorDashboardRow } from "../../../api/types";
import { getDefaultLandingPath, isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatCard } from "../../../components/StatCard";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { IndicatorBreakdownChart, IndicatorTrendChart } from "../components/IndicatorCharts";
import { IndicatorReportDialog } from "../components/IndicatorReportDialog";


const IMPLEMENTED_KEYS = new Set([
  "anomalies-treated", "treatments", "anomalies-by-process", "finding-classification",
  "repetition-pareto", "actions", "effectiveness", "affected-orders", "learned-lessons",
]);
const DYNAMIC_SERIES_KEYS = new Set(["anomalies-by-process", "finding-classification", "repetition-pareto", "affected-orders"]);
const PAGE_SIZE = 20;

type Column = {
  key: string;
  label: string;
  format?: "date" | "percentage" | "boolean";
};

const COLUMNS: Record<string, Column[]> = {
  "anomalies-treated": [
    { key: "code", label: "Codigo" },
    { key: "title", label: "Titulo" },
    { key: "process", label: "Proceso" },
    { key: "classification", label: "Clasificacion" },
    { key: "status", label: "Estado" },
    { key: "detected_at", label: "Detectada", format: "date" },
    { key: "closed_at", label: "Cerrada", format: "date" },
  ],
  treatments: [
    { key: "code", label: "Tratamiento" },
    { key: "anomaly", label: "Anomalia" },
    { key: "process", label: "Proceso" },
    { key: "responsible", label: "Responsable" },
    { key: "status", label: "Estado" },
    { key: "created_at", label: "Creado", format: "date" },
    { key: "completed_at", label: "Completado", format: "date" },
  ],
  "anomalies-by-process": [
    { key: "code", label: "Codigo" },
    { key: "process", label: "Proceso" },
    { key: "count", label: "Cantidad" },
    { key: "percentage", label: "Porcentaje", format: "percentage" },
    { key: "previous", label: "Periodo anterior" },
    { key: "delta", label: "Variacion" },
  ],
  "finding-classification": [
    { key: "code", label: "Codigo" }, { key: "title", label: "Titulo" },
    { key: "process", label: "Proceso" }, { key: "classification", label: "Clasificacion" },
    { key: "classified_at", label: "Clasificada", format: "date" }, { key: "status", label: "Estado" },
  ],
  "repetition-pareto": [
    { key: "group", label: "Grupo" }, { key: "count", label: "Cantidad" },
    { key: "percentage", label: "Porcentaje", format: "percentage" },
    { key: "cumulative_percentage", label: "Acumulado", format: "percentage" },
    { key: "previous", label: "Periodo anterior" }, { key: "delta", label: "Variacion" },
    { key: "cases", label: "Casos" },
  ],
  actions: [
    { key: "code", label: "Accion" }, { key: "source", label: "Origen" },
    { key: "title", label: "Descripcion" }, { key: "process", label: "Proceso" },
    { key: "responsible", label: "Responsable" }, { key: "effective_status", label: "Estado" },
    { key: "due_date", label: "Comprometida", format: "date" },
    { key: "completed_at", label: "Finalizada", format: "date" },
  ],
  effectiveness: [
    { key: "code", label: "Codigo" }, { key: "source", label: "Circuito" },
    { key: "process", label: "Proceso" }, { key: "responsible", label: "Responsable" },
    { key: "effective_status", label: "Resultado" }, { key: "due_date", label: "Vencimiento", format: "date" },
    { key: "verified_at", label: "Verificada", format: "date" },
  ],
  "affected-orders": [
    { key: "type", label: "Tipo" }, { key: "number", label: "Numero" },
    { key: "quantity", label: "Cantidad" }, { key: "anomaly", label: "Anomalia" },
    { key: "process", label: "Proceso" }, { key: "detected_at", label: "Detectada", format: "date" },
  ],
  "learned-lessons": [
    { key: "treatment", label: "Tratamiento" }, { key: "anomaly", label: "Anomalia" },
    { key: "process", label: "Proceso" }, { key: "learning", label: "Aprendizaje" },
    { key: "procedure_modified", label: "Procedimiento modificado", format: "boolean" },
    { key: "saved_at", label: "Registrada", format: "date" },
    { key: "validated_at", label: "Eficacia validada", format: "date" },
  ],
};

function localIsoDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function initialFilters(): IndicatorDashboardFilters {
  const today = new Date();
  return {
    dateFrom: `${today.getFullYear()}-01-01`,
    dateTo: localIsoDate(today),
    area: "",
    groupBy: "process_type",
    page: 1,
    pageSize: PAGE_SIZE,
  };
}

function metricHint(metric: { percentage: number | null; hint?: string; comparison: { delta: number; previous: number } | null }) {
  const parts = [];
  if (metric.percentage !== null) {
    parts.push(`${metric.percentage.toFixed(1)} %`);
  }
  if (metric.hint) {
    parts.push(metric.hint);
  }
  if (metric.comparison) {
    const sign = metric.comparison.delta > 0 ? "+" : "";
    parts.push(`${sign}${metric.comparison.delta} vs. periodo anterior (${metric.comparison.previous})`);
  }
  return parts.join(" · ") || "Sin base de calculo";
}

function formatCell(row: IndicatorDashboardRow, column: Column) {
  const value = row[column.key];
  if (value === null || value === "") {
    return "—";
  }
  if (column.format === "date" && typeof value === "string") {
    return formatDateTime(value);
  }
  if (column.format === "percentage" && typeof value === "number") {
    return `${value.toFixed(1)} %`;
  }
  if (column.format === "boolean") {
    return value ? "Si" : "No";
  }
  return String(value);
}

export function IndicatorDashboardPage() {
  const { indicatorKey = "" } = useParams();
  const { user } = useAuth();
  const [filters, setFilters] = useState<IndicatorDashboardFilters>(initialFilters);
  const [exporting, setExporting] = useState(false);
  const [actionError, setActionError] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const requestKey = JSON.stringify(filters);
  const implemented = IMPLEMENTED_KEYS.has(indicatorKey);
  const { data: catalogs } = useAsyncTask(fetchCatalogBootstrap, []);
  const { data, loading, error, reload } = useAsyncTask(
    () => implemented ? fetchIndicatorDashboard(indicatorKey, filters) : Promise.resolve(null),
    [indicatorKey, implemented, requestKey],
  );
  usePageTitle(data?.title ?? "Indicador");

  const visibleSeriesKeys = useMemo(
    () => DYNAMIC_SERIES_KEYS.has(indicatorKey) ? data?.breakdown.slice(0, 5).map((item) => item.key) : undefined,
    [data?.breakdown, indicatorKey],
  );

  if (!isAdminUser(user)) {
    return <Navigate replace to={getDefaultLandingPath(user)} />;
  }

  const setFilter = (key: keyof IndicatorDashboardFilters, value: string | number) => {
    setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));
  };

  const clearFilters = () => setFilters(initialFilters());
  const columns = COLUMNS[indicatorKey] ?? [];
  const exportCsv = async () => {
    setExporting(true);
    setActionError("");
    try {
      const file = await downloadIndicatorCsv(indicatorKey, filters);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "No se pudo exportar el CSV.");
    } finally {
      setExporting(false);
    }
  };

  if (!implemented) {
    return (
      <section className="page-shell page-shell-management">
        <PageHeader title="Indicador" description="Dashboard del Sistema de Gestion de Calidad." actionLabel="Volver a indicadores" actionTo="/indicators" />
        <section className="panel indicator-foundation-panel">
          <div>
            <p className="eyebrow">Proxima fase</p>
            <h2>Dashboard en implementacion</h2>
            <p>La ruta y el permiso ya estan preparados. Este indicador se incorpora en la Fase 3 del road map.</p>
          </div>
        </section>
      </section>
    );
  }

  return (
    <section className="page-shell page-shell-management">
      <PageHeader
        title={data?.title ?? "Indicador"}
        description={data?.description ?? "Calculando dashboard..."}
        actionLabel="Volver a indicadores"
        actionTo="/indicators"
      />

      <TabbedFilters
        ariaLabel="Filtros del indicador"
        onClear={clearFilters}
        actions={(
          <div className="form-actions">
            <button className="button button-secondary" disabled={exporting || loading} onClick={exportCsv} type="button">{exporting ? "Exportando..." : "Exportar CSV"}</button>
            <button className="button button-primary" disabled={loading} onClick={() => setReportOpen(true)} type="button">Enviar informe</button>
          </div>
        )}
        items={[
          {
            id: "period",
            label: "Periodo",
            active: Boolean(filters.dateFrom || filters.dateTo),
            content: (
              <div className="inline-filter-fields">
                <label className="field"><span>Desde</span><input onChange={(event) => setFilter("dateFrom", event.target.value)} type="date" value={filters.dateFrom} /></label>
                <label className="field"><span>Hasta</span><input onChange={(event) => setFilter("dateTo", event.target.value)} type="date" value={filters.dateTo} /></label>
              </div>
            ),
          },
          {
            id: "process",
            label: "Proceso",
            active: Boolean(filters.area),
            content: (
              <select aria-label="Proceso" onChange={(event) => setFilter("area", event.target.value)} value={filters.area}>
                <option value="">Todos los procesos</option>
                {catalogs?.areas.map((area) => <option key={area.id} value={area.id}>{`${area.code} - ${area.name}`}</option>)}
              </select>
            ),
          },
          ...(indicatorKey === "repetition-pareto" ? [{
            id: "grouping",
            label: "Agrupacion",
            active: filters.groupBy !== "process_type",
            content: (
              <select aria-label="Agrupacion de Pareto" onChange={(event) => setFilter("groupBy", event.target.value)} value={filters.groupBy}>
                <option value="process_type">Proceso y tipo</option>
                <option value="process">Proceso</option>
                <option value="type">Tipo de anomalia</option>
                <option value="origin">Origen / imputacion</option>
                <option value="classification">Clasificacion</option>
                <option value="order">Orden afectada</option>
              </select>
            ),
          }] : []),
        ]}
      />
      {actionError ? <p className="form-error indicator-action-error">{actionError}</p> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        {data ? (
          <>
            <section className="stats-grid indicator-metrics-grid">
              {data.metrics.map((metric) => (
                <StatCard key={metric.key} label={metric.label} value={metric.value} hint={metricHint(metric)} tone={metric.tone} />
              ))}
            </section>

            <section className="indicator-dashboard-grid">
              <article className="panel indicator-chart-panel">
                <div className="section-head compact"><div><p className="eyebrow">Evolucion</p><h2>Resultado mensual</h2></div></div>
                <IndicatorTrendChart series={data.series} visibleKeys={visibleSeriesKeys} />
              </article>
              <article className="panel indicator-chart-panel">
                <div className="section-head compact"><div><p className="eyebrow">Distribucion</p><h2>{indicatorKey === "repetition-pareto" ? "Pareto acumulado" : "Composicion del período"}</h2></div></div>
                <IndicatorBreakdownChart items={data.breakdown} />
              </article>
            </section>

            <section className="panel compact indicator-formula-panel">
              <strong>Criterios de calculo</strong>
              <ul>{data.formula_notes.map((note) => <li key={note}>{note}</li>)}</ul>
            </section>

            <section className="panel">
              <div className="section-head compact">
                <div><p className="eyebrow">Datos de respaldo</p><h2>{`${data.rows.count} resultado(s)`}</h2></div>
              </div>
              <div className="data-table-wrap">
                <table className="data-table indicator-data-table">
                  <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
                  <tbody>
                    {data.rows.results.map((row, index) => (
                      <tr key={String(row.id ?? index)}>
                        {columns.map((column, columnIndex) => (
                          <td key={column.key}>
                            {columnIndex === 0 && typeof row.detail_url === "string" ? <Link className="text-link" to={row.detail_url}>{formatCell(row, column)}</Link> : formatCell(row, column)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.rows.count === 0 ? <p className="muted-copy">No hay datos para el período y proceso seleccionados.</p> : null}
              <PaginationControls page={filters.page} pageSize={PAGE_SIZE} totalCount={data.rows.count} disabled={loading} onPageChange={(page) => setFilter("page", page)} />
            </section>
          </>
        ) : null}
      </DataState>
      {reportOpen ? <IndicatorReportDialog indicatorKey={indicatorKey} filters={filters} onClose={() => setReportOpen(false)} /> : null}
    </section>
  );
}
