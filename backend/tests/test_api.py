from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.security import AppSettings


class FakeAnalyticsService:
    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def get_database_summary(self):
        self.calls["database_summary"] = {}
        return {
            "metrics": {"scopes": 2, "jornadas": 4, "catalogedGames": 40, "withData": 35, "pending": 3, "failed": 2},
            "scopeSummary": [],
            "jornadaSummary": [],
            "autoSyncTargets": [],
            "autoSync": {"configPath": "data/auto_sync_targets.json", "revalidateWindow": 2, "publish": True},
        }

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

    def get_player_similarity(self, **kwargs):
        self.calls["player_similarity"] = kwargs
        return {
            "scope": kwargs,
            "target": {
                "playerKey": kwargs.get("target_player_key"),
                "name": "Jugador A",
                "gamesPlayed": 12,
                "minutes": 24.5,
                "points": 13.2,
                "rebounds": 4.8,
                "assists": 3.1,
                "turnovers": 1.9,
                "usg": 22.4,
                "efg": 53.7,
                "astTo": 1.63,
            },
            "filters": {"minGames": kwargs.get("min_games"), "minMinutes": kwargs.get("min_minutes")},
            "featureWeights": {"PLAYS": 0.14},
            "candidates": [
                {
                    "playerKey": "p2",
                    "name": "Jugador B",
                    "team": "Team B",
                    "similarityScore": 88.1,
                    "reasons": ["Puntos: 14.0 vs 13.5"],
                    "differences": ["Mas rebotes: 7.0 vs 4.0"],
                }
            ],
            "players": [],
        }

    def generate_player_report(self, **kwargs):
        self.calls["player_report"] = kwargs
        return {
            "scope": kwargs,
            "selectedPlayerKey": kwargs.get("player_key"),
            "report": {
                "kind": "player",
                "fileName": "player.png",
                "fileUrl": "/reports/files/player/player.png",
                "previewUrl": "/reports/files/player/player.png",
                "mimeType": "image/png",
                "sizeBytes": 123,
                "generatedAt": "2026-04-06T10:00:00",
            },
        }

    def generate_team_report(self, **kwargs):
        self.calls["team_report"] = kwargs
        return {
            "scope": kwargs,
            "selectedTeam": kwargs.get("team"),
            "selectedPlayerKeys": kwargs.get("player_keys") or [],
            "report": {
                "kind": "team",
                "fileName": "team.pdf",
                "fileUrl": "/reports/files/team/team.pdf",
                "previewUrl": "/reports/files/team/team.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 456,
                "generatedAt": "2026-04-06T10:00:00",
            },
        }

    def generate_phase_report(self, **kwargs):
        self.calls["phase_report"] = kwargs
        return {
            "scope": kwargs,
            "selectedTeams": kwargs.get("teams") or [],
            "report": {
                "kind": "phase",
                "fileName": "phase.pdf",
                "fileUrl": "/reports/files/phase/phase.pdf",
                "previewUrl": "/reports/files/phase/phase.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 789,
                "generatedAt": "2026-04-06T10:00:00",
            },
        }

    def get_report_file_path(self, kind, filename):
        self.calls["report_file"] = {"kind": kind, "filename": filename}
        return None


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeAnalyticsService()
        self.client = TestClient(create_app(self.service, settings=_settings()))

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

    def test_database_summary_endpoint_returns_metrics(self) -> None:
        response = self.client.get("/database/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["catalogedGames"], 40)

    def test_similarity_endpoint_accepts_target_and_filters(self) -> None:
        response = self.client.get(
            "/similarity/player",
            params={
                "season": "25_26",
                "league": "Primera FEB",
                "target_player_key": "p1",
                "min_games": 7,
                "min_minutes": 15,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["player_similarity"]["target_player_key"], "p1")
        self.assertEqual(self.service.calls["player_similarity"]["min_games"], 7)
        self.assertEqual(response.json()["candidates"][0]["playerKey"], "p2")

    def test_player_report_endpoint_accepts_json_body(self) -> None:
        response = self.client.post(
            "/reports/player",
            json={
                "season": "25_26",
                "league": "Primera FEB",
                "phases": ["Liga"],
                "jornadas": [1, 2],
                "team": "Team A",
                "playerKey": "p1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["player_report"]["player_key"], "p1")
        self.assertEqual(response.json()["report"]["kind"], "player")

    def test_team_report_endpoint_accepts_player_keys_and_filters(self) -> None:
        response = self.client.post(
            "/reports/team",
            json={
                "season": "25_26",
                "league": "Primera FEB",
                "team": "Team A",
                "playerKeys": ["p1", "p2"],
                "rivalTeam": "Team B",
                "homeAway": "Local",
                "h2hHomeAway": "Visitante",
                "minGames": 4,
                "minMinutes": 80,
                "minShots": 30,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["team_report"]["player_keys"], ["p1", "p2"])
        self.assertEqual(self.service.calls["team_report"]["home_away"], "Local")

    def test_phase_report_endpoint_accepts_team_list(self) -> None:
        response = self.client.post(
            "/reports/phase",
            json={
                "season": "25_26",
                "league": "Primera FEB",
                "phases": ["Liga"],
                "teams": ["Team A", "Team B"],
                "minGames": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls["phase_report"]["teams"], ["Team A", "Team B"])

    def test_report_budget_counts_successful_report_generation(self) -> None:
        report_response = self.client.post(
            "/reports/player",
            json={
                "season": "25_26",
                "league": "Primera FEB",
                "playerKey": "p1",
            },
        )
        budget_response = self.client.get("/reports/budget")

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(budget_response.status_code, 200)
        self.assertEqual(budget_response.json()["counts"]["player"], 1)


def _settings() -> AppSettings:
    return AppSettings(
        app_env="development",
        storage_root=Path(tempfile.mkdtemp()),
        app_storage_mode="local",
        report_storage_mode="local",
        session_secret="",
        admin_password_hash="",
        session_ttl_hours=12,
        allowed_origins=(),
        auth_enabled=False,
        secure_cookies=False,
        frontend_dist_dir=Path(tempfile.gettempdir()) / "missing-frontend-dist",
        report_budget_monthly_tokens=1_000,
        report_budget_seed_tokens={"player": 100.0, "team": 300.0, "phase": 200.0},
    )


if __name__ == "__main__":
    unittest.main()
