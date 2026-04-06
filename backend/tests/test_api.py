from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.api.main import create_app


class FakeAnalyticsService:
    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def get_meta(self, **kwargs):
        self.calls["meta"] = kwargs
        return {
            "seasons": ["25_26"],
            "leagues": ["Primera FEB"],
            "phases": ["Liga"],
            "jornadas": [1, 2],
            "selected": kwargs,
            "teams": [],
            "players": [],
        }

    def get_gm_players(self, **kwargs):
        self.calls["gm"] = kwargs
        return {"scope": kwargs, "columns": ["JUGADOR"], "rows": [{"JUGADOR": "Jugador A"}], "players": []}

    def get_dependency_players(self, **kwargs):
        self.calls["dependency_players"] = kwargs
        return {"scope": kwargs, "rows": [], "teams": [], "players": []}

    def get_dependency_team_summary(self, **kwargs):
        self.calls["dependency_team_summary"] = kwargs
        return {"scope": kwargs, "selectedTeam": kwargs.get("team"), "metrics": {}, "detail": None, "tableRows": []}

    def get_player_trends(self, **kwargs):
        self.calls["player_trends"] = kwargs
        return {
            "scope": kwargs,
            "selectedPlayerKey": kwargs.get("player_key"),
            "selectedMetrics": kwargs.get("metrics") or [],
            "window": kwargs.get("window"),
            "recentGames": [],
            "chartRows": [],
            "summaryRows": [],
            "players": [],
        }

    def get_team_trends(self, **kwargs):
        self.calls["team_trends"] = kwargs
        return {
            "scope": kwargs,
            "selectedTeam": kwargs.get("team"),
            "selectedMetrics": kwargs.get("metrics") or [],
            "window": kwargs.get("window"),
            "recentGames": [],
            "chartRows": [],
            "summaryRows": [],
            "teams": [],
        }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeAnalyticsService()
        self.client = TestClient(create_app(self.service))

    def test_meta_endpoint_parses_repeated_filters(self) -> None:
        response = self.client.get(
            "/meta/scopes",
            params=[
                ("season", "25_26"),
                ("league", "Primera FEB"),
                ("phases", "Liga"),
                ("phases", "Playoff"),
                ("jornadas", "1"),
                ("jornadas", "2"),
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["meta"]["phases"], ["Liga", "Playoff"])
        self.assertEqual(self.service.calls["meta"]["jornadas"], [1, 2])

    def test_dependency_endpoint_returns_empty_payload_without_errors(self) -> None:
        response = self.client.get("/dependency/players")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"], [])

    def test_player_trends_endpoint_accepts_multiple_metrics_and_window(self) -> None:
        response = self.client.get(
            "/trends/player",
            params=[
                ("player_key", "p1"),
                ("window", "7"),
                ("metrics", "PUNTOS"),
                ("metrics", "REB"),
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["player_trends"]["metrics"], ["PUNTOS", "REB"])
        self.assertEqual(self.service.calls["player_trends"]["window"], 7)

    def test_team_trends_endpoint_accepts_team_name(self) -> None:
        response = self.client.get("/trends/team", params={"team": "Team A", "window": 3})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedTeam"], "Team A")


if __name__ == "__main__":
    unittest.main()
