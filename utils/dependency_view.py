from __future__ import annotations

import re
from typing import Any

import pandas as pd
from unidecode import unidecode

from storage import ReportBundle


DEPENDENCY_SHARE_COLUMNS = [
    "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "%MIN_CLUTCH_EQUIPO",
]

DEPENDENCY_SCORE_WEIGHTS = {
    "%PLAYS_EQUIPO": 0.30,
    "%PUNTOS_EQUIPO": 0.25,
    "%AST_EQUIPO": 0.20,
    "%REB_EQUIPO": 0.10,
    "%MIN_CLUTCH_EQUIPO": 0.15,
}

FOCUS_LABELS = {
    "%PLAYS_EQUIPO": "Uso ofensivo",
    "%PUNTOS_EQUIPO": "Anotacion",
    "%AST_EQUIPO": "Creacion",
    "%REB_EQUIPO": "Rebote",
    "%MIN_CLUTCH_EQUIPO": "Minutos clutch",
}

DEPENDENCY_OUTPUT_COLUMNS = [
    "PLAYER_KEY",
    "JUGADOR",
    "EQUIPO",
    "PJ",
    "MINUTOS JUGADOS",
    "PUNTOS",
    "ASISTENCIAS",
    "REB TOTALES",
    "PLAYS",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "%PLAYS_EQUIPO",
    "%MIN_EQUIPO",
    "MINUTOS_CLUTCH",
    "%MIN_CLUTCH_EQUIPO",
    "HAS_CLUTCH_DATA",
    "STD_PUNTOS",
    "STD_PLAYS",
    "DEPENDENCIA_SCORE",
    "DEPENDENCIA_RIESGO",
    "FOCO_PRINCIPAL",
]


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _safe_share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    shares = numerator.div(denominator.replace(0, pd.NA)) * 100.0
    return pd.to_numeric(shares, errors="coerce").fillna(0.0)


def _normalize_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", unidecode(text).upper()).strip()


def _format_name_to_clutch(roster_name: str) -> str:
    name = _normalize_text(roster_name)
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


def _build_clutch_minutes_lookup(clutch_df: pd.DataFrame) -> pd.DataFrame:
    if clutch_df.empty:
        return pd.DataFrame(columns=["__team_norm", "__name_norm", "MINUTOS_CLUTCH"])

    lookup = clutch_df.copy()
    lookup["MINUTOS_CLUTCH"] = _numeric_series(lookup, "MINUTOS_CLUTCH")
    lookup["__team_norm"] = lookup["EQUIPO"].map(_normalize_text)
    lookup["__name_norm"] = lookup["JUGADOR"].map(_normalize_text)
    return lookup.groupby(["__team_norm", "__name_norm"], as_index=False)["MINUTOS_CLUTCH"].sum().reset_index(drop=True)


def _build_clutch_features(players_df: pd.DataFrame, clutch_df: pd.DataFrame) -> pd.DataFrame:
    features = players_df[["PLAYER_KEY", "JUGADOR", "EQUIPO"]].copy()
    features["__team_norm"] = features["EQUIPO"].map(_normalize_text)
    features["__name_norm"] = features["JUGADOR"].map(_format_name_to_clutch).map(_normalize_text)

    if clutch_df.empty:
        features["MINUTOS_CLUTCH"] = pd.Series(float("nan"), index=features.index, dtype=float)
        features["%MIN_CLUTCH_EQUIPO"] = pd.Series(float("nan"), index=features.index, dtype=float)
        features["HAS_CLUTCH_DATA"] = False
        return features[["PLAYER_KEY", "MINUTOS_CLUTCH", "%MIN_CLUTCH_EQUIPO", "HAS_CLUTCH_DATA"]]

    clutch_lookup = _build_clutch_minutes_lookup(clutch_df)
    team_totals = clutch_df.copy()
    team_totals["MINUTOS_CLUTCH"] = _numeric_series(team_totals, "MINUTOS_CLUTCH")
    team_totals["__team_norm"] = team_totals["EQUIPO"].map(_normalize_text)
    team_clutch_totals = team_totals.groupby("__team_norm", as_index=False)["MINUTOS_CLUTCH"].sum().rename(
        columns={"MINUTOS_CLUTCH": "__team_clutch_total"}
    )

    merged = features.merge(clutch_lookup, on=["__team_norm", "__name_norm"], how="left")
    merged = merged.merge(team_clutch_totals, on="__team_norm", how="left")

    team_has_clutch = pd.to_numeric(merged["__team_clutch_total"], errors="coerce").fillna(0.0) > 0
    clutch_minutes = pd.to_numeric(merged["MINUTOS_CLUTCH"], errors="coerce")
    clutch_minutes = clutch_minutes.where(team_has_clutch, pd.NA)
    clutch_minutes = clutch_minutes.fillna(0.0).where(team_has_clutch, pd.NA)
    clutch_share = _safe_share(
        clutch_minutes.fillna(0.0),
        pd.to_numeric(merged["__team_clutch_total"], errors="coerce").fillna(0.0),
    ).where(team_has_clutch, pd.NA)

    merged["MINUTOS_CLUTCH"] = clutch_minutes
    merged["%MIN_CLUTCH_EQUIPO"] = clutch_share
    merged["HAS_CLUTCH_DATA"] = team_has_clutch
    return merged[["PLAYER_KEY", "MINUTOS_CLUTCH", "%MIN_CLUTCH_EQUIPO", "HAS_CLUTCH_DATA"]]


