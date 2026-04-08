import { useEffect, useMemo } from "react";

import { generateTeamReport } from "../api";
import { MetricCard } from "../components/MetricCard";
import { ReportBudgetPanel } from "../components/ReportBudgetPanel";
import { ReportPreview } from "../components/ReportPreview";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeTaskKey, useReports } from "../reports";
import { useScopeMeta } from "../scope";
import type { ScopeState } from "../types";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

const LOCATION_FILTERS = ["Todos", "Local", "Visitante"];

export function TeamReportPage({ scope, setScope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const { getLatestJob, openPreview, startReportJob } = useReports();
  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-team-report-team", "");
  const [selectedPlayerKeys, setSelectedPlayerKeys] = useLocalStorageState<string[]>("react-team-report-players", []);
  const [selectedRival, setSelectedRival] = useLocalStorageState<string>("react-team-report-rival", "");
  const [homeAway, setHomeAway] = useLocalStorageState<string>("react-team-report-home-away", "Todos");
  const [h2hHomeAway, setH2hHomeAway] = useLocalStorageState<string>("react-team-report-h2h", "Todos");
  const [minGames, setMinGames] = useLocalStorageState<number>("react-team-report-min-games", 5);
  const [minMinutes, setMinMinutes] = useLocalStorageState<number>("react-team-report-min-minutes", 50);
  const [minShots, setMinShots] = useLocalStorageState<number>("react-team-report-min-shots", 20);

  const teamOptions = meta.teams.map((team) => ({ value: team.name, label: team.name }));
  const currentTeam = teamOptions.some((team) => team.value === selectedTeam) ? selectedTeam : teamOptions[0]?.value ?? "";
  const teamPlayers = meta.players.filter((player) => player.team === currentTeam);
  const teamPlayerOptions = teamPlayers.map((player) => ({ value: player.playerKey, label: player.label }));
  const validPlayerKeys = new Set(teamPlayers.map((player) => player.playerKey));
  const currentPlayerKeys = selectedPlayerKeys.filter((value) => validPlayerKeys.has(value));
  const rivalOptions = [{ value: "", label: "Sin rival concreto" }, ...teamOptions.filter((team) => team.value !== currentTeam)];

  useEffect(() => {
    if (currentTeam && currentTeam !== selectedTeam) {
      setSelectedTeam(currentTeam);
    }
  }, [currentTeam, selectedTeam, setSelectedTeam]);

  useEffect(() => {
    if (currentPlayerKeys.length !== selectedPlayerKeys.length) {
      setSelectedPlayerKeys(currentPlayerKeys);
    }
  }, [currentPlayerKeys, selectedPlayerKeys, setSelectedPlayerKeys]);

  useEffect(() => {
    if (selectedRival && !rivalOptions.some((team) => team.value === selectedRival)) {
      setSelectedRival("");
    }
  }, [rivalOptions, selectedRival, setSelectedRival]);

  const reportTaskKey = buildScopeTaskKey("team", scope, [
    currentTeam,
    currentPlayerKeys.join(","),
    selectedRival,
    homeAway,
    h2hHomeAway,
    minGames,
    minMinutes,
    minShots
  ]);
  const reportJob = getLatestJob(reportTaskKey);
  const error = reportJob?.status === "error" ? reportJob.error : null;

  async function handleGenerate() {
    if (!currentTeam) {
      return;
    }
    await startReportJob({
      taskKey: reportTaskKey,
      kind: "team",
      title: currentTeam,
      subtitle: `PDF de equipo${selectedRival ? ` | Rival ${selectedRival}` : ""}`,
      run: () =>
        generateTeamReport(scope, {
          team: currentTeam,
          playerKeys: currentPlayerKeys,
          rivalTeam: selectedRival,
          homeAway,
          h2hHomeAway,
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
            <h2>Equipo</h2>
            <p className="panel-copy">Genera el PDF de equipo con rival y filtros de plantilla.</p>
          </div>
          {reportJob?.status === "pending" ? <span className="status-badge">Generando</span> : null}
        </div>

        <div className="split-layout">
          <div className="split-main">
            <section className="control-panel">
              <div className="search-toolbar-grid">
                <SearchSelect
                  label="Equipo objetivo"
                  options={teamOptions}
                  value={currentTeam}
                  onChange={setSelectedTeam}
                  placeholder="Busca un equipo"
                  disabled={!teamOptions.length}
                />
                <SearchSelect
                  label="Rival H2H"
                  options={rivalOptions}
                  value={selectedRival}
                  onChange={setSelectedRival}
                  placeholder="Busca un rival"
                  disabled={!rivalOptions.length}
                />
              </div>

              <SearchMultiSelect
                label="Jugadores concretos"
                options={teamPlayerOptions}
                values={currentPlayerKeys}
                onChange={setSelectedPlayerKeys}
                placeholder="Busca jugadores"
                emptyText="No hay jugadores disponibles."
                suggestionLimit={5}
                showSuggestionsOnlyWhenQuery={true}
              />

              <div className="form-grid report-form-grid-wide">
                <label>
                  Filtro general
                  <div className="chip-grid">
                    {LOCATION_FILTERS.map((option) => (
                      <button
                        key={option}
                        type="button"
                        className={homeAway === option ? "filter-chip is-selected" : "filter-chip"}
                        onClick={() => setHomeAway(option)}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </label>
                <label>
                  Filtro H2H
                  <div className="chip-grid">
                    {LOCATION_FILTERS.map((option) => (
                      <button
                        key={option}
                        type="button"
                        className={h2hHomeAway === option ? "filter-chip is-selected" : "filter-chip"}
                        onClick={() => setH2hHomeAway(option)}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </label>
              </div>

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
                <MetricCard label="Equipo" value={currentTeam || "-"} />
                <MetricCard label="Jugadores marcados" value={String(currentPlayerKeys.length)} />
                <MetricCard label="Filtro general" value={homeAway} />
                <MetricCard label="Filtro H2H" value={h2hHomeAway} />
              </div>

              <ReportBudgetPanel focusKind="team" />

              {error ? <p className="error-text">{error}</p> : null}

              <div className="report-action-card">
                <div className="report-action-copy">
                  <span className="eyebrow">Salida</span>
                  <h3>Informe de equipo</h3>
                  <p className="panel-copy">
                    {currentTeam
                      ? `${currentTeam}${selectedRival ? ` | Rival ${selectedRival}` : ""} | ${currentPlayerKeys.length} jugadores fijados`
                      : "Selecciona un equipo para generar el PDF."}
                  </p>
                </div>
                <button
                  className="primary-cta-button"
                  type="button"
                  onClick={() => {
                    void handleGenerate();
                  }}
                  disabled={!currentTeam || reportJob?.status === "pending"}
                >
                  {reportJob?.status === "pending" ? "Generando PDF..." : "Generar informe PDF"}
                </button>
              </div>
            </section>
          </div>

          <aside className="split-side">
            <ReportPreview
              title={reportJob?.title ?? currentTeam ?? "Informe de equipo"}
              subtitle="Vista previa y descarga del PDF."
              report={reportJob?.report ?? null}
              emptyMessage="Genera un informe para verlo aqui."
              isGenerating={reportJob?.status === "pending"}
              statusMessage="Generando el PDF del equipo."
              onOpenFloating={reportJob?.report ? () => openPreview(reportJob.id) : null}
            />
          </aside>
        </div>
      </section>
    </div>
  );
}
