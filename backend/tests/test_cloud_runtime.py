from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.api.cloud_runtime import prepare_runtime_storage
from backend.api.security import AppSettings


def _settings(
    storage_root: Path,
    *,
    app_storage_mode: str = "local",
    sqlite_bucket: str = "",
    sqlite_object: str = "snapshots/feb.sqlite",
    sqlite_local_path: Path | None = None,
) -> AppSettings:
    return AppSettings(
        app_env="production",
        storage_root=storage_root,
        app_storage_mode=app_storage_mode,
        report_storage_mode="ephemeral" if app_storage_mode == "gcs_snapshot" else "local",
        session_secret="secret",
        admin_password_hash="hash",
        session_ttl_hours=12,
        allowed_origins=(),
        auth_enabled=True,
        secure_cookies=True,
        frontend_dist_dir=storage_root / "frontend-dist",
        sqlite_bucket=sqlite_bucket,
        sqlite_object=sqlite_object,
        sqlite_local_path=(sqlite_local_path or storage_root / "feb.sqlite"),
        sqlite_snapshot_version="20260408T100000Z",
    )


class _FakeBlob:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def download_to_filename(self, filename: str) -> None:
        Path(filename).write_bytes(self.payload)


class _FakeBucket:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def blob(self, blob_name: str) -> _FakeBlob:
        return _FakeBlob(self.payload)


class _FakeClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def bucket(self, bucket_name: str) -> _FakeBucket:
        return _FakeBucket(self.payload)


class CloudRuntimeTests(unittest.TestCase):
    def test_local_mode_keeps_existing_sqlite_path_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sqlite_path = Path(tmp_dir) / "data" / "feb.sqlite"
            settings = _settings(Path(tmp_dir), sqlite_local_path=sqlite_path)

            result = prepare_runtime_storage(settings, storage_client_factory=lambda: self.fail("No deberia descargar snapshot en local."))

            self.assertEqual(result, sqlite_path.resolve())
            self.assertFalse(sqlite_path.exists())

    def test_gcs_snapshot_mode_downloads_sqlite_to_local_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sqlite_path = Path(tmp_dir) / "runtime" / "feb.sqlite"
            settings = _settings(
                Path(tmp_dir),
                app_storage_mode="gcs_snapshot",
                sqlite_bucket="club-snapshots",
                sqlite_object="snapshots/feb.sqlite",
                sqlite_local_path=sqlite_path,
            )

            result = prepare_runtime_storage(settings, storage_client_factory=lambda: _FakeClient(b"sqlite-snapshot"))

            self.assertEqual(result, sqlite_path.resolve())
            self.assertEqual(sqlite_path.read_bytes(), b"sqlite-snapshot")


if __name__ == "__main__":
    unittest.main()
