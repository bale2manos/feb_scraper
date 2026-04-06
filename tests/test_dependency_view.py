from __future__ import annotations

import unittest

import pandas as pd

from storage import ReportBundle
from utils.dependency_view import build_dependency_players_view


def _empty_bundle(
    *,
    players_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    clutch_df: pd.DataFrame | None = None,
    boxscores_df: pd.DataFrame | None = None,
) -> ReportBundle:
    empty = pd.DataFrame()
    return ReportBundle(
        players_df=players_df,
        teams_df=teams_df,
        assists_df=empty.copy(),
        clutch_df=clutch_df.copy() if clutch_df is not None else empty.copy(),
        clutch_lineups_df=empty.copy(),
        games_df=empty.copy(),
        boxscores_df=boxscores_df.copy() if boxscores_df is not None else empty.copy(),
    )


class DependencyViewTests(unittest.TestCase):
    def build_main_bundle(self) -> ReportBundle:
        players_df = pd.DataFrame(
            [
                {
                    "PLAYER_KEY": "p1",
                    "JUGADOR": "Juan Perez",
                    "EQUIPO": "Team A",
                    "PJ": 2,
                    "MINUTOS JUGADOS": 60,
                    "PUNTOS": 26,
                    "ASISTENCIAS": 8,
                    "REB OFFENSIVO": 4,
                    "REB DEFENSIVO": 7,
                    "T2 INTENTADO": 20,
                    "T3 INTENTADO": 10,
                    "TL INTENTADOS": 8,
                    "PERDIDAS": 6,
                },
                {
                    "PLAYER_KEY": "p2",
                    "JUGADOR": "Luis Gomez",
                    "EQUIPO": "Team A",
                    "PJ": 2,
                    "MINUTOS JUGADOS": 40,
                    "PUNTOS": 14,
                    "ASISTENCIAS": 6,
                    "REB OFFENSIVO": 2,
                    "REB DEFENSIVO": 5,
                    "T2 INTENTADO": 10,
                    "T3 INTENTADO": 4,
                    "TL INTENTADOS": 2,
                    "PERDIDAS": 2,
                },
                {
                    "PLAYER_KEY": "p3",
                    "JUGADOR": "Ana Lopez",
                    "EQUIPO": "Team B",
                    "PJ": 2,
                    "MINUTOS JUGADOS": 55,
                    "PUNTOS": 20,
                    "ASISTENCIAS": 8,
                    "REB OFFENSIVO": 3,
                    "REB DEFENSIVO": 7,
                    "T2 INTENTADO": 16,
                    "T3 INTENTADO": 8,
                    "TL INTENTADOS": 4,
                    "PERDIDAS": 4,
                },
                {
                    "PLAYER_KEY": "p4",
                    "JUGADOR": "Marta Ruiz",
                    "EQUIPO": "Team B",
                    "PJ": 2,
                    "MINUTOS JUGADOS": 45,
                    "PUNTOS": 20,
                    "ASISTENCIAS": 4,
                    "REB OFFENSIVO": 2,
                    "REB DEFENSIVO": 8,
                    "T2 INTENTADO": 10,
                    "T3 INTENTADO": 7,
                    "TL INTENTADOS": 2,
                    "PERDIDAS": 2,
                },
            ]
        )

        teams_df = pd.DataFrame(
            [
                {
                    "EQUIPO": "Team A",
                    "PUNTOS +": 40,
                    "ASISTENCIAS": 14,
                    "REB OFFENSIVO": 6,
                    "REB DEFENSIVO": 12,
                    "PLAYS": 56.4,
                    "MINUTOS JUGADOS": 100,
                },
                {
                    "EQUIPO": "Team B",
                    "PUNTOS +": 40,
                    "ASISTENCIAS": 12,
                    "REB OFFENSIVO": 5,
                    "REB DEFENSIVO": 15,
                    "PLAYS": 50.64,
                    "MINUTOS JUGADOS": 100,
                },
            ]
        )

        clutch_df = pd.DataFrame(
            [
                {"EQUIPO": "Team A", "JUGADOR": "J. PEREZ", "MINUTOS_CLUTCH": 12},
                {"EQUIPO": "Team A", "JUGADOR": "L. GOMEZ", "MINUTOS_CLUTCH": 8},
            ]
        )

        boxscores_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "IdPartido": 1, "JORNADA": 1, "PUNTOS": 10, "T2 INTENTADO": 9, "T3 INTENTADO": 5, "TL INTENTADOS": 4, "PERDIDAS": 2},
                {"PLAYER_KEY": "p1", "IdPartido": 2, "JORNADA": 2, "PUNTOS": 16, "T2 INTENTADO": 11, "T3 INTENTADO": 5, "TL INTENTADOS": 4, "PERDIDAS": 4},
                {"PLAYER_KEY": "p2", "IdPartido": 1, "JORNADA": 1, "PUNTOS": 6, "T2 INTENTADO": 4, "T3 INTENTADO": 2, "TL INTENTADOS": 1, "PERDIDAS": 1},
                {"PLAYER_KEY": "p2", "IdPartido": 2, "JORNADA": 2, "PUNTOS": 8, "T2 INTENTADO": 6, "T3 INTENTADO": 2, "TL INTENTADOS": 1, "PERDIDAS": 1},
                {"PLAYER_KEY": "p3", "IdPartido": 1, "JORNADA": 1, "PUNTOS": 8, "T2 INTENTADO": 7, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 2},
                {"PLAYER_KEY": "p3", "IdPartido": 2, "JORNADA": 2, "PUNTOS": 12, "T2 INTENTADO": 9, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 2},
                {"PLAYER_KEY": "p4", "IdPartido": 1, "JORNADA": 1, "PUNTOS": 9, "T2 INTENTADO": 4, "T3 INTENTADO": 4, "TL INTENTADOS": 1, "PERDIDAS": 1},
                {"PLAYER_KEY": "p4", "IdPartido": 2, "JORNADA": 2, "PUNTOS": 11, "T2 INTENTADO": 6, "T3 INTENTADO": 3, "TL INTENTADOS": 1, "PERDIDAS": 1},
            ]
        )
        return _empty_bundle(players_df=players_df, teams_df=teams_df, clutch_df=clutch_df, boxscores_df=boxscores_df)

    def test_build_dependency_players_view_computes_shares_totals_and_clutch(self) -> None:
        result = build_dependency_players_view(self.build_main_bundle()).set_index("PLAYER_KEY")
        self.assertAlmostEqual(float(result.loc["p1", "REB TOTALES"]), 11.0, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "PLAYS"]), 39.52, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%PUNTOS_EQUIPO"]), 65.0, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%AST_EQUIPO"]), 57.14, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%REB_EQUIPO"]), 61.11, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%PLAYS_EQUIPO"]), 70.07, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%MIN_EQUIPO"]), 60.0, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "MINUTOS_CLUTCH"]), 12.0, places=2)
        self.assertAlmostEqual(float(result.loc["p1", "%MIN_CLUTCH_EQUIPO"]), 60.0, places=2)
        self.assertTrue(bool(result.loc["p1", "HAS_CLUTCH_DATA"]))

    def test_dependency_score_respects_expected_ordering(self) -> None:
        result = build_dependency_players_view(self.build_main_bundle()).set_index("PLAYER_KEY")
        self.assertGreater(float(result.loc["p1", "DEPENDENCIA_SCORE"]), float(result.loc["p2", "DEPENDENCIA_SCORE"]))
        self.assertGreater(float(result.loc["p3", "DEPENDENCIA_SCORE"]), float(result.loc["p4", "DEPENDENCIA_SCORE"]))

    def test_missing_clutch_reweights_without_errors(self) -> None:
        result = build_dependency_players_view(self.build_main_bundle()).set_index("PLAYER_KEY")
        self.assertFalse(bool(result.loc["p3", "HAS_CLUTCH_DATA"]))
        self.assertTrue(pd.isna(result.loc["p3", "MINUTOS_CLUTCH"]))
        self.assertTrue(pd.isna(result.loc["p3", "%MIN_CLUTCH_EQUIPO"]))
        self.assertTrue(pd.notna(result.loc["p3", "DEPENDENCIA_SCORE"]))

    def test_shares_use_team_totals_only_in_games_played(self) -> None:
        bundle = _empty_bundle(
            players_df=pd.DataFrame(
                [
                    {
                        "PLAYER_KEY": "p1",
                        "JUGADOR": "Player One",
                        "EQUIPO": "Team X",
                        "PJ": 1,
                        "MINUTOS JUGADOS": 30,
                        "PUNTOS": 10,
                        "ASISTENCIAS": 4,
                        "REB OFFENSIVO": 1,
                        "REB DEFENSIVO": 4,
                        "T2 INTENTADO": 6,
                        "T3 INTENTADO": 2,
                        "TL INTENTADOS": 2,
                        "PERDIDAS": 2,
                    }
                ]
            ),
            teams_df=pd.DataFrame(
                [
                    {
                        "EQUIPO": "Team X",
                        "PUNTOS +": 100,
                        "ASISTENCIAS": 30,
                        "REB OFFENSIVO": 15,
                        "REB DEFENSIVO": 25,
                        "PLAYS": 120,
                        "MINUTOS JUGADOS": 200,
                    }
                ]
            ),
            boxscores_df=pd.DataFrame(
                [
                    {
                        "PLAYER_KEY": "p1",
                        "IdPartido": 1,
                        "JORNADA": 1,
                        "EQUIPO LOCAL": "Team X",
                        "PUNTOS": 10,
                        "ASISTENCIAS": 4,
                        "REB OFFENSIVO": 1,
                        "REB DEFENSIVO": 4,
                        "T2 INTENTADO": 6,
                        "T3 INTENTADO": 2,
                        "TL INTENTADOS": 2,
                        "PERDIDAS": 2,
                        "MINUTOS JUGADOS": 30,
                    },
                    {
                        "PLAYER_KEY": "mate",
                        "IdPartido": 1,
                        "JORNADA": 1,
                        "EQUIPO LOCAL": "Team X",
                        "PUNTOS": 20,
                        "ASISTENCIAS": 6,
                        "REB OFFENSIVO": 2,
                        "REB DEFENSIVO": 6,
                        "T2 INTENTADO": 10,
                        "T3 INTENTADO": 4,
                        "TL INTENTADOS": 4,
                        "PERDIDAS": 2,
                        "MINUTOS JUGADOS": 20,
                    },
                    {
                        "PLAYER_KEY": "other_game",
                        "IdPartido": 2,
                        "JORNADA": 2,
                        "EQUIPO LOCAL": "Team X",
                        "PUNTOS": 70,
                        "ASISTENCIAS": 20,
                        "REB OFFENSIVO": 12,
                        "REB DEFENSIVO": 15,
                        "T2 INTENTADO": 25,
                        "T3 INTENTADO": 10,
                        "TL INTENTADOS": 8,
                        "PERDIDAS": 5,
                        "MINUTOS JUGADOS": 40,
                    },
                ]
            ),
        )

        result = build_dependency_players_view(bundle).iloc[0]
        self.assertAlmostEqual(float(result["%PUNTOS_EQUIPO"]), 33.33, places=2)
        self.assertAlmostEqual(float(result["%AST_EQUIPO"]), 40.0, places=2)
        self.assertAlmostEqual(float(result["%REB_EQUIPO"]), 38.46, places=2)
        self.assertAlmostEqual(float(result["%MIN_EQUIPO"]), 60.0, places=2)

    def test_zero_denominators_return_zero_shares(self) -> None:
        bundle = _empty_bundle(
            players_df=pd.DataFrame(
                [
                    {
                        "PLAYER_KEY": "zero",
                        "JUGADOR": "Zero Player",
                        "EQUIPO": "Zero Team",
                        "PJ": 1,
                        "MINUTOS JUGADOS": 10,
                        "PUNTOS": 5,
                        "ASISTENCIAS": 2,
                        "REB OFFENSIVO": 1,
                        "REB DEFENSIVO": 2,
                        "T2 INTENTADO": 3,
                        "T3 INTENTADO": 1,
                        "TL INTENTADOS": 2,
                        "PERDIDAS": 1,
                    }
                ]
            ),
            teams_df=pd.DataFrame(
                [
                    {
                        "EQUIPO": "Zero Team",
                        "PUNTOS +": 0,
                        "ASISTENCIAS": 0,
                        "REB OFFENSIVO": 0,
                        "REB DEFENSIVO": 0,
                        "PLAYS": 0,
                        "MINUTOS JUGADOS": 0,
                    }
                ]
            ),
            boxscores_df=pd.DataFrame(
                [{"PLAYER_KEY": "zero", "PUNTOS": 5, "T2 INTENTADO": 3, "T3 INTENTADO": 1, "TL INTENTADOS": 2, "PERDIDAS": 1}]
            ),
        )

        result = build_dependency_players_view(bundle).iloc[0]
        self.assertEqual(float(result["%PUNTOS_EQUIPO"]), 0.0)
        self.assertEqual(float(result["%AST_EQUIPO"]), 0.0)
        self.assertEqual(float(result["%REB_EQUIPO"]), 0.0)
        self.assertEqual(float(result["%PLAYS_EQUIPO"]), 0.0)
        self.assertEqual(float(result["%MIN_EQUIPO"]), 0.0)

    def test_focus_and_band_assignment(self) -> None:
        main_result = build_dependency_players_view(self.build_main_bundle()).set_index("PLAYER_KEY")
        self.assertEqual(str(main_result.loc["p1", "FOCO_PRINCIPAL"]), "Uso ofensivo")

        bundle = _empty_bundle(
            players_df=pd.DataFrame(
                [
                    {
                        "PLAYER_KEY": "solo",
                        "JUGADOR": "Solo Player",
                        "EQUIPO": "Solo Team",
                        "PJ": 1,
                        "MINUTOS JUGADOS": 30,
                        "PUNTOS": 18,
                        "ASISTENCIAS": 6,
                        "REB OFFENSIVO": 2,
                        "REB DEFENSIVO": 6,
                        "T2 INTENTADO": 10,
                        "T3 INTENTADO": 4,
                        "TL INTENTADOS": 4,
                        "PERDIDAS": 2,
                    }
                ]
            ),
            teams_df=pd.DataFrame(
                [
                    {
                        "EQUIPO": "Solo Team",
                        "PUNTOS +": 18,
                        "ASISTENCIAS": 6,
                        "REB OFFENSIVO": 2,
                        "REB DEFENSIVO": 6,
                        "PLAYS": 17.76,
                        "MINUTOS JUGADOS": 30,
                    }
                ]
            ),
            boxscores_df=pd.DataFrame(
                [{"PLAYER_KEY": "solo", "PUNTOS": 18, "T2 INTENTADO": 10, "T3 INTENTADO": 4, "TL INTENTADOS": 4, "PERDIDAS": 2}]
            ),
        )

        result = build_dependency_players_view(bundle).iloc[0]
        self.assertEqual(str(result["DEPENDENCIA_RIESGO"]), "Critica")

    def test_single_game_std_is_zero(self) -> None:
        bundle = _empty_bundle(
            players_df=pd.DataFrame(
                [
                    {
                        "PLAYER_KEY": "single",
                        "JUGADOR": "Single Game",
                        "EQUIPO": "One Team",
                        "PJ": 1,
                        "MINUTOS JUGADOS": 18,
                        "PUNTOS": 7,
                        "ASISTENCIAS": 3,
                        "REB OFFENSIVO": 1,
                        "REB DEFENSIVO": 4,
                        "T2 INTENTADO": 5,
                        "T3 INTENTADO": 2,
                        "TL INTENTADOS": 2,
                        "PERDIDAS": 1,
                    }
                ]
            ),
            teams_df=pd.DataFrame(
                [
                    {
                        "EQUIPO": "One Team",
                        "PUNTOS +": 7,
                        "ASISTENCIAS": 3,
                        "REB OFFENSIVO": 1,
                        "REB DEFENSIVO": 4,
                        "PLAYS": 8.88,
                        "MINUTOS JUGADOS": 18,
                    }
                ]
            ),
            boxscores_df=pd.DataFrame(
                [{"PLAYER_KEY": "single", "PUNTOS": 7, "T2 INTENTADO": 5, "T3 INTENTADO": 2, "TL INTENTADOS": 2, "PERDIDAS": 1}]
            ),
        )

        result = build_dependency_players_view(bundle).iloc[0]
        self.assertEqual(float(result["STD_PUNTOS"]), 0.0)
        self.assertEqual(float(result["STD_PLAYS"]), 0.0)


if __name__ == "__main__":
    unittest.main()
