import { useEffect, useState } from "react";

import { emptyScopeMeta, getDependencyPlayers, getDependencySummary, getMeta, normalizeScopeWithMeta } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { ScopeFilters } from "../components/ScopeFilters";
import { useLocalStorageState } from "../hooks";
import type { DependencyResponse, DependencySummary, ScopeMeta, ScopeState } from "../types";
import { downloadCsv, formatNumber, formatPercent } from "../utils";

const INITIAL_SCOPE: ScopeState = { season: "", league: "", phases: [], jornadas: [] };

export function DependencyPage() {
  const [scope, setScope] = useLocalStorageState<ScopeState>("react-dependency-scope", INITIAL_SCOPE);
  const [meta, setMeta] = useState<ScopeMeta>(emptyScopeMeta());
  const [data, setData] = useState<DependencyResponse | null>(null);
  const [summary, setSummary] = useState<DependencySummary | null>(null);
  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-dependency-team", "");
  const [selectedPlayerKey, setSelectedPlayerKey] = useState<string | null>(null);

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
    if (!scope.season || !scope.league) {
      return;
    }
    void getDependencyPlayers(scope).then((response) => {
      setData(response);
      const firstTeam = response.teams[0]?.name ?? "";
      setSelectedTeam((current) => (response.teams.some((team) => team.name === current) ? current : firstTeam));
    });
  }, [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|"), setSelectedTeam]);

  useEffect(() => {
    if (!scope.season || !scope.league || !selectedTeam) {
      return;
    }
    void getDependencySummary(scope, selectedTeam, selectedPlayerKey).then((response) => {
      setSummary(response);
      if (response.selectedPlayerKey && response.selectedPlayerKey !== selectedPlayerKey) {
        setSelectedPlayerKey(response.selectedPlayerKey);
      }
    });
  }, [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|"), selectedTeam, selectedPlayerKey]);

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Riesgo de roster</span>
            <h2>Dependencia</h2>
            <p className="panel-copy">
              La idea se mantiene: detectar donde depende de verdad el equipo. La ejecucion cambia para que la lectura sea mas directa y mas util en una reunion deportiva.
            </p>
          </div>
          <div className="toolbar">
            <label>
              Equipo
              <select value={selectedTeam} onChange={(event) => setSelectedTeam(event.target.value)}>
                {(data?.teams ?? []).map((team) => (
                  <option key={team.name} value={team.name}>
                    {team.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={() => downloadCsv("dependencia.csv", summary?.tableRows ?? [])}>
              Descargar CSV
            </button>
          </div>
        </div>

        {summary ? (
          <>
            <div className="metric-grid metric-grid-wide">
              <MetricCard label="Jugador critico" value={String(summary.metrics.criticalPlayer ?? "-")} />
              <MetricCard label="Uso top1" value={formatPercent(summary.metrics.topUsage)} />
              <MetricCard label="Anotacion top1" value={formatPercent(summary.metrics.topScoring)} />
              <MetricCard label="Creacion top1" value={formatPercent(summary.metrics.topCreation)} />
              <MetricCard label="Concentracion top3" value={formatPercent(summary.metrics.top3Usage)} />
            </div>

            <div className="insight-banner">
              <strong>Riesgo estructural</strong>
              <span>{summary.structuralRisk}</span>
            </div>

            <div className="split-layout">
              <div className="split-main">
                <DataTable
                  title="Jerarquia de dependencia"
                  subtitle="Selecciona cualquier jugador para ver el diagnostico y las metricas de impacto a la derecha."
                  columns={[
                    "JUGADOR",
                    "PJ",
                    "MINUTOS JUGADOS",
                    "%PLAYS_EQUIPO",
                    "%PUNTOS_EQUIPO",
                    "%AST_EQUIPO",
                    "%REB_EQUIPO",
                    "DEPENDENCIA_SCORE",
                    "DEPENDENCIA_RIESGO",
                    "FOCO_PRINCIPAL"
                  ]}
                  rows={summary.tableRows}
                  selectedKey={selectedPlayerKey}
                  onSelect={(row) => setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""))}
                  defaultSortColumn="DEPENDENCIA_SCORE"
                />
              </div>

              <aside className="split-side">
                <section className="panel detail-panel">
                  <div className="detail-panel-header">
                    <span className="eyebrow">Jugador fijado</span>
                    <h3>{summary.detail?.name ?? "Selecciona un jugador"}</h3>
                    <p className="panel-copy">
                      {summary.detail
                        ? `${summary.detail.team} · ${summary.detail.gamesPlayed} PJ · ${summary.detail.risk} · ${summary.detail.focus}`
                        : "Haz click en una fila para ver mejor el riesgo individual."}
                    </p>
                  </div>

                  {summary.detail ? (
                    <>
                      {summary.detail.image ? (
                        <img className="player-image player-image-large" src={summary.detail.image} alt={summary.detail.name} />
                      ) : (
                        <div className="player-placeholder">DEP</div>
                      )}
                      <div className="metric-grid">
                        <MetricCard label="% uso ofensivo" value={formatPercent(summary.detail.usageShare)} />
                        <MetricCard label="% anotacion" value={formatPercent(summary.detail.scoringShare)} />
                        <MetricCard label="% creacion" value={formatPercent(summary.detail.creationShare)} />
                        <MetricCard label="% rebote" value={formatPercent(summary.detail.reboundShare)} />
                        {summary.detail.hasClutchData ? (
                          <MetricCard label="% minutos clutch" value={formatPercent(summary.detail.clutchShare)} />
                        ) : null}
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
            </div>
          </>
        ) : (
          <p className="empty-state">Selecciona un equipo para cargar la vista.</p>
        )}
      </section>
    </div>
  );
}
