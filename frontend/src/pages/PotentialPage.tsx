import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMarketOpportunity, getMarketPool } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PlayerDetailActions } from "../components/PlayerDetailActions";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { useDebouncedValue, useLocalStorageState } from "../hooks";
import {
  addPlayerToMarketShortlist,
  queueMarketIntent,
  readMarketSelectedLeagues,
  readMarketShortlist,
  removePlayerFromMarketShortlist,
  writeMarketSelectedLeagues,
  writeMarketShortlist,
} from "../market";
import { useScopeMeta } from "../scope";
import type { MarketOpportunityRow, MarketPoolRow, ScopeState } from "../types";
import { formatNumber, getBirthYear, getPlayerAge } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

const OPPORTUNITY_COLUMNS = [
  "JUGADOR",
  "EQUIPO",
  "LIGA",
  "AÑO NACIMIENTO",
  "PJ",
  "MIN",
  "USG%",
  "TS%",
  "eFG%",
  "PPP",
  "AST/TO",
  "OpportunityScore",
] as const;

export function PotentialPage({ scope }: ScopePageProps) {
  const navigate = useNavigate();
  const { meta } = useScopeMeta();
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>(() => readMarketSelectedLeagues(scope.season, scope.league));
  const [query, setQuery] = useLocalStorageState<string>("react-potential-query", "");
  const [minGames, setMinGames] = useLocalStorageState<number>("react-potential-min-games", 5);
  const [maxMinutes, setMaxMinutes] = useLocalStorageState<number>("react-potential-max-minutes", 22);
  const [maxUsg, setMaxUsg] = useLocalStorageState<number>("react-potential-max-usg", 24);
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [selectedDetailKey, setSelectedDetailKey] = useState<string | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [shortlistMessage, setShortlistMessage] = useState("");
  const leaguesSignature = selectedLeagues.join("|");
  const debouncedQuery = useDebouncedValue(query, 220);

  useEffect(() => {
    setSelectedLeagues(readMarketSelectedLeagues(scope.season, scope.league));
  }, [scope.season, scope.league]);

  useEffect(() => {
    if (!scope.season) {
      return;
    }
    writeMarketSelectedLeagues(scope.season, selectedLeagues);
  }, [scope.season, selectedLeagues]);

  useEffect(() => {
    if (!scope.season || !selectedLeagues.length) {
      setShortlist([]);
      return;
    }
    setShortlist(readMarketShortlist(scope.season, selectedLeagues));
  }, [scope.season, selectedLeagues]);

  useEffect(() => {
    if (!scope.season || !selectedLeagues.length) {
      return;
    }
    writeMarketShortlist(scope.season, selectedLeagues, shortlist);
  }, [scope.season, selectedLeagues, shortlist]);

  useEffect(() => {
    if (!shortlistMessage) {
      return;
    }
    const timeoutId = window.setTimeout(() => setShortlistMessage(""), 2200);
    return () => window.clearTimeout(timeoutId);
  }, [shortlistMessage]);

  const opportunityQuery = useQuery({
    queryKey: ["market-opportunity", scope.season, leaguesSignature, minGames, maxMinutes, maxUsg, debouncedQuery],
    queryFn: ({ signal }) =>
      getMarketOpportunity(
        {
          season: scope.season,
          leagues: selectedLeagues,
          minGames,
          maxMinutes,
          maxUsg,
          query: debouncedQuery,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && selectedLeagues.length),
    placeholderData: keepPreviousData,
  });

  const shortlistLookupQuery = useQuery({
    queryKey: ["market-pool", scope.season, leaguesSignature, 0, 0, ""],
    queryFn: ({ signal }) =>
      getMarketPool(
        {
          season: scope.season,
          leagues: selectedLeagues,
          minGames: 0,
          minMinutes: 0,
          query: "",
        },
        { signal }
      ),
    enabled: Boolean(scope.season && selectedLeagues.length),
    placeholderData: keepPreviousData,
  });

  const opportunityData = opportunityQuery.data ?? null;
  const opportunityRows = opportunityData?.rows ?? [];
  const availableLeagues = opportunityData?.availableLeagues ?? meta.leagues;
  const shortlistLookupRows = shortlistLookupQuery.data?.rows ?? [];

  useEffect(() => {
    if (!availableLeagues.length) {
      return;
    }
    if (!selectedLeagues.length) {
      setSelectedLeagues(scope.league && availableLeagues.includes(scope.league) ? [scope.league] : availableLeagues.slice(0, 1));
      return;
    }
    const validLeagues = selectedLeagues.filter((league) => availableLeagues.includes(league));
    if (validLeagues.length === selectedLeagues.length) {
      return;
    }
    setSelectedLeagues(validLeagues.length ? validLeagues : scope.league && availableLeagues.includes(scope.league) ? [scope.league] : availableLeagues.slice(0, 1));
  }, [availableLeagues, scope.league, selectedLeagues]);

  const shortlistLookup = useMemo(() => {
    const map = new Map<string, MarketPoolRow>();
    shortlistLookupRows.forEach((row) => map.set(String(row.PLAYER_KEY), row));
    return map;
  }, [shortlistLookupRows]);

  const opportunityLookup = useMemo(() => {
    const map = new Map<string, MarketOpportunityRow>();
    opportunityRows.forEach((row) => map.set(String(row.PLAYER_KEY), row));
    return map;
  }, [opportunityRows]);

  const selectedOpportunityRow = selectedDetailKey ? opportunityLookup.get(selectedDetailKey) ?? null : null;
  const selectedLookupRow = selectedDetailKey ? shortlistLookup.get(selectedDetailKey) ?? null : null;
  const selectedImage =
    typeof selectedOpportunityRow?.IMAGEN === "string" && /^https?:\/\//.test(selectedOpportunityRow.IMAGEN)
      ? selectedOpportunityRow.IMAGEN
      : typeof selectedLookupRow?.IMAGEN === "string" && /^https?:\/\//.test(String(selectedLookupRow.IMAGEN))
        ? String(selectedLookupRow.IMAGEN)
        : null;
  const selectedBirthYear = getBirthYear(selectedOpportunityRow?.["AÑO NACIMIENTO"] ?? selectedLookupRow?.["AÑO NACIMIENTO"]);
  const selectedAge = getPlayerAge(selectedOpportunityRow?.["AÑO NACIMIENTO"] ?? selectedLookupRow?.["AÑO NACIMIENTO"]);

  const shortlistCards = shortlist.map((playerKey) => {
    const poolRow = shortlistLookup.get(playerKey);
    const opportunityRow = opportunityLookup.get(playerKey);
    return {
      playerKey,
      name: opportunityRow?.JUGADOR ?? poolRow?.JUGADOR ?? "Jugador",
      team: opportunityRow?.EQUIPO ?? poolRow?.EQUIPO ?? "-",
      league: opportunityRow?.LIGA ?? poolRow?.LIGA ?? "",
      focus: opportunityRow?.FOCO_PRINCIPAL ?? poolRow?.FOCO_PRINCIPAL ?? "",
      score: opportunityRow?.OpportunityScore ?? null,
    };
  });

  const error = opportunityQuery.error instanceof Error ? opportunityQuery.error.message : null;

  function addToShortlist(playerKey: string, league: string) {
    if (!scope.season) {
      return;
    }
    const nextLeagues = selectedLeagues.includes(league) ? selectedLeagues : [...selectedLeagues, league];
    if (!selectedLeagues.includes(league)) {
      setSelectedLeagues(nextLeagues);
    }
    const nextShortlist = addPlayerToMarketShortlist(scope.season, nextLeagues, playerKey);
    setShortlist(nextShortlist);
    setShortlistMessage(nextShortlist.includes(playerKey) ? "Añadido al shortlist" : "Shortlist llena (máximo 6)");
  }

  function removeFromShortlist(playerKey: string) {
    if (!scope.season) {
      return;
    }
    const next = removePlayerFromMarketShortlist(scope.season, selectedLeagues, playerKey);
    setShortlist(next);
  }

  function useAsTarget(playerKey: string, league: string) {
    if (!scope.season || !league) {
      return;
    }
    queueMarketIntent({
      season: scope.season,
      league,
      playerKey,
      action: "target",
      source: "potencial",
    });
    navigate("/similares");
  }

  return (
    <div className="page-stack">
      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Upside</span>
            <h2>Potencial</h2>
            <p className="panel-copy">Detecta perfiles poco usados o con pocos minutos que ya muestran eficiencia y margen.</p>
          </div>
          <div className="toolbar">
            {opportunityQuery.isFetching && !opportunityQuery.isLoading ? <span className="status-badge">Actualizando</span> : null}
          </div>
        </div>

        <section className="control-panel">
          <div className="search-toolbar-grid">
            <SearchMultiSelect
              label="Ligas"
              options={availableLeagues.map((league) => ({ value: league, label: league }))}
              values={selectedLeagues}
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
                Partidos mínimos
                <input type="number" min={0} max={100} value={minGames} onChange={(event) => setMinGames(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Máx minutos
                <input type="number" min={0} max={60} step={1} value={maxMinutes} onChange={(event) => setMaxMinutes(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Máx USG%
                <input type="number" min={0} max={60} step={1} value={maxUsg} onChange={(event) => setMaxUsg(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
          </div>
        </section>

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Candidatos" value={String(opportunityData?.summary.candidateCount ?? opportunityRows.length)} isLoading={opportunityQuery.isLoading} />
          <MetricCard label="Ligas activas" value={String(selectedLeagues.length)} />
          <MetricCard label="Top potencial" value={opportunityData?.summary.leaders.topOpportunity ?? "-"} isLoading={opportunityQuery.isLoading} />
          <MetricCard label="Mejor eficiencia" value={opportunityData?.summary.leaders.bestEfficiency ?? "-"} isLoading={opportunityQuery.isLoading} />
          <MetricCard label="Shortlist" value={`${shortlist.length}/6`} />
        </div>

        {shortlistMessage ? <p className="detail-note">{shortlistMessage}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        <div className="market-layout">
          <div className="market-main">
            <DataTable
              title="Perfiles con potencial"
              subtitle="Jugadores con uso o minutos contenidos, pero con eficiencia suficiente para merecer una segunda mirada."
              columns={[...OPPORTUNITY_COLUMNS]}
              rows={opportunityRows}
              isLoading={opportunityQuery.isLoading}
              isUpdating={opportunityQuery.isFetching && !opportunityQuery.isLoading}
              selectedKey={selectedDetailKey}
              onSelect={(row) => {
                setSelectedDetailKey(String(row.PLAYER_KEY ?? ""));
                setShowDetail(true);
              }}
              defaultSortColumn="OpportunityScore"
              storageKey="potential-opportunity-v1"
              lockedLeadingColumns={["JUGADOR"]}
              defaultVisibleColumns={[...OPPORTUNITY_COLUMNS]}
            />
          </div>

          <aside className="market-side page-stack">
            <section className="panel detail-panel">
              <div className="detail-panel-header">
                <div>
                  <span className="eyebrow">Shortlist</span>
                  <h3>{shortlist.length ? `${shortlist.length} jugadores` : "Shortlist vacía"}</h3>
                  <p className="panel-copy">Compartida con Similares y ligada a la temporada y ligas activas.</p>
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
                        {player.score != null ? <span className="detail-note">Score potencial {formatNumber(player.score, 1)}</span> : null}
                        {player.focus ? <span className="detail-note">{player.focus}</span> : null}
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="tab-button"
                          onClick={() => useAsTarget(player.playerKey, player.league)}
                          disabled={!player.league}
                        >
                          Buscar reemplazo
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => {
                            setSelectedDetailKey(player.playerKey);
                            setShowDetail(true);
                          }}
                        >
                          Ver detalle
                        </button>
                        <button type="button" className="ghost-button" onClick={() => removeFromShortlist(player.playerKey)}>
                          Quitar
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="empty-state">Añade jugadores con potencial para compararlos luego en Similares.</p>
              )}
            </section>

            {showDetail ? (
              <section className="panel detail-panel">
                <div className="detail-panel-header">
                  <div>
                    <span className="eyebrow">Detalle</span>
                    <h3>{selectedOpportunityRow?.JUGADOR ?? selectedLookupRow?.JUGADOR ?? "Selecciona un jugador"}</h3>
                    <p className="panel-copy">
                      {selectedOpportunityRow
                        ? `${selectedOpportunityRow.EQUIPO} | ${selectedOpportunityRow.LIGA} | Score ${formatNumber(selectedOpportunityRow.OpportunityScore, 1)}`
                        : selectedLookupRow
                          ? `${selectedLookupRow.EQUIPO} | ${selectedLookupRow.LIGA}`
                          : "Selecciona una fila para ver el detalle."}
                    </p>
                  </div>
                  <button type="button" className="ghost-button" onClick={() => setShowDetail(false)}>
                    Cerrar
                  </button>
                </div>

                {selectedOpportunityRow || selectedLookupRow ? (
                  <>
                    {selectedImage ? (
                      <img
                        className="player-image player-image-large"
                        src={selectedImage}
                        alt={selectedOpportunityRow?.JUGADOR ?? selectedLookupRow?.JUGADOR ?? "Jugador"}
                      />
                    ) : (
                      <div className="player-placeholder">POT</div>
                    )}

                    <div className="metric-grid">
                      {selectedAge != null ? <MetricCard label="Edad" value={String(selectedAge)} /> : null}
                      {selectedBirthYear != null ? <MetricCard label="Nacimiento" value={String(selectedBirthYear)} /> : null}
                      <MetricCard label="MIN" value={formatNumber(selectedOpportunityRow?.MIN ?? selectedLookupRow?.MIN ?? 0, 1)} />
                      <MetricCard label="USG%" value={formatNumber(selectedOpportunityRow?.["USG%"] ?? selectedLookupRow?.["USG%"] ?? 0, 1)} />
                      <MetricCard label="TS%" value={formatNumber(selectedOpportunityRow?.["TS%"] ?? selectedLookupRow?.["TS%"] ?? 0, 1)} />
                      <MetricCard label="eFG%" value={formatNumber(selectedOpportunityRow?.["eFG%"] ?? selectedLookupRow?.["eFG%"] ?? 0, 1)} />
                      <MetricCard label="PPP" value={formatNumber(selectedOpportunityRow?.PPP ?? selectedLookupRow?.PPP ?? 0, 3)} />
                      <MetricCard label="AST/TO" value={formatNumber(selectedOpportunityRow?.["AST/TO"] ?? selectedLookupRow?.["AST/TO"] ?? 0, 2)} />
                    </div>

                    {selectedOpportunityRow ? (
                      <>
                        <div className="detail-note-block">
                          <strong>Fortalezas</strong>
                          <ul className="detail-list">
                            {selectedOpportunityRow.strengths.map((strength) => (
                              <li key={strength}>{strength}</li>
                            ))}
                          </ul>
                        </div>
                        <div className="detail-note-block">
                          <strong>Frenos</strong>
                          <ul className="detail-list">
                            {selectedOpportunityRow.blockers.map((blocker) => (
                              <li key={blocker}>{blocker}</li>
                            ))}
                          </ul>
                        </div>
                      </>
                    ) : (
                      <p className="detail-note">Este jugador está en tu shortlist, pero no entra con los filtros actuales de Potencial.</p>
                    )}

                    <div className="toolbar">
                      <button
                        type="button"
                        className="ghost-button strong-ghost-button"
                        onClick={() =>
                          addToShortlist(
                            String(selectedOpportunityRow?.PLAYER_KEY ?? selectedLookupRow?.PLAYER_KEY ?? ""),
                            String(selectedOpportunityRow?.LIGA ?? selectedLookupRow?.LIGA ?? "")
                          )
                        }
                        disabled={shortlist.includes(String(selectedOpportunityRow?.PLAYER_KEY ?? selectedLookupRow?.PLAYER_KEY ?? ""))}
                      >
                        {shortlist.includes(String(selectedOpportunityRow?.PLAYER_KEY ?? selectedLookupRow?.PLAYER_KEY ?? ""))
                          ? "Ya en shortlist"
                          : "Añadir al shortlist"}
                      </button>
                    </div>

                    <PlayerDetailActions
                      playerKey={selectedOpportunityRow?.PLAYER_KEY ?? selectedLookupRow?.PLAYER_KEY ?? ""}
                      team={selectedOpportunityRow?.EQUIPO ?? selectedLookupRow?.EQUIPO ?? ""}
                      season={scope.season}
                      league={selectedOpportunityRow?.LIGA ?? selectedLookupRow?.LIGA ?? scope.league ?? ""}
                      currentPage="potencial"
                    />
                  </>
                ) : (
                  <p className="empty-state">No hay detalle seleccionado.</p>
                )}
              </section>
            ) : null}
          </aside>
        </div>
      </section>
    </div>
  );
}
