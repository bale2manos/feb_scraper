# -*- coding: utf-8 -*-
"""
App de Scraping FEB UNIFICADO - Interfaz Streamlit
==================================================

Aplica        # Guardar valores originales para restauración
        original_temporada = web_scraping.TEMPORADA_TXT
        original_phases = scraper_all_games.PHASES
        original_web_base_url = web_scraping.get_current_base_url()  # Usar función dinámica
        
        # Configurar URL según la liga seleccionada
        year = int(selected_season.split("/")[0])
        liga_url = get_liga_url(selected_league, year)
        
        # Actualizar configuración
        web_scraping.set_base_url(liga_url)  # Usar función dinámicagable para ejecutar pipeline UNIFICADO de scraping FEB.
Permite a usuarios no expertos seleccionar temporadas, fases y jornadas
de forma intuitiva.

CARACTERÍSTICAS PRINCIPALES:
- Pipeline UNIFICADO (máxima eficiencia: 1 acceso por partido)
- Soporte para filtrado de jornadas específicas
- Nombres de archivo automáticos con sufijo de jornadas (jX_Y_Z)
- Interface optimizada para mejor experiencia de usuario
"""

import streamlit as st
import pandas as pd
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import threading
import queue
from typing import List, Optional

# Importar configuración centralizada
from config import (
    TEMPORADAS_DISPONIBLES,
    LIGAS_DISPONIBLES,
    LIGA_DEFAULT,
    get_liga_fases,
    get_liga_url,
    DATA_DIR,
    format_season_short
)

# Importar utilidades para nombres de archivo con jornadas
from utils.filename_utils import (
    generate_all_filenames_with_jornadas,
    format_jornadas_display,
    get_jornadas_suffix,
    get_liga_short
)

