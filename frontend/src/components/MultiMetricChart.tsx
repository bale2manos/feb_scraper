type MultiMetricChartProps = {
  rows: Record<string, unknown>[];
  metrics: string[];
};

const COLORS = ["#0f766e", "#dc2626", "#2563eb", "#d97706", "#7c3aed", "#0891b2"];

export function MultiMetricChart({ rows, metrics }: MultiMetricChartProps) {
  if (!rows.length || !metrics.length) {
    return <p className="empty-state">No hay datos suficientes para pintar el grafico.</p>;
  }

  const width = 920;
  const height = 320;
  const paddingLeft = 56;
  const paddingRight = 32;
  const paddingTop = 24;
  const paddingBottom = 52;
  const allValues = rows.flatMap((row) =>
    metrics.map((metric) => Number(row[metric] ?? 0)).filter((value) => Number.isFinite(value))
  );
  const minValue = Math.min(...allValues, 0);
  const maxValue = Math.max(...allValues, 1);
  const range = maxValue - minValue || 1;
  const step = rows.length > 1 ? (width - paddingLeft - paddingRight) / (rows.length - 1) : 0;
  const yTicks = 4;

  function toY(value: number) {
    return height - paddingBottom - ((value - minValue) / range) * (height - paddingTop - paddingBottom);
  }

  const axisLabels = Array.from({ length: yTicks + 1 }, (_, index) => {
    const value = minValue + (range / yTicks) * index;
    return {
      value,
      y: toY(value)
    };
  });

  return (
    <div className="chart-shell">
      <div className="chart-caption-row">
        <div>
          <h3 className="chart-title">Evolucion reciente</h3>
          <p className="chart-copy">Cruza varias metricas en el mismo grafico para ver cambios de rol, forma o contexto competitivo.</p>
        </div>
        {metrics.length > 1 ? <span className="chart-note">Las metricas comparten el mismo eje Y</span> : null}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Grafico de tendencias">
        {axisLabels.map((tick) => (
          <g key={tick.value}>
            <line
              x1={paddingLeft}
              y1={tick.y}
              x2={width - paddingRight}
              y2={tick.y}
              className="chart-grid-line"
            />
            <text x={paddingLeft - 10} y={tick.y + 4} textAnchor="end" className="chart-axis-label">
              {tick.value.toFixed(Math.abs(tick.value) >= 100 ? 0 : 1)}
            </text>
          </g>
        ))}
        <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} className="chart-axis" />
        <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={height - paddingBottom} className="chart-axis" />

        {metrics.map((metric, metricIndex) => {
          const color = COLORS[metricIndex % COLORS.length];
          const points = rows
            .map((row, rowIndex) => {
              const x = paddingLeft + rowIndex * step;
              const value = Number(row[metric] ?? 0);
              const y = toY(value);
              return `${x},${y}`;
            })
            .join(" ");

          return (
            <g key={metric}>
              <polyline
                fill="none"
                stroke={color}
                strokeWidth="3.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                points={points}
              />
              {rows.map((row, rowIndex) => {
                const x = paddingLeft + rowIndex * step;
                const value = Number(row[metric] ?? 0);
                const y = toY(value);
                return (
                  <circle
                    key={`${metric}-${rowIndex}`}
                    cx={x}
                    cy={y}
                    r="4.5"
                    fill="white"
                    stroke={color}
                    strokeWidth="2.5"
                  />
                );
              })}
            </g>
          );
        })}

        {rows.map((row, rowIndex) => {
          const x = paddingLeft + rowIndex * step;
          const shouldRenderLabel = rows.length <= 8 || rowIndex === 0 || rowIndex === rows.length - 1 || rowIndex % 2 === 0;
          if (!shouldRenderLabel) {
            return null;
          }
          return (
            <text key={`label-${rowIndex}`} x={x} y={height - 18} textAnchor="middle" className="chart-label">
              {String(row.PARTIDO ?? "")}
            </text>
          );
        })}
      </svg>
      <div className="chart-legend">
        {metrics.map((metric, index) => (
          <span className="legend-item" key={metric}>
            <span className="legend-swatch" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
            {metric}
          </span>
        ))}
      </div>
    </div>
  );
}
