from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from .security import AppSettings


class _BlobLike(Protocol):
    def download_to_filename(self, filename: str) -> None: ...


class _BucketLike(Protocol):
    def blob(self, blob_name: str) -> _BlobLike: ...


class _StorageClientLike(Protocol):
    def bucket(self, bucket_name: str) -> _BucketLike: ...


StorageClientFactory = Callable[[], _StorageClientLike]


def prepare_runtime_storage(settings: AppSettings, *, storage_client_factory: StorageClientFactory | None = None) -> Path:
    sqlite_local_path = Path(settings.sqlite_local_path or (settings.storage_root / "data" / "feb.sqlite")).resolve()
    sqlite_local_path.parent.mkdir(parents=True, exist_ok=True)
    settings.storage_root.mkdir(parents=True, exist_ok=True)

    if not settings.uses_gcs_snapshot:
        return sqlite_local_path

    if not settings.sqlite_bucket or not settings.sqlite_object:
        raise RuntimeError("La configuracion cloud read-only requiere SQLITE_BUCKET y SQLITE_OBJECT.")

    temp_path = sqlite_local_path.with_suffix(f"{sqlite_local_path.suffix}.download")
    if temp_path.exists():
        temp_path.unlink()

    client = storage_client_factory() if storage_client_factory is not None else _build_storage_client()
    bucket = client.bucket(settings.sqlite_bucket)
    blob = bucket.blob(settings.sqlite_object)

    try:
        blob.download_to_filename(str(temp_path))
    except Exception as exc:  # pragma: no cover - exercised via tests with fake client
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(
            f"No se ha podido descargar la snapshot SQLite desde gs://{settings.sqlite_bucket}/{settings.sqlite_object}: {exc}"
        ) from exc

    temp_path.replace(sqlite_local_path)
    return sqlite_local_path


def _build_storage_client():
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError(
            "Falta la dependencia google-cloud-storage. Instala backend/requirements.txt para usar APP_STORAGE_MODE=gcs_snapshot."
        ) from exc
    return storage.Client()
