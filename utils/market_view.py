from __future__ import annotations

from typing import Any

import pandas as pd


MARKET_POOL_COLUMNS = [
    "PLAYER_KEY",
    "DORSAL",
    "IMAGEN",
    "JUGADOR",
    "EQUIPO",
    "LIGA",
    "PJ",
    "MINUTOS JUGADOS",
    "PUNTOS",
    "REB TOTALES",
    "ASISTENCIAS",
    "PERDIDAS",
    "PLAYS",
    "USG%",
    "TS%",
    "eFG%",
    "PPP",
    "AST/TO",
    "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "DEPENDENCIA_SCORE",
    "FOCO_PRINCIPAL",
]

MARKET_NUMERIC_COLUMNS = [
    "PJ",
    "MINUTOS JUGADOS",
    "PUNTOS",
    "REB TOTALES",
    "ASISTENCIAS",
    "PERDIDAS",
    "PLAYS",
    "USG%",
    "TS%",
    "eFG%",
    "PPP",
    "AST/TO",
    "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "DEPENDENCIA_SCORE",
]

MARKET_COMPARE_BLOCKS = [
    {
        "key": "volume",
        "title": "Volumen",
        "metrics": ["PJ", "MINUTOS JUGADOS", "PUNTOS", "REB TOTALES", "ASISTENCIAS", "PERDIDAS"],
    },
    {
        "key": "role",
        "title": "Rol",
        "metrics": ["USG%", "PLAYS", "%PLAYS_EQUIPO", "%PUNTOS_EQUIPO", "%AST_EQUIPO", "%REB_EQUIPO"],
    },
    {
        "key": "efficiency",
        "title": "Eficiencia",
        "metrics": ["eFG%", "TS%", "PPP", "AST/TO"],
    },
    {
        "key": "context",
        "title": "Contexto",
        "metrics": ["DEPENDENCIA_SCORE", "FOCO_PRINCIPAL"],
    },
]

MARKET_METRIC_LABELS = {
    "PJ": "PJ",
    "MINUTOS JUGADOS": "MIN",
    "PUNTOS": "PTS",
    "REB TOTALES": "REB",
    "ASISTENCIAS": "AST",
    "PERDIDAS": "TOV",
    "USG%": "USG%",
    "PLAYS": "PLAYS",
    "%PLAYS_EQUIPO": "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO": "%PUNTOS_EQUIPO",
    "%AST_EQUIPO": "%AST_EQUIPO",
    "%REB_EQUIPO": "%REB_EQUIPO",
    "eFG%": "eFG%",
    "TS%": "TS%",
    "PPP": "PPP",
    "AST/TO": "AST/TO",
    "DEPENDENCIA_SCORE": "DEPENDENCIA_SCORE",
    "FOCO_PRINCIPAL": "FOCO_PRINCIPAL",
}

LOWER_IS_BETTER_COLUMNS = {"PERDIDAS"}

MARKET_DEPENDENCY_COLUMNS = [
    "%PLAYS_EQUIPO",
    "%PUNTOS_EQUIPO",
    "%AST_EQUIPO",
    "%REB_EQUIPO",
    "DEPENDENCIA_SCORE",
    "FOCO_PRINCIPAL",
]


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _to_number(value: Any) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0])


def _format_metric_value(column: str, value: Any) -> str:
    if column == "FOCO_PRINCIPAL":
        return str(value or "-")
    numeric = _to_number(value)
    if column == "PPP":
        return f"{numeric:.3f}"
    if column in {
        "MINUTOS JUGADOS",
        "PUNTOS",
        "REB TOTALES",
        "ASISTENCIAS",
        "PERDIDAS",
        "PLAYS",
        "USG%",
        "TS%",
        "eFG%",
        "%PLAYS_EQUIPO",
        "%PUNTOS_EQUIPO",
        "%AST_EQUIPO",
        "%REB_EQUIPO",
        "DEPENDENCIA_SCORE",
    }:
        return f"{numeric:.1f}"
    if column in {"AST/TO"}:
        return f"{numeric:.2f}"
    if column == "PJ":
        return str(int(round(numeric)))
    return f"{numeric:.1f}"


