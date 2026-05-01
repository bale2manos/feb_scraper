from __future__ import annotations

import contextlib
import gc
import io
import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from dataclasses import dataclass
from functools import lru_cache
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib

matplotlib.use("Agg", force=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import (
    AUTO_SYNC_TARGETS_FILE,
    GENERIC_PLAYER_IMAGE,
    PHASE_REPORTS_DIR,
    PLAYER_REPORTS_DIR,
    SQLITE_DB_FILE,
    TEAM_REPORTS_DIR,
)
from storage import DataStore, ReportBundle, ReportFilters
from utils.auto_sync import iter_enabled_targets, load_auto_sync_config
from utils.dependency_view import (
    build_dependency_players_view,
    build_player_dependency_diagnosis,
    build_structural_risk_summary,
)
from utils.similarity_view import (
    SIMILARITY_FEATURE_WEIGHTS,
    build_player_similarity_results,
    build_similarity_player_pool,
    get_similarity_feature_catalog,
    resolve_similarity_feature_weights,
)
from utils.market_view import (
    build_market_compare_results,
    build_market_opportunity_results,
    build_market_player_pool,
    filter_market_pool,
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

from .gm_view import build_gm_players_view

REPORT_DIRECTORIES = {
    "player": PLAYER_REPORTS_DIR.resolve(),
    "team": TEAM_REPORTS_DIR.resolve(),
    "phase": PHASE_REPORTS_DIR.resolve(),
}


@lru_cache(maxsize=1)
def _get_player_report_fn():
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        from player_report.player_report_gen import generate_report

    return generate_report


@lru_cache(maxsize=1)
def _get_team_report_fn():
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        from team_report.build_team_report import build_team_report

    return build_team_report


@lru_cache(maxsize=1)
def _get_phase_report_fn():
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        from phase_report.build_phase_report import build_phase_report

    return build_phase_report


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
        clutch_games_df=empty.copy(),
        games_df=empty.copy(),
        boxscores_df=empty.copy(),
    )


def _clone_bundle(bundle: ReportBundle) -> ReportBundle:
    return ReportBundle(
        players_df=bundle.players_df.copy(),
        teams_df=bundle.teams_df.copy(),
        assists_df=bundle.assists_df.copy(),
        clutch_df=bundle.clutch_df.copy(),
        clutch_lineups_df=bundle.clutch_lineups_df.copy(),
        clutch_games_df=bundle.clutch_games_df.copy(),
        games_df=bundle.games_df.copy(),
        boxscores_df=bundle.boxscores_df.copy(),
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


def _coerce_int(value: Any, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    numeric = max(numeric, minimum)
    if maximum is not None:
        numeric = min(numeric, maximum)
    return numeric


def _extract_birth_year(value: Any) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    year = int(numeric)
    if year < 1900 or year > 2100:
        return None
    return year


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _call_silently(fn, *args, **kwargs):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        return fn(*args, **kwargs)


class AnalyticsService:
    def __init__(self, db_path: str | Path = SQLITE_DB_FILE) -> None:
        self.db_path = str(db_path)

    def _db_signature(self) -> tuple[str, int, int]:
        path = Path(self.db_path)
        if not path.exists():
            return str(path.resolve()), 0, 0
        stat = path.stat()
        return str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size)

    @staticmethod
    def _normalize_phases(phases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
        return tuple(sorted(str(value) for value in (phases or []) if str(value).strip()))

    @staticmethod
    def _normalize_jornadas(jornadas: list[int] | tuple[int, ...] | None) -> tuple[int, ...]:
        normalized = {int(value) for value in (jornadas or [])}
        return tuple(sorted(normalized))

    @staticmethod
    def _normalize_similarity_weight_overrides(
        weights: dict[str, Any] | None,
    ) -> tuple[tuple[str, float], ...]:
        if not weights:
            return tuple()
        normalized: dict[str, float] = {}
        for key, value in weights.items():
            text = str(key or "").strip()
            if not text or text not in SIMILARITY_FEATURE_WEIGHTS:
                continue
            numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0]
            normalized[text] = max(float(numeric), 0.0)
        return tuple(sorted(normalized.items()))

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

    def _resolve_market_scope(
        self,
        *,
        season: str | None,
        leagues: list[str] | tuple[str, ...] | None,
    ) -> dict[str, Any]:
        store = self._get_store()
        seasons = store.get_available_seasons()
        resolved_season = season if season in seasons else (seasons[0] if seasons else None)
        available_leagues = store.get_available_leagues(resolved_season) if resolved_season else []
        normalized_leagues: list[str] = []
        for league in leagues or []:
            text = str(league or "").strip()
            if text and text in available_leagues and text not in normalized_leagues:
                normalized_leagues.append(text)
        selected_leagues = normalized_leagues or ([available_leagues[0]] if available_leagues else [])
        return {
            "seasons": seasons,
            "season": resolved_season,
            "availableLeagues": available_leagues,
            "selectedLeagues": selected_leagues,
        }

    def _load_bundle(
        self,
        resolved_scope: dict[str, Any],
        db_signature: tuple[str, int, int] | None = None,
        *,
        clone: bool = False,
    ) -> ReportBundle:
        selected = resolved_scope["selected"]
        season = selected["season"]
        league = selected["league"]
        bundle = self._cached_bundle(
            db_signature or self._db_signature(),
            season,
            league,
            tuple(selected["phases"]),
            tuple(selected["jornadas"]),
        )
        return _clone_bundle(bundle) if clone else bundle

    @lru_cache(maxsize=32)
    def _cached_bundle(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
    ) -> ReportBundle:
        if not season or not league:
            return _empty_bundle()
        filters = ReportFilters(
            season=season,
            league=league,
            phases=phases,
            jornadas=jornadas,
        )
        return self._get_store().load_report_bundle(filters)

    @lru_cache(maxsize=32)
    def _cached_market_pool_context(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        leagues: tuple[str, ...],
    ) -> dict[str, Any]:
        resolved_market_scope = self._resolve_market_scope(season=season, leagues=leagues)
        pool_frames: list[pd.DataFrame] = []

        for league in resolved_market_scope["selectedLeagues"]:
            resolved_scope = self._resolve_scope(ScopeFilters(season=resolved_market_scope["season"], league=league, phases=[], jornadas=[]))
            bundle = self._load_bundle(resolved_scope, db_signature)
            gm_df = build_gm_players_view(bundle.players_df, "Promedios", bundle.teams_df)
            dependency_df = build_dependency_players_view(bundle)
            pool_frames.append(build_market_player_pool(gm_df, dependency_df, league))

        pool_df = pd.concat(pool_frames, ignore_index=True) if pool_frames else build_market_player_pool(pd.DataFrame(), pd.DataFrame(), "")
        return {
            "season": resolved_market_scope["season"],
            "availableLeagues": list(resolved_market_scope["availableLeagues"]),
            "selectedLeagues": list(resolved_market_scope["selectedLeagues"]),
            "pool": pool_df,
        }

    def _build_market_summary(self, pool_df: pd.DataFrame, *, selected_leagues: list[str], min_games: int, min_minutes: float, query: str) -> dict[str, Any]:
        top_points_row = pool_df.iloc[0] if not pool_df.empty else {}
        top_ts_row = (
            pool_df.sort_values(by=["TS%", "PUNTOS"], ascending=[False, False], na_position="last").iloc[0]
            if not pool_df.empty and "TS%" in pool_df.columns
            else {}
        )
        top_dependency_row = (
            pool_df.sort_values(by=["DEPENDENCIA_SCORE", "PUNTOS"], ascending=[False, False], na_position="last").iloc[0]
            if not pool_df.empty and "DEPENDENCIA_SCORE" in pool_df.columns
            else {}
        )
        return {
            "playerCount": int(len(pool_df.index)),
            "leagueCount": int(len(selected_leagues)),
            "filters": {
                "minGames": int(min_games),
                "minMinutes": float(min_minutes),
                "query": str(query or ""),
            },
            "leaders": {
                "topScorer": str(top_points_row.get("JUGADOR") or ""),
                "topEfficiency": str(top_ts_row.get("JUGADOR") or ""),
                "topDependency": str(top_dependency_row.get("JUGADOR") or ""),
            },
        }

    @staticmethod
    def _build_market_player_payload(player_row: dict[str, Any]) -> dict[str, Any]:
        birth_year = _extract_birth_year(player_row.get("AÑO NACIMIENTO"))
        return {
            "playerKey": str(player_row.get("PLAYER_KEY") or ""),
            "label": _build_player_selection_label(player_row.get("JUGADOR"), player_row.get("EQUIPO"), player_row.get("DORSAL")),
            "name": str(player_row.get("JUGADOR") or ""),
            "team": str(player_row.get("EQUIPO") or ""),
            "league": str(player_row.get("LIGA") or ""),
            "image": _resolve_image(player_row.get("IMAGEN")),
            "birthYear": birth_year,
            "gamesPlayed": int(pd.to_numeric(pd.Series([player_row.get("PJ")]), errors="coerce").fillna(0).iloc[0]),
            "minutes": float(pd.to_numeric(pd.Series([player_row.get("MINUTOS JUGADOS")]), errors="coerce").fillna(0.0).iloc[0]),
            "points": float(pd.to_numeric(pd.Series([player_row.get("PUNTOS")]), errors="coerce").fillna(0.0).iloc[0]),
            "rebounds": float(pd.to_numeric(pd.Series([player_row.get("REB TOTALES")]), errors="coerce").fillna(0.0).iloc[0]),
            "assists": float(pd.to_numeric(pd.Series([player_row.get("ASISTENCIAS")]), errors="coerce").fillna(0.0).iloc[0]),
            "turnovers": float(pd.to_numeric(pd.Series([player_row.get("PERDIDAS")]), errors="coerce").fillna(0.0).iloc[0]),
            "plays": float(pd.to_numeric(pd.Series([player_row.get("PLAYS")]), errors="coerce").fillna(0.0).iloc[0]),
            "usg": float(pd.to_numeric(pd.Series([player_row.get("USG%")]), errors="coerce").fillna(0.0).iloc[0]),
            "ts": float(pd.to_numeric(pd.Series([player_row.get("TS%")]), errors="coerce").fillna(0.0).iloc[0]),
            "efg": float(pd.to_numeric(pd.Series([player_row.get("eFG%")]), errors="coerce").fillna(0.0).iloc[0]),
            "ppp": float(pd.to_numeric(pd.Series([player_row.get("PPP")]), errors="coerce").fillna(0.0).iloc[0]),
            "astTo": float(pd.to_numeric(pd.Series([player_row.get("AST/TO")]), errors="coerce").fillna(0.0).iloc[0]),
            "dependencyScore": float(pd.to_numeric(pd.Series([player_row.get("DEPENDENCIA_SCORE")]), errors="coerce").fillna(0.0).iloc[0]),
            "focus": str(player_row.get("FOCO_PRINCIPAL") or ""),
        }

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

    def get_report_file_path(self, kind: str, filename: str) -> Path | None:
        base_dir = REPORT_DIRECTORIES.get(str(kind))
        if base_dir is None:
            return None
        safe_name = Path(str(filename)).name
        candidate = (base_dir / safe_name).resolve()
        if candidate.parent != base_dir or not candidate.exists():
            return None
        return candidate

    def _build_report_file_payload(self, path: Path, kind: str) -> dict[str, Any]:
        resolved = path.resolve()
        mime_type = guess_type(resolved.name)[0] or ("image/png" if resolved.suffix.lower() == ".png" else "application/pdf")
        version = resolved.stat().st_mtime_ns
        url = f"/reports/files/{kind}/{quote(resolved.name)}?v={version}"
        return {
            "kind": kind,
            "fileName": resolved.name,
            "fileUrl": url,
            "previewUrl": url,
            "mimeType": mime_type,
            "sizeBytes": int(resolved.stat().st_size),
            "generatedAt": datetime.fromtimestamp(resolved.stat().st_mtime).isoformat(timespec="seconds"),
        }

    def _load_scope_tables(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        scope_columns = [
            "Temporada",
            "Liga",
            "Fase",
            "JornadaMin",
            "JornadaMax",
            "JornadasDetectadas",
            "PartidosCatalogados",
            "ConDatos",
            "Pendientes",
            "Fallidos",
            "UltimaRevision",
            "UltimoScrapeo",
        ]
        jornada_columns = ["Temporada", "Liga", "Fase", "Jornada", "Partidos", "ConDatos", "Pendientes", "Fallidos"]
        if not Path(self.db_path).exists():
            return pd.DataFrame(columns=scope_columns), pd.DataFrame(columns=jornada_columns)

        store = self._get_store()
        with store.connect() as conn:
            scope_df = pd.read_sql_query(
                """
                SELECT
                    season_full AS Temporada,
                    league_name AS Liga,
                    phase AS Fase,
                    MIN(jornada) AS JornadaMin,
                    MAX(jornada) AS JornadaMax,
                    COUNT(DISTINCT jornada) AS JornadasDetectadas,
                    COUNT(*) AS PartidosCatalogados,
                    SUM(CASE WHEN scrape_status IN ('success', 'imported') THEN 1 ELSE 0 END) AS ConDatos,
                    SUM(CASE WHEN scrape_status = 'pending' THEN 1 ELSE 0 END) AS Pendientes,
                    SUM(CASE WHEN scrape_status LIKE 'failed:%' THEN 1 ELSE 0 END) AS Fallidos,
                    MAX(last_seen_at) AS UltimaRevision,
                    MAX(last_scraped_at) AS UltimoScrapeo
                FROM games_catalog
                GROUP BY season_full, league_name, phase
                ORDER BY season_full DESC, league_name, phase
                """,
                conn,
            )
            jornada_df = pd.read_sql_query(
                """
                SELECT
                    season_full AS Temporada,
                    league_name AS Liga,
                    phase AS Fase,
                    jornada AS Jornada,
                    COUNT(*) AS Partidos,
                    SUM(CASE WHEN scrape_status IN ('success', 'imported') THEN 1 ELSE 0 END) AS ConDatos,
                    SUM(CASE WHEN scrape_status = 'pending' THEN 1 ELSE 0 END) AS Pendientes,
                    SUM(CASE WHEN scrape_status LIKE 'failed:%' THEN 1 ELSE 0 END) AS Fallidos
                FROM games_catalog
                GROUP BY season_full, league_name, phase, jornada
                ORDER BY season_full DESC, league_name, phase, jornada
                """,
                conn,
            )

        for frame in (scope_df, jornada_df):
            for column in frame.columns:
                if "Revision" in column or "Scrapeo" in column:
                    frame[column] = frame[column].where(frame[column].notna(), "").astype(str)
        return scope_df, jornada_df

    def get_meta(self, *, season: str | None, league: str | None, phases: list[str] | None, jornadas: list[int] | None) -> dict[str, Any]:
        payload = self._cached_meta(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=32)
    def _cached_meta(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
        return {
            **resolved_scope,
            "teams": self._build_team_options(bundle.teams_df),
            "players": self._build_player_options(bundle.players_df),
        }

    def get_database_summary(self) -> dict[str, Any]:
        db_signature = self._db_signature()
        payload = deepcopy(self._cached_database_summary(db_signature))
        payload["dataHealth"] = deepcopy(self._cached_database_health(db_signature))
        payload["reportLibrary"] = deepcopy(self._cached_report_library(self._report_library_signature()))
        return payload

    @lru_cache(maxsize=8)
    def _cached_database_summary(self, db_signature: tuple[str, int, int]) -> dict[str, Any]:
        scope_df, jornada_df = self._load_scope_tables()
        auto_config = load_auto_sync_config()
        auto_targets = iter_enabled_targets(auto_config)
        auto_target_rows = [
            {
                "Temporada": target["season"],
                "Liga": target["league"],
                "Fases": ", ".join(target.get("phases", [])),
                "Jornadas": ", ".join(str(value) for value in target.get("jornadas", [])) or "todas",
            }
            for target in auto_targets
        ]
        metrics = {
            "scopes": int(scope_df.shape[0]),
            "jornadas": int(jornada_df.shape[0]),
            "catalogedGames": int(pd.to_numeric(scope_df.get("PartidosCatalogados", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
            "withData": int(pd.to_numeric(scope_df.get("ConDatos", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
            "pending": int(pd.to_numeric(scope_df.get("Pendientes", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
            "failed": int(pd.to_numeric(scope_df.get("Fallidos", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
        }
        return {
            "metrics": metrics,
            "scopeSummary": _to_records(scope_df),
            "jornadaSummary": _to_records(jornada_df),
            "autoSyncTargets": auto_target_rows,
            "autoSync": {
                "configPath": str(AUTO_SYNC_TARGETS_FILE),
                "revalidateWindow": int(auto_config.get("revalidate_window", 2)),
                "publish": bool(auto_config.get("publish", True)),
                "targetCount": len(auto_target_rows),
            },
        }

    def _report_library_signature(self) -> tuple[tuple[str, int, int], ...]:
        signature: list[tuple[str, int, int]] = []
        for kind, directory in REPORT_DIRECTORIES.items():
            if not directory.exists():
                signature.append((kind, 0, 0))
                continue
            files = [entry for entry in directory.iterdir() if entry.is_file()]
            latest_mtime_ns = max((int(entry.stat().st_mtime_ns) for entry in files), default=0)
            signature.append((kind, len(files), latest_mtime_ns))
        return tuple(signature)

    @lru_cache(maxsize=8)
    def _cached_report_library(self, report_signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
        recent_candidates: list[tuple[int, dict[str, Any]]] = []
        total_size_bytes = 0
        metrics = {
            "totalFiles": 0,
            "playerFiles": 0,
            "teamFiles": 0,
            "phaseFiles": 0,
            "totalSizeBytes": 0,
            "latestGeneratedAt": None,
            "latestFileName": None,
        }

        for kind, directory in REPORT_DIRECTORIES.items():
            files = sorted(
                [entry for entry in directory.iterdir() if entry.is_file()],
                key=lambda entry: entry.stat().st_mtime_ns,
                reverse=True,
            ) if directory.exists() else []
            metrics[f"{kind}Files"] = len(files)
            metrics["totalFiles"] += len(files)
            for entry in files:
                stat = entry.stat()
                total_size_bytes += int(stat.st_size)
                recent_candidates.append((int(stat.st_mtime_ns), self._build_report_file_payload(entry, kind)))

        recent_candidates.sort(key=lambda item: item[0], reverse=True)
        recent_files = [payload for _, payload in recent_candidates[:12]]
        latest_file = recent_files[0] if recent_files else None
        metrics["totalSizeBytes"] = total_size_bytes
        metrics["latestGeneratedAt"] = latest_file.get("generatedAt") if latest_file else None
        metrics["latestFileName"] = latest_file.get("fileName") if latest_file else None
        return {
            "metrics": metrics,
            "recentFiles": recent_files,
        }

    @lru_cache(maxsize=8)
    def _cached_database_health(self, db_signature: tuple[str, int, int]) -> dict[str, Any]:
        base_payload = {
            "metrics": {
                "uniquePlayers": 0,
                "uniqueTeams": 0,
                "playedGames": 0,
                "playersMissingBirthDate": 0,
                "playersMissingDorsal": 0,
                "gamesWithoutBoxscore": 0,
                "gamesWithClutch": 0,
                "gamesWithLineups": 0,
                "assistRows": 0,
                "clutchPlayerRows": 0,
                "clutchLineupRows": 0,
            },
            "coverage": {
                "birthDatePct": 0.0,
                "dorsalPct": 0.0,
                "boxscorePct": 0.0,
                "clutchGamesPct": 0.0,
                "lineupGamesPct": 0.0,
            },
            "issues": [],
        }
        if not Path(self.db_path).exists():
            return base_payload

        store = self._get_store()
        with store.connect() as conn:
            counts = conn.execute(
                """
                SELECT
                    (SELECT COUNT(DISTINCT player_key) FROM boxscores) AS unique_players,
                    (
                        SELECT COUNT(DISTINCT team_name)
                        FROM (
                            SELECT local_team AS team_name FROM games_catalog WHERE TRIM(COALESCE(local_team, '')) <> ''
                            UNION
                            SELECT away_team AS team_name FROM games_catalog WHERE TRIM(COALESCE(away_team, '')) <> ''
                        )
                    ) AS unique_teams,
                    (SELECT COUNT(*) FROM games_catalog WHERE played = 1) AS played_games,
                    (SELECT COUNT(DISTINCT game_id) FROM boxscores) AS games_with_boxscore,
                    (SELECT COUNT(DISTINCT game_id) FROM clutch_player) AS games_with_clutch,
                    (SELECT COUNT(DISTINCT game_id) FROM clutch_lineups) AS games_with_lineups,
                    (
                        SELECT COUNT(DISTINCT bs.player_key)
                        FROM boxscores bs
                        JOIN player_bios pb ON pb.player_key = bs.player_key
                        WHERE TRIM(COALESCE(pb.birth_date, '')) <> ''
                    ) AS players_with_birth_date,
                    (SELECT COUNT(DISTINCT player_key) FROM boxscores WHERE TRIM(COALESCE(jersey, '')) <> '') AS players_with_dorsal,
                    (SELECT COUNT(*) FROM assists) AS assist_rows,
                    (SELECT COUNT(*) FROM clutch_player) AS clutch_player_rows,
                    (SELECT COUNT(*) FROM clutch_lineups) AS clutch_lineup_rows,
                    (SELECT SUM(CASE WHEN scrape_status = 'pending' THEN 1 ELSE 0 END) FROM games_catalog) AS pending_games,
                    (SELECT SUM(CASE WHEN scrape_status LIKE 'failed:%' THEN 1 ELSE 0 END) FROM games_catalog) AS failed_games
                """
            ).fetchone()

        unique_players = int(counts["unique_players"] or 0)
        unique_teams = int(counts["unique_teams"] or 0)
        played_games = int(counts["played_games"] or 0)
        games_with_boxscore = int(counts["games_with_boxscore"] or 0)
        games_with_clutch = int(counts["games_with_clutch"] or 0)
        games_with_lineups = int(counts["games_with_lineups"] or 0)
        players_with_birth_date = int(counts["players_with_birth_date"] or 0)
        players_with_dorsal = int(counts["players_with_dorsal"] or 0)
        pending_games = int(counts["pending_games"] or 0)
        failed_games = int(counts["failed_games"] or 0)

        players_missing_birth_date = max(unique_players - players_with_birth_date, 0)
        players_missing_dorsal = max(unique_players - players_with_dorsal, 0)
        games_without_boxscore = max(played_games - games_with_boxscore, 0)

        def _coverage(part: int, total: int) -> float:
            return round((part / total) * 100.0, 1) if total > 0 else 0.0

        birth_date_pct = _coverage(players_with_birth_date, unique_players)
        dorsal_pct = _coverage(players_with_dorsal, unique_players)
        boxscore_pct = _coverage(games_with_boxscore, played_games)
        clutch_games_pct = _coverage(games_with_clutch, played_games)
        lineup_games_pct = _coverage(games_with_lineups, played_games)

        def _build_issue(key: str, label: str, value: int, hint: str, *, status: str) -> dict[str, Any]:
            status_label = {
                "ok": "OK",
                "watch": "Vigilar",
                "warning": "Revisar",
            }.get(status, "Info")
            return {
                "key": key,
                "label": label,
                "value": int(value),
                "hint": hint,
                "status": status,
                "statusLabel": status_label,
            }

        issues = [
            _build_issue(
                "players_missing_birth_date",
                "Jugadores sin fecha de nacimiento",
                players_missing_birth_date,
                "Conviene completarlo para scouting, edad y contexto de potencial.",
                status="ok" if players_missing_birth_date == 0 else ("watch" if birth_date_pct >= 85.0 else "warning"),
            ),
            _build_issue(
                "players_missing_dorsal",
                "Jugadores sin dorsal",
                players_missing_dorsal,
                "Afecta a tablas, clutch y lectura rapida de informes.",
                status="ok" if players_missing_dorsal == 0 else ("watch" if dorsal_pct >= 92.0 else "warning"),
            ),
            _build_issue(
                "games_without_boxscore",
                "Partidos jugados sin boxscore",
                games_without_boxscore,
                "Si este numero sube, la cobertura real del scope se resiente aunque el partido este catalogado.",
                status="ok" if games_without_boxscore == 0 else "warning",
            ),
            _build_issue(
                "pending_games",
                "Partidos pendientes de scrapeo",
                pending_games,
                "Sirve para revisar si el autosync dominical ha dejado trabajo a medias.",
                status="ok" if pending_games == 0 else "watch",
            ),
            _build_issue(
                "failed_games",
                "Partidos con fallo registrado",
                failed_games,
                "Estos casos suelen merecer revision manual antes del siguiente publish.",
                status="ok" if failed_games == 0 else "warning",
            ),
        ]

        return {
            "metrics": {
                "uniquePlayers": unique_players,
                "uniqueTeams": unique_teams,
                "playedGames": played_games,
                "playersMissingBirthDate": players_missing_birth_date,
                "playersMissingDorsal": players_missing_dorsal,
                "gamesWithoutBoxscore": games_without_boxscore,
                "gamesWithClutch": games_with_clutch,
                "gamesWithLineups": games_with_lineups,
                "assistRows": int(counts["assist_rows"] or 0),
                "clutchPlayerRows": int(counts["clutch_player_rows"] or 0),
                "clutchLineupRows": int(counts["clutch_lineup_rows"] or 0),
            },
            "coverage": {
                "birthDatePct": birth_date_pct,
                "dorsalPct": dorsal_pct,
                "boxscorePct": boxscore_pct,
                "clutchGamesPct": clutch_games_pct,
                "lineupGamesPct": lineup_games_pct,
            },
            "issues": issues,
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
        payload = self._cached_gm_players(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
            mode,
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_gm_players(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
        mode: str,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
        gm_df = build_gm_players_view(bundle.players_df, mode, bundle.teams_df)
        if "PUNTOS" in gm_df.columns:
            gm_df = gm_df.sort_values(by=["PUNTOS", "JUGADOR"], ascending=[False, True], na_position="last").reset_index(drop=True)
        visible_columns = [column for column in gm_df.columns if column not in {"PLAYER_KEY", "DORSAL", "IMAGEN"}]
        return {
            "scope": resolved_scope["selected"],
            "mode": mode,
            "columns": visible_columns,
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
        payload = self._cached_dependency_players(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_dependency_players(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
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
        payload = self._cached_dependency_team_summary(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
            team,
            player_key,
        )
        return deepcopy(payload)

    @lru_cache(maxsize=128)
    def _cached_dependency_team_summary(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
        team: str | None,
        player_key: str | None,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
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
            "birthYear": _extract_birth_year(player_meta.iloc[0]["AÑO NACIMIENTO"] if not player_meta.empty and "AÑO NACIMIENTO" in player_meta.columns else None),
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
        payload = self._cached_player_trends(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
            player_key,
            _coerce_int(window, 0),
            tuple(str(metric) for metric in (metrics or [])),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=128)
    def _cached_player_trends(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
        player_key: str | None,
        window: int,
        metrics: tuple[str, ...],
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
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
        payload = self._cached_team_trends(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
            team,
            _coerce_int(window, 0),
            tuple(str(metric) for metric in (metrics or [])),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=128)
    def _cached_team_trends(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
        team: str | None,
        window: int,
        metrics: tuple[str, ...],
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
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

    def generate_player_report(
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
        if bundle.players_df.empty:
            raise ValueError("No hay jugadores disponibles para generar el informe.")

        players_source = bundle.players_df
        selected_team = str(team).strip() if team else "Todos"
        if selected_team and selected_team != "Todos" and "EQUIPO" in players_source.columns:
            players_source = players_source[players_source["EQUIPO"].astype(str) == selected_team].copy()

        selectable_players = (
            players_source[[column for column in ["PLAYER_KEY", "JUGADOR", "EQUIPO", "DORSAL"] if column in players_source.columns]]
            .dropna(subset=["PLAYER_KEY", "JUGADOR"])
            .drop_duplicates(subset=["PLAYER_KEY"])
            .sort_values(by=["JUGADOR", "EQUIPO"])
        )
        if selectable_players.empty:
            raise ValueError("No hay jugadores disponibles para el equipo seleccionado.")

        available_keys = selectable_players["PLAYER_KEY"].astype(str).tolist()
        selected_player_key = player_key if player_key in available_keys else available_keys[0]
        player_row = selectable_players[selectable_players["PLAYER_KEY"].astype(str) == str(selected_player_key)].iloc[0]
        player_name = str(player_row["JUGADOR"])
        label = _build_player_selection_label(player_row["JUGADOR"], player_row.get("EQUIPO"), player_row.get("DORSAL"))
        report_players_df = bundle.players_df.copy()
        report_teams_df = bundle.teams_df.copy()
        report_clutch_df = bundle.clutch_df.copy()
        try:
            path = Path(
                _call_silently(
                    _get_player_report_fn(),
                    player_name,
                    output_dir=PLAYER_REPORTS_DIR,
                    overwrite=True,
                    data_df=report_players_df,
                    teams_df=report_teams_df,
                    clutch_df=report_clutch_df,
                )
            )
        finally:
            del report_players_df, report_teams_df, report_clutch_df
            gc.collect()

        return {
            "scope": resolved_scope["selected"],
            "selectedTeam": selected_team,
            "selectedPlayerKey": str(selected_player_key),
            "playerName": player_name,
            "playerLabel": label,
            "report": self._build_report_file_payload(path, "player"),
        }

    def generate_team_report(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        team: str | None,
        player_keys: list[str] | None,
        rival_team: str | None,
        home_away: str,
        h2h_home_away: str,
        min_games: int,
        min_minutes: int,
        min_shots: int,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        if bundle.players_df.empty or bundle.teams_df.empty:
            raise ValueError("No hay datos de equipo suficientes para generar el informe.")

        teams = sorted(bundle.teams_df["EQUIPO"].dropna().astype(str).unique().tolist())
        if not teams:
            raise ValueError("No hay equipos disponibles en el scope actual.")
        selected_team = team if team in teams else teams[0]

        team_players_source = (
            bundle.players_df[bundle.players_df["EQUIPO"].astype(str) == str(selected_team)][
                [column for column in ["PLAYER_KEY", "JUGADOR"] if column in bundle.players_df.columns]
            ]
            .dropna(subset=["PLAYER_KEY", "JUGADOR"])
            .drop_duplicates(subset=["PLAYER_KEY"])
            .sort_values(by=["JUGADOR"])
        )
        valid_player_keys = {str(value) for value in team_players_source["PLAYER_KEY"].astype(str).tolist()}
        selected_player_keys = [str(value) for value in (player_keys or []) if str(value) in valid_player_keys]
        selected_player_names = (
            team_players_source[team_players_source["PLAYER_KEY"].astype(str).isin(selected_player_keys)]["JUGADOR"]
            .dropna()
            .astype(str)
            .tolist()
        )
        valid_rivals = [value for value in teams if value != selected_team]
        selected_rival = rival_team if rival_team in valid_rivals else None
        resolved_home_away = home_away if home_away in {"Todos", "Local", "Visitante"} else "Todos"
        resolved_h2h_home_away = h2h_home_away if h2h_home_away in {"Todos", "Local", "Visitante"} else "Todos"

        report_players_df = bundle.players_df.copy()
        report_teams_df = bundle.teams_df.copy()
        report_assists_df = bundle.assists_df.copy()
        report_games_df = bundle.games_df.copy()
        report_boxscores_df = bundle.boxscores_df.copy()
        report_clutch_games_df = bundle.clutch_games_df.copy()
        report_clutch_lineups_df = bundle.clutch_lineups_df.copy()
        try:
            path = Path(
                _call_silently(
                    _get_team_report_fn(),
                    team_filter=selected_team if not selected_player_names else None,
                    player_filter=selected_player_names or None,
                    rival_team=selected_rival,
                    home_away_filter=resolved_home_away,
                    h2h_home_away_filter=resolved_h2h_home_away,
                    min_games=_coerce_int(min_games, 5, minimum=0, maximum=100),
                    min_minutes=_coerce_int(min_minutes, 50, minimum=0, maximum=500),
                    min_shots=_coerce_int(min_shots, 20, minimum=0, maximum=300),
                    players_df=report_players_df,
                    teams_df=report_teams_df,
                    assists_df=report_assists_df,
                    games_df=report_games_df,
                    boxscores_df=report_boxscores_df,
                    clutch_games_df=report_clutch_games_df,
                    clutch_lineups_df=report_clutch_lineups_df,
                )
            )
        finally:
            del report_players_df, report_teams_df, report_assists_df, report_games_df, report_boxscores_df, report_clutch_games_df, report_clutch_lineups_df
            gc.collect()

        return {
            "scope": resolved_scope["selected"],
            "selectedTeam": selected_team,
            "selectedPlayerKeys": selected_player_keys,
            "selectedPlayerNames": selected_player_names,
            "rivalTeam": selected_rival,
            "filters": {
                "homeAway": resolved_home_away,
                "h2hHomeAway": resolved_h2h_home_away,
                "minGames": _coerce_int(min_games, 5, minimum=0, maximum=100),
                "minMinutes": _coerce_int(min_minutes, 50, minimum=0, maximum=500),
                "minShots": _coerce_int(min_shots, 20, minimum=0, maximum=300),
            },
            "report": self._build_report_file_payload(path, "team"),
        }

    def generate_phase_report(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        teams: list[str] | None,
        min_games: int,
        min_minutes: int,
        min_shots: int,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope)
        if bundle.players_df.empty or bundle.teams_df.empty:
            raise ValueError("No hay datos de fase suficientes para generar el informe.")

        available_teams = sorted(bundle.teams_df["EQUIPO"].dropna().astype(str).unique().tolist())
        selected_teams = [str(value) for value in (teams or []) if str(value) in available_teams]
        report_teams_df = bundle.teams_df.copy()
        report_players_df = bundle.players_df.copy()
        try:
            path = Path(
                _call_silently(
                    _get_phase_report_fn(),
                    teams=selected_teams or None,
                    phase=None,
                    min_games=_coerce_int(min_games, 5, minimum=0, maximum=100),
                    min_minutes=_coerce_int(min_minutes, 50, minimum=0, maximum=500),
                    min_shots=_coerce_int(min_shots, 20, minimum=0, maximum=300),
                    teams_df=report_teams_df,
                    players_df=report_players_df,
                )
            )
        finally:
            del report_teams_df, report_players_df
            gc.collect()

        return {
            "scope": resolved_scope["selected"],
            "selectedTeams": selected_teams,
            "filters": {
                "minGames": _coerce_int(min_games, 5, minimum=0, maximum=100),
                "minMinutes": _coerce_int(min_minutes, 50, minimum=0, maximum=500),
                "minShots": _coerce_int(min_shots, 20, minimum=0, maximum=300),
            },
            "report": self._build_report_file_payload(path, "phase"),
        }

    def get_player_similarity(
        self,
        *,
        season: str | None,
        league: str | None,
        phases: list[str] | None,
        jornadas: list[int] | None,
        target_player_key: str | None,
        min_games: int,
        min_minutes: float,
    ) -> dict[str, Any]:
        payload = self._cached_player_similarity(
            self._db_signature(),
            season,
            league,
            self._normalize_phases(phases),
            self._normalize_jornadas(jornadas),
            target_player_key,
            _coerce_int(min_games, 5, minimum=0, maximum=100),
            float(min_minutes if min_minutes is not None else 10.0),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=128)
    def _cached_player_similarity(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        league: str | None,
        phases: tuple[str, ...],
        jornadas: tuple[int, ...],
        target_player_key: str | None,
        min_games: int,
        min_minutes: float,
    ) -> dict[str, Any]:
        resolved_scope = self._resolve_scope(ScopeFilters(season=season, league=league, phases=phases, jornadas=jornadas))
        bundle = self._load_bundle(resolved_scope, db_signature)
        gm_df = build_gm_players_view(bundle.players_df, "Promedios", bundle.teams_df)
        dependency_df = build_dependency_players_view(bundle)
        similarity_pool = build_similarity_player_pool(bundle, gm_df, dependency_df)
        player_options = self._build_player_options(bundle.players_df)
        available_keys = [str(option["playerKey"]) for option in player_options]
        selected_player_key = target_player_key if target_player_key in available_keys else (available_keys[0] if available_keys else None)
        similarity_result = build_player_similarity_results(
            similarity_pool,
            str(selected_player_key or ""),
            min_games=min_games,
            min_minutes=max(float(min_minutes), 0.0),
            limit=10,
        )

        target = similarity_result.get("target")
        if target:
            target = {
                "playerKey": str(target.get("PLAYER_KEY") or ""),
                "label": _build_player_selection_label(target.get("JUGADOR"), target.get("EQUIPO"), target.get("DORSAL")),
                "name": str(target.get("JUGADOR") or ""),
                "team": str(target.get("EQUIPO") or ""),
                "image": _resolve_image(target.get("IMAGEN")),
                "gamesPlayed": int(pd.to_numeric(pd.Series([target.get("PJ")]), errors="coerce").fillna(0).iloc[0]),
                "minutes": float(pd.to_numeric(pd.Series([target.get("MINUTOS JUGADOS")]), errors="coerce").fillna(0.0).iloc[0]),
                "points": float(pd.to_numeric(pd.Series([target.get("PUNTOS")]), errors="coerce").fillna(0.0).iloc[0]),
                "rebounds": float(pd.to_numeric(pd.Series([target.get("REB TOTALES")]), errors="coerce").fillna(0.0).iloc[0]),
                "assists": float(pd.to_numeric(pd.Series([target.get("ASISTENCIAS")]), errors="coerce").fillna(0.0).iloc[0]),
                "turnovers": float(pd.to_numeric(pd.Series([target.get("PERDIDAS")]), errors="coerce").fillna(0.0).iloc[0]),
                "usg": float(pd.to_numeric(pd.Series([target.get("USG%")]), errors="coerce").fillna(0.0).iloc[0]),
                "efg": float(pd.to_numeric(pd.Series([target.get("eFG%")]), errors="coerce").fillna(0.0).iloc[0]),
                "astTo": float(pd.to_numeric(pd.Series([target.get("AST/TO")]), errors="coerce").fillna(0.0).iloc[0]),
                "focus": str(target.get("FOCO_PRINCIPAL") or ""),
                "dependencyScore": float(pd.to_numeric(pd.Series([target.get("DEPENDENCIA_SCORE")]), errors="coerce").fillna(0.0).iloc[0]),
            }

        candidates = []
        for candidate in similarity_result.get("candidates", []):
            candidates.append(
                {
                    "playerKey": str(candidate.get("PLAYER_KEY") or ""),
                    "label": _build_player_selection_label(candidate.get("JUGADOR"), candidate.get("EQUIPO"), candidate.get("DORSAL")),
                    "name": str(candidate.get("JUGADOR") or ""),
                    "team": str(candidate.get("EQUIPO") or ""),
                    "image": _resolve_image(candidate.get("IMAGEN")),
                    "gamesPlayed": int(pd.to_numeric(pd.Series([candidate.get("PJ")]), errors="coerce").fillna(0).iloc[0]),
                    "minutes": float(pd.to_numeric(pd.Series([candidate.get("MINUTOS JUGADOS")]), errors="coerce").fillna(0.0).iloc[0]),
                    "points": float(pd.to_numeric(pd.Series([candidate.get("PUNTOS")]), errors="coerce").fillna(0.0).iloc[0]),
                    "rebounds": float(pd.to_numeric(pd.Series([candidate.get("REB TOTALES")]), errors="coerce").fillna(0.0).iloc[0]),
                    "assists": float(pd.to_numeric(pd.Series([candidate.get("ASISTENCIAS")]), errors="coerce").fillna(0.0).iloc[0]),
                    "usg": float(pd.to_numeric(pd.Series([candidate.get("USG%")]), errors="coerce").fillna(0.0).iloc[0]),
                    "similarityScore": float(pd.to_numeric(pd.Series([candidate.get("similarityScore")]), errors="coerce").fillna(0.0).iloc[0]),
                    "focus": str(candidate.get("FOCO_PRINCIPAL") or ""),
                    "dependencyScore": float(pd.to_numeric(pd.Series([candidate.get("DEPENDENCIA_SCORE")]), errors="coerce").fillna(0.0).iloc[0]),
                    "reasons": list(candidate.get("reasons") or []),
                    "differences": list(candidate.get("differences") or []),
                }
            )

        return {
            "scope": resolved_scope["selected"],
            "target": target,
            "filters": {
                "minGames": min_games,
                "minMinutes": round(max(float(min_minutes), 0.0), 1),
            },
            "featureWeights": resolve_similarity_feature_weights(),
            "candidates": candidates,
            "players": player_options,
        }

    def get_market_pool(
        self,
        *,
        season: str | None,
        leagues: list[str] | None,
        min_games: int,
        min_minutes: float,
        query: str | None,
    ) -> dict[str, Any]:
        payload = self._cached_market_pool(
            self._db_signature(),
            season,
            tuple(str(value or "").strip() for value in (leagues or [])),
            _coerce_int(min_games, 5, minimum=0, maximum=100),
            max(float(min_minutes if min_minutes is not None else 10.0), 0.0),
            str(query or "").strip(),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_market_pool(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        leagues: tuple[str, ...],
        min_games: int,
        min_minutes: float,
        query: str,
    ) -> dict[str, Any]:
        context = self._cached_market_pool_context(db_signature, season, leagues)
        filtered_pool = filter_market_pool(
            context["pool"],
            min_games=min_games,
            min_minutes=min_minutes,
            query=query,
        )
        rows = []
        for row in _to_records(filtered_pool):
            rows.append(
                {
                    "PLAYER_KEY": row.get("PLAYER_KEY"),
                    "IMAGEN": _resolve_image(row.get("IMAGEN")),
                    "JUGADOR": row.get("JUGADOR"),
                    "EQUIPO": row.get("EQUIPO"),
                    "LIGA": row.get("LIGA"),
                    "AÑO NACIMIENTO": _extract_birth_year(row.get("AÑO NACIMIENTO")),
                    "PJ": row.get("PJ"),
                    "MIN": row.get("MINUTOS JUGADOS"),
                    "PTS": row.get("PUNTOS"),
                    "REB": row.get("REB TOTALES"),
                    "AST": row.get("ASISTENCIAS"),
                    "TOV": row.get("PERDIDAS"),
                    "PLAYS": row.get("PLAYS"),
                    "USG%": row.get("USG%"),
                    "TS%": row.get("TS%"),
                    "eFG%": row.get("eFG%"),
                    "PPP": row.get("PPP"),
                    "AST/TO": row.get("AST/TO"),
                    "%PLAYS_EQUIPO": row.get("%PLAYS_EQUIPO"),
                    "%PUNTOS_EQUIPO": row.get("%PUNTOS_EQUIPO"),
                    "%AST_EQUIPO": row.get("%AST_EQUIPO"),
                    "%REB_EQUIPO": row.get("%REB_EQUIPO"),
                    "DEPENDENCIA_SCORE": row.get("DEPENDENCIA_SCORE"),
                    "FOCO_PRINCIPAL": row.get("FOCO_PRINCIPAL"),
                }
            )

        return {
            "season": context["season"],
            "availableLeagues": context["availableLeagues"],
            "selectedLeagues": context["selectedLeagues"],
            "rows": rows,
            "summary": self._build_market_summary(
                filtered_pool,
                selected_leagues=context["selectedLeagues"],
                min_games=min_games,
                min_minutes=min_minutes,
                query=query,
            ),
        }

    def get_market_compare(
        self,
        *,
        season: str | None,
        leagues: list[str] | None,
        player_keys: list[str] | None,
    ) -> dict[str, Any]:
        payload = self._cached_market_compare(
            self._db_signature(),
            season,
            tuple(str(value or "").strip() for value in (leagues or [])),
            tuple(str(value or "").strip() for value in (player_keys or [])),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_market_compare(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        leagues: tuple[str, ...],
        player_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        context = self._cached_market_pool_context(db_signature, season, leagues)
        compare_result = build_market_compare_results(context["pool"], list(player_keys))
        return {
            "season": context["season"],
            "availableLeagues": context["availableLeagues"],
            "selectedLeagues": context["selectedLeagues"],
            **compare_result,
        }

    def get_market_suggestions(
        self,
        *,
        season: str | None,
        leagues: list[str] | None,
        anchor_player_key: str | None,
        limit: int,
        weights: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._cached_market_suggestions(
            self._db_signature(),
            season,
            tuple(str(value or "").strip() for value in (leagues or [])),
            str(anchor_player_key or "").strip(),
            _coerce_int(limit, 6, minimum=1, maximum=10),
            self._normalize_similarity_weight_overrides(weights),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_market_suggestions(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        leagues: tuple[str, ...],
        anchor_player_key: str,
        limit: int,
        weights: tuple[tuple[str, float], ...],
    ) -> dict[str, Any]:
        context = self._cached_market_pool_context(db_signature, season, leagues)
        resolved_weights = resolve_similarity_feature_weights(dict(weights) if weights else None)
        if not anchor_player_key:
            return {
                "season": context["season"],
                "availableLeagues": context["availableLeagues"],
                "selectedLeagues": context["selectedLeagues"],
                "availableMetrics": get_similarity_feature_catalog(),
                "featureWeights": resolved_weights,
                "anchor": None,
                "candidates": [],
            }

        similarity_result = build_player_similarity_results(
            context["pool"],
            anchor_player_key,
            min_games=5,
            min_minutes=10.0,
            limit=limit,
            feature_weights=resolved_weights,
        )
        target = similarity_result.get("target")
        candidates = []
        for candidate in similarity_result.get("candidates", []):
            candidates.append(
                {
                    **self._build_market_player_payload(candidate),
                    "similarityScore": float(pd.to_numeric(pd.Series([candidate.get("similarityScore")]), errors="coerce").fillna(0.0).iloc[0]),
                    "reasons": list(candidate.get("reasons") or []),
                    "differences": list(candidate.get("differences") or []),
                }
            )

        return {
            "season": context["season"],
            "availableLeagues": context["availableLeagues"],
            "selectedLeagues": context["selectedLeagues"],
            "availableMetrics": get_similarity_feature_catalog(),
            "featureWeights": resolved_weights,
            "anchor": self._build_market_player_payload(target) if target else None,
            "candidates": candidates,
        }

    def get_market_opportunity(
        self,
        *,
        season: str | None,
        leagues: list[str] | None,
        min_games: int,
        max_minutes: float,
        max_usg: float,
        query: str | None,
    ) -> dict[str, Any]:
        payload = self._cached_market_opportunity(
            self._db_signature(),
            season,
            tuple(str(value or "").strip() for value in (leagues or [])),
            _coerce_int(min_games, 5, minimum=0, maximum=100),
            max(float(max_minutes if max_minutes is not None else 22.0), 0.0),
            max(float(max_usg if max_usg is not None else 24.0), 0.0),
            str(query or "").strip(),
        )
        return deepcopy(payload)

    @lru_cache(maxsize=64)
    def _cached_market_opportunity(
        self,
        db_signature: tuple[str, int, int],
        season: str | None,
        leagues: tuple[str, ...],
        min_games: int,
        max_minutes: float,
        max_usg: float,
        query: str,
    ) -> dict[str, Any]:
        context = self._cached_market_pool_context(db_signature, season, leagues)
        results = build_market_opportunity_results(
            context["pool"],
            min_games=min_games,
            max_minutes=max_minutes,
            max_usg=max_usg,
            query=query,
        )
        return {
            "season": context["season"],
            "availableLeagues": context["availableLeagues"],
            "selectedLeagues": context["selectedLeagues"],
            "filters": results["summary"]["filters"],
            "summary": results["summary"],
            "rows": results["rows"],
        }
