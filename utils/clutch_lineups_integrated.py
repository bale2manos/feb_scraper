# -*- coding: utf-8 -*-
"""
Clutch Lineups Integrado
=========================

Versión integrada del scrape_clutch_lineup.py para usar en la aplicación.
Extrae quintetos y sus estadísticas en momentos clutch.
"""

import sys
import os
import time
import logging
from typing import List, Dict, Tuple, Callable
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Importar scrapers necesarios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.scraper_all_games import scrape_all
from scrapers.scrape_clutch_lineup import lineups_for_game
from config import BASE_PLAY_URL

# Importar módulos de configuración para modificar variables globales
from utils import web_scraping
from scrapers import scraper_all_games

# Configuración
MAX_WORKERS = 2  # Reducido para evitar errores de conexión
MAX_RETRIES = 2

def setup_logging_clutch_lineups(log_file: str = "clutch_lineups.log") -> None:
    """Configura logging para el scraper de clutch lineups."""
    logger = logging.getLogger('clutch_lineups')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def scrape_one_game_lineups(game_meta: Tuple) -> pd.DataFrame:
    """
    Worker function: extrae lineups clutch de un partido específico.
    
    Args:
        game_meta: Tupla con (fase, jornada, pid, idequipo, local, rival, resultado)
    
    Returns:
        DataFrame con lineups clutch para ese partido
    """
    fase, jornada, pid, idequipo, local, rival, resultado = game_meta
    
    try:
        df = lineups_for_game(pid, retries=MAX_RETRIES, keep_snapshot=False)
        
        if df is not None and not df.empty:
            # Agregar metadatos del partido
            df.insert(1, "FASE", fase)
            df.insert(2, "JORNADA", jornada)
            df.insert(3, "LOCAL", local)
            df.insert(4, "RIVAL", rival)
            df.insert(5, "RESULTADO", resultado)
            
        return df
        
    except Exception as e:
        logger = logging.getLogger('clutch_lineups')
        logger.error(f"Error procesando partido {pid}: {str(e)}")
        return pd.DataFrame()

