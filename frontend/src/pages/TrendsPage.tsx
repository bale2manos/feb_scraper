import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { getPlayerTrends, getTeamTrends } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { MultiMetricChart } from "../components/MultiMetricChart";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeQueryKey, useScopeMeta } from "../scope";
import type { ScopeState, TrendsResponse } from "../types";
import { formatNumber } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

function arraysEqual(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function clampWindow(nextValue: number, maxValue: number) {
  if (!Number.isFinite(nextValue)) {
    return 1;
  }
  return Math.min(Math.max(Math.round(nextValue), 1), Math.max(maxValue, 1));
}

function buildComparisonChartRows<T extends { selectedMetrics: string[]; chartRows: Record<string, unknown>[] }>(
  responses: T[],
  labels: string[],
  metricKey: string
) {
  const jornadas = Array.from(
    new Set(
      responses.flatMap((response) =>
        response.chartRows
          .map((row) => Number(row.JORNADA))
          .filter((value) => Number.isFinite(value))
      )
    )
  ).sort((left, right) => left - right);

  if (!jornadas.length) {
    const maxCount = Math.max(...responses.map((response) => response.chartRows.length), 0);
    return Array.from({ length: maxCount }, (_, index) => {
      const row: Record<string, unknown> = {
        PARTIDO: `Tramo ${index + 1}`
      };
      responses.forEach((response, responseIndex) => {
        const sourceRow = response.chartRows[index] ?? null;
        row[labels[responseIndex]] = sourceRow ? sourceRow[metricKey] : null;
      });
      return row;
    });
  }

  return jornadas.map((jornada) => {
    const row: Record<string, unknown> = {
      JORNADA: jornada,
      PARTIDO: `J${jornada}`
    };
    responses.forEach((response, responseIndex) => {
      const sourceRow = response.chartRows.find((candidate) => Number(candidate.JORNADA) === jornada) ?? null;
      row[labels[responseIndex]] = sourceRow ? sourceRow[metricKey] : null;
    });
    return row;
  });
}

export function TrendsPage({ scope, setScope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const [activeTab, setActiveTab] = useLocalStorageState<"players" | "teams">("react-trends-tab", "players");

  const [selectedPlayerKey, setSelectedPlayerKey] = useLocalStorageState<string>("react-trends-player", "");
  const [playerWindow, setPlayerWindow] = useLocalStorageState<number>("react-trends-player-window", 5);
  const [playerMetrics, setPlayerMetrics] = useLocalStorageState<string[]>("react-trends-player-metrics", ["PUNTOS"]);
  const [playerCompareKeys, setPlayerCompareKeys] = useLocalStorageState<string[]>("react-trends-player-compare-keys", []);
  const [playerCompareMetric, setPlayerCompareMetric] = useLocalStorageState<string>("react-trends-player-compare-metric", "PUNTOS");
  const [playerScaleMode, setPlayerScaleMode] = useLocalStorageState<"shared" | "normalized">("react-trends-player-scale-mode", "shared");

  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-trends-team", "");
  const [teamWindow, setTeamWindow] = useLocalStorageState<number>("react-trends-team-window", 5);
  const [teamMetrics, setTeamMetrics] = useLocalStorageState<string[]>("react-trends-team-metrics", ["NETRTG"]);
  const [teamCompareKeys, setTeamCompareKeys] = useLocalStorageState<string[]>("react-trends-team-compare-keys", []);
  const [teamCompareMetric, setTeamCompareMetric] = useLocalStorageState<string>("react-trends-team-compare-metric", "NETRTG");
  const [teamScaleMode, setTeamScaleMode] = useLocalStorageState<"shared" | "normalized">("react-trends-team-scale-mode", "shared");

  const playerQuery = useQuery({
    queryKey: ["trends-player", ...buildScopeQueryKey(scope), selectedPlayerKey, playerWindow, playerMetrics.join("|")],
    queryFn: ({ signal }) => getPlayerTrends(scope, selectedPlayerKey, playerWindow, playerMetrics, { signal }),
    enabled: activeTab === "players" && Boolean(scope.season && scope.league),
    placeholderData: keepPreviousData
  });
  const playerData = playerQuery.data ?? null;

  useEffect(() => {
    if (!playerData || playerQuery.isPlaceholderData) {
      return;
    }
    if ((playerData.selectedPlayerKey ?? "") !== selectedPlayerKey) {
      setSelectedPlayerKey(playerData.selectedPlayerKey ?? "");
    }
    if (playerData.window && playerData.window !== playerWindow) {
      setPlayerWindow(playerData.window);
    }
    if (!arraysEqual(playerData.selectedMetrics, playerMetrics)) {
      setPlayerMetrics(playerData.selectedMetrics);
    }
    const validMetricKeys = new Set(playerData.availableMetrics.map((metric) => metric.key));
    if (!validMetricKeys.has(playerCompareMetric)) {
      setPlayerCompareMetric(playerData.availableMetrics[0]?.key ?? "PUNTOS");
    }
  }, [
    playerCompareMetric,
    playerData,
    playerMetrics,
    playerQuery.isPlaceholderData,
    playerWindow,
    selectedPlayerKey,
    setPlayerCompareMetric,
    setPlayerMetrics,
    setPlayerWindow,
    setSelectedPlayerKey
  ]);

  const playerOptions = playerData?.players ?? meta.players;
  const playerOptionsForSelect = playerOptions.map((player) => ({ value: player.playerKey, label: player.label }));
  const playerLabelMap = new Map(playerOptions.map((player) => [player.playerKey, player.label]));

  useEffect(() => {
    const validKeys = new Set(playerOptions.map((player) => player.playerKey));
    setPlayerCompareKeys((current) => current.filter((value) => validKeys.has(value) && value !== selectedPlayerKey));
  }, [playerOptions, selectedPlayerKey, setPlayerCompareKeys]);

  const playerCompareTargetKeys = useMemo(() => {
    const unique = new Set<string>();
    if (selectedPlayerKey) {
      unique.add(selectedPlayerKey);
    }
    playerCompareKeys.forEach((value) => {
      if (value && value !== selectedPlayerKey) {
        unique.add(value);
      }
    });
    return [...unique];
  }, [playerCompareKeys, selectedPlayerKey]);

  const playerCompareQuery = useQuery({
    queryKey: ["trends-player-compare", ...buildScopeQueryKey(scope), playerCompareTargetKeys.join("|"), playerWindow, playerCompareMetric],
    queryFn: async ({ signal }) => {
      const responses = await Promise.all(
        playerCompareTargetKeys.map((playerKey) => getPlayerTrends(scope, playerKey, playerWindow, [playerCompareMetric], { signal }))
      );
      const nextData: Record<string, TrendsResponse> = {};
      responses.forEach((response) => {
        const playerKey = response.selectedPlayerKey ?? "";
        if (playerKey) {
          nextData[playerKey] = response;
        }
      });
      return nextData;
    },
    enabled: activeTab === "players" && Boolean(scope.season && scope.league && playerCompareTargetKeys.length && playerCompareMetric),
    placeholderData: keepPreviousData
  });
  const playerCompareData = playerCompareQuery.data ?? {};

  const teamQuery = useQuery({
    queryKey: ["trends-team", ...buildScopeQueryKey(scope), selectedTeam, teamWindow, teamMetrics.join("|")],
    queryFn: ({ signal }) => getTeamTrends(scope, selectedTeam, teamWindow, teamMetrics, { signal }),
    enabled: activeTab === "teams" && Boolean(scope.season && scope.league),
    placeholderData: keepPreviousData
  });
  const teamData = teamQuery.data ?? null;

  useEffect(() => {
    if (!teamData || teamQuery.isPlaceholderData) {
      return;
    }
    if ((teamData.selectedTeam ?? "") !== selectedTeam) {
      setSelectedTeam(teamData.selectedTeam ?? "");
    }
    if (teamData.window && teamData.window !== teamWindow) {
      setTeamWindow(teamData.window);
    }
    if (!arraysEqual(teamData.selectedMetrics, teamMetrics)) {
      setTeamMetrics(teamData.selectedMetrics);
    }
    const validMetricKeys = new Set(teamData.availableMetrics.map((metric) => metric.key));
    if (!validMetricKeys.has(teamCompareMetric)) {
      setTeamCompareMetric(teamData.availableMetrics[0]?.key ?? "NETRTG");
    }
  }, [
    selectedTeam,
    setSelectedTeam,
    setTeamCompareMetric,
    setTeamMetrics,
    setTeamWindow,
    teamCompareMetric,
    teamData,
    teamMetrics,
    teamQuery.isPlaceholderData,
    teamWindow
  ]);

  const teamOptions = teamData?.teams ?? meta.teams;
  const teamOptionsForSelect = teamOptions.map((team) => ({ value: team.name, label: team.name }));
  const teamLabelMap = new Map(teamOptions.map((team) => [team.name, team.name]));

  useEffect(() => {
    const validTeams = new Set(teamOptions.map((team) => team.name));
    setTeamCompareKeys((current) => current.filter((value) => validTeams.has(value) && value !== selectedTeam));
  }, [selectedTeam, setTeamCompareKeys, teamOptions]);

  const teamCompareTargetKeys = useMemo(() => {
    const unique = new Set<string>();
    if (selectedTeam) {
      unique.add(selectedTeam);
    }
    teamCompareKeys.forEach((value) => {
      if (value && value !== selectedTeam) {
        unique.add(value);
      }
    });
    return [...unique];
  }, [selectedTeam, teamCompareKeys]);

  const teamCompareQuery = useQuery({
    queryKey: ["trends-team-compare", ...buildScopeQueryKey(scope), teamCompareTargetKeys.join("|"), teamWindow, teamCompareMetric],
    queryFn: async ({ signal }) => {
      const responses = await Promise.all(
        teamCompareTargetKeys.map((team) => getTeamTrends(scope, team, teamWindow, [teamCompareMetric], { signal }))
      );
      const nextData: Record<string, TrendsResponse> = {};
      responses.forEach((response) => {
        const team = response.selectedTeam ?? "";
        if (team) {
          nextData[team] = response;
        }
      });
      return nextData;
    },
    enabled: activeTab === "teams" && Boolean(scope.season && scope.league && teamCompareTargetKeys.length && teamCompareMetric),
    placeholderData: keepPreviousData
  });
  const teamCompareData = teamCompareQuery.data ?? {};

  const trendData = activeTab === "players" ? playerData : teamData;
  const selectedMetrics = activeTab === "players" ? playerMetrics : teamMetrics;
  const playerWindowMax = Math.max(playerData?.windowMax ?? 1, 1);
  const teamWindowMax = Math.max(teamData?.windowMax ?? 1, 1);
  const compareMetricLabel =
    playerData?.availableMetrics.find((metric) => metric.key === playerCompareMetric)?.label ?? playerCompareMetric;
  const teamCompareMetricLabel =
    teamData?.availableMetrics.find((metric) => metric.key === teamCompareMetric)?.label ?? teamCompareMetric;

  const playerComparisonResponses = useMemo(
    () => playerCompareTargetKeys.map((key) => playerCompareData[key]).filter((response): response is TrendsResponse => Boolean(response)),
    [playerCompareData, playerCompareTargetKeys]
  );
  const playerComparisonLabels = playerComparisonResponses.map(
    (response) => playerLabelMap.get(response.selectedPlayerKey ?? "") ?? String(response.selectedPlayerKey ?? "")
  );
  const playerComparisonChartRows = buildComparisonChartRows(playerComparisonResponses, playerComparisonLabels, playerCompareMetric);
  const playerComparisonSummaryRows = playerComparisonResponses
    .map((response) => {
      const summary = response.summaryRows.find((row) => row.metric === playerCompareMetric);
      return {
        JUGADOR: playerLabelMap.get(response.selectedPlayerKey ?? "") ?? String(response.selectedPlayerKey ?? ""),
        MEDIA_RECIENTE: summary?.recent_avg ?? 0,
        MEDIA_FILTRO: summary?.scope_avg ?? 0,
        DELTA: summary?.delta ?? 0,
        PARTIDOS: response.recentCount
      };
    })
    .sort((left, right) => Number(right.MEDIA_RECIENTE) - Number(left.MEDIA_RECIENTE));

  const teamComparisonResponses = useMemo(
    () => teamCompareTargetKeys.map((key) => teamCompareData[key]).filter((response): response is TrendsResponse => Boolean(response)),
    [teamCompareData, teamCompareTargetKeys]
  );
  const teamComparisonLabels = teamComparisonResponses.map(
    (response) => teamLabelMap.get(response.selectedTeam ?? "") ?? String(response.selectedTeam ?? "")
  );
  const teamComparisonChartRows = buildComparisonChartRows(teamComparisonResponses, teamComparisonLabels, teamCompareMetric);
  const teamComparisonSummaryRows = teamComparisonResponses
    .map((response) => {
      const summary = response.summaryRows.find((row) => row.metric === teamCompareMetric);
      return {
        EQUIPO: teamLabelMap.get(response.selectedTeam ?? "") ?? String(response.selectedTeam ?? ""),
        MEDIA_RECIENTE: summary?.recent_avg ?? 0,
        MEDIA_FILTRO: summary?.scope_avg ?? 0,
        DELTA: summary?.delta ?? 0,
        PARTIDOS: response.recentCount
      };
    })
    .sort((left, right) => Number(right.MEDIA_RECIENTE) - Number(left.MEDIA_RECIENTE));

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Tendencias</span>
            <h2>Tendencias</h2>
            <p className="panel-copy">Evolucion reciente de jugadores y equipos.</p>
          </div>
          <div className="tab-row tab-row-wide">
            {(playerQuery.isFetching || teamQuery.isFetching || playerCompareQuery.isFetching || teamCompareQuery.isFetching) &&
            !(playerQuery.isLoading || teamQuery.isLoading || playerCompareQuery.isLoading || teamCompareQuery.isLoading) ? (
              <span className="status-badge">Actualizando</span>
            ) : null}
            <button type="button" className={activeTab === "players" ? "tab-button is-active" : "tab-button"} onClick={() => setActiveTab("players")}>
              Jugadores
            </button>
            <button type="button" className={activeTab === "teams" ? "tab-button is-active" : "tab-button"} onClick={() => setActiveTab("teams")}>
              Equipos
            </button>
          </div>
        </div>

        {trendData ? (
          <>
            <div className="metric-grid metric-grid-wide">
              {trendData.summaryRows.map((row) => (
                <MetricCard
                  key={row.metric}
                  label={row.metric}
                  value={formatNumber(row.recent_avg, 1)}
                  hint={`Media del filtro ${formatNumber(row.scope_avg, 1)} | Delta ${formatNumber(row.delta, 1)}`}
                  isLoading={activeTab === "players" ? playerQuery.isLoading : teamQuery.isLoading}
                />
              ))}
            </div>

            <section className="panel panel-soft">
              {activeTab === "players" ? (
                <div className="trend-control-block">
                  <div className="search-toolbar-grid">
                    <SearchSelect
                      label="Jugador"
                      options={playerOptionsForSelect}
                      value={selectedPlayerKey}
                      onChange={setSelectedPlayerKey}
                      placeholder="Busca un jugador"
                      disabled={!playerOptionsForSelect.length}
                    />
                    <div className="compact-control-card">
                      <label>
                        Partidos a mostrar
                        <input
                          type="number"
                          min={1}
                          max={playerWindowMax}
                          value={playerWindow}
                          onChange={(event) => setPlayerWindow(clampWindow(Number(event.target.value), playerWindowMax))}
                        />
                      </label>
                      <span className="detail-note">
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
                </div>
              ) : (
                <div className="trend-control-block">
                  <div className="search-toolbar-grid">
                    <SearchSelect
                      label="Equipo"
                      options={teamOptionsForSelect}
                      value={selectedTeam}
                      onChange={setSelectedTeam}
                      placeholder="Busca un equipo"
                      disabled={!teamOptionsForSelect.length}
                    />
                    <div className="compact-control-card">
                      <label>
                        Partidos a mostrar
                        <input
                          type="number"
                          min={1}
                          max={teamWindowMax}
                          value={teamWindow}
                          onChange={(event) => setTeamWindow(clampWindow(Number(event.target.value), teamWindowMax))}
                        />
                      </label>
                      <span className="detail-note">
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
                </div>
              )}

              {selectedMetrics.length > 1 ? (
                <div className="toolbar">
                  <span className="detail-note">Escala del grafico</span>
                  <button
                    type="button"
                    className={(activeTab === "players" ? playerScaleMode : teamScaleMode) === "shared" ? "tab-button is-active" : "tab-button"}
                    onClick={() => (activeTab === "players" ? setPlayerScaleMode("shared") : setTeamScaleMode("shared"))}
                  >
                    Compartida
                  </button>
                  <button
                    type="button"
                    className={(activeTab === "players" ? playerScaleMode : teamScaleMode) === "normalized" ? "tab-button is-active" : "tab-button"}
                    onClick={() => (activeTab === "players" ? setPlayerScaleMode("normalized") : setTeamScaleMode("normalized"))}
                  >
                    Normalizada
                  </button>
                </div>
              ) : null}
              <MultiMetricChart rows={trendData.chartRows} metrics={selectedMetrics} scaleMode={activeTab === "players" ? playerScaleMode : teamScaleMode} />
            </section>

            {activeTab === "players" ? (
              <section className="panel panel-soft">
                <div className="comparison-panel">
                  <div className="comparison-panel-header">
                    <div>
                      <h3>Comparar jugadores</h3>
                      <p className="panel-copy">El jugador principal siempre se incluye.</p>
                    </div>
                    <label>
                      Metrica comparada
                      <select value={playerCompareMetric} onChange={(event) => setPlayerCompareMetric(event.target.value)}>
                        {(playerData?.availableMetrics ?? []).map((metric) => (
                          <option key={metric.key} value={metric.key}>
                            {metric.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <SearchMultiSelect
                    label="Jugadores a comparar"
                    options={playerOptionsForSelect.filter((player) => player.value !== selectedPlayerKey)}
                    values={playerCompareKeys}
                    onChange={setPlayerCompareKeys}
                    placeholder="Busca jugadores para comparar"
                    suggestionLimit={5}
                    showSuggestionsOnlyWhenQuery={true}
                  />
                </div>

                {playerComparisonLabels.length > 1 ? (
                  <>
                    <div className="chart-caption-row">
                      <div>
                        <h3 className="chart-title">Comparativa de jugadores</h3>
                        <p className="chart-copy">{compareMetricLabel} en la misma ventana de partidos para varios jugadores.</p>
                      </div>
                      <span className="chart-note">Comparacion alineada por jornada</span>
                    </div>
                    <MultiMetricChart rows={playerComparisonChartRows} metrics={playerComparisonLabels} />
                    <DataTable
                      title="Resumen comparado"
                      subtitle={`Media reciente y delta de ${compareMetricLabel}.`}
                      columns={["JUGADOR", "MEDIA_RECIENTE", "MEDIA_FILTRO", "DELTA", "PARTIDOS"]}
                      rows={playerComparisonSummaryRows}
                      isLoading={playerCompareQuery.isLoading}
                      isUpdating={playerCompareQuery.isFetching && !playerCompareQuery.isLoading}
                      idField="JUGADOR"
                      defaultSortColumn="MEDIA_RECIENTE"
                      searchPlaceholder="Buscar jugador"
                      storageKey="trends-player-compare"
                      lockedLeadingColumns={["JUGADOR"]}
                    />
                  </>
                ) : (
                  <p className="empty-state">Anade al menos otro jugador para ver la comparativa.</p>
                )}
              </section>
            ) : null}

            {activeTab === "teams" ? (
              <section className="panel panel-soft">
                <div className="comparison-panel">
                  <div className="comparison-panel-header">
                    <div>
                      <h3>Comparar equipos</h3>
                      <p className="panel-copy">El equipo principal siempre se incluye.</p>
                    </div>
                    <label>
                      Metrica comparada
                      <select value={teamCompareMetric} onChange={(event) => setTeamCompareMetric(event.target.value)}>
                        {(teamData?.availableMetrics ?? []).map((metric) => (
                          <option key={metric.key} value={metric.key}>
                            {metric.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <SearchMultiSelect
                    label="Equipos a comparar"
                    options={teamOptionsForSelect.filter((team) => team.value !== selectedTeam)}
                    values={teamCompareKeys}
                    onChange={setTeamCompareKeys}
                    placeholder="Busca equipos para comparar"
                    suggestionLimit={5}
                    showSuggestionsOnlyWhenQuery={true}
                    emptySelectionText="Sin equipos anadidos."
                  />
                </div>

                {teamComparisonLabels.length > 1 ? (
                  <>
                    <div className="chart-caption-row">
                      <div>
                        <h3 className="chart-title">Comparativa de equipos</h3>
                        <p className="chart-copy">{teamCompareMetricLabel} en la misma ventana de partidos para varios equipos.</p>
                      </div>
                      <span className="chart-note">Comparacion alineada por jornada</span>
                    </div>
                    <MultiMetricChart rows={teamComparisonChartRows} metrics={teamComparisonLabels} />
                    <DataTable
                      title="Resumen comparado"
                      subtitle={`Media reciente y delta de ${teamCompareMetricLabel}.`}
                      columns={["EQUIPO", "MEDIA_RECIENTE", "MEDIA_FILTRO", "DELTA", "PARTIDOS"]}
                      rows={teamComparisonSummaryRows}
                      isLoading={teamCompareQuery.isLoading}
                      isUpdating={teamCompareQuery.isFetching && !teamCompareQuery.isLoading}
                      idField="EQUIPO"
                      defaultSortColumn="MEDIA_RECIENTE"
                      searchPlaceholder="Buscar equipo"
                      storageKey="trends-team-compare"
                      lockedLeadingColumns={["EQUIPO"]}
                    />
                  </>
                ) : (
                  <p className="empty-state">Anade al menos otro equipo para ver la comparativa.</p>
                )}
              </section>
            ) : null}

            <DataTable
              title="Ultimos partidos"
              subtitle="Detalle de los partidos recientes dentro del filtro."
              columns={Object.keys(trendData.recentGames[0] ?? {})}
              rows={trendData.recentGames}
              isLoading={activeTab === "players" ? playerQuery.isLoading : teamQuery.isLoading}
              isUpdating={(activeTab === "players" ? playerQuery.isFetching : teamQuery.isFetching) && !(activeTab === "players" ? playerQuery.isLoading : teamQuery.isLoading)}
              idField="PARTIDO"
              defaultSortColumn="JORNADA"
              searchPlaceholder="Buscar rival, fase o resultado"
              storageKey={activeTab === "players" ? "trends-player-games" : "trends-team-games"}
              lockedLeadingColumns={["PARTIDO"]}
            />
          </>
        ) : (
          <p className="empty-state">Selecciona un jugador o un equipo para cargar la tendencia.</p>
        )}
      </section>
    </div>
  );
}
