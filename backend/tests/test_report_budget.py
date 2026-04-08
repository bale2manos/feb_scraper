from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.api.report_budget import ReportBudgetTracker
from backend.api.security import AppSettings


def _settings(
    storage_root: Path,
    *,
    report_budget_bucket: str = "",
    report_budget_object: str = "usage/report_budget.json",
    report_budget_monthly_tokens: int = 1_000,
) -> AppSettings:
    return AppSettings(
        app_env="production",
        storage_root=storage_root,
        app_storage_mode="local",
        report_storage_mode="local",
        session_secret="secret",
        admin_password_hash="hash",
        session_ttl_hours=12,
        allowed_origins=(),
        auth_enabled=True,
        secure_cookies=True,
        frontend_dist_dir=storage_root / "frontend-dist",
        report_budget_monthly_tokens=report_budget_monthly_tokens,
        report_budget_bucket=report_budget_bucket,
        report_budget_object=report_budget_object,
        report_budget_seed_tokens={"player": 100.0, "team": 300.0, "phase": 200.0},
    )


class _FakeBlob:
    def __init__(self) -> None:
        self.payload: str | None = None

    def exists(self) -> bool:
        return self.payload is not None

    def download_as_text(self, encoding: str = "utf-8") -> str:
        if self.payload is None:
            raise FileNotFoundError("missing blob")
        return self.payload

    def upload_from_string(self, data: str, content_type: str = "application/octet-stream") -> None:
        self.payload = data


class _FakeBucket:
    def __init__(self, blob: _FakeBlob) -> None:
        self._blob = blob

    def blob(self, blob_name: str) -> _FakeBlob:
        return self._blob


class _FakeClient:
    def __init__(self, blob: _FakeBlob) -> None:
        self._blob = blob

    def bucket(self, bucket_name: str) -> _FakeBucket:
        return _FakeBucket(self._blob)


class ReportBudgetTests(unittest.TestCase):
    def test_local_tracker_records_tokens_and_estimates_remaining_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tracker = ReportBudgetTracker(_settings(Path(tmp_dir)))

            tracker.record_report("player", 120.0)
            summary = tracker.record_report("team", 280.0)

            self.assertEqual(summary["counts"]["player"], 1)
            self.assertEqual(summary["counts"]["team"], 1)
            self.assertEqual(summary["remainingTokens"], 600)
            self.assertEqual(summary["estimatedReportsRemaining"]["phase"], 3)

    def test_gcs_tracker_persists_usage_in_bucket_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            blob = _FakeBlob()
            tracker = ReportBudgetTracker(
                _settings(Path(tmp_dir), report_budget_bucket="club-bucket"),
                storage_client_factory=lambda: _FakeClient(blob),
            )

            tracker.record_report("phase", 75.0)
            summary = tracker.get_summary()

            self.assertTrue(blob.exists())
            self.assertEqual(summary["counts"]["phase"], 1)
            self.assertEqual(summary["consumedTokens"], 75.0)


if __name__ == "__main__":
    unittest.main()