def _build_volatility_features(boxscores_df: pd.DataFrame) -> pd.DataFrame:
    if boxscores_df.empty:
        return pd.DataFrame(columns=["PLAYER_KEY", "STD_PUNTOS", "STD_PLAYS"])

    frame = boxscores_df.copy()
    frame["PUNTOS"] = _numeric_series(frame, "PUNTOS")
    frame["PLAYS"] = (
        _numeric_series(frame, "T2 INTENTADO")
        + _numeric_series(frame, "T3 INTENTADO")
        + 0.44 * _numeric_series(frame, "TL INTENTADOS")
        + _numeric_series(frame, "PERDIDAS")
    )
    return frame.groupby("PLAYER_KEY", as_index=False).agg(
        STD_PUNTOS=("PUNTOS", lambda series: float(pd.to_numeric(series, errors="coerce").std(ddof=0) or 0.0)),
        STD_PLAYS=("PLAYS", lambda series: float(pd.to_numeric(series, errors="coerce").std(ddof=0) or 0.0)),
    )


def _build_team_totals_in_player_games(boxscores_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["PLAYER_KEY", "EQUIPO", "team_points", "team_ast", "team_reb", "team_plays", "team_minutes"]
    if boxscores_df.empty or "PLAYER_KEY" not in boxscores_df.columns:
        return pd.DataFrame(columns=columns)
    if "IdPartido" not in boxscores_df.columns or "EQUIPO LOCAL" not in boxscores_df.columns:
        return pd.DataFrame(columns=columns)

    frame = boxscores_df.copy()
    frame["EQUIPO"] = frame["EQUIPO LOCAL"].fillna("").astype(str)
    frame["PUNTOS"] = _numeric_series(frame, "PUNTOS")
    frame["ASISTENCIAS"] = _numeric_series(frame, "ASISTENCIAS")
    frame["REB TOTALES"] = _numeric_series(frame, "REB OFFENSIVO") + _numeric_series(frame, "REB DEFENSIVO")
    frame["PLAYS"] = (
        _numeric_series(frame, "T2 INTENTADO")
        + _numeric_series(frame, "T3 INTENTADO")
        + 0.44 * _numeric_series(frame, "TL INTENTADOS")
        + _numeric_series(frame, "PERDIDAS")
    )
    frame["MINUTOS JUGADOS"] = _numeric_series(frame, "MINUTOS JUGADOS")

    team_game_totals = frame.groupby(["IdPartido", "EQUIPO"], as_index=False).agg(
        team_points=("PUNTOS", "sum"),
        team_ast=("ASISTENCIAS", "sum"),
        team_reb=("REB TOTALES", "sum"),
        team_plays=("PLAYS", "sum"),
        team_minutes=("MINUTOS JUGADOS", "sum"),
    )
    player_games = frame[["PLAYER_KEY", "IdPartido", "EQUIPO"]].drop_duplicates()
    return player_games.merge(team_game_totals, on=["IdPartido", "EQUIPO"], how="left").groupby(
        ["PLAYER_KEY", "EQUIPO"], as_index=False
    )[["team_points", "team_ast", "team_reb", "team_plays", "team_minutes"]].sum()


def _compute_percentile_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series(float("nan"), index=series.index, dtype=float)
    valid = numeric.notna()
    if valid.any():
        result.loc[valid] = numeric.loc[valid].rank(method="average", pct=True)
    return result


def _compute_dependency_score(df: pd.DataFrame) -> pd.Series:
    percentile_df = pd.DataFrame(
        {column: _compute_percentile_series(df[column]) for column in DEPENDENCY_SHARE_COLUMNS if column in df.columns},
        index=df.index,
    )
    weight_df = pd.DataFrame(
        {column: pd.Series(DEPENDENCY_SCORE_WEIGHTS[column], index=df.index, dtype=float) for column in percentile_df.columns},
        index=df.index,
    )
    available_weights = weight_df.where(percentile_df.notna(), 0.0)
    weighted_sum = (percentile_df.fillna(0.0) * available_weights).sum(axis=1)
    weight_sum = available_weights.sum(axis=1)
    return pd.to_numeric(weighted_sum.div(weight_sum.replace(0, pd.NA)) * 100.0, errors="coerce").fillna(0.0)


def _dependency_band(score: float) -> str:
    if score >= 80.0:
        return "Critica"
    if score >= 65.0:
        return "Alta"
    if score >= 45.0:
        return "Media"
    return "Baja"


def _primary_focus(row: pd.Series) -> str:
    available = {column: float(row[column]) for column in DEPENDENCY_SHARE_COLUMNS if column in row.index and pd.notna(row[column])}
    if not available:
        return FOCUS_LABELS["%PLAYS_EQUIPO"]
    winner = max(available.items(), key=lambda item: item[1])[0]
    return FOCUS_LABELS.get(winner, winner)


def build_dependency_players_view(bundle: ReportBundle) -> pd.DataFrame:
    if bundle.players_df.empty:
        return pd.DataFrame(columns=DEPENDENCY_OUTPUT_COLUMNS)

    players = bundle.players_df.copy()
    players["PJ"] = pd.to_numeric(players.get("PJ", 0), errors="coerce").fillna(0).astype("Int64")
    players["MINUTOS JUGADOS"] = _numeric_series(players, "MINUTOS JUGADOS")
    players["PUNTOS"] = _numeric_series(players, "PUNTOS")
    players["ASISTENCIAS"] = _numeric_series(players, "ASISTENCIAS")
    players["REB TOTALES"] = _numeric_series(players, "REB OFFENSIVO") + _numeric_series(players, "REB DEFENSIVO")
    players["PLAYS"] = (
        _numeric_series(players, "T2 INTENTADO")
        + _numeric_series(players, "T3 INTENTADO")
        + 0.44 * _numeric_series(players, "TL INTENTADOS")
        + _numeric_series(players, "PERDIDAS")
    )

    player_game_totals = _build_team_totals_in_player_games(bundle.boxscores_df)
    if not player_game_totals.empty:
        players = players.merge(player_game_totals, on=["PLAYER_KEY", "EQUIPO"], how="left")
    else:
        team_totals = bundle.teams_df.copy() if not bundle.teams_df.empty else pd.DataFrame(columns=["EQUIPO"])
        team_totals["team_points"] = _numeric_series(team_totals, "PUNTOS +")
        team_totals["team_ast"] = _numeric_series(team_totals, "ASISTENCIAS")
        team_totals["team_reb"] = _numeric_series(team_totals, "REB OFFENSIVO") + _numeric_series(team_totals, "REB DEFENSIVO")
        team_totals["team_plays"] = _numeric_series(team_totals, "PLAYS")
        team_totals["team_minutes"] = _numeric_series(team_totals, "MINUTOS JUGADOS")
        players = players.merge(
            team_totals[["EQUIPO", "team_points", "team_ast", "team_reb", "team_plays", "team_minutes"]],
            on="EQUIPO",
            how="left",
        )

    players["%PUNTOS_EQUIPO"] = _safe_share(players["PUNTOS"], _numeric_series(players, "team_points"))
    players["%AST_EQUIPO"] = _safe_share(players["ASISTENCIAS"], _numeric_series(players, "team_ast"))
    players["%REB_EQUIPO"] = _safe_share(players["REB TOTALES"], _numeric_series(players, "team_reb"))
    players["%PLAYS_EQUIPO"] = _safe_share(players["PLAYS"], _numeric_series(players, "team_plays"))
    players["%MIN_EQUIPO"] = _safe_share(players["MINUTOS JUGADOS"], _numeric_series(players, "team_minutes"))

    players = players.merge(_build_clutch_features(players, bundle.clutch_df), on="PLAYER_KEY", how="left")
    players = players.merge(_build_volatility_features(bundle.boxscores_df), on="PLAYER_KEY", how="left")
    players["HAS_CLUTCH_DATA"] = players["HAS_CLUTCH_DATA"].fillna(False).astype(bool)
    players["STD_PUNTOS"] = pd.to_numeric(players["STD_PUNTOS"], errors="coerce").fillna(0.0)
    players["STD_PLAYS"] = pd.to_numeric(players["STD_PLAYS"], errors="coerce").fillna(0.0)

    players["DEPENDENCIA_SCORE"] = _compute_dependency_score(players)
    players["DEPENDENCIA_RIESGO"] = players["DEPENDENCIA_SCORE"].map(_dependency_band)
    players["FOCO_PRINCIPAL"] = players.apply(_primary_focus, axis=1)

    rounded_columns = [
        "MINUTOS JUGADOS",
        "PUNTOS",
        "ASISTENCIAS",
        "REB TOTALES",
        "PLAYS",
        "%PUNTOS_EQUIPO",
        "%AST_EQUIPO",
        "%REB_EQUIPO",
        "%PLAYS_EQUIPO",
        "%MIN_EQUIPO",
        "MINUTOS_CLUTCH",
        "%MIN_CLUTCH_EQUIPO",
        "STD_PUNTOS",
        "STD_PLAYS",
        "DEPENDENCIA_SCORE",
    ]
    for column in rounded_columns:
        if column in players.columns:
            players[column] = pd.to_numeric(players[column], errors="coerce").round(2)

    output = players[[column for column in DEPENDENCY_OUTPUT_COLUMNS if column in players.columns]].copy()
    return output.sort_values(by=["DEPENDENCIA_SCORE", "%PLAYS_EQUIPO", "PJ"], ascending=[False, False, False], na_position="last")


def build_structural_risk_summary(team_df: pd.DataFrame) -> str:
    if team_df.empty:
        return "Riesgo estructural del equipo: sin datos en el scope actual."

    candidates = {
        "%PLAYS_EQUIPO": "Uso ofensivo",
        "%PUNTOS_EQUIPO": "Anotacion",
        "%AST_EQUIPO": "Creacion",
        "%REB_EQUIPO": "Rebote",
    }
    if bool(team_df["HAS_CLUTCH_DATA"].fillna(False).any()) and "%MIN_CLUTCH_EQUIPO" in team_df.columns:
        candidates["%MIN_CLUTCH_EQUIPO"] = "Minutos clutch"

    best_label = None
    best_player = ""
    best_gap = -1.0
    for column, label in candidates.items():
        column_df = team_df[["JUGADOR", column]].copy()
        column_df[column] = pd.to_numeric(column_df[column], errors="coerce").fillna(0.0)
        column_df = column_df.sort_values(by=column, ascending=False, na_position="last").reset_index(drop=True)
        if column_df.empty:
            continue
        top1 = float(column_df.iloc[0][column] or 0.0)
        top2 = float(column_df.iloc[1][column] or 0.0) if len(column_df) > 1 else 0.0
        gap = max(top1 - top2, 0.0)
        if gap > best_gap:
            best_gap = gap
            best_label = label
            best_player = str(column_df.iloc[0]["JUGADOR"] or "")

    if best_label is None:
        return "Riesgo estructural del equipo: no hay metricas suficientes para estimarlo."
    return f"Riesgo estructural del equipo: la mayor brecha esta en {best_label} ({best_player}, +{best_gap:.1f} pp sobre el segundo)."


def build_player_dependency_diagnosis(player_row: pd.Series) -> str:
    player_name = str(player_row.get("JUGADOR") or "El jugador")
    focus = str(player_row.get("FOCO_PRINCIPAL") or "Uso ofensivo")
    risk = str(player_row.get("DEPENDENCIA_RIESGO") or "Media")
    focus_column = next((column for column, label in FOCUS_LABELS.items() if label == focus), "%PLAYS_EQUIPO")
    share = float(pd.to_numeric(player_row.get(focus_column), errors="coerce") or 0.0)

    if focus == "Minutos clutch":
        diagnosis = (
            f"{player_name} tiene su mayor peso en los minutos clutch: participa en el {share:.1f}% "
            f"de los minutos clutch del equipo con los filtros actuales. Su dependencia actual se clasifica como {risk.lower()}."
        )
    else:
        diagnosis = (
            f"{player_name} concentra su mayor peso en {focus.lower()} con un {share:.1f}% del total del equipo "
            f"con los filtros actuales. Su dependencia actual se clasifica como {risk.lower()}."
        )

    if bool(player_row.get("HAS_CLUTCH_DATA")) and pd.notna(player_row.get("%MIN_CLUTCH_EQUIPO")) and focus != "Minutos clutch":
        clutch_share = float(pd.to_numeric(player_row.get("%MIN_CLUTCH_EQUIPO"), errors="coerce") or 0.0)
        diagnosis += f" Ademas participa en el {clutch_share:.1f}% de los minutos clutch del equipo."
    return diagnosis