def _percentile_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    percentile_df = pd.DataFrame(index=df.index)
    for column in columns:
        percentile_df[column] = _numeric_series(df, column).rank(method="average", pct=True).mul(100.0)
    return percentile_df.fillna(0.0)


def _preserve_player_order(df: pd.DataFrame, player_keys: list[str]) -> pd.DataFrame:
    if df.empty or "PLAYER_KEY" not in df.columns:
        return df
    lookup = {str(player_key): index for index, player_key in enumerate(player_keys)}
    ordered = df.copy()
    ordered["_player_order"] = ordered["PLAYER_KEY"].astype(str).map(lookup)
    ordered = ordered.dropna(subset=["_player_order"]).sort_values(by=["_player_order", "JUGADOR"], ascending=[True, True], na_position="last")
    return ordered.drop(columns=["_player_order"])


def build_market_player_pool(gm_df: pd.DataFrame, dependency_df: pd.DataFrame, league: str) -> pd.DataFrame:
    if gm_df.empty:
        return pd.DataFrame(columns=MARKET_POOL_COLUMNS)

    dependency_subset = (
        dependency_df[["PLAYER_KEY", *[column for column in MARKET_DEPENDENCY_COLUMNS if column in dependency_df.columns]]]
        .drop_duplicates(subset=["PLAYER_KEY"])
        .copy()
        if not dependency_df.empty and "PLAYER_KEY" in dependency_df.columns
        else pd.DataFrame(columns=["PLAYER_KEY", *MARKET_DEPENDENCY_COLUMNS])
    )

    pool_df = gm_df.merge(dependency_subset, on="PLAYER_KEY", how="left")
    pool_df["LIGA"] = str(league or "").strip()
    for column in MARKET_NUMERIC_COLUMNS:
        pool_df[column] = _numeric_series(pool_df, column)
    if "FOCO_PRINCIPAL" not in pool_df.columns:
        pool_df["FOCO_PRINCIPAL"] = ""
    return pool_df[[column for column in MARKET_POOL_COLUMNS if column in pool_df.columns]].copy().reset_index(drop=True)


def filter_market_pool(
    pool_df: pd.DataFrame,
    *,
    min_games: int = 5,
    min_minutes: float = 10.0,
    query: str | None = None,
) -> pd.DataFrame:
    if pool_df.empty:
        return pool_df.copy()

    filtered = pool_df[
        (_numeric_series(pool_df, "PJ") >= max(int(min_games), 0))
        & (_numeric_series(pool_df, "MINUTOS JUGADOS") >= max(float(min_minutes), 0.0))
    ].copy()

    normalized_query = str(query or "").strip().casefold()
    if normalized_query:
        haystack = (
            filtered.get("JUGADOR", "").astype(str)
            + " "
            + filtered.get("EQUIPO", "").astype(str)
            + " "
            + filtered.get("LIGA", "").astype(str)
        ).str.casefold()
        filtered = filtered.loc[haystack.str.contains(normalized_query, na=False)].copy()

    sort_columns = [column for column in ["PUNTOS", "USG%", "JUGADOR"] if column in filtered.columns]
    sort_directions = [False, False, True][: len(sort_columns)]
    if sort_columns:
        filtered = filtered.sort_values(by=sort_columns, ascending=sort_directions, na_position="last")
    return filtered.reset_index(drop=True)


