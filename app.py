from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

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
    LIGAS_DISPONIBLES,
    PLAYER_REPORTS_DIR,
    SQLITE_DB_FILE,
    SYNC_RUNTIME_STATUS_FILE,
    TEMPORADAS_DISPONIBLES,
    get_liga_fases,
)
from phase_report.build_phase_report import build_phase_report
from player_report.player_report_gen import generate_report
from storage import DataStore, ReportBundle, ReportFilters, SyncSummary
from team_report.build_team_report import build_team_report
from utils.auto_sync import expand_targets_by_phase, iter_enabled_targets, load_auto_sync_config, save_auto_sync_config, target_label
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

    player_options = sorted(players_source["JUGADOR"].dropna().astype(str).unique().tolist())
    player_name = st.selectbox("Jugador", player_options, key="player_name")

    if st.button("Generar informe de jugador", type="primary", key="player_generate"):
        with st.spinner("Generando informe de jugador..."):
            path = generate_report(
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
    team_players = sorted(
        bundle.players_df[bundle.players_df["EQUIPO"] == selected_team]["JUGADOR"].dropna().astype(str).unique().tolist()
    )
    selected_players = st.multiselect(
        "Jugadores concretos (opcional)",
        options=team_players,
        default=[],
        key="team_players",
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
            path = build_team_report(
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
            path = build_phase_report(
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

    has_data = render_db_status(store)
    db_signature = get_db_signature()

    filters: ReportFilters | None = None
    bundle = empty_bundle()
    if has_data:
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
    else:
        with st.sidebar:
            st.header("Filtros de informes")
            st.info("Cuando la base tenga datos, aqui apareceran los filtros de temporada, liga, fase y jornada.")

    if cloud_mode:
        with st.sidebar:
            st.info("Modo cloud: la pestana `Scraper` esta oculta y la app funciona en solo lectura.")

    tab_names = ["Base de datos", "Jugador", "Equipo", "Fase"]
    if not cloud_mode:
        tab_names.append("Scraper")

    tabs = st.tabs(tab_names)
    with tabs[0]:
        render_database_tab(db_signature)
    with tabs[1]:
        render_player_tab(bundle)
    with tabs[2]:
        render_team_tab(bundle)
    with tabs[3]:
        render_phase_tab(bundle, filters)
    if not cloud_mode:
        with tabs[4]:
            render_scraper_tab(store)


if __name__ == "__main__":
    main()
