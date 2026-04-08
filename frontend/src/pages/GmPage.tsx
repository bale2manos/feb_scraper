import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { getGmPlayers } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PlayerDetailActions } from "../components/PlayerDetailActions";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeQueryKey, useScopeMeta } from "../scope";
import type { ScopeState } from "../types";
import { downloadCsv, formatNumber } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

type NumericFilter = {
  id: string;
  column: string;
  min: string;
  max: string;
};

const NON_FILTERABLE_COLUMNS = new Set(["PLAYER_KEY", "IMAGEN", "DORSAL"]);
const GM_DEFAULT_VISIBLE_COLUMNS = [
  "JUGADOR",
  "EQUIPO",
  "AÑO NACIMIENTO",
  "MINUTOS JUGADOS",
  "PUNTOS",
  "REB TOTALES",
  "ASISTENCIAS"
] as const;

function buildFilterId() {
  return `filter-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function GmPage({ scope, setScope }: ScopePageProps) {
  const [mode, setMode] = useLocalStorageState<string>("react-gm-mode-v2", "Promedios");
  const [selectedPlayerKey, setSelectedPlayerKey] = useState<string | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [filters, setFilters] = useLocalStorageState<NumericFilter[]>("react-gm-stat-filters", []);
  const { meta } = useScopeMeta();

  const gmQuery = useQuery({
    queryKey: ["gm", ...buildScopeQueryKey(scope), mode],
    queryFn: ({ signal }) => getGmPlayers(scope, mode, { signal }),
    enabled: Boolean(scope.season && scope.league),
    placeholderData: keepPreviousData
  });

  const data = gmQuery.data ?? null;
  const error = gmQuery.error instanceof Error ? gmQuery.error.message : null;

  const numericColumns = useMemo(() => {
    const sampleRows = data?.rows ?? [];
    const keys = new Set<string>();
    sampleRows.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
    return [...keys]
      .filter((key) => !NON_FILTERABLE_COLUMNS.has(key))
      .filter((key) =>
        sampleRows.some((row) => {
          const numeric = Number(row[key]);
          return Number.isFinite(numeric);
        })
      )
      .sort((left, right) => left.localeCompare(right, "es"));
  }, [data?.rows]);

  useEffect(() => {
    setFilters((current) =>
      current
        .filter((filter) => numericColumns.includes(filter.column))
        .map((filter) => ({ ...filter, column: filter.column || numericColumns[0] || "" }))
    );
  }, [numericColumns, setFilters]);

  const normalizedFilters = useMemo(
    () => filters.filter((filter) => filter.column && numericColumns.includes(filter.column)),
    [filters, numericColumns]
  );

  const filteredRows = useMemo(() => {
    const rows = data?.rows ?? [];
    if (!normalizedFilters.length) {
      return rows;
    }
    return rows.filter((row) =>
      normalizedFilters.every((filter) => {
        const numeric = Number(row[filter.column]);
        if (!Number.isFinite(numeric)) {
          return false;
        }
        const minValue = filter.min.trim() === "" ? null : Number(filter.min);
        const maxValue = filter.max.trim() === "" ? null : Number(filter.max);
        if (minValue !== null && Number.isFinite(minValue) && numeric < minValue) {
          return false;
        }
        if (maxValue !== null && Number.isFinite(maxValue) && numeric > maxValue) {
          return false;
        }
        return true;
      })
    );
  }, [data?.rows, normalizedFilters]);

  useEffect(() => {
    if (!selectedPlayerKey) {
      return;
    }
    if (!filteredRows.some((row) => String(row.PLAYER_KEY ?? "") === selectedPlayerKey)) {
      setSelectedPlayerKey(null);
      setShowDetail(false);
    }
  }, [filteredRows, selectedPlayerKey]);

  const selectedRow = useMemo(
    () => filteredRows.find((row) => String(row.PLAYER_KEY ?? "") === selectedPlayerKey) ?? null,
    [filteredRows, selectedPlayerKey]
  );

  const selectedImage =
    typeof selectedRow?.IMAGEN === "string" && /^https?:\/\//.test(String(selectedRow.IMAGEN)) ? String(selectedRow.IMAGEN) : null;
  const playersCount = filteredRows.length;
  const totalPlayersCount = data?.rows.length ?? 0;
  const teamsCount = new Set(filteredRows.map((row) => String(row.EQUIPO ?? ""))).size;
  const topPlayer = String(filteredRows[0]?.JUGADOR ?? "-");

  function addFilter() {
    if (!numericColumns.length) {
      return;
    }
    setFilters((current) => [...current, { id: buildFilterId(), column: numericColumns[0], min: "", max: "" }]);
  }

  function updateFilter(filterId: string, patch: Partial<NumericFilter>) {
    setFilters((current) => current.map((filter) => (filter.id === filterId ? { ...filter, ...patch } : filter)));
  }

  function removeFilter(filterId: string) {
    setFilters((current) => current.filter((filter) => filter.id !== filterId));
  }

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Mercado</span>
            <h2>GM</h2>
            <p className="panel-copy">Buscador global de jugadores con filtros por estadistica.</p>
          </div>
          <div className="toolbar">
            {gmQuery.isFetching && !gmQuery.isLoading ? <span className="status-badge">Actualizando</span> : null}
            <label>
              Modo
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="Promedios">Promedios</option>
                <option value="Totales">Totales</option>
              </select>
            </label>
            <button type="button" onClick={() => downloadCsv("gm.csv", filteredRows)}>
              Descargar CSV
            </button>
          </div>
        </div>

        <section className="control-panel">
          <div className="toolbar">
            <div>
              <strong>Filtros estadisticos</strong>
              <p className="panel-copy">Anade rangos por columna para recortar el mercado.</p>
            </div>
            <div className="toolbar">
              <button type="button" onClick={addFilter} disabled={!numericColumns.length}>
                Anadir filtro
              </button>
              {filters.length ? (
                <button type="button" className="ghost-button" onClick={() => setFilters([])}>
                  Limpiar filtros
                </button>
              ) : null}
            </div>
          </div>

          {filters.length ? (
            <div className="filter-builder">
              {filters.map((filter) => (
                <div key={filter.id} className="filter-row">
                  <SearchSelect
                    label="Columna"
                    options={numericColumns.map((column) => ({ value: column, label: column }))}
                    value={filter.column}
                    onChange={(value) => updateFilter(filter.id, { column: value })}
                    placeholder="Busca una columna"
                    suggestionLimit={null}
                  />
                  <label>
                    Min
                    <input type="number" value={filter.min} onChange={(event) => updateFilter(filter.id, { min: event.target.value })} />
                  </label>
                  <label>
                    Max
                    <input type="number" value={filter.max} onChange={(event) => updateFilter(filter.id, { max: event.target.value })} />
                  </label>
                  <button type="button" className="ghost-button" onClick={() => removeFilter(filter.id)}>
                    Quitar
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="detail-note">Sin filtros activos.</p>
          )}
        </section>

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Jugadores visibles" value={String(playersCount)} isLoading={gmQuery.isLoading} hint={`De ${totalPlayersCount}`} />
          <MetricCard label="Equipos" value={String(teamsCount)} isLoading={gmQuery.isLoading} />
          <MetricCard label="Modo" value={mode} />
          <MetricCard label="Primero en tabla" value={topPlayer} isLoading={gmQuery.isLoading} />
          <MetricCard label="Filtros activos" value={String(normalizedFilters.length)} />
        </div>

        {gmQuery.isLoading ? <p className="empty-state">Cargando jugadores...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {data ? (
          <div className={showDetail ? "split-layout" : "page-stack"}>
            <div className="split-main">
              <DataTable
                title="Mercado filtrado"
                subtitle="Tabla ordenable, con busqueda, columnas reordenables y columnas ocultables."
                columns={data.columns}
                rows={filteredRows}
                isLoading={gmQuery.isLoading}
                isUpdating={gmQuery.isFetching && !gmQuery.isLoading}
                selectedKey={selectedPlayerKey}
                onSelect={(row) => {
                  setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""));
                  setShowDetail(true);
                }}
                defaultSortColumn="PUNTOS"
                storageKey={`gm-${mode.toLowerCase()}-v5`}
                lockedLeadingColumns={["JUGADOR"]}
                defaultVisibleColumns={[...GM_DEFAULT_VISIBLE_COLUMNS]}
              />
            </div>

            {showDetail ? (
              <aside className="split-side">
                <section className="panel detail-panel">
                  <div className="detail-panel-header">
                    <div>
                      <span className="eyebrow">Detalle</span>
                      <h3>{String(selectedRow?.JUGADOR ?? "Selecciona un jugador")}</h3>
                      <p className="panel-copy">
                        {selectedRow
                          ? `${String(selectedRow.EQUIPO ?? "")} | ${String(selectedRow.NACIONALIDAD ?? "Sin nacionalidad")} | ${mode}`
                          : "Selecciona una fila para ver el detalle."}
                      </p>
                    </div>
                    <button type="button" className="ghost-button" onClick={() => setShowDetail(false)}>
                      Cerrar
                    </button>
                  </div>

                  {selectedRow ? (
                    <>
                      {selectedImage ? (
                        <img className="player-image player-image-large" src={selectedImage} alt={String(selectedRow.JUGADOR ?? "Jugador")} />
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
                      <div className="toolbar">
                        <PlayerDetailActions
                          playerKey={selectedPlayerKey}
                          team={String(selectedRow.EQUIPO ?? "")}
                          currentPage="other"
                        />
                      </div>
                    </>
                  ) : (
                    <div className="detail-empty">
                      <p className="empty-state">No hay detalle seleccionado.</p>
                    </div>
                  )}
                </section>
              </aside>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
