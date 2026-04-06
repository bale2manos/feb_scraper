import { useEffect, useState } from "react";

import { emptyScopeMeta, getGmPlayers, getMeta, normalizeScopeWithMeta } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { ScopeFilters } from "../components/ScopeFilters";
import { useLocalStorageState } from "../hooks";
import type { GmResponse, ScopeMeta, ScopeState } from "../types";
import { downloadCsv, formatNumber } from "../utils";

const INITIAL_SCOPE: ScopeState = { season: "", league: "", phases: [], jornadas: [] };

export function GmPage() {
  const [scope, setScope] = useLocalStorageState<ScopeState>("react-gm-scope", INITIAL_SCOPE);
  const [mode, setMode] = useLocalStorageState<string>("react-gm-mode", "Totales");
  const [meta, setMeta] = useState<ScopeMeta>(emptyScopeMeta());
  const [data, setData] = useState<GmResponse | null>(null);
  const [selectedPlayerKey, setSelectedPlayerKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    setLoading(true);
    setError(null);
    void getGmPlayers(scope, mode)
      .then((response) => {
        setData(response);
        const firstKey = String(response.rows[0]?.PLAYER_KEY ?? "");
        setSelectedPlayerKey((current) => (current && response.rows.some((row) => String(row.PLAYER_KEY ?? "") === current) ? current : firstKey || null));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|"), mode]);

  const selectedRow = data?.rows.find((row) => String(row.PLAYER_KEY ?? "") === selectedPlayerKey) ?? null;

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>GM</h2>
            <p className="panel-copy">Base de mercado con lectura rápida, ordenación por columnas y descarga CSV.</p>
          </div>
          <div className="toolbar">
            <label>
              Modo
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="Totales">Totales</option>
                <option value="Promedios">Promedios</option>
              </select>
            </label>
            <button type="button" onClick={() => downloadCsv("gm.csv", data?.rows ?? [])}>
              Descargar CSV
            </button>
          </div>
        </div>
        {loading ? <p className="empty-state">Cargando jugadores...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {data ? (
          <>
            <DataTable
              columns={data.columns}
              rows={data.rows}
              selectedKey={selectedPlayerKey}
              onSelect={(row) => setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""))}
            />
            {selectedRow ? (
              <div className="detail-card">
                <img className="player-image" src={String(selectedRow.IMAGEN ?? "")} alt={String(selectedRow.JUGADOR ?? "Jugador")} />
                <div className="detail-content">
                  <h3>{String(selectedRow.JUGADOR ?? "")}</h3>
                  <p className="panel-copy">{String(selectedRow.EQUIPO ?? "")}</p>
                  <div className="metric-grid">
                    <MetricCard label="Puntos" value={formatNumber(selectedRow.PUNTOS, 1)} />
                    <MetricCard label="Rebotes" value={formatNumber(selectedRow["REB TOTALES"], 1)} />
                    <MetricCard label="Asistencias" value={formatNumber(selectedRow.ASISTENCIAS, 1)} />
                    <MetricCard label="USG%" value={formatNumber(selectedRow["USG%"], 1)} />
                    <MetricCard label="PPP" value={formatNumber(selectedRow.PPP, 3)} />
                    <MetricCard label="TS%" value={formatNumber(selectedRow["TS%"], 1)} />
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
