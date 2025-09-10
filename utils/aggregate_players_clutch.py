# -*- coding: utf-8 -*-
"""
Aggregación por jugador *con equipo* desde el Excel de temporada (per-game)
- Recalcula PTS = 3PM*3 + (FGM-3PM)*2 + FTM
- Recalcula eFG% y TS% por partido
- Agrega por (EQUIPO, JUGADOR) en toda la temporada:
    * Sumas de contadores
    * USG% y NET_RTG como medias ponderadas por MIN_CLUTCH
    * eFG% y TS% recomputadas desde los totales agregados
- Guarda una sola hoja: 'by_player' (con EQUIPO)

Uso:
    python aggregate_clutch_by_player.py --in ./data/clutch_season_report.xlsx --out ./data/clutch_by_player.xlsx
"""

import os
import argparse
import pandas as pd
import numpy as np

REQ_NUM_COLS = [
    "FGA","FGM","3PA","3PM","FTA","FTM","MIN_CLUTCH",
    # opcionales:
    "PTS","AST","TO","STL","REB","REB_O","REB_D","USG%","PLUS_MINUS","NET_RTG"
]

def _to_num(s):
    return pd.to_numeric(s, errors="coerce")

def weighted_mean(series, weights):
    s = _to_num(series)
    w = _to_num(weights)
    mask = (s.notna()) & (w.notna()) & (w > 0)
    if not mask.any():
        return np.nan
    return (s[mask] * w[mask]).sum() / w[mask].sum()

def load_excel(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo: {path}")
    return pd.read_excel(path)

def ensure_columns(df):
    for c in ["EQUIPO","JUGADOR"]:
        if c not in df.columns:
            raise ValueError(f"Falta columna clave: '{c}'")

    # numéricas requeridas (crea a 0 si faltan)
    for c in REQ_NUM_COLS:
        if c not in df.columns:
            df[c] = 0
        df[c] = _to_num(df[c])

    # limpia posibles columnas antiguas
    for old in ["eFG%_old","TS%_old","PTS_delta"]:
        if old in df.columns:
            df.drop(columns=[old], inplace=True)

    return df

def recalc_counts_and_rates_per_game(df):
    fgm = _to_num(df["FGM"]).fillna(0)
    tpm = _to_num(df["3PM"]).fillna(0)
    ftm = _to_num(df["FTM"]).fillna(0)
    fga = _to_num(df["FGA"]).fillna(0)
    fta = _to_num(df["FTA"]).fillna(0)

    # Puntos inferidos
    twos_made = (fgm - tpm).clip(lower=0)
    df["PTS"] = (tpm * 3 + twos_made * 2 + ftm).astype(float)

    # eFG% y TS% por partido
    df["eFG%"] = (fgm + 0.5 * tpm) / fga.replace(0, np.nan)
    df["TS%"]  = df["PTS"] / (2.0 * (fga + 0.44 * fta).replace(0, np.nan))
    return df

def aggregate_by_team_player(df):
    # Sumas por (EQUIPO, JUGADOR)
    group_cols = ["EQUIPO","JUGADOR"]
    sum_cols = ["MIN_CLUTCH","PTS","FGA","FGM","3PA","3PM","FTA","FTM",
                "AST","TO","STL","REB","REB_O","REB_D","PLUS_MINUS"]
    existing_sum = [c for c in sum_cols if c in df.columns]

    g = df.groupby(group_cols, dropna=False)
    out = g[existing_sum].sum().reset_index()
    out["GAMES"] = g.size().values

    # Medias ponderadas por MIN_CLUTCH
    for col in ["USG%","NET_RTG"]:
        if col in df.columns:
            out[col] = g.apply(lambda x: weighted_mean(x[col], x["MIN_CLUTCH"])).values

    # Recalcular eFG% y TS% desde TOTALES
    fgm = _to_num(out["FGM"]).fillna(0)
    tpm = _to_num(out["3PM"]).fillna(0)
    fga = _to_num(out["FGA"]).fillna(0)
    fta = _to_num(out["FTA"]).fillna(0)
    pts = _to_num(out["PTS"]).fillna(0)

    out["eFG%"] = (fgm + 0.5 * tpm) / fga.replace(0, np.nan)
    out["TS%"]  = pts / (2.0 * (fga + 0.44 * fta).replace(0, np.nan))

    # Orden de columnas
    desired = ["EQUIPO","JUGADOR","GAMES","MIN_CLUTCH","PTS","FGA","FGM","3PA","3PM","FTA","FTM",
               "eFG%","TS%","AST","TO","STL","REB","REB_O","REB_D","USG%","PLUS_MINUS","NET_RTG"]
    cols = [c for c in desired if c in out.columns] + [c for c in out.columns if c not in desired]
    return out[cols]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Excel fuente (per-game de todos los partidos)")
    ap.add_argument("--out", dest="out_path", required=True, help="Excel destino con hoja 'by_player'")
    args = ap.parse_args()

    df = load_excel(args.in_path)
    df = ensure_columns(df)
    df = recalc_counts_and_rates_per_game(df)

    by_player = aggregate_by_team_player(df)

    os.makedirs(os.path.dirname(args.out_path) or ".", exist_ok=True)
    with pd.ExcelWriter(args.out_path, engine="openpyxl") as xw:
        by_player.to_excel(xw, index=False, sheet_name="by_player")

    print(f"[OK] Guardado: {args.out_path}")
    print(f" - by_player: {len(by_player)} filas (una por EQUIPO-JUGADOR)")

if __name__ == "__main__":
    main()
