import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { getMarketCompare, getMarketPool, getMarketSuggestions } from "../api";
import { MarketCompareBlock } from "../components/MarketCompareBlock";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PlayerDetailActions } from "../components/PlayerDetailActions";
import { SearchMultiSelect } from "../components/SearchMultiSelect";
import { SearchSelect } from "../components/SearchSelect";
import { useDebouncedValue, useLocalStorageState } from "../hooks";
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
import type { MarketSuggestionCandidate, ScopeState } from "../types";
import { formatNumber } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

const DEFAULT_SHORTLIST_LIMIT = 6;

function formatBaselineMetric(value: unknown, digits = 1, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return `${formatNumber(numeric, digits)}${suffix}`;
}

export function SimilarityPage({ scope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>(() => readMarketSelectedLeagues(scope.season, scope.league));
  const [targetPlayerKey, setTargetPlayerKey] = useLocalStorageState<string>("react-similarity-target-player", "");
  const [minGames, setMinGames] = useLocalStorageState<number>("react-similarity-min-games", 5);
  const [minMinutes, setMinMinutes] = useLocalStorageState<number>("react-similarity-min-minutes", 10);
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [selectedDetailKey, setSelectedDetailKey] = useState<string | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [shortlistMessage, setShortlistMessage] = useState("");
  const leaguesSignature = selectedLeagues.join("|");
  const debouncedTargetPlayerKey = useDebouncedValue(targetPlayerKey, 120);

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
    if (!scope.season) {
      return;
    }
    const intent = consumeMarketIntent(scope.season);
    if (!intent) {
      return;
    }
    const nextLeagues = [...new Set([intent.league, ...selectedLeagues])];
    setSelectedLeagues(nextLeagues);
    if (intent.action === "compare") {
      const nextShortlist = addPlayerToMarketShortlist(scope.season, nextLeagues, intent.playerKey);
      setShortlist(nextShortlist);
    } else if (!intent.action) {
      const nextShortlist = addPlayerToMarketShortlist(scope.season, nextLeagues, intent.playerKey);
      setShortlist(nextShortlist);
      setTargetPlayerKey(intent.playerKey);
    } else {
      setTargetPlayerKey(intent.playerKey);
    }
    setSelectedDetailKey(intent.playerKey);
    setShowDetail(true);
  }, [scope.season, selectedLeagues, setTargetPlayerKey, targetPlayerKey]);

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

  const poolQuery = useQuery({
    queryKey: ["market-pool", scope.season, leaguesSignature, minGames, minMinutes],
    queryFn: ({ signal }) =>
      getMarketPool(
        {
          season: scope.season,
          leagues: selectedLeagues,
          minGames,
          minMinutes,
          query: "",
        },
        { signal }
      ),
    enabled: Boolean(scope.season && selectedLeagues.length),
    placeholderData: keepPreviousData,
  });

  const poolData = poolQuery.data ?? null;
  const poolRows = poolData?.rows ?? [];
  const availableLeagues = poolData?.availableLeagues ?? meta.leagues;
  const playerOptions = poolRows.map((player) => ({
    value: String(player.PLAYER_KEY),
    label: `${String(player.JUGADOR)} | ${String(player.EQUIPO)} | ${String(player.LIGA)}`,
  }));

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

  useEffect(() => {
    if (!playerOptions.length) {
      if (targetPlayerKey) {
        setTargetPlayerKey("");
      }
      return;
    }
    if (playerOptions.some((option) => option.value === targetPlayerKey)) {
      return;
    }
    setTargetPlayerKey(playerOptions[0]?.value ?? "");
  }, [playerOptions, setTargetPlayerKey, targetPlayerKey]);

  const suggestionsQuery = useQuery({
    queryKey: ["market-suggestions", scope.season, leaguesSignature, debouncedTargetPlayerKey],
    queryFn: ({ signal }) =>
      getMarketSuggestions(
        {
          season: scope.season,
          leagues: selectedLeagues,
          anchorPlayerKey: debouncedTargetPlayerKey,
          limit: 10,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && selectedLeagues.length && debouncedTargetPlayerKey),
    placeholderData: keepPreviousData,
  });

  const compareQuery = useQuery({
    queryKey: ["market-compare", scope.season, leaguesSignature, shortlist.join("|")],
    queryFn: ({ signal }) =>
      getMarketCompare(
        {
          season: scope.season,
          leagues: selectedLeagues,
          playerKeys: shortlist,
        },
        { signal }
      ),
    enabled: Boolean(scope.season && selectedLeagues.length && shortlist.length >= 2 && shortlist.length <= DEFAULT_SHORTLIST_LIMIT),
    placeholderData: keepPreviousData,
  });

  const target = suggestionsQuery.data?.anchor ?? null;
  const candidates = suggestionsQuery.data?.candidates ?? [];
  const targetBaselineCards = target
    ? [
        { label: "PJ", value: String(target.gamesPlayed) },
        { label: "Minutos", value: formatBaselineMetric(target.minutes, 1) },
        { label: "Puntos", value: formatBaselineMetric(target.points, 1) },
        { label: "Reb", value: formatBaselineMetric(target.rebounds, 1) },
        { label: "Ast", value: formatBaselineMetric(target.assists, 1) },
        { label: "Perdidas", value: formatBaselineMetric(target.turnovers, 1) },
        { label: "USG%", value: formatBaselineMetric(target.usg, 1, "%") },
        { label: "eFG%", value: formatBaselineMetric(target.efg, 1, "%") },
        { label: "AST/TO", value: formatBaselineMetric(target.astTo, 2) },
      ]
    : [];

  const candidateRows = useMemo(
    () =>
      candidates.map((candidate) => ({
        PLAYER_KEY: candidate.playerKey,
        JUGADOR: candidate.name,
        EQUIPO: candidate.team,
        LIGA: candidate.league,
        PJ: candidate.gamesPlayed,
        MINUTOS: candidate.minutes,
        PUNTOS: candidate.points,
        REBOTES: candidate.rebounds,
        ASISTENCIAS: candidate.assists,
        "USG%": candidate.usg,
        SCORE: candidate.similarityScore,
      })),
    [candidates]
  );

  const poolLookup = useMemo(() => {
    const map = new Map<string, (typeof poolRows)[number]>();
    poolRows.forEach((row) => map.set(String(row.PLAYER_KEY), row));
    return map;
  }, [poolRows]);
  const candidateLookup = useMemo(() => new Map(candidates.map((candidate) => [candidate.playerKey, candidate])), [candidates]);
  const compareLookup = useMemo(() => new Map((compareQuery.data?.players ?? []).map((player) => [player.playerKey, player])), [compareQuery.data?.players]);

  const shortlistCards = shortlist.map((playerKey) => {
    const poolRow = poolLookup.get(playerKey);
    const comparePlayer = compareLookup.get(playerKey);
    const candidate = candidateLookup.get(playerKey);
    return {
      playerKey,
      name: poolRow?.JUGADOR ?? comparePlayer?.name ?? candidate?.name ?? "Jugador",
      team: poolRow?.EQUIPO ?? comparePlayer?.team ?? candidate?.team ?? "-",
      league: poolRow?.LIGA ?? comparePlayer?.league ?? candidate?.league ?? "",
      focus: poolRow?.FOCO_PRINCIPAL ?? comparePlayer?.focus ?? candidate?.focus ?? "",
    };
  });

  const selectedCandidate = selectedDetailKey ? candidateLookup.get(selectedDetailKey) ?? null : null;
  const selectedPoolRow = selectedDetailKey ? poolLookup.get(selectedDetailKey) ?? null : null;
  const selectedImage =
    typeof selectedCandidate?.image === "string" && /^https?:\/\//.test(selectedCandidate.image)
      ? selectedCandidate.image
      : typeof selectedPoolRow?.IMAGEN === "string" && /^https?:\/\//.test(String(selectedPoolRow.IMAGEN))
        ? String(selectedPoolRow.IMAGEN)
        : null;
  const topCandidate = candidates[0] ?? null;
  const error = poolQuery.error instanceof Error ? poolQuery.error.message : suggestionsQuery.error instanceof Error ? suggestionsQuery.error.message : null;

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

  return (
    <div className="page-stack">
      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Decisión</span>
            <h2>Similares</h2>
            <p className="panel-copy">Busca reemplazo, guarda una shortlist y compara 2 a 6 jugadores en la misma vista.</p>
          </div>
          <div className="toolbar">
            {(poolQuery.isFetching || suggestionsQuery.isFetching || compareQuery.isFetching) && !(poolQuery.isLoading || suggestionsQuery.isLoading) ? (
              <span className="status-badge">Actualizando</span>
            ) : null}
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
            <SearchSelect
              label="Jugador objetivo"
              options={playerOptions}
              value={targetPlayerKey}
              onChange={setTargetPlayerKey}
              placeholder="Busca un jugador"
              disabled={!playerOptions.length}
              suggestionLimit={5}
            />
            <div className="compact-control-card">
              <label>
                Partidos mínimos
                <input type="number" min={0} max={100} value={minGames} onChange={(event) => setMinGames(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Minutos medios mínimos
                <input type="number" min={0} max={60} step={1} value={minMinutes} onChange={(event) => setMinMinutes(Math.max(0, Number(event.target.value || 0)))} />
              </label>
            </div>
          </div>
        </section>

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Jugador objetivo" value={target?.label ?? "-"} isLoading={suggestionsQuery.isLoading} />
          <MetricCard label="Reemplazos sugeridos" value={String(candidates.length)} isLoading={suggestionsQuery.isLoading} />
          <MetricCard label="Mejor score" value={topCandidate ? formatNumber(topCandidate.similarityScore, 1) : "-"} isLoading={suggestionsQuery.isLoading} />
          <MetricCard label="Shortlist" value={`${shortlist.length}/${DEFAULT_SHORTLIST_LIMIT}`} />
          <MetricCard label="Ligas activas" value={String(selectedLeagues.length)} />
        </div>

        {targetBaselineCards.length ? (
          <section className="detail-note-block">
            <strong>Baseline del objetivo</strong>
            <div className="metric-grid metric-grid-wide">
              {targetBaselineCards.map((metric) => (
                <MetricCard key={metric.label} label={metric.label} value={metric.value} />
              ))}
            </div>
          </section>
        ) : null}

        {shortlistMessage ? <p className="detail-note">{shortlistMessage}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        <div className="market-layout">
          <div className="market-main">
            <DataTable
              title="Reemplazos sugeridos"
              subtitle="Ranking de candidatos dentro de las ligas activas. Si no hay objetivo, el comparador manual sigue disponible."
              columns={["JUGADOR", "EQUIPO", "LIGA", "PJ", "MINUTOS", "PUNTOS", "REBOTES", "ASISTENCIAS", "USG%", "SCORE"]}
              rows={candidateRows}
              isLoading={suggestionsQuery.isLoading}
              isUpdating={suggestionsQuery.isFetching && !suggestionsQuery.isLoading}
              selectedKey={selectedDetailKey}
              onSelect={(row) => {
                setSelectedDetailKey(String(row.PLAYER_KEY ?? ""));
                setShowDetail(true);
              }}
              defaultSortColumn="SCORE"
              storageKey="similarity-unified-candidates-v2"
              lockedLeadingColumns={["JUGADOR"]}
            />
          </div>

          <aside className="market-side page-stack">
            <section className="panel detail-panel">
              <div className="detail-panel-header">
                <div>
                  <span className="eyebrow">Shortlist</span>
                  <h3>{shortlist.length ? `${shortlist.length} jugadores` : "Shortlist vacía"}</h3>
                  <p className="panel-copy">La comparación profunda funciona aunque no tengas jugador objetivo.</p>
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
                          className={targetPlayerKey === player.playerKey ? "tab-button is-active" : "tab-button"}
                          onClick={() => setTargetPlayerKey(player.playerKey)}
                        >
                          {targetPlayerKey === player.playerKey ? "Objetivo" : "Usar como objetivo"}
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
                <p className="empty-state">Añade jugadores desde GM, Dependencia, Potencial o desde los propios reemplazos sugeridos.</p>
              )}
            </section>

            {showDetail ? (
              <section className="panel detail-panel">
                <div className="detail-panel-header">
                  <div>
                    <span className="eyebrow">Detalle</span>
                    <h3>{selectedCandidate?.label ?? selectedPoolRow?.JUGADOR ?? "Selecciona un jugador"}</h3>
                    <p className="panel-copy">
                      {selectedCandidate
                        ? `${selectedCandidate.focus || "Perfil mixto"} | Score ${formatNumber(selectedCandidate.similarityScore, 1)}`
                        : selectedPoolRow
                          ? `${selectedPoolRow.EQUIPO} | ${selectedPoolRow.LIGA}`
                          : "Selecciona una fila o una tarjeta de shortlist."}
                    </p>
                  </div>
                  <button type="button" className="ghost-button" onClick={() => setShowDetail(false)}>
                    Cerrar
                  </button>
                </div>

                {selectedCandidate || selectedPoolRow ? (
                  <>
                    {selectedImage ? (
                      <img className="player-image player-image-large" src={selectedImage} alt={selectedCandidate?.name ?? selectedPoolRow?.JUGADOR ?? "Jugador"} />
                    ) : (
                      <div className="player-placeholder">SIM</div>
                    )}
                    <div className="metric-grid">
                      <MetricCard label="Minutos" value={formatNumber(selectedCandidate?.minutes ?? selectedPoolRow?.MIN ?? 0, 1)} />
                      <MetricCard label="Puntos" value={formatNumber(selectedCandidate?.points ?? selectedPoolRow?.PTS ?? 0, 1)} />
                      <MetricCard label="Rebotes" value={formatNumber(selectedCandidate?.rebounds ?? selectedPoolRow?.REB ?? 0, 1)} />
                      <MetricCard label="Asistencias" value={formatNumber(selectedCandidate?.assists ?? selectedPoolRow?.AST ?? 0, 1)} />
                      <MetricCard label="USG%" value={formatNumber(selectedCandidate?.usg ?? selectedPoolRow?.["USG%"] ?? 0, 1)} />
                      <MetricCard label="Score" value={selectedCandidate ? formatNumber(selectedCandidate.similarityScore, 1) : "-"} />
                    </div>

                    {selectedCandidate ? (
                      <>
                        <div className="detail-note-block">
                          <strong>Por qué encaja</strong>
                          <ul className="detail-list">
                            {selectedCandidate.reasons.map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                        <div className="detail-note-block">
                          <strong>Diferencias principales</strong>
                          <ul className="detail-list">
                            {selectedCandidate.differences.map((difference) => (
                              <li key={difference}>{difference}</li>
                            ))}
                          </ul>
                        </div>
                      </>
                    ) : null}

                    <div className="toolbar">
                      <button
                        type="button"
                        className="ghost-button strong-ghost-button"
                        onClick={() => addToShortlist(selectedCandidate?.playerKey ?? String(selectedPoolRow?.PLAYER_KEY ?? ""), selectedCandidate?.league ?? String(selectedPoolRow?.LIGA ?? ""))}
                        disabled={shortlist.includes(selectedCandidate?.playerKey ?? String(selectedPoolRow?.PLAYER_KEY ?? ""))}
                      >
                        {shortlist.includes(selectedCandidate?.playerKey ?? String(selectedPoolRow?.PLAYER_KEY ?? "")) ? "Ya en shortlist" : "Añadir al shortlist"}
                      </button>
                    </div>
                    <PlayerDetailActions
                      playerKey={selectedCandidate?.playerKey ?? String(selectedPoolRow?.PLAYER_KEY ?? "")}
                      team={selectedCandidate?.team ?? String(selectedPoolRow?.EQUIPO ?? "")}
                      season={scope.season}
                      league={selectedCandidate?.league ?? String(selectedPoolRow?.LIGA ?? scope.league ?? "")}
                      currentPage="similares"
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
              <h3>Comparación profunda</h3>
              <p className="panel-copy">Volumen, rol, eficiencia y contexto para la shortlist actual.</p>
            </div>
          </div>

          {shortlist.length < 2 ? (
            <p className="empty-state">Necesitas al menos 2 jugadores en shortlist para activar el comparador.</p>
          ) : compareQuery.error instanceof Error ? (
            <p className="error-text">{compareQuery.error.message}</p>
          ) : compareQuery.data ? (
            <div className="page-stack">
              {compareQuery.data.blocks.map((block) => (
                <MarketCompareBlock key={block.key} block={block} players={compareQuery.data?.players ?? []} />
              ))}
            </div>
          ) : (
            <p className="empty-state">Cargando comparador...</p>
          )}
        </section>
      </section>
    </div>
  );
}
