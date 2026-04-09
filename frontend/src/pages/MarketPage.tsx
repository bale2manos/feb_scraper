import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useMemo, useState } from "react";

import { getMarketCompare, getMarketPool, getMarketSuggestions } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PlayerDetailActions } from "../components/PlayerDetailActions";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { SearchSelect } from "../components/SearchSelect";
import { useDebouncedValue } from "../hooks";
import {
  addPlayerToMarketShortlist,
  consumeMarketIntent,
  readMarketSelectedLeagues,
  readMarketShortlist,
  removePlayerFromMarketShortlist,
  writeMarketSelectedLeagues,
  writeMarketShortlist,
} from "../market";
import { useScopeMeta } from "../scope";
import type { MarketCompareMetric, MarketComparePlayer, MarketPoolRow, ScopeState } from "../types";
import { formatNumber } from "../utils";

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

const POOL_COLUMNS = ["JUGADOR", "EQUIPO", "LIGA", "MIN", "PTS", "REB", "AST", "USG%", "TS%", "DEPENDENCIA_SCORE"] as const;
const DEFAULT_SHORTLIST_LIMIT = 6;

function buildFilterId() {
  return `market-filter-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function asNumber(value: unknown) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatDelta(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return "";
  }
  if (Math.abs(value) < 0.01) {
    return "Top del shortlist";
  }
  const prefix = value > 0 ? "+" : "";
  return `vs mejor ${prefix}${formatNumber(value, 1)}`;
}

function findMetricRow(metric: MarketCompareMetric, playerKey: string) {
  return metric.rows.find((row) => row.playerKey === playerKey) ?? null;
}

function CompareBlock({ block, players }: { block: { key: string; title: string; metrics: MarketCompareMetric[] }; players: MarketComparePlayer[] }) {
  return (
    <section className="panel panel-soft market-compare-block">
      <div className="page-header market-compare-header">
        <div>
          <span className="eyebrow">Comparador</span>
          <h3>{block.title}</h3>
        </div>
      </div>

      <div
        className="market-compare-grid"
        style={{ gridTemplateColumns: `minmax(140px, 1.1fr) repeat(${players.length}, minmax(150px, 1fr))` }}
      >
        <div className="market-compare-grid-head">Metrica</div>
        {players.map((player) => (
          <div key={`${block.key}-${player.playerKey}-head`} className="market-compare-grid-head">
            <strong>{player.name}</strong>
            <span>{player.team}</span>
          </div>
        ))}

        {block.metrics.map((metric) => (
          <Fragment key={`${block.key}-${metric.key}`}>
            <div key={`${block.key}-${metric.key}-label`} className="market-compare-grid-label">
              <strong>{metric.label}</strong>
            </div>
            {players.map((player) => {
              const metricRow = findMetricRow(metric, player.playerKey);
              return (
                <div key={`${block.key}-${metric.key}-${player.playerKey}`} className="market-compare-grid-cell">
                  <strong>{metricRow?.formatted ?? "-"}</strong>
                  {metricRow?.percentile != null ? <span>Pctl {formatNumber(metricRow.percentile, 0)}</span> : null}
                  {metricRow?.deltaToBest != null ? <span>{formatDelta(metricRow.deltaToBest)}</span> : null}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </section>
  );
}

export function MarketPage({ scope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>(() => readMarketSelectedLeagues(scope.season, scope.league));
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [selectedPlayerKey, setSelectedPlayerKey] = useState<string | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [anchorPlayerKey, setAnchorPlayerKey] = useState("");
  const [query, setQuery] = useState("");
  const [minGames, setMinGames] = useState(5);
  const [minMinutes, setMinMinutes] = useState(10);
  const [filters, setFilters] = useState<NumericFilter[]>([]);
  const [shortlistMessage, setShortlistMessage] = useState("");
  const debouncedQuery = useDebouncedValue(query, 220);

  const effectiveLeagues = selectedLeagues;
  const leaguesSignature = effectiveLeagues.join("|");

  useEffect(() => {
    setSelectedLeagues(readMarketSelectedLeagues(scope.season, scope.league));
  }, [scope.season, scope.league]);

  useEffect(() => {
    if (!scope.season) {
      return;
    }
    writeMarketSelectedLeagues(scope.season, effectiveLeagues);
  }, [effectiveLeagues, scope.season]);

  useEffect(() => {
    if (!scope.season) {
      return;
    }
    const intent = consumeMarketIntent(scope.season);
    if (!intent) {
      return;
    }
    const nextLeagues = [...new Set([intent.league, ...effectiveLeagues])];
    setSelectedLeagues(nextLeagues);
    const nextShortlist = addPlayerToMarketShortlist(scope.season, nextLeagues, intent.playerKey);
    setShortlist(nextShortlist);
    setAnchorPlayerKey(intent.playerKey);
    setSelectedPlayerKey(intent.playerKey);
    setShowDetail(true);
  }, [effectiveLeagues, scope.season]);

  useEffect(() => {
    if (!scope.season || !effectiveLeagues.length) {
      setShortlist([]);
      return;
    }
    setShortlist(readMarketShortlist(scope.season, effectiveLeagues));
  }, [effectiveLeagues, scope.season]);

  useEffect(() => {
    if (!scope.season || !effectiveLeagues.length) {
      return;
    }
    writeMarketShortlist(scope.season, effectiveLeagues, shortlist);
  }, [effectiveLeagues, scope.season, shortlist]);

  useEffect(() => {
    if (!anchorPlayerKey || shortlist.includes(anchorPlayerKey)) {
      return;
    }
    setAnchorPlayerKey(shortlist[0] ?? "");
  }, [anchorPlayerKey, shortlist]);

  useEffect(() => {
    if (!shortlistMessage) {
      return;
    }
    const timeoutId = window.setTimeout(() => setShortlistMessage(""), 2200);
    return () => window.clearTimeout(timeoutId);
  }, [shortlistMessage]);

  const marketPoolQuery = useQuery({
    queryKey: ["market-pool", scope.season, leaguesSignature, minGames, minMinutes, debouncedQuery],
    queryFn: ({ signal }) =>
      getMarketPool(
        {
          season: scope.season,
          leagues: effectiveLeagues,
          minGames,
          minMinutes,
          query: debouncedQuery,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && effectiveLeagues.length),
    placeholderData: keepPreviousData,
  });

  const poolData = marketPoolQuery.data ?? null;
  const poolError = marketPoolQuery.error instanceof Error ? marketPoolQuery.error.message : null;
  const availableLeagues = poolData?.availableLeagues ?? meta.leagues;

  useEffect(() => {
    if (!availableLeagues.length) {
      return;
    }
    if (!selectedLeagues.length) {
      setSelectedLeagues(scope.league && availableLeagues.includes(scope.league) ? [scope.league] : availableLeagues.slice(0, 1));
      return;
    }
    const validLeagues = effectiveLeagues.filter((league) => availableLeagues.includes(league));
    if (validLeagues.length === effectiveLeagues.length) {
      return;
    }
    setSelectedLeagues(validLeagues.length ? validLeagues : scope.league && availableLeagues.includes(scope.league) ? [scope.league] : availableLeagues.slice(0, 1));
  }, [availableLeagues, effectiveLeagues, scope.league, selectedLeagues.length]);

  const numericColumns = useMemo(() => {
    const sampleRows = poolData?.rows ?? [];
    const keys = new Set<string>();
    sampleRows.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
    return [...keys]
      .filter((key) => !["PLAYER_KEY", "IMAGEN", "JUGADOR", "EQUIPO", "LIGA", "FOCO_PRINCIPAL"].includes(key))
      .filter((key) =>
        sampleRows.some((row) => {
          const numeric = Number((row as Record<string, unknown>)[key]);
          return Number.isFinite(numeric);
        })
      )
      .sort((left, right) => left.localeCompare(right, "es"));
  }, [poolData?.rows]);

  useEffect(() => {
    setFilters((current) =>
      current
        .filter((filter) => numericColumns.includes(filter.column))
        .map((filter) => ({ ...filter, column: filter.column || numericColumns[0] || "" }))
    );
  }, [numericColumns]);

  const filteredRows = useMemo(() => {
    const rows = poolData?.rows ?? [];
    if (!filters.length) {
      return rows;
    }
    return rows.filter((row) =>
      filters.every((filter) => {
        const numeric = Number((row as Record<string, unknown>)[filter.column]);
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
  }, [filters, poolData?.rows]);

  const rowLookup = useMemo(() => {
    const entries = new Map<string, MarketPoolRow>();
    filteredRows.forEach((row) => entries.set(String(row.PLAYER_KEY), row));
    (poolData?.rows ?? []).forEach((row) => {
      if (!entries.has(String(row.PLAYER_KEY))) {
        entries.set(String(row.PLAYER_KEY), row);
      }
    });
    return entries;
  }, [filteredRows, poolData?.rows]);

  const compareQuery = useQuery({
    queryKey: ["market-compare", scope.season, leaguesSignature, shortlist.join("|")],
    queryFn: ({ signal }) =>
      getMarketCompare(
        {
          season: scope.season,
          leagues: effectiveLeagues,
          playerKeys: shortlist,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && effectiveLeagues.length && shortlist.length >= 2 && shortlist.length <= DEFAULT_SHORTLIST_LIMIT),
    placeholderData: keepPreviousData,
  });

  const suggestionsQuery = useQuery({
    queryKey: ["market-suggestions", scope.season, leaguesSignature, anchorPlayerKey],
    queryFn: ({ signal }) =>
      getMarketSuggestions(
        {
          season: scope.season,
          leagues: effectiveLeagues,
          anchorPlayerKey,
          limit: 6,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && effectiveLeagues.length && anchorPlayerKey),
    placeholderData: keepPreviousData,
  });

  const comparePlayers = compareQuery.data?.players ?? [];
  const compareLookup = useMemo(() => new Map(comparePlayers.map((player) => [player.playerKey, player])), [comparePlayers]);
  const suggestionsLookup = useMemo(() => {
    const entries = new Map<string, { playerKey: string } & Record<string, unknown>>();
    (suggestionsQuery.data?.candidates ?? []).forEach((candidate) => entries.set(candidate.playerKey, candidate));
    if (suggestionsQuery.data?.anchor) {
      entries.set(suggestionsQuery.data.anchor.playerKey, suggestionsQuery.data.anchor);
    }
    return entries;
  }, [suggestionsQuery.data]);

  const shortlistCards = shortlist
    .map((playerKey) => ({
      playerKey,
      row: rowLookup.get(playerKey),
      compare: compareLookup.get(playerKey),
      suggestion: suggestionsLookup.get(playerKey),
    }))
    .map((entry) => ({
      playerKey: entry.playerKey,
      name: entry.row ? String(entry.row.JUGADOR ?? "Jugador") : String(entry.compare?.name ?? entry.suggestion?.name ?? "Jugador"),
      team: entry.row ? String(entry.row.EQUIPO ?? "-") : String(entry.compare?.team ?? entry.suggestion?.team ?? "-"),
      league: entry.row ? String(entry.row.LIGA ?? "") : String(entry.compare?.league ?? entry.suggestion?.league ?? ""),
      focus: entry.row ? String(entry.row.FOCO_PRINCIPAL ?? "") : String(entry.compare?.focus ?? entry.suggestion?.focus ?? ""),
    }));

  const selectedRow = useMemo(
    () => filteredRows.find((row) => String(row.PLAYER_KEY ?? "") === selectedPlayerKey) ?? (selectedPlayerKey ? rowLookup.get(selectedPlayerKey) ?? null : null),
    [filteredRows, rowLookup, selectedPlayerKey]
  );
  const selectedImage =
    typeof selectedRow?.IMAGEN === "string" && /^https?:\/\//.test(String(selectedRow.IMAGEN)) ? String(selectedRow.IMAGEN) : null;

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

  function addToShortlist(playerKey: string, league: string) {
    if (!scope.season) {
      return;
    }
    const nextLeagues = effectiveLeagues.includes(league) ? effectiveLeagues : [...effectiveLeagues, league];
    if (!effectiveLeagues.includes(league)) {
      setSelectedLeagues(nextLeagues);
    }
    const nextShortlist = addPlayerToMarketShortlist(scope.season, nextLeagues, playerKey);
    setShortlist(nextShortlist);
    setAnchorPlayerKey((current) => current || playerKey);
    setShortlistMessage(
      nextShortlist.includes(playerKey) ? "Jugador anadido al shortlist" : "Shortlist llena (maximo 6 jugadores)"
    );
  }

  function removeFromShortlist(playerKey: string) {
    if (!scope.season) {
      return;
    }
    const nextShortlist = removePlayerFromMarketShortlist(scope.season, effectiveLeagues, playerKey);
    setShortlist(nextShortlist);
  }

  return (
    <div className="page-stack">
      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Decision engine</span>
            <h2>Mercado</h2>
            <p className="panel-copy">Pool abierto de mercado, shortlist persistente y comparador profundo de 2 a 6 jugadores.</p>
          </div>
          <div className="toolbar">
            {marketPoolQuery.isFetching && !marketPoolQuery.isLoading ? <span className="status-badge">Actualizando</span> : null}
            <span className="scope-badge">Temporada compartida: {scope.season || "-"}</span>
          </div>
        </div>

        <section className="control-panel">
          <div className="search-toolbar-grid">
            <SearchMultiSelect
              label="Ligas"
              options={availableLeagues.map((league) => ({ value: league, label: league }))}
              values={effectiveLeagues}
              onChange={setSelectedLeagues}
              placeholder="Busca una liga"
              suggestionLimit={null}
              emptySelectionText="Sin ligas"
            />
            <div className="compact-control-card">
              <label>
                Buscar jugador
                <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre o equipo" />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Min PJ
                <input type="number" min={0} max={100} value={minGames} onChange={(event) => setMinGames(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Min MIN
                <input type="number" min={0} max={60} step={1} value={minMinutes} onChange={(event) => setMinMinutes(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
          </div>

          <div className="toolbar">
            <div>
              <strong>Filtros numericos</strong>
              <p className="panel-copy">Refina el pool sin tocar la shortlist ni el comparador.</p>
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
            <p className="detail-note">Sin filtros numericos activos.</p>
          )}
        </section>

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Jugadores visibles" value={String(filteredRows.length)} isLoading={marketPoolQuery.isLoading} />
          <MetricCard label="Ligas activas" value={String(poolData?.summary.leagueCount ?? effectiveLeagues.length)} isLoading={marketPoolQuery.isLoading} />
          <MetricCard label="Top anotador" value={poolData?.summary.leaders.topScorer ?? "-"} isLoading={marketPoolQuery.isLoading} />
          <MetricCard label="Top eficiencia" value={poolData?.summary.leaders.topEfficiency ?? "-"} isLoading={marketPoolQuery.isLoading} />
          <MetricCard label="Shortlist" value={`${shortlist.length}/${DEFAULT_SHORTLIST_LIMIT}`} />
        </div>

        {shortlistMessage ? <p className="detail-note">{shortlistMessage}</p> : null}
        {poolError ? <p className="error-text">{poolError}</p> : null}

        <div className="market-layout">
          <div className="market-main">
            <DataTable
              title="Pool de mercado"
              subtitle="Tabla compacta para construir shortlist y abrir detalle."
              columns={[...POOL_COLUMNS]}
              rows={filteredRows}
              isLoading={marketPoolQuery.isLoading}
              isUpdating={marketPoolQuery.isFetching && !marketPoolQuery.isLoading}
              selectedKey={selectedPlayerKey}
              onSelect={(row) => {
                setSelectedPlayerKey(String(row.PLAYER_KEY ?? ""));
                setShowDetail(true);
              }}
              defaultSortColumn="PTS"
              storageKey="market-pool-v1"
              lockedLeadingColumns={["JUGADOR"]}
              defaultVisibleColumns={[...POOL_COLUMNS]}
            />
          </div>

          <aside className="market-side page-stack">
            <section className="panel detail-panel">
              <div className="detail-panel-header">
                <div>
                  <span className="eyebrow">Shortlist</span>
                  <h3>{shortlist.length ? `${shortlist.length} jugadores` : "Shortlist vacia"}</h3>
                  <p className="panel-copy">Persistida por temporada y ligas seleccionadas.</p>
                </div>
              </div>

              {shortlistCards.length ? (
                <div className="market-shortlist-grid">
                  {shortlistCards.map((player) => (
                    <article key={player.playerKey} className="market-shortlist-card">
                      <div>
                        <strong>{player.name}</strong>
                        <p className="panel-copy">
                          {player.team} {player.league ? `| ${player.league}` : ""}
                        </p>
                        {player.focus ? <span className="detail-note">{player.focus}</span> : null}
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className={anchorPlayerKey === player.playerKey ? "tab-button is-active" : "tab-button"}
                          onClick={() => setAnchorPlayerKey(player.playerKey)}
                        >
                          {anchorPlayerKey === player.playerKey ? "Ancla" : "Fijar ancla"}
                        </button>
                        <button type="button" className="ghost-button" onClick={() => removeFromShortlist(player.playerKey)}>
                          Quitar
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => {
                            setSelectedPlayerKey(player.playerKey);
                            setShowDetail(true);
                          }}
                        >
                          Ver detalle
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="empty-state">Anade jugadores desde el pool o desde otras pantallas.</p>
              )}
            </section>

            {showDetail ? (
              <section className="panel detail-panel">
                <div className="detail-panel-header">
                  <div>
                    <span className="eyebrow">Detalle</span>
                    <h3>{selectedRow?.JUGADOR ?? "Selecciona un jugador"}</h3>
                    <p className="panel-copy">
                      {selectedRow
                        ? `${String(selectedRow.EQUIPO ?? "")} | ${String(selectedRow.LIGA ?? "")} | ${formatNumber(selectedRow.MIN, 1)} MIN`
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
                      <div className="player-placeholder">MKT</div>
                    )}
                    <div className="metric-grid">
                      <MetricCard label="PTS" value={formatNumber(selectedRow.PTS, 1)} />
                      <MetricCard label="REB" value={formatNumber(selectedRow.REB, 1)} />
                      <MetricCard label="AST" value={formatNumber(selectedRow.AST, 1)} />
                      <MetricCard label="USG%" value={formatNumber(selectedRow["USG%"], 1)} />
                      <MetricCard label="TS%" value={formatNumber(selectedRow["TS%"], 1)} />
                      <MetricCard label="Dependencia" value={formatNumber(selectedRow.DEPENDENCIA_SCORE, 1)} />
                    </div>
                    <div className="toolbar">
                      <button
                        type="button"
                        className="ghost-button strong-ghost-button"
                        onClick={() => addToShortlist(String(selectedRow.PLAYER_KEY), String(selectedRow.LIGA ?? ""))}
                        disabled={shortlist.includes(String(selectedRow.PLAYER_KEY))}
                      >
                        {shortlist.includes(String(selectedRow.PLAYER_KEY)) ? "Ya en shortlist" : "Anadir al shortlist"}
                      </button>
                      <button type="button" className="ghost-button" onClick={() => setAnchorPlayerKey(String(selectedRow.PLAYER_KEY))}>
                        Fijar ancla
                      </button>
                    </div>
                    <PlayerDetailActions
                      playerKey={String(selectedRow.PLAYER_KEY)}
                      team={String(selectedRow.EQUIPO ?? "")}
                      season={scope.season}
                      league={String(selectedRow.LIGA ?? scope.league ?? "")}
                      currentPage="mercado"
                    />
                  </>
                ) : (
                  <p className="empty-state">No hay detalle seleccionado.</p>
                )}
              </section>
            ) : null}
          </aside>
        </div>

        <section className="panel page-panel">
          <div className="page-header">
            <div>
              <span className="eyebrow">Comparador</span>
              <h3>Comparacion profunda</h3>
              <p className="panel-copy">Rendimiento, rol, eficiencia y contexto para 2 a 6 nombres.</p>
            </div>
          </div>

          {shortlist.length < 2 ? (
            <p className="empty-state">Necesitas al menos 2 jugadores en shortlist para activar el comparador.</p>
          ) : compareQuery.error instanceof Error ? (
            <p className="error-text">{compareQuery.error.message}</p>
          ) : compareQuery.data ? (
            <div className="page-stack">
              {compareQuery.data.blocks.map((block) => (
                <CompareBlock key={block.key} block={block} players={compareQuery.data?.players ?? []} />
              ))}
            </div>
          ) : (
            <p className="empty-state">Cargando comparador...</p>
          )}
        </section>

        <section className="panel page-panel">
          <div className="page-header">
            <div>
              <span className="eyebrow">Sugerencias</span>
              <h3>Encajes alrededor del ancla</h3>
              <p className="panel-copy">El motor de similaridad se aplica al pool actual de mercado.</p>
            </div>
          </div>

          {!anchorPlayerKey ? (
            <p className="empty-state">Fija un jugador ancla en la shortlist para activar sugerencias.</p>
          ) : suggestionsQuery.error instanceof Error ? (
            <p className="error-text">{suggestionsQuery.error.message}</p>
          ) : suggestionsQuery.data?.candidates.length ? (
            <div className="market-suggestion-grid">
              {suggestionsQuery.data.candidates.map((candidate) => (
                <article key={candidate.playerKey} className="panel panel-soft market-suggestion-card">
                  <div className="market-suggestion-header">
                    <div>
                      <strong>{candidate.name}</strong>
                      <p className="panel-copy">
                        {candidate.team} | {candidate.league}
                      </p>
                    </div>
                    <span className="status-badge">Score {formatNumber(candidate.similarityScore, 1)}</span>
                  </div>
                  <div className="metric-grid">
                    <MetricCard label="PTS" value={formatNumber(candidate.points, 1)} />
                    <MetricCard label="REB" value={formatNumber(candidate.rebounds, 1)} />
                    <MetricCard label="AST" value={formatNumber(candidate.assists, 1)} />
                    <MetricCard label="USG%" value={formatNumber(candidate.usg, 1)} />
                  </div>
                  <div className="detail-note-block">
                    <strong>Razones de encaje</strong>
                    <ul className="detail-list">
                      {candidate.reasons.slice(0, 3).map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="toolbar">
                    <button type="button" onClick={() => addToShortlist(candidate.playerKey, candidate.league)} disabled={shortlist.includes(candidate.playerKey)}>
                      {shortlist.includes(candidate.playerKey) ? "Ya en shortlist" : "Anadir a shortlist"}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => {
                        setSelectedPlayerKey(candidate.playerKey);
                        setShowDetail(true);
                      }}
                    >
                      Ver detalle
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : suggestionsQuery.isLoading ? (
            <p className="empty-state">Buscando sugerencias...</p>
          ) : (
            <p className="empty-state">No hay sugerencias utiles para el ancla actual.</p>
          )}
        </section>
      </section>
    </div>
  );
}
