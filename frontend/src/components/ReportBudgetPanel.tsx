import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { getReportBudget } from "../api";
import type { ReportBudgetResponse } from "../types";

type ReportKind = "player" | "team" | "phase";

const REPORT_KIND_LABELS: Record<ReportKind, string> = {
  player: "Jugador",
  team: "Equipo",
  phase: "Fase"
};

type ReportBudgetQueryLike = {
  data: ReportBudgetResponse | undefined;
  isLoading: boolean;
  isError: boolean;
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

export function useReportBudget() {
  return useQuery({
    queryKey: ["report-budget"],
    queryFn: ({ signal }) => getReportBudget({ signal })
  });
}

function buildKindSummary(data: ReportBudgetResponse, focusKind?: ReportKind) {
  if (!focusKind) {
    return `Quedan ${formatTokens(data.remainingTokens)} tokens este mes.`;
  }
  const label = REPORT_KIND_LABELS[focusKind].toLowerCase();
  return `${data.estimatedReportsRemaining[focusKind]} informes de ${label} estimados con el ritmo actual.`;
}

export function ReportBudgetPanel({ focusKind, budgetQuery }: { focusKind?: ReportKind; budgetQuery: ReportBudgetQueryLike }) {
  const monthLabel = useMemo(() => formatMonthLabel(budgetQuery.data?.monthIso ?? ""), [budgetQuery.data?.monthIso]);
  const data = budgetQuery.data;
  const shouldOpen = Boolean(data?.isWarning || data?.isBlocked || data?.warning);
  const summaryLabel = data
    ? `Consumo cloud: ${formatTokens(data.consumedTokens)} / ${formatTokens(data.monthlyTokens)}`
    : "Consumo cloud";

  if (budgetQuery.isLoading) {
    return (
      <details className="budget-disclosure">
        <summary>Consumo cloud</summary>
        <p className="detail-note">Cargando el contador mensual...</p>
      </details>
    );
  }

  if (budgetQuery.isError || !data) {
    return <p className="detail-note">No se ha podido cargar el contador cloud.</p>;
  }

  const alertClassName = data.isBlocked ? "budget-alert budget-alert-danger" : "budget-alert budget-alert-warning";
  const alertTitle = data.isBlocked ? "Generacion bloqueada" : "Margen ajustado";
  const compactMessage = data.message ?? buildKindSummary(data, focusKind);

  return (
    <div className="report-budget-shell">
      {data.isWarning || data.isBlocked ? (
        <section className={alertClassName}>
          <div>
            <strong>{alertTitle}</strong>
            <p>{compactMessage}</p>
          </div>
          <span className="budget-alert-pill">
            {formatTokens(data.consumedTokens)} / {formatTokens(data.hardLimitTokens)}
          </span>
        </section>
      ) : null}

      <details className="budget-disclosure" open={shouldOpen}>
        <summary>{summaryLabel}</summary>
        <div className="budget-disclosure-body">
          <p className="detail-note">
            {compactMessage} 1 token equivale a 1 segundo estimado de presupuesto Cloud Run en {monthLabel}.
          </p>
          <div className="budget-mini-grid">
            <div>
              <strong>{formatTokens(data.remainingTokens)}</strong>
              <span>restantes</span>
            </div>
            <div>
              <strong>{data.estimatedReportsRemaining.player}</strong>
              <span>jugador</span>
            </div>
            <div>
              <strong>{data.estimatedReportsRemaining.team}</strong>
              <span>equipo</span>
            </div>
            <div>
              <strong>{data.estimatedReportsRemaining.phase}</strong>
              <span>fase</span>
            </div>
          </div>
          {data.warning ? <p className="error-text">{data.warning}</p> : null}
        </div>
      </details>
    </div>
  );
}
