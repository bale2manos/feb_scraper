# -*- coding: utf-8 -*-
"""
Total Assists Scraper Integrado
================================

Versión integrada del total_assists_scraper.py para usar en la aplicación.
Extrae asistencias de todos los partidos y genera estadísticas por pasador-anotador.
"""

import sys
import os
import time
import logging
from typing import List, Dict, Tuple, Callable
import pandas as pd
from pathlib import Path
from selenium.common.exceptions import WebDriverException
from concurrent.futures import ProcessPoolExecutor, as_completed

# Importar scrapers necesarios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.scraper_all_games import scrape_all
from scrapers.scraper_pbp import scrape_play_by_play, compute_synergies
from utils.web_scraping import init_driver

# Importar módulos de configuración para modificar variables globales
from utils import web_scraping
from scrapers import scraper_all_games

# Configuración
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
WORKERS = 2  # Reducido para evitar errores de conexión

def setup_logging_assists(log_file: str = "assists_scraper.log") -> None:
    """Configura logging para el scraper de assists."""
    logger = logging.getLogger('assists_scraper')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def scrape_one_game_assists(args: Tuple[str,int,str,str,str,str,str]) -> List[Dict]:
    """
    Worker function: extrae asistencias de un partido específico.
    
    Args:
        args: Tupla con (phase, jornada, pid, _, local, rival, _)
    
    Returns:
        Lista de registros de asistencias para ese partido
    """
    phase, jornada, pid, _, local, rival, _ = args
    driver = init_driver()
    records = []
    game_str = f"{local} vs {rival}"
    backoff = INITIAL_BACKOFF
    
    logger = logging.getLogger('assists_scraper')
    
    for attempt in range(1, MAX_RETRIES+1):
        try:
            raw = scrape_play_by_play(driver, pid)
            break
        except WebDriverException as e:
            logger.warning(f"[{pid}] attempt {attempt}/{MAX_RETRIES} failed: {e!r}")
            if attempt == MAX_RETRIES:
                logger.error(f"[{pid}] giving up.")
                raw = []
                break
            time.sleep(backoff)
            backoff *= 2
    
    driver.quit()
    
    # Agregar y empaquetar datos
    for row in compute_synergies(raw):
        records.append({
            "FASE": phase,
            "JORNADA": jornada,
            "GAME": game_str,
            "EQUIPO": row["team"],
            "PASADOR": row["passer"],
            "ANOTADOR": row["scorer"],
            "N_ASISTENCIAS": row["count"],
        })
    
    return records

def main_assists(output_file: str, progress_callback: Callable[[str, str], None] = None,
                temporada: str = None, liga: str = None, fases: list = None) -> pd.DataFrame:
    """
    Función principal del scraper de asistencias.
    
    Args:
        output_file: Ruta del archivo de salida
        progress_callback: Función para reportar progreso (msg_type, message)
        temporada: Temporada específica (ej: "24_25")
        liga: Liga específica (ej: "primera_feb") 
        fases: Lista de fases específicas (ej: ["regular", "playoff"])
    
    Returns:
        DataFrame con las asistencias extraídas
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(output_file).parent / "assists_scraper.log")
    setup_logging_assists(log_file)
    logger = logging.getLogger('assists_scraper')
    
    progress_callback("info", "🏀 Iniciando extracción de asistencias")
    logger.info("Starting assists scraper")
    
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
        futures = {exe.submit(scrape_one_game_assists, g): g[2] for g in unique_games}
        completed = 0
        
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                recs = fut.result()
                all_records.extend(recs)
                completed += 1
                
                progress_callback("info", f"📊 Partido {completed}/{len(unique_games)} procesado: {len(recs)} asistencias")
                logger.info(f"[{pid}] done, got {len(recs)} assists")
                
            except Exception as e:
                logger.error(f"[{pid}] crashed: {e!r}")
                progress_callback("error", f"❌ Error procesando partido {pid}: {str(e)}")
    
    # Crear DataFrame
    progress_callback("info", "📝 Generando archivo final...")
    df = pd.DataFrame(all_records, columns=[
        "FASE", "JORNADA", "GAME", "EQUIPO", "PASADOR", "ANOTADOR", "N_ASISTENCIAS"
    ])
    
    # Guardar archivo
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_file, index=False)
    
    progress_callback("success", f"✅ Asistencias extraídas: {len(df)} registros guardados")
    logger.info(f"Saved {len(df)} assist records to {output_file}")
    
    # Restaurar configuración original si se modificó
    if temporada and 'original_temporada' in locals():
        web_scraping.TEMPORADA_TXT = original_temporada
        logger.info(f"Restored original temporada: {original_temporada}")
    
    if fases and 'original_phases' in locals():
        scraper_all_games.PHASES = original_phases
        logger.info(f"Restored original phases: {original_phases}")
    
    return df

if __name__ == "__main__":
    # Test independiente
    output_file = "./data/assists_test.xlsx"
    df = main_assists(output_file)
    print(f"✅ Test completado: {len(df)} registros en {output_file}")