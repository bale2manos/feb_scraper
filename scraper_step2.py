# scraper_step2.py
"""
Paso 2 · Extraer todos los partidos de una jornada:
  - Usa utilidades de `utils.py`
  - Selecciona temporada, fase y jornada
  - Lee la tabla de resultados
  - Genera una lista de filas: [IdPartido, IdEquipo, Equipo, Rival, Resultado]
"""

import re
import time
import csv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importar utilidades
from utils import (
    init_driver,
    accept_cookies,
    SELECT_ID_TEMPORADA,
    SELECT_ID_FASE,
    SELECT_ID_JORNADA,
    BASE_URL,
    TEMPORADA_TXT,
    FASE_TXT,
    JORNADA_IDX,
)

# Nombre del CSV de salida (opcional)
OUT_CSV = "resultados_jornada.csv"


def scrape_jornada():
    driver = init_driver()
    driver.get(BASE_URL)
    accept_cookies(driver)

    wait = WebDriverWait(driver, 15)

    # Seleccionar Temporada
    sel_temp = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_TEMPORADA)))
    Select(sel_temp).select_by_visible_text(TEMPORADA_TXT)
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_TEMPORADA} option[selected]"),
        TEMPORADA_TXT
    ))

    # Seleccionar Fase
    sel_fase = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_FASE)))
    Select(sel_fase).select_by_visible_text(FASE_TXT)
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_FASE} option[selected]"),
        FASE_TXT
    ))

    # Seleccionar Jornada
    sel_jor = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
    Select(sel_jor).select_by_index(JORNADA_IDX)
    wait.until(EC.presence_of_element_located((
        By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid"
    )))
    
    print(f"✅ Jornada {JORNADA_IDX+1} seleccionada y POSTBACK OK")
    
    time.sleep(1)

    print("Vamos a extraer los partidos de la jornada...")
    
    # Extraer partidos
    rows = []
    table = driver.find_element(By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid")
    trs = table.find_elements(By.TAG_NAME, "tr")[1:]

    for tr in trs:
        # Equipos
        eq_links = tr.find_elements(By.CSS_SELECTOR, "td:nth-child(1) a")
        local, visit = eq_links[0].text.strip(), eq_links[1].text.strip()

        # Resultado e ID partido
        res_link = tr.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
        marcador = res_link.text.strip()
        partido_id = re.search(r"p=(\d+)", res_link.get_attribute("href")).group(1)

        # Calcular ganador
        pts_local, pts_visit = map(int, marcador.split("-"))
        if pts_local > pts_visit:
            res_local, res_visit = "Gano", "Perdio"
        else:
            res_local, res_visit = "Perdio", "Gano"

        # Dos filas por partido
        rows.append([partido_id, 1, local,     visit,    res_local])
        rows.append([partido_id, 2, visit,     local,    res_visit])

    driver.quit()
    return rows


def save_csv(rows):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["IdPartido","IdEquipo","Local","Rival","Resultado"])
        writer.writerows(rows)
    print(f"✅ CSV guardado como {OUT_CSV}")


def main():
    rows = scrape_jornada()
    for r in rows:
        print(r)
    save_csv(rows)


if __name__ == "__main__":
    main()
