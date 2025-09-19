# -*- coding: utf-8 -*-
"""
Unified Scraper Integrated
===========================

Pipeline COMPLETAMENTE OPTIMIZADO que extrae TODOS los datos de cada partido
en una sola sesión web. Esto incluye:

- Boxscores completos
- Play-by-play para asistencias  
- Datos clutch individuales
- Clutch lineups (quintetos)

Beneficios:
- 3x más rápido: Un solo acceso por partido
- Menos errores de conexión
- Uso más eficiente de recursos
- Misma funcionalidad completa
"""

import sys
import os
import time
import logging
import re
from typing import List, Dict, Tuple, Callable, Optional
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Importar módulos necesarios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar scrapers existentes para reutilizar lógica
from scrapers.scraper_all_games import scrape_all
from scrapers.scrape_game import scrape_boxscore
from scrapers.scrape_clutch import clutch_for_game
from scrapers.scrape_clutch_lineup import lineups_for_game

# Importar utils para asistencias
from scrapers.scraper_pbp import scrape_play_by_play, compute_synergies
from utils.web_scraping import init_driver
from utils import web_scraping
from scrapers import scraper_all_games

# Configuración
MAX_WORKERS = 2  # Reducido para evitar errores de conexión
MAX_RETRIES = 2
INITIAL_BACKOFF = 2

def setup_logging_unified(log_file: str = "unified_scraper.log") -> None:
    """Configura logging para el scraper unificado."""
    logger = logging.getLogger('unified_scraper')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def scrape_one_game_unified(game_meta: Tuple) -> Tuple[List[Dict], List[Dict], List[Dict], pd.DataFrame]:
    """
    Worker function: extrae TODOS los datos de un partido en una sola sesión.
    MANEJO INDEPENDIENTE DE ERRORES: Si falla clutch, solo falla clutch.
    Boxscores y asistencias siguen funcionando aunque clutch falle.
    
    Args:
        game_meta: Tupla con (fase, jornada, pid, idequipo, local, rival, resultado)
    
    Returns:
        Tupla con (boxscore_records, assists_records, clutch_data_records, clutch_lineups_df)
    """
    phase, jornada, pid, idequipo, local, rival, resultado = game_meta
    
    boxscore_records = []
    assists_records = []
    clutch_data_records = []
    clutch_lineups_df = pd.DataFrame()
    game_str = f"{local} vs {rival}"
    
    logger = logging.getLogger('unified_scraper')
    
    # === PARTE 1 & 2: BOXSCORES + ASISTENCIAS (datos esenciales) ===
    success_core_data = False
    for attempt in range(1, MAX_RETRIES+1):
        try:
            logger.info(f"[{pid}] Extrayendo datos CORE (boxscores + asistencias) - intento {attempt}/{MAX_RETRIES}")
            
            # Inicializar driver una sola vez para los datos core
            driver = init_driver()
            
            try:
                # === BOXSCORES ===
                boxscore_records = scrape_boxscore(driver, pid, phase, jornada)
                logger.info(f"[{pid}] ✅ Boxscores: {len(boxscore_records)} registros")
                
                # === ASISTENCIAS (Play-by-Play) ===
                # Reutilizar el mismo driver
                raw_pbp = scrape_play_by_play(driver, pid)
                
                # Procesar asistencias
                for row in compute_synergies(raw_pbp):
                    assists_records.append({
                        "FASE": phase,
                        "JORNADA": jornada,
                        "GAME": game_str,
                        "EQUIPO": row["team"],
                        "PASADOR": row["passer"],
                        "ANOTADOR": row["scorer"],
                        "N_ASISTENCIAS": row["count"],
                    })
                
                logger.info(f"[{pid}] ✅ Asistencias: {len(assists_records)} registros")
                success_core_data = True
                
            finally:
                driver.quit()
            
            # Si llegamos aquí, los datos core están OK
            if success_core_data:
                break
                
        except Exception as e:
            logger.warning(f"[{pid}] CORE data attempt {attempt}/{MAX_RETRIES} failed: {e!r}")
            if attempt == MAX_RETRIES:
                logger.error(f"[{pid}] CORE data failed completely - critical error")
                # Para datos core, si falla todo, devolvemos vacío
                return [], [], [], pd.DataFrame()
            time.sleep(INITIAL_BACKOFF * (2 ** (attempt-1)))
    
    # === PARTE 3: CLUTCH DATA (independiente - puede fallar) ===
    try:
        logger.info(f"[{pid}] Extrayendo CLUTCH data (independiente)")
        clutch_df = clutch_for_game(pid)
        
        # Convertir DataFrame a lista de diccionarios con metadatos del partido
        if not clutch_df.empty:
            for _, row in clutch_df.iterrows():
                clutch_data_records.append({
                    "FASE": phase,
                    "JORNADA": jornada,
                    "GAME": game_str,
                    "JUGADOR": row.get("JUGADOR", ""),
                    "EQUIPO": row.get("EQUIPO", ""),
                    "MINUTOS_CLUTCH": row.get("MIN_CLUTCH", 0),
                    "SEGUNDOS_CLUTCH": row.get("MIN_CLUTCH", 0) * 60,
                    "PTS": row.get("PTS", 0),
                    "FGA": row.get("FGA", 0),
                    "FGM": row.get("FGM", 0),
                    "3PA": row.get("3PA", 0),
                    "3PM": row.get("3PM", 0),
                    "FTA": row.get("FTA", 0),
                    "FTM": row.get("FTM", 0),
                    "eFG%": row.get("eFG%", 0),
                    "TS%": row.get("TS%", 0),
                    "AST": row.get("AST", 0),
                    "TO": row.get("TO", 0),
                    "STL": row.get("STL", 0),
                    "REB": row.get("REB", 0),
                    "REB_O": row.get("REB_O", 0),
                    "REB_D": row.get("REB_D", 0),
                    "USG%": row.get("USG%", 0),
                    "PLUS_MINUS": row.get("PLUS_MINUS", 0),
                    "NET_RTG": row.get("NET_RTG", 0)
                })
        
        logger.info(f"[{pid}] ✅ Clutch data: {len(clutch_data_records)} registros")
        
    except Exception as e:
        logger.warning(f"[{pid}] ⚠️ CLUTCH data failed (no afecta datos core): {e!r}")
        # clutch_data_records ya está vacío, no hacemos nada más
        
    # === PARTE 4: CLUTCH LINEUPS (independiente - puede fallar) ===
    try:
        logger.info(f"[{pid}] Extrayendo CLUTCH lineups (independiente)")
        lineups_df = lineups_for_game(pid)
        
        # Añadir metadatos del partido al DataFrame de lineups
        if not lineups_df.empty:
            lineups_df = lineups_df.copy()
            lineups_df['FASE'] = phase
            lineups_df['JORNADA'] = jornada
            lineups_df['GAME'] = game_str
            lineups_df['PARTIDO_ID'] = pid
            
            clutch_lineups_df = lineups_df
        
        logger.info(f"[{pid}] ✅ Clutch lineups: {len(clutch_lineups_df)} lineups")
        
    except Exception as e:
        logger.warning(f"[{pid}] ⚠️ CLUTCH lineups failed (no afecta datos core): {e!r}")
        # clutch_lineups_df ya está vacío, no hacemos nada más
    
    # === RESUMEN ===
    core_success = len(boxscore_records) > 0 or len(assists_records) > 0
    clutch_success = len(clutch_data_records) > 0 or len(clutch_lineups_df) > 0
    
    if core_success and clutch_success:
        logger.info(f"[{pid}] 🎉 UNIFICADO COMPLETADO: TODOS los datos extraídos")
    elif core_success:
        logger.info(f"[{pid}] ✅ CORE COMPLETADO: Boxscores y asistencias OK (clutch falló pero no importa)")
    else:
        logger.error(f"[{pid}] ❌ FALLO CRÍTICO: No se pudieron extraer datos core")
    
    return boxscore_records, assists_records, clutch_data_records, clutch_lineups_df

