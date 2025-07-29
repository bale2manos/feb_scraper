import re
import time
from collections import defaultdict
from typing import List, Tuple, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils import init_driver, accept_cookies

BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"

# Expresiones precompiladas
ASSIST_RE = re.compile(r"\(([^)]+)\)\s*([^:]+):\s*ASISTENCIA", re.IGNORECASE)
SHOT_RE   = re.compile(r"\(([^)]+)\)\s*([^:]+):\s*TIRO DE [23] ANOTADO", re.IGNORECASE)

def scrape_play_by_play(driver, partido_id: str) -> List[Tuple[str, str, str, str]]:
    driver.get(BASE_PLAY_URL.format(partido_id))
    accept_cookies(driver)
    wait = WebDriverWait(driver, 10)

    # 1) Pestaña “Directo”
    wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "a.btn-tab[data-action='keyfacts']"
    ))).click()

    # 2) Marcar todos los cuartos (robusto contra overlays)
    wait.until(EC.presence_of_all_elements_located((
        By.CSS_SELECTOR, "div.selector.inline.de.checkboxes input.checkbox"
    )))
    for cb in driver.find_elements(By.CSS_SELECTOR, "div.selector.inline.de.checkboxes input.checkbox"):
        if not cb.is_selected():
            # asegúrate de que el input esté en vista
            driver.execute_script("arguments[0].scrollIntoView(true);", cb)
            # haz el click vía JS para no chocar con overlays
            driver.execute_script("arguments[0].click();", cb)
            time.sleep(0.1)


    # 3) Esperar Play-by-Play
    wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR, "div.widget-keyfacts .fila[data-cuarto]"
    )))

    # 4) Extraer (texto, tiempo) de cada fila
    raw: List[Tuple[str, str]] = []
    for fila in driver.find_elements(By.CSS_SELECTOR, "div.widget-keyfacts .fila[data-cuarto]"):
        try:
            tiempo = fila.find_element(By.CSS_SELECTOR, "span.tiempo").text.split()[0]
            textos  = fila.find_elements(By.CSS_SELECTOR, "span.accion")
            texto = " ".join([t.text for t in textos if t.text.strip()])
            raw.append((texto.strip(), tiempo.strip()))
        except Exception as e:
            print(f"Error processing row: {e}")
            continue

    # 5) Agrupar por tiempo y emparejar asistencias+canastas del mismo equipo
    por_tiempo: Dict[str, List[str]] = defaultdict(list)
    for texto, tiempo in raw:
        por_tiempo[tiempo].append(texto)

    sinergias: List[Tuple[str, str, str, str]] = []
    for tiempo, textos in por_tiempo.items():
        # buscar todas las asistencias y todas las canastas
        assists = []
        shots   = []
        for t in textos:
            m = ASSIST_RE.match(t)
            if m:
                assists.append((m.group(1).strip(), m.group(2).strip()))
            n = SHOT_RE.match(t)
            if n:
                shots.append((n.group(1).strip(), n.group(2).strip()))

        # emparejar sólo si coinciden de equipo
        for equipo_p, pasador in assists:
            for equipo_q, anotador in shots:
                if equipo_p == equipo_q:
                    sinergias.append((equipo_p, pasador, equipo_q, anotador))

    return sinergias

def compute_synergies(
    data: List[Tuple[str, str, str, str]]
) -> List[Dict[str, object]]:
    counter: Dict[Tuple[str,str,str,str], int] = {}
    for row in data:
        counter[row] = counter.get(row, 0) + 1

    return [
        {"team": team1, "passer": paser, "scorer": scorer, "count": cnt}
        for ((team1, paser, _, scorer), cnt) in counter.items()
    ]

if __name__ == "__main__":
    from pprint import pprint

    driver = init_driver()
    raw = scrape_play_by_play(driver, "2413780")
    driver.quit()

    table = compute_synergies(raw)
    pprint(table)
