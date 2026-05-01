from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cloud_runtime import StorageClientFactory, prepare_runtime_storage
from .report_budget import ReportBudgetTracker
from .security import (
    AppSettings,
    FixedWindowRateLimiter,
    SessionData,
    apply_security_headers,
    clear_session_cookie,
    create_session_cookie,
    get_optional_session,
    load_app_settings,
    login_rate_limit_key,
    report_rate_limit_key,
    require_authenticated_session,
    set_session_cookie,
    verify_password,
)
from .service import AnalyticsService


class LoginRequest(BaseModel):
    password: str = Field(default="", min_length=1)


class PlayerReportRequest(BaseModel):
    season: str | None = None
    league: str | None = None
    phases: list[str] = Field(default_factory=list)
    jornadas: list[int] = Field(default_factory=list)
    team: str | None = None
    playerKey: str | None = None


class TeamReportRequest(BaseModel):
    season: str | None = None
    league: str | None = None
    phases: list[str] = Field(default_factory=list)
    jornadas: list[int] = Field(default_factory=list)
    team: str | None = None
    playerKeys: list[str] = Field(default_factory=list)
    rivalTeam: str | None = None
    homeAway: str = "Todos"
    h2hHomeAway: str = "Todos"
    minGames: int = 5
    minMinutes: int = 50
    minShots: int = 20


class PhaseReportRequest(BaseModel):
    season: str | None = None
    league: str | None = None
    phases: list[str] = Field(default_factory=list)
    jornadas: list[int] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    minGames: int = 5
    minMinutes: int = 50
    minShots: int = 20


class MarketCompareRequest(BaseModel):
    season: str | None = None
    leagues: list[str] = Field(default_factory=list)
    playerKeys: list[str] = Field(default_factory=list)


def _build_runtime_summary(service: AnalyticsService, settings: AppSettings) -> dict[str, object]:
    raw_db_path = getattr(service, "db_path", None) or settings.sqlite_local_path
    db_path = Path(str(raw_db_path)).resolve() if raw_db_path else None
    db_exists = bool(db_path and db_path.exists())
    stat = db_path.stat() if db_exists and db_path is not None else None
    snapshot_bucket = settings.sqlite_bucket if settings.uses_gcs_snapshot and settings.sqlite_bucket else None
    snapshot_object = settings.sqlite_object if settings.uses_gcs_snapshot and settings.sqlite_object else None
    return {
        "environment": settings.app_env,
        "appStorageMode": settings.app_storage_mode,
        "reportStorageMode": settings.report_storage_mode,
        "sourceLabel": "Snapshot GCS" if settings.uses_gcs_snapshot else "SQLite local",
        "dbPath": str(db_path) if db_path else "",
        "dbExists": db_exists,
        "dbSizeBytes": int(stat.st_size) if stat is not None else 0,
        "dbLastModified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat is not None else None,
        "snapshotVersion": settings.sqlite_snapshot_version or None,
        "snapshotBucket": snapshot_bucket,
        "snapshotObject": snapshot_object,
    }


