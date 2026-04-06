from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
from unidecode import unidecode

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from config import (
    APP_MODE_CLOUD,
    APP_MODE_ENV_VAR,
    APP_MODE_LOCAL,
    AUTO_SYNC_TARGETS_FILE,
    DATA_DIR,
    DEFAULT_SYNC_TASK_NAME,
    DEFAULT_SYNC_DAY,
    DEFAULT_SYNC_TIME,
    GENERIC_PLAYER_IMAGE,
    LIGAS_DISPONIBLES,
    PLAYER_REPORTS_DIR,
    SQLITE_DB_FILE,
    SYNC_RUNTIME_STATUS_FILE,
    TEMPORADAS_DISPONIBLES,
    get_liga_fases,
)
from storage import DataStore, ReportBundle, ReportFilters, SyncSummary
from utils.auto_sync import expand_targets_by_phase, iter_enabled_targets, load_auto_sync_config, save_auto_sync_config, target_label
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
from utils.sync_runtime import (
    SyncAlreadyRunningError,
    SyncExecutionLock,
    SyncRuntimeTracker,
    get_scheduled_task_status,
    load_runtime_status,
    parse_iso_datetime,
    runtime_status_is_live,
)


REPO_ROOT = Path(__file__).resolve().parent

GM_SCOPE_SEASON_KEY = "gm_scope_season"
GM_SCOPE_LEAGUE_KEY = "gm_scope_league"
GM_SCOPE_PHASES_KEY = "gm_scope_phases"
GM_SCOPE_JORNADAS_KEY = "gm_scope_jornadas"
GM_MODE_KEY = "gm_mode"
APP_PAGE_KEY = "app_active_page"
GM_NATIONALITIES_KEY = "gm_nationalities"
GM_BIRTH_RANGE_KEY = "gm_birth_range"
GM_SELECTED_PLAYER_KEY = "gm_selected_player"
GM_REPORT_PATH_KEY = "gm_player_report_path"
GM_RULE_IDS_KEY = "gm_rule_ids"
GM_RULE_NEXT_ID_KEY = "gm_rule_next_id"
GM_VISIBLE_COLUMNS_KEY = "gm_visible_columns"
GM_SORT_COLUMN_KEY = "gm_sort_column"
DEP_SCOPE_SEASON_KEY = "dep_scope_season"
DEP_SCOPE_LEAGUE_KEY = "dep_scope_league"
DEP_SCOPE_PHASES_KEY = "dep_scope_phases"
DEP_SCOPE_JORNADAS_KEY = "dep_scope_jornadas"
DEP_SELECTED_TEAM_KEY = "dep_selected_team"
DEP_SELECTED_PLAYER_KEY = "dep_selected_player"
TREND_SCOPE_SEASON_KEY = "trend_scope_season"
TREND_SCOPE_LEAGUE_KEY = "trend_scope_league"
TREND_SCOPE_PHASES_KEY = "trend_scope_phases"
TREND_SCOPE_JORNADAS_KEY = "trend_scope_jornadas"
TREND_SELECTED_PLAYER_KEY = "trend_selected_player"
TREND_SELECTED_TEAM_KEY = "trend_selected_team"
TREND_PLAYER_CHART_METRICS_KEY = "trend_player_chart_metrics"
TREND_TEAM_CHART_METRICS_KEY = "trend_team_chart_metrics"
TREND_PLAYER_WINDOW_KEY = "trend_player_window"
TREND_TEAM_WINDOW_KEY = "trend_team_window"
GM_BIRTH_YEAR_COLUMN = "AÑO NACIMIENTO"
GM_LEGACY_BIRTH_YEAR_COLUMNS = ("ANO NACIMIENTO",)

GM_COUNT_COLUMNS = [
    "MINUTOS JUGADOS",
    "PUNTOS",
    "TL CONVERTIDOS",
    "TL INTENTADOS",
    "T2 CONVERTIDO",
    "T2 INTENTADO",
    "T3 CONVERTIDO",
    "T3 INTENTADO",
    "REB OFFENSIVO",
    "REB DEFENSIVO",
    "ASISTENCIAS",
    "RECUPEROS",
    "PERDIDAS",
    "FaltasCOMETIDAS",
    "FaltasRECIBIDAS",
    "TAPONES",
]
GM_COUNT_DERIVED_COLUMNS = ["FGM", "FGA", "PLAYS", "REB TOTALES"]
GM_RATE_COLUMNS = ["T1%", "T2%", "T3%", "eFG%", "TS%", "PPP", "AST/TO", "TOV%", "USG%"]
GM_RULE_METRICS = [
    "PJ",
    "MINUTOS JUGADOS",
    "PUNTOS",
    "FGM",
    "FGA",
    "PLAYS",
    "REB TOTALES",
    "REB OFFENSIVO",
    "REB DEFENSIVO",
    "ASISTENCIAS",
    "RECUPEROS",
    "PERDIDAS",
    "TAPONES",
    "FaltasCOMETIDAS",
    "FaltasRECIBIDAS",
    "TL CONVERTIDOS",
    "TL INTENTADOS",
    "T2 CONVERTIDO",
    "T2 INTENTADO",
    "T3 CONVERTIDO",
    "T3 INTENTADO",
    "AST/TO",
    "TOV%",
    "USG%",
    "T1%",
    "T2%",
    "T3%",
    "eFG%",
    "TS%",
    "PPP",
]
GM_DEFAULT_RULE_SEQUENCE = ["PUNTOS", "REB TOTALES", "ASISTENCIAS"]
GM_DEFAULT_TABLE_COLUMNS = [
    "JUGADOR",
    "EQUIPO",
    "PJ",
    "NACIONALIDAD",
    GM_BIRTH_YEAR_COLUMN,
    "PUNTOS",
    "REB TOTALES",
    "ASISTENCIAS",
    "MINUTOS JUGADOS",
    "AST/TO",
    "USG%",
    "PPP",
    "TS%",
    "eFG%",
]
GM_DEFAULT_VISIBLE_COLUMNS = [
    "JUGADOR",
    "EQUIPO",
    "PJ",
    "NACIONALIDAD",
    GM_BIRTH_YEAR_COLUMN,
    "PUNTOS",
    "REB TOTALES",
    "ASISTENCIAS",
    "MINUTOS JUGADOS",
    "AST/TO",
    "USG%",
    "PPP",
]
GM_EXPORT_COLUMNS = [
    "JUGADOR",
    "EQUIPO",
    "NACIONALIDAD",
    GM_BIRTH_YEAR_COLUMN,
    *GM_RULE_METRICS,
]

DEPENDENCY_DEFAULT_TABLE_COLUMNS = [
    "JUGADOR",
    "PJ",
    "MINUTOS JUGADOS",
    "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "DEPENDENCIA_SCORE",
    "DEPENDENCIA_RIESGO",
    "FOCO_PRINCIPAL",
]


def get_app_mode() -> str:
    mode = os.getenv(APP_MODE_ENV_VAR, APP_MODE_LOCAL).strip().lower()
    return mode or APP_MODE_LOCAL


def is_cloud_mode() -> bool:
    return get_app_mode() == APP_MODE_CLOUD


def empty_bundle() -> ReportBundle:
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


def serialize_sync_summary(summary: SyncSummary) -> dict[str, Any]:
    return {
        "discovered_games": summary.discovered_games,
        "missing_games": summary.missing_games,
        "refreshed_games": summary.refreshed_games,
        "scraped_games": summary.scraped_games,
        "skipped_games": summary.skipped_games,
        "failed_games": summary.failed_games,
        "changed_scopes": list(summary.changed_scopes),
    }


def parse_jornadas_text(value: str) -> list[int]:
    text = (value or "").replace(";", ",").strip()
    if not text:
        return []
    jornadas = []
    for part in text.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        jornadas.append(int(cleaned))
    return sorted(set(jornadas))


@st.cache_resource
def get_store() -> DataStore:
    return DataStore(SQLITE_DB_FILE)


@st.cache_resource
def get_generate_report_fn():
    from player_report.player_report_gen import generate_report

    return generate_report


@st.cache_resource
def get_build_team_report_fn():
    from team_report.build_team_report import build_team_report

    return build_team_report


@st.cache_resource
def get_build_phase_report_fn():
    from phase_report.build_phase_report import build_phase_report

    return build_phase_report


def get_db_signature() -> tuple[tuple[str, int, int], ...]:
    tracked_paths = [
        SQLITE_DB_FILE,
        SQLITE_DB_FILE.with_name(f"{SQLITE_DB_FILE.name}-wal"),
        SQLITE_DB_FILE.with_name(f"{SQLITE_DB_FILE.name}-shm"),
        SYNC_RUNTIME_STATUS_FILE,
    ]
    signature_parts: list[tuple[str, int, int]] = []
    for path in tracked_paths:
        if path.exists():
            stat = path.stat()
            signature_parts.append((path.name, int(stat.st_mtime_ns), int(stat.st_size)))
        else:
            signature_parts.append((path.name, 0, 0))
    return tuple(signature_parts)


def format_datetime_text(value: Any) -> str:
    dt = parse_iso_datetime(value)
    if dt is None:
        if isinstance(value, str) and value.strip():
            return value
        return "-"
    local_dt = dt.astimezone()
    return local_dt.strftime("%d/%m/%Y %H:%M:%S")


def format_relative_time(value: Any) -> str:
    dt = parse_iso_datetime(value)
    if dt is None:
        return "-"
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _normalize_object_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def query_running_sync_processes() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []

    ps_script = """
    $items = @(Get-CimInstance Win32_Process | Where-Object {
      $_.CommandLine -like '*sync_and_publish.py*'
    } | ForEach-Object {
      [pscustomobject]@{
        pid = $_.ProcessId
        command = $_.CommandLine
        started_at = "$($_.CreationDate)"
      }
    })
    if ($items.Count -eq 0) { exit 0 }
    $items | ConvertTo-Json -Compress
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0 or not (result.stdout or "").strip():
        return []
    try:
        return _normalize_object_list(json.loads(result.stdout))
    except Exception:
        return []


def infer_runtime_status() -> dict[str, Any]:
    processes = query_running_sync_processes()
    if not processes or not SQLITE_DB_FILE.exists():
        return {}

    store = DataStore(SQLITE_DB_FILE)
    with store.connect() as conn:
        last_row = conn.execute(
            """
            SELECT season_full, league_name, phase, jornada, pid, game_label, last_scraped_at
            FROM games_catalog
            WHERE last_scraped_at IS NOT NULL
            ORDER BY last_scraped_at DESC
            LIMIT 1
            """
        ).fetchone()
        pending_rows = conn.execute(
            """
            SELECT season_full, league_name, phase, COUNT(*) AS pending_games, MIN(jornada) AS next_jornada
            FROM games_catalog
            WHERE scrape_status = 'pending'
            GROUP BY season_full, league_name, phase
            ORDER BY season_full DESC, league_name, phase
            """
        ).fetchall()

        next_games: list[dict[str, Any]] = []
        current_scope: dict[str, Any] | None = None
        if last_row is not None:
            next_game_rows = conn.execute(
                """
                SELECT pid, phase, jornada, game_label, local_team, away_team
                FROM games_catalog
                WHERE season_full = ? AND league_name = ? AND phase = ? AND scrape_status = 'pending'
                ORDER BY jornada, id
                LIMIT 5
                """,
                [last_row["season_full"], last_row["league_name"], last_row["phase"]],
            ).fetchall()
            next_games = [
                {
                    "pid": row["pid"],
                    "phase": row["phase"],
                    "jornada": int(row["jornada"] or 0),
                    "game_label": row["game_label"],
                    "local_team": row["local_team"],
                    "away_team": row["away_team"],
                }
                for row in next_game_rows
            ]
            scope_pending = next((row for row in pending_rows if row["league_name"] == last_row["league_name"] and row["phase"] == last_row["phase"] and row["season_full"] == last_row["season_full"]), None)
            current_scope = {
                "label": f"{last_row['league_name']} {last_row['season_full']} | {last_row['phase']}",
                "season": last_row["season_full"],
                "league": last_row["league_name"],
                "phases": [last_row["phase"]],
                "games_total": int(scope_pending["pending_games"] or 0) if scope_pending is not None else 0,
                "games_done": 0,
                "games_success": 0,
                "games_failed": 0,
            }

    if last_row is None:
        return {}

    queued_scopes = [
        f"{row['league_name']} {row['season_full']} | {row['phase']} ({int(row['pending_games'] or 0)} pendientes)"
        for row in pending_rows[:8]
    ]
    primary_process = sorted(processes, key=lambda item: str(item.get("pid")))[0]
    return {
        "status": "running",
        "mode": "inferred",
        "source": "db_snapshot",
        "pid": primary_process.get("pid"),
        "command": primary_process.get("command"),
        "started_at": primary_process.get("started_at"),
        "heartbeat_at": last_row["last_scraped_at"],
        "scope_index": None,
        "scopes_total": None,
        "current_scope": current_scope,
        "current_step": "scraping_game",
        "current_message": f"Estado inferido. Ultimo partido scrapeado: {last_row['game_label']}",
        "current_game": {
            "pid": last_row["pid"],
            "phase": last_row["phase"],
            "jornada": int(last_row["jornada"] or 0),
            "game_label": last_row["game_label"],
        },
        "next_games": next_games,
        "queued_scopes": queued_scopes,
        "recent_events": [
            {
                "timestamp": last_row["last_scraped_at"],
                "level": "info",
                "message": f"Ultimo partido scrapeado: {last_row['game_label']}",
            }
        ],
    }


@st.cache_data(show_spinner=False)
def load_db_summary(_db_signature: tuple[tuple[str, int, int], ...]) -> dict[str, int]:
    if not SQLITE_DB_FILE.exists():
        return {"games": 0, "players": 0, "scopes": 0}
    store = DataStore(SQLITE_DB_FILE)
    with store.connect() as conn:
        games = int(conn.execute("SELECT COUNT(*) FROM games_catalog").fetchone()[0])
        players = int(conn.execute("SELECT COUNT(*) FROM player_bios").fetchone()[0])
        scopes = int(conn.execute("SELECT COUNT(*) FROM imported_scopes").fetchone()[0])
    return {"games": games, "players": players, "scopes": scopes}


@st.cache_data(show_spinner=False)
def load_status_totals(_db_signature: tuple[tuple[str, int, int], ...]) -> dict[str, int]:
    if not SQLITE_DB_FILE.exists():
        return {"success": 0, "imported": 0, "pending": 0, "failed": 0}
    store = DataStore(SQLITE_DB_FILE)
    with store.connect() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN scrape_status = 'success' THEN 1 ELSE 0 END) AS success,
                SUM(CASE WHEN scrape_status = 'imported' THEN 1 ELSE 0 END) AS imported,
                SUM(CASE WHEN scrape_status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN scrape_status LIKE 'failed:%' THEN 1 ELSE 0 END) AS failed
            FROM games_catalog
            """
        ).fetchone()
    return {
        "success": int(row["success"] or 0),
        "imported": int(row["imported"] or 0),
        "pending": int(row["pending"] or 0),
        "failed": int(row["failed"] or 0),
    }


