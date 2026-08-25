import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  downloadAffectedOrdersCsv,
  fetchAffectedOrders,
  type AffectedOrderFilters,
} from "../../../api/anomalies";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import { formatDateTime, humanizeToken } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatCard } from "../../../components/StatCard";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  "registered",
  "in_evaluation",
  "in_analysis",
  "in_treatment",
  "pending_verification",
  "closed",
  "cancelled",
  "reopened",
];

const EMPTY_FILTERS: AffectedOrderFilters = {
  search: "",
  orderType: "",
  number: "",
  anomaly: "",
  area: "",
  status: "",
  quantityMin: "",
  quantityMax: "",
  dateFrom: "",
  dateTo: "",
  ordering: "-detected_at",
};

export function AffectedOrdersPage() {
  usePageTitle("Ordenes afectadas");
  const [filters, setFilters] = useState<AffectedOrderFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const { data: catalogs } = useAsyncTask(fetchCatalogBootstrap, []);
  const requestFilters = useMemo(() => ({ ...filters, page, pageSize: PAGE_SIZE }), [filters, page]);
  const requestKey = JSON.stringify(requestFilters);
  const { data, loading, error, reload } = useAsyncTask(
    () => fetchAffectedOrders(requestFilters),
    [requestKey],
  );

  const setFilter = (name: keyof AffectedOrderFilters, value: string) => {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await downloadAffectedOrdersCsv(filters);
    } catch (caught) {
      setExportError(caught instanceof Error ? caught.message : "No se pudo exportar el listado.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="page-shell">
      <PageHeader
        title="Ordenes afectadas"
        description="Consulta consolidada de ordenes vinculadas con anomalias y cantidades de piezas o productos afectados."
        actionLabel="Volver al panel"
        actionTo="/dashboard?view=sections"
      />

      <TabbedFilters
        actions={(
          <div className="form-actions">
            <select
              aria-label="Ordenar listado"
              onChange={(event) => setFilter("ordering", event.target.value)}
              value={filters.ordering}
            >
              <option value="-detected_at">Mas recientes</option>
              <option value="detected_at">Mas antiguas</option>
              <option value="type">Tipo de orden</option>
              <option value="number">Numero ascendente</option>
              <option value="-quantity">Mayor cantidad</option>
              <option value="process">Proceso</option>
            </select>
            <button className="button button-secondary" disabled={exporting} onClick={() => void handleExport()} type="button">
              {exporting ? "Exportando..." : "Exportar CSV"}
            </button>
          </div>
        )}
        ariaLabel="Filtros de ordenes afectadas"
        onClear={clearFilters}
        items={[
          {
            id: "search",
            label: "Buscar",
            active: Boolean(filters.search),
            content: <input aria-label="Buscar ordenes afectadas" onChange={(event) => setFilter("search", event.target.value)} placeholder="Tipo, numero, anomalia o proceso" type="search" value={filters.search} />,
          },
          {
            id: "type",
            label: "Tipo de orden",
            active: Boolean(filters.orderType),
            content: (
              <select aria-label="Tipo de orden" onChange={(event) => setFilter("orderType", event.target.value)} value={filters.orderType}>
                <option value="">Todos</option>
                {catalogs?.orderTypes.map((item) => <option key={item.id} value={item.id}>{`${item.code} - ${item.name}`}</option>)}
              </select>
            ),
          },
          {
            id: "number",
            label: "Numero",
            active: Boolean(filters.number),
            content: <input aria-label="Numero de orden" onChange={(event) => setFilter("number", event.target.value)} placeholder="Coincidencia parcial" type="search" value={filters.number} />,
          },
          {
            id: "anomaly",
            label: "Anomalia",
            active: Boolean(filters.anomaly),
            content: <input aria-label="Anomalia" onChange={(event) => setFilter("anomaly", event.target.value)} placeholder="Codigo o titulo" type="search" value={filters.anomaly} />,
          },
          {
            id: "process",
            label: "Proceso",
            active: Boolean(filters.area),
            content: (
              <select aria-label="Proceso" onChange={(event) => setFilter("area", event.target.value)} value={filters.area}>
                <option value="">Todos</option>
                {catalogs?.areas.map((item) => <option key={item.id} value={item.id}>{`${item.code} - ${item.name}`}</option>)}
              </select>
            ),
          },
          {
            id: "quantity",
            label: "Cantidad",
            active: Boolean(filters.quantityMin || filters.quantityMax),
            content: (
              <div className="inline-filter-fields">
                <input aria-label="Cantidad minima" min="0" onChange={(event) => setFilter("quantityMin", event.target.value)} placeholder="Minima" type="number" value={filters.quantityMin} />
                <input aria-label="Cantidad maxima" min="0" onChange={(event) => setFilter("quantityMax", event.target.value)} placeholder="Maxima" type="number" value={filters.quantityMax} />
              </div>
            ),
          },
          {
            id: "status",
            label: "Estado",
            active: Boolean(filters.status),
            content: (
              <select aria-label="Estado de anomalia" onChange={(event) => setFilter("status", event.target.value)} value={filters.status}>
                <option value="">Todos</option>
                {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{humanizeToken(status)}</option>)}
              </select>
            ),
          },
          {
            id: "dates",
            label: "Fechas",
            active: Boolean(filters.dateFrom || filters.dateTo),
            content: (
              <div className="inline-filter-fields">
                <label className="field"><span>Desde</span><input onChange={(event) => setFilter("dateFrom", event.target.value)} type="date" value={filters.dateFrom} /></label>
                <label className="field"><span>Hasta</span><input onChange={(event) => setFilter("dateTo", event.target.value)} type="date" value={filters.dateTo} /></label>
              </div>
            ),
          },
        ]}
      />

      {exportError ? <div className="panel warning">{exportError}</div> : null}

      {data ? (
        <>
          <section className="stats-grid affected-orders-stats">
            <StatCard label="Ordenes diferentes" value={data.totals.unique_orders} hint="Tipo y numero unicos" tone="accent" />
            <StatCard label="Registros" value={data.totals.records} hint="Afectaciones encontradas" />
            <StatCard label="Anomalias" value={data.totals.anomalies} hint="Casos involucrados" tone="success" />
            <StatCard label="Cantidad total afectada" value={data.totals.total_quantity} hint="Segun los filtros aplicados" tone="warning" />
          </section>
          {data.totals.by_type.length ? (
            <div className="panel compact affected-orders-breakdown">
              <strong>Totales por tipo</strong>
              <div className="badge-stack horizontal">
                {data.totals.by_type.map((item) => (
                  <span className="status-badge info" key={item.order_type_id}>{`${item.code}: ${item.records} registro(s) / ${item.total_quantity} pieza(s)`}</span>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      <DataState
        loading={loading}
        error={error}
        onRetry={reload}
        empty={Boolean(data && data.count === 0)}
        emptyTitle="Sin ordenes afectadas"
        emptyDescription="No hay registros que coincidan con los filtros seleccionados."
      >
        {data ? (
          <section className="panel">
            <div className="data-table-wrap">
              <table className="data-table affected-orders-table">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Numero</th>
                    <th>Cantidad</th>
                    <th>Anomalia</th>
                    <th>Proceso</th>
                    <th>Fecha</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((item) => (
                    <tr key={item.id}>
                      <td><strong>{item.order_type.code}</strong><small>{item.order_type.name}</small></td>
                      <td>{item.number}</td>
                      <td>{item.quantity}</td>
                      <td><Link className="text-link" to={`/anomalies/${item.anomaly_id}`}>{item.anomaly_code}</Link><small>{item.anomaly_title}</small></td>
                      <td>{item.process?.name || "Sin proceso"}</td>
                      <td>{formatDateTime(item.detected_at)}</td>
                      <td><StatusBadge compact value={item.anomaly_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationControls disabled={loading} onPageChange={setPage} page={page} pageSize={PAGE_SIZE} totalCount={data.count} />
          </section>
        ) : null}
      </DataState>
    </section>
  );
}
