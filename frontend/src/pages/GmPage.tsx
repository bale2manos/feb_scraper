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
        setSelectedPlayerKey((current) =>
          current && response.rows.some((row) => String(row.PLAYER_KEY ?? "") === current) ? current : firstKey || null
        );
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|"), mode]);

  const selectedRow = data?.rows.find((row) => String(row.PLAYER_KEY ?? "") === selectedPlayerKey) ?? null;
  const playersCount = data?.rows.length ?? 0;
  const teamsCount = new Set((data?.rows ?? []).map((row) => String(row.EQUIPO ?? ""))).size;
  const topPlayer = String(data?.rows[0]?.JUGADOR ?? "-");

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Mercado</span>
            <h2>Vista GM</h2>
            <p className="panel-copy">
              Misma idea de base de datos y scouting, pero con una disposicion mas clara para filtrar, comparar y leer el perfil seleccionado sin perder el contexto.
            </p>
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

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Jugadores en pantalla" value={String(playersCount)} />
          <MetricCard label="Equipos presentes" value={String(teamsCount)} />
          <MetricCard label="Modo actual" value={mode} />
          <MetricCard label="Primera referencia" value={topPlayer} hint="Jugador top segun el orden actual" />
        </div>

        {loading ? <p className="empty-state">Cargando jugadores...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {data ? (
          <div className="split-layout">
            <div className="split-main">
              <DataTable
                title="Mercado filtrado"
                subtitle="Tabla ordenable y con busqueda rapida para bajar friccion en el uso diario."
                columns={data.columns}
                rows={data.rows}
                selectedKey={selectedPlayerKey}
                onSelect={(row) => setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""))}
                defaultSortColumn="PUNTOS"
              />
            </div>

            <aside className="split-side">
              <section className="panel detail-panel">
                <div className="detail-panel-header">
                  <span className="eyebrow">Detalle</span>
                  <h3>{String(selectedRow?.JUGADOR ?? "Selecciona un jugador")}</h3>
                  <p className="panel-copy">
                    {selectedRow
                      ? `${String(selectedRow.EQUIPO ?? "")} · ${String(selectedRow.NACIONALIDAD ?? "Sin nacionalidad")} · ${mode}`
                      : "Pulsa una fila para fijar el perfil y leer sus metricas sin perder la tabla de vista."}
                  </p>
                </div>

                {selectedRow ? (
                  <>
                    {selectedRow.IMAGEN ? (
                      <img className="player-image player-image-large" src={String(selectedRow.IMAGEN)} alt={String(selectedRow.JUGADOR ?? "Jugador")} />
                    ) : (
                      <div className="player-placeholder">GM</div>
                    )}
                    <div className="metric-grid">
                      <MetricCard label="Puntos" value={formatNumber(selectedRow.PUNTOS, 1)} />
                      <MetricCard label="Rebotes" value={formatNumber(selectedRow["REB TOTALES"], 1)} />
                      <MetricCard label="Asistencias" value={formatNumber(selectedRow.ASISTENCIAS, 1)} />
                      <MetricCard label="Minutos" value={formatNumber(selectedRow["MINUTOS JUGADOS"], 1)} />
                      <MetricCard label="USG%" value={formatNumber(selectedRow["USG%"], 1)} />
                      <MetricCard label="PPP" value={formatNumber(selectedRow.PPP, 3)} />
                      <MetricCard label="TS%" value={formatNumber(selectedRow["TS%"], 1)} />
                      <MetricCard label="AST/TO" value={formatNumber(selectedRow["AST/TO"], 2)} />
                    </div>
                  </>
                ) : (
                  <div className="detail-empty">
                    <p className="empty-state">No hay detalle seleccionado todavia.</p>
                  </div>
                )}
              </section>
            </aside>
          </div>
        ) : null}
      </section>
    </div>
  );
}