@st.cache_data(show_spinner=False)
def load_scope_summary(_db_signature: tuple[tuple[str, int, int], ...]) -> pd.DataFrame:
    columns = [
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
    if not SQLITE_DB_FILE.exists():
        return pd.DataFrame(columns=columns)

    store = DataStore(SQLITE_DB_FILE)
    with store.connect() as conn:
        df = pd.read_sql_query(
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
    return df


@st.cache_data(show_spinner=False)
def load_jornada_summary(_db_signature: tuple[tuple[str, int, int], ...]) -> pd.DataFrame:
    columns = ["Temporada", "Liga", "Fase", "Jornada", "Partidos", "ConDatos", "Pendientes", "Fallidos"]
    if not SQLITE_DB_FILE.exists():
        return pd.DataFrame(columns=columns)

    store = DataStore(SQLITE_DB_FILE)
    with store.connect() as conn:
        df = pd.read_sql_query(
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
    return df


@st.cache_data(show_spinner=False)
def load_available_seasons(_db_signature: tuple[tuple[str, int, int], ...]) -> list[str]:
    return DataStore(SQLITE_DB_FILE).get_available_seasons()


@st.cache_data(show_spinner=False)
def load_available_leagues(_db_signature: tuple[tuple[str, int, int], ...], season: str) -> list[str]:
    return DataStore(SQLITE_DB_FILE).get_available_leagues(season)


@st.cache_data(show_spinner=False)
def load_available_phases(_db_signature: tuple[tuple[str, int, int], ...], season: str, league: str) -> list[str]:
    return DataStore(SQLITE_DB_FILE).get_available_phases(season, league)


@st.cache_data(show_spinner=False)
def load_available_jornadas(_db_signature: tuple[tuple[str, int, int], ...], season: str, league: str, phases: tuple[str, ...]) -> list[int]:
    return DataStore(SQLITE_DB_FILE).get_available_jornadas(season, league, phases)


@st.cache_data(show_spinner=False)
def load_report_bundle(
    _db_signature: float,
    season: str,
    league: str,
    phases: tuple[str, ...],
    jornadas: tuple[int, ...],
) -> ReportBundle:
    store = DataStore(SQLITE_DB_FILE)
    filters = ReportFilters(season=season, league=league, phases=phases, jornadas=jornadas)
    return store.load_report_bundle(filters)


@st.cache_data(show_spinner=False)
def load_gm_view_data(
    _db_signature: float,
    season: str,
    league: str,
    phases: tuple[str, ...],
    jornadas: tuple[int, ...],
    mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bundle = load_report_bundle(_db_signature, season, league, phases, jornadas)
    gm_df = _normalize_gm_view_columns(build_gm_players_view(bundle.players_df, mode, bundle.teams_df))
    clutch_lookup = _gm_build_clutch_lookup(bundle.clutch_df)
    return gm_df, clutch_lookup


@st.cache_data(show_spinner=False)
def load_dependency_view_data(
    _db_signature: tuple[tuple[str, int, int], ...],
    season: str,
    league: str,
    phases: tuple[str, ...],
    jornadas: tuple[int, ...],
) -> pd.DataFrame:
    bundle = load_report_bundle(_db_signature, season, league, phases, jornadas)
    return build_dependency_players_view(bundle)


def _gm_numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _gm_safe_ratio(numerator: pd.Series, denominator: pd.Series, scale: float = 1.0) -> pd.Series:
    ratio = numerator.div(denominator.replace(0, pd.NA)).mul(scale)
    return pd.to_numeric(ratio, errors="coerce").fillna(0.0)


def _extract_birth_year(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    year = text.split("/")[-1].strip()
    if len(year) == 4 and year.isdigit():
        return int(year)
    return None


def _display_or_dash(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    text = str(value).strip()
    return text or "-"


def _as_float(value: Any) -> float:
    series = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0)
    return float(series.iloc[0])


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
    name_text = _display_or_dash(player_name)
    dorsal_text = _format_optional_dorsal(dorsal)
    prefix = f"{dorsal_text} " if dorsal_text else ""
    team_text = str(team_name).strip() if team_name is not None and not pd.isna(team_name) else ""
    if team_text:
        return f"{prefix}{name_text} | {team_text}"
    return f"{prefix}{name_text}"


def _resolve_player_image_source(image_value: Any) -> str | Path:
    if image_value is not None and not pd.isna(image_value):
        text = str(image_value).strip()
        if text:
            if text.startswith("http://") or text.startswith("https://"):
                return text
            local_path = Path(text)
            if local_path.exists():
                return local_path
    return GENERIC_PLAYER_IMAGE


def _normalize_gm_view_columns(gm_df: pd.DataFrame) -> pd.DataFrame:
    if gm_df.empty:
        if GM_BIRTH_YEAR_COLUMN not in gm_df.columns:
            gm_df = gm_df.copy()
            gm_df[GM_BIRTH_YEAR_COLUMN] = pd.Series(dtype="Int64")
        return gm_df

    normalized = gm_df.copy()
    for legacy_name in GM_LEGACY_BIRTH_YEAR_COLUMNS:
        if GM_BIRTH_YEAR_COLUMN not in normalized.columns and legacy_name in normalized.columns:
            normalized = normalized.rename(columns={legacy_name: GM_BIRTH_YEAR_COLUMN})

    if GM_BIRTH_YEAR_COLUMN not in normalized.columns:
        normalized[GM_BIRTH_YEAR_COLUMN] = pd.Series(pd.NA, index=normalized.index, dtype="Int64")

    return normalized


def _ensure_select_state(key: str, options: list[Any], default_index: int = 0) -> None:
    if not options:
        st.session_state.pop(key, None)
        return
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[min(default_index, len(options) - 1)]


def _ensure_multiselect_state(key: str, options: list[Any]) -> None:
    current = st.session_state.get(key)
    if current is None:
        st.session_state[key] = []
        return
    st.session_state[key] = [value for value in current if value in options]


def _ensure_multiselect_default_state(key: str, options: list[Any], default_values: list[Any]) -> None:
    valid_defaults = [value for value in default_values if value in options]
    current = st.session_state.get(key)
    if not current:
        st.session_state[key] = valid_defaults
        return
    filtered_current = [value for value in current if value in options]
    st.session_state[key] = filtered_current or valid_defaults


def _init_gm_rule_state() -> list[int]:
    rule_ids = st.session_state.get(GM_RULE_IDS_KEY)
    if not rule_ids:
        st.session_state[GM_RULE_IDS_KEY] = [0]
        st.session_state[GM_RULE_NEXT_ID_KEY] = 1
        return [0]
    if GM_RULE_NEXT_ID_KEY not in st.session_state:
        st.session_state[GM_RULE_NEXT_ID_KEY] = max(rule_ids) + 1
    return list(rule_ids)


def _clear_gm_rule_state(rule_id: int) -> None:
    for suffix in ("metric", "min", "max"):
        st.session_state.pop(f"gm_rule_{suffix}_{rule_id}", None)


def _default_gm_metric(position: int) -> str:
    if position < len(GM_DEFAULT_RULE_SEQUENCE):
        return GM_DEFAULT_RULE_SEQUENCE[position]
    return GM_DEFAULT_RULE_SEQUENCE[-1]


def _parse_optional_float(value: Any) -> tuple[float | None, str | None]:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None, None
    try:
        return float(text), None
    except ValueError:
        return None, f"`{value}` no es un numero valido."


def _gm_normalize_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", unidecode(text).upper()).strip()


def _gm_format_name_to_clutch(roster_name: str) -> str:
    name = _gm_normalize_text(roster_name)
    if not name:
        return ""
    if re.match(r"^[A-Z]\.\s", name):
        return name
    if "," in name:
        surnames, names = [part.strip() for part in name.split(",", 1)]
        initial = names.split()[0][0] if names else ""
        return f"{initial}. {surnames}".strip()
    parts = name.split()
    if len(parts) == 1:
        return f"{parts[0][0]}. {parts[0]}"
    initial = parts[0][0]
    surnames = " ".join(parts[1:])
    return f"{initial}. {surnames}"


def _gm_ast_to_ratio(assists: pd.Series, turnovers: pd.Series) -> pd.Series:
    ratio = assists.div(turnovers.replace(0, pd.NA))
    fallback = assists.where((turnovers == 0) & (assists > 0), 0.0)
    return pd.to_numeric(ratio, errors="coerce").fillna(fallback).round(2)


def _gm_build_team_totals_lookup(teams_df: pd.DataFrame) -> pd.DataFrame:
    if teams_df.empty:
        return pd.DataFrame(columns=["EQUIPO", "team_MP", "team_FGA", "team_FTA", "team_TOV"])
    lookup = teams_df.copy()
    lookup["team_MP"] = pd.to_numeric(lookup.get("MINUTOS JUGADOS", 0), errors="coerce").fillna(0.0)
    lookup["team_T2I"] = pd.to_numeric(lookup.get("T2 INTENTADO", 0), errors="coerce").fillna(0.0)
    lookup["team_T3I"] = pd.to_numeric(lookup.get("T3 INTENTADO", 0), errors="coerce").fillna(0.0)
    lookup["team_FTA"] = pd.to_numeric(lookup.get("TL INTENTADOS", 0), errors="coerce").fillna(0.0)
    lookup["team_TOV"] = pd.to_numeric(lookup.get("PERDIDAS", 0), errors="coerce").fillna(0.0)
    lookup["team_FGA"] = lookup["team_T2I"] + lookup["team_T3I"]
    return lookup[["EQUIPO", "team_MP", "team_FGA", "team_FTA", "team_TOV"]].copy()


def _gm_compute_usg(
    teams: pd.Series,
    minutes: pd.Series,
    t1_attempts: pd.Series,
    t2_attempts: pd.Series,
    t3_attempts: pd.Series,
    turnovers: pd.Series,
    teams_df: pd.DataFrame,
) -> pd.Series:
    if teams_df.empty:
        return pd.Series(0.0, index=teams.index, dtype=float)
    team_lookup = _gm_build_team_totals_lookup(teams_df).set_index("EQUIPO")
    team_mp = teams.map(team_lookup["team_MP"]).fillna(0.0)
    team_fga = teams.map(team_lookup["team_FGA"]).fillna(0.0)
    team_fta = teams.map(team_lookup["team_FTA"]).fillna(0.0)
    team_tov = teams.map(team_lookup["team_TOV"]).fillna(0.0)
    player_fga = t2_attempts + t3_attempts
    numerator = (player_fga + 0.44 * t1_attempts + turnovers) * (team_mp / 5.0)
    denominator = minutes * (team_fga + 0.44 * team_fta + team_tov)
    return pd.to_numeric(numerator.div(denominator.replace(0, pd.NA)) * 100.0, errors="coerce").fillna(0.0)


def _gm_build_clutch_lookup(clutch_df: pd.DataFrame) -> pd.DataFrame:
    if clutch_df.empty:
        return pd.DataFrame()
    lookup = clutch_df.copy()
    lookup["__team_norm"] = lookup["EQUIPO"].map(_gm_normalize_text)
    lookup["__name_norm"] = lookup["JUGADOR"].map(_gm_normalize_text)
    return lookup


def _gm_match_player_to_clutch(player_name: str, team_name: str, clutch_lookup: pd.DataFrame) -> dict[str, Any]:
    expected_name = _gm_format_name_to_clutch(player_name)
    result: dict[str, Any] = {
        "status": "missing",
        "expected_name": expected_name,
        "confidence": 0.0,
        "row": None,
    }
    if clutch_lookup.empty or not expected_name:
        return result

    expected_name_norm = _gm_normalize_text(expected_name)
    team_norm = _gm_normalize_text(team_name)
    exact_match = clutch_lookup[
        (clutch_lookup["__team_norm"] == team_norm)
        & (clutch_lookup["__name_norm"] == expected_name_norm)
    ]
    if not exact_match.empty:
        result.update(
            {
                "status": "exact",
                "confidence": 1.0,
                "row": exact_match.iloc[0].to_dict(),
            }
        )
        return result

    loose_match = clutch_lookup[clutch_lookup["__name_norm"] == expected_name_norm]
    if len(loose_match) == 1:
        result.update(
            {
                "status": "loose",
                "confidence": 0.55,
                "row": loose_match.iloc[0].to_dict(),
            }
        )
    return result


def _gm_count_clutch_matches(gm_df: pd.DataFrame, clutch_lookup: pd.DataFrame) -> dict[str, int]:
    if gm_df.empty or clutch_lookup.empty:
        return {"exact": 0, "loose": 0}
    exact = 0
    loose = 0
    unique_players = gm_df[["PLAYER_KEY", "JUGADOR", "EQUIPO"]].drop_duplicates(subset=["PLAYER_KEY"])
    for _, row in unique_players.iterrows():
        match = _gm_match_player_to_clutch(str(row["JUGADOR"]), str(row["EQUIPO"]), clutch_lookup)
        if match["status"] == "exact":
            exact += 1
        elif match["status"] == "loose":
            loose += 1
    return {"exact": exact, "loose": loose}


def _gm_rule_summary(rule: dict[str, Any]) -> str:
    metric = rule["metric"]
    minimum = rule.get("min")
    maximum = rule.get("max")
    if minimum is not None and maximum is not None:
        return f"{metric}: {minimum:g} a {maximum:g}"
    if minimum is not None:
        return f"{metric} >= {minimum:g}"
    if maximum is not None:
        return f"{metric} <= {maximum:g}"
    return metric


def build_gm_players_view(players_df: pd.DataFrame, mode: str, teams_df: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = ["PLAYER_KEY", *GM_EXPORT_COLUMNS]
    if players_df.empty:
        return pd.DataFrame(columns=columns)

    df = players_df.copy()
    numeric_values = {column: _gm_numeric_series(df, column) for column in GM_COUNT_COLUMNS}
    player_keys = df["PLAYER_KEY"].astype(str) if "PLAYER_KEY" in df.columns else df.index.astype(str)
    player_names = df["JUGADOR"].fillna("").astype(str) if "JUGADOR" in df.columns else pd.Series("", index=df.index, dtype=str)
    teams = df["EQUIPO"].fillna("").astype(str) if "EQUIPO" in df.columns else pd.Series("", index=df.index, dtype=str)
    nationalities = df["NACIONALIDAD"].fillna("").astype(str) if "NACIONALIDAD" in df.columns else pd.Series("", index=df.index, dtype=str)
    birth_dates = df["FECHA NACIMIENTO"] if "FECHA NACIMIENTO" in df.columns else pd.Series([None] * len(df), index=df.index)
    games_played = pd.to_numeric(df["PJ"], errors="coerce").fillna(0) if "PJ" in df.columns else pd.Series(0, index=df.index, dtype=float)
    games_divisor = games_played.replace(0, pd.NA)
    minutes_total = numeric_values["MINUTOS JUGADOS"]

    rebounds_total = numeric_values["REB OFFENSIVO"] + numeric_values["REB DEFENSIVO"]
    field_goals_att = numeric_values["T2 INTENTADO"] + numeric_values["T3 INTENTADO"]
    field_goals_made = numeric_values["T2 CONVERTIDO"] + numeric_values["T3 CONVERTIDO"]
    plays_total = field_goals_att + 0.44 * numeric_values["TL INTENTADOS"] + numeric_values["PERDIDAS"]

    gm_df = pd.DataFrame(index=df.index)
    gm_df["PLAYER_KEY"] = player_keys
    gm_df["JUGADOR"] = player_names
    gm_df["EQUIPO"] = teams
    gm_df["NACIONALIDAD"] = nationalities
    gm_df[GM_BIRTH_YEAR_COLUMN] = birth_dates.apply(_extract_birth_year).astype("Int64")
    gm_df["PJ"] = games_played.round(0).astype("Int64")

    if mode == "Promedios":
        for column in GM_COUNT_COLUMNS:
            gm_df[column] = numeric_values[column].div(games_divisor).fillna(0.0)
        gm_df["REB TOTALES"] = rebounds_total.div(games_divisor).fillna(0.0)
        gm_df["FGM"] = field_goals_made.div(games_divisor).fillna(0.0)
        gm_df["FGA"] = field_goals_att.div(games_divisor).fillna(0.0)
        gm_df["PLAYS"] = plays_total.div(games_divisor).fillna(0.0)
        average_columns = [*GM_COUNT_COLUMNS, *GM_COUNT_DERIVED_COLUMNS]
        gm_df[average_columns] = gm_df[average_columns].apply(pd.to_numeric, errors="coerce").round(2)
    else:
        for column in GM_COUNT_COLUMNS:
            gm_df[column] = numeric_values[column]
        gm_df["REB TOTALES"] = rebounds_total
        gm_df["FGM"] = field_goals_made
        gm_df["FGA"] = field_goals_att
        gm_df["PLAYS"] = plays_total
        integer_columns = [column for column in [*GM_COUNT_COLUMNS, *GM_COUNT_DERIVED_COLUMNS] if column != "MINUTOS JUGADOS"]
        gm_df[integer_columns] = gm_df[integer_columns].apply(pd.to_numeric, errors="coerce").round(0).astype("Int64")
        gm_df["MINUTOS JUGADOS"] = pd.to_numeric(gm_df["MINUTOS JUGADOS"], errors="coerce").round(2)

    gm_df["T1%"] = _gm_safe_ratio(numeric_values["TL CONVERTIDOS"], numeric_values["TL INTENTADOS"], 100.0).round(2)
    gm_df["T2%"] = _gm_safe_ratio(numeric_values["T2 CONVERTIDO"], numeric_values["T2 INTENTADO"], 100.0).round(2)
    gm_df["T3%"] = _gm_safe_ratio(numeric_values["T3 CONVERTIDO"], numeric_values["T3 INTENTADO"], 100.0).round(2)
    gm_df["eFG%"] = _gm_safe_ratio(field_goals_made + 0.5 * numeric_values["T3 CONVERTIDO"], field_goals_att, 100.0).round(2)
    gm_df["TS%"] = _gm_safe_ratio(numeric_values["PUNTOS"], 2 * (field_goals_att + 0.44 * numeric_values["TL INTENTADOS"]), 100.0).round(2)
    gm_df["PPP"] = _gm_safe_ratio(numeric_values["PUNTOS"], plays_total, 1.0).round(3)
    gm_df["AST/TO"] = _gm_ast_to_ratio(numeric_values["ASISTENCIAS"], numeric_values["PERDIDAS"])
    gm_df["TOV%"] = _gm_safe_ratio(numeric_values["PERDIDAS"], plays_total, 100.0).round(2)
    gm_df["USG%"] = _gm_compute_usg(
        teams,
        minutes_total,
        numeric_values["TL INTENTADOS"],
        numeric_values["T2 INTENTADO"],
        numeric_values["T3 INTENTADO"],
        numeric_values["PERDIDAS"],
        teams_df if teams_df is not None else pd.DataFrame(),
    ).round(2)

    export_columns = [column for column in columns if column in gm_df.columns]
    return gm_df[export_columns]


def apply_gm_filters(
    gm_df: pd.DataFrame,
    *,
    nationalities: list[str],
    birth_year_range: tuple[int, int] | None,
    rules: list[dict[str, Any]],
) -> pd.DataFrame:
    filtered_df = gm_df.copy()
    if nationalities:
        filtered_df = filtered_df[filtered_df["NACIONALIDAD"].isin(nationalities)]

    if birth_year_range is not None:
        min_year, max_year = birth_year_range
        birth_years = pd.to_numeric(filtered_df[GM_BIRTH_YEAR_COLUMN], errors="coerce")
        filtered_df = filtered_df[(birth_years >= min_year) & (birth_years <= max_year)]

    for rule in rules:
        minimum = rule.get("min")
        maximum = rule.get("max")
        if minimum is None and maximum is None:
            continue
        metric = rule["metric"]
        metric_values = pd.to_numeric(filtered_df[metric], errors="coerce")
        if minimum is not None:
            filtered_df = filtered_df[metric_values >= minimum]
            metric_values = pd.to_numeric(filtered_df[metric], errors="coerce")
        if maximum is not None:
            filtered_df = filtered_df[metric_values <= maximum]
    return filtered_df


def serialize_gm_csv(filtered_df: pd.DataFrame) -> bytes:
    export_columns = [column for column in GM_EXPORT_COLUMNS if column in filtered_df.columns]
    export_df = filtered_df[export_columns].copy()
    return export_df.to_csv(index=False, na_rep="").encode("utf-8-sig")


def serialize_dependency_csv(filtered_df: pd.DataFrame) -> bytes:
    export_df = filtered_df.copy()
    return export_df.to_csv(index=False, na_rep="").encode("utf-8-sig")


def render_gm_rule_builder(*, inside_form: bool = False) -> tuple[list[dict[str, Any]], list[str], bool, int | None]:
    st.write("**Reglas numéricas**")
    st.caption(
        "`T1%`, `T2%` y `T3%` son porcentajes de acierto. Si más adelante añadimos reparto de finalización, "
        "se mostrará como `%Plays T1`, `%Plays T2` y `%Plays T3`."
    )
    header_cols = st.columns([2.2, 1.2, 1.2, 0.7])
    header_cols[0].caption("Métrica")
    header_cols[1].caption("Min")
    header_cols[2].caption("Max")
    header_cols[3].caption(" ")

    rule_ids = _init_gm_rule_state()
    remove_rule_id: int | None = None
    add_rule_clicked = False
    rules: list[dict[str, Any]] = []
    errors: list[str] = []

    for position, rule_id in enumerate(rule_ids):
        metric_key = f"gm_rule_metric_{rule_id}"
        min_key = f"gm_rule_min_{rule_id}"
        max_key = f"gm_rule_max_{rule_id}"

        if st.session_state.get(metric_key) not in GM_RULE_METRICS:
            st.session_state[metric_key] = _default_gm_metric(position)
        if min_key not in st.session_state:
            st.session_state[min_key] = ""
        if max_key not in st.session_state:
            st.session_state[max_key] = ""

        row_cols = st.columns([2.2, 1.2, 1.2, 0.7])
        metric = row_cols[0].selectbox(
            f"Métrica {position + 1}",
            options=GM_RULE_METRICS,
            key=metric_key,
            label_visibility="collapsed",
        )
        min_value_raw = row_cols[1].text_input(
            f"Mínimo {position + 1}",
            key=min_key,
            placeholder="sin mín",
            label_visibility="collapsed",
        )
        max_value_raw = row_cols[2].text_input(
            f"Máximo {position + 1}",
            key=max_key,
            placeholder="sin máx",
            label_visibility="collapsed",
        )
        remove_disabled = len(rule_ids) == 1
        if inside_form:
            remove_clicked = row_cols[3].form_submit_button(
                f"Quitar {position + 1}",
                disabled=remove_disabled,
                use_container_width=True,
            )
        else:
            remove_clicked = row_cols[3].button(
                "Quitar",
                key=f"gm_rule_remove_{rule_id}",
                disabled=remove_disabled,
                use_container_width=True,
            )
        if remove_clicked:
            remove_rule_id = rule_id

        minimum, min_error = _parse_optional_float(min_value_raw)
        maximum, max_error = _parse_optional_float(max_value_raw)
        if min_error:
            errors.append(f"Regla {position + 1}: {min_error}")
        if max_error:
            errors.append(f"Regla {position + 1}: {max_error}")
        if minimum is not None and maximum is not None and minimum > maximum:
            errors.append(f"Regla {position + 1}: el mínimo no puede ser mayor que el máximo.")

        rules.append({"metric": metric, "min": minimum, "max": maximum})

    actions_cols = st.columns([1.2, 4])
    if inside_form:
        add_rule_clicked = actions_cols[0].form_submit_button("Añadir regla", use_container_width=True)
    else:
        add_rule_clicked = actions_cols[0].button("Añadir regla", key="gm_rule_add", use_container_width=True)
        if add_rule_clicked:
            next_rule_id = int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0))
            st.session_state[GM_RULE_IDS_KEY] = [*rule_ids, next_rule_id]
            st.session_state[GM_RULE_NEXT_ID_KEY] = next_rule_id + 1
            st.rerun()

        if remove_rule_id is not None:
            remaining_ids = [rule_id for rule_id in rule_ids if rule_id != remove_rule_id]
            _clear_gm_rule_state(remove_rule_id)
            st.session_state[GM_RULE_IDS_KEY] = remaining_ids or [int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0))]
            if not remaining_ids:
                st.session_state[GM_RULE_NEXT_ID_KEY] = int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0)) + 1
            st.rerun()

    return rules, errors, add_rule_clicked, remove_rule_id