def create_app(
    service: AnalyticsService | None = None,
    settings: AppSettings | None = None,
    *,
    storage_client_factory: StorageClientFactory | None = None,
) -> FastAPI:
    resolved_settings = settings or load_app_settings()
    app = FastAPI(
        title="FEB Analytics API",
        version="0.1.0",
        docs_url=None if resolved_settings.is_production else "/docs",
        redoc_url=None if resolved_settings.is_production else "/redoc",
        openapi_url=None if resolved_settings.is_production else "/openapi.json",
    )
    # Configure CORS: always in development, or when allowed_origins is specified in production
    cors_origins = list(resolved_settings.allowed_origins)
    if not cors_origins and not resolved_settings.is_production:
        cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    sqlite_runtime_path = None
    if service is None:
        sqlite_runtime_path = prepare_runtime_storage(resolved_settings, storage_client_factory=storage_client_factory)

    app.state.analytics_service = service or AnalyticsService(sqlite_runtime_path or resolved_settings.sqlite_local_path)
    app.state.settings = resolved_settings
    app.state.report_budget_tracker = ReportBudgetTracker(resolved_settings, storage_client_factory=storage_client_factory)
    app.state.login_rate_limiter = FixedWindowRateLimiter()
    app.state.report_rate_limiter = FixedWindowRateLimiter()

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        apply_security_headers(response, app.state.settings)
        return response

    def get_service() -> AnalyticsService:
        return app.state.analytics_service

    def get_settings() -> AppSettings:
        return app.state.settings

    def get_report_budget_tracker() -> ReportBudgetTracker:
        return app.state.report_budget_tracker

    def get_current_session(
        request: Request,
        settings: AppSettings = Depends(get_settings),
    ) -> SessionData:
        return require_authenticated_session(request, settings)

    def enforce_report_rate_limit(
        request: Request,
        session: SessionData = Depends(get_current_session),
        settings: AppSettings = Depends(get_settings),
    ) -> SessionData:
        limiter: FixedWindowRateLimiter = app.state.report_rate_limiter
        key = report_rate_limit_key(request, session)
        if not limiter.allow(key, limit=settings.report_rate_limit, window_seconds=settings.report_rate_window_seconds):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Has superado el limite temporal de informes.")
        return session

    def enforce_report_budget_limit(
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict[str, object]:
        summary = budget_tracker.get_summary()
        if bool(summary.get("isBlocked")):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(
                    summary.get("message")
                    or "Se ha alcanzado el limite mensual de informes cloud. Vuelve a intentarlo el mes que viene."
                ),
            )
        return summary

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/auth/session")
    def auth_session(
        request: Request,
        settings: AppSettings = Depends(get_settings),
    ) -> dict[str, object]:
        if not settings.auth_enabled:
            return {"authenticated": True, "authRequired": False, "ttlHours": settings.session_ttl_hours}
        session = get_optional_session(request, settings)
        return {
            "authenticated": session is not None,
            "authRequired": True,
            "ttlHours": settings.session_ttl_hours,
        }

    @app.post("/auth/login")
    def auth_login(
        payload: Annotated[LoginRequest, Body()],
        request: Request,
        settings: AppSettings = Depends(get_settings),
    ) -> JSONResponse:
        if not settings.auth_enabled:
            return JSONResponse({"authenticated": True, "authRequired": False, "ttlHours": settings.session_ttl_hours})

        limiter: FixedWindowRateLimiter = app.state.login_rate_limiter
        if not limiter.allow(
            login_rate_limit_key(request),
            limit=settings.login_rate_limit,
            window_seconds=settings.login_rate_window_seconds,
        ):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos de acceso. Espera unos minutos.")

        if not verify_password(payload.password, settings.admin_password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña incorrecta.")

        response = JSONResponse({"authenticated": True, "authRequired": True, "ttlHours": settings.session_ttl_hours})
        set_session_cookie(response, settings, create_session_cookie(settings))
        return response

    @app.post("/auth/logout")
    def auth_logout(settings: AppSettings = Depends(get_settings)) -> JSONResponse:
        response = JSONResponse({"authenticated": False, "authRequired": settings.auth_enabled, "ttlHours": settings.session_ttl_hours})
        clear_session_cookie(response, settings)
        return response

    @app.get("/database/summary")
    def database_summary(
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
        settings: AppSettings = Depends(get_settings),
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict:
        payload = service.get_database_summary()
        payload["runtime"] = _build_runtime_summary(service, settings)
        payload["reportBudget"] = budget_tracker.get_summary()
        return payload

    @app.get("/meta/scopes")
    def meta_scopes(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_meta(season=season, league=league, phases=phases, jornadas=jornadas)

    @app.get("/gm/players")
    def gm_players(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        mode: str = "Totales",
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_gm_players(season=season, league=league, phases=phases, jornadas=jornadas, mode=mode)

    @app.get("/dependency/players")
    def dependency_players(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_dependency_players(season=season, league=league, phases=phases, jornadas=jornadas)

    @app.get("/dependency/team-summary")
    def dependency_team_summary(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        team: str | None = None,
        player_key: str | None = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_dependency_team_summary(
            season=season,
            league=league,
            phases=phases,
            jornadas=jornadas,
            team=team,
            player_key=player_key,
        )

    @app.get("/trends/player")
    def player_trends(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        player_key: str | None = None,
        window: int | None = None,
        metrics: Annotated[list[str] | None, Query()] = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_player_trends(
            season=season,
            league=league,
            phases=phases,
            jornadas=jornadas,
            player_key=player_key,
            window=window,
            metrics=metrics,
        )

    @app.get("/trends/team")
    def team_trends(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        team: str | None = None,
        window: int | None = None,
        metrics: Annotated[list[str] | None, Query()] = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_team_trends(
            season=season,
            league=league,
            phases=phases,
            jornadas=jornadas,
            team=team,
            window=window,
            metrics=metrics,
        )

    @app.get("/similarity/player")
    def player_similarity(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
        target_player_key: str | None = None,
        min_games: int = 5,
        min_minutes: float = 10.0,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_player_similarity(
            season=season,
            league=league,
            phases=phases,
            jornadas=jornadas,
            target_player_key=target_player_key,
            min_games=min_games,
            min_minutes=min_minutes,
        )

    @app.get("/market/pool")
    def market_pool(
        season: str | None = None,
        leagues: Annotated[list[str] | None, Query()] = None,
        min_games: int = 5,
        min_minutes: float = 10.0,
        query: str | None = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_market_pool(
            season=season,
            leagues=leagues,
            min_games=min_games,
            min_minutes=min_minutes,
            query=query,
        )

    @app.post("/market/compare")
    def market_compare(
        payload: Annotated[MarketCompareRequest, Body()],
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        try:
            return service.get_market_compare(
                season=payload.season,
                leagues=payload.leagues,
                player_keys=payload.playerKeys,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/market/suggestions")
    def market_suggestions(
        season: str | None = None,
        leagues: Annotated[list[str] | None, Query()] = None,
        anchor_player_key: str | None = None,
        limit: int = 6,
        weights: str | None = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        parsed_weights: dict[str, object] | None = None
        if weights:
            try:
                payload = json.loads(weights)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="El formato de pesos de similares no es valido.") from exc
            if payload is not None and not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Los pesos de similares deben enviarse como objeto JSON.")
            parsed_weights = payload
        try:
            return service.get_market_suggestions(
                season=season,
                leagues=leagues,
                anchor_player_key=anchor_player_key,
                limit=limit,
                weights=parsed_weights,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/market/opportunity")
    def market_opportunity(
        season: str | None = None,
        leagues: Annotated[list[str] | None, Query()] = None,
        min_games: int = 5,
        max_minutes: float = 22.0,
        max_usg: float = 24.0,
        query: str | None = None,
        _: SessionData = Depends(get_current_session),
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_market_opportunity(
            season=season,
            leagues=leagues,
            min_games=min_games,
            max_minutes=max_minutes,
            max_usg=max_usg,
            query=query,
        )

    @app.post("/reports/player")
    def player_report(
        payload: Annotated[PlayerReportRequest, Body()],
        _: SessionData = Depends(enforce_report_rate_limit),
        __: dict[str, object] = Depends(enforce_report_budget_limit),
        service: AnalyticsService = Depends(get_service),
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict:
        try:
            started_at = time.perf_counter()
            result = service.generate_player_report(
                season=payload.season,
                league=payload.league,
                phases=payload.phases,
                jornadas=payload.jornadas,
                team=payload.team,
                player_key=payload.playerKey,
            )
            _record_report_budget(budget_tracker, "player", time.perf_counter() - started_at)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reports/team")
    def team_report(
        payload: Annotated[TeamReportRequest, Body()],
        _: SessionData = Depends(enforce_report_rate_limit),
        __: dict[str, object] = Depends(enforce_report_budget_limit),
        service: AnalyticsService = Depends(get_service),
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict:
        try:
            started_at = time.perf_counter()
            result = service.generate_team_report(
                season=payload.season,
                league=payload.league,
                phases=payload.phases,
                jornadas=payload.jornadas,
                team=payload.team,
                player_keys=payload.playerKeys,
                rival_team=payload.rivalTeam,
                home_away=payload.homeAway,
                h2h_home_away=payload.h2hHomeAway,
                min_games=payload.minGames,
                min_minutes=payload.minMinutes,
                min_shots=payload.minShots,
            )
            _record_report_budget(budget_tracker, "team", time.perf_counter() - started_at)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reports/phase")
    def phase_report(
        payload: Annotated[PhaseReportRequest, Body()],
        _: SessionData = Depends(enforce_report_rate_limit),
        __: dict[str, object] = Depends(enforce_report_budget_limit),
        service: AnalyticsService = Depends(get_service),
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict:
        try:
            started_at = time.perf_counter()
            result = service.generate_phase_report(
                season=payload.season,
                league=payload.league,
                phases=payload.phases,
                jornadas=payload.jornadas,
                teams=payload.teams,
                min_games=payload.minGames,
                min_minutes=payload.minMinutes,
                min_shots=payload.minShots,
            )
            _record_report_budget(budget_tracker, "phase", time.perf_counter() - started_at)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/reports/budget")
    def report_budget(
        _: SessionData = Depends(get_current_session),
        budget_tracker: ReportBudgetTracker = Depends(get_report_budget_tracker),
    ) -> dict:
        return budget_tracker.get_summary()

    @app.get("/reports/files/{kind}/{filename}")
    def report_file(
        kind: str,
        filename: str,
        _: SessionData = Depends(enforce_report_rate_limit),
        service: AnalyticsService = Depends(get_service),
    ) -> FileResponse:
        path = service.get_report_file_path(kind, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="No se ha encontrado el archivo solicitado.")
        return FileResponse(path, filename=path.name)

    _mount_frontend(app, resolved_settings)
    return app


def _mount_frontend(app: FastAPI, settings: AppSettings) -> None:
    dist_dir = settings.frontend_dist_dir
    if not dist_dir.exists():
        return

    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(dist_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_spa(full_path: str) -> Response:
        if _is_reserved_backend_path(full_path):
            raise HTTPException(status_code=404, detail="Ruta no encontrada.")
        candidate = (dist_dir / full_path).resolve()
        if _is_safe_static_candidate(candidate, dist_dir) and candidate.is_file():
            return FileResponse(candidate)
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend no disponible.")


def _is_reserved_backend_path(full_path: str) -> bool:
    normalized = str(full_path or "").lstrip("/")
    return normalized in {
        "health",
        "database/summary",
        "meta/scopes",
        "gm/players",
        "dependency/players",
        "dependency/team-summary",
        "trends/player",
        "trends/team",
        "similarity/player",
        "market/pool",
        "market/compare",
        "market/suggestions",
        "market/opportunity",
        "auth/session",
        "auth/login",
        "auth/logout",
        "docs",
        "redoc",
        "openapi.json",
    } or normalized.startswith("reports/") or normalized.startswith("assets/")


def _is_safe_static_candidate(candidate: Path, dist_dir: Path) -> bool:
    try:
        dist_resolved = dist_dir.resolve()
        return candidate == dist_resolved or dist_resolved in candidate.parents
    except FileNotFoundError:
        return False


def _record_report_budget(tracker: ReportBudgetTracker, kind: str, elapsed_seconds: float) -> None:
    try:
        tracker.record_report(kind, elapsed_seconds)
    except Exception:
        # El contador mensual nunca debe romper la generacion del informe.
        return


app = create_app()
