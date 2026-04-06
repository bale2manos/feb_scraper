from __future__ import annotations

from typing import Any

import pandas as pd


PLAYER_TREND_METRIC_OPTIONS = {
    "PUNTOS": "PTS",
    "PLAYS": "Plays",
    "REB": "REB",
    "AST": "AST",
    "PERDIDAS": "PERD",
    "MINUTOS": "Minutos",
}

TEAM_TREND_METRIC_OPTIONS = {
    "PUNTOS +": "Puntos +",
    "PUNTOS -": "Puntos -",
    "OFFRTG": "OFFRTG",
    "DEFRTG": "DEFRTG",
    "NETRTG": "NETRTG",
    "%REB": "%REB",
}


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _as_float(value: Any) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0])


def _build_result_label(points_for: float, points_against: float) -> str:
    if points_for > points_against:
        return "Victoria"
    if points_for < points_against:
        return "Derrota"
    return "Empate"


def _build_match_label(jornada: Any, rival: Any) -> str:
    jornada_text = str(int(jornada)) if pd.notna(jornada) and str(jornada).strip() else "?"
    rival_text = str(rival or "").strip()
    return f"J{jornada_text} vs {rival_text}" if rival_text else f"J{jornada_text}"


def _player_plays_series(frame: pd.DataFrame) -> pd.Series:
    return (
        _numeric_series(frame, "T2 INTENTADO")
        + _numeric_series(frame, "T3 INTENTADO")
        + 0.44 * _numeric_series(frame, "TL INTENTADOS")
        + _numeric_series(frame, "PERDIDAS")
    )


def build_recent_player_games(boxscores_df: pd.DataFrame, player_key: str, last_n: int = 5) -> pd.DataFrame:
    columns = ["PARTIDO", "FASE", "JORNADA", "RIVAL", "RESULTADO", "MINUTOS", "PUNTOS", "REB", "AST", "PERDIDAS", "PLAYS"]
    if boxscores_df.empty or "PLAYER_KEY" not in boxscores_df.columns or not player_key:
        return pd.DataFrame(columns=columns)

    frame = boxscores_df[boxscores_df["PLAYER_KEY"].astype(str) == str(player_key)].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)

    frame["MINUTOS"] = _numeric_series(frame, "MINUTOS JUGADOS")
    frame["PUNTOS"] = _numeric_series(frame, "PUNTOS")
    frame["REB"] = _numeric_series(frame, "REB OFFENSIVO") + _numeric_series(frame, "REB DEFENSIVO")
    frame["AST"] = _numeric_series(frame, "ASISTENCIAS")
    frame["PERDIDAS"] = _numeric_series(frame, "PERDIDAS")
    frame["PLAYS"] = _player_plays_series(frame)
    frame["__jornada_sort"] = pd.to_numeric(frame.get("JORNADA"), errors="coerce")
    frame["__game_sort"] = pd.to_numeric(frame.get("IdPartido"), errors="coerce")
    frame["PARTIDO"] = [
        _build_match_label(jornada, rival)
        for jornada, rival in zip(frame.get("JORNADA", pd.Series(index=frame.index)), frame.get("EQUIPO RIVAL", pd.Series(index=frame.index)))
    ]

    recent = frame.sort_values(by=["__jornada_sort", "__game_sort"], ascending=[False, False], na_position="last").head(last_n)
    return pd.DataFrame(
        {
            "PARTIDO": recent["PARTIDO"].astype(str),
            "FASE": recent.get("FASE", pd.Series("", index=recent.index)).fillna("").astype(str),
            "JORNADA": recent.get("JORNADA", pd.Series("", index=recent.index)),
            "RIVAL": recent.get("EQUIPO RIVAL", pd.Series("", index=recent.index)).fillna("").astype(str),
            "RESULTADO": recent.get("RESULTADO", pd.Series("", index=recent.index)).fillna("").astype(str),
            "MINUTOS": recent["MINUTOS"].round(1),
            "PUNTOS": recent["PUNTOS"].round(1),
            "REB": recent["REB"].round(1),
            "AST": recent["AST"].round(1),
            "PERDIDAS": recent["PERDIDAS"].round(1),
            "PLAYS": recent["PLAYS"].round(2),
        }
    ).reset_index(drop=True)


