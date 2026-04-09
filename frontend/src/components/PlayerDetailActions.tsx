import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { addPlayerToMarketShortlist, queueMarketIntent, readSharedScopeFromStorage } from "../market";

type PlayerDetailActionsProps = {
  playerKey: string | null | undefined;
  team?: string | null;
  season?: string | null;
  league?: string | null;
  currentPage?: "potencial" | "similares" | "tendencias" | "jugador" | "other";
  className?: string;
};

function persistLocalSelection(key: string, value: unknown) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function PlayerDetailActions({
  playerKey,
  team,
  season,
  league,
  currentPage = "other",
  className = "player-detail-actions"
}: PlayerDetailActionsProps) {
  const navigate = useNavigate();
  const [shortlistNotice, setShortlistNotice] = useState("");
  const normalizedPlayerKey = String(playerKey ?? "").trim();
  const normalizedTeam = String(team ?? "").trim() || "Todos";
  const sharedScope = readSharedScopeFromStorage();
  const normalizedSeason = String(season ?? sharedScope.season ?? "").trim();
  const normalizedLeague = String(league ?? sharedScope.league ?? "").trim();

  useEffect(() => {
    if (!shortlistNotice) {
      return;
    }
    const timeoutId = window.setTimeout(() => setShortlistNotice(""), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [shortlistNotice]);

  if (!normalizedPlayerKey) {
    return null;
  }

  return (
    <div className={className}>
      {currentPage !== "jugador" ? (
        <button
          type="button"
          className="ghost-button strong-ghost-button"
          onClick={() => {
            persistLocalSelection("react-player-report-team", normalizedTeam);
            persistLocalSelection("react-player-report-player", normalizedPlayerKey);
            navigate("/jugador");
          }}
        >
          Generar informe
        </button>
      ) : null}

      {currentPage !== "tendencias" ? (
        <button
          type="button"
          className="ghost-button strong-ghost-button"
          onClick={() => {
            persistLocalSelection("react-trends-tab", "players");
            persistLocalSelection("react-trends-player", normalizedPlayerKey);
            navigate("/tendencias");
          }}
        >
          Ver tendencia
        </button>
      ) : null}

      {currentPage !== "similares" ? (
        <button
          type="button"
          className="ghost-button strong-ghost-button"
          onClick={() => {
            queueMarketIntent({
              season: normalizedSeason,
              league: normalizedLeague,
              playerKey: normalizedPlayerKey,
              action: "target",
              source: currentPage
            });
            navigate("/similares");
          }}
          disabled={!normalizedSeason || !normalizedLeague}
        >
          Buscar reemplazo
        </button>
      ) : null}

      <button
        type="button"
        className="ghost-button strong-ghost-button"
        onClick={() => {
          if (!normalizedSeason || !normalizedLeague) {
            return;
          }
          const nextShortlist = addPlayerToMarketShortlist(normalizedSeason, [normalizedLeague], normalizedPlayerKey);
          setShortlistNotice(
            nextShortlist.includes(normalizedPlayerKey)
              ? "Añadido al shortlist"
              : "Shortlist llena (máximo 6)"
          );
        }}
        disabled={!normalizedSeason || !normalizedLeague}
      >
        Añadir al shortlist
      </button>

      {currentPage !== "similares" ? (
        <button
          type="button"
          className="ghost-button strong-ghost-button"
          onClick={() => {
            if (!normalizedSeason || !normalizedLeague) {
              return;
            }
            queueMarketIntent({
              season: normalizedSeason,
              league: normalizedLeague,
              playerKey: normalizedPlayerKey,
              action: "compare",
              source: currentPage
            });
            navigate("/similares");
          }}
          disabled={!normalizedSeason || !normalizedLeague}
        >
          Abrir comparador
        </button>
      ) : null}

      {shortlistNotice ? <span className="detail-note">{shortlistNotice}</span> : null}
    </div>
  );
}
