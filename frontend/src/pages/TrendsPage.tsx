import { useEffect, useState } from "react";

import { emptyScopeMeta, getMeta, getPlayerTrends, getTeamTrends, normalizeScopeWithMeta } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { MultiMetricChart } from "../components/MultiMetricChart";
import { ScopeFilters } from "../components/ScopeFilters";
import { useLocalStorageState } from "../hooks";
import type { ScopeMeta, ScopeState, TrendsResponse } from "../types";
import { formatNumber } from "../utils";

const INITIAL_SCOPE: ScopeState = { season: "", league: "", phases: [], jornadas: [] };

function arraysEqual(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

export function TrendsPage() {
  const [scope, setScope] = useLocalStorageState<ScopeState>("react-trends-scope", INITIAL_SCOPE);
  const [meta, setMeta] = useState<ScopeMeta>(emptyScopeMeta());
  const [activeTab, setActiveTab] = useLocalStorageState<"players" | "teams">("react-trends-tab", "players");

  const [selectedPlayerKey, setSelectedPlayerKey] = useLocalStorageState<string>("react-trends-player", "");
  const [playerWindow, setPlayerWindow] = useLocalStorageState<number>("react-trends-player-window", 5);
  const [playerMetrics, setPlayerMetrics] = useLocalStorageState<string[]>("react-trends-player-metrics", ["PUNTOS"]);
  const [playerData, setPlayerData] = useState<TrendsResponse | null>(null);

  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-trends-team", "");
  const [teamWindow, setTeamWindow] = useLocalStorageState<number>("react-trends-team-window", 5);
  const [teamMetrics, setTeamMetrics] = useLocalStorageState<string[]>("react-trends-team-metrics", ["NETRTG"]);
  const [teamData, setTeamData] = useState<TrendsResponse | null>(null);

  useEffect(() => {
    void getMeta(scope).then((response) => {
      setMeta(response);
      setScope((current) => {
        const next = normalizeScopeWithMeta(current, response);
        return JSON.stringify(current) === JSON.stringify(next) ? current : next;
      });
    });
  }, [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|"), setScope]);

  useEffect(() => {
    if (activeTab !== "players" || !scope.season || !scope.league) {
      return;
    }
    void getPlayerTrends(scope, selectedPlayerKey, playerWindow, playerMetrics).then((response) => {
      setPlayerData(response);
      if ((response.selectedPlayerKey ?? "") !== selectedPlayerKey) {
        setSelectedPlayerKey(response.selectedPlayerKey ?? "");
      }
      if (response.window && response.window !== playerWindow) {
        setPlayerWindow(response.window);
      }
      if (!arraysEqual(response.selectedMetrics, playerMetrics)) {
        setPlayerMetrics(response.selectedMetrics);
      }
    });
  }, [
    activeTab,
    scope.season,
    scope.league,
    scope.phases.join("|"),
    scope.jornadas.join("|"),
    selectedPlayerKey,
    playerWindow,
    playerMetrics.join("|"),
    setPlayerMetrics,
    setPlayerWindow,
    setSelectedPlayerKey
  ]);

  useEffect(() => {
    if (activeTab !== "teams" || !scope.season || !scope.league) {
      return;
    }
    void getTeamTrends(scope, selectedTeam, teamWindow, teamMetrics).then((response) => {
      setTeamData(response);
      if ((response.selectedTeam ?? "") !== selectedTeam) {
        setSelectedTeam(response.selectedTeam ?? "");
      }
      if (response.window && response.window !== teamWindow) {
        setTeamWindow(response.window);
      }
      if (!arraysEqual(response.selectedMetrics, teamMetrics)) {
        setTeamMetrics(response.selectedMetrics);
      }
    });
  }, [
    activeTab,
    scope.season,
    scope.league,
    scope.phases.join("|"),
    scope.jornadas.join("|"),
    selectedTeam,
    teamWindow,
    teamMetrics.join("|"),
    setSelectedTeam,
    setTeamMetrics,
    setTeamWindow
  ]);

  const trendData = activeTab === "players" ? playerData : teamData;
  const selectedMetrics = activeTab === "players" ? playerMetrics : teamMetrics;

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Forma reciente</span>
            <h2>Tendencias</h2>
            <p className="panel-copy">
              Mismas tendencias de jugadores y equipos, pero con una disposicion mucho mas comoda para comparar ventana, metricas activas y lectura de la serie reciente.
            </p>
          </div>
          <div className="tab-row tab-row-wide">
            <button type="button" className={activeTab === "players" ? "tab-button is-active" : "tab-button"} onClick={() => setActiveTab("players")}>
              Jugadores
            </button>
            <button type="button" className={activeTab === "teams" ? "tab-button is-active" : "tab-button"} onClick={() => setActiveTab("teams")}>
              Equipos
            </button>
          </div>
        </div>

        {activeTab === "players" ? (
          <section className="control-panel">
            <div className="form-grid trend-control-grid">
              <label>
                Jugador
                <select value={selectedPlayerKey} onChange={(event) => setSelectedPlayerKey(event.target.value)}>
                  {(playerData?.players ?? meta.players).map((player) => (
                    <option key={player.playerKey} value={player.playerKey}>
                      {player.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Partidos a mostrar
                <input
                  type="number"
                  min={1}
                  max={Math.max(playerData?.windowMax ?? 1, 1)}
                  value={playerWindow}
                  onChange={(event) => setPlayerWindow(Number(event.target.value))}
                />
              </label>
              <div className="control-summary-card">
                <span className="metric-label">Metrica activa</span>
                <strong>{selectedMetrics.length ? selectedMetrics.join(", ") : "Sin metricas"}</strong>
                <span className="metric-hint">
                  {playerData?.recentCount ?? 0} partidos usados de {playerData?.windowMax ?? 0}
                </span>
              </div>
            </div>
            <div className="checkbox-grid">
              {(playerData?.availableMetrics ?? []).map((metric) => (
                <label key={metric.key} className={playerMetrics.includes(metric.key) ? "checkbox-chip is-selected" : "checkbox-chip"}>
                  <input
                    type="checkbox"
                    checked={playerMetrics.includes(metric.key)}
                    onChange={(event) =>
                      setPlayerMetrics((current) =>
                        event.target.checked ? [...current, metric.key] : current.filter((item) => item !== metric.key)
                      )
                    }
                  />
                  {metric.label}
                </label>
              ))}
            </div>
          </section>
        ) : (
          <section className="control-panel">
            <div className="form-grid trend-control-grid">
              <label>
                Equipo
                <select value={selectedTeam} onChange={(event) => setSelectedTeam(event.target.value)}>
                  {(teamData?.teams ?? meta.teams).map((team) => (
                    <option key={team.name} value={team.name}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Partidos a mostrar
                <input
                  type="number"
                  min={1}
                  max={Math.max(teamData?.windowMax ?? 1, 1)}
                  value={teamWindow}
                  onChange={(event) => setTeamWindow(Number(event.target.value))}
                />
              </label>
              <div className="control-summary-card">
                <span className="metric-label">Metrica activa</span>
                <strong>{selectedMetrics.length ? selectedMetrics.join(", ") : "Sin metricas"}</strong>
                <span className="metric-hint">
                  {teamData?.recentCount ?? 0} partidos usados de {teamData?.windowMax ?? 0}
                </span>
              </div>
            </div>
            <div className="checkbox-grid">
              {(teamData?.availableMetrics ?? []).map((metric) => (
                <label key={metric.key} className={teamMetrics.includes(metric.key) ? "checkbox-chip is-selected" : "checkbox-chip"}>
                  <input
                    type="checkbox"
                    checked={teamMetrics.includes(metric.key)}
                    onChange={(event) =>
                      setTeamMetrics((current) =>
                        event.target.checked ? [...current, metric.key] : current.filter((item) => item !== metric.key)
                      )
                    }
                  />
                  {metric.label}
                </label>
              ))}
            </div>
          </section>
        )}

        {trendData ? (
          <>
            <div className="metric-grid metric-grid-wide">
              {trendData.summaryRows.map((row) => (
                <MetricCard
                  key={row.metric}
                  label={row.metric}
                  value={formatNumber(row.recent_avg, 1)}
                  hint={`Scope ${formatNumber(row.scope_avg, 1)} · Delta ${formatNumber(row.delta, 1)}`}
                />
              ))}
            </div>

            <section className="panel panel-soft">
              <MultiMetricChart rows={trendData.chartRows} metrics={selectedMetrics} />
            </section>

            <DataTable
              title="Ultimos partidos"
              subtitle="Serie reciente ordenada por jornada para contrastar el grafico con el detalle de cada partido."
              columns={Object.keys(trendData.recentGames[0] ?? {})}
              rows={trendData.recentGames}
              idField="PARTIDO"
              defaultSortColumn="JORNADA"
              searchPlaceholder="Buscar rival, fase o resultado"
            />
          </>
        ) : (
          <p className="empty-state">Selecciona un jugador o un equipo para cargar la tendencia.</p>
        )}
      </section>
    </div>
  );
}