def build_player_scope_baseline(players_df: pd.DataFrame, player_key: str) -> dict[str, float]:
    if players_df.empty or "PLAYER_KEY" not in players_df.columns:
        return {column: 0.0 for column in PLAYER_TREND_METRIC_OPTIONS}

    rows = players_df[players_df["PLAYER_KEY"].astype(str) == str(player_key)].copy()
    if rows.empty:
        return {column: 0.0 for column in PLAYER_TREND_METRIC_OPTIONS}

    row = rows.iloc[0]
    games = max(_as_float(row.get("PJ")), 1.0)
    rebounds = _as_float(row.get("REB OFFENSIVO")) + _as_float(row.get("REB DEFENSIVO"))
    plays = _as_float(row.get("T2 INTENTADO")) + _as_float(row.get("T3 INTENTADO")) + 0.44 * _as_float(row.get("TL INTENTADOS")) + _as_float(row.get("PERDIDAS"))
    return {
        "PUNTOS": _as_float(row.get("PUNTOS")) / games,
        "PLAYS": plays / games,
        "REB": rebounds / games,
        "AST": _as_float(row.get("ASISTENCIAS")) / games,
        "PERDIDAS": _as_float(row.get("PERDIDAS")) / games,
        "MINUTOS": _as_float(row.get("MINUTOS JUGADOS")) / games,
    }


def build_recent_team_games(games_df: pd.DataFrame, team_name: str, last_n: int = 5) -> pd.DataFrame:
    columns = ["PARTIDO", "FASE", "JORNADA", "RIVAL", "RESULTADO", "PUNTOS +", "PUNTOS -", "OFFRTG", "DEFRTG", "NETRTG", "%REB"]
    if games_df.empty or not team_name:
        return pd.DataFrame(columns=columns)

    frame = games_df[games_df["EQUIPO LOCAL"].astype(str) == str(team_name)].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)

    frame["PUNTOS +"] = _numeric_series(frame, "PUNTOS")
    frame["PUNTOS -"] = _numeric_series(frame, "PTS_RIVAL")
    frame["OFFRTG"] = _numeric_series(frame, "OFFRTG")
    frame["DEFRTG"] = _numeric_series(frame, "DEFRTG")
    frame["NETRTG"] = _numeric_series(frame, "NETRTG")
    frame["%REB"] = _numeric_series(frame, "%REB") * 100.0
    frame["RESULTADO"] = [_build_result_label(points_for, points_against) for points_for, points_against in zip(frame["PUNTOS +"], frame["PUNTOS -"])]
    frame["PARTIDO"] = [
        _build_match_label(jornada, rival)
        for jornada, rival in zip(frame.get("JORNADA", pd.Series(index=frame.index)), frame.get("EQUIPO RIVAL", pd.Series(index=frame.index)))
    ]
    frame["__jornada_sort"] = pd.to_numeric(frame.get("JORNADA"), errors="coerce")
    frame["__game_sort"] = pd.to_numeric(frame.get("PID"), errors="coerce")

    recent = frame.sort_values(by=["__jornada_sort", "__game_sort"], ascending=[False, False], na_position="last").head(last_n)
    return pd.DataFrame(
        {
            "PARTIDO": recent["PARTIDO"].astype(str),
            "FASE": recent.get("FASE", pd.Series("", index=recent.index)).fillna("").astype(str),
            "JORNADA": recent.get("JORNADA", pd.Series("", index=recent.index)),
            "RIVAL": recent.get("EQUIPO RIVAL", pd.Series("", index=recent.index)).fillna("").astype(str),
            "RESULTADO": recent["RESULTADO"].astype(str),
            "PUNTOS +": recent["PUNTOS +"].round(1),
            "PUNTOS -": recent["PUNTOS -"].round(1),
            "OFFRTG": recent["OFFRTG"].round(2),
            "DEFRTG": recent["DEFRTG"].round(2),
            "NETRTG": recent["NETRTG"].round(2),
            "%REB": recent["%REB"].round(2),
        }
    ).reset_index(drop=True)


