#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integración de extracción de partidos y boxscores:
  - Recorre fases y jornadas para obtener IDs de partido
  - Para cada partido, descarga el boxscore de jugadores
  - Genera un único Excel con todas las fases + jornadas + datos de boxscore
"""

import os
import re
import sys
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .scrape_game import scrape_boxscore
from utils.web_scraping import (
    init_driver,
    accept_cookies,
)
from config import (
    TEMPORADA_TXT,
    FASES_PRINCIPALES as PHASES,
    OUTPUT_PHASES_FILE as OUTPUT_FILE,
    BASE_PLAY_URL,
    MAX_WORKERS,
    SELECT_ID_TEMPORADA,
    SELECT_ID_FASE,
    SELECT_ID_JORNADA,
    WEBDRIVER_TIMEOUT
)
from utils.web_scraping import get_current_base_url

# --- Configuración específica del scraper ---
RETRY_COUNT   = 3
RETRY_DELAY   = 2  # segundos entre reintentos

# Variables globales para filtros
SELECTED_JORNADAS = None  # Lista de jornadas a procesar (None = todas)

# Thread-safe locks
data_lock = Lock()
error_lock = Lock()


def get_all_match_ids():
    """Extrae la lista de (fase, jornada, partido_id) para todas las jornadas de cada fase."""
    driver = init_driver()
    base_url = get_current_base_url()  # Obtener URL dinámicamente
    driver.get(base_url)
    accept_cookies(driver)

    wait = WebDriverWait(driver, 15)
    # Seleccionar temporada
    sel_temp = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_TEMPORADA)))
    Select(sel_temp).select_by_visible_text(TEMPORADA_TXT)
    wait.until(EC.text_to_be_present_in_element(
        (By.CSS_SELECTOR, f"#{SELECT_ID_TEMPORADA} option[selected]"),
        TEMPORADA_TXT
    ))

    matches = []
    for fase in PHASES:
        # Seleccionar fase
        sel_fase = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_FASE)))
        Select(sel_fase).select_by_visible_text(fase)
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, f"#{SELECT_ID_FASE} option[selected]"),
            fase
        ))
        print(f"[+] Fase seleccionada: {fase}")

        # Averiguar número de jornadas
        sel_jor_ini = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
        total_jornadas = len(Select(sel_jor_ini).options)
        print(f"    → {total_jornadas} jornadas detectadas")

        # Determinar qué jornadas procesar
        if SELECTED_JORNADAS is not None:
            # Filtrar solo las jornadas seleccionadas (convertir a índices 0-based)
            jornadas_to_process = [j-1 for j in SELECTED_JORNADAS if 1 <= j <= total_jornadas]
            print(f"    → Filtrando {len(jornadas_to_process)} jornadas específicas: {[j+1 for j in jornadas_to_process]}")
        else:
            # Procesar todas las jornadas
            jornadas_to_process = list(range(total_jornadas))
            print(f"    → Procesando todas las {total_jornadas} jornadas")

        for idx in jornadas_to_process:
            # Seleccionar jornada (re-buscar para evitar stale elements)
            sel_jor = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
            Select(sel_jor).select_by_index(idx)
            wait.until(EC.presence_of_element_located((
                By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid"
            )))
            time.sleep(0.3)

            # Extraer IDs de partido de la tabla
            table = driver.find_element(By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid")
            filas = table.find_elements(By.TAG_NAME, "tr")[1:]
            for tr in filas:
                href = tr.find_element(By.CSS_SELECTOR, "td:nth-child(2) a").get_attribute("href")
                pid = re.search(r"p=(\d+)", href).group(1)
                matches.append({
                    "fase":    fase,
                    "jornada": idx + 1,
                    "pid":     pid
                })
            print(f"    → Jornada {idx+1}/{total_jornadas} procesada")

    driver.quit()
    return matches


def safe_int(s: str) -> int:
    try:
        return int(s)
    except:
        return 0


def parse_frac(frac: str) -> tuple[int, int]:
    m = re.match(r"(\d+)\s*/\s*(\d+)", frac or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def process_match(match_data, all_data, errors):
    """
    Procesa un partido individual con reintentos.
    Función thread-safe que maneja su propio driver.
    """
    driver = None
    try:
        driver = init_driver()
        
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                recs = scrape_boxscore(driver, match_data["pid"], match_data["fase"], match_data["jornada"])
                if not recs:
                    raise ValueError("No se extrajeron datos")

                total_minutes = sum(float(r.get("MINUTOS JUGADOS", 0)) for r in recs)
                if total_minutes < 400:  # Un partido debería tener mínimo 400 minutos total
                    raise ValueError(f"Minutos totales sospechosos: {total_minutes}")
                
                # Thread-safe data append
                with data_lock:
                    all_data.extend(recs)
                
                print(f"✅ OK: {match_data['fase']} J{match_data['jornada']} → {len(recs)} registros")
                return True  # Success
                
            except Exception as e:
                print(f"⚠️  Error en {match_data['pid']} (intento {attempt}/{RETRY_COUNT}): {e}")
                if attempt < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)
                else:
                    # Thread-safe error append
                    with error_lock:
                        errors.append((match_data, str(e)))
                    print(f"❌ Falló definitivamente: {match_data['fase']} J{match_data['jornada']}")
                    return False
    finally:
        if driver:
            driver.quit()
    
    return False

def main():
    print("🚀 Iniciando scraper multihilo con extracción de boxscores...")
    print("=" * 70)
    
    # 1) Obtener lista de partidos
    print("📋 Obteniendo lista de partidos...")
    all_matches = get_all_match_ids()
    print(f"✅ {len(all_matches)} partidos encontrados en total.")
    
    # 2) Scrape boxscores con threads paralelos
    print(f"⚡ Iniciando procesamiento paralelo con {MAX_WORKERS} threads...")
    start_time = time.time()
    
    all_data = []
    errors = []
    completed_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_match = {
            executor.submit(process_match, match, all_data, errors): match 
            for match in all_matches
        }
        
        # Process completed tasks
        for future in as_completed(future_to_match):
            completed_count += 1
            match = future_to_match[future]
            
            try:
                success = future.result()
                if success:
                    print(f"📊 Progreso: {completed_count}/{len(all_matches)} partidos procesados")
                else:
                    print(f"⚠️  Partido fallido: {completed_count}/{len(all_matches)}")
            except Exception as e:
                with error_lock:
                    errors.append((match, str(e)))
                print(f"❌ Error crítico en partido {match['pid']}: {e}")
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # 3) Guardar todo en un solo Excel
    print("\n💾 Guardando datos...")
    df = pd.DataFrame(all_data)
    df.to_excel(OUTPUT_FILE, index=False)
    
    # 4) Mostrar resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL:")
    print(f"   🎯 Total partidos procesados: {len(all_matches)}")
    print(f"   ✅ Partidos exitosos: {len(all_matches) - len(errors)}")
    print(f"   ❌ Partidos con errores: {len(errors)}")
    print(f"   📝 Total registros extraídos: {len(all_data)}")
    print(f"   ⏱️  Tiempo total: {processing_time:.2f} segundos")
    print(f"   ⚡ Velocidad promedio: {len(all_matches)/processing_time:.2f} partidos/segundo")
    print(f"   💾 Archivo generado: {OUTPUT_FILE}")
    print("=" * 70)
    
    # 5) Log de errores
    if errors:
        error_file = "errors.log"
        with open(error_file, "w", encoding="utf-8") as f:
            for m, err in errors:
                f.write(f"{m['fase']} J{m['jornada']} PID={m['pid']} → {err}\n")
        print(f"⚠️  {len(errors)} errores registrados en {error_file}")
    else:
        print("🎉 ¡Todos los partidos procesados exitosamente!")


def main_old_single_thread():
    """Versión original con un solo thread - mantenida para referencia."""
    # 1) Obtener lista de partidos
    all_matches = get_all_match_ids()
    print(f"[!] {len(all_matches)} partidos encontrados en total.")

    # 2) Scrape boxscores con reintentos
    driver = init_driver()
    all_data = []
    errors = []

    for m in all_matches:
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                recs = scrape_boxscore(driver, m["pid"], m["fase"], m["jornada"])
                all_data.extend(recs)
                print(f"OK: {m['fase']} J{m['jornada']} → {len(recs)} registros")
                break
            except Exception as e:
                print(f"Error en {m['pid']} (intento {attempt}): {e}")
                time.sleep(RETRY_DELAY)
                if attempt == RETRY_COUNT:
                    errors.append((m, str(e)))

    driver.quit()

    # 3) Guardar todo en un solo Excel
    df = pd.DataFrame(all_data)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"[+] Excel generado: {OUTPUT_FILE}")

    # 4) Log de errores
    if errors:
        with open("errors.log", "w", encoding="utf-8") as f:
            for m, err in errors:
                f.write(f"{m['fase']} J{m['jornada']} PID={m['pid']} → {err}\n")
        print(f"[!] {len(errors)} errores registrados en errors.log")


if __name__ == "__main__":
    main()