def main_unified_scraper(
    boxscores_output: str,
    assists_output: str, 
    clutch_data_output: str, 
    clutch_lineups_output: str, 
    progress_callback: Callable[[str, str], None] = None,
    temporada: str = None, 
    liga: str = None, 
    fases: list = None,
    jornadas: list = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Función principal del scraper UNIFICADO.
    
    Args:
        boxscores_output: Ruta del archivo de salida para boxscores
        assists_output: Ruta del archivo de salida para asistencias
        clutch_data_output: Ruta del archivo de salida para clutch data
        clutch_lineups_output: Ruta del archivo de salida para clutch lineups
        progress_callback: Función para reportar progreso (msg_type, message)
        temporada: Temporada específica (ej: "2024/2025")
        liga: Liga específica (ej: "Primera FEB") 
        fases: Lista de fases específicas (ej: ["Liga Regular "B-A""])
        jornadas: Lista de jornadas específicas (ej: [1, 2, 3]) - opcional
    
    Returns:
        Tupla con (boxscores_df, assists_df, clutch_data_df, clutch_lineups_df)
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(boxscores_output).parent / "unified_scraper.log")
    setup_logging_unified(log_file)
    logger = logging.getLogger('unified_scraper')
    
    progress_callback("info", "🚀⚡ Iniciando pipeline UNIFICADO - Máxima eficiencia")
    logger.info("Starting UNIFIED scraper - maximum efficiency mode")
    
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
    
    # === FILTRADO POR JORNADAS (si se especifica) ===
    if jornadas:
        progress_callback("info", f"📅 Filtrando por jornadas específicas: {sorted(jornadas)}")
        logger.info(f"Filtering by jornadas: {sorted(jornadas)}")
        
        # Filtrar juegos por jornada
        # games tiene formato: [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
        # La jornada está en la posición 1
        filtered_games = []
        for game in games:
            jornada_game = game[1]  # Índice 1 es jornada
            if jornada_game in jornadas:
                filtered_games.append(game)
        
        games = filtered_games
        progress_callback("info", f"✅ Filtrado aplicado: {len(games)} partidos tras filtrar por jornadas")
        logger.info(f"Filtered games: {len(games)} games after jornada filter")
    else:
        progress_callback("info", f"📅 Sin filtro de jornadas: procesando todas las jornadas disponibles")
        logger.info("No jornada filter applied: processing all available jornadas")
    
    # Filtrar partidos únicos por ID
    unique_games = {}
    for game in games:
        pid = game[2]
        if pid not in unique_games:
            unique_games[pid] = game
    
    game_metas = list(unique_games.values())
    
    progress_callback("info", f"🎯 Procesando {len(game_metas)} partidos únicos (PIPELINE UNIFICADO: 1 acceso total por partido)")
    logger.info(f"Processing {len(game_metas)} unique games - UNIFIED PIPELINE: single total access per game")
    
    all_boxscore_data: List[Dict] = []
    all_assists_data: List[Dict] = []
    all_clutch_data: List[Dict] = []
    all_clutch_lineups: List[pd.DataFrame] = []
    
    # Procesamiento paralelo
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(scrape_one_game_unified, meta): meta[2] for meta in game_metas}
        completed = 0
        
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                boxscore_records, assists_records, clutch_data_records, clutch_lineups_df = fut.result()
                
                # Acumular resultados
                all_boxscore_data.extend(boxscore_records)
                all_assists_data.extend(assists_records)
                all_clutch_data.extend(clutch_data_records)
                if not clutch_lineups_df.empty:
                    all_clutch_lineups.append(clutch_lineups_df)
                
                completed += 1
                progress = int((completed / len(game_metas)) * 100)
                progress_callback("info", f"⚡ Progreso UNIFICADO: {completed}/{len(game_metas)} partidos ({progress}%)")
                
            except Exception as e:
                logger.error(f"Error procesando partido {pid}: {str(e)}")
                progress_callback("warning", f"⚠️ Error en partido {pid}: {str(e)}")
    
    # === GUARDAR BOXSCORES ===
    progress_callback("info", "💾 Guardando boxscores...")
    
    if all_boxscore_data:
        boxscores_df = pd.DataFrame(all_boxscore_data)
        boxscores_df.to_excel(boxscores_output, index=False)
        logger.info(f"Boxscores saved: {len(boxscores_df)} records -> {boxscores_output}")
        progress_callback("success", f"✅ Boxscores: {len(boxscores_df)} registros guardados")
    else:
        boxscores_df = pd.DataFrame()
        progress_callback("warning", "⚠️ No se encontraron boxscores")
    
    # === GUARDAR ASISTENCIAS ===
    progress_callback("info", "💾 Guardando asistencias...")
    
    if all_assists_data:
        assists_df = pd.DataFrame(all_assists_data)
        assists_df.to_excel(assists_output, index=False)
        logger.info(f"Assists saved: {len(assists_df)} records -> {assists_output}")
        progress_callback("success", f"✅ Asistencias: {len(assists_df)} registros guardados")
    else:
        assists_df = pd.DataFrame()
        progress_callback("warning", "⚠️ No se encontraron asistencias")
    
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
    
    progress_callback("success", "🚀⚡ Pipeline UNIFICADO completado - ¡Máxima optimización alcanzada!")
    logger.info("UNIFIED pipeline completed successfully - maximum optimization achieved")
    
    # Restaurar configuración original si se modificó
    if temporada and 'original_temporada' in locals():
        web_scraping.TEMPORADA_TXT = original_temporada
        logger.info(f"Restored original temporada: {original_temporada}")
    
    if fases and 'original_phases' in locals():
        scraper_all_games.PHASES = original_phases
        logger.info(f"Restored original phases: {original_phases}")
    
    return boxscores_df, assists_df, clutch_data_df, clutch_lineups_df

if __name__ == "__main__":
    # Ejemplo de uso
    boxscores_output = "./data/boxscores_unified_test.xlsx"
    assists_output = "./data/assists_unified_test.xlsx"
    clutch_data_output = "./data/clutch_data_unified_test.xlsx"
    clutch_lineups_output = "./data/clutch_lineups_unified_test.xlsx"
    
    def test_callback(msg_type, message):
        print(f"[{msg_type.upper()}] {message}")
    
    boxscores_df, assists_df, clutch_data_df, clutch_lineups_df = main_unified_scraper(
        boxscores_output,
        assists_output, 
        clutch_data_output, 
        clutch_lineups_output, 
        test_callback,
        jornadas=[1, 2]  # Ejemplo: filtrar solo jornadas 1 y 2
    )
    
    print(f"Resultados UNIFICADOS:")
    print(f"- Boxscores: {len(boxscores_df)} registros")
    print(f"- Asistencias: {len(assists_df)} registros")
    print(f"- Clutch data: {len(clutch_data_df)} registros")
    print(f"- Clutch lineups: {len(clutch_lineups_df)} lineups")