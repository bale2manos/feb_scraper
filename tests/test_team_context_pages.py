from __future__ import annotations

import unittest

import pandas as pd

from team_report.tools.context_pages import (
    build_clutch_split_payload,
    build_context_split_payload,
    build_team_clutch_page,
    build_team_context_page,
)


class TeamContextPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.team_name = "Team A"
        self.games_df = pd.DataFrame(
            [
                {
                    "PID": 1,
                    "EQUIPO LOCAL": "Team A",
                    "EQUIPO RIVAL": "Team B",
                    "PUNTOS": 80,
                    "PTS_RIVAL": 70,
                    "OFFRTG": 112.0,
                    "DEFRTG": 98.0,
                    "NETRTG": 14.0,
                    "ASISTENCIAS": 18,
                    "PERDIDAS": 10,
                    "T2 CONVERTIDO": 20,
                    "T2 INTENTADO": 40,
                    "T3 CONVERTIDO": 10,
                    "T3 INTENTADO": 25,
                    "TL CONVERTIDOS": 10,
                    "TL INTENTADOS": 12,
                    "%OREB": 0.30,
                    "%DREB": 0.70,
                    "%REB": 0.52,
                    "IS_HOME": True,
                },
                {
                    "PID": 2,
                    "EQUIPO LOCAL": "Team A",
                    "EQUIPO RIVAL": "Team C",
                    "PUNTOS": 72,
                    "PTS_RIVAL": 78,
                    "OFFRTG": 101.0,
                    "DEFRTG": 109.0,
                    "NETRTG": -8.0,
                    "ASISTENCIAS": 14,
                    "PERDIDAS": 13,
                    "T2 CONVERTIDO": 18,
                    "T2 INTENTADO": 38,
                    "T3 CONVERTIDO": 8,
                    "T3 INTENTADO": 24,
                    "TL CONVERTIDOS": 12,
                    "TL INTENTADOS": 15,
                    "%OREB": 0.27,
                    "%DREB": 0.66,
                    "%REB": 0.49,
                    "IS_HOME": True,
                },
                {
                    "PID": 3,
                    "EQUIPO LOCAL": "Team A",
                    "EQUIPO RIVAL": "Team D",
                    "PUNTOS": 76,
                    "PTS_RIVAL": 71,
                    "OFFRTG": 108.0,
                    "DEFRTG": 99.0,
                    "NETRTG": 9.0,
                    "ASISTENCIAS": 17,
                    "PERDIDAS": 11,
                    "T2 CONVERTIDO": 21,
                    "T2 INTENTADO": 41,
                    "T3 CONVERTIDO": 7,
                    "T3 INTENTADO": 20,
                    "TL CONVERTIDOS": 13,
                    "TL INTENTADOS": 16,
                    "%OREB": 0.31,
                    "%DREB": 0.69,
                    "%REB": 0.53,
                    "IS_HOME": False,
                },
                {
                    "PID": 4,
                    "EQUIPO LOCAL": "Team A",
                    "EQUIPO RIVAL": "Team E",
                    "PUNTOS": 65,
                    "PTS_RIVAL": 75,
                    "OFFRTG": 95.0,
                    "DEFRTG": 108.0,
                    "NETRTG": -13.0,
                    "ASISTENCIAS": 12,
                    "PERDIDAS": 15,
                    "T2 CONVERTIDO": 17,
                    "T2 INTENTADO": 39,
                    "T3 CONVERTIDO": 6,
                    "T3 INTENTADO": 22,
                    "TL CONVERTIDOS": 11,
                    "TL INTENTADOS": 14,
                    "%OREB": 0.24,
                    "%DREB": 0.63,
                    "%REB": 0.46,
                    "IS_HOME": False,
                },
            ]
        )
        self.boxscores_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "EQUIPO LOCAL": "Team A", "IdPartido": 1, "MINUTOS JUGADOS": 30, "PUNTOS": 18, "T2 INTENTADO": 8, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 2},
                {"PLAYER_KEY": "p2", "JUGADOR": "Beta", "DORSAL": "12", "EQUIPO LOCAL": "Team A", "IdPartido": 1, "MINUTOS JUGADOS": 25, "PUNTOS": 12, "T2 INTENTADO": 6, "T3 INTENTADO": 3, "TL INTENTADOS": 1, "PERDIDAS": 1},
                {"PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "EQUIPO LOCAL": "Team A", "IdPartido": 2, "MINUTOS JUGADOS": 31, "PUNTOS": 17, "T2 INTENTADO": 9, "T3 INTENTADO": 3, "TL INTENTADOS": 4, "PERDIDAS": 2},
                {"PLAYER_KEY": "p2", "JUGADOR": "Beta", "DORSAL": "12", "EQUIPO LOCAL": "Team A", "IdPartido": 2, "MINUTOS JUGADOS": 22, "PUNTOS": 9, "T2 INTENTADO": 5, "T3 INTENTADO": 4, "TL INTENTADOS": 1, "PERDIDAS": 2},
                {"PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "EQUIPO LOCAL": "Team A", "IdPartido": 3, "MINUTOS JUGADOS": 29, "PUNTOS": 16, "T2 INTENTADO": 7, "T3 INTENTADO": 5, "TL INTENTADOS": 2, "PERDIDAS": 1},
                {"PLAYER_KEY": "p3", "JUGADOR": "Gamma", "DORSAL": "21", "EQUIPO LOCAL": "Team A", "IdPartido": 3, "MINUTOS JUGADOS": 24, "PUNTOS": 14, "T2 INTENTADO": 5, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 1},
                {"PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "EQUIPO LOCAL": "Team A", "IdPartido": 4, "MINUTOS JUGADOS": 28, "PUNTOS": 13, "T2 INTENTADO": 8, "T3 INTENTADO": 3, "TL INTENTADOS": 2, "PERDIDAS": 3},
                {"PLAYER_KEY": "p3", "JUGADOR": "Gamma", "DORSAL": "21", "EQUIPO LOCAL": "Team A", "IdPartido": 4, "MINUTOS JUGADOS": 26, "PUNTOS": 11, "T2 INTENTADO": 6, "T3 INTENTADO": 3, "TL INTENTADOS": 2, "PERDIDAS": 1},
            ]
        )
        self.clutch_games_df = pd.DataFrame(
            [
                {"IdPartido": 1, "EQUIPO": "Team A", "PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "FGA": 4, "FGM": 2, "3PA": 2, "3PM": 1, "FTA": 2, "FTM": 2, "PTS": 999},
                {"IdPartido": 1, "EQUIPO": "Team A", "PLAYER_KEY": "p2", "JUGADOR": "Beta", "DORSAL": "12", "FGA": 2, "FGM": 1, "3PA": 1, "3PM": 0, "FTA": 0, "FTM": 0, "PTS": 999},
                {"IdPartido": 2, "EQUIPO": "Team A", "PLAYER_KEY": "p1", "JUGADOR": "Alpha", "DORSAL": "7", "FGA": 3, "FGM": 1, "3PA": 1, "3PM": 0, "FTA": 2, "FTM": 2, "PTS": 999},
                {"IdPartido": 2, "EQUIPO": "Team A", "PLAYER_KEY": "p2", "JUGADOR": "Beta", "DORSAL": "12", "FGA": 5, "FGM": 2, "3PA": 2, "3PM": 1, "FTA": 1, "FTM": 1, "PTS": 999},
            ]
        )
        self.clutch_lineups_df = pd.DataFrame(
            [
                {"PARTIDO_ID": 1, "EQUIPO": "Team A", "SEC_CLUTCH": 120, "NET_RTG": 12.0},
                {"PARTIDO_ID": 1, "EQUIPO": "Team A", "SEC_CLUTCH": 60, "NET_RTG": 6.0},
                {"PARTIDO_ID": 2, "EQUIPO": "Team A", "SEC_CLUTCH": 90, "NET_RTG": -8.0},
                {"PARTIDO_ID": 2, "EQUIPO": "Team A", "SEC_CLUTCH": 90, "NET_RTG": -4.0},
            ]
        )

    def test_context_payload_home_away_includes_requested_metrics(self) -> None:
        payload = build_context_split_payload(self.team_name, self.games_df, self.boxscores_df, "home_away")

        self.assertEqual(payload["title"], "Local vs Visitante")
        local_row = next(row for row in payload["rows"] if row["SPLIT"] == "Local")
        away_row = next(row for row in payload["rows"] if row["SPLIT"] == "Visitante")
        self.assertEqual(local_row["PJ"], 2)
        self.assertAlmostEqual(local_row["WIN_PCT"], 50.0)
        self.assertAlmostEqual(local_row["AST"], 16.0)
        self.assertAlmostEqual(local_row["TURNOVERS"], 11.5)
        self.assertAlmostEqual(local_row["T3_PCT"], 36.7346938776, places=3)
        self.assertAlmostEqual(away_row["OREB_PCT"], 27.5)
        self.assertAlmostEqual(away_row["DREB_PCT"], 66.0)
        self.assertAlmostEqual(away_row["REB_PCT"], 49.5)
        self.assertEqual(len(payload["leaders"]), 2)

    def test_context_payload_result_split_tracks_wins_and_losses(self) -> None:
        payload = build_context_split_payload(self.team_name, self.games_df, self.boxscores_df, "result")

        self.assertEqual(payload["title"], "Victoria vs Derrota")
        win_row = next(row for row in payload["rows"] if row["SPLIT"] == "Victoria")
        loss_row = next(row for row in payload["rows"] if row["SPLIT"] == "Derrota")
        metric_keys = [metric[0] for metric in payload["metricSpecs"]]
        self.assertEqual(win_row["PJ"], 2)
        self.assertEqual(loss_row["PJ"], 2)
        self.assertNotIn("WIN_PCT", metric_keys)
        self.assertGreater(win_row["NETRTG"], loss_row["NETRTG"])

    def test_clutch_payload_splits_wins_losses_and_shot_share(self) -> None:
        payload = build_clutch_split_payload(self.team_name, self.games_df, self.clutch_games_df, self.clutch_lineups_df)

        self.assertEqual(payload["title"], "Clutch y cierre")
        win_row = next(row for row in payload["rows"] if row["SPLIT"] == "Victoria")
        loss_row = next(row for row in payload["rows"] if row["SPLIT"] == "Derrota")
        self.assertEqual(win_row["GAMES"], 1)
        self.assertEqual(loss_row["GAMES"], 1)
        self.assertAlmostEqual(win_row["NET_RTG"], 10.0)
        self.assertAlmostEqual(loss_row["NET_RTG"], -6.0)

        win_table = next(table for table in payload["shotTables"] if "victoria" in table["title"].lower())
        total_share = sum(row["SHOT_SHARE"] for row in win_table["rows"])
        self.assertAlmostEqual(total_share, 100.0)
        alpha = next(row for row in win_table["rows"] if row["JUGADOR"] == "Alpha")
        self.assertEqual(alpha["PLAYER_LABEL"], "#7 Alpha")
        self.assertAlmostEqual(alpha["PTS"], 7.0)

    def test_clutch_payload_handles_missing_data_without_crashing(self) -> None:
        payload = build_clutch_split_payload(self.team_name, self.games_df, pd.DataFrame(), pd.DataFrame())

        self.assertEqual(len(payload["shotTables"]), 2)
        self.assertTrue(all(not table["rows"] for table in payload["shotTables"]))

        clutch_fig = build_team_clutch_page(self.team_name, payload)
        self.assertIsNotNone(clutch_fig)

    def test_context_and_clutch_pages_render_figures(self) -> None:
        context_payload = build_context_split_payload(self.team_name, self.games_df, self.boxscores_df, "home_away")
        clutch_payload = build_clutch_split_payload(self.team_name, self.games_df, self.clutch_games_df, self.clutch_lineups_df)

        context_fig = build_team_context_page(self.team_name, context_payload)
        clutch_fig = build_team_clutch_page(self.team_name, clutch_payload)

        self.assertIsNotNone(context_fig)
        self.assertIsNotNone(clutch_fig)


if __name__ == "__main__":
    unittest.main()
