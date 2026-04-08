import { useNavigate } from "react-router-dom";

type PlayerDetailActionsProps = {
  playerKey: string | null | undefined;
  team?: string | null;
  currentPage?: "similares" | "tendencias" | "jugador" | "other";
  className?: string;
};

function persistLocalSelection(key: string, value: unknown) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function PlayerDetailActions({
  playerKey,
  team,
  currentPage = "other",
  className = "player-detail-actions"
}: PlayerDetailActionsProps) {
  const navigate = useNavigate();
  const normalizedPlayerKey = String(playerKey ?? "").trim();
  const normalizedTeam = String(team ?? "").trim() || "Todos";

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
            persistLocalSelection("react-similarity-target-player", normalizedPlayerKey);
            navigate("/similares");
          }}
        >
          Ver similares
        </button>
      ) : null}
    </div>
  );
}
