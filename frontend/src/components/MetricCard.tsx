type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  isLoading?: boolean;
};

export function MetricCard({ label, value, hint, isLoading = false }: MetricCardProps) {
  return (
    <div className={isLoading ? "metric-card is-loading" : "metric-card"}>
      <span className="metric-label">{label}</span>
      {isLoading ? <span className="skeleton-line skeleton-line-strong" /> : <strong className="metric-value">{value}</strong>}
      {hint ? <span className="metric-hint">{hint}</span> : null}
    </div>
  );
}
