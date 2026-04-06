import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function buildMetaResponse() {
  return {
    seasons: ["25_26", "24_25"],
    leagues: ["Primera FEB"],
    phases: ["Liga"],
    jornadas: [1, 2, 3],
    selected: {
      season: "25_26",
      league: "Primera FEB",
      phases: ["Liga"],
      jornadas: [1, 2]
    },
    teams: [{ name: "Team A", gamesPlayed: 10 }],
    players: [
      { playerKey: "p1", label: "#7 Jugador Uno | Team A", name: "Jugador Uno", team: "Team A", gamesPlayed: 10 },
      { playerKey: "p2", label: "#12 Jugador Dos | Team A", name: "Jugador Dos", team: "Team A", gamesPlayed: 8 }
    ]
  };
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    globalThis.fetch = vi.fn((input) => {
      const url = String(input);
      if (url.includes("/meta/scopes")) {
        return Promise.resolve(new Response(JSON.stringify(buildMetaResponse()), { status: 200 }));
      }
      if (url.includes("/gm/players")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              scope: buildMetaResponse().selected,
              mode: "Totales",
              columns: ["JUGADOR", "PUNTOS"],
              rows: [{ PLAYER_KEY: "p1", JUGADOR: "Jugador Uno", PUNTOS: 10, IMAGEN: "img", EQUIPO: "Team A", "REB TOTALES": 5, ASISTENCIAS: 4, "USG%": 20, PPP: 1.1, "TS%": 56 }],
              players: buildMetaResponse().players
            }),
            { status: 200 }
          )
        );
      }
      if (url.includes("/trends/player")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              scope: buildMetaResponse().selected,
              players: buildMetaResponse().players,
              selectedPlayerKey: "p2",
              availableMetrics: [
                { key: "PUNTOS", label: "PTS" },
                { key: "REB", label: "REB" }
              ],
              selectedMetrics: ["PUNTOS", "REB"],
              window: 3,
              windowMax: 8,
              recentCount: 3,
              summaryRows: [{ metric: "PUNTOS", recent_avg: 12, scope_avg: 10, delta: 2 }],
              recentGames: [{ PARTIDO: "J3 vs X", PUNTOS: 12, REB: 5 }],
              chartRows: [{ PARTIDO: "J3 vs X", PUNTOS: 12, REB: 5 }]
            }),
            { status: 200 }
          )
        );
      }
      if (url.includes("/trends/team")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              scope: buildMetaResponse().selected,
              teams: buildMetaResponse().teams,
              selectedTeam: "Team A",
              availableMetrics: [{ key: "NETRTG", label: "NETRTG" }],
              selectedMetrics: ["NETRTG"],
              window: 4,
              windowMax: 10,
              recentCount: 4,
              summaryRows: [{ metric: "NETRTG", recent_avg: 4, scope_avg: 2, delta: 2 }],
              recentGames: [{ PARTIDO: "J3 vs X", NETRTG: 4 }],
              chartRows: [{ PARTIDO: "J3 vs X", NETRTG: 4 }]
            }),
            { status: 200 }
          )
        );
      }
      if (url.includes("/dependency/players")) {
        return Promise.resolve(new Response(JSON.stringify({ scope: buildMetaResponse().selected, rows: [], teams: buildMetaResponse().teams, players: buildMetaResponse().players }), { status: 200 }));
      }
      if (url.includes("/dependency/team-summary")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              scope: buildMetaResponse().selected,
              selectedTeam: "Team A",
              selectedPlayerKey: "p1",
              structuralRisk: "Riesgo estructural del equipo: uso ofensivo.",
              metrics: { criticalPlayer: "Jugador Uno", topUsage: 35, topScoring: 28, topCreation: 22, top3Usage: 75 },
              detail: {
                playerKey: "p1",
                name: "Jugador Uno",
                image: "img",
                team: "Team A",
                gamesPlayed: 10,
                risk: "Alta",
                focus: "Uso ofensivo",
                dependencyScore: 77,
                usageShare: 35,
                scoringShare: 28,
                creationShare: 22,
                reboundShare: 16,
                clutchShare: 12,
                hasClutchData: true,
                diagnosis: "Detalle"
              },
              tableRows: [{ PLAYER_KEY: "p1", JUGADOR: "Jugador Uno" }],
              note: "Nota"
            }),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    }) as typeof fetch;
  });

  it("permite cambiar de vista y actualizar tendencias con jugador, equipo, ventana y métricas", async () => {
    render(<App />);

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Temporada"), { target: { value: "24_25" } });
    await waitFor(() => {
      const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
      expect(String(calls[calls.length - 1]?.[0])).toContain("/gm/players");
    });

    fireEvent.click(screen.getByRole("button", { name: "Tendencias" }));
    await waitFor(() => expect(screen.getByLabelText("Jugador")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Jugador"), { target: { value: "p2" } });
    fireEvent.change(screen.getByLabelText("Partidos a mostrar"), { target: { value: 3 } });
    fireEvent.click(screen.getByLabelText("REB"));

    await waitFor(() => {
      const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
      const lastUrl = String(calls[calls.length - 1]?.[0]);
      expect(lastUrl).toContain("/trends/player");
      expect(lastUrl).toContain("window=3");
      expect(lastUrl).toContain("metrics=REB");
    });

    fireEvent.click(screen.getByRole("button", { name: "Equipos" }));
    await waitFor(() => expect(screen.getByLabelText("Equipo")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Equipo"), { target: { value: "Team A" } });

    await waitFor(() => {
      const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
      const lastUrl = String(calls[calls.length - 1]?.[0]);
      expect(lastUrl).toContain("/trends/team");
    });
  });
});
