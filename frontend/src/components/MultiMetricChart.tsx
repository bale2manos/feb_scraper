type MultiMetricChartProps = {
  rows: Record<string, unknown>[];
  metrics: string[];
};

const COLORS = ["#0f766e", "#dc2626", "#2563eb", "#d97706", "#7c3aed", "#0891b2"];

export function MultiMetricChart({ rows, metrics }: MultiMetricChartProps) {
  if (!rows.length || !metrics.length) {
    return <p className="empty-state">No hay datos suficientes para pintar el gráfico.</p>;
  }

  const width = 880;
  const height = 260;
  const padding = 32;
  const allValues = rows.flatMap((row) =>
    metrics.map((metric) => Number(row[metric] ?? 0)).filter((value) => Number.isFinite(value))
  );
  const maxValue = Math.max(...allValues, 1);
  const step = rows.length > 1 ? (width - padding * 2) / (rows.length - 1) : 0;

  return (
    <div className="chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Gráfico de tendencias">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="chart-axis" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} className="chart-axis" />
        {metrics.map((metric, metricIndex) => {
          const points = rows
            .map((row, rowIndex) => {
              const x = padding + rowIndex * step;
              const value = Number(row[metric] ?? 0);
              const y = height - padding - (value / maxValue) * (height - padding * 2);
              return `${x},${y}`;
            })
            .join(" ");
          return <polyline key={metric} fill="none" stroke={COLORS[metricIndex % COLORS.length]} strokeWidth="3" points={points} />;
        })}
        {rows.map((row, rowIndex) => {
          const x = padding + rowIndex * step;
          return (
            <text key={`label-${rowIndex}`} x={x} y={height - 8} textAnchor="middle" className="chart-label">
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
