from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import GENERIC_PLAYER_IMAGE, SQLITE_DB_FILE
from storage import DataStore, ReportBundle, ReportFilters
from utils.dependency_view import (
    build_dependency_players_view,
    build_player_dependency_diagnosis,
    build_structural_risk_summary,
)
from utils.trends_view import (
    PLAYER_TREND_METRIC_OPTIONS,
    TEAM_TREND_METRIC_OPTIONS,
    build_player_scope_baseline,
    build_recent_player_games,
    build_recent_team_games,
    build_recent_vs_scope_summary,
    build_team_scope_baseline,
    build_trend_chart_frame,
)

from .gm_view import GM_DEFAULT_TABLE_COLUMNS, build_gm_players_view


@dataclass(slots=True)
class ScopeFilters:
    season: str | None = None
    league: str | None = None
    phases: list[str] | None = None
    jornadas: list[int] | None = None


def _empty_bundle() -> ReportBundle:
    empty = pd.DataFrame()
    return ReportBundle(
        players_df=empty.copy(),
        teams_df=empty.copy(),
        assists_df=empty.copy(),
        clutch_df=empty.copy(),
        clutch_lineups_df=empty.copy(),
        games_df=empty.copy(),
        boxscores_df=empty.copy(),
    )


def _to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _format_optional_dorsal(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    numeric = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.notna(numeric) and float(numeric).is_integer():
        text = str(int(numeric))
    return f"#{text}"


def _build_player_selection_label(player_name: Any, team_name: Any = None, dorsal: Any = None) -> str:
    name_text = str(player_name or "").strip() or "-"
    dorsal_text = _format_optional_dorsal(dorsal)
    prefix = f"{dorsal_text} " if dorsal_text else ""
    team_text = str(team_name).strip() if team_name is not None and not pd.isna(team_name) else ""
    if team_text:
        return f"{prefix}{name_text} | {team_text}"
    return f"{prefix}{name_text}"


def _resolve_image(image_value: Any) -> str:
    if image_value is not None and not pd.isna(image_value):
        text = str(image_value).strip()
        if text:
            return text
    return str(GENERIC_PLAYER_IMAGE)


class AnalyticsService:
    def __init__(self, db_path: str | Path = SQLITE_DB_FILE) -> None:
        self.db_path = str(db_path)

    def _get_store(self) -> DataStore:
        return DataStore(self.db_path)

    def _resolve_scope(self, filters: ScopeFilters) -> dict[str, Any]:
        store = self._get_store()
        seasons = store.get_available_seasons()
        season = filters.season if filters.season in seasons else (seasons[0] if seasons else None)

        leagues = store.get_available_leagues(season) if season else []
        league = filters.league if filters.league in leagues else (leagues[0] if leagues else None)

        phases_available = store.get_available_phases(season, league) if season and league else []
        phases = [phase for phase in (filters.phases or []) if phase in phases_available]

        jornadas_available = store.get_available_jornadas(season, league, tuple(phases)) if season and league else []
        jornadas = [int(jornada) for jornada in (filters.jornadas or []) if int(jornada) in jornadas_available]

        return {
            "seasons": seasons,
            "leagues": leagues,
            "phases": phases_available,
            "jornadas": jornadas_available,
            "selected": {
                "season": season,
                "league": league,
                "phases": phases,
                "jornadas": jornadas,
            },
        }

    def _load_bundle(self, resolved_scope: dict[str, Any]) -> ReportBundle:
        selected = resolved_scope["selected"]
        season = selected["season"]
        league = selected["league"]
        if not season or not league:
            return _empty_bundle()
        filters = ReportFilters(
            season=season,
            league=league,
            phases=tuple(selected["phases"]),
            jornadas=tuple(selected["jornadas"]),
        )
        return self._get_store().load_report_bundle(filters)

    def _build_player_options(self, players_df: pd.DataFrame) -> list[dict[str, Any]]:
        if players_df.empty:
            return []
        frame = players_df[["PLAYER_KEY", "JUGADOR", "EQUIPO"]].copy()
        frame["DORSAL"] = players_df["DORSAL"] if "DORSAL" in players_df.columns else None
        frame["PJ"] = pd.to_numeric(players_df["PJ"] if "PJ" in players_df.columns else 0, errors="coerce").fillna(0).astype(int)
        frame["label"] = [
            _build_player_selection_label(player_name, team_name, dorsal)
            for player_name, team_name, dorsal in zip(frame["JUGADOR"], frame["EQUIPO"], frame["DORSAL"])
        ]
        frame = frame.sort_values(by=["label", "PLAYER_KEY"], ascending=True, na_position="last")
        frame = frame.rename(
            columns={
                "PLAYER_KEY": "playerKey",
                "JUGADOR": "name",
                "EQUIPO": "team",
                "DORSAL": "dorsal",
                "PJ": "gamesPlayed",
            }
        )
        return _to_records(frame)

    def _build_team_options(self, teams_df: pd.DataFrame) -> list[dict[str, Any]]:
        if teams_df.empty or "EQUIPO" not in teams_df.columns:
            return []
        frame = teams_df[["EQUIPO"]].copy()
        frame["PJ"] = pd.to_numeric(teams_df["PJ"] if "PJ" in teams_df.columns else 0, errors="coerce").fillna(0).astype(int)
        frame = frame.sort_values(by="EQUIPO", ascending=True, na_position="last")
        frame = frame.rename(columns={"EQUIPO": "name", "PJ": "gamesPlayed"})
        return _to_records(frame)

    def get_meta(self, *, season: str | None, league: str | None, phases: list[str] | None, jornadas: list[int] | None) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        return {
            **resolved_scope,
            "teams": self._build_team_options(bundle.teams_df),
            "players": self._build_player_options(bundle.players_df),
        }

    def get_gm_players(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        mode: str,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        gm_df = build_gm_players_view(bundle.players_df, mode, bundle.teams_df)
        if "PUNTOS" in gm_df.columns:
            gm_df = gm_df.sort_values(by=["PUNTOS", "JUGADOR"], ascending=[False, True], na_position="last").reset_index(drop=True)
        return {
            "scope": resolved_scope["selected"],
            "mode": mode,
            "columns": [column for column in GM_DEFAULT_TABLE_COLUMNS if column in gm_df.columns],
            "rows": _to_records(gm_df),
            "players": self._build_player_options(bundle.players_df),
        }

    def get_dependency_players(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        dependency_df = build_dependency_players_view(bundle)
        if "DEPENDENCIA_SCORE" in dependency_df.columns:
            dependency_df = dependency_df.sort_values(by=["DEPENDENCIA_SCORE", "JUGADOR"], ascending=[False, True], na_position="last").reset_index(drop=True)
        return {
            "scope": resolved_scope["selected"],
            "rows": _to_records(dependency_df),
            "teams": self._build_team_options(bundle.teams_df),
            "players": self._build_player_options(bundle.players_df),
        }

    def get_dependency_team_summary(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        team: str | None,
        player_key: str | None,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        dependency_df = build_dependency_players_view(bundle)
        if "DEPENDENCIA_SCORE" in dependency_df.columns:
            dependency_df = dependency_df.sort_values(by=["DEPENDENCIA_SCORE", "JUGADOR"], ascending=[False, True], na_position="last")

        teams = sorted(dependency_df["EQUIPO"].dropna().astype(str).unique().tolist()) if not dependency_df.empty else []
        selected_team = team if team in teams else (teams[0] if teams else None)
        team_df = dependency_df[dependency_df["EQUIPO"].astype(str) == str(selected_team)].copy() if selected_team else pd.DataFrame()

        if team_df.empty:
            return {
                "scope": resolved_scope["selected"],
                "selectedTeam": selected_team,
                "structuralRisk": "Riesgo estructural del equipo: sin datos en el scope actual.",
                "metrics": {},
                "detail": None,
                "tableRows": [],
                "note": "Los porcentajes se calculan sobre los partidos disputados por ese jugador dentro del scope actual.",
            }

        selected_player_key = player_key if player_key in team_df["PLAYER_KEY"].astype(str).tolist() else str(team_df.iloc[0]["PLAYER_KEY"])
        player_row = team_df[team_df["PLAYER_KEY"].astype(str) == selected_player_key].iloc[0]
        player_meta = bundle.players_df[bundle.players_df["PLAYER_KEY"].astype(str) == selected_player_key].head(1)
        image = _resolve_image(player_meta.iloc[0]["IMAGEN"] if not player_meta.empty and "IMAGEN" in player_meta.columns else None)

        metrics = {
            "criticalPlayer": str(team_df.iloc[0]["JUGADOR"]),
            "topUsage": float(pd.to_numeric(team_df["%PLAYS_EQUIPO"], errors="coerce").fillna(0.0).max() or 0.0),
            "topScoring": float(pd.to_numeric(team_df["%PUNTOS_EQUIPO"], errors="coerce").fillna(0.0).max() or 0.0),
            "topCreation": float(pd.to_numeric(team_df["%AST_EQUIPO"], errors="coerce").fillna(0.0).max() or 0.0),
            "top3Usage": float(pd.to_numeric(team_df["%PLAYS_EQUIPO"], errors="coerce").fillna(0.0).nlargest(3).sum() or 0.0),
        }

        detail = {
            "playerKey": selected_player_key,
            "name": str(player_row["JUGADOR"]),
            "image": image,
            "team": str(player_row["EQUIPO"]),
            "gamesPlayed": int(pd.to_numeric(player_row.get("PJ"), errors="coerce") or 0),
            "risk": str(player_row.get("DEPENDENCIA_RIESGO") or ""),
            "focus": str(player_row.get("FOCO_PRINCIPAL") or ""),
            "dependencyScore": float(pd.to_numeric(player_row.get("DEPENDENCIA_SCORE"), errors="coerce") or 0.0),
            "usageShare": float(pd.to_numeric(player_row.get("%PLAYS_EQUIPO"), errors="coerce") or 0.0),
            "scoringShare": float(pd.to_numeric(player_row.get("%PUNTOS_EQUIPO"), errors="coerce") or 0.0),
            "creationShare": float(pd.to_numeric(player_row.get("%AST_EQUIPO"), errors="coerce") or 0.0),
            "reboundShare": float(pd.to_numeric(player_row.get("%REB_EQUIPO"), errors="coerce") or 0.0),
            "clutchShare": float(pd.to_numeric(player_row.get("%MIN_CLUTCH_EQUIPO"), errors="coerce") or 0.0) if pd.notna(player_row.get("%MIN_CLUTCH_EQUIPO")) else None,
            "hasClutchData": bool(player_row.get("HAS_CLUTCH_DATA")),
            "diagnosis": build_player_dependency_diagnosis(player_row),
        }

        return {
            "scope": resolved_scope["selected"],
            "selectedTeam": selected_team,
            "selectedPlayerKey": selected_player_key,
            "structuralRisk": build_structural_risk_summary(team_df),
            "metrics": metrics,
            "detail": detail,
            "tableRows": _to_records(team_df.reset_index(drop=True)),
            "note": "Los porcentajes se calculan sobre los partidos disputados por ese jugador dentro del scope actual.",
        }

    def get_player_trends(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        player_key: str | None,
        window: int | None,
        metrics: list[str] | None,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        player_options = self._build_player_options(bundle.players_df)
        available_keys = [str(option["playerKey"]) for option in player_options]
        selected_player_key = player_key if player_key in available_keys else (available_keys[0] if available_keys else None)

        games_played_lookup = {
            str(option["playerKey"]): int(option.get("gamesPlayed") or 0)
            for option in player_options
        }
        window_max = max(games_played_lookup.get(str(selected_player_key), 0), 0)
        resolved_window = max(min(int(window or min(window_max or 1, 5)), window_max or 1), 1) if selected_player_key else 0

        recent_df = build_recent_player_games(bundle.boxscores_df, str(selected_player_key or ""), last_n=resolved_window) if selected_player_key else pd.DataFrame()
        baseline = build_player_scope_baseline(bundle.players_df, str(selected_player_key or "")) if selected_player_key else {metric: 0.0 for metric in PLAYER_TREND_METRIC_OPTIONS}
        selected_metrics = [metric for metric in (metrics or []) if metric in PLAYER_TREND_METRIC_OPTIONS] or ["PUNTOS"]
        chart_df = build_trend_chart_frame(recent_df, selected_metrics)
        summary_df = build_recent_vs_scope_summary(recent_df, baseline, list(PLAYER_TREND_METRIC_OPTIONS))

        return {
            "scope": resolved_scope["selected"],
            "players": player_options,
            "selectedPlayerKey": selected_player_key,
            "availableMetrics": [{"key": key, "label": label} for key, label in PLAYER_TREND_METRIC_OPTIONS.items()],
            "selectedMetrics": selected_metrics,
            "window": resolved_window,
            "windowMax": window_max,
            "recentCount": int(recent_df.shape[0]),
            "summaryRows": _to_records(summary_df),
            "recentGames": _to_records(recent_df),
            "chartRows": _to_records(chart_df),
        }

    def get_team_trends(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        team: str | None,
        window: int | None,
        metrics: list[str] | None,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        team_options = self._build_team_options(bundle.teams_df)
        available_teams = [str(option["name"]) for option in team_options]
        selected_team = team if team in available_teams else (available_teams[0] if available_teams else None)
        games_played_lookup = {
            str(option["name"]): int(option.get("gamesPlayed") or 0)
            for option in team_options
        }
        window_max = max(games_played_lookup.get(str(selected_team), 0), 0)
        resolved_window = max(min(int(window or min(window_max or 1, 5)), window_max or 1), 1) if selected_team else 0

        recent_df = build_recent_team_games(bundle.games_df, str(selected_team or ""), last_n=resolved_window) if selected_team else pd.DataFrame()
        baseline = build_team_scope_baseline(bundle.games_df, str(selected_team or "")) if selected_team else {metric: 0.0 for metric in TEAM_TREND_METRIC_OPTIONS}
        selected_metrics = [metric for metric in (metrics or []) if metric in TEAM_TREND_METRIC_OPTIONS] or ["NETRTG"]
        chart_df = build_trend_chart_frame(recent_df, selected_metrics)
        summary_df = build_recent_vs_scope_summary(recent_df, baseline, list(TEAM_TREND_METRIC_OPTIONS))

        return {
            "scope": resolved_scope["selected"],
            "teams": team_options,
            "selectedTeam": selected_team,
            "availableMetrics": [{"key": key, "label": label} for key, label in TEAM_TREND_METRIC_OPTIONS.items()],
            "selectedMetrics": selected_metrics,
            "window": resolved_window,
            "windowMax": window_max,
            "recentCount": int(recent_df.shape[0]),
            "summaryRows": _to_records(summary_df),
            "recentGames": _to_records(recent_df),
            "chartRows": _to_records(chart_df),
        }
