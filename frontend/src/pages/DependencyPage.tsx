import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { getDependencyPlayers, getDependencySummary } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeQueryKey, useScopeMeta } from "../scope";
import type { ScopeState } from "../types";
import { downloadCsv, formatNumber, formatPercent } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

type DependencyOverviewRow = {
  EQUIPO: string;
  JUGADOR_CRITICO: string;
  DEPENDENCIA_SCORE: number;
  "%USO_TOP1": number;
  "%PUNTOS_TOP1": number;
  "%AST_TOP1": number;
  "%REB_TOP1": number;
  "%CLUTCH_TOP1": number;
  CONCENTRACION_TOP3: number;
  DEPENDENCIA_RIESGO: string;
  FOCO_PRINCIPAL: string;
};

const OVERVIEW_CRITERIA = [
  { key: "DEPENDENCIA_SCORE", label: "Score" },
  { key: "%USO_TOP1", label: "Uso" },
  { key: "%PUNTOS_TOP1", label: "Puntos" },
  { key: "%AST_TOP1", label: "AST" },
  { key: "%REB_TOP1", label: "REB" },
  { key: "%CLUTCH_TOP1", label: "Clutch" }
] as const;

const TEAM_CRITERIA = [
  { key: "DEPENDENCIA_SCORE", label: "Score" },
  { key: "%PLAYS_EQUIPO", label: "Uso" },
  { key: "%PUNTOS_EQUIPO", label: "Puntos" },
  { key: "%AST_EQUIPO", label: "AST" },
  { key: "%REB_EQUIPO", label: "REB" },
  { key: "%MIN_CLUTCH_EQUIPO", label: "Clutch" }
] as const;

function asNumber(value: unknown) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

