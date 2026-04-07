from __future__ import annotations

import unittest

import pandas as pd

from storage import ReportBundle
from utils.dependency_view import build_dependency_players_view
from utils.similarity_view import build_player_similarity_results, build_similarity_player_pool
from backend.api.gm_view import build_gm_players_view


def _bundle(players_df: pd.DataFrame, teams_df: pd.DataFrame, boxscores_df: pd.DataFrame | None = None) -> ReportBundle:
    empty = pd.DataFrame()
    return ReportBundle(
        players_df=players_df,
        teams_df=teams_df,
        assists_df=empty.copy(),
        clutch_df=empty.copy(),
        clutch_lineups_df=empty.copy(),
        games_df=empty.copy(),
        boxscores_df=boxscores_df.copy() if boxscores_df is not None else empty.copy(),
    )


class SimilarityViewTests(unittest.TestCase):
    def build_main_pool(self) -> pd.DataFrame:
        players_df = pd.DataFrame(
            [
                {
                    "PLAYER_KEY": "target",
                    "DORSAL": "7",
                    "JUGADOR": "Target Player",
                    "EQUIPO": "Team A",
                    "PJ": 10,
                    "MINUTOS JUGADOS": 260,
                    "PUNTOS": 130,
                    "REB OFFENSIVO": 18,
                    "REB DEFENSIVO": 42,
                    "ASISTENCIAS": 52,
                    "PERDIDAS": 20,
                    "T2 CONVERTIDO": 40,
                    "T2 INTENTADO": 80,
                    "T3 CONVERTIDO": 18,
                    "T3 INTENTADO": 45,
                    "TL CONVERTIDOS": 14,
                    "TL INTENTADOS": 18,
                },
                {
                    "PLAYER_KEY": "near",
                    "DORSAL": "9",
                    "JUGADOR": "Near Match",
                    "EQUIPO": "Team B",
                    "PJ": 10,
                    "MINUTOS JUGADOS": 255,
                    "PUNTOS": 126,
                    "REB OFFENSIVO": 16,
                    "REB DEFENSIVO": 40,
                    "ASISTENCIAS": 50,
                    "PERDIDAS": 18,
                    "T2 CONVERTIDO": 39,
                    "T2 INTENTADO": 78,
                    "T3 CONVERTIDO": 17,
                    "T3 INTENTADO": 44,
                    "TL CONVERTIDOS": 13,
                    "TL INTENTADOS": 17,
                },
                {
                    "PLAYER_KEY": "far",
                    "DORSAL": "4",
                    "JUGADOR": "Far Match",
                    "EQUIPO": "Team C",
                    "PJ": 10,
                    "MINUTOS JUGADOS": 180,
                    "PUNTOS": 70,
                    "REB OFFENSIVO": 30,
                    "REB DEFENSIVO": 55,
                    "ASISTENCIAS": 14,
                    "PERDIDAS": 28,
                    "T2 CONVERTIDO": 25,
                    "T2 INTENTADO": 65,
                    "T3 CONVERTIDO": 4,
                    "T3 INTENTADO": 20,
                    "TL CONVERTIDOS": 16,
                    "TL INTENTADOS": 24,
                },
                {
                    "PLAYER_KEY": "small",
                    "DORSAL": "12",
                    "JUGADOR": "Small Sample",
                    "EQUIPO": "Team D",
                    "PJ": 3,
                    "MINUTOS JUGADOS": 24,
                    "PUNTOS": 12,
                    "REB OFFENSIVO": 1,
                    "REB DEFENSIVO": 4,
                    "ASISTENCIAS": 3,
                    "PERDIDAS": 2,
                    "T2 CONVERTIDO": 4,
                    "T2 INTENTADO": 8,
                    "T3 CONVERTIDO": 1,
                    "T3 INTENTADO": 3,
                    "TL CONVERTIDOS": 1,
                    "TL INTENTADOS": 2,
                },
            ]
        )
        teams_df = pd.DataFrame(
            [
                {"EQUIPO": "Team A", "PJ": 10, "MINUTOS JUGADOS": 200, "PUNTOS +": 700, "ASISTENCIAS": 180, "REB OFFENSIVO": 90, "REB DEFENSIVO": 220, "PLAYS": 560, "T2 INTENTADO": 430, "T3 INTENTADO": 180, "TL INTENTADOS": 120, "PERDIDAS": 78},
                {"EQUIPO": "Team B", "PJ": 10, "MINUTOS JUGADOS": 200, "PUNTOS +": 690, "ASISTENCIAS": 176, "REB OFFENSIVO": 86, "REB DEFENSIVO": 214, "PLAYS": 548, "T2 INTENTADO": 420, "T3 INTENTADO": 176, "TL INTENTADOS": 118, "PERDIDAS": 76},
                {"EQUIPO": "Team C", "PJ": 10, "MINUTOS JUGADOS": 200, "PUNTOS +": 640, "ASISTENCIAS": 120, "REB OFFENSIVO": 110, "REB DEFENSIVO": 240, "PLAYS": 530, "T2 INTENTADO": 410, "T3 INTENTADO": 150, "TL INTENTADOS": 110, "PERDIDAS": 72},
                {"EQUIPO": "Team D", "PJ": 3, "MINUTOS JUGADOS": 200, "PUNTOS +": 210, "ASISTENCIAS": 60, "REB OFFENSIVO": 30, "REB DEFENSIVO": 70, "PLAYS": 170, "T2 INTENTADO": 130, "T3 INTENTADO": 55, "TL INTENTADOS": 34, "PERDIDAS": 20},
            ]
        )
        boxscores_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "target", "IdPartido": 1, "EQUIPO LOCAL": "Team A", "PUNTOS": 13, "ASISTENCIAS": 5, "REB OFFENSIVO": 2, "REB DEFENSIVO": 4, "T2 INTENTADO": 8, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 2, "MINUTOS JUGADOS": 26},
                {"PLAYER_KEY": "mate_a", "IdPartido": 1, "EQUIPO LOCAL": "Team A", "PUNTOS": 57, "ASISTENCIAS": 13, "REB OFFENSIVO": 7, "REB DEFENSIVO": 18, "T2 INTENTADO": 35, "T3 INTENTADO": 12, "TL INTENTADOS": 10, "PERDIDAS": 6, "MINUTOS JUGADOS": 64},
                {"PLAYER_KEY": "near", "IdPartido": 1, "EQUIPO LOCAL": "Team B", "PUNTOS": 13, "ASISTENCIAS": 5, "REB OFFENSIVO": 2, "REB DEFENSIVO": 4, "T2 INTENTADO": 8, "T3 INTENTADO": 4, "TL INTENTADOS": 2, "PERDIDAS": 2, "MINUTOS JUGADOS": 25.5},
                {"PLAYER_KEY": "mate_b", "IdPartido": 1, "EQUIPO LOCAL": "Team B", "PUNTOS": 56, "ASISTENCIAS": 12, "REB OFFENSIVO": 6, "REB DEFENSIVO": 17, "T2 INTENTADO": 34, "T3 INTENTADO": 12, "TL INTENTADOS": 9, "PERDIDAS": 6, "MINUTOS JUGADOS": 66},
                {"PLAYER_KEY": "far", "IdPartido": 1, "EQUIPO LOCAL": "Team C", "PUNTOS": 7, "ASISTENCIAS": 1, "REB OFFENSIVO": 3, "REB DEFENSIVO": 5, "T2 INTENTADO": 6, "T3 INTENTADO": 2, "TL INTENTADOS": 3, "PERDIDAS": 3, "MINUTOS JUGADOS": 18},
                {"PLAYER_KEY": "mate_c", "IdPartido": 1, "EQUIPO LOCAL": "Team C", "PUNTOS": 57, "ASISTENCIAS": 11, "REB OFFENSIVO": 8, "REB DEFENSIVO": 19, "T2 INTENTADO": 35, "T3 INTENTADO": 11, "TL INTENTADOS": 8, "PERDIDAS": 5, "MINUTOS JUGADOS": 70},
            ]
        )
        bundle = _bundle(players_df=players_df, teams_df=teams_df, boxscores_df=boxscores_df)
        gm_df = build_gm_players_view(bundle.players_df, "Promedios", bundle.teams_df)
        dependency_df = build_dependency_players_view(bundle)
        return build_similarity_player_pool(bundle, gm_df, dependency_df)

    def test_similarity_ranks_nearest_candidate_first(self) -> None:
        pool_df = self.build_main_pool()

        result = build_player_similarity_results(pool_df, "target", min_games=5, min_minutes=10, limit=10)

        self.assertEqual(result["target"]["PLAYER_KEY"], "target")
        self.assertEqual(result["candidates"][0]["PLAYER_KEY"], "near")
        self.assertGreater(float(result["candidates"][0]["similarityScore"]), float(result["candidates"][1]["similarityScore"]))

    def test_similarity_excludes_target_and_respects_filters(self) -> None:
        pool_df = self.build_main_pool()

        result = build_player_similarity_results(pool_df, "target", min_games=5, min_minutes=10, limit=10)
        candidate_keys = [row["PLAYER_KEY"] for row in result["candidates"]]

        self.assertNotIn("target", candidate_keys)
        self.assertNotIn("small", candidate_keys)

    def test_similarity_explanations_include_reasons_and_differences(self) -> None:
        pool_df = self.build_main_pool()

        result = build_player_similarity_results(pool_df, "target", min_games=5, min_minutes=10, limit=10)
        candidate = result["candidates"][0]

        self.assertEqual(len(candidate["reasons"]), 3)
        self.assertEqual(len(candidate["differences"]), 2)
        self.assertTrue(all(isinstance(text, str) and text for text in candidate["reasons"]))
        self.assertTrue(all(isinstance(text, str) and text for text in candidate["differences"]))


if __name__ == "__main__":
    unittest.main()
