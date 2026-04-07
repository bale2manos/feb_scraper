from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils.cloud_publish import CloudPublishConfig, load_cloud_publish_config, publish_sqlite_snapshot_to_cloud


class CloudPublishTests(unittest.TestCase):
    def test_load_cloud_publish_config_supports_uppercase_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            credentials_path = Path(tmp_dir) / "service-account.json"
            credentials_path.write_text("{}", encoding="utf-8")
            config_path = Path(tmp_dir) / "cloud_publish_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "GCP_PROJECT_ID": "club-project",
                        "GCP_REGION": "us-central1",
                        "CLOUD_RUN_SERVICE": "feb-analytics",
                        "GCS_BUCKET": "club-snapshots",
                        "GCS_OBJECT": "snapshots/feb.sqlite",
                        "GOOGLE_APPLICATION_CREDENTIALS": str(credentials_path),
                    }
                ),
                encoding="utf-8",
            )

            config = load_cloud_publish_config(config_path)

            self.assertIsNotNone(config)
            self.assertTrue(config.enabled)
            self.assertEqual(config.project_id, "club-project")
            self.assertEqual(config.gcs_uri, "gs://club-snapshots/snapshots/feb.sqlite")

    def test_load_cloud_publish_config_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = load_cloud_publish_config(Path(tmp_dir) / "missing.json")

            self.assertIsNone(config)

    @patch("utils.cloud_publish.subprocess.run")
    def test_publish_sqlite_snapshot_uploads_db_and_updates_cloud_run(self, run_mock) -> None:
        run_mock.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp_dir:
            sqlite_path = Path(tmp_dir) / "feb.sqlite"
            sqlite_path.write_bytes(b"sqlite-bytes")
            credentials_path = Path(tmp_dir) / "service-account.json"
            credentials_path.write_text("{}", encoding="utf-8")
            config = CloudPublishConfig(
                enabled=True,
                project_id="club-project",
                region="us-central1",
                cloud_run_service="feb-analytics",
                gcs_bucket="club-snapshots",
                gcs_object="snapshots/feb.sqlite",
                credentials_path=credentials_path,
            )

            result = publish_sqlite_snapshot_to_cloud(
                config,
                sqlite_path=sqlite_path,
                snapshot_version="20260408T101500Z",
            )

            self.assertEqual(result["snapshotVersion"], "20260408T101500Z")
            self.assertEqual(run_mock.call_count, 2)

            upload_command = run_mock.call_args_list[0].args[0]
            update_command = run_mock.call_args_list[1].args[0]
            upload_env = run_mock.call_args_list[0].kwargs["env"]

            self.assertIn("storage", upload_command)
            self.assertIn("cp", upload_command)
            self.assertIn(str(sqlite_path), upload_command)
            self.assertIn("gs://club-snapshots/snapshots/feb.sqlite", upload_command)
            self.assertIn("run", update_command)
            self.assertIn("services", update_command)
            self.assertIn("update", update_command)
            self.assertIn("--update-env-vars=SQLITE_SNAPSHOT_VERSION=20260408T101500Z", update_command)
            self.assertEqual(upload_env["GOOGLE_APPLICATION_CREDENTIALS"], str(credentials_path))
            self.assertEqual(upload_env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"], str(credentials_path))


if __name__ == "__main__":
    unittest.main()
