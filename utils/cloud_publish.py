from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import SQLITE_DB_FILE


DEFAULT_CLOUD_PUBLISH_CONFIG_FILE = Path(os.getenv("FEB_CLOUD_PUBLISH_CONFIG", Path(__file__).resolve().parents[1] / "data" / "cloud_publish_config.json")).resolve()


@dataclass(slots=True, frozen=True)
class CloudPublishConfig:
    enabled: bool
    project_id: str
    region: str
    cloud_run_service: str
    gcs_bucket: str
    gcs_object: str
    credentials_path: Path | None
    gcloud_executable: str = "gcloud"
    snapshot_version_env_var: str = "SQLITE_SNAPSHOT_VERSION"

    @property
    def gcs_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_object}"


def load_cloud_publish_config(config_path: str | Path | None = None) -> CloudPublishConfig | None:
    path = Path(config_path or DEFAULT_CLOUD_PUBLISH_CONFIG_FILE).expanduser().resolve()
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    enabled = bool(payload.get("enabled", True))
    project_id = _read_config_value(payload, "GCP_PROJECT_ID", "projectId")
    region = _read_config_value(payload, "GCP_REGION", "region")
    cloud_run_service = _read_config_value(payload, "CLOUD_RUN_SERVICE", "cloudRunService")
    gcs_bucket = _read_config_value(payload, "GCS_BUCKET", "bucket")
    gcs_object = _read_config_value(payload, "GCS_OBJECT", "object", default="snapshots/feb.sqlite")
    credentials_raw = _read_config_value(payload, "GOOGLE_APPLICATION_CREDENTIALS", "credentialsPath")
    gcloud_executable = _read_config_value(payload, "GCLOUD_EXECUTABLE", "gcloudExecutable", default="gcloud")
    snapshot_version_env_var = _read_config_value(
        payload,
        "SQLITE_SNAPSHOT_VERSION_ENV",
        "snapshotVersionEnvVar",
        default="SQLITE_SNAPSHOT_VERSION",
    )

    if enabled:
        missing = [
            name
            for name, value in (
                ("GCP_PROJECT_ID", project_id),
                ("GCP_REGION", region),
                ("CLOUD_RUN_SERVICE", cloud_run_service),
                ("GCS_BUCKET", gcs_bucket),
            )
            if not value
        ]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"La configuracion cloud publish no es valida. Faltan: {missing_text}")

    credentials_path = Path(credentials_raw).expanduser().resolve() if credentials_raw else None
    if credentials_path is not None and not credentials_path.exists():
        raise ValueError(f"No existe GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")

    return CloudPublishConfig(
        enabled=enabled,
        project_id=project_id,
        region=region,
        cloud_run_service=cloud_run_service,
        gcs_bucket=gcs_bucket,
        gcs_object=gcs_object,
        credentials_path=credentials_path,
        gcloud_executable=gcloud_executable or "gcloud",
        snapshot_version_env_var=snapshot_version_env_var or "SQLITE_SNAPSHOT_VERSION",
    )


def publish_sqlite_snapshot_to_cloud(
    config: CloudPublishConfig,
    *,
    sqlite_path: str | Path = SQLITE_DB_FILE,
    snapshot_version: str | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    if not config.enabled:
        raise RuntimeError("La publicacion cloud esta deshabilitada en la configuracion local.")

    sqlite_file = Path(sqlite_path).resolve()
    if not sqlite_file.exists():
        raise FileNotFoundError(f"No existe la SQLite a publicar: {sqlite_file}")
    if sqlite_file.stat().st_size <= 0:
        raise RuntimeError(f"La SQLite a publicar esta vacia: {sqlite_file}")

    version = snapshot_version or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _emit(progress_callback, "info", f"Subiendo snapshot SQLite a {config.gcs_uri}")
    _run_gcloud_command(
        config,
        [
            "storage",
            "cp",
            str(sqlite_file),
            config.gcs_uri,
            "--quiet",
        ],
    )

    _emit(progress_callback, "info", f"Forzando nueva revision de Cloud Run con {config.snapshot_version_env_var}={version}")
    _run_gcloud_command(
        config,
        [
            "run",
            "services",
            "update",
            config.cloud_run_service,
            f"--region={config.region}",
            f"--update-env-vars={config.snapshot_version_env_var}={version}",
            "--quiet",
        ],
    )

    _emit(progress_callback, "success", f"Snapshot cloud publicada en {config.gcs_uri}")
    return {
        "bucket": config.gcs_bucket,
        "object": config.gcs_object,
        "gcsUri": config.gcs_uri,
        "snapshotVersion": version,
        "sqlitePath": str(sqlite_file),
        "service": config.cloud_run_service,
        "region": config.region,
    }


def _run_gcloud_command(config: CloudPublishConfig, args: list[str]) -> None:
    command = [
        config.gcloud_executable,
        f"--project={config.project_id}",
        *args,
    ]
    env = os.environ.copy()
    if config.credentials_path is not None:
        credentials = str(config.credentials_path)
        env["GOOGLE_APPLICATION_CREDENTIALS"] = credentials
        env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = credentials
    env["CLOUDSDK_CORE_PROJECT"] = config.project_id

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=600,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"No se ha encontrado gcloud ({config.gcloud_executable}). Instala Google Cloud SDK o ajusta GCLOUD_EXECUTABLE."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Fallo ejecutando {' '.join(command)}: {stderr}")


def _read_config_value(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _emit(progress_callback: Callable[[str, str], None] | None, level: str, message: str) -> None:
    if progress_callback is not None:
        progress_callback(level, message)