def build_team_scope_baseline(games_df: pd.DataFrame, team_name: str) -> dict[str, float]:
    if games_df.empty or not team_name:
        return {column: 0.0 for column in TEAM_TREND_METRIC_OPTIONS}

    frame = games_df[games_df["EQUIPO LOCAL"].astype(str) == str(team_name)].copy()
    if frame.empty:
        return {column: 0.0 for column in TEAM_TREND_METRIC_OPTIONS}

    return {
        "PUNTOS +": float(_numeric_series(frame, "PUNTOS").mean() or 0.0),
        "PUNTOS -": float(_numeric_series(frame, "PTS_RIVAL").mean() or 0.0),
        "OFFRTG": float(_numeric_series(frame, "OFFRTG").mean() or 0.0),
        "DEFRTG": float(_numeric_series(frame, "DEFRTG").mean() or 0.0),
        "NETRTG": float(_numeric_series(frame, "NETRTG").mean() or 0.0),
        "%REB": float((_numeric_series(frame, "%REB") * 100.0).mean() or 0.0),
    }


def build_recent_vs_scope_summary(recent_df: pd.DataFrame, baseline: dict[str, float], metrics: list[str]) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for metric in metrics:
        recent_avg = float(pd.to_numeric(recent_df.get(metric, pd.Series(dtype=float)), errors="coerce").mean() or 0.0)
        scope_avg = float(baseline.get(metric, 0.0))
        rows.append(
            {
                "metric": metric,
                "recent_avg": recent_avg,
                "scope_avg": scope_avg,
                "delta": recent_avg - scope_avg,
            }
        )
    return pd.DataFrame(rows)


def _normalize_metric_list(metric: str | list[str] | tuple[str, ...] | Any) -> list[str]:
    if metric is None:
        return []
    if isinstance(metric, str):
        return [metric] if metric else []
    normalized: list[str] = []
    if isinstance(metric, pd.Index):
        iterable = metric.tolist()
    elif isinstance(metric, pd.Series):
        iterable = metric.tolist()
    elif hasattr(metric, "tolist") and not isinstance(metric, (list, tuple, set)):
        converted = metric.tolist()
        iterable = converted if isinstance(converted, list) else [converted]
    else:
        iterable = list(metric)

    for value in iterable:
        if isinstance(value, str):
            if value:
                normalized.append(value)
        elif isinstance(value, (list, tuple, set, pd.Index, pd.Series)):
            normalized.extend(_normalize_metric_list(list(value)))
        elif hasattr(value, "tolist") and not isinstance(value, (bytes, bytearray)):
            normalized.extend(_normalize_metric_list(value.tolist()))
    return normalized


def build_trend_chart_frame(recent_df: pd.DataFrame, metric: str | list[str]) -> pd.DataFrame:
    metrics = _normalize_metric_list(metric)
    available_columns = {str(value) for value in list(recent_df.columns)}
    metrics = [value for value in metrics if isinstance(value, str) and value in available_columns]
    if recent_df.empty or not metrics:
        columns = ["PARTIDO", "__ORDER"]
        if "JORNADA" in recent_df.columns:
            columns.insert(1, "JORNADA")
        return pd.DataFrame(columns=columns)

    base_columns = ["PARTIDO", *metrics]
    if "JORNADA" in recent_df.columns:
        base_columns.append("JORNADA")
    chart_df = recent_df[base_columns].copy()
    for value in metrics:
        chart_df[value] = pd.to_numeric(chart_df[value], errors="coerce").fillna(0.0)
    if "JORNADA" in chart_df.columns:
        chart_df["JORNADA"] = pd.to_numeric(chart_df["JORNADA"], errors="coerce")
    chart_df = chart_df.iloc[::-1].reset_index(drop=True)
    chart_df["__ORDER"] = range(len(chart_df))
    return chart_df
