import sys
import os

import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
import time
from collections import deque
from typing import List, Tuple, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.web_scraping import init_driver, accept_cookies

BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"

# Precompiled regexes
ASSIST_RE = re.compile(
    r"\(([^)]+)\)\s*([^:]+):\s*ASISTENCIA", 
    re.IGNORECASE
)
SHOT_RE = re.compile(
    r"\(([^)]+)\)\s*([^:]+):\s*(?:TIRO DE [23]|MATE)\s+ANOTADO", 
    re.IGNORECASE
)


def match_by_sequence(raw: List[Tuple[str,str]]) -> List[Tuple[str,str,str,str]]:
    pending = deque()
    pairs = []

    for texto, _ in raw:
        # push any new assist onto pendings
        m = ASSIST_RE.match(texto)
        if m:
            team, passer = m.group(1).strip(), m.group(2).strip()
            pending.append((team, passer))
            continue

        # upon a made shot, match it to the earliest same‐team assist
        n = SHOT_RE.match(texto)
        if n:
            team, scorer = n.group(1).strip(), n.group(2).strip()
            for _ in range(len(pending)):
                at, ap = pending.popleft()
                if at == team:
                    pairs.append((team, ap, team, scorer))
                    break
                # not a match → re‐queue
                pending.append((at, ap))

    return pairs


def scrape_play_by_play(driver, partido_id: str) -> List[Tuple[str,str,str,str]]:
    driver.get(BASE_PLAY_URL.format(partido_id))
    accept_cookies(driver)

    # remove GDPR overlay if present
    driver.execute_script("""
      const o = document.querySelector('.stpd_cmp_wrapper');
      if (o) o.remove();
    """)

    wait = WebDriverWait(driver, 10)

    # 1) Click “Directo”
    tab = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "a.btn-tab[data-action='keyfacts']"
    )))
    driver.execute_script("arguments[0].scrollIntoView()", tab)
    driver.execute_script("arguments[0].click()", tab)

    # 2) Check all quarters
    wait.until(EC.presence_of_all_elements_located((
        By.CSS_SELECTOR, "div.selector.inline.de.checkboxes input.checkbox"
    )))
    for cb in driver.find_elements(By.CSS_SELECTOR, "div.selector.inline.de.checkboxes input.checkbox"):
        if not cb.is_selected():
            driver.execute_script("arguments[0].scrollIntoView()", cb)
            driver.execute_script("arguments[0].click()", cb)
            time.sleep(0.1)

    # 3) Wait for the play‐by‐play rows
    wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR, "div.widget-keyfacts .fila[data-cuarto]"
    )))

    # 4) Scrape raw (deduping consecutive duplicates)
    raw: List[Tuple[str,str]] = []
    prev = None
    for fila in driver.find_elements(By.CSS_SELECTOR, "div.widget-keyfacts .fila[data-cuarto]"):
        try:
            tiempo = fila.find_element(By.CSS_SELECTOR, "span.tiempo").text.split()[0]
            textos = fila.find_elements(By.CSS_SELECTOR, "span.accion")
            texto = " ".join(t.text for t in textos if t.text.strip())
            key = (texto.strip(), tiempo.strip())
            if key != prev:
                raw.append(key)
                prev = key
        except Exception:
            continue

    # 5) Sequence‐based matching
    return match_by_sequence(raw)


def compute_synergies(
    data: List[Tuple[str,str,str,str]]
) -> List[Dict[str,object]]:
    counter: Dict[Tuple[str,str,str,str],int] = {}
    for row in data:
        counter[row] = counter.get(row, 0) + 1

    return [
        {"team": team1, "passer": paser, "scorer": scorer, "count": cnt}
        for ((team1, paser, _, scorer), cnt) in counter.items()
    ]


if __name__ == "__main__":
    from pprint import pprint

    driver = init_driver()
    pairs = scrape_play_by_play(driver, "2413697")
    driver.quit()

    table = compute_synergies(pairs)
    pprint(table)
    
    # Count the total assists per team
    team_assists = {}
    for row in table:
        team = row["team"]
        assists = row["count"]
        team_assists[team] = team_assists.get(team, 0) + assists

    pprint(team_assists)
    
    # Save it at ./game_assists.xlsx
    df = pd.DataFrame(table)
    df.to_excel("./game_assists.xlsx", index=False)