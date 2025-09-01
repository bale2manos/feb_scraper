# total_pbp_scraper_parallel.py

import time
import logging
from typing import List, Dict, Tuple
import pandas as pd
from selenium.common.exceptions import WebDriverException
from concurrent.futures import ProcessPoolExecutor, as_completed

from scraper_all_games import scrape_all         # your all-games scraper
from scraper_pbp import scrape_play_by_play, compute_synergies  
from utils.web_scraping import init_driver

MAX_RETRIES     = 5
INITIAL_BACKOFF = 1  # seconds
LOG_FILE        = "scraper.log"
OUT_CSV         = "assists.csv"
OUT_XLSX        = "./data/assists.xlsx"
WORKERS         = 4  # tune to your CPU / memory

def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); fh.setFormatter(fmt)
    ch = logging.StreamHandler(); ch.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(ch)

def scrape_one_game(args: Tuple[str,int,str,str,str,str,str]) -> List[Dict]:
    """
    Worker function: each process gets its own driver, does the retries/backoff,
    and returns a list of records for that partido_id.
    """
    phase, jornada, pid, _, local, rival, _ = args
    driver = init_driver()
    records = []
    game_str = f"{local} vs {rival}"
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES+1):
        try:
            raw = scrape_play_by_play(driver, pid)
            break
        except WebDriverException as e:
            logging.warning(f"[{pid}] attempt {attempt}/{MAX_RETRIES} failed: {e!r}")
            if attempt == MAX_RETRIES:
                logging.error(f"[{pid}] giving up.")
                raw = []
                break
            time.sleep(backoff); backoff *= 2

    driver.quit()

    # aggregate and package
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

def main():
    setup_logging()
    logging.info("Starting parallel scraper")
    games = scrape_all()
    # only one entry per partido_id passed to workers
    unique_games = []
    seen = set()
    for g in games:
        pid = g[2]
        if pid not in seen:
            seen.add(pid)
            unique_games.append(g)

    all_records: List[Dict] = []
    with ProcessPoolExecutor(max_workers=WORKERS) as exe:
        futures = { exe.submit(scrape_one_game, g): g[2] for g in unique_games }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                recs = fut.result()
                all_records.extend(recs)
                logging.info(f"[{pid}] done, got {len(recs)} pairs")
            except Exception as e:
                logging.error(f"[{pid}] crashed: {e!r}")

    logging.info("All games processed, saving output")
    df = pd.DataFrame(all_records, columns=[
        "FASE","JORNADA","GAME","EQUIPO","PASADOR","ANOTADOR","N_ASISTENCIAS"
    ])
    #df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    df.to_excel(OUT_XLSX, index=False)
    logging.info(f"Saved {len(df)} rows to {OUT_CSV} and {OUT_XLSX}")

if __name__ == "__main__":
    main()