def build_market_compare_results(pool_df: pd.DataFrame, player_keys: list[str]) -> dict[str, Any]:
    normalized_keys: list[str] = []
    for value in player_keys:
        text = str(value or "").strip()
        if text and text not in normalized_keys:
            normalized_keys.append(text)

    if len(normalized_keys) < 2:
        raise ValueError("Selecciona al menos 2 jugadores para comparar.")
    if len(normalized_keys) > 6:
        raise ValueError("La comparacion profunda admite un maximo de 6 jugadores.")
    if pool_df.empty or "PLAYER_KEY" not in pool_df.columns:
        raise ValueError("No hay datos de mercado disponibles para comparar.")

    selected = _preserve_player_order(pool_df[pool_df["PLAYER_KEY"].astype(str).isin(normalized_keys)].copy(), normalized_keys)
    if len(selected.index) < 2:
        raise ValueError("No se han encontrado suficientes jugadores validos en el pool actual.")

    percentile_df = _percentile_frame(pool_df, [column for column in MARKET_NUMERIC_COLUMNS if column in pool_df.columns])
    percentile_lookup = percentile_df.copy()
    percentile_lookup["PLAYER_KEY"] = pool_df["PLAYER_KEY"].astype(str).tolist()
    percentile_lookup = percentile_lookup.drop_duplicates(subset=["PLAYER_KEY"]).set_index("PLAYER_KEY")

    players = []
    percentiles: dict[str, dict[str, float | None]] = {}
    for _, player_row in selected.iterrows():
        player_key = str(player_row.get("PLAYER_KEY") or "")
        players.append(
            {
                "playerKey": player_key,
                "label": f"{str(player_row.get('JUGADOR') or '-') } | {str(player_row.get('EQUIPO') or '-')}",
                "name": str(player_row.get("JUGADOR") or ""),
                "team": str(player_row.get("EQUIPO") or ""),
                "league": str(player_row.get("LIGA") or ""),
                "image": str(player_row.get("IMAGEN") or ""),
                "focus": str(player_row.get("FOCO_PRINCIPAL") or ""),
                "dependencyScore": _to_number(player_row.get("DEPENDENCIA_SCORE")),
            }
        )
        percentiles[player_key] = {}

    blocks = []
    for block in MARKET_COMPARE_BLOCKS:
        metric_payloads = []
        for metric in block["metrics"]:
            if metric not in selected.columns:
                continue
            if metric == "FOCO_PRINCIPAL":
                metric_payloads.append(
                    {
                        "key": metric,
                        "label": MARKET_METRIC_LABELS.get(metric, metric),
                        "higherIsBetter": None,
                        "rows": [
                            {
                                "playerKey": str(player_row.get("PLAYER_KEY") or ""),
                                "value": str(player_row.get(metric) or ""),
                                "formatted": _format_metric_value(metric, player_row.get(metric)),
                                "percentile": None,
                                "deltaToBest": None,
                                "deltaToWorst": None,
                            }
                            for _, player_row in selected.iterrows()
                        ],
                    }
                )
                continue

            values = _numeric_series(selected, metric)
            higher_is_better = metric not in LOWER_IS_BETTER_COLUMNS
            best_value = float(values.max() if higher_is_better else values.min())
            worst_value = float(values.min() if higher_is_better else values.max())
            rows = []
            for _, player_row in selected.iterrows():
                player_key = str(player_row.get("PLAYER_KEY") or "")
                value = _to_number(player_row.get(metric))
                percentile = float(percentile_lookup.loc[player_key, metric]) if player_key in percentile_lookup.index else 0.0
                percentiles[player_key][metric] = percentile
                rows.append(
                    {
                        "playerKey": player_key,
                        "value": value,
                        "formatted": _format_metric_value(metric, player_row.get(metric)),
                        "percentile": percentile,
                        "deltaToBest": value - best_value,
                        "deltaToWorst": value - worst_value,
                    }
                )

            metric_payloads.append(
                {
                    "key": metric,
                    "label": MARKET_METRIC_LABELS.get(metric, metric),
                    "higherIsBetter": higher_is_better,
                    "bestValue": best_value,
                    "worstValue": worst_value,
                    "rows": rows,
                }
            )

        blocks.append({"key": block["key"], "title": block["title"], "metrics": metric_payloads})

    return {
        "players": players,
        "blocks": blocks,
        "percentiles": percentiles,
        "poolSummary": {
            "totalPlayers": int(len(pool_df.index)),
            "selectedPlayers": int(len(selected.index)),
            "selectedPlayerKeys": normalized_keys,
        },
    }
