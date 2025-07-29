# scraper_step1.py
"""
Paso 1 · Prueba de Selenium:
  - Abre la página de resultados de la FEB
  - Cierra el modal de cookies
  - Selecciona la temporada 2024/2025
  - Selecciona la fase “Liga Regular B-A”
  - Selecciona la jornada 1
  - Verifica cada postback antes de continuar
"""

import time
from pathlib import Path
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# -------------- CONFIG --------------
DRIVER_PATH = None  # Si no está en el PATH puedes poner aquí la ruta completa
BASE_URL      = "https://baloncestoenvivo.feb.es/resultados/tercerafeb/3/2024"
TEMPORADA_TXT = "2024/2025"
FASE_TXT      = 'Liga Regular "B-A"'    # prueba sólo la primera fase
JORNADA_IDX   = 1                        # 0-based → 0 = Jornada 1

# IDs reales en el HTML
SELECT_ID_TEMPORADA = "_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"
SELECT_ID_FASE      = "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"
SELECT_ID_JORNADA   = "_ctl0_MainContentPlaceHolderMaster_jornadasDropDownList"

# XPath del botón de “CONSENTIR TODO”
COOKIE_BTN_XPATH = (
    "//button[normalize-space()='CONSENTIR TODO' or "
    "normalize-space()='ACEPTAR TODO' or "
    "normalize-space()='Acepto']"
)

# -------------- HELPERS --------------

def init_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    # opts.add_argument("--headless=new")  # descomentar para headless
    if DRIVER_PATH:
        return webdriver.Chrome(
            service=webdriver.ChromeService(executable_path=Path(DRIVER_PATH)),
            options=opts
        )
    else:
        return webdriver.Chrome(options=opts)

def accept_cookies(driver, timeout=5):
    """
    Cierra el modal de cookies intentando en root y en iframes,
    probando varios textos y selectores.
    """
    texts = ["CONSENTIR TODO", "ACEPTAR TODO", "Acepto", "ACEPTAR"]
    xpaths = [f"//button[normalize-space()='{t}']" for t in texts]

    def try_click(by, locator):
        try:
            el = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, locator)))
            el.click()
            return True
        except Exception:
            return False

    # 1) Intentar en documento principal
    for xp in xpaths:
        if try_click(By.XPATH, xp):
            print("✅ Modal cookies cerrado (root)")
            return

    # 2) Intentar dentro de iframes
    for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
        driver.switch_to.frame(iframe)
        for xp in xpaths:
            if try_click(By.XPATH, xp):
                print(f"✅ Modal cookies cerrado (iframe id={iframe.get_attribute('id')})")
                driver.switch_to.default_content()
                return
        driver.switch_to.default_content()

    # 3) Por si hay un botón “Rechazar todo”
    if try_click(By.XPATH, "//button[normalize-space()='Rechazar todo']"):
        print("✅ Rechazar todo pulsado")

    # Si llegamos aquí, no se encontró
    print("ℹ️ No se detectó banner de cookies")


# -------------- MAIN --------------

def main():
    driver = init_driver()
    driver.get(BASE_URL)

    # cerrar modal de cookies
    accept_cookies(driver)
    time.sleep(1)

    wait = WebDriverWait(driver, 15)

    # — Seleccionar temporada —
    sel_temp = wait.until(EC.presence_of_element_located(
        (By.ID, SELECT_ID_TEMPORADA)
    ))
    Select(sel_temp).select_by_visible_text(TEMPORADA_TXT)
    # esperamos a que el option marcado tenga el texto deseado
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_TEMPORADA} option[selected]"),
        TEMPORADA_TXT
    ))
    print("✅ Temporada seleccionada y POSTBACK OK")

    # — Seleccionar fase —
    sel_fase = wait.until(EC.presence_of_element_located(
        (By.ID, SELECT_ID_FASE)
    ))
    Select(sel_fase).select_by_visible_text(FASE_TXT)
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_FASE} option[selected]"),
        FASE_TXT
    ))
    print(f"✅ Fase '{FASE_TXT}' seleccionada y POSTBACK OK")

    # — Seleccionar jornada 1 —
    sel_jor = wait.until(EC.presence_of_element_located(
        (By.ID, SELECT_ID_JORNADA)
    ))
    Select(sel_jor).select_by_index(JORNADA_IDX)
    # esperamos a que el título de la sección muestre "Resultados Jornada 1"
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, "h1.titulo-modulo"),
        "Resultados Jornada 1"
    ))
    print("✅ Jornada 1 seleccionada y POSTBACK OK")

    # dejar unos segundos para que lo veas en pantalla
    time.sleep(5)
    print("🌐 URL final:", driver.current_url)

    driver.quit()
    print("🚪 Navegador cerrado")

if __name__ == "__main__":
    main()
