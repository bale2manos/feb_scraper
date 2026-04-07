import { useEffect } from "react";

import { generatePhaseReport } from "../api";
import { MetricCard } from "../components/MetricCard";
import { ReportPreview } from "../components/ReportPreview";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeTaskKey, useReports } from "../reports";
import { useScopeMeta } from "../scope";
import type { ScopeState } from "../types";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

export function PhaseReportPage({ scope, setScope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const { getLatestJob, openPreview, startReportJob } = useReports();
  const [selectedTeams, setSelectedTeams] = useLocalStorageState<string[]>("react-phase-report-teams", []);
  const [minGames, setMinGames] = useLocalStorageState<number>("react-phase-report-min-games", 5);
  const [minMinutes, setMinMinutes] = useLocalStorageState<number>("react-phase-report-min-minutes", 50);
  const [minShots, setMinShots] = useLocalStorageState<number>("react-phase-report-min-shots", 20);

  const teamOptions = meta.teams.map((team) => ({ value: team.name, label: team.name }));
  const validSelectedTeams = selectedTeams.filter((team) => teamOptions.some((option) => option.value === team));

  useEffect(() => {
    if (validSelectedTeams.length !== selectedTeams.length) {
      setSelectedTeams(validSelectedTeams);
    }
  }, [selectedTeams, setSelectedTeams, validSelectedTeams]);

  const phaseSummary = scope.phases.length ? scope.phases.join(", ") : "todas las fases";
  const reportTaskKey = buildScopeTaskKey("phase", scope, [validSelectedTeams.join(","), minGames, minMinutes, minShots]);
  const reportJob = getLatestJob(reportTaskKey);
  const error = reportJob?.status === "error" ? reportJob.error : null;

  async function handleGenerate() {
    await startReportJob({
      taskKey: reportTaskKey,
      kind: "phase",
      title: "Informe de fase",
      subtitle: `${validSelectedTeams.length || "Todos"} equipos | ${phaseSummary}`,
      run: () =>
        generatePhaseReport(scope, {
          teams: validSelectedTeams,
          minGames,
          minMinutes,
          minShots
        }),
      getReport: (result) => result.report
    });
  }

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Informe</span>
            <h2>Fase</h2>
            <p className="panel-copy">Genera el PDF comparativo de la fase filtrada.</p>
          </div>
          {reportJob?.status === "pending" ? <span className="status-badge">Generando</span> : null}
        </div>

        <div className="split-layout">
          <div className="split-main">
            <section className="control-panel">
              <div className="insight-banner">
                <strong>Filtros</strong>
                <span>Fases activas: {phaseSummary}</span>
              </div>

              <SearchMultiSelect
                label="Equipos a incluir"
                options={teamOptions}
                values={validSelectedTeams}
                onChange={setSelectedTeams}
                placeholder="Busca equipos"
                emptyText="No hay equipos disponibles."
                suggestionLimit={5}
                showSuggestionsOnlyWhenQuery={true}
              />

              <div className="form-grid report-threshold-grid">
                <label>
                  Min partidos
                  <input type="number" min={0} value={minGames} onChange={(event) => setMinGames(Number(event.target.value) || 0)} />
                </label>
                <label>
                  Min minutos
                  <input type="number" min={0} value={minMinutes} onChange={(event) => setMinMinutes(Number(event.target.value) || 0)} />
                </label>
                <label>
                  Min tiros
                  <input type="number" min={0} value={minShots} onChange={(event) => setMinShots(Number(event.target.value) || 0)} />
                </label>
              </div>

              <div className="metric-grid metric-grid-wide">
                <MetricCard label="Equipos marcados" value={String(validSelectedTeams.length)} />
                <MetricCard label="Min partidos" value={String(minGames)} />
                <MetricCard label="Min minutos" value={String(minMinutes)} />
                <MetricCard label="Min tiros" value={String(minShots)} />
              </div>

              {error ? <p className="error-text">{error}</p> : null}

              <div className="report-action-card">
                <div className="report-action-copy">
                  <span className="eyebrow">Salida</span>
                  <h3>Informe comparativo</h3>
                  <p className="panel-copy">
                    {validSelectedTeams.length
                      ? `${validSelectedTeams.length} equipos incluidos | ${phaseSummary}`
                      : `Comparativa abierta para ${phaseSummary}`}
                  </p>
                </div>
                <button
                  className="primary-cta-button"
                  type="button"
                  onClick={() => {
                    void handleGenerate();
                  }}
                  disabled={reportJob?.status === "pending"}
                >
                  {reportJob?.status === "pending" ? "Generando PDF..." : "Generar informe PDF"}
                </button>
              </div>
            </section>
          </div>

          <aside className="split-side">
            <ReportPreview
              title={reportJob?.title ?? "Informe de fase"}
              subtitle="Vista previa y descarga del PDF."
              report={reportJob?.report ?? null}
              emptyMessage="Genera un informe para verlo aqui."
              isGenerating={reportJob?.status === "pending"}
              statusMessage="Generando el PDF comparativo."
              onOpenFloating={reportJob?.report ? () => openPreview(reportJob.id) : null}
            />
          </aside>
        </div>
      </section>
    </div>
  );
}
