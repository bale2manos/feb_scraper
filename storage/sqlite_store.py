from __future__ import annotations

import contextlib
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Sequence

import pandas as pd
from unidecode import unidecode

from config import DATA_DIR, SQLITE_DB_FILE, format_season_short, get_liga_url
from config import get_available_files_by_type, parse_filename_info
from scrapers import scraper_all_games
from scrapers.scrape_player_bio import obtener_datos_jugador
from utils import web_scraping
from utils.filename_utils import generate_all_filenames_with_jornadas, get_liga_short
from utils.unified_scraper_integrated import scrape_one_game_unified
from utils.web_scraping import init_driver

if TYPE_CHECKING:
    from utils.sync_runtime import SyncRuntimeTracker


LeagueName = str
SeasonText = str
ProgressCallback = Optional[Callable[[str, str], None]]


LEAGUE_CODE_TO_NAME = {
    "1FEB": "Primera FEB",
    "2FEB": "Segunda FEB",
    "3FEB": "Tercera FEB",
}
LEAGUE_NAME_TO_CODE = {value: key for key, value in LEAGUE_CODE_TO_NAME.items()}

BOX_SCORE_SUM_COLUMNS = [
    "MINUTOS JUGADOS",
    "PUNTOS",
    "T2 CONVERTIDO",
    "T2 INTENTADO",
    "T3 CONVERTIDO",
    "T3 INTENTADO",
    "TL CONVERTIDOS",
    "TL INTENTADOS",
    "REB OFFENSIVO",
    "REB DEFENSIVO",
    "ASISTENCIAS",
    "RECUPEROS",
    "PERDIDAS",
    "FaltasCOMETIDAS",
    "FaltasRECIBIDAS",
    "TAPONES",
]

BOXSCORE_QUERY = """
SELECT
    gc.pid AS "IdPartido",
    gc.phase AS "FASE",
    gc.jornada AS "JORNADA",
    bs.team_name AS "EQUIPO LOCAL",
    bs.opponent_name AS "EQUIPO RIVAL",
    bs.result_label AS "RESULTADO",
    bs.team_points AS "PTS_EQUIPO",
    bs.opponent_points AS "PTS_RIVAL",
    bs.is_starter AS "TITULAR",
    bs.jersey AS "DORSAL",
    bs.player_name AS "JUGADOR",
    bs.minutes_played AS "MINUTOS JUGADOS",
    bs.points AS "PUNTOS",
    bs.t2_made AS "T2 CONVERTIDO",
    bs.t2_att AS "T2 INTENTADO",
    bs.t3_made AS "T3 CONVERTIDO",
    bs.t3_att AS "T3 INTENTADO",
    bs.ft_made AS "TL CONVERTIDOS",
    bs.ft_att AS "TL INTENTADOS",
    bs.oreb AS "REB OFFENSIVO",
    bs.dreb AS "REB DEFENSIVO",
    bs.assists AS "ASISTENCIAS",
    bs.steals AS "RECUPEROS",
    bs.turnovers AS "PERDIDAS",
    bs.fouls_committed AS "FaltasCOMETIDAS",
    bs.fouls_received AS "FaltasRECIBIDAS",
    bs.blocks AS "TAPONES",
    bs.image_url AS "IMAGEN",
    bs.player_url AS "URL JUGADOR",
    bs.player_key AS "PLAYER_KEY"
FROM boxscores bs
JOIN games_catalog gc ON gc.id = bs.game_id
WHERE gc.played = 1
"""

ASSISTS_QUERY = """
SELECT
    gc.pid AS "IdPartido",
    gc.phase AS "FASE",
    gc.jornada AS "JORNADA",
    gc.game_label AS "GAME",
    a.team_name AS "EQUIPO",
    a.passer AS "PASADOR",
    a.scorer AS "ANOTADOR",
    a.n_assists AS "N_ASISTENCIAS"
FROM assists a
JOIN games_catalog gc ON gc.id = a.game_id
WHERE gc.played = 1
"""

CLUTCH_PLAYER_QUERY = """
SELECT
    gc.pid AS "IdPartido",
    gc.phase AS "FASE",
    gc.jornada AS "JORNADA",
    gc.game_label AS "GAME",
    cp.player_name AS "JUGADOR",
    cp.team_name AS "EQUIPO",
    cp.minutes_clutch AS "MINUTOS_CLUTCH",
    cp.seconds_clutch AS "SEGUNDOS_CLUTCH",
    cp.pts AS "PTS",
    cp.fga AS "FGA",
    cp.fgm AS "FGM",
    cp.tpa AS "3PA",
    cp.tpm AS "3PM",
    cp.fta AS "FTA",
    cp.ftm AS "FTM",
    cp.efg_pct AS "eFG%",
    cp.ts_pct AS "TS%",
    cp.ast AS "AST",
    cp.turnovers AS "TO",
    cp.stl AS "STL",
    cp.reb AS "REB",
    cp.reb_o AS "REB_O",
    cp.reb_d AS "REB_D",
    cp.usg_pct AS "USG%",
    cp.plus_minus AS "PLUS_MINUS",
    cp.net_rtg AS "NET_RTG",
    cp.player_key AS "PLAYER_KEY"
FROM clutch_player cp
JOIN games_catalog gc ON gc.id = cp.game_id
WHERE gc.played = 1
"""

CLUTCH_LINEUPS_QUERY = """
SELECT
    gc.pid AS "PARTIDO_ID",
    cl.team_name AS "EQUIPO",
    cl.lineup AS "LINEUP",
    cl.n_jug AS "N_JUG",
    cl.sec_clutch AS "SEC_CLUTCH",
    cl.min_clutch AS "MIN_CLUTCH",
    cl.points_for AS "POINTS_FOR",
    cl.points_against AS "POINTS_AGAINST",
    cl.off_possessions AS "OFF_POSSESSIONS",
    cl.def_possessions AS "DEF_POSSESSIONS",
    cl.off_rtg AS "OFF_RTG",
    cl.def_rtg AS "DEF_RTG",
    cl.net_rtg AS "NET_RTG",
    cl.fga_on AS "FGA_on",
    cl.fta_on AS "FTA_on",
    cl.to_on AS "TO_on",
    cl.orb_on AS "ORB_on",
    cl.opp_fga_on AS "OPP_FGA_on",
    cl.opp_fta_on AS "OPP_FTA_on",
    cl.opp_to_on AS "OPP_TO_on",
    cl.opp_orb_on AS "OPP_ORB_on",
    gc.phase AS "FASE",
    gc.jornada AS "JORNADA",
    gc.game_label AS "GAME"
FROM clutch_lineups cl
JOIN games_catalog gc ON gc.id = cl.game_id
WHERE gc.played = 1
"""


@dataclass(slots=True)
class ReportFilters:
    season: SeasonText
    league: LeagueName
    jornadas: Sequence[int] = field(default_factory=tuple)
    phases: Sequence[str] = field(default_factory=tuple)
    team: Optional[str] = None
    player: Optional[str] = None
    home_away: str = "Todos"


@dataclass(slots=True)
class ReportBundle:
    players_df: pd.DataFrame
    teams_df: pd.DataFrame
    assists_df: pd.DataFrame
    clutch_df: pd.DataFrame
    clutch_lineups_df: pd.DataFrame
    games_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    boxscores_df: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(slots=True)
class SyncSummary:
    discovered_games: int = 0
    missing_games: int = 0
    refreshed_games: int = 0
    scraped_games: int = 0
    skipped_games: int = 0
    failed_games: int = 0
    changed_scopes: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_spaces(value: str) -> str:
    import re

    return re.sub(r"\s+", " ", (value or "").strip())


def _normalize_name(value: str) -> str:
    return _normalize_spaces(unidecode(value or "").upper())


def _pair_key(team_a: str, team_b: str) -> str:
    teams = sorted([_normalize_name(team_a), _normalize_name(team_b)])
    return "||".join(teams)


def _scope_key(season_short: str, league_code: str, phase: str, jornada: int, team_a: str, team_b: str) -> str:
    return "##".join(
        [
            season_short,
            league_code,
            _normalize_name(phase),
            str(int(jornada) if pd.notna(jornada) else 0),
            _pair_key(team_a, team_b),
        ]
    )


def _season_short(value: str) -> str:
    return format_season_short(value) if "/" in value else value


def _season_full(value: str) -> str:
    if "/" in value:
        return value
    year_a, year_b = value.split("_")
    return f"20{year_a}/20{year_b}"


def _league_code(league: str) -> str:
    return LEAGUE_NAME_TO_CODE.get(league, league)


def _league_name(league_code: str) -> str:
    return LEAGUE_CODE_TO_NAME.get(league_code, league_code)


