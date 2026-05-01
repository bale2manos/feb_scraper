from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response, status


PASSWORD_HASHER = PasswordHasher()
SESSION_COOKIE_NAME = "feb_session"
SESSION_VERSION = 1


@dataclass(slots=True)
class AppSettings:
    app_env: str
    storage_root: Path
    app_storage_mode: str
    report_storage_mode: str
    session_secret: str
    admin_password_hash: str
    session_ttl_hours: int
    allowed_origins: tuple[str, ...]
    auth_enabled: bool
    secure_cookies: bool
    frontend_dist_dir: Path
    sqlite_bucket: str = ""
    sqlite_object: str = "snapshots/feb.sqlite"
    sqlite_local_path: Path | None = None
    sqlite_snapshot_version: str = ""
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 300
    report_rate_limit: int = 20
    report_rate_window_seconds: int = 60

    @property
    def session_ttl_seconds(self) -> int:
        return max(self.session_ttl_hours, 1) * 3600

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def uses_gcs_snapshot(self) -> bool:
        return self.app_storage_mode == "gcs_snapshot"


@dataclass(slots=True)
class SessionData:
    sid: str
    issued_at: int


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - max(window_seconds, 1)
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max(limit, 1):
                return False
            bucket.append(now)
            return True


def load_app_settings() -> AppSettings:
    app_env = str(os.getenv("APP_ENV", "development") or "development").strip().lower()
    storage_root = Path(os.getenv("APP_STORAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
    app_storage_mode = str(os.getenv("APP_STORAGE_MODE", "local") or "local").strip().lower()
    report_storage_mode = str(os.getenv("REPORT_STORAGE_MODE", "local") or "local").strip().lower()
    session_secret = str(os.getenv("SESSION_SECRET", "")).strip()
    admin_password_hash = str(os.getenv("ADMIN_PASSWORD_HASH", "")).strip()
    session_ttl_hours = _coerce_int(os.getenv("SESSION_TTL_HOURS"), 12, minimum=1, maximum=168)
    allowed_origins = tuple(
        origin.strip()
        for origin in str(os.getenv("ALLOWED_ORIGINS", "")).split(",")
        if origin.strip()
    )
    sqlite_bucket = str(os.getenv("SQLITE_BUCKET", "")).strip()
    sqlite_object = str(os.getenv("SQLITE_OBJECT", "snapshots/feb.sqlite") or "snapshots/feb.sqlite").strip()
    sqlite_local_path = Path(os.getenv("SQLITE_LOCAL_PATH", str(storage_root / "data" / "feb.sqlite"))).resolve()
    sqlite_snapshot_version = str(os.getenv("SQLITE_SNAPSHOT_VERSION", "")).strip()
    auth_enabled = bool(session_secret and admin_password_hash)
    if app_env == "production" and not auth_enabled:
        raise RuntimeError("En produccion debes definir SESSION_SECRET y ADMIN_PASSWORD_HASH.")
    if app_storage_mode == "gcs_snapshot" and (not sqlite_bucket or not sqlite_object):
        raise RuntimeError("Con APP_STORAGE_MODE=gcs_snapshot debes definir SQLITE_BUCKET y SQLITE_OBJECT.")

    return AppSettings(
        app_env=app_env,
        storage_root=storage_root,
        app_storage_mode=app_storage_mode,
        report_storage_mode=report_storage_mode,
        session_secret=session_secret,
        admin_password_hash=admin_password_hash,
        session_ttl_hours=session_ttl_hours,
        allowed_origins=allowed_origins,
        auth_enabled=auth_enabled,
        secure_cookies=app_env == "production",
        frontend_dist_dir=Path(__file__).resolve().parents[2] / "frontend" / "dist",
        sqlite_bucket=sqlite_bucket,
        sqlite_object=sqlite_object,
        sqlite_local_path=sqlite_local_path,
        sqlite_snapshot_version=sqlite_snapshot_version,
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session_cookie(settings: AppSettings) -> str:
    issued_at = int(time.time())
    payload = {
        "sid": secrets.token_urlsafe(24),
        "iat": issued_at,
        "v": SESSION_VERSION,
    }
    encoded_payload = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(settings.session_secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    encoded_signature = _urlsafe_b64encode(signature)
    return f"{encoded_payload}.{encoded_signature}"


def read_session_cookie(cookie_value: str | None, settings: AppSettings) -> SessionData | None:
    if not settings.auth_enabled:
        return SessionData(sid="development", issued_at=int(time.time()))
    if not cookie_value or "." not in str(cookie_value):
        return None
    payload_part, signature_part = str(cookie_value).split(".", 1)
    expected_signature = hmac.new(settings.session_secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_urlsafe_b64encode(expected_signature), signature_part):
        return None
    try:
        payload = json.loads(_urlsafe_b64decode(payload_part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    issued_at = _coerce_int(payload.get("iat"), 0, minimum=0)
    if not issued_at:
        return None
    if int(time.time()) - issued_at > settings.session_ttl_seconds:
        return None
    sid = str(payload.get("sid") or "").strip()
    if not sid:
        return None
    return SessionData(sid=sid, issued_at=issued_at)


def set_session_cookie(response: Response, settings: AppSettings, cookie_value: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def clear_session_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )


def get_optional_session(request: Request, settings: AppSettings) -> SessionData | None:
    return read_session_cookie(request.cookies.get(SESSION_COOKIE_NAME), settings)


def require_authenticated_session(request: Request, settings: AppSettings) -> SessionData:
    session = get_optional_session(request, settings)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion no valida o expirada.")
    return session


def apply_security_headers(response: Response, settings: AppSettings) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


def login_rate_limit_key(request: Request) -> str:
    return f"login:{_client_ip(request)}"


def report_rate_limit_key(request: Request, session: SessionData | None) -> str:
    if session is not None:
        return f"report:{session.sid}"
    return f"report-ip:{_client_ip(request)}"


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _coerce_int(value: Any, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    numeric = max(numeric, minimum)
    if maximum is not None:
        numeric = min(numeric, maximum)
    return numeric
