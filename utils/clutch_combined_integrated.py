# -*- coding: utf-8 -*-
"""
Clutch Combined Integrated
==========================

Módulo optimizado que extrae clutch data Y clutch lineups en una sola pasada
para evitar abrir los partidos dos veces. Combina las funcionalidades de:
- total_clutch_integrated.py (clutch data/stats)
- clutch_lineups_integrated.py (clutch lineups/quintetos)
"""

import sys
import os
import time
import logging
from typing import List, Dict, Tuple, Callable, Optional
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Importar scrapers necesarios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.scraper_all_games import scrape_all
from scrapers.scraper_minutes_clutch import run_scrape_and_parse
from scrapers.scrape_clutch_lineup import lineups_for_game

# Importar módulos de configuración para modificar variables globales
from utils import web_scraping
from scrapers import scraper_all_games

# Configuración
MAX_WORKERS = 2  # Reducido para evitar errores de conexión
MAX_RETRIES = 2
INITIAL_BACKOFF = 2

def setup_logging_clutch_combined(log_file: str = "clutch_combined.log") -> None:
    """Configura logging para el scraper combinado de clutch."""
    logger = logging.getLogger('clutch_combined')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def scrape_one_game_clutch_combined(game_meta: Tuple) -> Tuple[List[Dict], pd.DataFrame]:
    """
    Worker function: extrae AMBOS clutch data Y clutch lineups de un partido.
    
    Args:
        game_meta: Tupla con (fase, jornada, pid, idequipo, local, rival, resultado)
    
    Returns:
        Tupla con (clutch_data_records, clutch_lineups_df)
    """
    phase, jornada, pid, idequipo, local, rival, resultado = game_meta
    
    clutch_data_records = []
    clutch_lineups_df = pd.DataFrame()
    game_str = f"{local} vs {rival}"
    
    logger = logging.getLogger('clutch_combined')
    
    for attempt in range(1, MAX_RETRIES+1):
        try:
            logger.info(f"[{pid}] Extrayendo clutch data y lineups (intento {attempt}/{MAX_RETRIES})")
            
            # === PARTE 1: CLUTCH DATA ===
            # run_scrape_and_parse maneja su propio driver y devuelve DataFrame
            clutch_df = run_scrape_and_parse(pid)
            
            # Convertir DataFrame a lista de diccionarios con metadatos del partido
            for _, row in clutch_df.iterrows():
                clutch_data_records.append({
                    "FASE": phase,
                    "JORNADA": jornada,
                    "GAME": game_str,
                    "JUGADOR": row.get("PLAYER", ""),
                    "EQUIPO": row.get("TEAM", ""),
                    "MINUTOS_CLUTCH": row.get("MINUTES", 0),
                    "PUNTOS_CLUTCH": row.get("POINTS", 0),
                    "REBOTES_CLUTCH": row.get("REBOUNDS", 0),
                    "ASISTENCIAS_CLUTCH": row.get("ASSISTS", 0),
                    "FG_MADE_CLUTCH": row.get("FG_MADE", 0),
                    "FG_ATT_CLUTCH": row.get("FG_ATT", 0),
                    "FT_MADE_CLUTCH": row.get("FT_MADE", 0),
                    "FT_ATT_CLUTCH": row.get("FT_ATT", 0),
                    "T3_MADE_CLUTCH": row.get("T3_MADE", 0),
                    "T3_ATT_CLUTCH": row.get("T3_ATT", 0),
                })
            
            # === PARTE 2: CLUTCH LINEUPS ===
            # lineups_for_game maneja su propio driver y devuelve DataFrame
            lineups_df = lineups_for_game(pid)
            
            # Añadir metadatos del partido al DataFrame de lineups
            if not lineups_df.empty:
                lineups_df = lineups_df.copy()
                lineups_df['FASE'] = phase
                lineups_df['JORNADA'] = jornada
                lineups_df['GAME'] = game_str
                lineups_df['PARTIDO_ID'] = pid
                
                clutch_lineups_df = lineups_df
            
            logger.info(f"[{pid}] ✅ Completado: {len(clutch_data_records)} registros clutch, {len(clutch_lineups_df)} lineups")
            break
            
        except Exception as e:
            logger.warning(f"[{pid}] attempt {attempt}/{MAX_RETRIES} failed: {e!r}")
            if attempt == MAX_RETRIES:
                logger.error(f"[{pid}] giving up.")
                clutch_data_records = []
                clutch_lineups_df = pd.DataFrame()
                break
            time.sleep(INITIAL_BACKOFF * (2 ** (attempt-1)))
    
    return clutch_data_records, clutch_lineups_df

