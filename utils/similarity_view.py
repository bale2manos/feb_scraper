from __future__ import annotations

from typing import Any

import pandas as pd

from storage import ReportBundle


SIMILARITY_FEATURE_WEIGHTS: dict[str, float] = {
    "MINUTOS JUGADOS": 0.08,
    "PLAYS": 0.14,
    "USG%": 0.12,
    "%PLAYS_EQUIPO": 0.10,
    "PUNTOS": 0.10,
    "REB TOTALES": 0.08,
    "ASISTENCIAS": 0.10,
    "%AST_EQUIPO": 0.08,
    "%REB_EQUIPO": 0.06,
    "TS%": 0.08,
    "AST/TO": 0.06,
}

SIMILARITY_FEATURE_LABELS: dict[str, str] = {
    "MINUTOS JUGADOS": "Minutos",
    "PLAYS": "Plays",
    "USG%": "USG%",
    "%PLAYS_EQUIPO": "Uso ofensivo del equipo",
    "PUNTOS": "Puntos",
    "REB TOTALES": "Rebotes",
    "ASISTENCIAS": "Asistencias",
    "%AST_EQUIPO": "Creacion del equipo",
    "%REB_EQUIPO": "Peso en rebote",
    "TS%": "TS%",
    "AST/TO": "AST/TO",
}

SIMILARITY_DEPENDENCY_COLUMNS = ["%PLAYS_EQUIPO", "%AST_EQUIPO", "%REB_EQUIPO", "FOCO_PRINCIPAL", "DEPENDENCIA_SCORE"]
SIMILARITY_FEATURE_KEYS = tuple(SIMILARITY_FEATURE_WEIGHTS.keys())


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _to_number(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0]
    return float(numeric)


def _format_metric_value(column: str, value: Any) -> str:
    numeric = _to_number(value)
    if column in {"AST/TO", "TS%", "USG%", "%PLAYS_EQUIPO", "%AST_EQUIPO", "%REB_EQUIPO"}:
        return f"{numeric:.1f}"
    if abs(numeric) >= 100:
        return f"{numeric:.1f}"
    return f"{numeric:.2f}" if abs(numeric) < 10 else f"{numeric:.1f}"


def _percentile_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    percentile_df = pd.DataFrame(index=df.index)
    for column in columns:
        numeric = _numeric_series(df, column)
        percentile_df[column] = numeric.rank(method="average", pct=True)
    return percentile_df.fillna(0.0)


def _reason_text(column: str, target_value: Any, candidate_value: Any) -> str:
    label = SIMILARITY_FEATURE_LABELS.get(column, column)
    return f"{label}: { _format_metric_value(column, target_value) } vs { _format_metric_value(column, candidate_value) }"


def _difference_text(column: str, target_value: Any, candidate_value: Any) -> str:
    label = SIMILARITY_FEATURE_LABELS.get(column, column)
    candidate = _to_number(candidate_value)
    target = _to_number(target_value)
    direction = "Mas" if candidate > target else "Menos"
    return f"{direction} {label.lower()}: { _format_metric_value(column, candidate_value) } vs { _format_metric_value(column, target_value) }"


def get_similarity_feature_catalog() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": SIMILARITY_FEATURE_LABELS.get(key, key),
            "defaultWeight": float(default_weight),
        }
        for key, default_weight in SIMILARITY_FEATURE_WEIGHTS.items()
    ]


def resolve_similarity_feature_weights(weight_overrides: dict[str, Any] | None = None) -> dict[str, float]:
    resolved: dict[str, float] = {}
    for key, default_weight in SIMILARITY_FEATURE_WEIGHTS.items():
        raw_value = default_weight if weight_overrides is None else weight_overrides.get(key, default_weight)
        numeric = max(_to_number(raw_value), 0.0)
        resolved[key] = numeric

    active_total = sum(value for value in resolved.values() if value > 0)
    if active_total <= 0:
        raise ValueError("Selecciona al menos una metrica activa para calcular similares.")

    return {
        key: (value / active_total if value > 0 else 0.0)
        for key, value in resolved.items()
    }


