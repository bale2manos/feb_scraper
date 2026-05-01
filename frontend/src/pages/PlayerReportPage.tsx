import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { generatePlayerReport } from "../api";
import { MetricCard } from "../components/MetricCard";
import { ReportPreview } from "../components/ReportPreview";
import { ScopeFilters } from "../components/ScopeFilters";
import { SearchSelect } from "../components/SearchSelect";
import { useLocalStorageState } from "../hooks";
import { buildScopeTaskKey, useReports } from "../reports";
import { useScopeMeta } from "../scope";
import type { ScopeState } from "../types";

type ScopePageProps = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

export function PlayerReportPage({ scope, setScope }: ScopePageProps) {
  const navigate = useNavigate();
  const { meta } = useScopeMeta();
  const { getLatestJob, openPreview, startReportJob } = useReports();
  const [selectedTeam, setSelectedTeam] = useLocalStorageState<string>("react-player-report-team", "Todos");
  const [selectedPlayerKey, setSelectedPlayerKey] = useLocalStorageState<string>("react-player-report-player", "");
  const [isBulkRunning, setIsBulkRunning] = useState(false);
  const mountedRef = useRef(true);

  const teamOptions = useMemo(
    () => [{ value: "Todos", label: "Todos" }, ...meta.teams.map((team) => ({ value: team.name, label: team.name }))],
    [meta.teams]
  );
  const filteredPlayers = meta.players.filter((player) => selectedTeam === "Todos" || player.team === selectedTeam);
  const playerOptions = filteredPlayers.map((player) => ({ value: player.playerKey, label: player.label }));
  const selectedPlayer = filteredPlayers.find((player) => player.playerKey === selectedPlayerKey) ?? filteredPlayers[0] ?? null;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!teamOptions.some((team) => team.value === selectedTeam)) {
      setSelectedTeam("Todos");
    }
  }, [selectedTeam, setSelectedTeam, teamOptions]);

  useEffect(() => {
    if (!selectedPlayer) {
      if (selectedPlayerKey) {
        setSelectedPlayerKey("");
      }
      return;
    }
    if (selectedPlayer.playerKey !== selectedPlayerKey) {
      setSelectedPlayerKey(selectedPlayer.playerKey);
    }
  }, [selectedPlayer, selectedPlayerKey, setSelectedPlayerKey]);

  const playerTaskKey = buildScopeTaskKey("player", scope, [selectedTeam, selectedPlayer?.playerKey ?? ""]);
  const playerJob = getLatestJob(playerTaskKey);
  const error = playerJob?.status === "error" ? playerJob.error : null;

  async function handleGeneratePlayer() {
    if (!selectedPlayer) {
      return;
    }
    await startReportJob({
      taskKey: playerTaskKey,
      kind: "player",
      title: selectedPlayer.label,
      subtitle: `PNG individual | ${selectedTeam}`,
      run: () => generatePlayerReport(scope, selectedTeam, selectedPlayer.playerKey),
      getReport: (result) => result.report
    });
  }

  async function handleGenerateTeamBatch() {
    if (selectedTeam === "Todos" || !filteredPlayers.length) {
      return;
    }
    setIsBulkRunning(true);
    try {
      for (const player of filteredPlayers) {
        const taskKey = buildScopeTaskKey("player", scope, [selectedTeam, player.playerKey]);
        try {
          await startReportJob({
            taskKey,
            kind: "player",
            title: player.label,
            subtitle: `PNG individual | ${selectedTeam}`,
            run: () => generatePlayerReport(scope, selectedTeam, player.playerKey),
            getReport: (result) => result.report
          });
        } catch {
          // Seguimos con el resto del equipo y dejamos el error reflejado en el centro de informes.
        }
      }
    } finally {
      if (mountedRef.current) {
        setIsBulkRunning(false);
      }
    }
  }

  return (
    <div className="page-stack">
      <ScopeFilters scope={scope} meta={meta} onChange={setScope} />

      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Informe</span>
            <h2>Jugador</h2>
            <p className="panel-copy">Genera un PNG individual o lanza toda la serie de un equipo.</p>
          </div>
          {playerJob?.status === "pending" || isBulkRunning ? <span className="status-badge">Generando</span> : null}
        </div>

        <div className="split-layout">
          <div className="split-main">
            <section className="control-panel">
              <div className="search-toolbar-grid">
                <SearchSelect
                  label="Equipo"
                  options={teamOptions}
                  value={selectedTeam}
                  onChange={setSelectedTeam}
                  placeholder="Busca un equipo"
                />
                <SearchSelect
                  label="Jugador"
                  options={playerOptions}
                  value={selectedPlayer?.playerKey ?? ""}
                  onChange={setSelectedPlayerKey}
                  placeholder="Busca un jugador"
                  disabled={!playerOptions.length}
                  suggestionLimit={5}
                  showSuggestionsOnlyWhenQuery={true}
                />
              </div>

              <div className="metric-grid metric-grid-wide">
                <MetricCard label="Equipo" value={selectedTeam} />
                <MetricCard label="Jugadores disponibles" value={String(filteredPlayers.length)} />
                <MetricCard label="Jugador" value={selectedPlayer?.name ?? "-"} />
                <MetricCard label="Partidos en filtro" value={String(selectedPlayer?.gamesPlayed ?? 0)} />
              </div>

              {error ? <p className="error-text">{error}</p> : null}

              <div className="report-action-card report-action-card-stacked">
                <div className="report-action-copy">
                  <span className="eyebrow">Salida</span>
                  <h3>Informes de jugador</h3>
                  <p className="panel-copy">
                    {selectedPlayer
                      ? `${selectedPlayer.label} | ${selectedPlayer.gamesPlayed} partidos en el filtro`
                      : "Selecciona un jugador para generar el PNG."}
                  </p>
                </div>

                <div className="report-action-button-group">
                  <button
                    className="primary-cta-button"
                    type="button"
                    onClick={() => {
                      void handleGeneratePlayer();
                    }}
                    disabled={!selectedPlayer || playerJob?.status === "pending"}
                  >
                    {playerJob?.status === "pending" ? "Generando PNG..." : "Generar informe PNG"}
                  </button>

                  <button
                    className="ghost-button strong-ghost-button"
                    type="button"
                    onClick={() => {
                      void handleGenerateTeamBatch();
                    }}
                    disabled={selectedTeam === "Todos" || !filteredPlayers.length || isBulkRunning}
                  >
                    {isBulkRunning ? "Generando equipo..." : "Generar todos los jugadores del equipo"}
                  </button>

                  <button
                    className="ghost-button strong-ghost-button"
                    type="button"
                    onClick={() => {
                      if (!selectedPlayer?.playerKey) {
                        return;
                      }
                      window.localStorage.setItem("react-similarity-target-player", JSON.stringify(selectedPlayer.playerKey));
                      navigate("/similares");
                    }}
                    disabled={!selectedPlayer}
                  >
                    Buscar similares
                  </button>
                </div>
              </div>
            </section>
          </div>

          <aside className="split-side">
            <ReportPreview
              title={playerJob?.title ?? selectedPlayer?.label ?? "Informe de jugador"}
              subtitle="Vista previa y descarga del PNG."
              report={playerJob?.report ?? null}
              emptyMessage="Genera un informe para verlo aqui."
              isGenerating={playerJob?.status === "pending"}
              statusMessage="Generando el PNG del jugador."
              onOpenFloating={playerJob?.report ? () => openPreview(playerJob.id) : null}
            />
          </aside>
        </div>
      </section>
    </div>
  );
}
