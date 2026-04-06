from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .service import AnalyticsService


def create_app(service: AnalyticsService | None = None) -> FastAPI:
    app = FastAPI(title="FEB Analytics API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.analytics_service = service or AnalyticsService()

    def get_service() -> AnalyticsService:
        return app.state.analytics_service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/meta/scopes")
    def meta_scopes(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
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
        service: AnalyticsService = Depends(get_service),
    ) -> dict:
        return service.get_gm_players(season=season, league=league, phases=phases, jornadas=jornadas, mode=mode)

    @app.get("/dependency/players")
    def dependency_players(
        season: str | None = None,
        league: str | None = None,
        phases: Annotated[list[str] | None, Query()] = None,
        jornadas: Annotated[list[int] | None, Query()] = None,
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

    return app


app = create_app()
