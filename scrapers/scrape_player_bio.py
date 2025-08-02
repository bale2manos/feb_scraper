import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.web_scraping import accept_cookies, init_driver

def obtener_datos_jugador(driver, url, timeout=15):
    """
    Navega a la URL de un jugador en baloncestoenvivo.feb.es y extrae:
      - JUGADOR
      - FECHA NACIMIENTO (solo fecha dd/mm/yyyy)
      - NACIONALIDAD

    Args:
        driver: instancia de Selenium WebDriver ya inicializada.
        url (str): URL de la ficha del jugador.
        timeout (int): segundos de espera máxima para que cargue el contenido.

    Returns:
        dict: {
            'NOMBRE': str,
            'FECHA NACIMIENTO': str,
            'NACIONALIDAD': str
        }
    """
    driver.get(url)
    accept_cookies(driver)

    # Quitar overlay GDPR si existe
    driver.execute_script("""
        const o = document.querySelector('.stpd_cmp_wrapper');
        if(o) o.remove();
    """)

    wait = WebDriverWait(driver, timeout)
    contenedor = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "div.box-jugador")
    ))

    # Nombre
    nombre = contenedor.find_element(
        By.CSS_SELECTOR,
        ".jugador .nombre"
    ).text.strip()

    # Fecha nacimiento raw
    raw_fecha = contenedor.find_element(
        By.XPATH,
        ".//div[@class='info']//span[@class='label' and normalize-space(text())='Fecha Nacimiento']/following-sibling::span"
    ).text.strip()
    # Extraer solo la parte dd/mm/yyyy
    m = re.search(r'\d{2}/\d{2}/\d{4}', raw_fecha)
    fecha_nac = m.group(0) if m else raw_fecha

    # Nacionalidad
    nacionalidad = contenedor.find_element(
        By.XPATH,
        ".//div[@class='info']//span[@id and normalize-space(text())='Nacionalidad']/following-sibling::span"
    ).text.strip()
 

    return {
        'NOMBRE': nombre,
        'FECHA NACIMIENTO': fecha_nac,
        'NACIONALIDAD': nacionalidad
    }
    
if __name__ == "__main__":
    # Inicializar WebDriver (ejemplo con Chrome)
    driver = init_driver()
    try:
        url_jugador = "https://baloncestoenvivo.feb.es/Jugador.aspx?i=951077&c=2565811&med=0"  # Reemplaza con una URL válida
        datos = obtener_datos_jugador(driver, url_jugador)
        print(datos)
    finally:
        driver.quit()