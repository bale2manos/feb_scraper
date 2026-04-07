type MultiMetricChartProps = {
  rows: Record<string, unknown>[];
  metrics: string[];
  scaleMode?: "shared" | "normalized";
};

const COLORS = ["#0f766e", "#dc2626", "#2563eb", "#d97706", "#7c3aed", "#0891b2"];

function toNumeric(value: unknown) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function MultiMetricChart({ rows, metrics, scaleMode = "shared" }: MultiMetricChartProps) {
  if (!rows.length || !metrics.length) {
    return <p className="empty-state">No hay datos suficientes para pintar el grafico.</p>;
  }

  const width = Math.max(920, 88 * Math.max(rows.length, 2));
  const height = 320;
  const paddingLeft = 56;
  const paddingRight = 32;
  const paddingTop = 24;
  const paddingBottom = 52;
  const allValues = rows.flatMap((row) => metrics.map((metric) => toNumeric(row[metric])).filter((value): value is number => value !== null));
  const minValue = Math.min(...allValues, 0);
  const maxValue = Math.max(...allValues, 1);
  const range = maxValue - minValue || 1;
  const step = rows.length > 1 ? (width - paddingLeft - paddingRight) / (rows.length - 1) : 0;
  const yTicks = 4;
  const isNormalized = scaleMode === "normalized" && metrics.length > 1;

  const metricRanges = Object.fromEntries(
    metrics.map((metric) => {
      const values = rows.map((row) => toNumeric(row[metric])).filter((value): value is number => value !== null);
      const metricMin = Math.min(...values, 0);
      const metricMax = Math.max(...values, 1);
      return [metric, { min: metricMin, range: metricMax - metricMin || 1 }];
    })
  );

  function toY(value: number, metric: string) {
    const currentRange = isNormalized ? metricRanges[metric] : { min: minValue, range };
    return height - paddingBottom - ((value - currentRange.min) / currentRange.range) * (height - paddingTop - paddingBottom);
  }

  function buildLineSegments(metric: string) {
    const segments: string[] = [];
    let currentSegment: string[] = [];
    rows.forEach((row, rowIndex) => {
      const numeric = toNumeric(row[metric]);
      if (numeric === null) {
        if (currentSegment.length) {
          segments.push(currentSegment.join(" "));
          currentSegment = [];
        }
        return;
      }
      const x = paddingLeft + rowIndex * step;
      const y = toY(numeric, metric);
      currentSegment.push(`${x},${y}`);
    });
    if (currentSegment.length) {
      segments.push(currentSegment.join(" "));
    }
    return segments;
  }

  const axisLabels = Array.from({ length: yTicks + 1 }, (_, index) => {
    const value = isNormalized ? (100 / yTicks) * index : minValue + (range / yTicks) * index;
    return {
      value,
      y: height - paddingBottom - (index / yTicks) * (height - paddingTop - paddingBottom)
    };
  });

  return (
    <div className="chart-shell">
      <div className="chart-caption-row">
        <div>
          <h3 className="chart-title">Grafico</h3>
          <p className="chart-copy">Serie temporal dentro de la ventana seleccionada.</p>
        </div>
        {metrics.length > 1 ? <span className="chart-note">{isNormalized ? "Escala normalizada" : "Mismo eje Y"}</span> : null}
      </div>
      <div className="chart-scroll">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Grafico de tendencias">
          {axisLabels.map((tick) => (
            <g key={tick.value}>
              <line x1={paddingLeft} y1={tick.y} x2={width - paddingRight} y2={tick.y} className="chart-grid-line" />
              <text x={paddingLeft - 10} y={tick.y + 4} textAnchor="end" className="chart-axis-label">
                {isNormalized ? `${tick.value.toFixed(0)}%` : tick.value.toFixed(Math.abs(tick.value) >= 100 ? 0 : 1)}
              </text>
            </g>
          ))}
          <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} className="chart-axis" />
          <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={height - paddingBottom} className="chart-axis" />

          {metrics.map((metric, metricIndex) => {
            const color = COLORS[metricIndex % COLORS.length];
            const segments = buildLineSegments(metric);

            return (
              <g key={metric}>
                {segments.map((points, segmentIndex) => (
                  <polyline
                    key={`${metric}-segment-${segmentIndex}`}
                    fill="none"
                    stroke={color}
                    strokeWidth="3.5"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    points={points}
                  />
                ))}
                {rows.map((row, rowIndex) => {
                  const numeric = toNumeric(row[metric]);
                  if (numeric === null) {
                    return null;
                  }
                  const x = paddingLeft + rowIndex * step;
                  const y = toY(numeric, metric);
                  return <circle key={`${metric}-${rowIndex}`} cx={x} cy={y} r="4.5" fill="white" stroke={color} strokeWidth="2.5" />;
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
      </div>
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
