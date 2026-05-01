from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

COLOR_INK = "#10263f"
COLOR_MUTED = "#425466"
COLOR_SOFT = "#f8fafc"
COLOR_LINE = "#d0d7de"
COLOR_ACCENT = "#f97316"

CONTEXT_METRIC_SPECS = [
    ("PJ", "PJ"),
    ("WIN_PCT", "% victorias"),
    ("PTS_FOR", "PTS +"),
    ("PTS_AGAINST", "PTS -"),
    ("OFFRTG", "OFFRTG"),
    ("DEFRTG", "DEFRTG"),
    ("NETRTG", "NETRTG"),
    ("AST", "AST"),
    ("TURNOVERS", "PERDIDAS"),
    ("T2_PCT", "%T2"),
    ("T3_PCT", "%T3"),
    ("FT_PCT", "%TL"),
    ("OREB_PCT", "%OREB"),
    ("DREB_PCT", "%DREB"),
    ("REB_PCT", "%REB"),
]

CLUTCH_METRIC_SPECS = [
    ("GAMES", "PJ clutch"),
    ("PTS", "PTS prom."),
    ("FGA", "FGA prom."),
    ("EFG_PCT", "eFG%"),
    ("THREE_PA", "3PA prom."),
    ("FTA", "FTA prom."),
    ("NET_RTG", "NETRTG"),
]


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _safe_pct(numerator: float, denominator: float) -> float:
    return (numerator / denominator * 100.0) if denominator else 0.0


def _safe_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").fillna(0.0).mean())


def _format_value(metric_key: str, value: Any) -> str:
    numeric = float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0])
    if metric_key in {"PJ", "GAMES"}:
        return str(int(round(numeric)))
    if metric_key.endswith("_PCT") or metric_key == "WIN_PCT":
        return f"{numeric:.1f}%"
    return f"{numeric:.1f}"


def _format_count(value: Any) -> str:
    numeric = float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0])
    return str(int(round(numeric)))


def _format_player_metric(value: Any) -> str:
    numeric = float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0])
    return f"{numeric:.1f}"