export function DependencyPage({ scope, setScope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-dependency-team", "");
  const [selectedPlayerKey, setSelectedPlayerKey] = useLocalStorageState<string>("react-dependency-player", "");
  const [viewMode, setViewMode] = useLocalStorageState<"overview" | "team">("react-dependency-view-mode", "overview");
  const [overviewCriterion, setOverviewCriterion] = useLocalStorageState<string>("react-dependency-overview-criterion", "DEPENDENCIA_SCORE");
  const [teamCriterion, setTeamCriterion] = useLocalStorageState<string>("react-dependency-team-criterion", "DEPENDENCIA_SCORE");
  const [showPlayerDetail, setShowPlayerDetail] = useState(false);

  const playersQuery = useQuery({
    queryKey: ["dependency-players", ...buildScopeQueryKey(scope)],
    queryFn: ({ signal }) => getDependencyPlayers(scope, { signal }),
    enabled: Boolean(scope.season && scope.league),
    placeholderData: keepPreviousData
  });

  const data = playersQuery.data ?? null;
  const error = playersQuery.error instanceof Error ? playersQuery.error.message : null;

  useEffect(() => {
    const firstTeam = data?.teams[0]?.name ?? "";
    setSelectedTeam((current) => (data?.teams.some((team) => team.name === current) ? current : firstTeam));
  }, [data?.teams, setSelectedTeam]);

  useEffect(() => {
    setShowPlayerDetail(false);
  }, [selectedTeam]);

  const teamPlayerOptions = useMemo(() => {
    return (data?.players ?? [])
      .filter((player) => player.team === selectedTeam)
      .map((player) => ({ value: player.playerKey, label: player.label }));
  }, [data?.players, selectedTeam]);

  useEffect(() => {
    const firstPlayerKey = teamPlayerOptions[0]?.value ?? "";
    setSelectedPlayerKey((current) => (teamPlayerOptions.some((player) => player.value === current) ? current : firstPlayerKey));
  }, [setSelectedPlayerKey, teamPlayerOptions]);

  const summaryQuery = useQuery({
    queryKey: ["dependency-summary", ...buildScopeQueryKey(scope), selectedTeam, selectedPlayerKey],
    queryFn: ({ signal }) => getDependencySummary(scope, selectedTeam, selectedPlayerKey || undefined, { signal }),
    enabled: Boolean(scope.season && scope.league && selectedTeam),
    placeholderData: keepPreviousData
  });

  const summary = summaryQuery.data ?? null;

  useEffect(() => {
    if (!summary?.selectedPlayerKey) {
      return;
    }
    setSelectedPlayerKey((current) => (current === summary.selectedPlayerKey ? current : summary.selectedPlayerKey ?? ""));
  }, [setSelectedPlayerKey, summary?.selectedPlayerKey]);

  const detailImage =
    typeof summary?.detail?.image === "string" && /^https?:\/\//.test(summary.detail.image) ? summary.detail.image : null;

  const overviewRows = useMemo<DependencyOverviewRow[]>(() => {
    const rows = data?.rows ?? [];
    const grouped = new Map<string, Record<string, unknown>[]>();
    rows.forEach((row) => {
      const team = String(row.EQUIPO ?? "").trim();
      if (!team) {
        return;
      }
      const current = grouped.get(team) ?? [];
      current.push(row);
      grouped.set(team, current);
    });

    return [...grouped.entries()].map(([team, teamRows]) => {
      const sorted = [...teamRows].sort((left, right) => asNumber(right.DEPENDENCIA_SCORE) - asNumber(left.DEPENDENCIA_SCORE));
      const top = sorted[0] ?? {};
      const top3Usage = sorted.slice(0, 3).reduce((sum, row) => sum + asNumber(row["%PLAYS_EQUIPO"]), 0);
      return {
        EQUIPO: team,
        JUGADOR_CRITICO: String(top.JUGADOR ?? "-"),
        DEPENDENCIA_SCORE: asNumber(top.DEPENDENCIA_SCORE),
        "%USO_TOP1": asNumber(top["%PLAYS_EQUIPO"]),
        "%PUNTOS_TOP1": asNumber(top["%PUNTOS_EQUIPO"]),
        "%AST_TOP1": asNumber(top["%AST_EQUIPO"]),
        "%REB_TOP1": asNumber(top["%REB_EQUIPO"]),
        "%CLUTCH_TOP1": asNumber(top["%MIN_CLUTCH_EQUIPO"]),
        CONCENTRACION_TOP3: top3Usage,
        DEPENDENCIA_RIESGO: String(top.DEPENDENCIA_RIESGO ?? "-"),
        FOCO_PRINCIPAL: String(top.FOCO_PRINCIPAL ?? "-")
      };
    });
  }, [data?.rows]);

  const sortedOverviewRows = useMemo(() => {
    return [...overviewRows].sort((left, right) => asNumber(right[overviewCriterion as keyof DependencyOverviewRow]) - asNumber(left[overviewCriterion as keyof DependencyOverviewRow]));
  }, [overviewCriterion, overviewRows]);

  const topOverview = sortedOverviewRows[0] ?? null;
  const overviewCriterionLabel = OVERVIEW_CRITERIA.find((criterion) => criterion.key === overviewCriterion)?.label ?? "Score";
  const teamCriterionLabel = TEAM_CRITERIA.find((criterion) => criterion.key === teamCriterion)?.label ?? "Score";
  const teamHasClutch = Boolean(summary?.detail?.hasClutchData);

  const overviewTableColumns = useMemo(() => {
    const criterionColumn = overviewCriterion;
    const baseColumns = [
      "EQUIPO",
      "JUGADOR_CRITICO",
      criterionColumn,
      "DEPENDENCIA_SCORE",
      "%USO_TOP1",
      "%PUNTOS_TOP1",
      "%AST_TOP1",
      "%REB_TOP1",
      "%CLUTCH_TOP1",
      "CONCENTRACION_TOP3",
      "DEPENDENCIA_RIESGO",
      "FOCO_PRINCIPAL"
    ];
    return [...new Set(baseColumns)];
  }, [overviewCriterion]);

  const teamTableColumns = useMemo(() => {
    const columns = [
      "JUGADOR",
      teamCriterion,
      "PJ",
      "MINUTOS JUGADOS",
      "%PLAYS_EQUIPO",
      "%PUNTOS_EQUIPO",
      "%AST_EQUIPO",
      "%REB_EQUIPO",
      "DEPENDENCIA_SCORE",
      "DEPENDENCIA_RIESGO",
      "FOCO_PRINCIPAL"
    ];
    return [...new Set(teamHasClutch ? [...columns, "%MIN_CLUTCH_EQUIPO"] : columns)];
  }, [teamCriterion, teamHasClutch]);

  const sortedTeamRows = useMemo(() => {
    const rows = [...(summary?.tableRows ?? [])];
    return rows.sort((left, right) => asNumber(right[teamCriterion]) - asNumber(left[teamCriterion]));
  }, [summary?.tableRows, teamCriterion]);

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Riesgo</span>
            <h2>Dependencia</h2>
            <p className="panel-copy">Vista general por equipos y detalle equipo a equipo.</p>
          </div>
          <div className="toolbar">
            {(playersQuery.isFetching || summaryQuery.isFetching) && !(playersQuery.isLoading || summaryQuery.isLoading) ? (
              <span className="status-badge">Actualizando</span>
            ) : null}
            <button type="button" className={viewMode === "overview" ? "tab-button is-active" : "tab-button"} onClick={() => setViewMode("overview")}>
              Vista general
            </button>
            <button type="button" className={viewMode === "team" ? "tab-button is-active" : "tab-button"} onClick={() => setViewMode("team")}>
              Equipo a equipo
            </button>
          </div>
        </div>

        {playersQuery.isLoading ? <p className="empty-state">Cargando dependencia...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {viewMode === "overview" ? (
          <>
            <div className="toolbar">
              <label>
                Criterio
                <select value={overviewCriterion} onChange={(event) => setOverviewCriterion(event.target.value)}>
                  {OVERVIEW_CRITERIA.map((criterion) => (
                    <option key={criterion.key} value={criterion.key}>
                      {criterion.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="metric-grid metric-grid-wide">
              <MetricCard label={`Equipo top por ${overviewCriterionLabel}`} value={topOverview?.EQUIPO ?? "-"} isLoading={playersQuery.isLoading} />
              <MetricCard label="Jugador critico top" value={topOverview?.JUGADOR_CRITICO ?? "-"} isLoading={playersQuery.isLoading} />
              <MetricCard label="Uso top1" value={formatPercent(topOverview?.["%USO_TOP1"] ?? 0)} isLoading={playersQuery.isLoading} />
              <MetricCard label="AST top1" value={formatPercent(topOverview?.["%AST_TOP1"] ?? 0)} isLoading={playersQuery.isLoading} />
              <MetricCard label="REB top1" value={formatPercent(topOverview?.["%REB_TOP1"] ?? 0)} isLoading={playersQuery.isLoading} />
            </div>

            <div className="insight-banner">
              <strong>Lectura general</strong>
              <span>Haz click en cualquier equipo para ir al detalle.</span>
            </div>

            <DataTable
              title="Dependencia por equipo"
              subtitle="Cada fila resume al jugador mas critico de ese equipo."
              columns={overviewTableColumns}
              rows={sortedOverviewRows}
              isLoading={playersQuery.isLoading}
              isUpdating={playersQuery.isFetching && !playersQuery.isLoading}
              idField="EQUIPO"
              defaultSortColumn={overviewCriterion}
              searchPlaceholder="Buscar equipo o jugador critico"
              onSelect={(row) => {
                setSelectedTeam(String(row.EQUIPO ?? ""));
                setViewMode("team");
              }}
              storageKey={`dependency-overview-${overviewCriterion}`}
              lockedLeadingColumns={["EQUIPO"]}
            />

            <div className="toolbar">
              <button type="button" onClick={() => downloadCsv("dependencia_general.csv", sortedOverviewRows as unknown as Record<string, unknown>[])} disabled={!sortedOverviewRows.length}>
                Descargar CSV general
              </button>
            </div>
          </>
        ) : summary ? (
          <>
            <div className="search-toolbar-grid">
              <SearchSelect
                label="Equipo"
                options={(data?.teams ?? []).map((team) => ({ value: team.name, label: team.name }))}
                value={selectedTeam}
                onChange={setSelectedTeam}
                placeholder="Busca un equipo"
              />
              <SearchSelect
                label="Jugador"
                options={teamPlayerOptions}
                value={selectedPlayerKey}
                onChange={(value) => {
                  setSelectedPlayerKey(value);
                  setShowPlayerDetail(true);
                }}
                placeholder="Busca un jugador"
                disabled={!teamPlayerOptions.length}
              />
              <div className="compact-control-card">
                <label>
                  Criterio
                  <select value={teamCriterion} onChange={(event) => setTeamCriterion(event.target.value)}>
                    {TEAM_CRITERIA.map((criterion) => (
                      <option key={criterion.key} value={criterion.key} disabled={criterion.key === "%MIN_CLUTCH_EQUIPO" && !teamHasClutch}>
                        {criterion.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <div className="toolbar">
              <button type="button" onClick={() => downloadCsv("dependencia.csv", summary.tableRows ?? [])} disabled={!summary.tableRows.length}>
                Descargar CSV
              </button>
            </div>

            <div className="metric-grid metric-grid-wide">
              <MetricCard label="Jugador critico" value={String(summary.metrics.criticalPlayer ?? "-")} isLoading={summaryQuery.isLoading} />
              <MetricCard label="Uso top1" value={formatPercent(summary.metrics.topUsage)} isLoading={summaryQuery.isLoading} />
              <MetricCard label="Anotacion top1" value={formatPercent(summary.metrics.topScoring)} isLoading={summaryQuery.isLoading} />
              <MetricCard label="Creacion top1" value={formatPercent(summary.metrics.topCreation)} isLoading={summaryQuery.isLoading} />
              <MetricCard label="Concentracion top3" value={formatPercent(summary.metrics.top3Usage)} isLoading={summaryQuery.isLoading} />
            </div>

            <div className="insight-banner">
              <strong>Riesgo estructural</strong>
              <span>{summary.structuralRisk}</span>
            </div>

            <div className="split-layout">
              <div className="split-main">
                <DataTable
                  key={`dependency-team-${teamCriterion}`}
                  title="Jerarquia de dependencia"
                  subtitle={`Orden inicial por ${teamCriterionLabel}. Puedes reordenar columnas.`}
                  columns={teamTableColumns}
                  rows={sortedTeamRows}
                  isLoading={summaryQuery.isLoading}
                  isUpdating={summaryQuery.isFetching && !summaryQuery.isLoading}
                  selectedKey={selectedPlayerKey}
                  onSelect={(row) => {
                    setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""));
                    setShowPlayerDetail(true);
                  }}
                  defaultSortColumn={teamCriterion}
                  storageKey={`dependency-team-${selectedTeam || "team"}-${teamCriterion}`}
                  stickyFirstColumn={true}
                  lockedLeadingColumns={["JUGADOR"]}
                />
              </div>

              {showPlayerDetail ? (
                <aside className="split-side">
                  <section className="panel detail-panel">
                    <div className="detail-panel-header">
                      <div>
                        <span className="eyebrow">Jugador fijado</span>
                        <h3>{summary.detail?.name ?? "Selecciona un jugador"}</h3>
                        <p className="panel-copy">
                          {summary.detail
                            ? `${summary.detail.team} | ${summary.detail.gamesPlayed} PJ | ${summary.detail.risk} | ${summary.detail.focus}`
                            : "Selecciona una fila para ver el detalle."}
                        </p>
                      </div>
                      <button type="button" className="ghost-button" onClick={() => setShowPlayerDetail(false)}>
                        Cerrar
                      </button>
                    </div>

                    {summary.detail ? (
                      <>
                        {detailImage ? (
                          <img className="player-image player-image-large" src={detailImage} alt={summary.detail.name} />
                        ) : (
                          <div className="player-placeholder">DEP</div>
                        )}
                        <div className="metric-grid">
                          <MetricCard label="% uso ofensivo" value={formatPercent(summary.detail.usageShare)} />
                          <MetricCard label="% anotacion" value={formatPercent(summary.detail.scoringShare)} />
                          <MetricCard label="% creacion" value={formatPercent(summary.detail.creationShare)} />
                          <MetricCard label="% rebote" value={formatPercent(summary.detail.reboundShare)} />
                          {summary.detail.hasClutchData ? <MetricCard label="% minutos clutch" value={formatPercent(summary.detail.clutchShare)} /> : null}
                          <MetricCard label="Score dependencia" value={formatNumber(summary.detail.dependencyScore, 1)} />
                        </div>
                        <div className="insight-stack">
                          <p className="panel-copy">{summary.detail.diagnosis}</p>
                          <p className="detail-note">{summary.note}</p>
                        </div>
                      </>
                    ) : (
                      <div className="detail-empty">
                        <p className="empty-state">Sin detalle disponible para este equipo.</p>
                      </div>
                    )}
                  </section>
                </aside>
              ) : null}
            </div>
          </>
        ) : (
          <p className="empty-state">Selecciona un equipo para cargar la vista.</p>
        )}
      </section>
    </div>
  );
}
