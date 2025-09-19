# total_clutch_scraper_parallel.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from multiprocessing import set_start_method, freeze_support


import time
import logging
from typing import List, Dict, Tuple
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Ajusta estos imports según tu estructura:
from scraper_all_games import scrape_all        # devuelve [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
from scrape_clutch import clutch_for_game   # función añadida arriba

# --- Config ---
MAX_RETRIES     = 3
INITIAL_BACKOFF = 1    # seconds
LOG_FILE        = "./clutch_season.log"
OUT_XLSX        = "./data/clutch_season_report.xlsx"
WORKERS         = 4     # ajusta a tu CPU/RAM

def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); fh.setFormatter(fmt)
    ch = logging.StreamHandler(); ch.setFormatter(fmt)
    logger.handlers.clear()
    logger.addHandler(fh); logger.addHandler(ch)

def scrape_one_game(meta: Tuple[str,int,str,int,str,str,str]) -> pd.DataFrame:
    """
    Ejecuta clutch_for_game para un partido. Devuelve DataFrame con columnas
    de métricas + metadatos del partido.
    meta = (Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado)
    """
    fase, jornada, pid, _idequipo, local, rival, _resultado = meta
    game_str = f"{local} vs {rival}"
    backoff = INITIAL_BACKOFF

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = clutch_for_game(pid, retries=2, keep_snapshot=False)
            if df is None or df.empty:
                logging.warning(f"[{pid}] clutch_for_game devolvió vacío.")
                return pd.DataFrame()
            # añade metadatos
            df = df.copy()
            df.insert(0, "PARTIDO_ID", pid)
            df.insert(0, "JORNADA", jornada)
            df.insert(0, "FASE", fase)
            df.insert(3, "GAME", game_str)
            return df
        except Exception as e:
            last_exc = e
            logging.warning(f"[{pid}] intento {attempt}/{MAX_RETRIES} falló: {e!r}")
            time.sleep(backoff); backoff *= 2

    logging.error(f"[{pid}] agotados reintentos: {last_exc!r}")
    return pd.DataFrame()

def main():
    setup_logging()
    logging.info("Starting parallel clutch scraper")

    games = scrape_all()  # [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
    logging.info(f"scrape_all -> {len(games)} filas")

    # Un único registro por PARTIDO_ID
    unique_by_pid = {}
    for fase, jornada, pid, idequipo, local, rival, resultado in games:
        if pid not in unique_by_pid:
            unique_by_pid[pid] = (fase, jornada, pid, idequipo, local, rival, resultado)
    unique_games = list(unique_by_pid.values())
    logging.info(f"Partidos únicos: {len(unique_games)}")

    all_dfs = []
    with ProcessPoolExecutor(max_workers=WORKERS) as exe:
        futures = { exe.submit(scrape_one_game, meta): meta[2] for meta in unique_games }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    all_dfs.append(df)
                    logging.info(f"[{pid}] OK · {len(df)} filas")
                else:
                    logging.info(f"[{pid}] vacío")
            except Exception as e:
                logging.error(f"[{pid}] crash: {e!r}")

    if not all_dfs:
        logging.error("No se obtuvo ningún DataFrame. Abortando.")
        return

    df_all = pd.concat(all_dfs, ignore_index=True)
    desired = [
        "FASE","JORNADA","PARTIDO_ID","GAME",
        "EQUIPO","JUGADOR","MIN_CLUTCH","PTS","FGA","FGM","3PA","3PM","FTA","FTM",
        "eFG%","TS%","AST","TO","STL","REB","REB_O","REB_D","USG%","PLUS_MINUS","NET_RTG"
    ]
    cols = [c for c in desired if c in df_all.columns] + [c for c in df_all.columns if c not in desired]
    df_all = df_all[cols]

    os.makedirs(os.path.dirname(OUT_XLSX) or ".", exist_ok=True)
    df_all.to_excel(OUT_XLSX, index=False)
    logging.info(f"Saved Excel: {OUT_XLSX} · {len(df_all)} filas · {df_all['PARTIDO_ID'].nunique()} partidos")
    
    return df_all