def _format_dorsal(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    numeric = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.notna(numeric) and float(numeric).is_integer():
        text = str(int(numeric))
    return f"#{text}"


def _player_label(name: Any, dorsal: Any = None) -> str:
    dorsal_text = _format_dorsal(dorsal)
    name_text = str(name or "-")
    return f"{dorsal_text} {name_text}" if dorsal_text else name_text


def _clutch_points_series(frame: pd.DataFrame) -> pd.Series:
    if {"FGM", "3PM", "FTM"}.issubset(frame.columns):
        return 2 * _numeric_series(frame, "FGM") + _numeric_series(frame, "3PM") + _numeric_series(frame, "FTM")
    return _numeric_series(frame, "PTS")


def _player_plays(frame: pd.DataFrame) -> pd.Series:
    return _numeric_series(frame, "T2 INTENTADO") + _numeric_series(frame, "T3 INTENTADO") + 0.44 * _numeric_series(frame, "TL INTENTADOS") + _numeric_series(frame, "PERDIDAS")


def _prepare_team_games(team_name: str, games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return pd.DataFrame()
    frame = games_df[games_df["EQUIPO LOCAL"].astype(str) == str(team_name)].copy()
    if frame.empty:
        return frame
    frame["PID"] = pd.to_numeric(frame.get("PID"), errors="coerce")
    frame["WIN"] = _numeric_series(frame, "PUNTOS") > _numeric_series(frame, "PTS_RIVAL")
    frame["RESULT_SPLIT"] = frame["WIN"].map({True: "Victoria", False: "Derrota"})
    home_series = frame["IS_HOME"] if "IS_HOME" in frame.columns else pd.Series(pd.NA, index=frame.index)
    frame["HOME_AWAY_SPLIT"] = home_series.map({True: "Local", False: "Visitante"}).fillna("Sin dato")
    frame["T2_PCT"] = _safe_pct_series(frame, "T2 CONVERTIDO", "T2 INTENTADO")
    frame["T3_PCT"] = _safe_pct_series(frame, "T3 CONVERTIDO", "T3 INTENTADO")
    frame["FT_PCT"] = _safe_pct_series(frame, "TL CONVERTIDOS", "TL INTENTADOS")
    frame["OREB_PCT"] = _numeric_series(frame, "%OREB") * 100.0
    frame["DREB_PCT"] = _numeric_series(frame, "%DREB") * 100.0
    frame["REB_PCT"] = _numeric_series(frame, "%REB") * 100.0
    return frame


def _safe_pct_series(df: pd.DataFrame, made_column: str, att_column: str) -> pd.Series:
    made = _numeric_series(df, made_column)
    attempted = _numeric_series(df, att_column).replace(0, pd.NA)
    return (made / attempted).fillna(0.0) * 100.0


def _build_context_row(split_frame: pd.DataFrame, split_label: str) -> dict[str, float | str]:
    games = int(split_frame["PID"].nunique()) if "PID" in split_frame.columns else int(len(split_frame.index))
    t2_attempted = float(_numeric_series(split_frame, "T2 INTENTADO").sum())
    t3_attempted = float(_numeric_series(split_frame, "T3 INTENTADO").sum())
    ft_attempted = float(_numeric_series(split_frame, "TL INTENTADOS").sum())
    return {
        "SPLIT": split_label,
        "PJ": games,
        "WIN_PCT": _safe_pct(float(split_frame["WIN"].sum()) if "WIN" in split_frame.columns else 0.0, games),
        "PTS_FOR": _safe_mean(_numeric_series(split_frame, "PUNTOS")),
        "PTS_AGAINST": _safe_mean(_numeric_series(split_frame, "PTS_RIVAL")),
        "OFFRTG": _safe_mean(_numeric_series(split_frame, "OFFRTG")),
        "DEFRTG": _safe_mean(_numeric_series(split_frame, "DEFRTG")),
        "NETRTG": _safe_mean(_numeric_series(split_frame, "NETRTG")),
        "AST": _safe_mean(_numeric_series(split_frame, "ASISTENCIAS")),
        "TURNOVERS": _safe_mean(_numeric_series(split_frame, "PERDIDAS")),
        "T2_PCT": _safe_pct(float(_numeric_series(split_frame, "T2 CONVERTIDO").sum()), t2_attempted),
        "T3_PCT": _safe_pct(float(_numeric_series(split_frame, "T3 CONVERTIDO").sum()), t3_attempted),
        "FT_PCT": _safe_pct(float(_numeric_series(split_frame, "TL CONVERTIDOS").sum()), ft_attempted),
        "OREB_PCT": _safe_mean(_numeric_series(split_frame, "OREB_PCT")),
        "DREB_PCT": _safe_mean(_numeric_series(split_frame, "DREB_PCT")),
        "REB_PCT": _safe_mean(_numeric_series(split_frame, "REB_PCT")),
    }


def _build_split_leaders(team_name: str, split_games: pd.DataFrame, boxscores_df: pd.DataFrame, split_label: str) -> dict[str, str]:
    if split_games.empty or boxscores_df.empty:
        return {
            "SPLIT": split_label,
            "MINUTOS": "-",
            "PUNTOS": "-",
            "PLAYS": "-",
        }

    split_ids = split_games["PID"].dropna().astype(int).tolist()
    if not split_ids:
        return {
            "SPLIT": split_label,
            "MINUTOS": "-",
            "PUNTOS": "-",
            "PLAYS": "-",
        }

    team_boxscores = boxscores_df[
        (boxscores_df["EQUIPO LOCAL"].astype(str) == str(team_name))
        & (pd.to_numeric(boxscores_df["IdPartido"], errors="coerce").fillna(-1).astype(int).isin(split_ids))
    ].copy()
    if team_boxscores.empty:
        return {
            "SPLIT": split_label,
            "MINUTOS": "-",
            "PUNTOS": "-",
            "PLAYS": "-",
        }

    team_boxscores["PLAYS"] = _player_plays(team_boxscores)
    if "DORSAL" not in team_boxscores.columns:
        team_boxscores["DORSAL"] = ""
    team_boxscores["DORSAL"] = team_boxscores["DORSAL"].fillna("")
    grouped = (
        team_boxscores.groupby(["PLAYER_KEY", "JUGADOR", "DORSAL"], as_index=False)
        .agg(
            {
                "IdPartido": pd.Series.nunique,
                "MINUTOS JUGADOS": "mean",
                "PUNTOS": "mean",
                "PLAYS": "mean",
            }
        )
        .rename(columns={"IdPartido": "PJ"})
    )
    if grouped.empty:
        return {
            "SPLIT": split_label,
            "MINUTOS": "-",
            "PUNTOS": "-",
            "PLAYS": "-",
        }

    def _leader_text(column: str) -> str:
        leader = grouped.sort_values(by=[column, "PJ"], ascending=[False, False], na_position="last").iloc[0]
        return f"{_player_label(leader['JUGADOR'], leader.get('DORSAL'))} ({_format_player_metric(leader[column])})"

    return {
        "SPLIT": split_label,
        "MINUTOS": _leader_text("MINUTOS JUGADOS"),
        "PUNTOS": _leader_text("PUNTOS"),
        "PLAYS": _leader_text("PLAYS"),
    }


def build_context_split_payload(team_name: str, games_df: pd.DataFrame, boxscores_df: pd.DataFrame, split_mode: str) -> dict[str, Any]:
    prepared_games = _prepare_team_games(team_name, games_df)
    if split_mode == "home_away":
        split_column = "HOME_AWAY_SPLIT"
        labels = ["Local", "Visitante"]
        title = "Local vs Visitante"
        subtitle = "Metricas de equipo por partido; porcentajes y ratings agregados del split."
        metric_specs = CONTEXT_METRIC_SPECS
    else:
        split_column = "RESULT_SPLIT"
        labels = ["Victoria", "Derrota"]
        title = "Victoria vs Derrota"
        subtitle = "Metricas de equipo por partido cuando gana y cuando pierde."
        metric_specs = [metric for metric in CONTEXT_METRIC_SPECS if metric[0] != "WIN_PCT"]

    rows: list[dict[str, Any]] = []
    leaders: list[dict[str, str]] = []
    for label in labels:
        split_frame = prepared_games[prepared_games[split_column] == label].copy()
        rows.append(_build_context_row(split_frame, label))
        leaders.append(_build_split_leaders(team_name, split_frame, boxscores_df, label))

    return {
        "title": title,
        "subtitle": subtitle,
        "metricSpecs": metric_specs,
        "rows": rows,
        "leaders": leaders,
    }


def _prepare_clutch_games(team_name: str, games_df: pd.DataFrame, clutch_games_df: pd.DataFrame) -> pd.DataFrame:
    if clutch_games_df.empty:
        return pd.DataFrame(columns=["IdPartido", "RESULT_SPLIT"])
    game_map = _prepare_team_games(team_name, games_df)[["PID", "RESULT_SPLIT"]].copy()
    if game_map.empty:
        return pd.DataFrame(columns=["IdPartido", "RESULT_SPLIT"])
    frame = clutch_games_df[clutch_games_df["EQUIPO"].astype(str) == str(team_name)].copy()
    if frame.empty:
        return pd.DataFrame(columns=["IdPartido", "RESULT_SPLIT"])
    frame["IdPartido"] = pd.to_numeric(frame.get("IdPartido"), errors="coerce")
    frame["PTS_CALC"] = _clutch_points_series(frame)
    return frame.merge(game_map, left_on="IdPartido", right_on="PID", how="left").drop(columns=["PID"], errors="ignore")


def _prepare_clutch_lineups(team_name: str, games_df: pd.DataFrame, clutch_lineups_df: pd.DataFrame) -> pd.DataFrame:
    if clutch_lineups_df.empty:
        return pd.DataFrame(columns=["PARTIDO_ID", "RESULT_SPLIT", "SEC_CLUTCH", "NET_RTG"])
    game_map = _prepare_team_games(team_name, games_df)[["PID", "RESULT_SPLIT"]].copy()
    if game_map.empty:
        return pd.DataFrame(columns=["PARTIDO_ID", "RESULT_SPLIT", "SEC_CLUTCH", "NET_RTG"])
    frame = clutch_lineups_df[clutch_lineups_df["EQUIPO"].astype(str) == str(team_name)].copy()
    if frame.empty:
        return pd.DataFrame(columns=["PARTIDO_ID", "RESULT_SPLIT", "SEC_CLUTCH", "NET_RTG"])
    frame["PARTIDO_ID"] = pd.to_numeric(frame.get("PARTIDO_ID"), errors="coerce")
    frame["SEC_CLUTCH"] = _numeric_series(frame, "SEC_CLUTCH")
    return frame.merge(game_map, left_on="PARTIDO_ID", right_on="PID", how="left").drop(columns=["PID"], errors="ignore")


def _build_clutch_summary_row(split_frame: pd.DataFrame, lineup_frame: pd.DataFrame, split_label: str) -> dict[str, float | str]:
    games = int(split_frame["IdPartido"].nunique()) if "IdPartido" in split_frame.columns else 0
    fga = float(_numeric_series(split_frame, "FGA").sum())
    fgm = float(_numeric_series(split_frame, "FGM").sum())
    three_pa = float(_numeric_series(split_frame, "3PA").sum())
    fta = float(_numeric_series(split_frame, "FTA").sum())
    points = float((_numeric_series(split_frame, "PTS_CALC") if "PTS_CALC" in split_frame.columns else _clutch_points_series(split_frame)).sum())
    net_rtg = 0.0
    if not lineup_frame.empty:
        game_level = (
            lineup_frame.groupby("PARTIDO_ID", as_index=False)
            .apply(
                lambda frame: pd.Series(
                    {
                        "NET_RTG": float(
                            (_numeric_series(frame, "NET_RTG") * _numeric_series(frame, "SEC_CLUTCH")).sum() / _numeric_series(frame, "SEC_CLUTCH").sum()
                        )
                        if _numeric_series(frame, "SEC_CLUTCH").sum()
                        else 0.0
                    }
                ),
                include_groups=False,
            )
        )
        if isinstance(game_level, pd.Series):
            game_level = game_level.to_frame().T
        net_rtg = _safe_mean(_numeric_series(game_level, "NET_RTG"))

    return {
        "SPLIT": split_label,
        "GAMES": games,
        "PTS": float(points / games) if games else 0.0,
        "FGA": float(fga / games) if games else 0.0,
        "EFG_PCT": _safe_pct(fgm + 0.5 * float(_numeric_series(split_frame, "3PM").sum()), fga),
        "THREE_PA": float(three_pa / games) if games else 0.0,
        "FTA": float(fta / games) if games else 0.0,
        "NET_RTG": net_rtg,
    }


def _build_clutch_shot_table(split_frame: pd.DataFrame, split_label: str, limit: int = 6) -> dict[str, Any]:
    if split_frame.empty:
        return {"title": split_label, "rows": []}

    frame = split_frame.copy()
    if "DORSAL" not in frame.columns:
        frame["DORSAL"] = ""
    frame["DORSAL"] = frame["DORSAL"].fillna("")
    frame["PTS_CALC"] = _numeric_series(frame, "PTS_CALC") if "PTS_CALC" in frame.columns else _clutch_points_series(frame)
    grouped = (
        frame.groupby(["PLAYER_KEY", "JUGADOR", "DORSAL"], as_index=False)
        .agg({"FGA": "sum", "FGM": "sum", "3PA": "sum", "FTA": "sum", "PTS_CALC": "sum"})
        .sort_values(by=["FGA", "PTS_CALC"], ascending=[False, False], na_position="last")
        .head(limit)
    )
    total_fga = float(_numeric_series(frame, "FGA").sum())
    rows = []
    for _, row in grouped.iterrows():
        player_fga = float(pd.to_numeric(pd.Series([row.get("FGA")]), errors="coerce").fillna(0.0).iloc[0])
        player_fgm = float(pd.to_numeric(pd.Series([row.get("FGM")]), errors="coerce").fillna(0.0).iloc[0])
        rows.append(
            {
                "JUGADOR": str(row.get("JUGADOR") or "-"),
                "DORSAL": _format_dorsal(row.get("DORSAL")),
                "PLAYER_LABEL": _player_label(row.get("JUGADOR"), row.get("DORSAL")),
                "FGA": player_fga,
                "SHOT_SHARE": _safe_pct(player_fga, total_fga),
                "FG_PCT": _safe_pct(player_fgm, player_fga),
                "THREE_PA": float(pd.to_numeric(pd.Series([row.get("3PA")]), errors="coerce").fillna(0.0).iloc[0]),
                "FTA": float(pd.to_numeric(pd.Series([row.get("FTA")]), errors="coerce").fillna(0.0).iloc[0]),
                "PTS": float(pd.to_numeric(pd.Series([row.get("PTS_CALC")]), errors="coerce").fillna(0.0).iloc[0]),
            }
        )
    return {"title": split_label, "rows": rows}


def build_clutch_split_payload(team_name: str, games_df: pd.DataFrame, clutch_games_df: pd.DataFrame, clutch_lineups_df: pd.DataFrame) -> dict[str, Any]:
    prepared_clutch = _prepare_clutch_games(team_name, games_df, clutch_games_df)
    prepared_lineups = _prepare_clutch_lineups(team_name, games_df, clutch_lineups_df)

    rows: list[dict[str, Any]] = []
    shot_tables: list[dict[str, Any]] = []
    for label in ["Victoria", "Derrota"]:
        clutch_split = prepared_clutch[prepared_clutch["RESULT_SPLIT"] == label].copy()
        lineup_split = prepared_lineups[prepared_lineups["RESULT_SPLIT"] == label].copy()
        rows.append(_build_clutch_summary_row(clutch_split, lineup_split, label))
        shot_tables.append(_build_clutch_shot_table(clutch_split, f"Tiros clutch en {label.lower()}"))

    return {
        "title": "Clutch y cierre",
        "subtitle": "Resumen de equipo en promedios por partido clutch; tablas de jugadores en totales del split.",
        "rows": rows,
        "shotTables": shot_tables,
    }


def _style_table(table, font_size: float = 10.0, scale_y: float = 1.6) -> None:
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.0, scale_y)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(COLOR_LINE)
        cell.set_linewidth(0.7)
        if row == 0:
            cell.set_facecolor(COLOR_INK)
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor(COLOR_SOFT if row % 2 == 0 else "white")


def _draw_page_header(axis, title: str, subtitle: str, team_name: str) -> None:
    axis.add_patch(plt.Rectangle((0.0, 0.16), 0.012, 0.68, color=COLOR_ACCENT, transform=axis.transAxes, clip_on=False))
    axis.text(0.03, 0.72, title, fontsize=25, fontweight="bold", color=COLOR_INK, va="center")
    axis.text(0.03, 0.3, f"{team_name} · {subtitle}", fontsize=12.5, color=COLOR_MUTED, va="center")


def build_team_context_page(team_name: str, payload: dict[str, Any], dpi: int = 180):
    fig = plt.figure(figsize=(16, 9), dpi=dpi)
    fig.patch.set_facecolor(COLOR_SOFT)
    grid = fig.add_gridspec(3, 1, height_ratios=[0.18, 0.5, 0.32])
    ax_title = fig.add_subplot(grid[0])
    ax_table = fig.add_subplot(grid[1])
    ax_leaders = fig.add_subplot(grid[2])

    for axis in (ax_title, ax_table, ax_leaders):
        axis.axis("off")

    _draw_page_header(ax_title, payload["title"], payload["subtitle"], team_name)

    split_labels = [row["SPLIT"] for row in payload["rows"]]
    metric_table_rows = []
    for metric_key, label in payload.get("metricSpecs", CONTEXT_METRIC_SPECS):
        metric_table_rows.append(
            [label, *[_format_value(metric_key, row.get(metric_key, 0.0)) for row in payload["rows"]]]
        )
    table = ax_table.table(
        cellText=metric_table_rows,
        colLabels=["Metrica", *split_labels],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    _style_table(table, font_size=9.5, scale_y=1.5)

    ax_leaders.set_title(
        "Lideres por split (promedios)",
        loc="left",
        fontsize=12,
        fontweight="bold",
        color=COLOR_INK,
        pad=8,
    )
    leader_rows = [
        [row["SPLIT"], row["MINUTOS"], row["PUNTOS"], row["PLAYS"]]
        for row in payload["leaders"]
    ]
    leader_table = ax_leaders.table(
        cellText=leader_rows,
        colLabels=["Split", "Lider minutos", "Lider puntos", "Lider plays"],
        loc="center",
        cellLoc="left",
        colLoc="center",
    )
    _style_table(leader_table, font_size=10.0, scale_y=1.8)
    fig.tight_layout()
    return fig


def build_team_clutch_page(team_name: str, payload: dict[str, Any], dpi: int = 180):
    fig = plt.figure(figsize=(16, 9), dpi=dpi)
    fig.patch.set_facecolor(COLOR_SOFT)
    grid = fig.add_gridspec(3, 2, height_ratios=[0.16, 0.34, 0.5], width_ratios=[1, 1])
    ax_title = fig.add_subplot(grid[0, :])
    ax_summary = fig.add_subplot(grid[1, :])
    ax_wins = fig.add_subplot(grid[2, 0])
    ax_losses = fig.add_subplot(grid[2, 1])

    for axis in (ax_title, ax_summary, ax_wins, ax_losses):
        axis.axis("off")

    _draw_page_header(ax_title, payload["title"], payload["subtitle"], team_name)

    summary_rows = []
    split_labels = [row["SPLIT"] for row in payload["rows"]]
    for metric_key, label in CLUTCH_METRIC_SPECS:
        summary_rows.append([label, *[_format_value(metric_key, row.get(metric_key, 0.0)) for row in payload["rows"]]])
    summary_table = ax_summary.table(
        cellText=summary_rows,
        colLabels=["Metrica", *split_labels],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    _style_table(summary_table, font_size=10.0, scale_y=1.7)

    for axis, shot_table in zip((ax_wins, ax_losses), payload["shotTables"]):
        axis.set_title(f"{shot_table['title']} | totales del split", loc="left", fontsize=14, fontweight="bold", color=COLOR_INK, pad=12)
        if not shot_table["rows"]:
            axis.text(0.02, 0.55, "Sin datos clutch suficientes en este split.", fontsize=11, color="#64748b")
            continue
        cell_text = [
            [
                row["PLAYER_LABEL"],
                _format_count(row["FGA"]),
                _format_value("SHOT_SHARE_PCT", row["SHOT_SHARE"]),
                _format_value("FG_PCT", row["FG_PCT"]),
                _format_count(row["THREE_PA"]),
                _format_count(row["FTA"]),
                _format_count(row["PTS"]),
            ]
            for row in shot_table["rows"]
        ]
        shot_table_render = axis.table(
            cellText=cell_text,
            colLabels=["Jugador", "FGA tot", "% tiros", "FG%", "3PA tot", "FTA tot", "PTS calc tot"],
            loc="center",
            cellLoc="left",
            colLoc="center",
            colWidths=[0.29, 0.10, 0.13, 0.11, 0.11, 0.11, 0.15],
        )
        _style_table(shot_table_render, font_size=8.4, scale_y=1.55)

    fig.tight_layout()
    return fig
