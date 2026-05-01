from __future__ import annotations

import unittest

import pandas as pd

from utils.market_view import build_market_compare_results, build_market_opportunity_results, build_market_player_pool, filter_market_pool


class MarketViewTests(unittest.TestCase):
    def test_filter_market_pool_applies_thresholds_and_query(self) -> None:
        pool = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "JUGADOR": "Carlos", "EQUIPO": "Pinto", "LIGA": "Primera FEB", "PJ": 10, "MINUTOS JUGADOS": 22},
                {"PLAYER_KEY": "p2", "JUGADOR": "Juan", "EQUIPO": "Burgos", "LIGA": "Primera FEB", "PJ": 3, "MINUTOS JUGADOS": 9},
            ]
        )

        filtered = filter_market_pool(pool, min_games=5, min_minutes=10, query="carl")

        self.assertEqual(filtered["PLAYER_KEY"].tolist(), ["p1"])

    def test_build_market_compare_results_rejects_invalid_counts(self) -> None:
        pool = pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Carlos"}])

        with self.assertRaisesRegex(ValueError, "al menos 2"):
            build_market_compare_results(pool, ["p1"])

        with self.assertRaisesRegex(ValueError, "maximo de 6"):
            build_market_compare_results(pool, ["p1", "p2", "p3", "p4", "p5", "p6", "p7"])

    def test_percentiles_change_with_pool(self) -> None:
        gm_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "JUGADOR": "A", "EQUIPO": "T1", "PJ": 10, "MINUTOS JUGADOS": 30, "PUNTOS": 12, "REB TOTALES": 4, "ASISTENCIAS": 2, "PERDIDAS": 1, "PLAYS": 18, "USG%": 20, "TS%": 58, "eFG%": 54, "PPP": 1.1, "AST/TO": 2.0},
                {"PLAYER_KEY": "p2", "JUGADOR": "B", "EQUIPO": "T2", "PJ": 10, "MINUTOS JUGADOS": 28, "PUNTOS": 16, "REB TOTALES": 5, "ASISTENCIAS": 3, "PERDIDAS": 2, "PLAYS": 21, "USG%": 25, "TS%": 61, "eFG%": 57, "PPP": 1.2, "AST/TO": 1.5},
            ]
        )
        dependency_df = pd.DataFrame(
            [
                {"PLAYER_KEY": "p1", "%PLAYS_EQUIPO": 22, "%PUNTOS_EQUIPO": 18, "%AST_EQUIPO": 11, "%REB_EQUIPO": 9, "DEPENDENCIA_SCORE": 48, "FOCO_PRINCIPAL": "Uso ofensivo"},
                {"PLAYER_KEY": "p2", "%PLAYS_EQUIPO": 28, "%PUNTOS_EQUIPO": 24, "%AST_EQUIPO": 17, "%REB_EQUIPO": 10, "DEPENDENCIA_SCORE": 60, "FOCO_PRINCIPAL": "Anotacion"},
            ]
        )
        base_pool = build_market_player_pool(gm_df, dependency_df, "Primera FEB")
        compare_base = build_market_compare_results(base_pool, ["p1", "p2"])

        extended_gm_df = pd.concat(
            [
                gm_df,
                pd.DataFrame(
                    [
                        {
                            "PLAYER_KEY": "p3",
                            "JUGADOR": "C",
                            "EQUIPO": "T3",
                            "PJ": 10,
                            "MINUTOS JUGADOS": 35,
                            "PUNTOS": 30,
                            "REB TOTALES": 9,
                            "ASISTENCIAS": 7,
                            "PERDIDAS": 3,
                            "PLAYS": 28,
                            "USG%": 33,
                            "TS%": 67,
                            "eFG%": 62,
                            "PPP": 1.4,
                            "AST/TO": 2.3,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        extended_dependency_df = pd.concat(
            [
                dependency_df,
                pd.DataFrame(
                    [
                        {
                            "PLAYER_KEY": "p3",
                            "%PLAYS_EQUIPO": 35,
                            "%PUNTOS_EQUIPO": 31,
                            "%AST_EQUIPO": 19,
                            "%REB_EQUIPO": 15,
                            "DEPENDENCIA_SCORE": 72,
                            "FOCO_PRINCIPAL": "Anotacion",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        extended_pool = build_market_player_pool(extended_gm_df, extended_dependency_df, "Primera FEB")
        compare_extended = build_market_compare_results(extended_pool, ["p1", "p2"])

        self.assertNotEqual(compare_base["percentiles"]["p2"]["PUNTOS"], compare_extended["percentiles"]["p2"]["PUNTOS"])

    def test_opportunity_prefers_low_usage_high_efficiency_profile(self) -> None:
        pool = pd.DataFrame(
            [
                {
                    "PLAYER_KEY": "p1",
                    "JUGADOR": "Eficiente",
                    "EQUIPO": "T1",
                    "LIGA": "Primera FEB",
                    "PJ": 8,
                    "MINUTOS JUGADOS": 15,
                    "USG%": 16,
                    "TS%": 63,
                    "eFG%": 58,
                    "PPP": 1.24,
                    "AST/TO": 2.1,
                },
                {
                    "PLAYER_KEY": "p2",
                    "JUGADOR": "Mas usado",
                    "EQUIPO": "T2",
                    "LIGA": "Primera FEB",
                    "PJ": 8,
                    "MINUTOS JUGADOS": 22,
                    "USG%": 24,
                    "TS%": 55,
                    "eFG%": 49,
                    "PPP": 0.98,
                    "AST/TO": 1.1,
                },
            ]
        )

        result = build_market_opportunity_results(pool, min_games=5, max_minutes=22, max_usg=24, query="")

        self.assertEqual(result["rows"][0]["PLAYER_KEY"], "p1")
        self.assertGreater(result["rows"][0]["OpportunityScore"], result["rows"][1]["OpportunityScore"])


if __name__ == "__main__":
    unittest.main()
