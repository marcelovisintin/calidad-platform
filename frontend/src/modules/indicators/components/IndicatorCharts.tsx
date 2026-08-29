import type { IndicatorBreakdownItem, IndicatorSeriesPoint } from "../../../api/types";


const SERIES_TONES = ["tone-1", "tone-2", "tone-3", "tone-4", "tone-5"];

function percentageLabel(value: number | null) {
  return value === null ? "Sin base" : `${value.toFixed(1)} %`;
}

export function IndicatorTrendChart({ series, visibleKeys }: { series: IndicatorSeriesPoint[]; visibleKeys?: string[] }) {
  const available = new Map<string, string>();
  series.forEach((point) => point.values.forEach((value) => available.set(value.key, value.label)));
  const keys = (visibleKeys?.length ? visibleKeys : Array.from(available.keys())).slice(0, 5);
  const maximum = Math.max(1, ...series.flatMap((point) => point.values.filter((item) => keys.includes(item.key)).map((item) => item.count)));

  if (!series.length || !keys.length) {
    return <p className="muted-copy">No hay datos mensuales para graficar.</p>;
  }

  return (
    <div className="indicator-chart-scroll">
      <div className="indicator-chart-legend">
        {keys.map((key, index) => <span key={key}><i className={SERIES_TONES[index]} />{available.get(key)}</span>)}
      </div>
      <div className="indicator-trend-chart" role="img" aria-label="Evolucion mensual del indicador">
        {series.map((point) => (
          <div className="indicator-month-group" key={point.period}>
            <div className="indicator-month-bars">
              {keys.map((key, index) => {
                const value = point.values.find((item) => item.key === key)?.count ?? 0;
                const percentage = point.values.find((item) => item.key === key)?.percentage;
                const detail = typeof percentage === "number" ? `${value} (${percentage.toFixed(1)} %)` : String(value);
                return (
                  <div
                    aria-label={`${point.label}, ${available.get(key)}: ${detail}`}
                    className={`indicator-month-bar ${SERIES_TONES[index]}`}
                    key={key}
                    style={{ height: `${Math.max(value ? 8 : 2, (value / maximum) * 100)}%` }}
                    title={`${available.get(key)}: ${detail}`}
                  >
                    {value ? <span>{value}</span> : null}
                  </div>
                );
              })}
            </div>
            <small>{point.label}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export function IndicatorBreakdownChart({ items }: { items: IndicatorBreakdownItem[] }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));

  if (!items.length) {
    return <p className="muted-copy">No hay distribucion disponible para el período.</p>;
  }

  return (
    <div className="indicator-breakdown-chart">
      {items.map((item) => (
        <div className="indicator-breakdown-row" key={item.key}>
          <div className="indicator-breakdown-label">
            <strong>{item.label}</strong>
            <span>{`${item.count} · ${percentageLabel(item.percentage)}${typeof item.cumulative_percentage === "number" ? ` · Acum. ${item.cumulative_percentage.toFixed(1)} %` : ""}`}</span>
          </div>
          <div className="indicator-breakdown-track">
            <span style={{ width: `${Math.max(item.count ? 2 : 0, (item.count / maximum) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
