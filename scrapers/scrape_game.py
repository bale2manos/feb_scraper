#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.web_scraping import init_driver, accept_cookies
from config import BASE_PLAY_URL

# --- Configuración: cambia aquí el ID de partido ---
PARTIDO_ID     = "2413725"
# -----------------------------------------------------

def safe_int(s: str) -> int:
    """Convierte cadena a entero, devuelve 0 si no es válido."""
    try:
        return int(s)
    except:
        return 0

def parse_frac(frac: str) -> tuple[int, int]:
    """Dada 'X/Y' devuelve (X, Y), o (0, 0) si falla."""
    m = re.match(r"(\d+)\s*/\s*(\d+)", frac or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0

def scrape_boxscore(driver, partido_id: str, phase: str = None, jornada: int = None) -> list[dict]:
    url = BASE_PLAY_URL.format(partido_id)
    driver.get(url)
    accept_cookies(driver)

    # quitar posible overlay GDPR
    driver.execute_script("""
        const o = document.querySelector('.stpd_cmp_wrapper');
        if(o) o.remove();
    """)

    wait = WebDriverWait(driver, 15)
    # clicar pestaña "Ficha" (boxscore)
    ficha_tab = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "a.btn-tab[data-action='boxscore']")
    ))
    driver.execute_script("arguments[0].click()", ficha_tab)

    # esperar a que la tabla aparezca
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "h1.titulo-modulo + .responsive-scroll table tbody tr")
    ))
    
    # Esperar un poco para que se cargue completamente
    time.sleep(10)

    # Tomar snapshot del HTML
    html = driver.page_source
    
    # Save it for debugging
    out_dir = "./data/jugadores_per_game"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{partido_id}.html"), "w", encoding="utf-8") as f:
        f.write(html)

    soup = BeautifulSoup(html, 'html.parser')

    # extraer marcador local/visitante
    local_el = soup.select_one(".box-marcador .columna.equipo.local .resultado")
    visit_el = soup.select_one(".box-marcador .columna.equipo.visitante .resultado")
    local_score = safe_int(local_el.text.strip()) if local_el else 0
    visit_score = safe_int(visit_el.text.strip()) if visit_el else 0

    if not local_score or not visit_score:
        print(f"⚠️  No se encontró marcador válido en {url}")
        return []

    equipo_local = soup.select_one(
        ".box-marcador .columna.equipo.local .nombre a"
    ).text.strip()
    equipo_rival = soup.select_one(
        ".box-marcador .columna.equipo.visitante .nombre a"
    ).text.strip()

    print(f"Partido {partido_id}: {equipo_local} {local_score} - {visit_score} {equipo_rival}")

    # obtener primeros dos <tbody> (local y visitante)
    tbodies = soup.select("h1.titulo-modulo + .responsive-scroll table tbody")[2:4]
    if len(tbodies) < 2:
        print("⚠️  No se encontraron datos de jugadores.")
        return []

    registros = []
    jugador_local = True

    for tbody in tbodies:
        if jugador_local:
            equipo       = equipo_local
            rival        = equipo_rival
            pts_equipo   = local_score
            pts_rival    = visit_score
        else:
            equipo       = equipo_rival
            rival        = equipo_local
            pts_equipo   = visit_score
            pts_rival    = local_score

        resultado = "Victoria" if pts_equipo > pts_rival else "Derrota"
        print(f"[DEBUG] Procesando equipo: {equipo}. Tiene {len(tbody.find_all('tr'))} jugadores.")

        for tr in tbody.find_all("tr"):
            # saltar fila de totales y aquellas que no contengan la clase "inicial"
            if "row-total" in tr.get("class", []) or not tr.select_one("td.inicial"):
                continue
            
            # extraer datos
            titular     = tr.select_one("td.inicial").text.strip() == "*"
            dorsal      = tr.select_one("td.dorsal").text.strip()
            link        = tr.select_one("td.nombre a")
            jugador     = link.text.strip()
            href        = link["href"]
            c_param     = re.search(r"c=(\d+)", href)
            imagen      = f"https://imagenes.feb.es/Foto.aspx?c={c_param.group(1)}" if c_param else ""
            url_jug     = href

            minutos_raw     = tr.select_one("td.minutos").text.strip() or "0"
            minutos = int(minutos_raw.split(":")[0]) + int(minutos_raw.split(":")[1]) / 60 if ":" in minutos_raw else safe_int(minutos_raw)
            puntos      = safe_int(tr.select_one("td.puntos").text)
            t2c, t2i    = parse_frac(tr.select_one("td.tiros.dos").text)
            t3c, t3i    = parse_frac(tr.select_one("td.tiros.tres").text)
            tlc, tli    = parse_frac(tr.select_one("td.tiros.libres").text)
            reb_of      = safe_int(tr.select_one("td.rebotes.ofensivos").text)
            reb_def     = safe_int(tr.select_one("td.rebotes.defensivos").text)
            asist       = safe_int(tr.select_one("td.asistencias").text)
            recup       = safe_int(tr.select_one("td.recuperaciones").text)
            perd        = safe_int(tr.select_one("td.perdidas").text)
            falt_com    = safe_int(tr.select_one("td.faltas.cometidas").text)
            falt_rec    = safe_int(tr.select_one("td.faltas.recibidas").text)

            registros.append({
                "FASE":              phase,
                "JORNADA":           jornada,
                "EQUIPO LOCAL":       equipo,
                "EQUIPO RIVAL":       rival,
                "RESULTADO":          resultado,
                "PTS_EQUIPO":         pts_equipo,
                "PTS_RIVAL":          pts_rival,
                "TITULAR":            titular,
                "DORSAL":             dorsal,
                "JUGADOR":            jugador,
                "MINUTOS JUGADOS":    minutos,
                "PUNTOS":             puntos,
                "T2 CONVERTIDO":      t2c,
                "T2 INTENTADO":       t2i,
                "T3 CONVERTIDO":      t3c,
                "T3 INTENTADO":       t3i,
                "TL CONVERTIDOS":     tlc,
                "TL INTENTADOS":      tli,
                "REB OFFENSIVO":      reb_of,
                "REB DEFENSIVO":      reb_def,
                "ASISTENCIAS":        asist,
                "RECUPEROS":          recup,
                "PERDIDAS":           perd,
                "FaltasCOMETIDAS":    falt_com,
                "FaltasRECIBIDAS":    falt_rec,
                "IMAGEN":             imagen,
                "URL JUGADOR":        url_jug
            })

        jugador_local = not jugador_local
    return registros

def main():
    driver = init_driver()
    try:
        print(f"⏳  Descargando partido {PARTIDO_ID}…")
        data = scrape_boxscore(driver, PARTIDO_ID)
    finally:
        driver.quit()

    if not data:
        print(f"⚠️  No hay datos para el partido {PARTIDO_ID}")
        return

    df = pd.DataFrame(data)
    out_dir = "./data/jugadores_per_game"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{PARTIDO_ID}.xlsx")
    df.to_excel(path, index=False)
    print(f"✅  Guardado en {path}")

if __name__ == "__main__":
    init_time = time.time()
    main()
    elapsed = time.time() - init_time
    print(f"⏱️  Tiempo total de ejecución: {elapsed:.2f} segundos")
