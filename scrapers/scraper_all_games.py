# scraper_step3.py
"""
Paso 3 · Extraer TODOS los partidos de todas las jornadas
         para los dos grupos B-A y B-B
Salida: CSV con columnas [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
"""

import re
import time
import csv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.web_scraping import (
    init_driver,
    accept_cookies,
    SELECT_ID_TEMPORADA,
    SELECT_ID_FASE,
    SELECT_ID_JORNADA,
    BASE_URL,
    TEMPORADA_TXT,
)

# --- Configuración ---
PHASES = ['Liga Regular "B-A"', 'Liga Regular "B-B"']
OUT_CSV = "resultados_completos.csv"


def scrape_all():
    driver = init_driver()
    driver.get(BASE_URL)
    accept_cookies(driver)

    wait = WebDriverWait(driver, 15)
    # 1) Seleccionar Temporada una sola vez
    sel_temp = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_TEMPORADA)))
    Select(sel_temp).select_by_visible_text(TEMPORADA_TXT)
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_TEMPORADA} option[selected]"),
        TEMPORADA_TXT
    ))

    all_rows = []

    for fase in PHASES:
        # 2) Seleccionar fase
        sel_fase = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_FASE)))
        Select(sel_fase).select_by_visible_text(fase)
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, f"#{SELECT_ID_FASE} option[selected]"),
            fase
        ))

        print(f"✅ Fase '{fase}' seleccionada y POSTBACK OK")
        
        # 3) Averiguar cuántas jornadas hay en este select
        sel_jor_initial = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
        total_jornadas = len(Select(sel_jor_initial).options)
        
        print(f"ℹ️ Fase '{fase}' tiene {total_jornadas} jornadas")

        for idx in range(total_jornadas):
            # 4) Re-buscar el <select> de jornada para evitar stale
            sel_jor = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
            Select(sel_jor).select_by_index(idx)

            # 5) Esperar a que el título refleje la jornada seleccionada
            wait.until(EC.presence_of_element_located((
                By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid"
            )))
            
            print(f"✅ Jornada {idx+1} seleccionada y POSTBACK OK")
            time.sleep(0.3)  # pequeño margen para que “table” se pinte bien

            # 6) Extraer los partidos
            table = driver.find_element(By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid")
            filas = table.find_elements(By.TAG_NAME, "tr")[1:]
            for tr in filas:
                # Equipos
                eq = tr.find_elements(By.CSS_SELECTOR, "td:nth-child(1) a")
                local, visit = eq[0].text.strip(), eq[1].text.strip()
                # Resultado y ID partido
                res = tr.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
                marcador = res.text.strip()
                pid = re.search(r"p=(\d+)", res.get_attribute("href")).group(1)
                # Resultado por equipo
                pts_l, pts_v = map(int, marcador.split("-"))
                res_l, res_v = ("Gano","Perdio") if pts_l>pts_v else ("Perdio","Gano")
                # Añadimos filas
                all_rows.append([fase, idx+1, pid, 1, local,  visit, res_l])
                all_rows.append([fase, idx+1, pid, 2, visit, local,  res_v])

            print(f"✅ {fase} — Jornada {idx+1}/{total_jornadas} procesada")

    driver.quit()
    return all_rows


def save_csv(rows):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Fase","Jornada","IdPartido","IdEquipo","Local","Rival","Resultado"])
        w.writerows(rows)
    print(f"✅ Guardado CSV completo en: {OUT_CSV}")


if __name__ == "__main__":
    data = scrape_all()
    save_csv(data)
