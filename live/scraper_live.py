#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.web_scraping import init_driver, accept_cookies
from utils.config import BASE_PLAY_URL


def safe_int(s):
    try:
        return int(s)
    except:
        return 0


def parse_frac(frac: str):
    m = re.match(r"(\d+)\s*/\s*(\d+)", frac or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def scrape_boxscore_live(driver, partido_id: str):
    """
    Scrapear TODO LO QUE HAYA EN ESTE MOMENTO.
    Devuelve un JSON limpio con toda la información del boxscore.
    """
    url = BASE_PLAY_URL.format(partido_id)
    driver.get(url)
    accept_cookies(driver)

    # Quitar overlay GDPR
    driver.execute_script("""
        const o = document.querySelector('.stpd_cmp_wrapper');
        if(o) o.remove();
    """)

    wait = WebDriverWait(driver, 15)

    # Click en pestaña Ficha (boxscore)
    ficha_tab = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a.btn-tab[data-action='boxscore']")
        )
    )
    driver.execute_script("arguments[0].click()", ficha_tab)

    # Espera a la tabla
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "h1.titulo-modulo + .responsive-scroll table tbody")
    ))

    time.sleep(2)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # ============= INFORMACIÓN GLOBAL DEL PARTIDO =============

    # Estado del partido / tiempo y cuarto (si existen)
    status_el = soup.select_one(".contador.tiempo-partido")
    status = status_el.text.strip() if status_el else None

    # Intentar extraer el cuarto desde selectores comunes
    quarter = None
    q_selectors = [
        ".box-marcador .periodo",
        ".periodo",
        ".contador.periodo",
        ".box-marcador .contador.periodo",
        ".box-marcador .fase",
    ]
    import re
    for sel in q_selectors:
        el = soup.select_one(sel)
        if el and el.text.strip():
            txt = el.text.strip()
            m = re.search(r"(\d+)", txt)
            if m:
                try:
                    quarter = int(m.group(1))
                    break
                except:
                    pass

    # Si no lo encontramos en los selectores, intentar buscar patrones en el HTML
    if quarter is None:
        m = re.search(r"Q\s*(\d)", html)
        if m:
            try:
                quarter = int(m.group(1))
            except:
                quarter = None

    # Normalizar tiempo y cuarto: si no podemos inferirlos, aplicar valores por defecto
    # Intentar extraer el tiempo en formato mm:ss desde el status
    time_str = None
    if status:
        m = re.search(r"(\d{1,2}:\d{2})", status)
        if m:
            time_str = m.group(1)

    if quarter is None:
        # fallback solicitado: cuarto 4
        quarter = 4
    if not time_str:
        # fallback solicitado: 00:00 (si no consigue extraer el contador)
        time_str = "00:00"

    # Marcador
    local_score_el = soup.select_one(".box-marcador .equipo.local .resultado")
    visit_score_el = soup.select_one(".box-marcador .equipo.visitante .resultado")

    local_score = safe_int(local_score_el.text.strip()) if local_score_el else 0
    visit_score = safe_int(visit_score_el.text.strip()) if visit_score_el else 0

    # Extraer nombres de equipos (intentar varios selectores)
    local_name_el = soup.select_one(".box-marcador .equipo.local .nombre a")
    if not local_name_el:
        local_name_el = soup.select_one(".box-marcador .equipo.local .nombre")
    if not local_name_el:
        local_name_el = soup.select_one(".equipo.local .nombre")
    
    visit_name_el = soup.select_one(".box-marcador .equipo.visitante .nombre a")
    if not visit_name_el:
        visit_name_el = soup.select_one(".box-marcador .equipo.visitante .nombre")
    if not visit_name_el:
        visit_name_el = soup.select_one(".equipo.visitante .nombre")
    
    local_name = local_name_el.text.strip() if local_name_el else "LOCAL"
    visit_name = visit_name_el.text.strip() if visit_name_el else "VISITANTE"

    # ============= TABLAS DE JUGADORES (local y visitante) =============
    tbodies = soup.select("h1.titulo-modulo + .responsive-scroll table tbody")[2:4]

    if len(tbodies) < 2:
        print(f"[ERROR] No se encontraron suficientes tablas de boxscore para el partido {partido_id}. Encontrados: {len(tbodies)}")
        # Opcional: guardar HTML para depuración
        debug_path = f"debug_boxscore_{partido_id}.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[INFO] HTML guardado en {debug_path} para inspección.")
        return None

    def parse_team(tbody, team_name, team_score):
        players = []
        for tr in tbody.find_all("tr"):
            # saltar totales
            if "row-total" in tr.get("class", []):
                continue
            if not tr.select_one("td.inicial"):
                continue

            starter = tr.select_one("td.inicial").text.strip() == "*"

            name_el = tr.select_one("td.nombre a")
            name = name_el.text.strip()

            dorsal = tr.select_one("td.dorsal").text.strip()

            # minutos
            min_raw = tr.select_one("td.minutos").text.strip()
            if ":" in min_raw:
                m, s = min_raw.split(":")
                minutes = int(m) + int(s) / 60
            else:
                minutes = safe_int(min_raw)

            t2c, t2i = parse_frac(tr.select_one("td.tiros.dos").text)
            t3c, t3i = parse_frac(tr.select_one("td.tiros.tres").text)
            tlc, tli = parse_frac(tr.select_one("td.tiros.libres").text)

            players.append({
                "name": name,
                "dorsal": dorsal,
                "starter": starter,
                "min": minutes,
                "pts": safe_int(tr.select_one("td.puntos").text),
                "t2c": t2c, "t2i": t2i,
                "t3c": t3c, "t3i": t3i,
                "tlc": tlc, "tli": tli,
                "orb": safe_int(tr.select_one("td.rebotes.ofensivos").text),
                "drb": safe_int(tr.select_one("td.rebotes.defensivos").text),
                "ast": safe_int(tr.select_one("td.asistencias").text),
                "stl": safe_int(tr.select_one("td.recuperaciones").text),
                "to":  safe_int(tr.select_one("td.perdidas").text),
                "pf":  safe_int(tr.select_one("td.faltas.cometidas").text),
                "fd":  safe_int(tr.select_one("td.faltas.recibidas").text)
            })

        return {
            "team": team_name,
            "score": team_score,
            "players": players
        }

    local_data = parse_team(tbodies[0], local_name, local_score)
    visitor_data = parse_team(tbodies[1], visit_name, visit_score)

    return {
        "game_id": partido_id,
        "status": status,
        "quarter": quarter,
        "time": time_str,
        "local": local_data,
        "visitor": visitor_data
    }


# ================================================================
# Test manual
# ================================================================
if __name__ == "__main__":
    driver = init_driver()
    data = scrape_boxscore_live(driver, "2487631")
    driver.quit()
    print(data)
