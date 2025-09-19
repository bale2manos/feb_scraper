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
    "FGA","FGM","3PA","3PM","FTA","FTM","MIN_CLUTCH","MINUTOS_CLUTCH","SEGUNDOS_CLUTCH",
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

    # Mapear nombres de columnas de clutch_data a formato esperado
    column_mapping = {
        "MINUTOS_CLUTCH": "MIN_CLUTCH",
        "SEGUNDOS_CLUTCH": "SEGUNDOS_CLUTCH",  # Este ya está bien
        # Añadir más mapeos si es necesario
    }
    
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns and new_name not in df.columns:
            df[new_name] = df[old_name]
            print(f"[INFO] Mapeando {old_name} -> {new_name}")
        elif old_name in df.columns and old_name != new_name:
            # Si el nombre ya existe pero es diferente, usar el original
            print(f"[INFO] Usando columna original: {old_name}")
            if new_name not in df.columns:
                df[new_name] = df[old_name]

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
    
    # Determinar qué columnas de tiempo tenemos disponibles
    time_cols = []
    if "MIN_CLUTCH" in df.columns:
        time_cols.append("MIN_CLUTCH")
    if "MINUTOS_CLUTCH" in df.columns:
        time_cols.append("MINUTOS_CLUTCH")
    if "SEGUNDOS_CLUTCH" in df.columns:
        time_cols.append("SEGUNDOS_CLUTCH")
    
    # Incluir todas las columnas de tiempo disponibles en la agregación
    sum_cols = time_cols + ["PTS","FGA","FGM","3PA","3PM","FTA","FTM",
                           "AST","TO","STL","REB","REB_O","REB_D","PLUS_MINUS"]
    existing_sum = [c for c in sum_cols if c in df.columns]

    g = df.groupby(group_cols, dropna=False)
    out = g[existing_sum].sum().reset_index()
    out["GAMES"] = g.size().values

    # Determinar cuál usar como columna principal de minutos para pesos
    weight_col = None
    if "MIN_CLUTCH" in out.columns:
        weight_col = "MIN_CLUTCH"
    elif "MINUTOS_CLUTCH" in out.columns:
        weight_col = "MINUTOS_CLUTCH"
        # Crear también MIN_CLUTCH para compatibilidad interna
        out["MIN_CLUTCH"] = out["MINUTOS_CLUTCH"]
    
    # Si tenemos SEGUNDOS_CLUTCH, recalcular minutos desde los segundos agregados (más preciso)
    if "SEGUNDOS_CLUTCH" in out.columns:
        if "MINUTOS_CLUTCH" in out.columns:
            out["MINUTOS_CLUTCH"] = out["SEGUNDOS_CLUTCH"] / 60.0
        if "MIN_CLUTCH" in out.columns:
            out["MIN_CLUTCH"] = out["SEGUNDOS_CLUTCH"] / 60.0
        print(f"[INFO] Recalculando minutos desde {out['SEGUNDOS_CLUTCH'].sum():.1f} segundos agregados")
        weight_col = "MIN_CLUTCH" if "MIN_CLUTCH" in out.columns else "MINUTOS_CLUTCH"

    # Medias ponderadas por minutos clutch
    if weight_col:
        for col in ["USG%","NET_RTG"]:
            if col in df.columns:
                out[col] = g.apply(lambda x: weighted_mean(x[col], x[weight_col] if weight_col in x.columns else x.get("MINUTOS_CLUTCH", x.get("MIN_CLUTCH", 0)))).values

    # Recalcular eFG% y TS% desde TOTALES
    fgm = _to_num(out["FGM"]).fillna(0)
    tpm = _to_num(out["3PM"]).fillna(0)
    fga = _to_num(out["FGA"]).fillna(0)
    fta = _to_num(out["FTA"]).fillna(0)
    pts = _to_num(out["PTS"]).fillna(0)

    out["eFG%"] = (fgm + 0.5 * tpm) / fga.replace(0, np.nan)
    out["TS%"]  = pts / (2.0 * (fga + 0.44 * fta).replace(0, np.nan))

    # Orden de columnas (flexible para ambos formatos)
    desired = ["EQUIPO","JUGADOR","GAMES","MIN_CLUTCH","MINUTOS_CLUTCH","SEGUNDOS_CLUTCH","PTS","FGA","FGM","3PA","3PM","FTA","FTM",
               "eFG%","TS%","AST","TO","STL","REB","REB_O","REB_D","USG%","PLUS_MINUS","NET_RTG"]
    cols = [c for c in desired if c in out.columns] + [c for c in out.columns if c not in desired]
    return out[cols]

def aggregate_clutch_from_file(
    input_path: str,
    output_path: str,
    progress_callback=None
):
    """
    Función wrapper para agregar estadísticas clutch desde clutch_data para la app.
    
    Args:
        input_path: Ruta del archivo clutch_data.xlsx
        output_path: Ruta donde guardar el archivo clutch_aggregated.xlsx
        progress_callback: Función para reportar progreso
    
    Returns:
        DataFrame con las estadísticas clutch agregadas por jugador
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    try:
        progress_callback("info", f"📊 Agregando clutch desde: {os.path.basename(input_path)}")
        
        # Verificar que existe el archivo fuente
        if not os.path.exists(input_path):
            progress_callback("warning", f"⚠️ No existe archivo clutch_data: {input_path}")
            return pd.DataFrame()
        
        # Cargar y procesar datos
        df = load_excel(input_path)
        
        if df.empty:
            progress_callback("warning", f"⚠️ Archivo clutch_data está vacío")
            return pd.DataFrame()
        
        progress_callback("info", f"📈 Procesando {len(df)} registros de clutch per-game")
        
        df = ensure_columns(df)
        df = recalc_counts_and_rates_per_game(df)
        
        # Agregar por jugador
        by_player = aggregate_by_team_player(df)
        
        # Guardar archivo
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with pd.ExcelWriter(output_path, engine="openpyxl") as xw:
            by_player.to_excel(xw, index=False, sheet_name="by_player")
        
        progress_callback("success", f"✅ Clutch agregado guardado: {os.path.basename(output_path)}")
        progress_callback("info", f"📊 {len(by_player)} jugadores únicos agregados")
        
        return by_player
        
    except Exception as e:
        progress_callback("error", f"❌ Error agregando clutch: {str(e)}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


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
