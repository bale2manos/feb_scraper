#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.web_scraping import init_driver, accept_cookies

# --- Configuración: cambia aquí el ID de partido ---
PARTIDO_ID = "2413612"
BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"
# -----------------------------------------------------

def safe_int(s: str) -> int:
    """Convierte cadena a entero, devuelve 0 si no es válido."""
    try:
        return int(s)
    except:
        return 0

def parse_frac(frac: str) -> tuple[int, int]:
    """Dada 'X/Y' devuelve (X,Y), o (0,0) si falla."""
    m = re.match(r"(\d+)\s*/\s*(\d+)", frac or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0

def scrape_boxscore(driver, partido_id: str):
    driver.get(BASE_PLAY_URL.format(partido_id))
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

    # extraer marcador local/visitante
    wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, ".box-marcador .columna.equipo.local .resultado")
    ))
    
    local_element = driver.find_element(By.CSS_SELECTOR, ".box-marcador .columna.equipo.local .resultado")
    local_score = safe_int(local_element.text)
    
    if not local_score:
        print("⚠️  No se encontró el marcador local.")
        return []    
    
    visit_element = driver.find_element(By.CSS_SELECTOR, ".box-marcador .columna.equipo.visitante .resultado")
    visit_score = safe_int(visit_element.text)
    
    if not visit_score:
        print("⚠️  No se encontró el marcador visitante.")
        return []
        
    # nombre equipo local
    equipo_local = driver.find_element(
        By.CSS_SELECTOR, ".box-marcador .columna.equipo.local .nombre a"
    ).text

    # nombre equipo rival (visitante)
    equipo_rival = driver.find_element(
        By.CSS_SELECTOR, ".box-marcador .columna.equipo.visitante .nombre a"
    ).text
    
    print(f"Partido {partido_id}: {equipo_local} {local_score} - {visit_score} {equipo_rival}")    

    registros = []
    
    # la tabla de estadísticas del rival es la segunda tras su <h1>
    tbodies = driver.find_elements(
        By.CSS_SELECTOR, "h1.titulo-modulo + .responsive-scroll table tbody"
    )
    print(f"[DEBUG] Se encontraron {len(tbodies)} tablas de jugadores.")
    tbodies = tbodies[:2]  # solo considerar las dos primeras tablas (local y rival)

    if len(tbodies) < 2:
        print("⚠️  No se encontraron datos de jugadores.")
        return []
    
    
    jugador_local = True
    for tbody in tbodies:
        if jugador_local:
            equipo = equipo_local
            rival = equipo_rival
            score_equipo = local_score
            score_rival = visit_score
        else:
            equipo = equipo_rival
            rival = equipo_local
            score_equipo = visit_score
            score_rival = local_score
        
        rows = tbody.find_elements(By.TAG_NAME, "tr")[:-1]
        print(f"[DEBUG] Procesando equipo: {equipo}. Tiene {len(rows)} jugadores.")
        
        resultado = "Victoria" if score_equipo > score_rival else "Derrota"

        for tr in rows:
            # Buscar el texto del td con clase "inicial" dentro de este tr
            titular = tr.find_element(By.CSS_SELECTOR, "td.inicial").text
            titular = True if titular.strip() == "*" else False
            dorsal = tr.find_element(By.CSS_SELECTOR, "td.dorsal").text.strip()
            link = tr.find_element(By.CSS_SELECTOR, "td.nombre a")
            jugador = link.text.strip()
            c_param = re.search(r"c=(\d+)", link.get_attribute("href"))
            url_jugador = link.get_attribute("href")
            imagen = f"https://imagenes.feb.es/Foto.aspx?c={c_param.group(1)}" if c_param else ""

            minutos = tr.find_element(By.CSS_SELECTOR, "td.minutos").text.strip() or 0
            puntos = safe_int(tr.find_element(By.CSS_SELECTOR, "td.puntos").text.strip())
            t2c, t2i = parse_frac(tr.find_element(By.CSS_SELECTOR, "td.tiros.dos").text.strip())
            t3c, t3i = parse_frac(tr.find_element(By.CSS_SELECTOR, "td.tiros.tres").text.strip())
            tlc, tli = parse_frac(tr.find_element(By.CSS_SELECTOR, "td.tiros.libres").text.strip())
            reb_of = safe_int(tr.find_element(By.CSS_SELECTOR, "td.rebotes.ofensivos").text.strip())
            reb_def = safe_int(tr.find_element(By.CSS_SELECTOR, "td.rebotes.defensivos").text.strip())
            asist = safe_int(tr.find_element(By.CSS_SELECTOR, "td.asistencias").text.strip())
            recup = safe_int(tr.find_element(By.CSS_SELECTOR, "td.recuperaciones").text.strip())
            perd = safe_int(tr.find_element(By.CSS_SELECTOR, "td.perdidas").text.strip())
            faltas_com = safe_int(tr.find_element(By.CSS_SELECTOR, "td.faltas.cometidas").text.strip())
            faltas_rec = safe_int(tr.find_element(By.CSS_SELECTOR, "td.faltas.recibidas").text.strip())

            registros.append({
                "EQUIPO LOCAL": equipo,
                "EQUIPO RIVAL": rival,
                "RESULTADO": resultado,
                "PTS_EQUIPO": score_equipo,
                "PTS_RIVAL": score_rival,
                "TITULAR": titular,
                "DORSAL": dorsal,
                "JUGADOR": jugador,
                "MINUTOS JUGADOS": minutos,
                "PUNTOS": puntos,
                "T2 CONVERTIDO": t2c,
                "T2 INTENTADO": t2i,
                "T3 CONVERTIDO": t3c,
                "T3 INTENTADO": t3i,
                "TL CONVERTIDOS": tlc,
                "TL INTENTADOS": tli,
                "REB OFFENSIVO": reb_of,
                "REB DEFENSIVO": reb_def,
                "ASISTENCIAS": asist,
                "RECUPEROS": recup,
                "PERDIDAS": perd,
                "FaltasCOMETIDAS": faltas_com,
                "FaltasRECIBIDAS": faltas_rec,
                "IMAGEN": imagen,
                "URL JUGADOR": url_jugador
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
    main()
