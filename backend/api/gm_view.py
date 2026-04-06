from __future__ import annotations

import re
from typing import Any

import pandas as pd
from unidecode import unidecode


GM_BIRTH_YEAR_COLUMN = "AÑO NACIMIENTO"

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

GM_EXPORT_COLUMNS = [
    "JUGADOR",
    "EQUIPO",
    "NACIONALIDAD",
    GM_BIRTH_YEAR_COLUMN,
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
]


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series, scale: float = 1.0) -> pd.Series:
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


def _normalize_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", unidecode(text).upper()).strip()


def _ast_to_ratio(assists: pd.Series, turnovers: pd.Series) -> pd.Series:
    ratio = assists.div(turnovers.replace(0, pd.NA))
    fallback = assists.where((turnovers == 0) & (assists > 0), 0.0)
    return pd.to_numeric(ratio, errors="coerce").fillna(fallback).round(2)


def _build_team_totals_lookup(teams_df: pd.DataFrame) -> pd.DataFrame:
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


def _compute_usg(
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
    team_lookup = _build_team_totals_lookup(teams_df).set_index("EQUIPO")
    team_mp = teams.map(team_lookup["team_MP"]).fillna(0.0)
    team_fga = teams.map(team_lookup["team_FGA"]).fillna(0.0)
    team_fta = teams.map(team_lookup["team_FTA"]).fillna(0.0)
    team_tov = teams.map(team_lookup["team_TOV"]).fillna(0.0)
    player_fga = t2_attempts + t3_attempts
    numerator = (player_fga + 0.44 * t1_attempts + turnovers) * (team_mp / 5.0)
    denominator = minutes * (team_fga + 0.44 * team_fta + team_tov)
    return pd.to_numeric(numerator.div(denominator.replace(0, pd.NA)) * 100.0, errors="coerce").fillna(0.0)


def build_gm_players_view(players_df: pd.DataFrame, mode: str, teams_df: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = ["PLAYER_KEY", "DORSAL", "IMAGEN", *GM_EXPORT_COLUMNS]
    if players_df.empty:
        return pd.DataFrame(columns=columns)

    df = players_df.copy()
    numeric_values = {column: _numeric_series(df, column) for column in GM_COUNT_COLUMNS}
    player_keys = df["PLAYER_KEY"].astype(str) if "PLAYER_KEY" in df.columns else df.index.astype(str)
    player_names = df["JUGADOR"].fillna("").astype(str) if "JUGADOR" in df.columns else pd.Series("", index=df.index, dtype=str)
    teams = df["EQUIPO"].fillna("").astype(str) if "EQUIPO" in df.columns else pd.Series("", index=df.index, dtype=str)
    nationalities = df["NACIONALIDAD"].fillna("").astype(str) if "NACIONALIDAD" in df.columns else pd.Series("", index=df.index, dtype=str)
    dorsals = df["DORSAL"] if "DORSAL" in df.columns else pd.Series([None] * len(df), index=df.index)
    images = df["IMAGEN"] if "IMAGEN" in df.columns else pd.Series([None] * len(df), index=df.index)
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
    gm_df["DORSAL"] = dorsals
    gm_df["IMAGEN"] = images
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

    gm_df["T1%"] = _safe_ratio(numeric_values["TL CONVERTIDOS"], numeric_values["TL INTENTADOS"], 100.0).round(2)
    gm_df["T2%"] = _safe_ratio(numeric_values["T2 CONVERTIDO"], numeric_values["T2 INTENTADO"], 100.0).round(2)
    gm_df["T3%"] = _safe_ratio(numeric_values["T3 CONVERTIDO"], numeric_values["T3 INTENTADO"], 100.0).round(2)
    gm_df["eFG%"] = _safe_ratio(field_goals_made + 0.5 * numeric_values["T3 CONVERTIDO"], field_goals_att, 100.0).round(2)
    gm_df["TS%"] = _safe_ratio(numeric_values["PUNTOS"], 2 * (field_goals_att + 0.44 * numeric_values["TL INTENTADOS"]), 100.0).round(2)
    gm_df["PPP"] = _safe_ratio(numeric_values["PUNTOS"], plays_total, 1.0).round(3)
    gm_df["AST/TO"] = _ast_to_ratio(numeric_values["ASISTENCIAS"], numeric_values["PERDIDAS"])
    gm_df["TOV%"] = _safe_ratio(numeric_values["PERDIDAS"], plays_total, 100.0).round(2)
    gm_df["USG%"] = _compute_usg(
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
