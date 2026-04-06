from __future__ import annotations

import unittest

import pandas as pd

from utils.trends_view import (
    PLAYER_TREND_METRIC_OPTIONS,
    TEAM_TREND_METRIC_OPTIONS,
    build_player_scope_baseline,
    build_recent_player_games,
    build_recent_team_games,
    build_recent_vs_scope_summary,
    build_team_scope_baseline,
    build_trend_chart_frame,
)


class TrendsViewTests(unittest.TestCase):
    def test_build_recent_player_games_orders_by_recency_and_exposes_columns(self) -> None:
        boxscores_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "IdPartido": 10, "JORNADA": 1, "FASE": "Liga", "EQUIPO RIVAL": "A", "MINUTOS JUGADOS": 20, "PUNTOS": 8, "REB OFFENSIVO": 1, "REB DEFENSIVO": 3, "ASISTENCIAS": 2, "PERDIDAS": 1, "T2 INTENTADO": 5, "T3 INTENTADO": 2, "TL INTENTADOS": 2},
                {"PLAYER_KEY": "p1", "IdPartido": 12, "JORNADA": 3, "FASE": "Liga", "EQUIPO RIVAL": "C", "MINUTOS JUGADOS": 28, "PUNTOS": 14, "REB OFFENSIVO": 2, "REB DEFENSIVO": 4, "ASISTENCIAS": 5, "PERDIDAS": 3, "T2 INTENTADO": 8, "T3 INTENTADO": 4, "TL INTENTADOS": 4},
                {"PLAYER_KEY": "p1", "IdPartido": 11, "JORNADA": 2, "FASE": "Liga", "EQUIPO RIVAL": "B", "MINUTOS JUGADOS": 24, "PUNTOS": 10, "REB OFFENSIVO": 1, "REB DEFENSIVO": 5, "ASISTENCIAS": 3, "PERDIDAS": 2, "T2 INTENTADO": 6, "T3 INTENTADO": 3, "TL INTENTADOS": 2},
            ]
        )

        recent_df = build_recent_player_games(boxscores_df, "p1", last_n=2)

        self.assertEqual(list(recent_df.columns), ["PARTIDO", "FASE", "JORNADA", "RIVAL", "RESULTADO", "MINUTOS", "PUNTOS", "REB", "AST", "PERDIDAS", "PLAYS"])
        self.assertEqual(int(recent_df.shape[0]), 2)
        self.assertEqual(str(recent_df.iloc[0]["RIVAL"]), "C")
        self.assertEqual(str(recent_df.iloc[1]["RIVAL"]), "B")
        self.assertAlmostEqual(float(recent_df.iloc[0]["PLAYS"]), 16.76, places=2)

    def test_build_player_scope_baseline_uses_scope_averages(self) -> None:
        players_df = pd.DataFrame(
            [
                {
                    "PLAYER_KEY": "p1",
                    "PJ": 2,
                    "PUNTOS": 24,
                    "REB OFFENSIVO": 3,
                    "REB DEFENSIVO": 7,
                    "ASISTENCIAS": 8,
                    "PERDIDAS": 4,
                    "MINUTOS JUGADOS": 50,
                    "T2 INTENTADO": 14,
                    "T3 INTENTADO": 6,
                    "TL INTENTADOS": 4,
                }
            ]
        )

        baseline = build_player_scope_baseline(players_df, "p1")

        self.assertAlmostEqual(float(baseline["PUNTOS"]), 12.0, places=2)
        self.assertAlmostEqual(float(baseline["REB"]), 5.0, places=2)
        self.assertAlmostEqual(float(baseline["AST"]), 4.0, places=2)
        self.assertAlmostEqual(float(baseline["PERDIDAS"]), 2.0, places=2)
        self.assertAlmostEqual(float(baseline["MINUTOS"]), 25.0, places=2)
        self.assertAlmostEqual(float(baseline["PLAYS"]), 12.88, places=2)

    def test_build_recent_team_games_orders_by_recency_and_derives_result(self) -> None:
        games_df = pd.DataFrame(
            [
                {"PID": 1, "JORNADA": 1, "FASE": "Liga", "EQUIPO LOCAL": "Team A", "EQUIPO RIVAL": "Rival 1", "PUNTOS": 70, "PTS_RIVAL": 65, "OFFRTG": 102.3, "DEFRTG": 98.0, "NETRTG": 4.3, "%REB": 0.51},
                {"PID": 3, "JORNADA": 3, "FASE": "Liga", "EQUIPO LOCAL": "Team A", "EQUIPO RIVAL": "Rival 3", "PUNTOS": 68, "PTS_RIVAL": 74, "OFFRTG": 96.2, "DEFRTG": 104.0, "NETRTG": -7.8, "%REB": 0.47},
                {"PID": 2, "JORNADA": 2, "FASE": "Liga", "EQUIPO LOCAL": "Team A", "EQUIPO RIVAL": "Rival 2", "PUNTOS": 75, "PTS_RIVAL": 70, "OFFRTG": 105.0, "DEFRTG": 99.5, "NETRTG": 5.5, "%REB": 0.53},
            ]
        )

        recent_df = build_recent_team_games(games_df, "Team A", last_n=2)

        self.assertEqual(int(recent_df.shape[0]), 2)
        self.assertEqual(str(recent_df.iloc[0]["RIVAL"]), "Rival 3")
        self.assertEqual(str(recent_df.iloc[0]["RESULTADO"]), "Derrota")
        self.assertEqual(str(recent_df.iloc[1]["RIVAL"]), "Rival 2")
        self.assertAlmostEqual(float(recent_df.iloc[1]["%REB"]), 53.0, places=2)

    def test_build_team_scope_baseline_uses_scope_averages(self) -> None:
        games_df = pd.DataFrame(
            [
                {"EQUIPO LOCAL": "Team A", "PUNTOS": 80, "PTS_RIVAL": 70, "OFFRTG": 110.0, "DEFRTG": 96.0, "NETRTG": 14.0, "%REB": 0.52},
                {"EQUIPO LOCAL": "Team A", "PUNTOS": 70, "PTS_RIVAL": 75, "OFFRTG": 101.0, "DEFRTG": 107.0, "NETRTG": -6.0, "%REB": 0.48},
            ]
        )

        baseline = build_team_scope_baseline(games_df, "Team A")

        self.assertAlmostEqual(float(baseline["PUNTOS +"]), 75.0, places=2)
        self.assertAlmostEqual(float(baseline["PUNTOS -"]), 72.5, places=2)
        self.assertAlmostEqual(float(baseline["OFFRTG"]), 105.5, places=2)
        self.assertAlmostEqual(float(baseline["DEFRTG"]), 101.5, places=2)
        self.assertAlmostEqual(float(baseline["NETRTG"]), 4.0, places=2)
        self.assertAlmostEqual(float(baseline["%REB"]), 50.0, places=2)

    def test_build_recent_vs_scope_summary_computes_deltas(self) -> None:
        recent_df = pd.DataFrame(
            [
                {"PUNTOS": 10, "PLAYS": 11.5},
                {"PUNTOS": 14, "PLAYS": 13.5},
            ]
        )
        baseline = {"PUNTOS": 10.0, "PLAYS": 10.0}

        summary_df = build_recent_vs_scope_summary(recent_df, baseline, ["PUNTOS", "PLAYS"]).set_index("metric")

        self.assertAlmostEqual(float(summary_df.loc["PUNTOS", "recent_avg"]), 12.0, places=2)
        self.assertAlmostEqual(float(summary_df.loc["PUNTOS", "scope_avg"]), 10.0, places=2)
        self.assertAlmostEqual(float(summary_df.loc["PUNTOS", "delta"]), 2.0, places=2)
        self.assertAlmostEqual(float(summary_df.loc["PLAYS", "delta"]), 2.5, places=2)

    def test_recent_helpers_use_available_games_when_less_than_five_and_chart_reverses_order(self) -> None:
        boxscores_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "IdPartido": 1, "JORNADA": 1, "EQUIPO RIVAL": "A", "MINUTOS JUGADOS": 20, "PUNTOS": 8, "REB OFFENSIVO": 1, "REB DEFENSIVO": 2, "ASISTENCIAS": 2, "PERDIDAS": 1, "T2 INTENTADO": 5, "T3 INTENTADO": 2, "TL INTENTADOS": 2},
                {"PLAYER_KEY": "p1", "IdPartido": 2, "JORNADA": 2, "EQUIPO RIVAL": "B", "MINUTOS JUGADOS": 22, "PUNTOS": 9, "REB OFFENSIVO": 1, "REB DEFENSIVO": 3, "ASISTENCIAS": 3, "PERDIDAS": 2, "T2 INTENTADO": 6, "T3 INTENTADO": 2, "TL INTENTADOS": 1},
            ]
        )

        recent_df = build_recent_player_games(boxscores_df, "p1")
        chart_df = build_trend_chart_frame(recent_df, "PUNTOS")

        self.assertEqual(int(recent_df.shape[0]), 2)
        self.assertEqual(str(recent_df.iloc[0]["RIVAL"]), "B")
        self.assertEqual(str(chart_df.iloc[0]["PARTIDO"]), "J1 vs A")
        self.assertEqual(str(chart_df.iloc[1]["PARTIDO"]), "J2 vs B")

    def test_build_trend_chart_frame_supports_multiple_metrics(self) -> None:
        recent_df = pd.DataFrame(
            [
                {"PARTIDO": "J2 vs B", "JORNADA": 2, "PUNTOS": 9, "REB": 4},
                {"PARTIDO": "J1 vs A", "JORNADA": 1, "PUNTOS": 8, "REB": 3},
            ]
        )

        chart_df = build_trend_chart_frame(recent_df, ["PUNTOS", "REB"])

        self.assertEqual(list(chart_df.columns), ["PARTIDO", "PUNTOS", "REB", "JORNADA", "__ORDER"])
        self.assertEqual(str(chart_df.iloc[0]["PARTIDO"]), "J1 vs A")
        self.assertAlmostEqual(float(chart_df.iloc[1]["REB"]), 4.0, places=2)

    def test_build_trend_chart_frame_flattens_nested_metric_lists(self) -> None:
        recent_df = pd.DataFrame(
            [
                {"PARTIDO": "J2 vs B", "JORNADA": 2, "PUNTOS": 9, "REB": 4},
                {"PARTIDO": "J1 vs A", "JORNADA": 1, "PUNTOS": 8, "REB": 3},
            ]
        )

        chart_df = build_trend_chart_frame(recent_df, [["PUNTOS", "REB"]])

        self.assertEqual(list(chart_df.columns), ["PARTIDO", "PUNTOS", "REB", "JORNADA", "__ORDER"])
        self.assertAlmostEqual(float(chart_df.iloc[0]["PUNTOS"]), 8.0, places=2)

    def test_build_trend_chart_frame_accepts_pandas_index_metrics(self) -> None:
        recent_df = pd.DataFrame(
            [
                {"PARTIDO": "J2 vs B", "JORNADA": 2, "PUNTOS": 9, "REB": 4},
                {"PARTIDO": "J1 vs A", "JORNADA": 1, "PUNTOS": 8, "REB": 3},
            ]
        )

        chart_df = build_trend_chart_frame(recent_df, pd.Index(["PUNTOS", "REB"]))

        self.assertEqual(list(chart_df.columns), ["PARTIDO", "PUNTOS", "REB", "JORNADA", "__ORDER"])
        self.assertAlmostEqual(float(chart_df.iloc[1]["REB"]), 4.0, places=2)

    def test_empty_inputs_return_empty_frames_and_zero_baselines(self) -> None:
        empty_player_recent = build_recent_player_games(pd.DataFrame(), "p1")
        empty_team_recent = build_recent_team_games(pd.DataFrame(), "Team A")
        player_baseline = build_player_scope_baseline(pd.DataFrame(), "p1")
        team_baseline = build_team_scope_baseline(pd.DataFrame(), "Team A")

        self.assertTrue(empty_player_recent.empty)
        self.assertTrue(empty_team_recent.empty)
        self.assertEqual(player_baseline, {column: 0.0 for column in PLAYER_TREND_METRIC_OPTIONS})
        self.assertEqual(team_baseline, {column: 0.0 for column in TEAM_TREND_METRIC_OPTIONS})


if __name__ == "__main__":
    unittest.main()
