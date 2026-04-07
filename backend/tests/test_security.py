from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.security import AppSettings
from backend.tests.test_api import FakeAnalyticsService


PASSWORD = "club-secret"


def _settings(
    *,
    auth_enabled: bool,
    production: bool = False,
    frontend_dist_dir: Path | None = None,
) -> AppSettings:
    return AppSettings(
        app_env="production" if production else "development",
        storage_root=Path(tempfile.gettempdir()),
        app_storage_mode="local",
        report_storage_mode="local",
        session_secret="test-session-secret" if auth_enabled else "",
        admin_password_hash=PasswordHasher().hash(PASSWORD) if auth_enabled else "",
        session_ttl_hours=12,
        allowed_origins=(),
        auth_enabled=auth_enabled,
        secure_cookies=production,
        frontend_dist_dir=frontend_dist_dir or Path(tempfile.gettempdir()) / "missing-frontend-dist",
        sqlite_bucket="",
        sqlite_object="snapshots/feb.sqlite",
        sqlite_local_path=Path(tempfile.gettempdir()) / "feb.sqlite",
        sqlite_snapshot_version="",
    )


class SecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeAnalyticsService()

    def test_protected_endpoint_requires_login_when_auth_enabled(self) -> None:
        client = TestClient(create_app(self.service, settings=_settings(auth_enabled=True)))

        response = client.get("/gm/players")

        self.assertEqual(response.status_code, 401)

    def test_login_sets_cookie_and_unlocks_protected_routes(self) -> None:
        client = TestClient(create_app(self.service, settings=_settings(auth_enabled=True)))

        login_response = client.post("/auth/login", json={"password": PASSWORD})
        protected_response = client.get("/gm/players")

        self.assertEqual(login_response.status_code, 200)
        self.assertIn("feb_session", login_response.headers.get("set-cookie", ""))
        self.assertEqual(protected_response.status_code, 200)

    def test_report_files_are_protected(self) -> None:
        client = TestClient(create_app(self.service, settings=_settings(auth_enabled=True)))

        response = client.get("/reports/files/player/player.png")

        self.assertEqual(response.status_code, 401)

    def test_production_disables_docs_and_sets_security_headers(self) -> None:
        client = TestClient(create_app(self.service, settings=_settings(auth_enabled=False, production=True)))

        docs_response = client.get("/docs")
        health_response = client.get("/health")

        self.assertEqual(docs_response.status_code, 404)
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(health_response.headers.get("x-frame-options"), "DENY")

    def test_frontend_routes_fall_back_to_index_when_dist_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dist_dir = Path(tmp_dir)
            index_file = dist_dir / "index.html"
            index_file.write_text("<!doctype html><html><body>frontend ok</body></html>", encoding="utf-8")
            client = TestClient(create_app(self.service, settings=_settings(auth_enabled=False, frontend_dist_dir=dist_dir)))

            response = client.get("/gm")

            self.assertEqual(response.status_code, 200)
            self.assertIn("frontend ok", response.text)


if __name__ == "__main__":
    unittest.main()
