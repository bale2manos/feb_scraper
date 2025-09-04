# total_clutch_scraper_parallel.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import time
import logging
from typing import List, Dict, Tuple
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

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
    logging.info("=== Inicio total_clutch_scraper_parallel ===")

    # 1) Listado de TODOS los partidos de la temporada
    games = scrape_all()  # lista de filas [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
    logging.info(f"Scrape_all devolvió {len(games)} filas (incluye local/visitante).")

    # 2) Un solo registro por PARTIDO_ID
    unique_by_pid: Dict[str, Tuple[str,int,str,int,str,str,str]] = {}
    for row in games:
        fase, jornada, pid, idequipo, local, rival, resultado = row
        if pid not in unique_by_pid:
            unique_by_pid[pid] = (fase, jornada, pid, idequipo, local, rival, resultado)
    unique_games = list(unique_by_pid.values())
    logging.info(f"Partidos únicos: {len(unique_games)}")

    # 3) Paralelizar por partido
    all_dfs: List[pd.DataFrame] = []
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
                    logging.info(f"[{pid}] sin datos")
            except Exception as e:
                logging.error(f"[{pid}] crash: {e!r}")

    if not all_dfs:
        logging.error("No se obtuvo ningún DataFrame de partidos. Abortando.")
        return

    # 4) Concatenar y guardar
    df_all = pd.concat(all_dfs, ignore_index=True)
    # Orden de columnas (si existen):
    desired = [
        "FASE","JORNADA","PARTIDO_ID","GAME",
        "EQUIPO","JUGADOR","MIN_CLUTCH","PTS","FGA","FGM","3PA","3PM","FTA","FTM",
        "eFG%","TS%","AST","TO","STL","REB","REB_O","REB_D","USG%","PLUS_MINUS","NET_RTG"
    ]
    cols = [c for c in desired if c in df_all.columns] + [c for c in df_all.columns if c not in desired]
    df_all = df_all[cols]

    os.makedirs(os.path.dirname(OUT_XLSX) or ".", exist_ok=True)
    df_all.to_excel(OUT_XLSX, index=False)
    logging.info(f"Guardado Excel: {OUT_XLSX} · {len(df_all)} filas totales · {df_all['PARTIDO_ID'].nunique()} partidos")

if __name__ == "__main__":
    main()
