from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from backend.api.service import AnalyticsService, ReportBundle, _empty_bundle


class ServiceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AnalyticsService("missing.sqlite")
        self.resolved_scope = {
            "selected": {
                "season": "25_26",
                "league": "Primera FEB",
                "phases": ["Liga"],
                "jornadas": [1, 2],
            }
        }

    def test_gm_cache_reuses_same_response_for_same_signature(self) -> None:
        gm_df = pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "PUNTOS": 12, "EQUIPO": "Team A"}])
        bundle = ReportBundle(
            players_df=pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "EQUIPO": "Team A", "PJ": 2}]),
            teams_df=pd.DataFrame([{"EQUIPO": "Team A", "PJ": 2}]),
            assists_df=pd.DataFrame(),
            clutch_df=pd.DataFrame(),
            clutch_lineups_df=pd.DataFrame(),
            games_df=pd.DataFrame(),
            boxscores_df=pd.DataFrame(),
        )

        with (
            patch.object(self.service, "_db_signature", return_value=("db", 1, 100)),
            patch.object(self.service, "_resolve_scope", return_value=self.resolved_scope) as resolve_mock,
            patch.object(self.service, "_load_bundle", return_value=bundle),
            patch("backend.api.service.build_gm_players_view", return_value=gm_df) as build_mock,
        ):
            first = self.service.get_gm_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2], mode="Promedios")
            second = self.service.get_gm_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2], mode="Promedios")

        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(resolve_mock.call_count, 1)
        self.assertEqual(build_mock.call_count, 1)

    def test_gm_cache_invalidates_when_db_signature_changes(self) -> None:
        gm_df = pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "PUNTOS": 12, "EQUIPO": "Team A"}])
        bundle = _empty_bundle()

        with (
            patch.object(self.service, "_db_signature", side_effect=[("db", 1, 100), ("db", 2, 100)]),
            patch.object(self.service, "_resolve_scope", return_value=self.resolved_scope) as resolve_mock,
            patch.object(self.service, "_load_bundle", return_value=bundle),
            patch("backend.api.service.build_gm_players_view", return_value=gm_df) as build_mock,
        ):
            self.service.get_gm_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2], mode="Promedios")
            self.service.get_gm_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2], mode="Promedios")

        self.assertEqual(resolve_mock.call_count, 2)
        self.assertEqual(build_mock.call_count, 2)

    def test_bundle_cache_reuses_loaded_bundle_across_endpoints(self) -> None:
        gm_df = pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "PUNTOS": 12, "EQUIPO": "Team A"}])
        dependency_df = pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "EQUIPO": "Team A", "DEPENDENCIA_SCORE": 77}])
        bundle = ReportBundle(
            players_df=pd.DataFrame([{"PLAYER_KEY": "p1", "JUGADOR": "Jugador A", "EQUIPO": "Team A", "PJ": 2}]),
            teams_df=pd.DataFrame([{"EQUIPO": "Team A", "PJ": 2}]),
            assists_df=pd.DataFrame(),
            clutch_df=pd.DataFrame(),
            clutch_lineups_df=pd.DataFrame(),
            games_df=pd.DataFrame(),
            boxscores_df=pd.DataFrame(),
        )
        fake_store = type(
            "FakeStore",
            (),
            {"load_report_bundle": lambda self, filters: bundle},
        )()

        with (
            patch.object(self.service, "_db_signature", return_value=("db", 1, 100)),
            patch.object(self.service, "_resolve_scope", return_value=self.resolved_scope),
            patch.object(self.service, "_get_store", return_value=fake_store) as store_mock,
            patch("backend.api.service.build_gm_players_view", return_value=gm_df),
            patch("backend.api.service.build_dependency_players_view", return_value=dependency_df),
        ):
            self.service.get_meta(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2])
            self.service.get_gm_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2], mode="Promedios")
            self.service.get_dependency_players(season="25_26", league="Primera FEB", phases=["Liga"], jornadas=[1, 2])

        self.assertEqual(store_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