def build_similarity_player_pool(
    bundle: ReportBundle,
    gm_df: pd.DataFrame,
    dependency_df: pd.DataFrame,
) -> pd.DataFrame:
    if gm_df.empty:
        return pd.DataFrame(
            columns=[
                "PLAYER_KEY",
                "DORSAL",
                "IMAGEN",
                "JUGADOR",
                "EQUIPO",
                "PJ",
                "MINUTOS JUGADOS",
                "PUNTOS",
                "REB TOTALES",
                "ASISTENCIAS",
                "USG%",
                "PLAYS",
                "TS%",
                "AST/TO",
                "%PLAYS_EQUIPO",
                "%AST_EQUIPO",
                "%REB_EQUIPO",
                "FOCO_PRINCIPAL",
                "DEPENDENCIA_SCORE",
            ]
        )

    dependency_subset = (
        dependency_df[["PLAYER_KEY", *[column for column in SIMILARITY_DEPENDENCY_COLUMNS if column in dependency_df.columns]]]
        .drop_duplicates(subset=["PLAYER_KEY"])
        .copy()
        if not dependency_df.empty and "PLAYER_KEY" in dependency_df.columns
        else pd.DataFrame(columns=["PLAYER_KEY", *SIMILARITY_DEPENDENCY_COLUMNS])
    )

    pool_df = gm_df.merge(dependency_subset, on="PLAYER_KEY", how="left")
    for column in SIMILARITY_FEATURE_WEIGHTS:
        pool_df[column] = _numeric_series(pool_df, column)
    pool_df["PJ"] = pd.to_numeric(pool_df.get("PJ", 0), errors="coerce").fillna(0).astype(int)
    if "FOCO_PRINCIPAL" not in pool_df.columns:
        pool_df["FOCO_PRINCIPAL"] = ""
    if "DEPENDENCIA_SCORE" not in pool_df.columns:
        pool_df["DEPENDENCIA_SCORE"] = 0.0
    return pool_df.reset_index(drop=True)


def build_player_similarity_results(
    pool_df: pd.DataFrame,
    target_player_key: str,
    min_games: int = 5,
    min_minutes: float = 10.0,
    limit: int = 10,
    feature_weights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if pool_df.empty or "PLAYER_KEY" not in pool_df.columns:
        return {"target": None, "candidates": []}

    player_keys = pool_df["PLAYER_KEY"].astype(str)
    if str(target_player_key) not in player_keys.tolist():
        return {"target": None, "candidates": []}

    target_row = pool_df.loc[player_keys == str(target_player_key)].iloc[0]
    candidate_pool = pool_df[
        (player_keys != str(target_player_key))
        & (_numeric_series(pool_df, "PJ") >= max(int(min_games), 0))
        & (_numeric_series(pool_df, "MINUTOS JUGADOS") >= max(float(min_minutes), 0.0))
    ].copy()

    if candidate_pool.empty:
        return {
            "target": target_row.to_dict(),
            "candidates": [],
        }

    resolved_weights = resolve_similarity_feature_weights(feature_weights)
    active_columns = [column for column, weight in resolved_weights.items() if weight > 0]
    reference_df = pd.concat([target_row.to_frame().T, candidate_pool], ignore_index=True)
    percentile_df = _percentile_frame(reference_df, active_columns)
    target_percentiles = percentile_df.iloc[0]
    candidate_percentiles = percentile_df.iloc[1:].reset_index(drop=True)
    candidate_pool = candidate_pool.reset_index(drop=True)

    weight_sum = sum(resolved_weights.values()) or 1.0
    weighted_distances: list[float] = []
    reasons_list: list[list[str]] = []
    differences_list: list[list[str]] = []

    for index, candidate in candidate_pool.iterrows():
        feature_scores: list[tuple[str, float]] = []
        distance_sum = 0.0
        for column, weight in resolved_weights.items():
            if weight <= 0:
                continue
            delta = float(candidate_percentiles.loc[index, column] - target_percentiles[column])
            impact = abs(delta) * weight
            feature_scores.append((column, impact))
            distance_sum += weight * (delta**2)

        distance = (distance_sum / weight_sum) ** 0.5
        weighted_distances.append(distance)

        sorted_by_similarity = sorted(feature_scores, key=lambda item: item[1])
        sorted_by_difference = sorted(feature_scores, key=lambda item: item[1], reverse=True)
        reasons_list.append(
            [_reason_text(column, target_row[column], candidate[column]) for column, _ in sorted_by_similarity[:3]]
        )
        differences_list.append(
            [_difference_text(column, target_row[column], candidate[column]) for column, _ in sorted_by_difference[:2]]
        )

    candidate_pool["similarityScore"] = [round(max(0.0, (1.0 - distance) * 100.0), 2) for distance in weighted_distances]
    candidate_pool["reasons"] = reasons_list
    candidate_pool["differences"] = differences_list

    candidate_pool = candidate_pool.sort_values(
        by=["similarityScore", "PJ", "MINUTOS JUGADOS"],
        ascending=[False, False, False],
        na_position="last",
    ).head(limit)

    return {
        "target": target_row.to_dict(),
        "candidates": candidate_pool.to_dict(orient="records"),
    }