# Configuración de la página
st.set_page_config(
    page_title="🚀 Scraper FEB UNIFICADO",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_default_phases_for_league(league: str, available_phases: list) -> list:
    """
    Obtiene las fases por defecto apropiadas para una liga específica.
    """
    if not available_phases:
        return []
    
    league_defaults = {
        "Primera FEB": ["Liga Regular Único"],
        "Segunda FEB": ["Liga Regular \"ESTE\"", "Liga Regular \"OESTE\""],
        "Tercera FEB": ["Liga Regular \"B-A\"", "Liga Regular \"B-B\""]
    }
    
    if league in league_defaults:
        preferred_phases = league_defaults[league]
        valid_defaults = [phase for phase in preferred_phases if phase in available_phases]
        if valid_defaults:
            return valid_defaults
    
    if len(available_phases) <= 2:
        return available_phases
    else:
        return available_phases[:2]

def check_selenium_installation():
    """Verifica si selenium y chromedriver están disponibles."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
        return True, "✅ Selenium y ChromeDriver funcionando correctamente"
    except Exception as e:
        return False, f"❌ Error con Selenium/ChromeDriver: {str(e)}"

def check_dependencies():
    """Verifica todas las dependencias necesarias."""
    missing_deps = []
    
    try:
        import selenium
    except ImportError:
        missing_deps.append("selenium")
    
    try:
        import pandas
    except ImportError:
        missing_deps.append("pandas")
    
    try:
        from utils.unified_scraper_integrated import main_unified_scraper
        from utils.aggregate_players_integrated import aggregate_players_main
        from utils.aggregate_teams_integrated import aggregate_teams_main
    except ImportError as e:
        missing_deps.append(f"Módulos de scraping: {str(e)}")
    
    return missing_deps

def run_unified_scraper_thread(
    selected_season: str, 
    selected_phases: List[str], 
    selected_league: str, 
    selected_jornadas: Optional[List[int]], 
    output_queue: queue.Queue
):
    """
    Ejecuta el scraper UNIFICADO completo en un hilo separado.
    """
    original_temporada = None
    original_phases = None
    original_web_base_url = None
    
    try:
        # Importar módulos necesarios
        sys.path.append(str(Path(__file__).parent))
        from utils.unified_scraper_integrated import main_unified_scraper
        from utils import web_scraping
        from utils.aggregate_players_integrated import aggregate_players_main
        from utils.aggregate_teams_integrated import aggregate_teams_main
        from scrapers import scraper_all_games
        from config import get_liga_url
        
        # Guardar valores originales para restauración
        original_temporada = web_scraping.TEMPORADA_TXT
        original_phases = scraper_all_games.PHASES
        original_web_base_url = web_scraping.get_current_base_url()  # Usar función dinámica
        
        # Configurar URL según la liga seleccionada
        year = int(selected_season.split("/")[0])
        liga_url = get_liga_url(selected_league, year)
        
        # Actualizar configuración
        if hasattr(web_scraping, 'BASE_URL'):
            web_scraping.BASE_URL = liga_url
        
        web_scraping.TEMPORADA_TXT = selected_season
        scraper_all_games.PHASES = selected_phases
        
        output_queue.put(("info", f"📅 Temporada: {selected_season}"))
        output_queue.put(("info", f"🏀 Liga: {selected_league}"))
        output_queue.put(("info", f"📋 Fases: {len(selected_phases)} seleccionadas"))
        
        if selected_jornadas:
            output_queue.put(("info", f"📅 Jornadas específicas: {format_jornadas_display(selected_jornadas)}"))
        else:
            output_queue.put(("info", f"📅 Procesando todas las jornadas disponibles"))
        
        # Generar nombres de archivos con sufijo de jornadas
        season_short = format_season_short(selected_season)
        liga_short = get_liga_short(selected_league)
        
        filenames = generate_all_filenames_with_jornadas(
            str(DATA_DIR), 
            season_short, 
            liga_short, 
            selected_jornadas
        )
        
        # Rutas completas
        boxscores_path = filenames["boxscores"]
        assists_path = filenames["assists"] 
        clutch_data_path = filenames["clutch_data"]
        clutch_lineups_path = filenames["clutch_lineups"]
        clutch_aggregated_path = filenames["clutch_aggregated"]
        players_path = filenames["players"]
        teams_path = filenames["teams"]
        
        # Crear directorio de datos si no existe
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # === PIPELINE UNIFICADO: EXTRACCIÓN COMPLETA ===
        output_queue.put(("info", f"🚀⚡ INICIANDO PIPELINE UNIFICADO - Máxima eficiencia"))
        output_queue.put(("info", f"🎯 Extractores: Boxscores + Asistencias + Clutch + Lineups"))
        output_queue.put(("info", f"⚡ Beneficio: 1 acceso por partido (3x más rápido)"))
        
        def unified_callback(msg_type, message):
            output_queue.put((msg_type, message))
        
        # Ejecutar scraper unificado
        boxscores_df, assists_df, clutch_data_df, clutch_lineups_df = main_unified_scraper(
            boxscores_path,
            assists_path, 
            clutch_data_path, 
            clutch_lineups_path, 
            unified_callback,
            temporada=selected_season, 
            liga=selected_league, 
            fases=selected_phases,
            jornadas=selected_jornadas
        )
        
        if boxscores_df is not None:
            output_queue.put(("success", f"🚀⚡ PIPELINE UNIFICADO COMPLETADO"))
            output_queue.put(("success", f"📊 Extraído: Boxscores ({len(boxscores_df)}), Asistencias ({len(assists_df)}), Clutch ({len(clutch_data_df)}), Lineups ({len(clutch_lineups_df)})"))
        else:
            output_queue.put(("error", f"❌ Error en pipeline unificado"))
            return
        
        # === AGREGACIÓN DE JUGADORES ===
        output_queue.put(("info", f"🧑‍🤝‍🧑 AGREGACIÓN: Procesando jugadores"))
        
        def players_callback(msg_type, message):
            output_queue.put((msg_type, message))
        
        players_df = aggregate_players_main(
            boxscores_path, 
            players_path, 
            players_callback
        )
        
        if players_df is not None:
            output_queue.put(("success", f"✅ JUGADORES AGREGADOS: {len(players_df)} registros"))
        else:
            output_queue.put(("error", f"❌ Error en agregación de jugadores"))
            return
        
        # === AGREGACIÓN DE EQUIPOS ===
        output_queue.put(("info", f"🏀 AGREGACIÓN: Procesando equipos"))
        
        def teams_callback(msg_type, message):
            output_queue.put((msg_type, message))
        
        games_df, teams_df = aggregate_teams_main(
            boxscores_path,
            players_path.replace('.xlsx', '_games.xlsx'),
            teams_path,
            teams_callback
        )
        
        if games_df is not None and teams_df is not None:
            output_queue.put(("success", f"✅ EQUIPOS AGREGADOS: {len(teams_df)} equipos, {len(games_df)} partidos"))
        else:
            output_queue.put(("error", f"❌ Error en agregación de equipos"))
            return
        
        # === GENERACIÓN DE ESTADÍSTICAS CLUTCH AGREGADAS ===
        output_queue.put(("info", f"🔥 CLUTCH AGGREGATED: Agregando estadísticas por jugador"))
        
        def clutch_aggregated_callback(msg_type, message):
            output_queue.put((msg_type, message))
        
        # Importar y ejecutar agregación de estadísticas clutch
        from utils.aggregate_players_clutch import aggregate_clutch_from_file
        
        # Ejecutar agregación de estadísticas clutch
        clutch_aggregated_df = aggregate_clutch_from_file(
            clutch_data_path,
            clutch_aggregated_path,
            clutch_aggregated_callback
        )
        
        if clutch_aggregated_df is not None and not clutch_aggregated_df.empty:
            output_queue.put(("success", f"✅ CLUTCH AGGREGATED: {len(clutch_aggregated_df)} jugadores agregados"))
        else:
            output_queue.put(("warning", f"⚠️ CLUTCH AGGREGATED: No se generaron estadísticas (puede ser normal si no hay datos clutch)"))
        
        # === FINALIZACIÓN ===
        output_queue.put(("success", f"🎉 PIPELINE UNIFICADO COMPLETADO - Máxima eficiencia alcanzada"))
        output_queue.put(("success", f"📊 Archivos generados con sufijo de jornadas:"))
        
        for key, path in filenames.items():
            filename = os.path.basename(path)
            output_queue.put(("success", f"   • {filename}"))
        
        # Enviar archivos para descarga
        output_queue.put(("files", [
            boxscores_path,
            assists_path,
            clutch_data_path,
            clutch_lineups_path,
            players_path,
            teams_path,
            clutch_aggregated_path
        ]))
        
        # Restaurar valores originales
        if original_temporada is not None:
            web_scraping.TEMPORADA_TXT = original_temporada
        if original_phases is not None:
            scraper_all_games.PHASES = original_phases
        if original_web_base_url is not None:
            web_scraping.set_base_url(original_web_base_url)  # Usar función dinámica
        
    except Exception as e:
        # Restaurar valores originales también en caso de error
        try:
            if 'original_temporada' in locals() and original_temporada is not None:
                web_scraping.TEMPORADA_TXT = original_temporada
            if 'original_phases' in locals() and original_phases is not None:
                scraper_all_games.PHASES = original_phases
            if 'original_web_base_url' in locals() and original_web_base_url is not None:
                web_scraping.set_base_url(original_web_base_url)  # Usar función dinámica
        except:
            pass
        output_queue.put(("error", f"❌ Error durante el proceso: {str(e)}"))

def main():
    st.title("🚀 Scraper FEB UNIFICADO - Pipeline Máxima Eficiencia")
    st.markdown("""
    Esta aplicación ejecuta un **pipeline UNIFICADO de máxima eficiencia** para extraer y procesar datos de baloncesto 
    de la Federación Española de Baloncesto:
    
    **🚀⚡ PIPELINE UNIFICADO:** Extracción completa (Boxscores + Asistencias + Clutch + Lineups)  
    **📊 AGREGACIONES:** Procesamiento de jugadores y equipos  
    **🎯 OPTIMIZACIÓN:** 1 acceso por partido (3x más rápido)  
    **📅 JORNADAS:** Filtrado opcional por jornadas específicas  
    **📝 ARCHIVOS:** Nombres automáticos con sufijo de jornadas (jX_Y_Z)  
    
    Todos los datos se procesan automáticamente y se generan **6 archivos Excel** listos para análisis.
    """)
    
    # Sidebar para configuración
    st.sidebar.header("⚙️ Configuración")
    
    # Verificación de dependencias
    st.sidebar.subheader("🔍 Estado del Sistema")
    
    missing_deps = check_dependencies()
    if missing_deps:
        st.sidebar.error("❌ Dependencias faltantes:")
        for dep in missing_deps:
            st.sidebar.write(f"- {dep}")
        st.stop()
    else:
        st.sidebar.success("✅ Todas las dependencias están instaladas")
    
    # Verificar Selenium
    selenium_ok, selenium_msg = check_selenium_installation()
    if selenium_ok:
        st.sidebar.success(selenium_msg)
    else:
        st.sidebar.error(selenium_msg)
        st.sidebar.info("💡 Para instalar ChromeDriver: https://chromedriver.chromium.org/")
        if not selenium_ok:
            st.stop()
    
    # Selección de temporada
    st.sidebar.subheader("📅 Selección de Temporada")
    selected_season = st.sidebar.selectbox(
        "Temporada:",
        TEMPORADAS_DISPONIBLES,
        index=len(TEMPORADAS_DISPONIBLES)-1,
        help="Selecciona la temporada de la cual extraer datos"
    )
    
    # Selección de liga
    st.sidebar.subheader("🏀 Selección de Liga")
    selected_league = st.sidebar.selectbox(
        "Liga:",
        list(LIGAS_DISPONIBLES.keys()),
        index=list(LIGAS_DISPONIBLES.keys()).index(LIGA_DEFAULT),
        help="Selecciona la liga de la cual extraer datos"
    )
    
    # Obtener fases disponibles para la liga seleccionada
    available_phases = get_liga_fases(selected_league)
    
    # Selección de fases
    st.sidebar.subheader("🏆 Selección de Fases")
    st.sidebar.info(f"📋 Liga: **{selected_league}**\n\n🎯 Fases disponibles: {len(available_phases)}")
    
    # Para Tercera FEB, mantener la lógica existente
    if selected_league == "Tercera FEB":
        select_all_main = st.sidebar.checkbox(
            "Seleccionar fases principales (B-A, B-B)",
            help="Selecciona automáticamente las fases principales"
        )
        
        if select_all_main:
            safe_defaults = get_default_phases_for_league(selected_league, available_phases)
            selected_phases = safe_defaults
            st.sidebar.success("✅ Fases principales seleccionadas")
        else:
            safe_defaults = get_default_phases_for_league(selected_league, available_phases)
            selected_phases = st.sidebar.multiselect(
                "Fases:",
                available_phases,
                default=safe_defaults,
                help="Puedes seleccionar múltiples fases. Se generará un único archivo con todas."
            )
    else:
        safe_defaults = get_default_phases_for_league(selected_league, available_phases)
        selected_phases = st.sidebar.multiselect(
            "Fases:",
            available_phases,
            default=safe_defaults,
            help="Puedes seleccionar múltiples fases. Se generará un único archivo con todas."
        )
    
    # === NUEVO: Selección de jornadas ===
    st.sidebar.subheader("📅 Selección de Jornadas (Opcional)")
    
    enable_jornadas_filter = st.sidebar.checkbox(
        "Filtrar por jornadas específicas",
        value=False,
        help="Si no se selecciona, se procesarán TODAS las jornadas disponibles"
    )
    
    selected_jornadas = None
    if enable_jornadas_filter:
        available_jornadas = list(range(1, 41))  # Hasta jornada 40
        
        selected_jornadas = st.sidebar.multiselect(
            "Jornadas:",
            available_jornadas,
            default=[],
            help="Selecciona las jornadas específicas que quieres procesar. Ejemplo: [1, 2, 3] para las primeras 3 jornadas."
        )
        
        if selected_jornadas:
            st.sidebar.success(f"✅ Jornadas seleccionadas: {len(selected_jornadas)}")
            st.sidebar.info(f"📋 Jornadas: {', '.join(map(str, sorted(selected_jornadas)))}")
        else:
            st.sidebar.warning("⚠️ Selecciona al menos una jornada o desactiva el filtro")
    else:
        st.sidebar.info("📋 Se procesarán TODAS las jornadas disponibles")
    
    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📊 Resumen de Configuración")
        
        if selected_phases:
            st.success(f"**Temporada seleccionada:** {selected_season}")
            st.info(f"**Número de fases:** {len(selected_phases)}")
            
            # Mostrar jornadas seleccionadas
            if enable_jornadas_filter and selected_jornadas:
                st.info(f"**Jornadas seleccionadas:** {len(selected_jornadas)} jornadas")
                if len(selected_jornadas) <= 10:
                    st.write(f"**Jornadas:** {', '.join(map(str, sorted(selected_jornadas)))}")
                else:
                    st.write(f"**Jornadas:** {min(selected_jornadas)} a {max(selected_jornadas)} (y otras)")
            elif enable_jornadas_filter:
                st.warning("⚠️ Filtro de jornadas activado pero ninguna seleccionada")
            else:
                st.info("**Jornadas:** Todas las disponibles")
            
            # Mostrar fases seleccionadas
            st.write("**Fases seleccionadas:**")
            for phase in selected_phases:
                st.write(f"- {phase}")
            
            # Mostrar nombres de archivos de salida con nueva estructura de directorios
            season_short = format_season_short(selected_season)
            liga_short = get_liga_short(selected_league)
            
            if enable_jornadas_filter and selected_jornadas:
                jornadas_suffix = get_jornadas_suffix(selected_jornadas)
                directory_name = f"{liga_short}_{season_short}{jornadas_suffix}"
                st.write(f"**Estructura de directorios y archivos:**")
                st.write(f"📁 **Directorio**: `data/{directory_name}/`")
                st.write(f"   • `boxscores_{season_short}_{liga_short}.xlsx` (📊 Boxscores completos)")
                st.write(f"   • `assists_{season_short}_{liga_short}.xlsx` (🏀 Asistencias jugador-anotador)")
                st.write(f"   • `clutch_data_{season_short}_{liga_short}.xlsx` (🔥 Estadísticas clutch)")
                st.write(f"   • `clutch_lineups_{season_short}_{liga_short}.xlsx` (🔥👥 Clutch lineups)")
                st.write(f"   • `players_{season_short}_{liga_short}.xlsx` (🧑‍🤝‍🧑 Jugadores agregados)")
                st.write(f"   • `teams_{season_short}_{liga_short}.xlsx` (🏀 Equipos agregados)")
            else:
                directory_name = f"{liga_short}_{season_short}"
                st.write(f"**Estructura de directorios y archivos:**")
                st.write(f"📁 **Directorio**: `data/{directory_name}/`")
                st.write(f"   • `boxscores_{season_short}_{liga_short}.xlsx` (📊 Boxscores completos)")
                st.write(f"   • `assists_{season_short}_{liga_short}.xlsx` (🏀 Asistencias jugador-anotador)")
                st.write(f"   • `clutch_data_{season_short}_{liga_short}.xlsx` (🔥 Estadísticas clutch)")
                st.write(f"   • `clutch_lineups_{season_short}_{liga_short}.xlsx` (🔥👥 Clutch lineups)")
                st.write(f"   • `players_{season_short}_{liga_short}.xlsx` (🧑‍🤝‍🧑 Jugadores agregados)")
                st.write(f"   • `teams_{season_short}_{liga_short}.xlsx` (🏀 Equipos agregados)")
            
            
        else:
            st.warning("⚠️ Selecciona al menos una fase para continuar")
    
    with col2:
        st.header("🚀 Acciones")
        
        # Botón de inicio
        start_scraping = st.button(
            "🚀⚡ Ejecutar Pipeline UNIFICADO",
            disabled=(
                len(selected_phases) == 0 or 
                (enable_jornadas_filter and len(selected_jornadas) == 0)
            ),
            help="Inicia el proceso UNIFICADO: extracción máxima eficiencia + agregación",
            type="primary"
        )
        
        # Información adicional
        st.info("""
        **🚀⚡ Pipeline UNIFICADO de máxima eficiencia:**
        1. **📊 Extracción unificada:** Boxscores + Asistencias + Clutch + Lineups (1 acceso por partido)
        2. **🧑‍🤝‍🧑 Jugadores:** Agregación con biografías
        3. **🏀 Equipos:** Métricas avanzadas por equipo
        
        - Genera **6 archivos Excel** automáticamente
        - **3x más rápido** que versiones anteriores  
        - **Filtro opcional de jornadas** con sufijo automático (jX_Y_Z)
        - El proceso puede tardar varios minutos
        - Se mostrará el progreso en tiempo real
        - Los archivos se descargarán automáticamente
        """)
    
    # Área de progreso y resultados
    if start_scraping:
        st.header("📈 Progreso del Pipeline UNIFICADO")
        
        progress_container = st.container()
        log_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        with log_container:
            log_area = st.empty()
        
        # Configurar la cola de comunicación con el hilo
        output_queue = queue.Queue()
        
        # Iniciar el scraping en un hilo separado
        scraper_thread = threading.Thread(
            target=run_unified_scraper_thread,
            args=(selected_season, selected_phases, selected_league, selected_jornadas, output_queue)
        )
        scraper_thread.start()
        
        # Mostrar progreso en tiempo real
        logs = []
        progress_value = 0
        
        while scraper_thread.is_alive() or not output_queue.empty():
            try:
                message_type, message = output_queue.get(timeout=0.1)
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {message}"
                logs.append(formatted_message)
                
                # Actualizar progreso
                if message_type == "info":
                    progress_value = min(progress_value + 1, 85)
                elif message_type == "success":
                    if "PIPELINE UNIFICADO COMPLETADO" in message:
                        progress_value = 70
                    elif "JUGADORES AGREGADOS" in message:
                        progress_value = 85
                    elif "EQUIPOS AGREGADOS" in message:
                        progress_value = 95
                    elif "Máxima eficiencia alcanzada" in message:
                        progress_value = 100
                elif message_type == "error":
                    st.error(message)
                    break
                elif message_type == "files":
                    file_paths = message
                    st.success("🎉 ¡Todos los archivos generados exitosamente!")
                    
                    cols = st.columns(2)
                    for i, file_path in enumerate(file_paths):
                        if Path(file_path).exists():
                            with open(file_path, "rb") as file:
                                col_idx = i % 2
                                cols[col_idx].download_button(
                                    label=f"📥 {Path(file_path).name}",
                                    data=file.read(),
                                    file_name=Path(file_path).name,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"download_{i}"
                                )
                
                progress_bar.progress(progress_value)
                status_text.text(message)
                
                log_text = "\n".join(logs[-10:])
                log_area.text_area("📋 Log de actividad:", value=log_text, height=200)
                
            except queue.Empty:
                time.sleep(0.1)
                continue
        
        scraper_thread.join()
        
        if progress_value == 100:
            st.success("🚀⚡ ¡Pipeline UNIFICADO completado exitosamente - Máxima eficiencia alcanzada!")
            st.balloons()

if __name__ == "__main__":
    main()