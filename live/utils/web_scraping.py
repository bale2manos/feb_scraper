from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService

# Importar configuración centralizada
from utils.config import (
    DRIVER_PATH,
    BASE_URL as CONFIG_BASE_URL,  # Renombramos para evitar confusión
    TEMPORADA_TXT,
    FASE_DEFAULT as FASE_TXT,
    JORNADA_DEFAULT_IDX as JORNADA_IDX,
    SELECT_ID_TEMPORADA,
    SELECT_ID_FASE,
    SELECT_ID_JORNADA,
    COOKIE_BTN_XPATH,
    WEBDRIVER_TIMEOUT
)

# Variable global dinámica para BASE_URL
BASE_URL = CONFIG_BASE_URL

def get_current_base_url():
    """Obtiene la URL base actual (puede ser cambiada dinámicamente)."""
    return BASE_URL

def set_base_url(new_url):
    """Cambia la URL base dinámicamente."""
    global BASE_URL
    BASE_URL = new_url

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

def accept_cookies(driver, short_timeout=0.5):
    """
    Cierra el banner de cookies de forma rápida:
     - Busca los botones en root sin waits largos
     - Luego en iframes
     - Finalmente prueba "Rechazar todo"
    """
    texts = ["CONSENTIR TODO", "ACEPTAR TODO", "Acepto", "ACEPTAR"]
    xpaths = [f"//button[normalize-space()='{t}']" for t in texts]

    # 1) Root level (sin timeout largo)
    for xpath in xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xpath)
            for elem in elems:
                if elem.is_displayed() and elem.is_enabled():
                    elem.click()
                    return True
        except Exception:
            continue

    # 2) En iframes
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes[:3]:  # máximo 3 iframes
            try:
                driver.switch_to.frame(iframe)
                for xpath in xpaths:
                    try:
                        elems = driver.find_elements(By.XPATH, xpath)
                        for elem in elems:
                            if elem.is_displayed() and elem.is_enabled():
                                elem.click()
                                driver.switch_to.default_content()
                                return True
                    except Exception:
                        continue
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
                continue
    except Exception:
        pass

    # 3) Probar "Rechazar todo"
    reject_xpaths = ["//button[normalize-space()='RECHAZAR TODO']",
                     "//button[normalize-space()='Rechazar todo']"]
    for xpath in reject_xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xpath)
            for elem in elems:
                if elem.is_displayed() and elem.is_enabled():
                    elem.click()
                    return True
        except Exception:
            continue

    return False