def main_clutch_lineups(output_file: str, progress_callback: Callable[[str, str], None] = None,
                       temporada: str = None, liga: str = None, fases: list = None) -> pd.DataFrame:
    """
    Función principal del scraper de clutch lineups.
    
    Args:
        output_file: Ruta del archivo de salida
        progress_callback: Función para reportar progreso (msg_type, message)
        temporada: Temporada específica (ej: "24_25")
        liga: Liga específica (ej: "primera_feb") 
        fases: Lista de fases específicas (ej: ["regular", "playoff"])
    
    Returns:
        DataFrame con los lineups clutch extraídos
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(output_file).parent / "clutch_lineups.log")
    setup_logging_clutch_lineups(log_file)
    logger = logging.getLogger('clutch_lineups')
    
    progress_callback("info", "🔥👥 Iniciando extracción de clutch lineups")
    logger.info("Starting clutch lineups scraper")
    
    # Obtener lista de partidos (usando configuración global del scraper_app)
    progress_callback("info", "📋 Obteniendo lista de partidos...")
    logger.info(f"Using current global config: temporada={web_scraping.TEMPORADA_TXT}, fases={scraper_all_games.PHASES}")
    games = scrape_all()
    
    # Filtrar partidos únicos por ID
    unique_games = {}
    for game in games:
        pid = game[2]
        if pid not in unique_games:
            unique_games[pid] = game
    
    game_metas = list(unique_games.values())
    
    progress_callback("info", f"🎯 Procesando {len(game_metas)} partidos únicos")
    logger.info(f"Processing {len(game_metas)} unique games")
    
    all_dfs: List[pd.DataFrame] = []
    
    # Procesamiento paralelo
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(scrape_one_game_lineups, meta): meta[2] for meta in game_metas}
        completed = 0
        
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    all_dfs.append(df)
                    completed += 1
                    progress_callback("info", f"👥 Partido {completed}/{len(game_metas)} procesado: {len(df)} lineups")
                    logger.info(f"[{pid}] done, got {len(df)} lineups")
                else:
                    completed += 1
                    progress_callback("info", f"👥 Partido {completed}/{len(game_metas)} procesado: sin lineups clutch")
                    logger.info(f"[{pid}] no clutch lineups found")
                
            except Exception as e:
                logger.error(f"[{pid}] crashed: {e!r}")
                progress_callback("error", f"❌ Error procesando partido {pid}: {str(e)}")
    
    # Combinar todos los DataFrames
    if not all_dfs:
        progress_callback("error", "❌ No se obtuvieron lineups de ningún partido")
        logger.error("No lineups obtained from any game")
        return pd.DataFrame()
    
    progress_callback("info", "📊 Agregando datos de todos los partidos...")
    df_all = pd.concat(all_dfs, ignore_index=True)
    
    # Agregar por equipo y lineup
    progress_callback("info", "🔄 Agregando lineups por equipo...")
    grp_cols = ["EQUIPO", "LINEUP", "N_JUG"]
    sum_cols = [
        "SEC_CLUTCH", "POINTS_FOR", "POINTS_AGAINST",
        "FGA_on", "FTA_on", "TO_on", "ORB_on",
        "OPP_FGA_on", "OPP_FTA_on", "OPP_TO_on", "OPP_ORB_on"
    ]
    
    df_agg = df_all.groupby(grp_cols, dropna=False)[sum_cols].sum().reset_index()
    
    # Recalcular métricas desde totales agregados
    df_agg["MIN_CLUTCH"] = df_agg["SEC_CLUTCH"] / 60.0
    df_agg["OFF_POSSESSIONS"] = (
        df_agg["FGA_on"] - df_agg["ORB_on"] + 
        df_agg["TO_on"] + 0.44 * df_agg["FTA_on"]
    )
    df_agg["DEF_POSSESSIONS"] = (
        df_agg["OPP_FGA_on"] - df_agg["OPP_ORB_on"] + 
        df_agg["OPP_TO_on"] + 0.44 * df_agg["OPP_FTA_on"]
    )
    
    # Ratings ofensivo y defensivo
    df_agg["OFF_RTG"] = (
        100.0 * df_agg["POINTS_FOR"] / df_agg["OFF_POSSESSIONS"]
    ).where(df_agg["OFF_POSSESSIONS"] > 0)
    
    df_agg["DEF_RTG"] = (
        100.0 * df_agg["POINTS_AGAINST"] / df_agg["DEF_POSSESSIONS"]
    ).where(df_agg["DEF_POSSESSIONS"] > 0)
    
    df_agg["NET_RTG"] = df_agg["OFF_RTG"] - df_agg["DEF_RTG"]
    
    # Filtrar quintetos con al menos 1 minuto y 5 jugadores
    df_filtered = df_agg[
        (df_agg["SEC_CLUTCH"] >= 60) &  # Mínimo 1 minuto
        (df_agg["N_JUG"] == 5)          # Solo quintetos completos
    ].copy()
    
    # Ordenar por NET_RTG dentro de cada equipo
    df_filtered = df_filtered.sort_values(
        ["EQUIPO", "NET_RTG", "MIN_CLUTCH"], 
        ascending=[True, False, False]
    )
    
    # Guardar archivo con una hoja por equipo
    progress_callback("info", "💾 Guardando archivo final...")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for team, df_team in df_filtered.groupby("EQUIPO", dropna=False):
            sheet_name = (team[:28] or "Equipo") if team else "Sin_Equipo"
            df_team.to_excel(writer, index=False, sheet_name=sheet_name)
    
    progress_callback("success", f"✅ Clutch lineups extraídos: {len(df_filtered)} quintetos")
    progress_callback("info", f"📊 Equipos: {df_filtered['EQUIPO'].nunique()}")
    logger.info(f"Saved {len(df_filtered)} lineups from {df_filtered['EQUIPO'].nunique()} teams to {output_file}")
    
    return df_filtered

if __name__ == "__main__":
    # Test independiente
    output_file = "./data/clutch_lineups_test.xlsx"
    df = main_clutch_lineups(output_file)
    print(f"✅ Test completado: {len(df)} lineups en {output_file}")