def capture_logs(action) -> tuple[Any, list[dict[str, str]]]:
    logs: list[dict[str, str]] = []

    def callback(level: str, message: str) -> None:
        logs.append({"level": level, "message": message})

    result = action(callback)
    return result, logs


def persist_feedback(action: str, result: Any, logs: list[dict[str, str]]) -> None:
    st.session_state["last_action_feedback"] = {
        "action": action,
        "result": result,
        "logs": logs,
        "timestamp": time.time(),
    }


def clear_data_caches() -> None:
    st.cache_data.clear()


def load_active_runtime_snapshot() -> tuple[dict[str, Any], bool]:
    runtime_status = load_runtime_status()
    if runtime_status_is_live(runtime_status):
        return runtime_status, True
    inferred = infer_runtime_status()
    if inferred:
        return inferred, False
    return runtime_status, True


def render_sync_runtime_panel(*, key_prefix: str) -> None:
    st.subheader("Proceso de sincronizacion")
    left, right = st.columns([1, 1])
    with left:
        if st.button("Actualizar estado", key=f"{key_prefix}_refresh_runtime"):
            clear_data_caches()
            st.rerun()
    with right:
        auto_refresh = st.checkbox("Autoactualizar 15s", value=False, key=f"{key_prefix}_auto_refresh_runtime")

    runtime_status, exact_status = load_active_runtime_snapshot()
    task_status = get_scheduled_task_status(DEFAULT_SYNC_TASK_NAME) if not is_cloud_mode() else {"supported": False}

    if runtime_status.get("status") == "running":
        if exact_status:
            st.success("Hay una sincronizacion activa y esta vista se actualiza con el estado exacto del proceso.")
        else:
            st.warning(
                "Hay una sincronizacion activa, pero esta vista es inferida a partir de la base y los procesos en marcha."
            )
    elif runtime_status.get("status") == "failed":
        st.error(f"Ultima sincronizacion registrada con error: {runtime_status.get('current_message', '-')}")
    elif runtime_status.get("status") == "completed":
        st.info("La ultima sincronizacion registrada termino correctamente.")
    else:
        st.info("No hay una sincronizacion activa detectada ahora mismo.")

    meta_cols = st.columns(4)
    meta_cols[0].metric("Estado", str(runtime_status.get("status") or "sin datos"))
    meta_cols[1].metric("PID", str(runtime_status.get("pid") or "-"))
    meta_cols[2].metric("Ultimo latido", format_relative_time(runtime_status.get("heartbeat_at")))
    scope_position = "-"
    if runtime_status.get("scope_index") and runtime_status.get("scopes_total"):
        scope_position = f"{runtime_status['scope_index']}/{runtime_status['scopes_total']}"
    meta_cols[3].metric("Scope", scope_position)

    st.write(f"**Inicio:** {format_datetime_text(runtime_status.get('started_at'))}")
    st.write(f"**Paso actual:** {runtime_status.get('current_step') or '-'}")
    st.write(f"**Mensaje:** {runtime_status.get('current_message') or '-'}")

    current_scope = runtime_status.get("current_scope") or {}
    if current_scope:
        st.write(f"**Scope actual:** {current_scope.get('label') or '-'}")
        total_games = int(current_scope.get("games_total") or 0)
        done_games = int(current_scope.get("games_done") or 0)
        if total_games > 0:
            st.progress(min(done_games / total_games, 1.0), text=f"{done_games}/{total_games} partidos procesados")
            scope_cols = st.columns(3)
            scope_cols[0].metric("OK", int(current_scope.get("games_success") or 0))
            scope_cols[1].metric("KO", int(current_scope.get("games_failed") or 0))
            scope_cols[2].metric("Restantes", max(total_games - done_games, 0))
        recent_revalidation = current_scope.get("recent_revalidation") or []
        if recent_revalidation:
            revalidation_text = ", ".join(
                f"{item.get('phase')} J{item.get('jornada')}" for item in recent_revalidation if item.get("phase")
            )
            if revalidation_text:
                st.caption(f"Revalidacion activa: {revalidation_text}")

    current_game = runtime_status.get("current_game") or {}
    if current_game:
        current_label = current_game.get("game_label") or "-"
        st.info(
            f"Ahora mismo: J{current_game.get('jornada', '-')} | {current_game.get('phase', '-')} | {current_label} ({current_game.get('pid', '-')})"
        )

    next_games = runtime_status.get("next_games") or []
    if next_games:
        st.write("**Siguientes partidos en cola**")
        st.dataframe(pd.DataFrame(next_games), use_container_width=True, hide_index=True)

    queued_scopes = runtime_status.get("queued_scopes") or []
    if queued_scopes:
        st.write("**Scopes siguientes**")
        if queued_scopes and isinstance(queued_scopes[0], dict):
            st.dataframe(pd.DataFrame(queued_scopes), use_container_width=True, hide_index=True)
        else:
            st.dataframe(pd.DataFrame({"Scope": queued_scopes}), use_container_width=True, hide_index=True)

    recent_events = runtime_status.get("recent_events") or []
    if recent_events:
        st.write("**Ultimos eventos**")
        events_df = pd.DataFrame(recent_events[-15:])
        if "timestamp" in events_df.columns:
            events_df["timestamp"] = events_df["timestamp"].apply(format_datetime_text)
        st.dataframe(events_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("**Programacion semanal**")
    if task_status.get("supported") is False and os.name != "nt":
        st.info("La consulta de tareas programadas solo esta disponible en Windows.")
    elif task_status.get("exists"):
        st.success(
            f"Tarea `{DEFAULT_SYNC_TASK_NAME}` registrada. Estado: {task_status.get('state', '-')}. Proxima ejecucion: {format_datetime_text(task_status.get('next_run_time'))}."
        )
    else:
        st.warning(
            "La tarea semanal todavia no esta registrada en Windows. Hasta que no se registre, el domingo no se ejecutara sola."
        )

    if auto_refresh and runtime_status.get("status") == "running":
        time.sleep(15)
        clear_data_caches()
        st.rerun()


def rerun_with_feedback(action: str, result: Any, logs: list[dict[str, str]]) -> None:
    persist_feedback(action, result, logs)
    clear_data_caches()
    st.rerun()


def render_feedback() -> None:
    feedback = st.session_state.get("last_action_feedback")
    if not feedback:
        return

    st.subheader("Ultima ejecucion")
    st.write(f"**Accion:** {feedback['action']}")
    logs = feedback.get("logs") or []
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    result = feedback.get("result")
    if isinstance(result, SyncSummary):
        st.json(serialize_sync_summary(result))
    elif isinstance(result, dict):
        st.json(result)
    elif result is not None:
        st.write(result)


def render_db_status(store: DataStore) -> bool:
    db_signature = get_db_signature()
    summary = load_db_summary(db_signature)
    totals = load_status_totals(db_signature)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Partidos", summary["games"])
    col2.metric("Jugadores bio", summary["players"])
    col3.metric("Scopes", summary["scopes"])
    col4.metric("Con datos", totals["success"] + totals["imported"])
    col5.metric("Pendientes", totals["pending"])
    col6.metric("Fallidos", totals["failed"])

    if summary["games"] > 0:
        return True

    st.warning("La base SQLite esta vacia.")
    st.code(f"Base esperada: {SQLITE_DB_FILE}")

    if is_cloud_mode():
        st.error("En modo cloud la app es solo lectura. Carga primero `data/feb.sqlite` desde local.")
        return False

    st.info("Puedes importar el historico Excel o empezar a scrapeer directamente desde la pestana `Scraper`.")
    if st.button("Importar historico Excel a SQLite", key="bootstrap_import"):
        result, logs = capture_logs(lambda cb: store.import_historical(progress_callback=cb))
        rerun_with_feedback("Importacion historica", result, logs)
    return False


def build_common_filters(db_signature: tuple[tuple[str, int, int], ...]) -> tuple[ReportFilters | None, list[str], list[int]]:
    seasons = load_available_seasons(db_signature)
    if not seasons:
        return None, [], []

    with st.sidebar:
        st.header("Filtros de informes")
        season = st.selectbox("Temporada", seasons, index=0)
        leagues = load_available_leagues(db_signature, season)
        league = st.selectbox("Liga", leagues, index=0)
        available_phases = load_available_phases(db_signature, season, league)
        selected_phases = st.multiselect(
            "Fases",
            options=available_phases,
            default=[],
            placeholder="Vacio = todas las fases",
        )
        available_jornadas = load_available_jornadas(db_signature, season, league, tuple(selected_phases))
        selected_jornadas = st.multiselect(
            "Jornadas",
            options=available_jornadas,
            default=[],
            placeholder="Vacio = todas las jornadas",
        )

    return (
        ReportFilters(
            season=season,
            league=league,
            phases=tuple(selected_phases),
            jornadas=tuple(selected_jornadas),
        ),
        available_phases,
        available_jornadas,
    )


def render_database_tab(db_signature: tuple[tuple[str, int, int], ...]) -> None:
    st.subheader("Resumen de base de datos")
    st.write("Aqui puedes ver que temporadas, ligas, fases y jornadas ya estan catalogadas o scrapeadas.")
    render_sync_runtime_panel(key_prefix="db_tab")

    st.markdown("---")

    scope_df = load_scope_summary(db_signature)
    jornada_df = load_jornada_summary(db_signature)
    auto_config = load_auto_sync_config()
    auto_targets = iter_enabled_targets(auto_config)

    if scope_df.empty:
        st.info("La base todavia no tiene partidos catalogados.")
    else:
        st.dataframe(scope_df, use_container_width=True, hide_index=True)
        with st.expander("Detalle por jornada"):
            st.dataframe(jornada_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Autosync semanal")
    st.write(f"Archivo de configuracion: `{AUTO_SYNC_TARGETS_FILE}`")
    if auto_targets:
        auto_df = pd.DataFrame(
            [
                {
                    "Temporada": target["season"],
                    "Liga": target["league"],
                    "Fases": ", ".join(target["phases"]),
                    "Jornadas": ", ".join(str(value) for value in target.get("jornadas", [])) or "todas",
                }
                for target in auto_targets
            ]
        )
        st.dataframe(auto_df, use_container_width=True, hide_index=True)
        st.caption(
            f"Autosync configurado para revisar las ultimas {auto_config.get('revalidate_window', 2)} jornadas por fase y publicar cambios: {auto_config.get('publish', True)}."
        )
    else:
        st.info("Todavia no hay objetivos guardados para el autosync semanal.")


def render_gm_tab(db_signature: tuple[tuple[str, int, int], ...]) -> None:
    st.subheader("Vista GM")
    st.write("Búsqueda global de jugadores con filtros propios de temporada, liga, fases y jornadas.")

    seasons = load_available_seasons(db_signature)
    if not seasons:
        st.info("No hay datos suficientes para construir la vista GM.")
        return

    if GM_MODE_KEY not in st.session_state:
        st.session_state[GM_MODE_KEY] = "Promedios"

    st.markdown("---")
    with st.form("gm_scope_form", clear_on_submit=False):
        scope_apply_row = st.columns([1.4, 4.6])
        scope_apply_row[0].form_submit_button("Aplicar scope GM", use_container_width=True)
        scope_apply_row[1].caption(
            "Los cambios de temporada, liga, fases, jornadas y modo se aplican al pulsar Enter o `Aplicar scope GM`."
        )

        scope_top_cols = st.columns(2)
        _ensure_select_state(GM_SCOPE_SEASON_KEY, seasons)
        season = scope_top_cols[0].selectbox("Temporada GM", seasons, key=GM_SCOPE_SEASON_KEY)

        leagues = load_available_leagues(db_signature, season)
        _ensure_select_state(GM_SCOPE_LEAGUE_KEY, leagues)
        league = scope_top_cols[1].selectbox("Liga GM", leagues, key=GM_SCOPE_LEAGUE_KEY)

        available_phases = load_available_phases(db_signature, season, league)
        _ensure_multiselect_state(GM_SCOPE_PHASES_KEY, available_phases)
        selected_phases = st.multiselect(
            "Fases GM",
            options=available_phases,
            key=GM_SCOPE_PHASES_KEY,
            placeholder="Vacio = todas las fases",
        )

        available_jornadas = load_available_jornadas(db_signature, season, league, tuple(selected_phases))
        _ensure_multiselect_state(GM_SCOPE_JORNADAS_KEY, available_jornadas)
        selected_jornadas = st.multiselect(
            "Jornadas GM",
            options=available_jornadas,
            key=GM_SCOPE_JORNADAS_KEY,
            placeholder="Vacio = todas las jornadas",
        )

        mode = st.radio("Modo de estadisticas", ["Totales", "Promedios"], horizontal=True, key=GM_MODE_KEY)

    gm_df, clutch_lookup = load_gm_view_data(
        db_signature,
        season,
        league,
        tuple(selected_phases),
        tuple(selected_jornadas),
        mode,
    )
    gm_df = _normalize_gm_view_columns(gm_df)
    if gm_df.empty:
        st.info("No hay jugadores disponibles para el scope GM seleccionado.")
        return

    birth_year_series = pd.to_numeric(gm_df[GM_BIRTH_YEAR_COLUMN], errors="coerce").dropna()
    birth_year_bounds: tuple[int, int] | None = None
    if not birth_year_series.empty:
        birth_year_bounds = (int(birth_year_series.min()), int(birth_year_series.max()))

    st.caption(
        "Clutch sigue fuera del builder principal, pero esta vista ya prepara matching exacto/relajado para explorar esa capa."
    )

    nationality_options = sorted(value for value in gm_df["NACIONALIDAD"].dropna().astype(str).unique().tolist() if value)
    _ensure_multiselect_state(GM_NATIONALITIES_KEY, nationality_options)

    if birth_year_series.empty:
        st.session_state.pop(GM_BIRTH_RANGE_KEY, None)
    else:
        min_year, max_year = birth_year_bounds or (int(birth_year_series.min()), int(birth_year_series.max()))
        current_birth_range = st.session_state.get(GM_BIRTH_RANGE_KEY)
        if (
            not isinstance(current_birth_range, tuple)
            or len(current_birth_range) != 2
            or current_birth_range[0] < min_year
            or current_birth_range[1] > max_year
            or current_birth_range[0] > current_birth_range[1]
        ):
            st.session_state[GM_BIRTH_RANGE_KEY] = (min_year, max_year)

    st.markdown("---")
    with st.form("gm_filters_form", clear_on_submit=False):
        apply_row = st.columns([1.2, 4])
        apply_filters_clicked = apply_row[0].form_submit_button("Aplicar filtros", use_container_width=True)
        apply_row[1].caption("Los cambios de reglas y bio se aplican al pulsar Enter o `Aplicar filtros`.")

        st.write("**Filtros bio**")
        bio_cols = st.columns([1.5, 1.5])
        selected_nationalities = bio_cols[0].multiselect(
            "Nacionalidad",
            options=nationality_options,
            key=GM_NATIONALITIES_KEY,
            placeholder="Vacio = todas",
        )

        birth_year_range: tuple[int, int] | None = None
        if birth_year_series.empty:
            bio_cols[1].info("No hay años de nacimiento disponibles en este scope.")
        else:
            min_year, max_year = birth_year_bounds or (int(birth_year_series.min()), int(birth_year_series.max()))
            birth_year_range = bio_cols[1].slider(
                "Año nacimiento",
                min_value=min_year,
                max_value=max_year,
                key=GM_BIRTH_RANGE_KEY,
            )

        st.markdown("---")
        rules, rule_errors, add_rule_clicked, remove_rule_id = render_gm_rule_builder(inside_form=True)

    if add_rule_clicked:
        next_rule_id = int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0))
        st.session_state[GM_RULE_IDS_KEY] = [*st.session_state.get(GM_RULE_IDS_KEY, []), next_rule_id]
        st.session_state[GM_RULE_NEXT_ID_KEY] = next_rule_id + 1
        st.rerun()

    if remove_rule_id is not None:
        remaining_ids = [rule_id for rule_id in st.session_state.get(GM_RULE_IDS_KEY, []) if rule_id != remove_rule_id]
        _clear_gm_rule_state(remove_rule_id)
        st.session_state[GM_RULE_IDS_KEY] = remaining_ids or [int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0))]
        if not remaining_ids:
            st.session_state[GM_RULE_NEXT_ID_KEY] = int(st.session_state.get(GM_RULE_NEXT_ID_KEY, 0)) + 1
        st.rerun()

    if rule_errors:
        for message in rule_errors:
            st.error(message)
        st.info("Corrige los valores min/max y pulsa Enter o `Aplicar filtros`.")
        return

    filtered_df = apply_gm_filters(
        gm_df,
        nationalities=selected_nationalities,
        birth_year_range=birth_year_range,
        rules=rules,
    )

    active_rule_labels = [_gm_rule_summary(rule) for rule in rules if rule.get("min") is not None or rule.get("max") is not None]
    phases_summary = ", ".join(selected_phases) if selected_phases else "todas"
    jornadas_summary = ", ".join(str(value) for value in selected_jornadas) if selected_jornadas else "todas"
    nationality_summary = ", ".join(selected_nationalities) if selected_nationalities else "todas"
    birth_summary = (
        f"{birth_year_range[0]}-{birth_year_range[1]}"
        if birth_year_range is not None and birth_year_bounds is not None and birth_year_range != birth_year_bounds
        else "todos"
    )
    rules_summary = " | ".join(active_rule_labels) if active_rule_labels else "sin reglas numéricas activas"
    st.caption(
        f"Scope: {season} | {league} | Fases: {phases_summary} | Jornadas: {jornadas_summary} | "
        f"Modo: {mode} | Nacionalidad: {nationality_summary} | Nacimiento: {birth_summary} | Reglas: {rules_summary}"
    )

    sort_candidates = [column for column in [*GM_RULE_METRICS, *GM_RATE_COLUMNS, GM_BIRTH_YEAR_COLUMN] if column in filtered_df.columns]
    default_sort = next((rule["metric"] for rule in rules if rule.get("min") is not None or rule.get("max") is not None), "PUNTOS")
    if sort_candidates:
        if st.session_state.get(GM_SORT_COLUMN_KEY) not in sort_candidates:
            st.session_state[GM_SORT_COLUMN_KEY] = default_sort if default_sort in sort_candidates else sort_candidates[0]

    all_display_options = list(dict.fromkeys([column for column in filtered_df.columns if column != "PLAYER_KEY"]))
    _ensure_multiselect_default_state(GM_VISIBLE_COLUMNS_KEY, all_display_options, GM_DEFAULT_VISIBLE_COLUMNS)
    selected_columns = st.multiselect(
        "Columnas visibles",
        options=all_display_options,
        key=GM_VISIBLE_COLUMNS_KEY,
    )

    sort_cols = st.columns([1.5, 4.5])
    if sort_candidates:
        sort_column = sort_cols[0].selectbox("Ordenar por", sort_candidates, key=GM_SORT_COLUMN_KEY)
        sort_cols[1].caption("La tabla se ordena de mayor a menor en la métrica elegida.")
        if sort_column in filtered_df.columns:
            sort_by = [sort_column] if sort_column == "PJ" else [sort_column, "PJ"]
            ascending = [False] * len(sort_by)
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending, na_position="last")

    st.markdown("---")
    clutch_counts = _gm_count_clutch_matches(filtered_df if not filtered_df.empty else gm_df, clutch_lookup)
    current_year = datetime.now().year
    age_series = (
        current_year - pd.to_numeric(filtered_df[GM_BIRTH_YEAR_COLUMN], errors="coerce")
        if not filtered_df.empty
        else pd.Series(dtype=float)
    )
    summary_cols = st.columns(5)
    summary_cols[0].metric("Jugadores encontrados", int(filtered_df.shape[0]))
    summary_cols[1].metric("PTS media", f"{filtered_df['PUNTOS'].mean():.2f}" if not filtered_df.empty else "-")
    summary_cols[2].metric("AST media", f"{filtered_df['ASISTENCIAS'].mean():.2f}" if not filtered_df.empty else "-")
    summary_cols[3].metric("Edad media", f"{age_series.dropna().mean():.1f}" if not age_series.dropna().empty else "-")
    summary_cols[4].metric("Clutch exacto", clutch_counts["exact"])

    if filtered_df.empty:
        st.info("No hay jugadores que cumplan los filtros actuales.")
        return

    display_columns = selected_columns or [column for column in GM_DEFAULT_VISIBLE_COLUMNS if column in filtered_df.columns]
    st.dataframe(filtered_df[display_columns], use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar CSV GM",
        data=serialize_gm_csv(filtered_df),
        file_name=f"gm_players_{season.replace('/', '-')}_{league.replace(' ', '_').lower()}.csv",
        mime="text/csv",
        key="gm_download_csv",
    )

    selectable_players = (
        filtered_df[[column for column in ["PLAYER_KEY", "JUGADOR", "EQUIPO", "DORSAL"] if column in filtered_df.columns]]
        .drop_duplicates(subset=["PLAYER_KEY"])
        .sort_values(by=["JUGADOR", "EQUIPO"])
    )
    player_keys = selectable_players["PLAYER_KEY"].astype(str).tolist()
    _ensure_select_state(GM_SELECTED_PLAYER_KEY, player_keys)
    player_labels = {
        str(row["PLAYER_KEY"]): _build_player_selection_label(row["JUGADOR"], row.get("EQUIPO"), row.get("DORSAL"))
        for _, row in selectable_players.iterrows()
    }
    selected_player_key = st.selectbox(
        "Jugador para informe GM",
        options=player_keys,
        key=GM_SELECTED_PLAYER_KEY,
        format_func=lambda key: player_labels.get(key, key),
    )

    selected_row = filtered_df[filtered_df["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
    selected_player_data = selected_row.iloc[0] if not selected_row.empty else None
    if selected_player_data is not None:
        st.markdown("---")
        st.write("**Ficha rapida**")
        detail_cols = st.columns(4)
        detail_cols[0].metric("Equipo", _display_or_dash(selected_player_data["EQUIPO"]))
        detail_cols[1].metric("Nacionalidad", _display_or_dash(selected_player_data["NACIONALIDAD"]))
        detail_cols[2].metric("Año", _display_or_dash(selected_player_data[GM_BIRTH_YEAR_COLUMN]))
        detail_cols[3].metric("PJ", _display_or_dash(selected_player_data["PJ"]))

        stat_cols = st.columns(5)
        stat_cols[0].metric("PTS", f"{float(selected_player_data['PUNTOS']):.2f}")
        stat_cols[1].metric("REB", f"{float(selected_player_data['REB TOTALES']):.2f}")
        stat_cols[2].metric("AST", f"{float(selected_player_data['ASISTENCIAS']):.2f}")
        stat_cols[3].metric("AST/TO", f"{float(selected_player_data['AST/TO']):.2f}")
        stat_cols[4].metric("USG%", f"{float(selected_player_data['USG%']):.2f}")

        clutch_match = _gm_match_player_to_clutch(
            str(selected_player_data["JUGADOR"]),
            str(selected_player_data["EQUIPO"]),
            clutch_lookup,
        )
        if clutch_match["status"] == "exact":
            st.success(f"Match clutch exacto encontrado para `{clutch_match['expected_name']}`.")
        elif clutch_match["status"] == "loose":
            st.warning(
                f"Match clutch relajado encontrado para `{clutch_match['expected_name']}`. Conviene revisar el equipo antes de usarlo como filtro."
            )
        else:
            st.info(f"Sin match clutch para `{clutch_match['expected_name']}` en este scope.")

        clutch_row = clutch_match.get("row")
        if clutch_row:
            clutch_cols = st.columns(5)
            clutch_cols[0].metric("Clutch games", int(clutch_row.get("GAMES") or 0))
            clutch_cols[1].metric("Min clutch", f"{float(clutch_row.get('MINUTOS_CLUTCH') or 0.0):.2f}")
            clutch_cols[2].metric("PTS clutch", f"{float(clutch_row.get('PTS') or 0.0):.2f}")
            clutch_cols[3].metric("AST clutch", f"{float(clutch_row.get('AST') or 0.0):.2f}")
            clutch_cols[4].metric("REB clutch", f"{float(clutch_row.get('REB') or 0.0):.2f}")

            clutch_rate_cols = st.columns(4)
            clutch_rate_cols[0].metric("TS% clutch", f"{float(clutch_row.get('TS%') or 0.0):.2f}")
            clutch_rate_cols[1].metric("eFG% clutch", f"{float(clutch_row.get('eFG%') or 0.0):.2f}")
            clutch_rate_cols[2].metric("NET_RTG clutch", f"{float(clutch_row.get('NET_RTG') or 0.0):.2f}")
            clutch_rate_cols[3].metric("USG% clutch", f"{float(clutch_row.get('USG%') or 0.0):.2f}")

    if st.button("Generar informe GM", type="primary", key="gm_generate_player_report"):
        bundle = load_report_bundle(db_signature, season, league, tuple(selected_phases), tuple(selected_jornadas))
        player_rows = bundle.players_df[bundle.players_df["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
        if player_rows.empty:
            st.error("No se encontro el jugador seleccionado dentro del bundle GM.")
        else:
            player_name = str(player_rows["JUGADOR"].iloc[0])
            with st.spinner("Generando informe del jugador desde GM..."):
                path = get_generate_report_fn()(
                    player_name,
                    output_dir=PLAYER_REPORTS_DIR,
                    overwrite=True,
                    data_df=player_rows,
                    teams_df=bundle.teams_df,
                    clutch_df=bundle.clutch_df,
                )
            st.session_state[GM_REPORT_PATH_KEY] = str(path)

    report_path = st.session_state.get(GM_REPORT_PATH_KEY)
    if report_path and Path(report_path).exists():
        image_bytes = Path(report_path).read_bytes()
        st.image(image_bytes, caption=Path(report_path).name, use_container_width=True)
        st.download_button(
            "Descargar PNG GM",
            data=image_bytes,
            file_name=Path(report_path).name,
            mime="image/png",
            key="gm_player_download",
        )


def render_dependency_tab(db_signature: tuple[tuple[str, int, int], ...]) -> None:
    st.subheader("Dependencia y riesgo")

    seasons = load_available_seasons(db_signature)
    if not seasons:
        st.info("No hay datos suficientes para construir la vista de dependencia.")
        return

    with st.form("dep_scope_form", clear_on_submit=False):
        apply_row = st.columns([1.2, 4])
        apply_row[0].form_submit_button("Aplicar scope dependencia", use_container_width=True)
        apply_row[1].caption("Los cambios de temporada, liga, fases y jornadas se aplican al enviar este formulario.")

        scope_top_cols = st.columns(2)
        _ensure_select_state(DEP_SCOPE_SEASON_KEY, seasons)
        season = scope_top_cols[0].selectbox("Temporada dependencia", seasons, key=DEP_SCOPE_SEASON_KEY)

        leagues = load_available_leagues(db_signature, season)
        _ensure_select_state(DEP_SCOPE_LEAGUE_KEY, leagues)
        league = scope_top_cols[1].selectbox("Liga dependencia", leagues, key=DEP_SCOPE_LEAGUE_KEY)

        available_phases = load_available_phases(db_signature, season, league)
        _ensure_multiselect_state(DEP_SCOPE_PHASES_KEY, available_phases)
        selected_phases = st.multiselect(
            "Fases dependencia",
            options=available_phases,
            key=DEP_SCOPE_PHASES_KEY,
            placeholder="Vacio = todas las fases",
        )

        available_jornadas = load_available_jornadas(db_signature, season, league, tuple(selected_phases))
        _ensure_multiselect_state(DEP_SCOPE_JORNADAS_KEY, available_jornadas)
        selected_jornadas = st.multiselect(
            "Jornadas dependencia",
            options=available_jornadas,
            key=DEP_SCOPE_JORNADAS_KEY,
            placeholder="Vacio = todas las jornadas",
        )

    dependency_df = load_dependency_view_data(
        db_signature,
        season,
        league,
        tuple(selected_phases),
        tuple(selected_jornadas),
    )
    bundle = load_report_bundle(
        db_signature,
        season,
        league,
        tuple(selected_phases),
        tuple(selected_jornadas),
    )
    if dependency_df.empty:
        st.info("No hay jugadores disponibles para el scope de dependencia seleccionado.")
        return

    teams = sorted(dependency_df["EQUIPO"].dropna().astype(str).unique().tolist())
    if not teams:
        st.info("No hay equipos disponibles en el scope actual.")
        return

    phases_summary = ", ".join(selected_phases) if selected_phases else "todas"
    jornadas_summary = ", ".join(str(value) for value in selected_jornadas) if selected_jornadas else "todas"
    st.caption(
        f"Scope: {season} | {league} | Fases: {phases_summary} | Jornadas: {jornadas_summary} | "
        "Comparacion interna dentro del scope actual."
    )

    _ensure_select_state(DEP_SELECTED_TEAM_KEY, teams)
    selected_team = st.selectbox("Equipo objetivo", teams, key=DEP_SELECTED_TEAM_KEY)

    team_df = dependency_df[dependency_df["EQUIPO"] == selected_team].copy()
    if team_df.empty:
        st.info("No hay jugadores para el equipo seleccionado en este scope.")
        return

    team_df = team_df.sort_values(
        by=["DEPENDENCIA_SCORE", "%PLAYS_EQUIPO", "PJ"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    has_clutch = bool(team_df["HAS_CLUTCH_DATA"].fillna(False).any())
    if not has_clutch:
        st.info("Este equipo no tiene datos clutch en el scope actual. El score se reescala con las metricas disponibles.")

    critical_row = team_df.iloc[0]
    use_top_row = team_df.sort_values(by="%PLAYS_EQUIPO", ascending=False, na_position="last").iloc[0]
    points_top_row = team_df.sort_values(by="%PUNTOS_EQUIPO", ascending=False, na_position="last").iloc[0]
    ast_top_row = team_df.sort_values(by="%AST_EQUIPO", ascending=False, na_position="last").iloc[0]
    top3_use = pd.to_numeric(team_df["%PLAYS_EQUIPO"], errors="coerce").fillna(0.0).nlargest(3).sum()

    summary_cols = st.columns(5)
    summary_cols[0].metric(
        "Jugador critico",
        str(critical_row["JUGADOR"]),
        f"{float(critical_row['DEPENDENCIA_SCORE']):.1f} score",
    )
    summary_cols[1].metric(
        "Uso ofensivo top1",
        str(use_top_row["JUGADOR"]),
        f"{float(use_top_row['%PLAYS_EQUIPO']):.1f}%",
    )
    summary_cols[2].metric(
        "Anotacion top1",
        str(points_top_row["JUGADOR"]),
        f"{float(points_top_row['%PUNTOS_EQUIPO']):.1f}%",
    )
    summary_cols[3].metric(
        "Creacion top1",
        str(ast_top_row["JUGADOR"]),
        f"{float(ast_top_row['%AST_EQUIPO']):.1f}%",
    )
    summary_cols[4].metric("Concentracion top3", f"{float(top3_use):.1f}%")

    st.caption("Concentracion top3 = suma del % de plays de los 3 jugadores con mas uso ofensivo.")
    st.caption("Los porcentajes de dependencia se calculan sobre el total del equipo en los partidos que ese jugador ha disputado.")
    st.caption(build_structural_risk_summary(team_df))

    display_columns = [column for column in DEPENDENCY_DEFAULT_TABLE_COLUMNS if column in team_df.columns]
    if has_clutch and "%MIN_CLUTCH_EQUIPO" in team_df.columns and "%MIN_CLUTCH_EQUIPO" not in display_columns:
        score_index = display_columns.index("DEPENDENCIA_SCORE") if "DEPENDENCIA_SCORE" in display_columns else len(display_columns)
        display_columns.insert(score_index, "%MIN_CLUTCH_EQUIPO")

    st.dataframe(team_df[display_columns], use_container_width=True, hide_index=True)

    safe_team_name = re.sub(r"[^A-Za-z0-9_-]+", "_", selected_team.strip()).strip("_") or "equipo"
    st.download_button(
        "Descargar CSV dependencia",
        data=serialize_dependency_csv(team_df),
        file_name=f"dependencia_{season.replace('/', '-')}_{league.replace(' ', '_').lower()}_{safe_team_name}.csv",
        mime="text/csv",
        key="dependency_download_csv",
    )

    dorsal_lookup = (
        bundle.players_df[[column for column in ["PLAYER_KEY", "DORSAL"] if column in bundle.players_df.columns]]
        .drop_duplicates(subset=["PLAYER_KEY"])
    )
    selectable_players = (
        team_df[["PLAYER_KEY", "JUGADOR"]]
        .drop_duplicates(subset=["PLAYER_KEY"])
        .merge(dorsal_lookup, on="PLAYER_KEY", how="left")
        .sort_values(by=["JUGADOR"])
    )
    player_keys = selectable_players["PLAYER_KEY"].astype(str).tolist()
    _ensure_select_state(DEP_SELECTED_PLAYER_KEY, player_keys)
    player_labels = {
        str(row["PLAYER_KEY"]): _build_player_selection_label(row["JUGADOR"], dorsal=row.get("DORSAL"))
        for _, row in selectable_players.iterrows()
    }
    selected_player_key = st.selectbox(
        "Jugador para detalle",
        options=player_keys,
        key=DEP_SELECTED_PLAYER_KEY,
        format_func=lambda key: player_labels.get(key, key),
    )

    selected_row = team_df[team_df["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
    selected_player = selected_row.iloc[0] if not selected_row.empty else None
    if selected_player is None:
        return
    bundle_player_rows = bundle.players_df[bundle.players_df["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
    bundle_player = bundle_player_rows.iloc[0] if not bundle_player_rows.empty else None
    player_dorsal = _format_optional_dorsal(bundle_player.get("DORSAL") if bundle_player is not None else None)
    player_display_name = f"{player_dorsal} {selected_player['JUGADOR']}".strip()

    st.markdown("---")
    st.write("**Detalle de dependencia**")

    profile_cols = st.columns([1.0, 3.2])
    image_value = bundle_player.get("IMAGEN") if bundle_player is not None and "IMAGEN" in bundle_player.index else None
    profile_cols[0].image(_resolve_player_image_source(image_value), use_container_width=True)

    with profile_cols[1]:
        st.markdown(f"### {player_display_name}")
        detail_cols = st.columns(4)
        detail_cols[0].metric("Equipo", _display_or_dash(selected_player["EQUIPO"]))
        detail_cols[1].metric("PJ", _display_or_dash(selected_player["PJ"]))
        detail_cols[2].metric("Riesgo", _display_or_dash(selected_player["DEPENDENCIA_RIESGO"]))
        detail_cols[3].metric("Foco principal", _display_or_dash(selected_player["FOCO_PRINCIPAL"]))

    metric_pairs = [
        ("Score dependencia", f"{_as_float(selected_player['DEPENDENCIA_SCORE']):.1f}"),
        ("% uso ofensivo", f"{_as_float(selected_player['%PLAYS_EQUIPO']):.1f}%"),
        ("% anotacion", f"{_as_float(selected_player['%PUNTOS_EQUIPO']):.1f}%"),
        ("% creacion", f"{_as_float(selected_player['%AST_EQUIPO']):.1f}%"),
        ("% rebote", f"{_as_float(selected_player['%REB_EQUIPO']):.1f}%"),
    ]
    if has_clutch:
        clutch_text = "-" if pd.isna(selected_player["%MIN_CLUTCH_EQUIPO"]) else f"{_as_float(selected_player['%MIN_CLUTCH_EQUIPO']):.1f}%"
        metric_pairs.append(("% minutos clutch", clutch_text))

    metric_cols = st.columns(len(metric_pairs))
    for column, (label, value) in zip(metric_cols, metric_pairs):
        column.metric(label, value)

    st.caption(build_player_dependency_diagnosis(selected_player))

def _trend_metric_decimals(metric: str) -> int:
    if metric in {"PLAYS", "OFFRTG", "DEFRTG", "NETRTG", "%REB"}:
        return 2
    return 1


def _format_trend_metric(metric: str, value: float) -> str:
    return f"{value:.{_trend_metric_decimals(metric)}f}"


def _render_trend_summary_kpis(
    summary_df: pd.DataFrame,
    metric_order: list[str],
    metric_labels: dict[str, str],
    recent_count: int,
) -> None:
    if summary_df.empty:
        return

    indexed = summary_df.set_index("metric")
    for metric_chunk in (metric_order[:3], metric_order[3:]):
        if not metric_chunk:
            continue
        cols = st.columns(len(metric_chunk))
        for col, metric in zip(cols, metric_chunk):
            row = indexed.loc[metric] if metric in indexed.index else pd.Series({"recent_avg": 0.0, "delta": 0.0})
            col.metric(
                f"{metric_labels.get(metric, metric)} ult. {recent_count}",
                _format_trend_metric(metric, float(row.get("recent_avg", 0.0))),
                f"{float(row.get('delta', 0.0)):+.{_trend_metric_decimals(metric)}f} vs media",
            )


def _resolve_trend_window(widget_key: str, available_games: int) -> int:
    if available_games <= 0:
        st.session_state.pop(widget_key, None)
        return 0

    if available_games == 1:
        st.session_state[widget_key] = 1
        st.caption("Solo hay 1 partido disponible en este scope.")
        return 1

    default_window = min(5, available_games)
    current_window = pd.to_numeric(
        pd.Series([st.session_state.get(widget_key, default_window)]),
        errors="coerce",
    ).fillna(default_window).iloc[0]
    if current_window < 1 or current_window > available_games:
        st.session_state[widget_key] = default_window

    return st.slider(
        "Partidos a mostrar",
        min_value=1,
        max_value=available_games,
        value=int(st.session_state.get(widget_key, default_window)),
        key=widget_key,
    )


def _render_trend_chart(chart_df: pd.DataFrame, metrics: list[str], metric_labels: dict[str, str], chart_key: str) -> None:
    valid_metrics = [metric for metric in metrics if metric in chart_df.columns]
    if chart_df.empty or not valid_metrics:
        return

    value_vars = ["PARTIDO", "__ORDER", *valid_metrics]
    if "JORNADA" in chart_df.columns:
        value_vars.append("JORNADA")
    chart_long = chart_df[value_vars].melt(
        id_vars=[column for column in ["PARTIDO", "JORNADA", "__ORDER"] if column in chart_df.columns],
        value_vars=valid_metrics,
        var_name="METRICA",
        value_name="VALOR",
    )
    chart_long["METRICA_LABEL"] = chart_long["METRICA"].map(lambda value: metric_labels.get(value, value))

    chart = (
        alt.Chart(chart_long)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "PARTIDO:N",
                sort=alt.EncodingSortField(field="__ORDER", order="ascending"),
                axis=alt.Axis(labelAngle=-35, title="Partido"),
            ),
            y=alt.Y("VALOR:Q", title="Valor"),
            color=alt.Color("METRICA_LABEL:N", title="Metrica"),
            tooltip=[
                alt.Tooltip("PARTIDO:N", title="Partido"),
                *([alt.Tooltip("JORNADA:Q", title="Jornada")] if "JORNADA" in chart_long.columns else []),
                alt.Tooltip("METRICA_LABEL:N", title="Metrica"),
                alt.Tooltip("VALOR:Q", title="Valor", format=".2f"),
            ],
        )
    )
    st.altair_chart(chart, use_container_width=True, key=chart_key)


def _render_player_trends_tab(bundle: ReportBundle) -> None:
    if bundle.players_df.empty or bundle.boxscores_df.empty:
        st.info("No hay datos suficientes de jugadores para el scope actual.")
        return

    players_source = (
        bundle.players_df[[column for column in ["PLAYER_KEY", "JUGADOR", "EQUIPO", "DORSAL"] if column in bundle.players_df.columns]]
        .dropna(subset=["PLAYER_KEY", "JUGADOR"])
        .drop_duplicates(subset=["PLAYER_KEY"])
        .sort_values(by=["JUGADOR", "EQUIPO"])
    )
    if players_source.empty:
        st.info("No hay jugadores disponibles en este scope.")
        return

    player_keys = players_source["PLAYER_KEY"].astype(str).tolist()
    _ensure_select_state(TREND_SELECTED_PLAYER_KEY, player_keys)
    player_labels = {
        str(row["PLAYER_KEY"]): _build_player_selection_label(row["JUGADOR"], row.get("EQUIPO"), row.get("DORSAL"))
        for _, row in players_source.iterrows()
    }
    selected_player_key = st.selectbox(
        "Jugador",
        options=player_keys,
        key=TREND_SELECTED_PLAYER_KEY,
        format_func=lambda key: player_labels.get(key, key),
    )

    player_games_df = bundle.boxscores_df[bundle.boxscores_df["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
    if "IdPartido" in player_games_df.columns:
        available_player_games = int(player_games_df["IdPartido"].nunique())
    else:
        available_player_games = int(player_games_df.shape[0])
    player_window = _resolve_trend_window(TREND_PLAYER_WINDOW_KEY, available_player_games)
    if player_window <= 0:
        st.info("No hay partidos recientes para el jugador seleccionado.")
        return

    recent_df = build_recent_player_games(bundle.boxscores_df, str(selected_player_key), last_n=player_window)
    if recent_df.empty:
        st.info("No hay partidos recientes para el jugador seleccionado.")
        return

    recent_count = int(recent_df.shape[0])
    baseline = build_player_scope_baseline(bundle.players_df, str(selected_player_key))
    summary_df = build_recent_vs_scope_summary(recent_df, baseline, list(PLAYER_TREND_METRIC_OPTIONS.keys()))

    st.caption(f"Ultimos {recent_count} partidos vs media del scope actual.")
    _render_trend_summary_kpis(summary_df, list(PLAYER_TREND_METRIC_OPTIONS.keys()), PLAYER_TREND_METRIC_OPTIONS, recent_count)

    player_metric_options = list(PLAYER_TREND_METRIC_OPTIONS.keys())
    _ensure_multiselect_default_state(TREND_PLAYER_CHART_METRICS_KEY, player_metric_options, [player_metric_options[0]])
    selected_metrics = st.multiselect(
        "Metricas del grafico",
        options=player_metric_options,
        key=TREND_PLAYER_CHART_METRICS_KEY,
        format_func=lambda metric: PLAYER_TREND_METRIC_OPTIONS.get(metric, metric),
    )
    if not selected_metrics:
        st.info("Selecciona al menos una metrica para el grafico.")
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
        return

    chart_df = build_trend_chart_frame(recent_df, selected_metrics)
    st.caption("El grafico va de mas antiguo a mas reciente dentro de los filtros actuales.")
    if not chart_df.empty:
        player_chart_key = f"trend-player-chart::{selected_player_key}::{player_window}::{'|'.join(selected_metrics)}::{len(chart_df)}"
        _render_trend_chart(chart_df, selected_metrics, PLAYER_TREND_METRIC_OPTIONS, player_chart_key)
        if len(selected_metrics) > 1:
            st.caption("Las metricas comparten el mismo eje Y en este grafico.")
    st.dataframe(recent_df, use_container_width=True, hide_index=True)


def _render_team_trends_tab(bundle: ReportBundle) -> None:
    if bundle.games_df.empty:
        st.info("No hay datos suficientes de equipos para el scope actual.")
        return

    team_options = sorted(bundle.games_df["EQUIPO LOCAL"].dropna().astype(str).unique().tolist())
    if not team_options:
        st.info("No hay equipos disponibles en este scope.")
        return

    _ensure_select_state(TREND_SELECTED_TEAM_KEY, team_options)
    selected_team = st.selectbox("Equipo", team_options, key=TREND_SELECTED_TEAM_KEY)

    team_games_df = bundle.games_df[bundle.games_df["EQUIPO LOCAL"].astype(str) == str(selected_team)].copy()
    if "PID" in team_games_df.columns:
        available_team_games = int(team_games_df["PID"].nunique())
    else:
        available_team_games = int(team_games_df.shape[0])
    team_window = _resolve_trend_window(TREND_TEAM_WINDOW_KEY, available_team_games)
    if team_window <= 0:
        st.info("No hay partidos recientes para el equipo seleccionado.")
        return

    recent_df = build_recent_team_games(bundle.games_df, selected_team, last_n=team_window)
    if recent_df.empty:
        st.info("No hay partidos recientes para el equipo seleccionado.")
        return

    recent_count = int(recent_df.shape[0])
    baseline = build_team_scope_baseline(bundle.games_df, selected_team)
    summary_df = build_recent_vs_scope_summary(recent_df, baseline, list(TEAM_TREND_METRIC_OPTIONS.keys()))

    st.caption(f"Ultimos {recent_count} partidos vs media del scope actual.")
    _render_trend_summary_kpis(summary_df, list(TEAM_TREND_METRIC_OPTIONS.keys()), TEAM_TREND_METRIC_OPTIONS, recent_count)

    team_metric_options = list(TEAM_TREND_METRIC_OPTIONS.keys())
    _ensure_multiselect_default_state(TREND_TEAM_CHART_METRICS_KEY, team_metric_options, [team_metric_options[0]])
    selected_metrics = st.multiselect(
        "Metricas del grafico",
        options=team_metric_options,
        key=TREND_TEAM_CHART_METRICS_KEY,
        format_func=lambda metric: TEAM_TREND_METRIC_OPTIONS.get(metric, metric),
    )
    if not selected_metrics:
        st.info("Selecciona al menos una metrica para el grafico.")
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
        return

    chart_df = build_trend_chart_frame(recent_df, selected_metrics)
    st.caption("El grafico va de mas antiguo a mas reciente dentro de los filtros actuales.")
    if not chart_df.empty:
        team_chart_key = f"trend-team-chart::{selected_team}::{team_window}::{'|'.join(selected_metrics)}::{len(chart_df)}"
        _render_trend_chart(chart_df, selected_metrics, TEAM_TREND_METRIC_OPTIONS, team_chart_key)
        if len(selected_metrics) > 1:
            st.caption("Las metricas comparten el mismo eje Y en este grafico.")
    st.dataframe(recent_df, use_container_width=True, hide_index=True)


def render_trends_tab(db_signature: tuple[tuple[str, int, int], ...]) -> None:
    st.subheader("Tendencias")

    seasons = load_available_seasons(db_signature)
    if not seasons:
        st.info("No hay datos suficientes para construir la vista de tendencias.")
        return

    with st.form("trend_scope_form", clear_on_submit=False):
        apply_row = st.columns([1.1, 4])
        apply_row[0].form_submit_button("Aplicar scope tendencias", use_container_width=True)
        apply_row[1].caption("Los filtros de tendencias son independientes de GM y Dependencia.")

        top_cols = st.columns(2)
        _ensure_select_state(TREND_SCOPE_SEASON_KEY, seasons)
        season = top_cols[0].selectbox("Temporada tendencias", seasons, key=TREND_SCOPE_SEASON_KEY)

        leagues = load_available_leagues(db_signature, season)
        _ensure_select_state(TREND_SCOPE_LEAGUE_KEY, leagues)
        league = top_cols[1].selectbox("Liga tendencias", leagues, key=TREND_SCOPE_LEAGUE_KEY)

        available_phases = load_available_phases(db_signature, season, league)
        _ensure_multiselect_state(TREND_SCOPE_PHASES_KEY, available_phases)
        selected_phases = st.multiselect(
            "Fases tendencias",
            options=available_phases,
            key=TREND_SCOPE_PHASES_KEY,
            placeholder="Vacio = todas las fases",
        )

        available_jornadas = load_available_jornadas(db_signature, season, league, tuple(selected_phases))
        _ensure_multiselect_state(TREND_SCOPE_JORNADAS_KEY, available_jornadas)
        selected_jornadas = st.multiselect(
            "Jornadas tendencias",
            options=available_jornadas,
            key=TREND_SCOPE_JORNADAS_KEY,
            placeholder="Vacio = todas las jornadas",
        )

    bundle = load_report_bundle(
        db_signature,
        season,
        league,
        tuple(selected_phases),
        tuple(selected_jornadas),
    )
    if bundle.players_df.empty and bundle.games_df.empty:
        st.info("No hay datos de tendencias disponibles en el scope actual.")
        return

    phases_summary = ", ".join(selected_phases) if selected_phases else "todas"
    jornadas_summary = ", ".join(str(value) for value in selected_jornadas) if selected_jornadas else "todas"
    st.caption(f"Scope: {season} | {league} | Fases: {phases_summary} | Jornadas: {jornadas_summary}")

    player_tab, team_tab = st.tabs(["Jugadores", "Equipos"])
    with player_tab:
        _render_player_trends_tab(bundle)
    with team_tab:
        _render_team_trends_tab(bundle)


def render_player_tab(bundle: ReportBundle) -> None:
    st.subheader("Informe de jugador")
    if bundle.players_df.empty:
        st.info("No hay jugadores disponibles para el filtro actual.")
        return

    team_options = ["Todos"] + sorted(bundle.players_df["EQUIPO"].dropna().astype(str).unique().tolist())
    selected_team = st.selectbox("Equipo", team_options, key="player_team")

    players_source = bundle.players_df
    if selected_team != "Todos":
        players_source = players_source[players_source["EQUIPO"] == selected_team]

    selectable_players = (
        players_source[[column for column in ["PLAYER_KEY", "JUGADOR", "EQUIPO", "DORSAL"] if column in players_source.columns]]
        .dropna(subset=["PLAYER_KEY", "JUGADOR"])
        .drop_duplicates(subset=["PLAYER_KEY"])
        .sort_values(by=["JUGADOR", "EQUIPO"])
    )
    player_keys = selectable_players["PLAYER_KEY"].astype(str).tolist()
    _ensure_select_state("player_name", player_keys)
    player_labels = {
        str(row["PLAYER_KEY"]): _build_player_selection_label(row["JUGADOR"], row.get("EQUIPO"), row.get("DORSAL"))
        for _, row in selectable_players.iterrows()
    }
    selected_player_key = st.selectbox("Jugador", player_keys, key="player_name", format_func=lambda key: player_labels.get(key, key))
    selected_player_rows = selectable_players[selectable_players["PLAYER_KEY"].astype(str) == str(selected_player_key)].copy()
    if selected_player_rows.empty:
        st.info("No se ha encontrado el jugador seleccionado.")
        return
    player_name = str(selected_player_rows.iloc[0]["JUGADOR"])

    if st.button("Generar informe de jugador", type="primary", key="player_generate"):
        with st.spinner("Generando informe de jugador..."):
            path = get_generate_report_fn()(
                player_name,
                output_dir=PLAYER_REPORTS_DIR,
                overwrite=True,
                data_df=bundle.players_df,
                teams_df=bundle.teams_df,
                clutch_df=bundle.clutch_df,
            )
        st.session_state["player_report_path"] = str(path)

    report_path = st.session_state.get("player_report_path")
    if report_path and Path(report_path).exists():
        image_bytes = Path(report_path).read_bytes()
        st.image(image_bytes, caption=Path(report_path).name, use_container_width=True)
        st.download_button(
            "Descargar PNG",
            data=image_bytes,
            file_name=Path(report_path).name,
            mime="image/png",
            key="player_download",
        )


def render_team_tab(bundle: ReportBundle) -> None:
    st.subheader("Informe de equipo")
    if bundle.players_df.empty or bundle.teams_df.empty:
        st.info("No hay datos de equipo para el filtro actual.")
        return

    teams = sorted(bundle.teams_df["EQUIPO"].dropna().astype(str).unique().tolist())
    selected_team = st.selectbox("Equipo objetivo", teams, key="team_name")
    team_players_source = (
        bundle.players_df[bundle.players_df["EQUIPO"] == selected_team][[column for column in ["PLAYER_KEY", "JUGADOR", "DORSAL"] if column in bundle.players_df.columns]]
        .dropna(subset=["PLAYER_KEY", "JUGADOR"])
        .drop_duplicates(subset=["PLAYER_KEY"])
        .sort_values(by=["JUGADOR"])
    )
    team_player_keys = team_players_source["PLAYER_KEY"].astype(str).tolist()
    _ensure_multiselect_state("team_players", team_player_keys)
    team_player_labels = {
        str(row["PLAYER_KEY"]): _build_player_selection_label(row["JUGADOR"], dorsal=row.get("DORSAL"))
        for _, row in team_players_source.iterrows()
    }
    selected_player_keys = st.multiselect(
        "Jugadores concretos (opcional)",
        options=team_player_keys,
        default=[],
        key="team_players",
        format_func=lambda key: team_player_labels.get(key, key),
    )
    selected_players = (
        team_players_source[team_players_source["PLAYER_KEY"].astype(str).isin([str(value) for value in selected_player_keys])]["JUGADOR"]
        .dropna()
        .astype(str)
        .tolist()
    )
    rival_options = [""] + [team for team in teams if team != selected_team]
    selected_rival = st.selectbox("Rival para H2H (opcional)", rival_options, key="team_rival")

    col1, col2 = st.columns(2)
    with col1:
        home_away_filter = st.radio("Filtro general", ["Todos", "Local", "Visitante"], horizontal=True, key="team_home_away")
    with col2:
        h2h_home_away_filter = st.radio("Filtro H2H", ["Todos", "Local", "Visitante"], horizontal=True, key="team_h2h_home_away")

    col3, col4, col5 = st.columns(3)
    with col3:
        min_games = st.slider("Min partidos", 0, 20, 5, 1, key="team_min_games")
    with col4:
        min_minutes = st.slider("Min minutos", 0, 200, 50, 10, key="team_min_minutes")
    with col5:
        min_shots = st.slider("Min tiros", 0, 100, 20, 5, key="team_min_shots")

    if st.button("Generar informe de equipo", type="primary", key="team_generate"):
        with st.spinner("Generando informe de equipo..."):
            path = get_build_team_report_fn()(
                team_filter=selected_team if not selected_players else None,
                player_filter=selected_players or None,
                rival_team=selected_rival or None,
                home_away_filter=home_away_filter,
                h2h_home_away_filter=h2h_home_away_filter,
                min_games=min_games,
                min_minutes=min_minutes,
                min_shots=min_shots,
                players_df=bundle.players_df,
                teams_df=bundle.teams_df,
                assists_df=bundle.assists_df,
                clutch_lineups_df=bundle.clutch_lineups_df,
            )
        st.session_state["team_report_path"] = str(path)

    report_path = st.session_state.get("team_report_path")
    if report_path and Path(report_path).exists():
        pdf_bytes = Path(report_path).read_bytes()
        st.success(Path(report_path).name)
        st.download_button(
            "Descargar PDF",
            data=pdf_bytes,
            file_name=Path(report_path).name,
            mime="application/pdf",
            key="team_download",
        )


def render_phase_tab(bundle: ReportBundle, filters: ReportFilters | None) -> None:
    st.subheader("Informe de fase")
    if bundle.players_df.empty or bundle.teams_df.empty:
        st.info("No hay datos de fase para el filtro actual.")
        return

    available_teams = sorted(bundle.teams_df["EQUIPO"].dropna().astype(str).unique().tolist())
    selected_teams = st.multiselect("Equipos a incluir (opcional)", available_teams, default=[], key="phase_teams")

    col1, col2, col3 = st.columns(3)
    with col1:
        min_games = st.slider("Min partidos", 0, 20, 5, 1, key="phase_min_games")
    with col2:
        min_minutes = st.slider("Min minutos", 0, 200, 50, 10, key="phase_min_minutes")
    with col3:
        min_shots = st.slider("Min tiros", 0, 100, 20, 5, key="phase_min_shots")

    filter_text = ", ".join(filters.phases) if filters and filters.phases else "todas las fases"
    st.caption(f"El PDF se genera con el scope ya filtrado desde SQLite: {filter_text}.")

    if st.button("Generar informe de fase", type="primary", key="phase_generate"):
        with st.spinner("Generando informe de fase..."):
            path = get_build_phase_report_fn()(
                teams=selected_teams or None,
                phase=None,
                min_games=min_games,
                min_minutes=min_minutes,
                min_shots=min_shots,
                teams_df=bundle.teams_df,
                players_df=bundle.players_df,
            )
        st.session_state["phase_report_path"] = str(path)

    report_path = st.session_state.get("phase_report_path")
    if report_path and Path(report_path).exists():
        pdf_bytes = Path(report_path).read_bytes()
        st.success(Path(report_path).name)
        st.download_button(
            "Descargar PDF",
            data=pdf_bytes,
            file_name=Path(report_path).name,
            mime="application/pdf",
            key="phase_download",
        )


def build_targets_from_selection(season: str, leagues: list[str], jornadas: list[int]) -> list[dict[str, Any]]:
    targets = []
    for league in leagues:
        phases = st.session_state.get(f"manual_phases::{league}", get_liga_fases(league))
        targets.append(
            {
                "season": season,
                "league": league,
                "phases": list(phases) if phases else get_liga_fases(league),
                "jornadas": list(jornadas),
                "enabled": True,
            }
        )
    return targets


def run_targets_sync(
    store: DataStore,
    *,
    targets: list[dict[str, Any]],
    revalidate_window: int,
    publish_after: bool,
    commit_message: str,
    scrape_player_bios: bool = True,
    player_bio_limit: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    expanded_targets = expand_targets_by_phase(targets)

    def action(callback):
        tracker = SyncRuntimeTracker()

        def runtime_callback(level: str, message: str) -> None:
            callback(level, message)
            tracker.record_event(level, message)

        try:
            with SyncExecutionLock():
                tracker.start_run(
                    mode="manual",
                    targets=expanded_targets,
                    command="streamlit-manual-sync",
                    cwd=str(REPO_ROOT),
                )
                results = []
                total_targets = len(expanded_targets)
                for index, target in enumerate(expanded_targets, start=1):
                    callback("info", f"Sincronizando {target_label(target)}")
                    tracker.set_scope(target=target, index=index, total=total_targets)
                    summary = store.sync_games(
                        season=target["season"],
                        league=target["league"],
                        phases=list(target["phases"]),
                        jornadas=tuple(target.get("jornadas", [])),
                        revalidate_window=revalidate_window,
                        export_compat_files=True,
                        scrape_player_bios=scrape_player_bios,
                        player_bio_limit=player_bio_limit,
                        progress_callback=runtime_callback,
                        runtime_tracker=tracker,
                    )
                    tracker.complete_scope(target=target, summary=serialize_sync_summary(summary))
                    results.append(
                        {
                            "season": target["season"],
                            "league": target["league"],
                            "phases": list(target["phases"]),
                            "jornadas": list(target.get("jornadas", [])),
                            "summary": serialize_sync_summary(summary),
                        }
                    )

                published = False
                if publish_after:
                    tracker.set_step(step="publishing", message="Publicando cambios en GitHub")
                    published = store.publish_data_changes(
                        repo_root=REPO_ROOT,
                        commit_message=commit_message,
                        progress_callback=runtime_callback,
                    )

                tracker.finish_run(published=published, results=results)
                return {"targets": results, "published": published}
        except SyncAlreadyRunningError as exc:
            callback("warning", str(exc))
            return {"targets": [], "published": False, "error": str(exc)}
        except Exception as exc:
            if tracker.state:
                tracker.fail_run(f"Sync abortado: {type(exc).__name__}: {exc}")
            raise

    return capture_logs(action)


def render_scraper_tab(store: DataStore) -> None:
    st.subheader("Sincronizacion manual")
    st.caption("El estado exacto del proceso activo y la cola siguiente estan en la pestana `Base de datos`.")
    st.info(
        "Para scrapeear Primera FEB 25/26 y Segunda FEB 25/26: selecciona `2025/2026`, marca `Primera FEB` y `Segunda FEB`, deja las fases por defecto y pulsa `Sincronizar seleccion`."
    )
    st.caption("Cada sync hace dos fases seguidas: primero partidos y despues bios de jugadores pendientes. Las bios no son opcionales.")

    manual_season = st.selectbox("Temporada a sincronizar", TEMPORADAS_DISPONIBLES, index=len(TEMPORADAS_DISPONIBLES) - 1)
    manual_leagues = st.multiselect(
        "Ligas a sincronizar",
        options=list(LIGAS_DISPONIBLES.keys()),
        default=[],
        placeholder="Selecciona una o varias ligas",
    )

    for league in manual_leagues:
        st.multiselect(
            f"Fases para {league}",
            options=get_liga_fases(league),
            default=get_liga_fases(league),
            key=f"manual_phases::{league}",
        )

    jornadas_text = st.text_input(
        "Jornadas concretas (opcional)",
        value="",
        placeholder="Ejemplo: 1,2,3. Si lo dejas vacio se sincroniza todo y se revalidan las 2 ultimas jornadas.",
    )

    try:
        jornadas = parse_jornadas_text(jornadas_text)
    except ValueError:
        jornadas = []
        st.error("El campo de jornadas debe tener numeros separados por comas.")

    col1, col2 = st.columns(2)
    with col1:
        revalidate_window = st.number_input(
            "Revalidar ultimas jornadas por fase",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
        )
    with col2:
        publish_after = st.checkbox("Hacer commit/push al terminar", value=False)

    commit_message = st.text_input(
        "Mensaje de commit",
        value=f"chore(data): sync FEB data {time.strftime('%Y-%m-%d %H:%M')}",
    )

    targets = build_targets_from_selection(manual_season, manual_leagues, jornadas)
    expanded_manual_targets = expand_targets_by_phase(targets)
    if expanded_manual_targets:
        st.caption("Scopes seleccionados:")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Temporada": target["season"],
                        "Liga": target["league"],
                        "Fases": ", ".join(target["phases"]),
                        "Jornadas": ", ".join(str(value) for value in target.get("jornadas", [])) or "todas",
                    }
                    for target in expanded_manual_targets
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if st.button("Sincronizar seleccion", type="primary", key="manual_sync"):
        if not expanded_manual_targets:
            st.warning("Selecciona al menos una liga.")
        else:
            result, logs = run_targets_sync(
                store,
                targets=expanded_manual_targets,
                revalidate_window=int(revalidate_window),
                publish_after=publish_after,
                commit_message=commit_message,
                scrape_player_bios=True,
            )
            rerun_with_feedback("Sincronizacion manual multiliga", result, logs)

    st.markdown("---")
    st.subheader("Autosync semanal")
    auto_config = load_auto_sync_config()
    auto_publish = st.checkbox("Publicar automaticamente cada semana", value=bool(auto_config.get("publish", True)))
    auto_revalidate = st.number_input(
        "Ventana semanal de revalidacion",
        min_value=1,
        max_value=5,
        value=int(auto_config.get("revalidate_window", 2)),
        step=1,
        key="auto_revalidate_window",
    )

    if st.button("Guardar seleccion actual como autosync semanal", key="save_auto_sync"):
        if not expanded_manual_targets:
            st.warning("Selecciona primero una o varias ligas en la parte superior.")
        else:
            path = save_auto_sync_config(
                {
                    "revalidate_window": int(auto_revalidate),
                    "publish": auto_publish,
                    "targets": expanded_manual_targets,
                }
            )
            rerun_with_feedback(
                "Configuracion autosync",
                {"file": str(path), "targets": expanded_manual_targets, "publish": auto_publish},
                [{"level": "success", "message": f"Autosync guardado en {path}"}],
            )

    auto_targets = iter_enabled_targets(auto_config)
    if auto_targets:
        st.write("Objetivos guardados:")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Temporada": target["season"],
                        "Liga": target["league"],
                        "Fases": ", ".join(target["phases"]),
                        "Jornadas": ", ".join(str(value) for value in target.get("jornadas", [])) or "todas",
                    }
                    for target in auto_targets
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        if st.button("Ejecutar autosync guardado ahora", key="run_saved_auto_sync"):
            result, logs = run_targets_sync(
                store,
                targets=auto_targets,
                revalidate_window=int(auto_config.get("revalidate_window", 2)),
                publish_after=bool(auto_config.get("publish", True)),
                commit_message=commit_message,
                scrape_player_bios=True,
            )
            rerun_with_feedback("Autosync semanal manual", result, logs)
    else:
        st.info("No hay objetivos semanales guardados todavia.")

    schedule_command = f'powershell -ExecutionPolicy Bypass -File "{REPO_ROOT / "scripts" / "register_sunday_sync.ps1"}"'
    st.caption(f"Programacion recomendada: cada {DEFAULT_SYNC_DAY} a las {DEFAULT_SYNC_TIME}.")
    st.code(schedule_command)
    st.write(
        "La tarea semanal ejecuta `scripts/sync_and_publish.py --all-targets --publish`, revisa las ultimas dos jornadas por fase, solo scrapea lo que falte o haya que revalidar y despues completa las bios pendientes."
    )
    if st.button("Registrar tarea semanal del domingo", key="register_weekly_task"):
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO_ROOT / "scripts" / "register_sunday_sync.ps1"),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        logs = []
        if result.stdout.strip():
            logs.extend({"level": "info", "message": line} for line in result.stdout.strip().splitlines())
        if result.stderr.strip():
            logs.extend({"level": "warning", "message": line} for line in result.stderr.strip().splitlines())
        if result.returncode == 0:
            logs.append({"level": "success", "message": "Tarea semanal registrada correctamente."})
            rerun_with_feedback("Registro tarea semanal", {"registered": True}, logs)
        else:
            rerun_with_feedback("Registro tarea semanal", {"registered": False}, logs)

    with st.expander("Avanzado"):
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Importar historico Excel", key="advanced_import"):
                result, logs = capture_logs(lambda cb: store.import_historical(progress_callback=cb))
                rerun_with_feedback("Importacion historica", result, logs)
        with col_b:
            if st.button("Publicar cambios pendientes", key="advanced_publish"):
                result, logs = capture_logs(
                    lambda cb: store.publish_data_changes(
                        repo_root=REPO_ROOT,
                        commit_message=commit_message,
                        progress_callback=cb,
                    )
                )
                rerun_with_feedback("Publicacion manual", {"published": bool(result)}, logs)


def main() -> None:
    st.set_page_config(page_title="FEB Reports", page_icon="🏀", layout="wide", initial_sidebar_state="expanded")

    app_mode = get_app_mode()
    cloud_mode = is_cloud_mode()
    store = get_store()

    st.title("FEB Reports")
    st.caption(f"Modo activo: `{app_mode}`. Base principal: `{SQLITE_DB_FILE}`.")
    render_feedback()

    db_signature = get_db_signature()
    has_data = load_db_summary(db_signature)["games"] > 0

    page_names = ["Base de datos", "GM", "Dependencia", "Tendencias", "Jugador", "Equipo", "Fase"]
    if not cloud_mode:
        page_names.append("Scraper")

    with st.sidebar:
        st.header("Vista")
        _ensure_select_state(APP_PAGE_KEY, page_names)
        active_page = st.radio("Vista activa", page_names, key=APP_PAGE_KEY, label_visibility="collapsed")

    filters: ReportFilters | None = None
    bundle = empty_bundle()
    report_pages = {"Jugador", "Equipo", "Fase"}
    if has_data and active_page in report_pages:
        filters, _, _ = build_common_filters(db_signature)
        if filters is not None:
            bundle = load_report_bundle(
                db_signature,
                filters.season,
                filters.league,
                tuple(filters.phases),
                tuple(filters.jornadas),
            )
            with st.sidebar:
                st.markdown("---")
                st.write(f"**Partidos filtrados:** {bundle.games_df.shape[0]}")
                st.write(f"**Jugadores filtrados:** {bundle.players_df.shape[0]}")
                st.write(f"**Equipos filtrados:** {bundle.teams_df.shape[0]}")
    elif active_page in report_pages:
        with st.sidebar:
            st.header("Filtros de informes")
            st.info("Cuando la base tenga datos, aqui apareceran los filtros de temporada, liga, fase y jornada.")

    if cloud_mode:
        with st.sidebar:
            st.info("Modo cloud: la pestaña `Scraper` está oculta y la app funciona en solo lectura.")

    if active_page == "Base de datos":
        render_db_status(store)
        st.markdown("---")
        render_database_tab(db_signature)
    elif active_page == "GM":
        render_gm_tab(db_signature)
    elif active_page == "Dependencia":
        render_dependency_tab(db_signature)
    elif active_page == "Tendencias":
        render_trends_tab(db_signature)
    elif active_page == "Jugador":
        render_player_tab(bundle)
    elif active_page == "Equipo":
        render_team_tab(bundle)
    elif active_page == "Fase":
        render_phase_tab(bundle, filters)
    elif active_page == "Scraper" and not cloud_mode:
        render_scraper_tab(store)


if __name__ == "__main__":
    main()
