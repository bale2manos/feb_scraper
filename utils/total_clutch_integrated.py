# -*- coding: utf-8 -*-
"""
Total Clutch Scraper Integrado
===============================

Versión integrada del total_clutch_scraper.py para usar en la aplicación.
Extrae estadísticas de momentos clutch de todos los partidos.
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
from scrapers.scraper_minutes_clutch import run_scrape_and_parse

# Importar módulos de configuración para modificar variables globales
from utils import web_scraping
from scrapers import scraper_all_games

# Configuración
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
WORKERS = 2  # Reducido para evitar errores de conexión

def setup_logging_clutch(log_file: str = "clutch_scraper.log") -> None:
    """Configura logging para el scraper de clutch."""
    logger = logging.getLogger('clutch_scraper')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def scrape_one_game_clutch(args: Tuple[str,int,str,str,str,str,str]) -> List[Dict]:
    """
    Worker function: extrae datos clutch de un partido específico.
    
    Args:
        args: Tupla con (phase, jornada, pid, _, local, rival, _)
    
    Returns:
        Lista de registros clutch para ese partido
    """
    phase, jornada, pid, _, local, rival, _ = args
    records = []
    game_str = f"{local} vs {rival}"
    backoff = INITIAL_BACKOFF
    
    logger = logging.getLogger('clutch_scraper')
    
    for attempt in range(1, MAX_RETRIES+1):
        try:
            # run_scrape_and_parse maneja su propio driver y devuelve DataFrame
            clutch_df = run_scrape_and_parse(pid)
            raw_data = clutch_df.to_dict('records')  # Convertir a lista de diccionarios
            break
        except Exception as e:
            logger.warning(f"[{pid}] attempt {attempt}/{MAX_RETRIES} failed: {e!r}")
            if attempt == MAX_RETRIES:
                logger.error(f"[{pid}] giving up.")
                raw_data = []
                break
            time.sleep(backoff)
            backoff *= 2
    
    # Ya no necesitamos quit() porque run_scrape_and_parse maneja su propio driver
    
    # Procesar datos clutch
    for row in raw_data:
        records.append({
            "FASE": phase,
            "JORNADA": jornada,
            "GAME": game_str,
            "JUGADOR": row.get("player", ""),
            "EQUIPO": row.get("team", ""),
            "MINUTOS_CLUTCH": row.get("minutes", 0),
            "PUNTOS_CLUTCH": row.get("points", 0),
            "REBOTES_CLUTCH": row.get("rebounds", 0),
            "ASISTENCIAS_CLUTCH": row.get("assists", 0),
            "FG_MADE_CLUTCH": row.get("fg_made", 0),
            "FG_ATT_CLUTCH": row.get("fg_att", 0),
            "FT_MADE_CLUTCH": row.get("ft_made", 0),
            "FT_ATT_CLUTCH": row.get("ft_att", 0),
            "T3_MADE_CLUTCH": row.get("t3_made", 0),
            "T3_ATT_CLUTCH": row.get("t3_att", 0),
        })
    
    return records

def main_clutch(output_file: str, progress_callback: Callable[[str, str], None] = None,
               temporada: str = None, liga: str = None, fases: list = None) -> pd.DataFrame:
    """
    Función principal del scraper de clutch.
    
    Args:
        output_file: Ruta del archivo de salida
        progress_callback: Función para reportar progreso (msg_type, message)
        temporada: Temporada específica (ej: "24_25")
        liga: Liga específica (ej: "primera_feb") 
        fases: Lista de fases específicas (ej: ["regular", "playoff"])
    
    Returns:
        DataFrame con los datos clutch extraídos
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(output_file).parent / "clutch_scraper.log")
    setup_logging_clutch(log_file)
    logger = logging.getLogger('clutch_scraper')
    
    progress_callback("info", "🔥 Iniciando extracción de datos clutch")
    logger.info("Starting clutch scraper")
    
    # Obtener lista de partidos (usando configuración global del scraper_app)
    progress_callback("info", "📋 Obteniendo lista de partidos...")
    logger.info(f"Using current global config: temporada={web_scraping.TEMPORADA_TXT}, fases={scraper_all_games.PHASES}")
    games = scrape_all()
    
    # Filtrar partidos únicos por ID
    unique_games = []
    seen = set()
    for g in games:
        pid = g[2]
        if pid not in seen:
            seen.add(pid)
            unique_games.append(g)
    
    progress_callback("info", f"🎯 Procesando {len(unique_games)} partidos únicos")
    logger.info(f"Processing {len(unique_games)} unique games")
    
    all_records: List[Dict] = []
    
    # Procesamiento paralelo
    with ProcessPoolExecutor(max_workers=WORKERS) as exe:
        futures = {exe.submit(scrape_one_game_clutch, g): g[2] for g in unique_games}
        completed = 0
        
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                recs = fut.result()
                all_records.extend(recs)
                completed += 1
                
                progress_callback("info", f"🔥 Partido {completed}/{len(unique_games)} procesado: {len(recs)} datos clutch")
                logger.info(f"[{pid}] done, got {len(recs)} clutch records")
                
            except Exception as e:
                logger.error(f"[{pid}] crashed: {e!r}")
                progress_callback("error", f"❌ Error procesando partido {pid}: {str(e)}")
    
    # Crear DataFrame
    progress_callback("info", "📝 Generando archivo final...")
    df = pd.DataFrame(all_records, columns=[
        "FASE", "JORNADA", "GAME", "JUGADOR", "EQUIPO", "MINUTOS_CLUTCH", 
        "PUNTOS_CLUTCH", "REBOTES_CLUTCH", "ASISTENCIAS_CLUTCH",
        "FG_MADE_CLUTCH", "FG_ATT_CLUTCH", "FT_MADE_CLUTCH", "FT_ATT_CLUTCH",
        "T3_MADE_CLUTCH", "T3_ATT_CLUTCH"
    ])
    
    # Guardar archivo
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_file, index=False)
    
    progress_callback("success", f"✅ Datos clutch extraídos: {len(df)} registros guardados")
    logger.info(f"Saved {len(df)} clutch records to {output_file}")
    
    return df

if __name__ == "__main__":
    # Test independiente
    output_file = "./data/clutch_season_test.xlsx"
    df = main_clutch(output_file)
    print(f"✅ Test completado: {len(df)} registros en {output_file}")