def generate_clutch_season_stats(
    output_path: str,
    progress_callback=None,
    temporada: str = None,
    liga: str = None,
    fases: list = None,
    jornadas: list = None
):
    """
    Función wrapper para generar estadísticas de clutch season desde la app.
    Esta versión optimizada agrega desde los datos ya scrapeados en lugar de re-scrapear.
    
    Args:
        output_path: Ruta donde guardar el archivo de estadísticas clutch
        progress_callback: Función para reportar progreso
        temporada: Temporada específica (no usado, para compatibilidad)
        liga: Liga específica (no usado, para compatibilidad)
        fases: Lista de fases específicas (no usado, para compatibilidad)
        jornadas: Lista de jornadas específicas (no usado, para compatibilidad)
    
    Returns:
        DataFrame con las estadísticas clutch generadas
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    try:
        progress_callback("info", "🔥 Generando clutch season desde datos unificados")
        
        # Buscar el archivo clutch_data correspondiente
        output_dir = Path(output_path).parent
        clutch_data_pattern = output_dir / "clutch_data_*.xlsx"
        
        import glob
        clutch_data_files = glob.glob(str(clutch_data_pattern))
        
        if not clutch_data_files:
            progress_callback("warning", "⚠️ No se encontró archivo clutch_data para agregar")
            progress_callback("info", "🔄 Ejecutando scraping completo como fallback")
            return generate_clutch_season_stats_from_web(output_path, progress_callback)
        
        # Usar el primer archivo encontrado (debería ser único por directorio)
        clutch_data_path = clutch_data_files[0]
        progress_callback("info", f"📊 Agregando desde: {Path(clutch_data_path).name}")
        
        # Leer datos de clutch_data
        clutch_df = pd.read_excel(clutch_data_path)
        
        if clutch_df.empty:
            progress_callback("warning", "⚠️ Archivo clutch_data está vacío")
            return pd.DataFrame()
        
        # Verificar que tenemos las columnas necesarias
        required_columns = ["FASE", "JORNADA", "GAME", "JUGADOR", "EQUIPO", "MINUTOS_CLUTCH"]
        missing_columns = [col for col in required_columns if col not in clutch_df.columns]
        
        if missing_columns:
            progress_callback("warning", f"⚠️ Columnas faltantes en clutch_data: {missing_columns}")
            progress_callback("info", "🔄 Ejecutando scraping completo como fallback")
            return generate_clutch_season_stats_from_web(output_path, progress_callback)
        
        # Los datos ya están en el formato correcto para clutch season
        # Solo necesitamos agregar PARTIDO_ID si no existe
        if "PARTIDO_ID" not in clutch_df.columns:
            # Generar un PARTIDO_ID único por juego basado en GAME
            game_to_id = {game: f"GAME_{i:04d}" for i, game in enumerate(clutch_df["GAME"].unique())}
            clutch_df["PARTIDO_ID"] = clutch_df["GAME"].map(game_to_id)
        
        # Reordenar columnas al formato esperado
        desired_columns = [
            "FASE", "JORNADA", "PARTIDO_ID", "GAME",
            "EQUIPO", "JUGADOR", "MINUTOS_CLUTCH", "SEGUNDOS_CLUTCH"
        ]
        
        # Añadir columnas de estadísticas si existen
        stat_columns = ["PTS", "FGA", "FGM", "3PA", "3PM", "FTA", "FTM", 
                       "eFG%", "TS%", "AST", "TO", "STL", "REB", "REB_O", "REB_D", 
                       "USG%", "PLUS_MINUS", "NET_RTG"]
        
        available_stat_columns = [col for col in stat_columns if col in clutch_df.columns]
        all_columns = desired_columns + available_stat_columns
        
        # Filtrar solo las columnas que existen
        final_columns = [col for col in all_columns if col in clutch_df.columns]
        clutch_season_df = clutch_df[final_columns].copy()
        
        # Guardar archivo
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        clutch_season_df.to_excel(output_path, index=False)
        
        progress_callback("success", f"✅ Clutch season agregado: {len(clutch_season_df)} registros")
        progress_callback("info", f"📁 Guardado en: {Path(output_path).name}")
        
        return clutch_season_df
        
    except Exception as e:
        progress_callback("error", f"❌ Error generando clutch season: {str(e)}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def generate_clutch_season_stats_from_web(
    output_path: str,
    progress_callback=None
):
    """
    Función fallback que genera estadísticas clutch season scrapeando desde web.
    Se usa cuando no hay datos clutch_data disponibles.
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    try:
        # Configurar logging específico para clutch season
        global LOG_FILE, OUT_XLSX
        original_log_file = LOG_FILE
        original_out_xlsx = OUT_XLSX
        
        # Actualizar rutas
        LOG_FILE = str(Path(output_path).parent / "clutch_season.log")
        OUT_XLSX = output_path
        
        progress_callback("info", "🔥 Iniciando scraping completo de clutch season")
        
        # Configurar logging
        setup_logging()
        
        # Ejecutar la función principal
        result_df = main()
        
        if result_df is not None and not result_df.empty:
            progress_callback("success", f"✅ Clutch season scrapeado: {len(result_df)} estadísticas")
            return result_df
        else:
            progress_callback("warning", "⚠️ No se generaron estadísticas clutch")
            return pd.DataFrame()
            
    except Exception as e:
        progress_callback("error", f"❌ Error en scraping clutch season: {str(e)}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    finally:
        # Restaurar configuración original
        LOG_FILE = original_log_file
        OUT_XLSX = original_out_xlsx

if __name__ == "__main__":
    # Muy importante para evitar ejecuciones recursivas en workers (Windows/macOS)
    try:
        set_start_method("spawn")
    except RuntimeError:
        pass
    freeze_support()
    main()