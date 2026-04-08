import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { getReportBudget } from "../api";
import { MetricCard } from "./MetricCard";

type ReportKind = "player" | "team" | "phase";

const REPORT_KIND_LABELS: Record<ReportKind, string> = {
  player: "Jugador",
  team: "Equipo",
  phase: "Fase"
};

function formatTokens(value: number) {
  return Math.max(0, Math.round(value)).toLocaleString("es-ES");
}

function formatMonthLabel(monthIso: string) {
  const date = new Date(monthIso);
  if (Number.isNaN(date.getTime())) {
    return "mes actual";
  }
  return new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(date);
}

export function ReportBudgetPanel({ focusKind }: { focusKind?: ReportKind }) {
  const budgetQuery = useQuery({
    queryKey: ["report-budget"],
    queryFn: ({ signal }) => getReportBudget({ signal })
  });

  const monthLabel = useMemo(() => formatMonthLabel(budgetQuery.data?.monthIso ?? ""), [budgetQuery.data?.monthIso]);

  return (
    <section className="compact-control-card report-budget-panel">
      <div className="report-budget-header">
        <div>
          <span className="eyebrow">Cloud budget</span>
          <h3>Tokens restantes del mes</h3>
          <p className="panel-copy">
            {budgetQuery.data
              ? `1 token equivale a 1 segundo estimado de presupuesto Cloud Run en ${monthLabel}.`
              : "Medimos el consumo real de informes para estimar cuanta bolsa queda este mes."}
          </p>
        </div>
        {budgetQuery.data?.warning ? <span className="status-badge warning-badge">Tracking limitado</span> : null}
      </div>

      <div className="metric-grid metric-grid-wide">
        <MetricCard
          label="Tokens restantes"
          value={budgetQuery.data ? formatTokens(budgetQuery.data.remainingTokens) : "-"}
          hint={budgetQuery.data ? `${budgetQuery.data.percentRemaining.toFixed(1)}% del mes` : undefined}
          isLoading={budgetQuery.isLoading}
        />
        <MetricCard
          label="Tokens gastados"
          value={budgetQuery.data ? formatTokens(budgetQuery.data.consumedTokens) : "-"}
          hint={budgetQuery.data ? `${formatTokens(budgetQuery.data.monthlyTokens)} tokens al mes` : undefined}
          isLoading={budgetQuery.isLoading}
        />
        <MetricCard
          label="Jugador restantes"
          value={budgetQuery.data ? String(budgetQuery.data.estimatedReportsRemaining.player) : "-"}
          hint={
            budgetQuery.data
              ? `${budgetQuery.data.counts.player} generados | media ${budgetQuery.data.averageTokens.player.toFixed(1)} tokens`
              : undefined
          }
          isLoading={budgetQuery.isLoading}
        />
        <MetricCard
          label="Equipo restantes"
          value={budgetQuery.data ? String(budgetQuery.data.estimatedReportsRemaining.team) : "-"}
          hint={
            budgetQuery.data
              ? `${budgetQuery.data.counts.team} generados | media ${budgetQuery.data.averageTokens.team.toFixed(1)} tokens`
              : undefined
          }
          isLoading={budgetQuery.isLoading}
        />
        <MetricCard
          label="Fase restantes"
          value={budgetQuery.data ? String(budgetQuery.data.estimatedReportsRemaining.phase) : "-"}
          hint={
            budgetQuery.data
              ? `${budgetQuery.data.counts.phase} generados | media ${budgetQuery.data.averageTokens.phase.toFixed(1)} tokens`
              : undefined
          }
          isLoading={budgetQuery.isLoading}
        />
      </div>

      <p className="report-budget-note">
        {budgetQuery.data
          ? `Ritmo actual: Jugador ${budgetQuery.data.averageTokens.player.toFixed(1)} | Equipo ${budgetQuery.data.averageTokens.team.toFixed(1)} | Fase ${budgetQuery.data.averageTokens.phase.toFixed(1)} tokens.`
          : "En cuanto generes informes, la estimacion se ajustara con tus tiempos reales."}
        {focusKind ? ` En esta pantalla ahora mismo manda el coste de ${REPORT_KIND_LABELS[focusKind].toLowerCase()}.` : ""}
      </p>

      {budgetQuery.data?.warning ? <p className="error-text">{budgetQuery.data.warning}</p> : null}
      {budgetQuery.isError ? <p className="error-text">No se ha podido cargar el contador mensual.</p> : null}
    </section>
  );
}
