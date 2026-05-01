from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from math import floor
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from .security import AppSettings

DEFAULT_MONTHLY_TOKENS = 90_000
DEFAULT_WARNING_THRESHOLD_TOKENS = 70_000
DEFAULT_HARD_LIMIT_TOKENS = 80_000
DEFAULT_KIND_TOKENS = {
    "player": 110.0,
    "team": 223.0,
    "phase": 55.0,
}
DEFAULT_TIMEZONE = "Europe/Madrid"


class _BlobLike(Protocol):
    def exists(self) -> bool: ...

    def download_as_text(self, encoding: str = "utf-8") -> str: ...

    def upload_from_string(self, data: str, content_type: str = "application/octet-stream") -> None: ...


class _BucketLike(Protocol):
    def blob(self, blob_name: str) -> _BlobLike: ...


class _StorageClientLike(Protocol):
    def bucket(self, bucket_name: str) -> _BucketLike: ...


StorageClientFactory = Callable[[], _StorageClientLike]


@dataclass(slots=True)
class ReportBudgetTracker:
    settings: AppSettings
    storage_client_factory: StorageClientFactory | None = None
    _lock: Lock = field(init=False, repr=False)
    _last_warning: str | None = field(init=False, repr=False, default=None)
    _timezone: ZoneInfo = field(init=False, repr=False)
    _budget_file: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lock = Lock()
        self._timezone = ZoneInfo(self.settings.report_budget_timezone or DEFAULT_TIMEZONE)
        self._budget_file = (self.settings.storage_root / "output" / "report_budget_usage.json").resolve()

    def get_summary(self) -> dict[str, object]:
        with self._lock:
            try:
                payload = self._load_payload()
            except Exception as exc:  # pragma: no cover - defensive path
                self._last_warning = f"No se ha podido leer el contador mensual: {exc}"
                payload = self._empty_payload()
            return self._build_summary(payload)

    def record_report(self, kind: str, elapsed_seconds: float) -> dict[str, object]:
        normalized_kind = str(kind).strip().lower()
        if normalized_kind not in DEFAULT_KIND_TOKENS:
            raise ValueError(f"Tipo de informe no soportado para presupuesto: {kind}")

        tokens = max(float(elapsed_seconds), 0.0)
        with self._lock:
            payload = self._load_payload()
            month_key = self._current_month_key()
            month_payload = payload.setdefault("months", {}).setdefault(month_key, self._empty_month_payload())
            counts = month_payload.setdefault("counts", self._empty_count_payload())
            totals = month_payload.setdefault("tokens", self._empty_token_payload())

            counts[normalized_kind] = int(counts.get(normalized_kind, 0)) + 1
            totals[normalized_kind] = float(totals.get(normalized_kind, 0.0)) + tokens
            month_payload["lastUpdated"] = self._now().isoformat(timespec="seconds")

            try:
                self._save_payload(payload)
                self._last_warning = None
            except Exception as exc:
                self._last_warning = f"No se ha podido persistir el contador mensual: {exc}"

            return self._build_summary(payload)

    def _build_summary(self, payload: dict[str, object]) -> dict[str, object]:
        month_key = self._current_month_key()
        month_payload = dict((payload.get("months") or {}).get(month_key) or {})
        counts = {kind: int(dict(month_payload.get("counts") or {}).get(kind, 0)) for kind in DEFAULT_KIND_TOKENS}
        totals = {kind: float(dict(month_payload.get("tokens") or {}).get(kind, 0.0)) for kind in DEFAULT_KIND_TOKENS}
        seed_tokens = dict(self.settings.report_budget_seed_tokens or {})
        averages = {
            kind: (totals[kind] / counts[kind]) if counts[kind] > 0 else float(seed_tokens.get(kind, DEFAULT_KIND_TOKENS[kind]))
            for kind in DEFAULT_KIND_TOKENS
        }

        monthly_tokens = max(int(self.settings.report_budget_monthly_tokens), 1)
        warning_threshold = min(DEFAULT_WARNING_THRESHOLD_TOKENS, monthly_tokens)
        hard_limit = min(DEFAULT_HARD_LIMIT_TOKENS, monthly_tokens)
        consumed_tokens = sum(totals.values())
        remaining_tokens = max(float(monthly_tokens) - consumed_tokens, 0.0)
        estimated_remaining = {
            kind: max(floor(remaining_tokens / averages[kind]), 0) if averages[kind] > 0 else 0
            for kind in DEFAULT_KIND_TOKENS
        }
        now = self._now()
        is_warning = consumed_tokens >= warning_threshold
        is_blocked = consumed_tokens >= hard_limit
        limit_message = None
        if is_blocked:
            limit_message = (
                f"Se ha alcanzado el limite mensual de {hard_limit:,} tokens. "
                "Hemos bloqueado nuevas generaciones para guardar margen hasta el proximo mes."
            ).replace(",", ".")
        elif is_warning:
            limit_message = (
                f"Has superado {warning_threshold:,} tokens este mes. "
                f"Aun puedes generar informes, pero al llegar a {hard_limit:,} se bloquearan."
            ).replace(",", ".")

        return {
            "month": month_key,
            "monthIso": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "monthlyTokens": monthly_tokens,
            "consumedTokens": round(consumed_tokens, 1),
            "remainingTokens": max(int(remaining_tokens), 0),
            "percentRemaining": round((remaining_tokens / monthly_tokens) * 100.0, 1),
            "counts": counts,
            "averageTokens": {kind: round(value, 1) for kind, value in averages.items()},
            "estimatedReportsRemaining": estimated_remaining,
            "warningThresholdTokens": warning_threshold,
            "hardLimitTokens": hard_limit,
            "isWarning": is_warning,
            "isBlocked": is_blocked,
            "message": limit_message,
            "trackingMode": self._tracking_mode(),
            "trackingEnabled": True,
            "warning": self._last_warning,
            "lastUpdated": month_payload.get("lastUpdated"),
        }

    def _load_payload(self) -> dict[str, object]:
        if self._uses_gcs_budget_store():
            return self._load_payload_from_gcs()

        self._budget_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._budget_file.exists():
            return self._empty_payload()
        return json.loads(self._budget_file.read_text(encoding="utf-8"))

    def _save_payload(self, payload: dict[str, object]) -> None:
        if self._uses_gcs_budget_store():
            self._save_payload_to_gcs(payload)
            return

        self._budget_file.parent.mkdir(parents=True, exist_ok=True)
        self._budget_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_payload_from_gcs(self) -> dict[str, object]:
        client = self._build_storage_client()
        blob = client.bucket(self.settings.report_budget_bucket).blob(self.settings.report_budget_object)
        if not blob.exists():
            return self._empty_payload()
        raw = blob.download_as_text(encoding="utf-8")
        return json.loads(raw)

    def _save_payload_to_gcs(self, payload: dict[str, object]) -> None:
        client = self._build_storage_client()
        blob = client.bucket(self.settings.report_budget_bucket).blob(self.settings.report_budget_object)
        blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")

    def _build_storage_client(self):
        if self.storage_client_factory is not None:
            return self.storage_client_factory()
        try:
            from google.cloud import storage
        except ImportError as exc:  # pragma: no cover - depends on optional runtime package
            raise RuntimeError(
                "Falta la dependencia google-cloud-storage para persistir el contador mensual en GCS."
            ) from exc
        return storage.Client()

    def _uses_gcs_budget_store(self) -> bool:
        return bool(self.settings.report_budget_bucket and self.settings.report_budget_object)

    def _tracking_mode(self) -> str:
        return "gcs_json" if self._uses_gcs_budget_store() else "local_json"

    def _current_month_key(self) -> str:
        return self._now().strftime("%Y-%m")

    def _now(self) -> datetime:
        return datetime.now(self._timezone)

    @staticmethod
    def _empty_payload() -> dict[str, object]:
        return {
            "version": 1,
            "months": {},
        }

    @staticmethod
    def _empty_month_payload() -> dict[str, object]:
        return {
            "counts": ReportBudgetTracker._empty_count_payload(),
            "tokens": ReportBudgetTracker._empty_token_payload(),
            "lastUpdated": None,
        }

    @staticmethod
    def _empty_count_payload() -> dict[str, int]:
        return {kind: 0 for kind in DEFAULT_KIND_TOKENS}

    @staticmethod
    def _empty_token_payload() -> dict[str, float]:
        return {kind: 0.0 for kind in DEFAULT_KIND_TOKENS}