def _parse_game_label(game_label: str) -> tuple[Optional[str], Optional[str]]:
    import re

    text = _normalize_spaces(game_label)
    if not text:
        return None, None
    parts = re.split(r"\s+vs\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None, None


def _safe_float(value, default: float = 0.0) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def _value_or_none(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _player_key(player_name: str, player_url: Optional[str], team_name: Optional[str] = None) -> str:
    if player_url:
        return player_url.strip()
    base = "##".join([_normalize_name(team_name or ""), _normalize_name(player_name)])
    return f"legacy::{base}"


def _lookup_path(relative_or_name: str) -> Path:
    return DATA_DIR / relative_or_name


class DataStore:
    def __init__(self, db_path: Path | str = SQLITE_DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextlib.contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS games_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pid TEXT UNIQUE,
                    scope_key TEXT NOT NULL UNIQUE,
                    season_short TEXT NOT NULL,
                    season_full TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    league_name TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    jornada INTEGER NOT NULL,
                    local_team TEXT,
                    away_team TEXT,
                    score_local INTEGER,
                    score_away INTEGER,
                    score_text TEXT,
                    game_label TEXT,
                    played INTEGER NOT NULL DEFAULT 1,
                    source_scope TEXT,
                    last_seen_at TEXT,
                    last_scraped_at TEXT,
                    scrape_status TEXT NOT NULL DEFAULT 'pending'
                );

                CREATE TABLE IF NOT EXISTS boxscores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    season_short TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    phase TEXT,
                    jornada INTEGER,
                    team_name TEXT NOT NULL,
                    opponent_name TEXT NOT NULL,
                    result_label TEXT,
                    team_points INTEGER,
                    opponent_points INTEGER,
                    is_starter INTEGER NOT NULL DEFAULT 0,
                    jersey TEXT,
                    player_name TEXT NOT NULL,
                    player_key TEXT NOT NULL,
                    image_url TEXT,
                    player_url TEXT,
                    minutes_played REAL,
                    points INTEGER,
                    t2_made INTEGER,
                    t2_att INTEGER,
                    t3_made INTEGER,
                    t3_att INTEGER,
                    ft_made INTEGER,
                    ft_att INTEGER,
                    oreb INTEGER,
                    dreb INTEGER,
                    assists INTEGER,
                    steals INTEGER,
                    turnovers INTEGER,
                    fouls_committed INTEGER,
                    fouls_received INTEGER,
                    blocks INTEGER,
                    source_scope TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE (game_id, team_name, player_key),
                    FOREIGN KEY (game_id) REFERENCES games_catalog(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS assists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    season_short TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    phase TEXT,
                    jornada INTEGER,
                    team_name TEXT NOT NULL,
                    passer TEXT NOT NULL,
                    scorer TEXT NOT NULL,
                    n_assists INTEGER NOT NULL,
                    source_scope TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE (game_id, team_name, passer, scorer),
                    FOREIGN KEY (game_id) REFERENCES games_catalog(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS clutch_player (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    season_short TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    phase TEXT,
                    jornada INTEGER,
                    team_name TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    player_key TEXT NOT NULL,
                    minutes_clutch REAL,
                    seconds_clutch REAL,
                    pts INTEGER,
                    fga REAL,
                    fgm REAL,
                    tpa REAL,
                    tpm REAL,
                    fta REAL,
                    ftm REAL,
                    efg_pct REAL,
                    ts_pct REAL,
                    ast INTEGER,
                    turnovers INTEGER,
                    stl INTEGER,
                    reb INTEGER,
                    reb_o INTEGER,
                    reb_d INTEGER,
                    usg_pct REAL,
                    plus_minus REAL,
                    net_rtg REAL,
                    source_scope TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE (game_id, team_name, player_key),
                    FOREIGN KEY (game_id) REFERENCES games_catalog(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS clutch_lineups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    season_short TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    phase TEXT,
                    jornada INTEGER,
                    team_name TEXT NOT NULL,
                    lineup TEXT NOT NULL,
                    n_jug INTEGER,
                    sec_clutch REAL,
                    min_clutch REAL,
                    points_for REAL,
                    points_against REAL,
                    off_possessions REAL,
                    def_possessions REAL,
                    off_rtg REAL,
                    def_rtg REAL,
                    net_rtg REAL,
                    fga_on REAL,
                    fta_on REAL,
                    to_on REAL,
                    orb_on REAL,
                    opp_fga_on REAL,
                    opp_fta_on REAL,
                    opp_to_on REAL,
                    opp_orb_on REAL,
                    raw_partido_id TEXT,
                    source_scope TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE (game_id, team_name, lineup),
                    FOREIGN KEY (game_id) REFERENCES games_catalog(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS player_bios (
                    player_key TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    birth_date TEXT,
                    nationality TEXT,
                    image_url TEXT,
                    player_url TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS imported_scopes (
                    scope_name TEXT PRIMARY KEY,
                    season_short TEXT NOT NULL,
                    league_code TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );
                """
            )

    def has_data(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM games_catalog").fetchone()
        return bool(row["total"])

    def _log(self, progress_callback: ProgressCallback, level: str, message: str) -> None:
        if progress_callback:
            progress_callback(level, message)

    def _runtime_game_preview(self, row: dict) -> dict[str, object]:
        game_label = row.get("game_label")
        if not game_label:
            local_team = str(row.get("local_team") or "").strip()
            away_team = str(row.get("away_team") or "").strip()
            game_label = f"{local_team} vs {away_team}" if local_team and away_team else local_team or away_team
        return {
            "pid": str(row.get("pid") or ""),
            "phase": row.get("phase"),
            "jornada": _safe_int(row.get("jornada")),
            "game_label": game_label,
            "local_team": row.get("local_team"),
            "away_team": row.get("away_team"),
        }

    def reconcile_scrape_statuses(
        self,
        *,
        season: Optional[SeasonText] = None,
        league: Optional[LeagueName] = None,
        progress_callback: ProgressCallback = None,
    ) -> dict[str, int]:
        filters: list[str] = []
        params: list[object] = []
        if season:
            filters.append("season_short = ?")
            params.append(_season_short(season))
        if league:
            filters.append("league_name = ?")
            params.append(league)

        where_sql = ""
        if filters:
            where_sql = " AND " + " AND ".join(filters)

        with self.connect() as conn:
            recovered = conn.execute(
                f"""
                UPDATE games_catalog
                SET scrape_status = CASE WHEN pid IS NULL THEN 'imported' ELSE 'success' END
                WHERE scrape_status NOT IN ('success', 'imported')
                  AND EXISTS (SELECT 1 FROM boxscores bs WHERE bs.game_id = games_catalog.id)
                  {where_sql}
                """,
                params,
            ).rowcount
            reset_pending = conn.execute(
                f"""
                UPDATE games_catalog
                SET scrape_status = 'pending'
                WHERE scrape_status IN ('success', 'imported')
                  AND NOT EXISTS (SELECT 1 FROM boxscores bs WHERE bs.game_id = games_catalog.id)
                  {where_sql}
                """,
                params,
            ).rowcount

        if recovered or reset_pending:
            self._log(
                progress_callback,
                "info",
                f"Estados reconciliados: recuperados={recovered} incompletos_a_pending={reset_pending}",
            )
        return {"recovered": int(recovered or 0), "reset_pending": int(reset_pending or 0)}

    def repair_duplicate_games(
        self,
        *,
        season: Optional[SeasonText] = None,
        league: Optional[LeagueName] = None,
        progress_callback: ProgressCallback = None,
    ) -> dict[str, int]:
        filters: list[str] = []
        params: list[object] = []
        if season:
            filters.append("canonical.season_short = ?")
            params.append(_season_short(season))
        if league:
            filters.append("canonical.league_name = ?")
            params.append(league)

        where_sql = ""
        if filters:
            where_sql = " AND " + " AND ".join(filters)

        query = f"""
            SELECT
                canonical.id AS canonical_id,
                canonical.pid AS canonical_pid,
                canonical.season_short,
                canonical.league_name,
                canonical.phase,
                canonical.jornada,
                canonical.local_team AS canonical_local_team,
                canonical.away_team AS canonical_away_team,
                duplicate.id AS duplicate_id,
                duplicate.local_team AS duplicate_local_team,
                duplicate.away_team AS duplicate_away_team
            FROM games_catalog canonical
            JOIN games_catalog duplicate
              ON duplicate.season_short = canonical.season_short
             AND duplicate.league_name = canonical.league_name
             AND duplicate.phase = canonical.phase
             AND duplicate.jornada = canonical.jornada
            WHERE canonical.pid IS NOT NULL
              AND duplicate.pid IS NULL
              AND NOT EXISTS (SELECT 1 FROM boxscores bs WHERE bs.game_id = canonical.id)
              AND EXISTS (SELECT 1 FROM boxscores bs WHERE bs.game_id = duplicate.id)
              AND (
                    duplicate.local_team IN (canonical.local_team, canonical.away_team)
                 OR duplicate.away_team IN (canonical.local_team, canonical.away_team)
              )
              {where_sql}
            ORDER BY canonical.league_name, canonical.phase, canonical.jornada, canonical.id, duplicate.id
        """

        with self.connect() as conn:
            candidate_rows = [dict(row) for row in conn.execute(query, params).fetchall()]

        candidates_by_canonical: dict[int, list[dict[str, object]]] = {}
        for row in candidate_rows:
            candidates_by_canonical.setdefault(int(row["canonical_id"]), []).append(row)

        repaired = 0
        skipped = 0
        deleted = 0

        with self.connect() as conn:
            for canonical_id, candidates in candidates_by_canonical.items():
                if len(candidates) != 1:
                    skipped += 1
                    continue

                candidate = candidates[0]
                duplicate_id = int(candidate["duplicate_id"])
                canonical_local = _normalize_spaces(str(candidate["canonical_local_team"] or ""))
                canonical_away = _normalize_spaces(str(candidate["canonical_away_team"] or ""))
                duplicate_local = _normalize_spaces(str(candidate["duplicate_local_team"] or ""))
                duplicate_away = _normalize_spaces(str(candidate["duplicate_away_team"] or ""))

                team_map: dict[str, str] = {}
                used_targets: set[str] = set()
                for source_name in (duplicate_local, duplicate_away):
                    if source_name == canonical_local:
                        team_map[source_name] = canonical_local
                        used_targets.add(canonical_local)
                    elif source_name == canonical_away:
                        team_map[source_name] = canonical_away
                        used_targets.add(canonical_away)

                remaining_targets = [name for name in (canonical_local, canonical_away) if name not in used_targets]
                for source_name in (duplicate_local, duplicate_away):
                    if source_name and source_name not in team_map and remaining_targets:
                        team_map[source_name] = remaining_targets.pop(0)

                if duplicate_local not in team_map or duplicate_away not in team_map:
                    skipped += 1
                    continue

                for source_name, target_name in team_map.items():
                    conn.execute(
                        """
                        UPDATE boxscores
                        SET game_id = ?,
                            team_name = CASE WHEN team_name = ? THEN ? ELSE team_name END,
                            opponent_name = CASE WHEN opponent_name = ? THEN ? ELSE opponent_name END,
                            source_scope = COALESCE(source_scope, ?),
                            updated_at = ?
                        WHERE game_id = ?
                        """,
                        [
                            canonical_id,
                            source_name,
                            target_name,
                            source_name,
                            target_name,
                            f"repair::{candidate['season_short']}::{_league_code(str(candidate['league_name']))}",
                            _now_utc(),
                            duplicate_id,
                        ],
                    )
                    conn.execute(
                        """
                        UPDATE assists
                        SET game_id = ?,
                            team_name = CASE WHEN team_name = ? THEN ? ELSE team_name END,
                            source_scope = COALESCE(source_scope, ?),
                            updated_at = ?
                        WHERE game_id = ?
                        """,
                        [
                            canonical_id,
                            source_name,
                            target_name,
                            f"repair::{candidate['season_short']}::{_league_code(str(candidate['league_name']))}",
                            _now_utc(),
                            duplicate_id,
                        ],
                    )
                    conn.execute(
                        """
                        UPDATE clutch_player
                        SET game_id = ?,
                            team_name = CASE WHEN team_name = ? THEN ? ELSE team_name END,
                            source_scope = COALESCE(source_scope, ?),
                            updated_at = ?
                        WHERE game_id = ?
                        """,
                        [
                            canonical_id,
                            source_name,
                            target_name,
                            f"repair::{candidate['season_short']}::{_league_code(str(candidate['league_name']))}",
                            _now_utc(),
                            duplicate_id,
                        ],
                    )
                    conn.execute(
                        """
                        UPDATE clutch_lineups
                        SET game_id = ?,
                            team_name = CASE WHEN team_name = ? THEN ? ELSE team_name END,
                            source_scope = COALESCE(source_scope, ?),
                            updated_at = ?
                        WHERE game_id = ?
                        """,
                        [
                            canonical_id,
                            source_name,
                            target_name,
                            f"repair::{candidate['season_short']}::{_league_code(str(candidate['league_name']))}",
                            _now_utc(),
                            duplicate_id,
                        ],
                    )

                duplicate_score = conn.execute(
                    "SELECT score_local, score_away, score_text, last_scraped_at FROM games_catalog WHERE id = ?",
                    [duplicate_id],
                ).fetchone()
                conn.execute(
                    """
                    UPDATE games_catalog
                    SET score_local = COALESCE(score_local, ?),
                        score_away = COALESCE(score_away, ?),
                        score_text = COALESCE(score_text, ?),
                        scrape_status = 'success',
                        last_scraped_at = COALESCE(last_scraped_at, ?),
                        source_scope = COALESCE(source_scope, ?)
                    WHERE id = ?
                    """,
                    [
                        duplicate_score["score_local"] if duplicate_score else None,
                        duplicate_score["score_away"] if duplicate_score else None,
                        duplicate_score["score_text"] if duplicate_score else None,
                        duplicate_score["last_scraped_at"] if duplicate_score else _now_utc(),
                        f"repair::{candidate['season_short']}::{_league_code(str(candidate['league_name']))}",
                        canonical_id,
                    ],
                )

                remaining_refs = 0
                for table_name in ("boxscores", "assists", "clutch_player", "clutch_lineups"):
                    remaining_refs += int(conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE game_id = ?", [duplicate_id]).fetchone()[0] or 0)
                if remaining_refs == 0:
                    conn.execute("DELETE FROM games_catalog WHERE id = ?", [duplicate_id])
                    deleted += 1

                repaired += 1

        if repaired or skipped:
            self._log(
                progress_callback,
                "info",
                f"Reparacion de duplicados: reparados={repaired} omitidos={skipped} eliminados={deleted}",
            )
        return {"repaired": repaired, "skipped": skipped, "deleted": deleted}

    def get_available_seasons(self) -> list[str]:
        with self.connect() as conn:
            df = pd.read_sql_query(
                "SELECT DISTINCT season_short FROM games_catalog ORDER BY season_short DESC",
                conn,
            )
        return df["season_short"].tolist()

    def get_available_leagues(self, season: Optional[str] = None) -> list[str]:
        sql = "SELECT DISTINCT league_name FROM games_catalog"
        params: list[object] = []
        if season:
            sql += " WHERE season_short = ?"
            params.append(_season_short(season))
        sql += " ORDER BY league_name"
        with self.connect() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        return df["league_name"].tolist()

    def get_available_phases(self, season: str, league: str) -> list[str]:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT DISTINCT phase
                FROM games_catalog
                WHERE season_short = ? AND league_name = ?
                ORDER BY phase
                """,
                conn,
                params=[_season_short(season), league],
            )
        return df["phase"].tolist()

    def get_available_jornadas(self, season: str, league: str, phases: Sequence[str] = ()) -> list[int]:
        sql = """
            SELECT DISTINCT jornada
            FROM games_catalog
            WHERE season_short = ? AND league_name = ?
        """
        params: list[object] = [_season_short(season), league]
        if phases:
            placeholders = ",".join(["?"] * len(phases))
            sql += f" AND phase IN ({placeholders})"
            params.extend(list(phases))
        sql += " ORDER BY jornada"
        with self.connect() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        return [int(value) for value in df["jornada"].tolist()]

    def import_historical(self, progress_callback: ProgressCallback = None) -> dict[str, int]:
        self._log(progress_callback, "info", "Importando historico Excel a SQLite...")
        boxscore_files = get_available_files_by_type("boxscores")
        imported_scopes = 0
        for relative_path in boxscore_files:
            boxscores_path = _lookup_path(relative_path)
            info = parse_filename_info(relative_path)
            season_short = info["temporada"]
            league_code = info["liga"]
            if not season_short or not league_code or not boxscores_path.exists():
                continue
            scope_name = relative_path.replace("\\", "/")
            related_files = self._find_related_scope_files(boxscores_path, season_short, league_code)
            self._import_scope(
                scope_name=scope_name,
                season_short=season_short,
                league_code=league_code,
                boxscores_path=boxscores_path,
                assists_path=related_files.get("assists"),
                clutch_path=related_files.get("clutch_data"),
                lineups_path=related_files.get("clutch_lineups"),
                players_path=related_files.get("players"),
                progress_callback=progress_callback,
            )
            imported_scopes += 1
        self.refresh_aggregates(progress_callback=progress_callback)
        return {"scopes": imported_scopes}

    def _find_related_scope_files(self, boxscores_path: Path, season_short: str, league_code: str) -> dict[str, Optional[Path]]:
        folder = boxscores_path.parent
        return {
            "assists": candidate if (candidate := folder / f"assists_{season_short}_{league_code}.xlsx").exists() else None,
            "clutch_data": candidate if (candidate := folder / f"clutch_data_{season_short}_{league_code}.xlsx").exists() else None,
            "clutch_lineups": candidate if (candidate := folder / f"clutch_lineups_{season_short}_{league_code}.xlsx").exists() else None,
            "players": candidate if (candidate := folder / f"players_{season_short}_{league_code}.xlsx").exists() else None,
        }

    def _import_scope(
        self,
        *,
        scope_name: str,
        season_short: str,
        league_code: str,
        boxscores_path: Path,
        assists_path: Optional[Path],
        clutch_path: Optional[Path],
        lineups_path: Optional[Path],
        players_path: Optional[Path],
        progress_callback: ProgressCallback,
    ) -> None:
        season_full = _season_full(season_short)
        league_name = _league_name(league_code)
        self._log(progress_callback, "info", f"Importando {scope_name}")

        df_boxscores = pd.read_excel(boxscores_path) if boxscores_path.exists() else pd.DataFrame()
        df_assists = pd.read_excel(assists_path) if assists_path else pd.DataFrame()
        df_clutch = pd.read_excel(clutch_path) if clutch_path else pd.DataFrame()
        df_lineups = pd.read_excel(lineups_path) if lineups_path else pd.DataFrame()
        df_players = pd.read_excel(players_path) if players_path else pd.DataFrame()

        lookup: dict[tuple[str, int, str], int] = {}
        with self.connect() as conn:
            self._register_imported_scope(conn, scope_name, season_short, league_code, str(boxscores_path))
            lookup.update(self._build_game_lookup_from_lineups(conn, df_lineups, season_short, season_full, league_code, league_name, scope_name))
            lookup.update(self._build_game_lookup_from_game_labels(conn, df_assists, season_short, season_full, league_code, league_name, scope_name))
            lookup.update(self._build_game_lookup_from_game_labels(conn, df_clutch, season_short, season_full, league_code, league_name, scope_name))
            self._import_boxscores(conn, df_boxscores, season_short, season_full, league_code, league_name, scope_name, lookup)
            self._import_assists(conn, df_assists, season_short, league_code, scope_name, lookup)
            self._import_clutch_player(conn, df_clutch, season_short, league_code, scope_name, lookup)
            self._import_clutch_lineups(conn, df_lineups, season_short, league_code, scope_name, lookup)
            self._import_player_bios(conn, df_players)

    def _register_imported_scope(self, conn: sqlite3.Connection, scope_name: str, season_short: str, league_code: str, source_path: str) -> None:
        conn.execute(
            """
            INSERT INTO imported_scopes(scope_name, season_short, league_code, source_path, imported_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope_name) DO UPDATE SET
                season_short = excluded.season_short,
                league_code = excluded.league_code,
                source_path = excluded.source_path,
                imported_at = excluded.imported_at
            """,
            [scope_name, season_short, league_code, source_path, _now_utc()],
        )

    def _build_game_lookup_from_lineups(
        self,
        conn: sqlite3.Connection,
        df_lineups: pd.DataFrame,
        season_short: str,
        season_full: str,
        league_code: str,
        league_name: str,
        scope_name: str,
    ) -> dict[tuple[str, int, str], int]:
        lookup: dict[tuple[str, int, str], int] = {}
        if df_lineups.empty or "PARTIDO_ID" not in df_lineups.columns:
            return lookup
        unique_rows = df_lineups[["PARTIDO_ID", "FASE", "JORNADA", "GAME"]].drop_duplicates()
        for row in unique_rows.itertuples(index=False):
            local_team, away_team = _parse_game_label(getattr(row, "GAME", ""))
            if not local_team or not away_team:
                continue
            game_id = self._upsert_game(
                conn,
                pid=str(getattr(row, "PARTIDO_ID")),
                season_short=season_short,
                season_full=season_full,
                league_code=league_code,
                league_name=league_name,
                phase=getattr(row, "FASE"),
                jornada=_safe_int(getattr(row, "JORNADA")),
                local_team=local_team,
                away_team=away_team,
                score_local=None,
                score_away=None,
                game_label=getattr(row, "GAME"),
                played=True,
                source_scope=scope_name,
                scrape_status="imported",
                set_last_scraped=True,
            )
            lookup[(getattr(row, "FASE"), _safe_int(getattr(row, "JORNADA")), _pair_key(local_team, away_team))] = game_id
        return lookup

    def _build_game_lookup_from_game_labels(
        self,
        conn: sqlite3.Connection,
        df_source: pd.DataFrame,
        season_short: str,
        season_full: str,
        league_code: str,
        league_name: str,
        scope_name: str,
    ) -> dict[tuple[str, int, str], int]:
        lookup: dict[tuple[str, int, str], int] = {}
        if df_source.empty or "GAME" not in df_source.columns:
            return lookup
        unique_rows = df_source[["FASE", "JORNADA", "GAME"]].drop_duplicates()
        for row in unique_rows.itertuples(index=False):
            local_team, away_team = _parse_game_label(getattr(row, "GAME", ""))
            if not local_team or not away_team:
                continue
            game_id = self._upsert_game(
                conn,
                pid=None,
                season_short=season_short,
                season_full=season_full,
                league_code=league_code,
                league_name=league_name,
                phase=getattr(row, "FASE"),
                jornada=_safe_int(getattr(row, "JORNADA")),
                local_team=local_team,
                away_team=away_team,
                score_local=None,
                score_away=None,
                game_label=getattr(row, "GAME"),
                played=True,
                source_scope=scope_name,
                scrape_status="imported",
                set_last_scraped=True,
            )
            lookup[(getattr(row, "FASE"), _safe_int(getattr(row, "JORNADA")), _pair_key(local_team, away_team))] = game_id
        return lookup

    def _upsert_game(
        self,
        conn: sqlite3.Connection,
        *,
        pid: Optional[str],
        season_short: str,
        season_full: str,
        league_code: str,
        league_name: str,
        phase: str,
        jornada: int,
        local_team: Optional[str],
        away_team: Optional[str],
        score_local: Optional[int],
        score_away: Optional[int],
        game_label: Optional[str],
        played: bool,
        source_scope: str,
        scrape_status: str,
        set_last_scraped: bool,
        preserve_existing_scrape_status: bool = False,
    ) -> int:
        local_fallback = local_team or ""
        away_fallback = away_team or ""
        key = _scope_key(season_short, league_code, phase, jornada, local_fallback, away_fallback)
        existing = None
        if pid:
            existing = conn.execute(
                "SELECT id, scrape_status FROM games_catalog WHERE pid = ? OR scope_key = ?",
                [pid, key],
            ).fetchone()
        if existing is None:
            existing = conn.execute("SELECT id, scrape_status FROM games_catalog WHERE scope_key = ?", [key]).fetchone()

        now = _now_utc()
        score_text = None
        if score_local is not None and score_away is not None:
            score_text = f"{score_local}-{score_away}"

        if existing is None:
            conn.execute(
                """
                INSERT INTO games_catalog(
                    pid, scope_key, season_short, season_full, league_code, league_name, phase,
                    jornada, local_team, away_team, score_local, score_away, score_text,
                    game_label, played, source_scope, last_seen_at, last_scraped_at, scrape_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    pid,
                    key,
                    season_short,
                    season_full,
                    league_code,
                    league_name,
                    phase,
                    jornada,
                    local_team,
                    away_team,
                    score_local,
                    score_away,
                    score_text,
                    game_label,
                    1 if played else 0,
                    source_scope,
                    now,
                    now if set_last_scraped else None,
                    scrape_status,
                ],
            )
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        conn.execute(
            """
            UPDATE games_catalog
            SET
                pid = COALESCE(?, pid),
                season_short = ?,
                season_full = ?,
                league_code = ?,
                league_name = ?,
                phase = ?,
                jornada = ?,
                local_team = COALESCE(?, local_team),
                away_team = COALESCE(?, away_team),
                score_local = COALESCE(?, score_local),
                score_away = COALESCE(?, score_away),
                score_text = COALESCE(?, score_text),
                game_label = COALESCE(?, game_label),
                played = ?,
                source_scope = COALESCE(?, source_scope),
                last_seen_at = ?,
                last_scraped_at = COALESCE(?, last_scraped_at),
                scrape_status = ?
            WHERE id = ?
            """,
            [
                pid,
                season_short,
                season_full,
                league_code,
                league_name,
                phase,
                jornada,
                local_team,
                away_team,
                score_local,
                score_away,
                score_text,
                game_label,
                1 if played else 0,
                source_scope,
                now,
                now if set_last_scraped else None,
                existing["scrape_status"] if preserve_existing_scrape_status else scrape_status,
                existing["id"],
            ],
        )
        return int(existing["id"])

    def _extract_game_score(self, frame: pd.DataFrame, local_team: Optional[str], away_team: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        if frame.empty:
            return None, None
        team_scores = (
            frame.groupby("EQUIPO LOCAL")[["PTS_EQUIPO", "PTS_RIVAL"]]
            .first()
            .reset_index()
            .set_index("EQUIPO LOCAL")
        )
        if local_team and local_team in team_scores.index:
            return _safe_int(team_scores.loc[local_team, "PTS_EQUIPO"]), _safe_int(team_scores.loc[local_team, "PTS_RIVAL"])
        if away_team and away_team in team_scores.index:
            return _safe_int(team_scores.loc[away_team, "PTS_RIVAL"]), _safe_int(team_scores.loc[away_team, "PTS_EQUIPO"])
        first_row = frame.iloc[0]
        return _safe_int(first_row.get("PTS_EQUIPO")), _safe_int(first_row.get("PTS_RIVAL"))

    def _upsert_basic_bio(
        self,
        conn: sqlite3.Connection,
        *,
        player_key: str,
        player_name: str,
        image_url: Optional[str],
        player_url: Optional[str],
    ) -> None:
        conn.execute(
            """
            INSERT INTO player_bios(player_key, player_name, birth_date, nationality, image_url, player_url, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?, ?)
            ON CONFLICT(player_key) DO UPDATE SET
                player_name = excluded.player_name,
                image_url = COALESCE(excluded.image_url, player_bios.image_url),
                player_url = COALESCE(excluded.player_url, player_bios.player_url),
                updated_at = excluded.updated_at
            """,
            [player_key, player_name, image_url, player_url, _now_utc()],
        )

    def _import_boxscores(
        self,
        conn: sqlite3.Connection,
        df_boxscores: pd.DataFrame,
        season_short: str,
        season_full: str,
        league_code: str,
        league_name: str,
        scope_name: str,
        lookup: dict[tuple[str, int, str], int],
    ) -> None:
        if df_boxscores.empty:
            return
        source = df_boxscores.copy()
        source["__pair_key"] = source.apply(
            lambda row: _pair_key(str(row.get("EQUIPO LOCAL", "")), str(row.get("EQUIPO RIVAL", ""))),
            axis=1,
        )
        grouped = source.groupby(["FASE", "JORNADA", "__pair_key"], sort=False)
        for (phase, jornada, pair_key), frame in grouped:
            frame_pid = None
            if "IdPartido" in frame.columns:
                pid_series = frame["IdPartido"].dropna().astype(str).str.strip()
                if not pid_series.empty:
                    frame_pid = pid_series.iloc[0]
            teams = sorted(
                {
                    _normalize_spaces(str(value))
                    for value in pd.concat([frame["EQUIPO LOCAL"], frame["EQUIPO RIVAL"]]).dropna().tolist()
                    if _normalize_spaces(str(value))
                }
            )
            local_team = None
            away_team = None
            existing_game_id = None
            if frame_pid:
                pid_row = conn.execute(
                    """
                    SELECT id, local_team, away_team
                    FROM games_catalog
                    WHERE pid = ? AND season_short = ? AND league_name = ?
                    LIMIT 1
                    """,
                    [frame_pid, season_short, league_name],
                ).fetchone()
                if pid_row is not None:
                    existing_game_id = int(pid_row["id"])
                    local_team = pid_row["local_team"]
                    away_team = pid_row["away_team"]
            if existing_game_id is None:
                existing_game_id = lookup.get((phase, _safe_int(jornada), pair_key))
            if existing_game_id is not None:
                row = conn.execute("SELECT local_team, away_team FROM games_catalog WHERE id = ?", [existing_game_id]).fetchone()
                if row is not None:
                    local_team = row["local_team"]
                    away_team = row["away_team"]
            if not local_team or not away_team:
                if len(teams) >= 2:
                    local_team, away_team = teams[0], teams[1]
            score_local, score_away = self._extract_game_score(frame, local_team, away_team)
            game_id = self._upsert_game(
                conn,
                pid=frame_pid,
                season_short=season_short,
                season_full=season_full,
                league_code=league_code,
                league_name=league_name,
                phase=phase,
                jornada=_safe_int(jornada),
                local_team=local_team,
                away_team=away_team,
                score_local=score_local,
                score_away=score_away,
                game_label=f"{local_team} vs {away_team}" if local_team and away_team else None,
                played=True,
                source_scope=scope_name,
                scrape_status="imported",
                set_last_scraped=True,
            )
            lookup[(phase, _safe_int(jornada), pair_key)] = game_id

            for row in frame.to_dict(orient="records"):
                player_url = _value_or_none(row.get("URL JUGADOR"))
                player_name = _normalize_spaces(str(row.get("JUGADOR", "")))
                team_name = _normalize_spaces(str(row.get("EQUIPO LOCAL", "")))
                player_key = _player_key(player_name, player_url, team_name)
                conn.execute(
                    """
                    INSERT INTO boxscores(
                        game_id, season_short, league_code, phase, jornada, team_name, opponent_name,
                        result_label, team_points, opponent_points, is_starter, jersey, player_name,
                        player_key, image_url, player_url, minutes_played, points, t2_made, t2_att,
                        t3_made, t3_att, ft_made, ft_att, oreb, dreb, assists, steals, turnovers,
                        fouls_committed, fouls_received, blocks, source_scope, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id, team_name, player_key) DO UPDATE SET
                        result_label = excluded.result_label,
                        team_points = excluded.team_points,
                        opponent_points = excluded.opponent_points,
                        is_starter = excluded.is_starter,
                        jersey = excluded.jersey,
                        image_url = excluded.image_url,
                        player_url = excluded.player_url,
                        minutes_played = excluded.minutes_played,
                        points = excluded.points,
                        t2_made = excluded.t2_made,
                        t2_att = excluded.t2_att,
                        t3_made = excluded.t3_made,
                        t3_att = excluded.t3_att,
                        ft_made = excluded.ft_made,
                        ft_att = excluded.ft_att,
                        oreb = excluded.oreb,
                        dreb = excluded.dreb,
                        assists = excluded.assists,
                        steals = excluded.steals,
                        turnovers = excluded.turnovers,
                        fouls_committed = excluded.fouls_committed,
                        fouls_received = excluded.fouls_received,
                        blocks = excluded.blocks,
                        source_scope = excluded.source_scope,
                        updated_at = excluded.updated_at
                    """,
                    [
                        game_id,
                        season_short,
                        league_code,
                        _value_or_none(row.get("FASE")),
                        _safe_int(row.get("JORNADA")),
                        team_name,
                        _normalize_spaces(str(row.get("EQUIPO RIVAL", ""))),
                        _value_or_none(row.get("RESULTADO")),
                        _safe_int(row.get("PTS_EQUIPO")),
                        _safe_int(row.get("PTS_RIVAL")),
                        1 if bool(row.get("TITULAR")) else 0,
                        str(row.get("DORSAL", "")) if pd.notna(row.get("DORSAL")) else None,
                        player_name,
                        player_key,
                        _value_or_none(row.get("IMAGEN")),
                        player_url,
                        _safe_float(row.get("MINUTOS JUGADOS")),
                        _safe_int(row.get("PUNTOS")),
                        _safe_int(row.get("T2 CONVERTIDO")),
                        _safe_int(row.get("T2 INTENTADO")),
                        _safe_int(row.get("T3 CONVERTIDO")),
                        _safe_int(row.get("T3 INTENTADO")),
                        _safe_int(row.get("TL CONVERTIDOS")),
                        _safe_int(row.get("TL INTENTADOS")),
                        _safe_int(row.get("REB OFFENSIVO")),
                        _safe_int(row.get("REB DEFENSIVO")),
                        _safe_int(row.get("ASISTENCIAS")),
                        _safe_int(row.get("RECUPEROS")),
                        _safe_int(row.get("PERDIDAS")),
                        _safe_int(row.get("FaltasCOMETIDAS")),
                        _safe_int(row.get("FaltasRECIBIDAS")),
                        _safe_int(row.get("TAPONES")),
                        scope_name,
                        _now_utc(),
                    ],
                )
                self._upsert_basic_bio(
                    conn,
                    player_key=player_key,
                    player_name=player_name,
                    image_url=_value_or_none(row.get("IMAGEN")),
                    player_url=player_url,
                )

    def _import_assists(
        self,
        conn: sqlite3.Connection,
        df_assists: pd.DataFrame,
        season_short: str,
        league_code: str,
        scope_name: str,
        lookup: dict[tuple[str, int, str], int],
    ) -> None:
        if df_assists.empty:
            return
        for row in df_assists.to_dict(orient="records"):
            local_team, away_team = _parse_game_label(str(row.get("GAME", "")))
            if not local_team or not away_team:
                continue
            pair_key = _pair_key(local_team, away_team)
            game_id = lookup.get((row.get("FASE"), _safe_int(row.get("JORNADA")), pair_key))
            if game_id is None:
                continue
            conn.execute(
                """
                INSERT INTO assists(
                    game_id, season_short, league_code, phase, jornada, team_name, passer,
                    scorer, n_assists, source_scope, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, team_name, passer, scorer) DO UPDATE SET
                    n_assists = excluded.n_assists,
                    source_scope = excluded.source_scope,
                    updated_at = excluded.updated_at
                """,
                [
                    game_id,
                    season_short,
                    league_code,
                    _value_or_none(row.get("FASE")),
                    _safe_int(row.get("JORNADA")),
                    _normalize_spaces(str(row.get("EQUIPO", ""))),
                    _normalize_spaces(str(row.get("PASADOR", ""))),
                    _normalize_spaces(str(row.get("ANOTADOR", ""))),
                    _safe_int(row.get("N_ASISTENCIAS")),
                    scope_name,
                    _now_utc(),
                ],
            )

    def _import_clutch_player(
        self,
        conn: sqlite3.Connection,
        df_clutch: pd.DataFrame,
        season_short: str,
        league_code: str,
        scope_name: str,
        lookup: dict[tuple[str, int, str], int],
    ) -> None:
        if df_clutch.empty:
            return
        for row in df_clutch.to_dict(orient="records"):
            local_team, away_team = _parse_game_label(str(row.get("GAME", "")))
            if not local_team or not away_team:
                continue
            pair_key = _pair_key(local_team, away_team)
            game_id = lookup.get((row.get("FASE"), _safe_int(row.get("JORNADA")), pair_key))
            if game_id is None:
                continue
            player_name = _normalize_spaces(str(row.get("JUGADOR", "")))
            team_name = _normalize_spaces(str(row.get("EQUIPO", "")))
            conn.execute(
                """
                INSERT INTO clutch_player(
                    game_id, season_short, league_code, phase, jornada, team_name, player_name, player_key,
                    minutes_clutch, seconds_clutch, pts, fga, fgm, tpa, tpm, fta, ftm, efg_pct, ts_pct,
                    ast, turnovers, stl, reb, reb_o, reb_d, usg_pct, plus_minus, net_rtg, source_scope, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, team_name, player_key) DO UPDATE SET
                    minutes_clutch = excluded.minutes_clutch,
                    seconds_clutch = excluded.seconds_clutch,
                    pts = excluded.pts,
                    fga = excluded.fga,
                    fgm = excluded.fgm,
                    tpa = excluded.tpa,
                    tpm = excluded.tpm,
                    fta = excluded.fta,
                    ftm = excluded.ftm,
                    efg_pct = excluded.efg_pct,
                    ts_pct = excluded.ts_pct,
                    ast = excluded.ast,
                    turnovers = excluded.turnovers,
                    stl = excluded.stl,
                    reb = excluded.reb,
                    reb_o = excluded.reb_o,
                    reb_d = excluded.reb_d,
                    usg_pct = excluded.usg_pct,
                    plus_minus = excluded.plus_minus,
                    net_rtg = excluded.net_rtg,
                    source_scope = excluded.source_scope,
                    updated_at = excluded.updated_at
                """,
                [
                    game_id,
                    season_short,
                    league_code,
                    _value_or_none(row.get("FASE")),
                    _safe_int(row.get("JORNADA")),
                    team_name,
                    player_name,
                    _player_key(player_name, None, team_name),
                    _safe_float(row.get("MINUTOS_CLUTCH")),
                    _safe_float(row.get("SEGUNDOS_CLUTCH")),
                    _safe_int(row.get("PTS")),
                    _safe_float(row.get("FGA")),
                    _safe_float(row.get("FGM")),
                    _safe_float(row.get("3PA")),
                    _safe_float(row.get("3PM")),
                    _safe_float(row.get("FTA")),
                    _safe_float(row.get("FTM")),
                    _safe_float(row.get("eFG%")),
                    _safe_float(row.get("TS%")),
                    _safe_int(row.get("AST")),
                    _safe_int(row.get("TO")),
                    _safe_int(row.get("STL")),
                    _safe_int(row.get("REB")),
                    _safe_int(row.get("REB_O")),
                    _safe_int(row.get("REB_D")),
                    _safe_float(row.get("USG%")),
                    _safe_float(row.get("PLUS_MINUS")),
                    _safe_float(row.get("NET_RTG")),
                    scope_name,
                    _now_utc(),
                ],
            )

    def _import_clutch_lineups(
        self,
        conn: sqlite3.Connection,
        df_lineups: pd.DataFrame,
        season_short: str,
        league_code: str,
        scope_name: str,
        lookup: dict[tuple[str, int, str], int],
    ) -> None:
        if df_lineups.empty:
            return
        for row in df_lineups.to_dict(orient="records"):
            local_team, away_team = _parse_game_label(str(row.get("GAME", "")))
            if not local_team or not away_team:
                continue
            pair_key = _pair_key(local_team, away_team)
            game_id = lookup.get((row.get("FASE"), _safe_int(row.get("JORNADA")), pair_key))
            if game_id is None:
                continue
            conn.execute(
                """
                INSERT INTO clutch_lineups(
                    game_id, season_short, league_code, phase, jornada, team_name, lineup,
                    n_jug, sec_clutch, min_clutch, points_for, points_against, off_possessions,
                    def_possessions, off_rtg, def_rtg, net_rtg, fga_on, fta_on, to_on,
                    orb_on, opp_fga_on, opp_fta_on, opp_to_on, opp_orb_on, raw_partido_id,
                    source_scope, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, team_name, lineup) DO UPDATE SET
                    n_jug = excluded.n_jug,
                    sec_clutch = excluded.sec_clutch,
                    min_clutch = excluded.min_clutch,
                    points_for = excluded.points_for,
                    points_against = excluded.points_against,
                    off_possessions = excluded.off_possessions,
                    def_possessions = excluded.def_possessions,
                    off_rtg = excluded.off_rtg,
                    def_rtg = excluded.def_rtg,
                    net_rtg = excluded.net_rtg,
                    fga_on = excluded.fga_on,
                    fta_on = excluded.fta_on,
                    to_on = excluded.to_on,
                    orb_on = excluded.orb_on,
                    opp_fga_on = excluded.opp_fga_on,
                    opp_fta_on = excluded.opp_fta_on,
                    opp_to_on = excluded.opp_to_on,
                    opp_orb_on = excluded.opp_orb_on,
                    raw_partido_id = excluded.raw_partido_id,
                    source_scope = excluded.source_scope,
                    updated_at = excluded.updated_at
                """,
                [
                    game_id,
                    season_short,
                    league_code,
                    _value_or_none(row.get("FASE")),
                    _safe_int(row.get("JORNADA")),
                    _normalize_spaces(str(row.get("EQUIPO", ""))),
                    _normalize_spaces(str(row.get("LINEUP", ""))),
                    _safe_int(row.get("N_JUG")),
                    _safe_float(row.get("SEC_CLUTCH")),
                    _safe_float(row.get("MIN_CLUTCH")),
                    _safe_float(row.get("POINTS_FOR")),
                    _safe_float(row.get("POINTS_AGAINST")),
                    _safe_float(row.get("OFF_POSSESSIONS")),
                    _safe_float(row.get("DEF_POSSESSIONS")),
                    _safe_float(row.get("OFF_RTG")),
                    _safe_float(row.get("DEF_RTG")),
                    _safe_float(row.get("NET_RTG")),
                    _safe_float(row.get("FGA_on")),
                    _safe_float(row.get("FTA_on")),
                    _safe_float(row.get("TO_on")),
                    _safe_float(row.get("ORB_on")),
                    _safe_float(row.get("OPP_FGA_on")),
                    _safe_float(row.get("OPP_FTA_on")),
                    _safe_float(row.get("OPP_TO_on")),
                    _safe_float(row.get("OPP_ORB_on")),
                    _value_or_none(row.get("PARTIDO_ID")),
                    scope_name,
                    _now_utc(),
                ],
            )

    def _import_player_bios(self, conn: sqlite3.Connection, df_players: pd.DataFrame) -> None:
        if df_players.empty:
            return
        for row in df_players.to_dict(orient="records"):
            player_name = _normalize_spaces(str(row.get("JUGADOR", "")))
            player_url = _value_or_none(row.get("URL JUGADOR"))
            team_name = _value_or_none(row.get("EQUIPO"))
            key = _player_key(player_name, player_url, team_name)
            conn.execute(
                """
                INSERT INTO player_bios(player_key, player_name, birth_date, nationality, image_url, player_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_key) DO UPDATE SET
                    player_name = excluded.player_name,
                    birth_date = COALESCE(excluded.birth_date, player_bios.birth_date),
                    nationality = COALESCE(excluded.nationality, player_bios.nationality),
                    image_url = COALESCE(excluded.image_url, player_bios.image_url),
                    player_url = COALESCE(excluded.player_url, player_bios.player_url),
                    updated_at = excluded.updated_at
                """,
                [
                    key,
                    player_name,
                    _value_or_none(row.get("FECHA NACIMIENTO")),
                    _value_or_none(row.get("NACIONALIDAD")),
                    _value_or_none(row.get("IMAGEN")),
                    player_url,
                    _now_utc(),
                ],
            )

    def discover_games(
        self,
        *,
        season: SeasonText,
        league: LeagueName,
        phases: Sequence[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict]:
        season_full = _season_full(_season_short(season))
        year = int(season_full.split("/")[0])
        league_code = _league_code(league)
        league_name = _league_name(league_code)
        liga_url = get_liga_url(league, year)

        original_temporada = web_scraping.TEMPORADA_TXT
        original_base_url = web_scraping.get_current_base_url()
        original_phases = scraper_all_games.PHASES
        self._log(progress_callback, "info", f"Descubriendo partidos para {league_name} {season_full}...")
        try:
            web_scraping.set_base_url(liga_url)
            web_scraping.TEMPORADA_TXT = season_full
            scraper_all_games.PHASES = list(phases)
            rows = scraper_all_games.scrape_all()
        finally:
            web_scraping.TEMPORADA_TXT = original_temporada
            web_scraping.set_base_url(original_base_url)
            scraper_all_games.PHASES = original_phases

        unique_games: dict[str, tuple] = {}
        for row in rows:
            phase, jornada, pid, _, local, rival, _ = row
            unique_games[str(pid)] = (phase, jornada, str(pid), local, rival)

        discovered: list[dict] = []
        with self.connect() as conn:
            for phase, jornada, pid, local, rival in unique_games.values():
                game_id = self._upsert_game(
                    conn,
                    pid=pid,
                    season_short=_season_short(season_full),
                    season_full=season_full,
                    league_code=league_code,
                    league_name=league_name,
                    phase=phase,
                    jornada=_safe_int(jornada),
                    local_team=local,
                    away_team=rival,
                    score_local=None,
                    score_away=None,
                    game_label=f"{local} vs {rival}",
                    played=True,
                    source_scope=f"discover::{league_code}_{_season_short(season_full)}",
                    scrape_status="pending",
                    set_last_scraped=False,
                    preserve_existing_scrape_status=True,
                )
                discovered.append(
                    {
                        "game_id": game_id,
                        "pid": pid,
                        "phase": phase,
                        "jornada": _safe_int(jornada),
                        "local_team": local,
                        "away_team": rival,
                    }
                )
        self._log(progress_callback, "success", f"Partidos descubiertos: {len(discovered)}")
        return discovered

    def sync_games(
        self,
        *,
        season: SeasonText,
        league: LeagueName,
        phases: Sequence[str],
        jornadas: Sequence[int] = (),
        revalidate_window: int = 2,
        export_compat_files: bool = True,
        scrape_player_bios: bool = True,
        player_bio_limit: Optional[int] = None,
        progress_callback: ProgressCallback = None,
        runtime_tracker: Optional["SyncRuntimeTracker"] = None,
    ) -> SyncSummary:
        summary = SyncSummary()
        if runtime_tracker:
            runtime_tracker.set_step(
                step="repair_duplicates",
                message=f"Reparando duplicados conocidos en la base para {league} {_season_short(season)}",
            )
        self.repair_duplicate_games(season=season, league=league, progress_callback=progress_callback)
        if runtime_tracker:
            runtime_tracker.set_step(
                step="reconcile_status",
                message=f"Revisando estados previos en la base para {league} {_season_short(season)}",
            )
        self.reconcile_scrape_statuses(season=season, league=league, progress_callback=progress_callback)
        if runtime_tracker:
            runtime_tracker.set_step(
                step="discover",
                message=f"Descubriendo partidos para {league} {_season_short(season)}",
            )
        discovered = self.discover_games(season=season, league=league, phases=phases, progress_callback=progress_callback)
        summary.discovered_games = len(discovered)

        discovered_df = pd.DataFrame(discovered)
        if discovered_df.empty:
            return summary
        if jornadas:
            discovered_df = discovered_df[discovered_df["jornada"].isin(list(jornadas))]

        recent_pairs: set[tuple[str, int]] = set()
        for phase, phase_df in discovered_df.groupby("phase"):
            unique_jornadas = sorted(set(int(value) for value in phase_df["jornada"].tolist()))
            for jornada in unique_jornadas[-revalidate_window:]:
                recent_pairs.add((phase, jornada))

        with self.connect() as conn:
            existing = pd.read_sql_query(
                """
                SELECT pid, phase, jornada, scrape_status
                FROM games_catalog
                WHERE season_short = ? AND league_name = ?
                """,
                conn,
                params=[_season_short(season), league],
            )

        merged = discovered_df.merge(existing, on=["pid", "phase", "jornada"], how="left")
        complete_statuses = {"success", "imported"}
        missing_mask = merged["scrape_status"].isna() | (~merged["scrape_status"].isin(complete_statuses))
        refresh_mask = missing_mask & merged.apply(lambda row: (row["phase"], int(row["jornada"])) in recent_pairs, axis=1)
        summary.missing_games = int(missing_mask.sum())
        summary.refreshed_games = int(refresh_mask.sum())
        targets_df = merged[missing_mask].drop_duplicates(subset=["pid"]).reset_index(drop=True)
        target_records = targets_df.to_dict(orient="records")
        recent_pairs_payload = [
            {"phase": phase_name, "jornada": jornada_number}
            for phase_name, jornada_number in sorted(recent_pairs, key=lambda item: (item[0], item[1]))
        ]
        if runtime_tracker:
            runtime_tracker.set_scope_plan(
                target_games=len(target_records),
                next_games=[self._runtime_game_preview(row) for row in target_records[:5]],
                recent_pairs=recent_pairs_payload,
            )
        if targets_df.empty:
            summary.skipped_games = summary.discovered_games
            self._log(progress_callback, "info", "No hay partidos pendientes de sync.")
            return summary

        changed_scopes = {(_season_short(season), league)}
        self._log(progress_callback, "info", f"Scrapeando {len(targets_df)} partidos...")
        total_targets = len(target_records)
        for index, row in enumerate(target_records, start=1):
            pid = str(row["pid"])
            phase = row["phase"]
            jornada = int(row["jornada"])
            local_team = row["local_team"]
            away_team = row["away_team"]
            current_game = self._runtime_game_preview(row)
            next_games = [self._runtime_game_preview(item) for item in target_records[index : index + 5]]
            if runtime_tracker:
                runtime_tracker.set_step(
                    step="scraping_game",
                    message=f"Scrapeando partido {index}/{total_targets}: {current_game['game_label']}",
                    current_game=current_game,
                    next_games=next_games,
                )
            try:
                game_meta = (phase, jornada, pid, 1, local_team, away_team, "")
                boxscores_records, assists_records, clutch_records, lineups_df = scrape_one_game_unified(game_meta)
                with self.connect() as conn:
                    game_id = self._upsert_game(
                        conn,
                        pid=pid,
                        season_short=_season_short(season),
                        season_full=_season_full(_season_short(season)),
                        league_code=_league_code(league),
                        league_name=league,
                        phase=phase,
                        jornada=jornada,
                        local_team=local_team,
                        away_team=away_team,
                        score_local=None,
                        score_away=None,
                        game_label=f"{local_team} vs {away_team}",
                        played=True,
                        source_scope=f"sync::{_league_code(league)}_{_season_short(season)}",
                        scrape_status="success",
                        set_last_scraped=True,
                    )
                    self._persist_scraped_game(
                        conn=conn,
                        game_id=game_id,
                        season_short=_season_short(season),
                        league_code=_league_code(league),
                        phase=phase,
                        jornada=jornada,
                        local_team=local_team,
                        away_team=away_team,
                        scope_name=f"sync::{_league_code(league)}_{_season_short(season)}",
                        boxscores_records=boxscores_records,
                        assists_records=assists_records,
                        clutch_records=clutch_records,
                        lineups_df=lineups_df,
                    )
                summary.scraped_games += 1
                if runtime_tracker:
                    runtime_tracker.mark_game_result(
                        success=True,
                        index=index,
                        total=total_targets,
                        current_game=current_game,
                        next_games=next_games,
                    )
                self._log(progress_callback, "success", f"Partido scrapeado: {local_team} vs {away_team} ({pid})")
            except Exception as exc:
                summary.failed_games += 1
                with self.connect() as conn:
                    conn.execute(
                        "UPDATE games_catalog SET scrape_status = ?, last_scraped_at = ? WHERE pid = ?",
                        [f"failed:{type(exc).__name__}", _now_utc(), pid],
                    )
                if runtime_tracker:
                    runtime_tracker.mark_game_result(
                        success=False,
                        index=index,
                        total=total_targets,
                        current_game=current_game,
                        next_games=next_games,
                    )
                self._log(progress_callback, "warning", f"Fallo en {pid}: {exc}")

        summary.changed_scopes = tuple(sorted(changed_scopes))
        if scrape_player_bios:
            if runtime_tracker:
                runtime_tracker.set_step(
                    step="player_bios",
                    message=f"Completando bios pendientes para {league} {_season_short(season)}",
                )
            self.sync_missing_player_bios(
                season=season,
                league=league,
                limit=player_bio_limit,
                refresh_aggregates=False,
                progress_callback=progress_callback,
                runtime_tracker=runtime_tracker,
            )
        if runtime_tracker:
            runtime_tracker.set_step(
                step="refresh_aggregates",
                message=f"Refrescando agregados para {league} {_season_short(season)}",
            )
        self.refresh_aggregates(changed_scopes=summary.changed_scopes, progress_callback=progress_callback)
        if export_compat_files:
            if runtime_tracker:
                runtime_tracker.set_step(
                    step="export_compat",
                    message=f"Generando exportes de compatibilidad para {league} {_season_short(season)}",
                )
            self.export_compat(
                season=_season_short(season),
                league=league,
                phases=phases,
                jornadas=jornadas,
                progress_callback=progress_callback,
            )
        return summary

    def _persist_scraped_game(
        self,
        *,
        conn: sqlite3.Connection,
        game_id: int,
        season_short: str,
        league_code: str,
        phase: str,
        jornada: int,
        local_team: str,
        away_team: str,
        scope_name: str,
        boxscores_records: list[dict],
        assists_records: list[dict],
        clutch_records: list[dict],
        lineups_df: pd.DataFrame,
    ) -> None:
        boxscores_df = pd.DataFrame(boxscores_records)
        assists_df = pd.DataFrame(assists_records)
        clutch_df = pd.DataFrame(clutch_records)
        self._import_boxscores(
            conn,
            boxscores_df,
            season_short=season_short,
            season_full=_season_full(season_short),
            league_code=league_code,
            league_name=_league_name(league_code),
            scope_name=scope_name,
            lookup={(phase, jornada, _pair_key(local_team, away_team)): game_id},
        )
        self._import_assists(conn, assists_df, season_short, league_code, scope_name, {(phase, jornada, _pair_key(local_team, away_team)): game_id})
        self._import_clutch_player(conn, clutch_df, season_short, league_code, scope_name, {(phase, jornada, _pair_key(local_team, away_team)): game_id})
        self._import_clutch_lineups(conn, lineups_df, season_short, league_code, scope_name, {(phase, jornada, _pair_key(local_team, away_team)): game_id})
        score_local, score_away = self._extract_game_score(boxscores_df, local_team, away_team)
        conn.execute(
            """
            UPDATE games_catalog
            SET score_local = COALESCE(?, score_local),
                score_away = COALESCE(?, score_away),
                score_text = COALESCE(?, score_text),
                scrape_status = 'success',
                last_scraped_at = ?
            WHERE id = ?
            """,
            [
                score_local,
                score_away,
                f"{score_local}-{score_away}" if score_local is not None and score_away is not None else None,
                _now_utc(),
                game_id,
            ],
        )

    def _upsert_player_bio_record(
        self,
        conn: sqlite3.Connection,
        *,
        player_key: str,
        player_name: str,
        birth_date: Optional[str],
        nationality: Optional[str],
        player_url: Optional[str],
    ) -> None:
        conn.execute(
            """
            INSERT INTO player_bios(player_key, player_name, birth_date, nationality, image_url, player_url, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(player_key) DO UPDATE SET
                player_name = excluded.player_name,
                birth_date = COALESCE(excluded.birth_date, player_bios.birth_date),
                nationality = COALESCE(excluded.nationality, player_bios.nationality),
                player_url = COALESCE(excluded.player_url, player_bios.player_url),
                updated_at = excluded.updated_at
            """,
            [
                player_key,
                _normalize_spaces(player_name),
                _value_or_none(birth_date),
                _value_or_none(nationality),
                player_url,
                _now_utc(),
            ],
        )

    def count_pending_player_bios(self, *, season: Optional[SeasonText] = None, league: Optional[LeagueName] = None) -> int:
        sql = """
            SELECT COUNT(*) AS pending_count
            FROM (
                SELECT DISTINCT b.player_key
                FROM boxscores b
                JOIN games_catalog gc ON gc.id = b.game_id
                LEFT JOIN player_bios pb ON pb.player_key = b.player_key
                WHERE b.player_url IS NOT NULL
                  AND (pb.player_key IS NULL OR pb.birth_date IS NULL OR pb.nationality IS NULL)
        """
        params: list[object] = []
        if season:
            sql += " AND gc.season_short = ?"
            params.append(_season_short(season))
        if league:
            sql += " AND gc.league_name = ?"
            params.append(league)
        sql += "\n            ) pending_players"
        with self.connect() as conn:
            return int(conn.execute(sql, params).fetchone()[0] or 0)

    def sync_missing_player_bios(
        self,
        *,
        season: Optional[SeasonText] = None,
        league: Optional[LeagueName] = None,
        limit: Optional[int] = None,
        refresh_aggregates: bool = True,
        progress_callback: ProgressCallback = None,
        runtime_tracker: Optional["SyncRuntimeTracker"] = None,
    ) -> dict[str, int]:
        sql = """
            SELECT DISTINCT b.player_key, b.player_name, b.player_url
            FROM boxscores b
            JOIN games_catalog gc ON gc.id = b.game_id
            LEFT JOIN player_bios pb ON pb.player_key = b.player_key
            WHERE b.player_url IS NOT NULL
              AND (pb.player_key IS NULL OR pb.birth_date IS NULL OR pb.nationality IS NULL)
        """
        params: list[object] = []
        if season:
            sql += " AND gc.season_short = ?"
            params.append(_season_short(season))
        if league:
            sql += " AND gc.league_name = ?"
            params.append(league)
        sql += """
            ORDER BY COALESCE(gc.last_scraped_at, gc.last_seen_at) DESC, b.player_name
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        with self.connect() as conn:
            pending = pd.read_sql_query(sql, conn, params=params)
        if pending.empty:
            self._log(progress_callback, "info", "No hay bios pendientes para completar.")
            return {"pending": 0, "completed": 0, "failed": 0}

        pending_records = pending.to_dict(orient="records")
        total_pending = len(pending_records)
        completed = 0
        failed = 0
        self._log(progress_callback, "info", f"Completando bios pendientes: {total_pending} jugadores...")
        driver = init_driver()
        try:
            with self.connect() as conn:
                for index, row in enumerate(pending_records, start=1):
                    next_bios = [
                        {
                            "pid": item["player_key"],
                            "phase": "Bios",
                            "jornada": "-",
                            "game_label": item["player_name"],
                            "local_team": "",
                            "away_team": "",
                        }
                        for item in pending_records[index : index + 5]
                    ]
                    if runtime_tracker:
                        runtime_tracker.set_step(
                            step="player_bios",
                            message=f"Completando bio {index}/{total_pending}: {row['player_name']}",
                            current_game={
                                "pid": row["player_key"],
                                "phase": "Bios",
                                "jornada": "-",
                                "game_label": row["player_name"],
                                "local_team": "",
                                "away_team": "",
                            },
                            next_games=next_bios,
                        )
                    try:
                        data = obtener_datos_jugador(driver, row["player_url"])
                        self._upsert_player_bio_record(
                            conn,
                            player_key=row["player_key"],
                            player_name=data.get("NOMBRE") or row["player_name"],
                            birth_date=data.get("FECHA NACIMIENTO"),
                            nationality=data.get("NACIONALIDAD"),
                            player_url=row["player_url"],
                        )
                        completed += 1
                        if index == 1 or index % 10 == 0 or index == total_pending:
                            self._log(progress_callback, "info", f"Bios completadas: {completed}/{total_pending}")
                    except Exception as exc:
                        failed += 1
                        self._log(progress_callback, "warning", f"No se pudo completar bio de {row['player_name']}: {exc}")
        finally:
            driver.quit()

        if refresh_aggregates and season and league and (completed > 0):
            self.refresh_aggregates(changed_scopes=[(_season_short(season), league)], progress_callback=progress_callback)
        return {"pending": int(total_pending), "completed": int(completed), "failed": int(failed)}

    def _build_where_clause(self, filters: ReportFilters) -> tuple[str, list[object]]:
        clauses = ["gc.season_short = ?", "gc.league_name = ?"]
        params: list[object] = [_season_short(filters.season), filters.league]
        if filters.phases:
            placeholders = ",".join(["?"] * len(filters.phases))
            clauses.append(f"gc.phase IN ({placeholders})")
            params.extend(list(filters.phases))
        if filters.jornadas:
            placeholders = ",".join(["?"] * len(filters.jornadas))
            clauses.append(f"gc.jornada IN ({placeholders})")
            params.extend([int(value) for value in filters.jornadas])
        return " AND ".join(clauses), params

    def _query_df(self, base_query: str, filters: ReportFilters) -> pd.DataFrame:
        where_sql, params = self._build_where_clause(filters)
        query = f"{base_query} AND {where_sql}"
        with self.connect() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_available_teams(self, filters: ReportFilters) -> list[str]:
        bundle = self.load_report_bundle(filters)
        if bundle.teams_df.empty:
            return []
        return sorted(bundle.teams_df["EQUIPO"].dropna().astype(str).unique().tolist())

    def get_available_players(self, filters: ReportFilters) -> list[str]:
        bundle = self.load_report_bundle(filters)
        if bundle.players_df.empty:
            return []
        return sorted(bundle.players_df["JUGADOR"].dropna().astype(str).unique().tolist())

    def load_report_bundle(self, filters: ReportFilters) -> ReportBundle:
        boxscores_df = self._query_df(BOXSCORE_QUERY, filters)
        assists_df = self._query_df(ASSISTS_QUERY, filters)
        clutch_player_df = self._query_df(CLUTCH_PLAYER_QUERY, filters)
        clutch_lineups_df = self._query_df(CLUTCH_LINEUPS_QUERY, filters)
        with self.connect() as conn:
            bios_df = pd.read_sql_query("SELECT * FROM player_bios", conn)
            games_catalog_df = pd.read_sql_query(
                """
                SELECT id AS game_id, pid, phase, jornada, local_team, away_team
                FROM games_catalog
                WHERE season_short = ? AND league_name = ?
                """,
                conn,
                params=[_season_short(filters.season), filters.league],
            )
        players_df = self._aggregate_players(boxscores_df, bios_df)
        games_df = self._aggregate_team_games(boxscores_df, games_catalog_df)
        teams_df = self._aggregate_teams(games_df)
        clutch_df = self._aggregate_clutch(clutch_player_df)
        return ReportBundle(
            players_df=players_df,
            teams_df=teams_df,
            assists_df=assists_df,
            clutch_df=clutch_df,
            clutch_lineups_df=clutch_lineups_df,
            games_df=games_df,
            boxscores_df=boxscores_df,
        )

    def _aggregate_players(self, boxscores_df: pd.DataFrame, bios_df: pd.DataFrame) -> pd.DataFrame:
        if boxscores_df.empty:
            return pd.DataFrame(columns=["JUGADOR", "EQUIPO", "PJ"])
        df = boxscores_df.copy()
        if "PLAYER_KEY" not in df.columns:
            df["PLAYER_KEY"] = df.apply(
                lambda row: _player_key(row.get("JUGADOR", ""), row.get("URL JUGADOR"), row.get("EQUIPO LOCAL")),
                axis=1,
            )
        sum_columns = [column for column in BOX_SCORE_SUM_COLUMNS if column in df.columns]
        agg_dict = {column: "sum" for column in sum_columns}
        agg_dict.update({"DORSAL": "first", "FASE": "first", "IMAGEN": "first", "JUGADOR": "first", "EQUIPO LOCAL": "first", "URL JUGADOR": "first"})
        aggregated_df = df.groupby("PLAYER_KEY", as_index=False).agg(agg_dict)
        games_count = df.groupby("PLAYER_KEY").size().reset_index(name="PJ")
        aggregated_df = aggregated_df.merge(games_count, on="PLAYER_KEY", how="left")
        aggregated_df = aggregated_df.rename(columns={"EQUIPO LOCAL": "EQUIPO"})
        if not bios_df.empty:
            bios = bios_df.rename(columns={"player_key": "PLAYER_KEY", "birth_date": "FECHA NACIMIENTO", "nationality": "NACIONALIDAD", "image_url": "IMAGEN_BIO", "player_url": "URL JUGADOR_BIO", "player_name": "JUGADOR_BIO"})
            aggregated_df = aggregated_df.merge(
                bios[["PLAYER_KEY", "FECHA NACIMIENTO", "NACIONALIDAD", "IMAGEN_BIO", "URL JUGADOR_BIO", "JUGADOR_BIO"]],
                on="PLAYER_KEY",
                how="left",
            )
            aggregated_df["JUGADOR"] = aggregated_df["JUGADOR_BIO"].fillna(aggregated_df["JUGADOR"])
            aggregated_df["IMAGEN"] = aggregated_df["IMAGEN"].fillna(aggregated_df["IMAGEN_BIO"])
            aggregated_df["URL JUGADOR"] = aggregated_df["URL JUGADOR"].fillna(aggregated_df["URL JUGADOR_BIO"])
            aggregated_df = aggregated_df.drop(columns=["JUGADOR_BIO", "IMAGEN_BIO", "URL JUGADOR_BIO"])
        else:
            aggregated_df["FECHA NACIMIENTO"] = None
            aggregated_df["NACIONALIDAD"] = None
        return aggregated_df

    def _aggregate_team_games(self, boxscores_df: pd.DataFrame, games_catalog_df: pd.DataFrame) -> pd.DataFrame:
        if boxscores_df.empty:
            return pd.DataFrame()
        available_sum_columns = [column for column in BOX_SCORE_SUM_COLUMNS if column in boxscores_df.columns]
        agg_dict = {column: "sum" for column in available_sum_columns}
        agg_dict.update({"IdPartido": "first", "PTS_RIVAL": "first"})
        games_df = boxscores_df.groupby(["FASE", "JORNADA", "EQUIPO LOCAL", "EQUIPO RIVAL"], as_index=False).agg(agg_dict).rename(columns={"IdPartido": "PID"})
        games_df["PLAYS"] = games_df["TL INTENTADOS"] * 0.44 + games_df["T2 INTENTADO"] + games_df["T3 INTENTADO"] + games_df["PERDIDAS"]
        games_df["PPP"] = games_df["PUNTOS"] / games_df["PLAYS"].replace(0, pd.NA)
        games_df["POSS"] = games_df["PLAYS"] - games_df["REB OFFENSIVO"]
        games_df["OFFRTG"] = 100 * games_df["PUNTOS"] / games_df["POSS"].replace(0, pd.NA)
        games_df["PPP OPP"] = pd.NA
        games_df["DEFRTG"] = pd.NA
        games_df["%OREB"] = pd.NA
        games_df["%DREB"] = pd.NA
        games_df["%REB"] = pd.NA
        opponent_lookup = games_df.set_index(["FASE", "JORNADA", "EQUIPO LOCAL", "EQUIPO RIVAL"])
        for index, row in games_df.iterrows():
            key = (row["FASE"], row["JORNADA"], row["EQUIPO RIVAL"], row["EQUIPO LOCAL"])
            if key not in opponent_lookup.index:
                continue
            opponent = opponent_lookup.loc[key]
            games_df.at[index, "PPP OPP"] = opponent["PPP"]
            games_df.at[index, "DEFRTG"] = opponent["OFFRTG"]
            team_off = _safe_float(row["REB OFFENSIVO"])
            team_def = _safe_float(row["REB DEFENSIVO"])
            opp_off = _safe_float(opponent["REB OFFENSIVO"])
            opp_def = _safe_float(opponent["REB DEFENSIVO"])
            games_df.at[index, "%OREB"] = team_off / (team_off + opp_def) if (team_off + opp_def) > 0 else 0
            games_df.at[index, "%DREB"] = team_def / (team_def + opp_off) if (team_def + opp_off) > 0 else 0
            total_reb = team_off + team_def
            opp_total = opp_off + opp_def
            games_df.at[index, "%REB"] = total_reb / (total_reb + opp_total) if (total_reb + opp_total) > 0 else 0
        games_df["NETRTG"] = games_df["OFFRTG"] - games_df["DEFRTG"]
        if not games_catalog_df.empty:
            games_df = games_df.merge(games_catalog_df[["pid", "local_team", "away_team"]], left_on="PID", right_on="pid", how="left")
            games_df["IS_HOME"] = games_df["EQUIPO LOCAL"] == games_df["local_team"]
            games_df = games_df.drop(columns=["pid"], errors="ignore")
        else:
            games_df["IS_HOME"] = pd.NA
        return games_df

    def _attach_split_columns(self, aggregated: pd.DataFrame, subset: pd.DataFrame, numeric_columns: Sequence[str], prefix: str) -> pd.DataFrame:
        if subset.empty:
            for column in ["PJ", *numeric_columns]:
                aggregated[f"{prefix}_{column}"] = 0
            return aggregated
        split_df = subset.groupby("EQUIPO LOCAL").agg(
            {
                **{column: "sum" for column in numeric_columns if column in subset.columns},
                "PPP": "mean",
                "PPP OPP": "mean",
                "OFFRTG": "mean",
                "DEFRTG": "mean",
                "NETRTG": "mean",
                "%OREB": "mean",
                "%DREB": "mean",
                "%REB": "mean",
            }
        )
        split_df["PJ"] = subset.groupby("EQUIPO LOCAL").size()
        split_df = split_df.reset_index().rename(columns={"EQUIPO LOCAL": "EQUIPO"})
        rename_map = {column: f"{prefix}_{column}" for column in split_df.columns if column != "EQUIPO"}
        split_df = split_df.rename(columns=rename_map)
        merged = aggregated.merge(split_df, on="EQUIPO", how="left")
        split_columns = [column for column in merged.columns if column.startswith(f"{prefix}_")]
        if split_columns:
            merged[split_columns] = merged[split_columns].apply(pd.to_numeric, errors="coerce").fillna(0)
        return merged

    def _aggregate_teams(self, games_df: pd.DataFrame) -> pd.DataFrame:
        if games_df.empty:
            return pd.DataFrame()
        not_sum_columns = {"FASE", "JORNADA", "EQUIPO LOCAL", "EQUIPO RIVAL", "PPP", "PPP OPP", "OFFRTG", "DEFRTG", "NETRTG", "%OREB", "%DREB", "%REB", "PID", "pid", "local_team", "away_team", "IS_HOME"}
        aggregated = games_df.groupby("EQUIPO LOCAL").agg(
            {
                "FASE": "first",
                "PPP": "mean",
                "PPP OPP": "mean",
                "OFFRTG": "mean",
                "DEFRTG": "mean",
                "NETRTG": "mean",
                "%OREB": "mean",
                "%DREB": "mean",
                "%REB": "mean",
                **{column: "sum" for column in games_df.columns if column not in not_sum_columns},
            }
        ).reset_index()
        aggregated["PJ"] = games_df.groupby("EQUIPO LOCAL").size().values
        aggregated = aggregated.rename(columns={"EQUIPO LOCAL": "EQUIPO", "PTS_RIVAL": "PUNTOS -", "PUNTOS": "PUNTOS +"})
        numeric_columns = ["MINUTOS JUGADOS", "PUNTOS +", "T2 CONVERTIDO", "T2 INTENTADO", "T3 CONVERTIDO", "T3 INTENTADO", "TL CONVERTIDOS", "TL INTENTADOS", "REB OFFENSIVO", "REB DEFENSIVO", "ASISTENCIAS", "RECUPEROS", "PERDIDAS", "FaltasCOMETIDAS", "FaltasRECIBIDAS", "TAPONES", "PUNTOS -", "PLAYS", "POSS"]
        aggregated = self._attach_split_columns(aggregated, games_df[games_df["IS_HOME"] == True], numeric_columns, "LOCAL")
        aggregated = self._attach_split_columns(aggregated, games_df[games_df["IS_HOME"] == False], numeric_columns, "VISITANTE")
        return aggregated

    def _aggregate_clutch(self, clutch_player_df: pd.DataFrame) -> pd.DataFrame:
        if clutch_player_df.empty:
            return pd.DataFrame()
        df = clutch_player_df.copy()
        if "PLAYER_KEY" not in df.columns:
            df["PLAYER_KEY"] = df.apply(lambda row: _player_key(row.get("JUGADOR", ""), None, row.get("EQUIPO")), axis=1)
        grouped = df.groupby(["EQUIPO", "PLAYER_KEY", "JUGADOR"], as_index=False).agg(
            {
                "IdPartido": pd.Series.nunique,
                "MINUTOS_CLUTCH": "sum",
                "SEGUNDOS_CLUTCH": "sum",
                "PTS": "sum",
                "FGA": "sum",
                "FGM": "sum",
                "3PA": "sum",
                "3PM": "sum",
                "FTA": "sum",
                "FTM": "sum",
                "AST": "sum",
                "TO": "sum",
                "STL": "sum",
                "REB": "sum",
                "REB_O": "sum",
                "REB_D": "sum",
                "PLUS_MINUS": "sum",
            }
        ).rename(columns={"IdPartido": "GAMES"})
        grouped["eFG%"] = grouped.apply(lambda row: ((row["FGM"] + 0.5 * row["3PM"]) / row["FGA"]) if row["FGA"] else 0, axis=1)
        grouped["TS%"] = grouped.apply(lambda row: row["PTS"] / (2 * (row["FGA"] + 0.44 * row["FTA"])) if (row["FGA"] + 0.44 * row["FTA"]) else 0, axis=1)
        weighted = df.groupby(["EQUIPO", "PLAYER_KEY", "JUGADOR"], as_index=False).apply(
            lambda frame: pd.Series(
                {
                    "USG%": float((frame["USG%"] * frame["SEGUNDOS_CLUTCH"]).sum() / frame["SEGUNDOS_CLUTCH"].sum()) if frame["SEGUNDOS_CLUTCH"].sum() else 0.0,
                    "NET_RTG": float((frame["NET_RTG"] * frame["SEGUNDOS_CLUTCH"]).sum() / frame["SEGUNDOS_CLUTCH"].sum()) if frame["SEGUNDOS_CLUTCH"].sum() else 0.0,
                }
            ),
            include_groups=False,
        )
        if isinstance(weighted, pd.Series):
            weighted = weighted.to_frame().T
        grouped = grouped.merge(weighted, on=["EQUIPO", "PLAYER_KEY", "JUGADOR"], how="left")
        return grouped[["EQUIPO", "JUGADOR", "GAMES", "MINUTOS_CLUTCH", "SEGUNDOS_CLUTCH", "PTS", "FGA", "FGM", "3PA", "3PM", "FTA", "FTM", "eFG%", "TS%", "AST", "TO", "STL", "REB", "REB_O", "REB_D", "USG%", "PLUS_MINUS", "NET_RTG"]]

    def refresh_aggregates(self, *, changed_scopes: Optional[Sequence[tuple[str, str]]] = None, progress_callback: ProgressCallback = None) -> None:
        if changed_scopes:
            scopes = list(changed_scopes)
        else:
            with self.connect() as conn:
                scopes_df = pd.read_sql_query("SELECT DISTINCT season_short, league_name FROM games_catalog ORDER BY season_short, league_name", conn)
            scopes = list(scopes_df.itertuples(index=False, name=None))
        for season_short, league in scopes:
            bundle = self.load_report_bundle(ReportFilters(season=season_short, league=league))
            self._write_materialized_scope("players_agg", bundle.players_df, season_short, league)
            self._write_materialized_scope("games_agg", bundle.games_df, season_short, league)
            self._write_materialized_scope("teams_agg", bundle.teams_df, season_short, league)
            self._write_materialized_scope("clutch_agg", bundle.clutch_df, season_short, league)
            self._log(progress_callback, "success", f"Agregados refrescados para {league} {season_short}")

    def _write_materialized_scope(self, table_name: str, df: pd.DataFrame, season_short: str, league: str) -> None:
        frame = df.copy()
        frame.insert(0, "__league", league)
        frame.insert(0, "__season", season_short)
        with self.connect() as conn:
            try:
                conn.execute(f'DELETE FROM "{table_name}" WHERE "__season" = ? AND "__league" = ?', [season_short, league])
            except sqlite3.OperationalError:
                pass
            frame.to_sql(table_name, conn, if_exists="append", index=False)

    def export_compat(self, *, season: SeasonText, league: LeagueName, phases: Sequence[str] = (), jornadas: Sequence[int] = (), progress_callback: ProgressCallback = None) -> dict[str, str]:
        filters = ReportFilters(season=season, league=league, phases=tuple(phases), jornadas=tuple(jornadas))
        bundle = self.load_report_bundle(filters)
        filenames = generate_all_filenames_with_jornadas(str(DATA_DIR), _season_short(season), get_liga_short(league), list(jornadas) if jornadas else None)
        bundle.boxscores_df.drop(columns=["PLAYER_KEY"], errors="ignore").to_excel(filenames["boxscores"], index=False)
        bundle.assists_df.to_excel(filenames["assists"], index=False)
        self._query_df(CLUTCH_PLAYER_QUERY, filters).drop(columns=["PLAYER_KEY"], errors="ignore").to_excel(filenames["clutch_data"], index=False)
        bundle.clutch_lineups_df.to_excel(filenames["clutch_lineups"], index=False)
        bundle.players_df.drop(columns=["PLAYER_KEY"], errors="ignore").to_excel(filenames["players"], index=False)
        bundle.teams_df.to_excel(filenames["teams"], index=False)
        bundle.clutch_df.to_excel(filenames["clutch_aggregated"], index=False)
        bundle.games_df.to_excel(filenames["players"].replace(".xlsx", "_games.xlsx"), index=False)
        self._log(progress_callback, "success", f"Exportes compat generados en {Path(filenames['players']).parent}")
        return filenames

    def publish_data_changes(self, *, repo_root: Path | str, commit_message: Optional[str] = None, extra_paths: Sequence[str] = (), progress_callback: ProgressCallback = None) -> bool:
        repo_root = Path(repo_root)
        message = commit_message or f"chore(data): sync FEB data {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        paths = ["data", *extra_paths]
        status = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=repo_root, capture_output=True, text=True, check=False)
        if not status.stdout.strip():
            self._log(progress_callback, "info", "No hay cambios de datos para publicar.")
            return False
        subprocess.run(["git", "add", "--", *paths], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", message, "--", *paths], cwd=repo_root, check=True)
        subprocess.run(["git", "push", "origin", "HEAD"], cwd=repo_root, check=True)
        self._log(progress_callback, "success", "Cambios de datos publicados en GitHub.")
        return True
