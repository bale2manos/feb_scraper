from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import HTTPException, Request, Response, status

from .security import AppSettings

try:
    from google.auth.transport import requests as google_auth_requests
    from google.oauth2 import id_token
except ImportError:  # pragma: no cover - exercised only when dependencies are incomplete.
    google_auth_requests = None
    id_token = None


GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OIDC_STATE_COOKIE_NAME = "feb_oidc_state"
OIDC_STATE_TTL_SECONDS = 600


def build_google_authorization_url(request: Request, settings: AppSettings) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    redirect_uri = get_redirect_uri(request, settings)
    params = {
        "client_id": settings.google_oidc_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    if settings.google_oidc_hosted_domain:
        params["hd"] = settings.google_oidc_hosted_domain
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}", create_oidc_state_cookie(settings, state, nonce, redirect_uri)


def get_redirect_uri(request: Request, settings: AppSettings) -> str:
    if settings.google_oidc_redirect_uri:
        return settings.google_oidc_redirect_uri
    return str(request.url_for("auth_oidc_callback"))


def create_oidc_state_cookie(settings: AppSettings, state: str, nonce: str, redirect_uri: str) -> str:
    payload = {
        "state": state,
        "nonce": nonce,
        "redirect_uri": redirect_uri,
        "iat": int(time.time()),
    }
    encoded_payload = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(settings.session_secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_urlsafe_b64encode(signature)}"


def set_oidc_state_cookie(response: Response, settings: AppSettings, cookie_value: str) -> None:
    response.set_cookie(
        key=OIDC_STATE_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=OIDC_STATE_TTL_SECONDS,
        path="/",
    )


def clear_oidc_state_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=OIDC_STATE_COOKIE_NAME,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def consume_oidc_state(request: Request, settings: AppSettings, received_state: str) -> dict[str, Any]:
    cookie_value = request.cookies.get(OIDC_STATE_COOKIE_NAME)
    if not cookie_value or "." not in cookie_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se ha encontrado el estado OIDC.")
    payload_part, signature_part = cookie_value.split(".", 1)
    expected_signature = hmac.new(settings.session_secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_urlsafe_b64encode(expected_signature), signature_part):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado OIDC no valido.")
    try:
        payload = json.loads(_urlsafe_b64decode(payload_part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado OIDC no valido.") from exc

    issued_at = int(payload.get("iat") or 0)
    if not issued_at or int(time.time()) - issued_at > OIDC_STATE_TTL_SECONDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado OIDC expirado.")
    if not hmac.compare_digest(str(payload.get("state") or ""), received_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado OIDC no coincide.")
    return payload


def exchange_code_for_id_token(code: str, redirect_uri: str, settings: AppSettings) -> str:
    response = requests.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": settings.google_oidc_client_id,
            "client_secret": settings.google_oidc_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not response.ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google no ha aceptado el codigo OIDC.")
    token_payload = response.json()
    id_token_value = str(token_payload.get("id_token") or "")
    if not id_token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google no ha devuelto id_token.")
    return id_token_value


def verify_google_id_token(id_token_value: str, expected_nonce: str, settings: AppSettings) -> dict[str, Any]:
    if id_token is None or google_auth_requests is None:
        raise RuntimeError("Falta google-auth para validar tokens OpenID Connect.")
    claims = id_token.verify_oauth2_token(
        id_token_value,
        google_auth_requests.Request(),
        settings.google_oidc_client_id,
    )
    issuer = str(claims.get("iss") or "")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Issuer OIDC no valido.")
    if not hmac.compare_digest(str(claims.get("nonce") or ""), expected_nonce):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nonce OIDC no valido.")
    if not bool(claims.get("email_verified")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google no ha verificado este email.")

    email = str(claims.get("email") or "").strip().lower()
    if settings.google_oidc_allowed_emails and email not in settings.google_oidc_allowed_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este email no esta autorizado.")
    hosted_domain = str(claims.get("hd") or "").strip().lower()
    if settings.google_oidc_hosted_domain and hosted_domain != settings.google_oidc_hosted_domain:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dominio Google no autorizado.")
    return claims


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))
