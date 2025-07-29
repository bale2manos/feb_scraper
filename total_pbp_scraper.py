# total_pbp_scraper.py

import time
import logging
from typing import List, Dict

import pandas as pd
from selenium.common.exceptions import WebDriverException

from scraper_all_games import scrape_all         # your all-games scraper
from scraper_pbp import scrape_play_by_play, compute_synergies  # your pbp scraper and aggregator
from utils import init_driver

# --- Configuration ---
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
OUT_CSV = "assists.csv"
OUT_XLSX = "assists.xlsx"
LOG_FILE = "scraper.log"

def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)

def main():
    setup_logging()
    logging.info("Starting full play-by-play scraper")

    # 1) Get list of all games
    games = scrape_all()  # returns List of [phase, jornada, partido_id, idEquipo, local, rival, resultado]
    logging.info(f"Found {len(games)//2} matches (both sides)")

    # 2) Init a single driver for all pbp scrapes
    driver = init_driver()

    records: List[Dict] = []
    seen_games = set()  # to avoid reprocessing same partido_id twice
    for phase, jornada, pid, idEquipo, local, rival, resultado in games:
        # only run pbp once per match
        if pid in seen_games:
            continue
        seen_games.add(pid)

        game_str = f"{local} vs {rival}"
        logging.info(f"=== Processing partido {pid}: {game_str} — {phase} Jornada {jornada}")

        # 3) Exponential backoff retries
        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw_synergies = scrape_play_by_play(driver, pid)
                break
            except WebDriverException as e:
                logging.warning(f"[{pid}] pbp scrape failed (attempt {attempt}/{MAX_RETRIES}): {e!r}")
                if attempt == MAX_RETRIES:
                    logging.error(f"[{pid}] Giving up after {MAX_RETRIES} attempts")
                    raw_synergies = []
                    break
                time.sleep(backoff)
                backoff *= 2

        # 4) Aggregate counts
        agg = compute_synergies(raw_synergies)

        # 5) Emit one row per assist+score pair
        for row in agg:
            records.append({
                "FASE": phase,
                "JORNADA": jornada,
                "GAME": game_str,
                "EQUIPO": row["team"],
                "PASADOR": row["passer"],
                "ANOTADOR": row["scorer"],
                "N_ASISTENCIAS": row["count"],
            })

    driver.quit()
    logging.info("Finished scraping all play-by-play data")

    # 6) Save outputs
    df = pd.DataFrame(records, columns=[
        "FASE", "JORNADA", "GAME", "EQUIPO", "PASADOR", "ANOTADOR", "N_ASISTENCIAS"
    ])
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    df.to_excel(OUT_XLSX, index=False)
    logging.info(f"Saved {len(df)} rows to {OUT_CSV} and {OUT_XLSX}")


if __name__ == "__main__":
    main()
