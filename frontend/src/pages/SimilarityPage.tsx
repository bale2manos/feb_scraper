import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { getPlayerSimilarity } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeQueryKey, useScopeMeta } from "../scope";
import type { ScopeState } from "../types";
import { formatNumber } from "../utils";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

export function SimilarityPage({ scope, setScope }: ScopePageProps) {
  const { meta } = useScopeMeta();
  const [selectedPlayerKey, setSelectedPlayerKey] = useLocalStorageState<string>("react-similarity-target-player", "");
  const [minGames, setMinGames] = useLocalStorageState<number>("react-similarity-min-games", 5);
  const [minMinutes, setMinMinutes] = useLocalStorageState<number>("react-similarity-min-minutes", 10);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState<string | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  const playerOptions = meta.players.map((player) => ({ value: player.playerKey, label: player.label }));

  useEffect(() => {
    if (!meta.players.length) {
      return;
    }
    const fallbackPlayerKey = meta.players[0]?.playerKey ?? "";
    setSelectedPlayerKey((current) => (meta.players.some((player) => player.playerKey === current) ? current : fallbackPlayerKey));
  }, [meta.players, setSelectedPlayerKey]);

  const similarityQuery = useQuery({
    queryKey: ["similarity-player", ...buildScopeQueryKey(scope), selectedPlayerKey, minGames, minMinutes],
    queryFn: ({ signal }) => getPlayerSimilarity(scope, selectedPlayerKey, minGames, minMinutes, { signal }),
    enabled: Boolean(scope.season && scope.league && selectedPlayerKey),
    placeholderData: keepPreviousData,
  });

  const data = similarityQuery.data ?? null;
  const error = similarityQuery.error instanceof Error ? similarityQuery.error.message : null;

  useEffect(() => {
    if (!data?.target?.playerKey) {
      return;
    }
    setSelectedPlayerKey((current) => (current === data.target?.playerKey ? current : data.target?.playerKey ?? ""));
  }, [data?.target?.playerKey, setSelectedPlayerKey]);

  useEffect(() => {
    if (!selectedCandidateKey) {
      return;
    }
    if (!data?.candidates.some((candidate) => candidate.playerKey === selectedCandidateKey)) {
      setSelectedCandidateKey(null);
      setShowDetail(false);
    }
  }, [data?.candidates, selectedCandidateKey]);

  const candidateRows = useMemo(
    () =>
      (data?.candidates ?? []).map((candidate) => ({
        PLAYER_KEY: candidate.playerKey,
        JUGADOR: candidate.name,
        EQUIPO: candidate.team,
        PJ: candidate.gamesPlayed,
        MINUTOS: candidate.minutes,
        PUNTOS: candidate.points,
        REBOTES: candidate.rebounds,
        ASISTENCIAS: candidate.assists,
        "USG%": candidate.usg,
        SCORE: candidate.similarityScore,
      })),
    [data?.candidates]
  );

  const selectedCandidate = useMemo(
    () => data?.candidates.find((candidate) => candidate.playerKey === selectedCandidateKey) ?? null,
    [data?.candidates, selectedCandidateKey]
  );
  const formatBaselineMetric = (value: unknown, digits = 1, suffix = "") => {
    if (value === null || value === undefined || value === "") {
      return "-";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${formatNumber(numeric, digits)}${suffix}`;
  };
  const targetBaselineCards = useMemo(() => {
    if (!data?.target) {
      return [];
    }
    return [
      { label: "PJ", value: String(data.target.gamesPlayed) },
      { label: "Minutos", value: formatBaselineMetric(data.target.minutes, 1) },
      { label: "Puntos", value: formatBaselineMetric(data.target.points, 1) },
      { label: "Reb", value: formatBaselineMetric(data.target.rebounds, 1) },
      { label: "Ast", value: formatBaselineMetric(data.target.assists, 1) },
      { label: "Perdidas", value: formatBaselineMetric(data.target.turnovers, 1) },
      { label: "USG%", value: formatBaselineMetric(data.target.usg, 1, "%") },
      { label: "eFG%", value: formatBaselineMetric(data.target.efg, 1, "%") },
      { label: "AST/TO", value: formatBaselineMetric(data.target.astTo, 2) },
    ];
  }, [data?.target]);
  const selectedCandidateImage =
    typeof selectedCandidate?.image === "string" && /^https?:\/\//.test(selectedCandidate.image) ? selectedCandidate.image : null;

  const topCandidate = data?.candidates[0] ?? null;

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Reemplazo</span>
            <h2>Similares</h2>
            <p className="panel-copy">Ranking de perfiles parecidos dentro de la misma liga y el scope actual.</p>
          </div>
          <div className="toolbar">
            {similarityQuery.isFetching && !similarityQuery.isLoading ? <span className="status-badge">Actualizando</span> : null}
          </div>
        </div>

        <section className="control-panel">
          <div className="search-toolbar-grid">
            <SearchSelect
              label="Jugador objetivo"
              options={playerOptions}
              value={selectedPlayerKey}
              onChange={(value) => {
                setSelectedPlayerKey(value);
                setSelectedCandidateKey(null);
                setShowDetail(false);
              }}
              placeholder="Busca un jugador"
              disabled={!playerOptions.length}
              suggestionLimit={5}
            />
            <div className="compact-control-card">
              <label>
                Partidos minimos
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={minGames}
                  onChange={(event) => setMinGames(Math.max(0, Number(event.target.value || 0)))}
                />
              </label>
            </div>
            <div className="compact-control-card">
              <label>
                Minutos medios minimos
                <input
                  type="number"
                  min={0}
                  max={60}
                  step={1}
                  value={minMinutes}
                  onChange={(event) => setMinMinutes(Math.max(0, Number(event.target.value || 0)))}
                />
              </label>
            </div>
          </div>
        </section>

        <div className="metric-grid metric-grid-wide">
          <MetricCard label="Jugador objetivo" value={data?.target?.label ?? "-"} isLoading={similarityQuery.isLoading} />
          <MetricCard label="Candidatos" value={String(data?.candidates.length ?? 0)} isLoading={similarityQuery.isLoading} />
          <MetricCard label="Mejor score" value={topCandidate ? formatNumber(topCandidate.similarityScore, 1) : "-"} isLoading={similarityQuery.isLoading} />
          <MetricCard label="Filtro" value={`${data?.filters.minGames ?? minGames} PJ | ${data?.filters.minMinutes ?? minMinutes} MIN`} isLoading={similarityQuery.isLoading} />
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

        <div className="insight-banner">
          <strong>Lectura</strong>
          <span>{topCandidate ? `${topCandidate.label} es el perfil mas cercano ahora mismo.` : "Ajusta filtros si quieres ampliar el mercado."}</span>
        </div>

        {similarityQuery.isLoading ? <p className="empty-state">Buscando perfiles similares...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        <div className={showDetail ? "split-layout" : "page-stack"}>
          <div className="split-main">
            <DataTable
              title="Top 10 similares"
              subtitle="Candidatos ordenados por score de parecido."
              columns={["JUGADOR", "EQUIPO", "PJ", "MINUTOS", "PUNTOS", "REBOTES", "ASISTENCIAS", "USG%", "SCORE"]}
              rows={candidateRows}
              isLoading={similarityQuery.isLoading}
              isUpdating={similarityQuery.isFetching && !similarityQuery.isLoading}
              selectedKey={selectedCandidateKey}
              onSelect={(row) => {
                setSelectedCandidateKey(String(row.PLAYER_KEY ?? ""));
                setShowDetail(true);
              }}
              defaultSortColumn="SCORE"
              storageKey="similarity-candidates-v1"
              lockedLeadingColumns={["JUGADOR"]}
            />
          </div>

          {showDetail ? (
            <aside className="split-side">
              <section className="panel detail-panel">
                <div className="detail-panel-header">
                  <div>
                    <span className="eyebrow">Candidato</span>
                    <h3>{selectedCandidate?.label ?? "Selecciona un jugador"}</h3>
                    <p className="panel-copy">
                      {selectedCandidate
                        ? `${selectedCandidate.focus || "Perfil mixto"} | Score ${formatNumber(selectedCandidate.similarityScore, 1)}`
                        : "Haz click en un candidato para ver el detalle."}
                    </p>
                  </div>
                  <button type="button" className="ghost-button" onClick={() => setShowDetail(false)}>
                    Cerrar
                  </button>
                </div>

                {selectedCandidate ? (
                  <>
                    {selectedCandidateImage ? (
                      <img className="player-image player-image-large" src={selectedCandidateImage} alt={selectedCandidate.name} />
                    ) : (
                      <div className="player-placeholder">SIM</div>
                    )}
                    <div className="metric-grid">
                      <MetricCard label="Score" value={formatNumber(selectedCandidate.similarityScore, 1)} />
                      <MetricCard label="Minutos" value={formatNumber(selectedCandidate.minutes, 1)} />
                      <MetricCard label="Puntos" value={formatNumber(selectedCandidate.points, 1)} />
                      <MetricCard label="Rebotes" value={formatNumber(selectedCandidate.rebounds, 1)} />
                      <MetricCard label="Asistencias" value={formatNumber(selectedCandidate.assists, 1)} />
                      <MetricCard label="USG%" value={formatNumber(selectedCandidate.usg, 1)} />
                    </div>

                    <div className="detail-note-block">
                      <strong>Por que se parece</strong>
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
                ) : (
                  <div className="detail-empty">
                    <p className="empty-state">No hay detalle seleccionado.</p>
                  </div>
                )}
              </section>
            </aside>
          ) : null}
        </div>
      </section>
    </div>
  );
}
