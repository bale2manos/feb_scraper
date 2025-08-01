from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService


# -------- CONFIGURACIÓN GLOBAL --------
# -------------- CONFIG --------------
DRIVER_PATH = None  # Si no está en el PATH puedes poner aquí la ruta completa
BASE_URL      = "https://baloncestoenvivo.feb.es/resultados/tercerafeb/3/2024"
TEMPORADA_TXT = "2024/2025"
FASE_TXT      = 'Liga Regular "B-A"'    # prueba sólo la primera fase
JORNADA_IDX   = 5                        # 0-based → 0 = Jornada 1

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

# -------- UTILIDADES WEB DRIVER --------
def init_driver(minimized: bool = True):
    opts = webdriver.ChromeOptions()
    # set a fixed size so elements land where you expect
    opts.add_argument("--window-size=1200,800")
    # start minimized instead of maximized
    if minimized:
        opts.add_argument("--start-minimized")
    else:
        opts.add_argument("--start-maximized")
    # opts.add_argument("--headless=new")  # uncomment for headless

    if DRIVER_PATH:
        service = ChromeService(executable_path=Path(DRIVER_PATH))
        driver = webdriver.Chrome(service=service, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    # as a fallback, immediately minimize via WebDriver API
    if minimized:
        try:
            driver.minimize_window()
        except Exception:
            pass

    return driver

# en utils.py

from selenium.webdriver.common.by import By

def accept_cookies(driver, short_timeout=0.5):
    """
    Cierra el banner de cookies de forma rápida:
     - Busca los botones en root sin waits largos
     - Luego en iframes
     - Finalmente prueba "Rechazar todo"
    """
    texts = ["CONSENTIR TODO", "ACEPTAR TODO", "Acepto", "ACEPTAR"]
    xpaths = [f"//button[normalize-space()='{t}']" for t in texts]

    # 1) Intentar en documento principal
    for xp in xpaths:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            try:
                els[0].click()
                print("✅ Modal cookies cerrado (root)")
            except:
                pass
            return

    # 2) Dentro de iframes
    for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
        driver.switch_to.frame(iframe)
        for xp in xpaths:
            els = driver.find_elements(By.XPATH, xp)
            if els:
                try:
                    els[0].click()
                    print(f"✅ Modal cookies cerrado (iframe id={iframe.get_attribute('id')})")
                except:
                    pass
                driver.switch_to.default_content()
                return
        driver.switch_to.default_content()

    # 3) Rechazar todo (último recurso)
    btns = driver.find_elements(By.XPATH, "//button[normalize-space()='Rechazar todo']")
    if btns:
        try:
            btns[0].click()
            print("✅ Rechazar todo pulsado")
        except:
            pass
        return

    # Si llegamos aquí, nada
    print("ℹ️ No se detectó banner de cookies")