def main_clutch_combined(
    clutch_data_output: str, 
    clutch_lineups_output: str, 
    progress_callback: Callable[[str, str], None] = None,
    temporada: str = None, 
    liga: str = None, 
    fases: list = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Función principal del scraper combinado de clutch.
    
    Args:
        clutch_data_output: Ruta del archivo de salida para clutch data
        clutch_lineups_output: Ruta del archivo de salida para clutch lineups
        progress_callback: Función para reportar progreso (msg_type, message)
        temporada: Temporada específica (ej: "2024/2025")
        liga: Liga específica (ej: "Primera FEB") 
        fases: Lista de fases específicas (ej: ["Liga Regular "B-A""])
    
    Returns:
        Tupla con (clutch_data_df, clutch_lineups_df)
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(clutch_data_output).parent / "clutch_combined.log")
    setup_logging_clutch_combined(log_file)
    logger = logging.getLogger('clutch_combined')
    
    progress_callback("info", "🔥👥 Iniciando extracción COMBINADA de clutch data + lineups")
    logger.info("Starting combined clutch data + lineups scraper")
    
    # Configurar parámetros globales si se proporcionan
    if temporada:
        original_temporada = web_scraping.TEMPORADA_TXT
        web_scraping.TEMPORADA_TXT = temporada
        progress_callback("info", f"📅 Configurando temporada: {temporada}")
        logger.info(f"Setting temporada to: {temporada}")
    
    if fases:
        original_phases = scraper_all_games.PHASES
        scraper_all_games.PHASES = fases
        progress_callback("info", f"🎯 Configurando fases: {len(fases)} fases seleccionadas")
        logger.info(f"Setting phases to: {fases}")
    
    # Obtener lista de partidos (usando configuración actualizada)
    progress_callback("info", "📋 Obteniendo lista de partidos...")
    logger.info(f"Using config: temporada={web_scraping.TEMPORADA_TXT}, fases={scraper_all_games.PHASES}")
    games = scrape_all()
    
    # Filtrar partidos únicos por ID
    unique_games = {}
    for game in games:
        pid = game[2]
        if pid not in unique_games:
            unique_games[pid] = game
    
    game_metas = list(unique_games.values())
    
    progress_callback("info", f"🎯 Procesando {len(game_metas)} partidos únicos (OPTIMIZADO: 1 visita por partido)")
    logger.info(f"Processing {len(game_metas)} unique games - OPTIMIZED: single visit per game")
    
    all_clutch_data: List[Dict] = []
    all_clutch_lineups: List[pd.DataFrame] = []
    
    # Procesamiento paralelo
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(scrape_one_game_clutch_combined, meta): meta[2] for meta in game_metas}
        completed = 0
        
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                clutch_data_records, clutch_lineups_df = fut.result()
                
                # Acumular resultados
                all_clutch_data.extend(clutch_data_records)
                if not clutch_lineups_df.empty:
                    all_clutch_lineups.append(clutch_lineups_df)
                
                completed += 1
                progress = int((completed / len(game_metas)) * 100)
                progress_callback("info", f"⚡ Progreso: {completed}/{len(game_metas)} partidos ({progress}%)")
                
            except Exception as e:
                logger.error(f"Error procesando partido {pid}: {str(e)}")
                progress_callback("warning", f"⚠️ Error en partido {pid}: {str(e)}")
    
    # === GUARDAR CLUTCH DATA ===
    progress_callback("info", "💾 Guardando datos clutch...")
    
    if all_clutch_data:
        clutch_data_df = pd.DataFrame(all_clutch_data)
        clutch_data_df.to_excel(clutch_data_output, index=False)
        logger.info(f"Clutch data saved: {len(clutch_data_df)} records -> {clutch_data_output}")
        progress_callback("success", f"✅ Clutch data: {len(clutch_data_df)} registros guardados")
    else:
        clutch_data_df = pd.DataFrame()
        progress_callback("warning", "⚠️ No se encontraron datos clutch")
    
    # === GUARDAR CLUTCH LINEUPS ===
    progress_callback("info", "💾 Guardando clutch lineups...")
    
    if all_clutch_lineups:
        clutch_lineups_df = pd.concat(all_clutch_lineups, ignore_index=True)
        clutch_lineups_df.to_excel(clutch_lineups_output, index=False)
        logger.info(f"Clutch lineups saved: {len(clutch_lineups_df)} lineups -> {clutch_lineups_output}")
        progress_callback("success", f"✅ Clutch lineups: {len(clutch_lineups_df)} lineups guardados")
    else:
        clutch_lineups_df = pd.DataFrame()
        progress_callback("warning", "⚠️ No se encontraron clutch lineups")
    
    progress_callback("success", "🔥👥 Extracción COMBINADA completada - ¡Tiempo optimizado!")
    logger.info("Combined clutch extraction completed successfully")
    
    # Restaurar configuración original si se modificó
    if temporada and 'original_temporada' in locals():
        web_scraping.TEMPORADA_TXT = original_temporada
        logger.info(f"Restored original temporada: {original_temporada}")
    
    if fases and 'original_phases' in locals():
        scraper_all_games.PHASES = original_phases
        logger.info(f"Restored original phases: {original_phases}")
    
    return clutch_data_df, clutch_lineups_df

if __name__ == "__main__":
    # Ejemplo de uso
    clutch_data_output = "./data/clutch_data_combined_test.xlsx"
    clutch_lineups_output = "./data/clutch_lineups_combined_test.xlsx"
    
    def test_callback(msg_type, message):
        print(f"[{msg_type.upper()}] {message}")
    
    clutch_data_df, clutch_lineups_df = main_clutch_combined(
        clutch_data_output, 
        clutch_lineups_output, 
        test_callback
    )
    
    print(f"Resultados:")
    print(f"- Clutch data: {len(clutch_data_df)} registros")
    print(f"- Clutch lineups: {len(clutch_lineups_df)} lineups")