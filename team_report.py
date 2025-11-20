# team_report_app.py
import streamlit as st
from pathlib import Path
import pandas as pd
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the team report building function
from team_report.build_team_report import build_team_report

# Import file configuration utilities
from utils.file_config_ui import render_file_config_ui, validate_files

# --- Página ---
st.set_page_config(page_title="🏀 Generador de Informe de Equipo", layout="wide")
st.title("🏀 Generador de Informe de Equipo")
st.markdown("""
Genera informes detallados para equipos completos con estadísticas de todos los jugadores.

**🆕 Nueva funcionalidad:**
- ✨ **Filtrado por jornadas:** Analiza rendimiento del equipo en jornadas específicas
- 📊 **Comparación temporal:** Compara diferentes períodos de la temporada
- 🎯 **Análisis detallado:** Estadísticas granulares por jornada o conjunto de jornadas
- 🚀 **Generación masiva:** Crea informes de TODOS los equipos automáticamente
- 📦 **Descarga ZIP:** Obtén todos los informes en un archivo comprimido
""")

# Configuración de archivos con soporte para jornadas
file_paths = render_file_config_ui(
    file_types=['jugadores_aggregated', 'teams_aggregated', 'clutch_lineups', 'assists'],
    key_prefix="team_report"
)

# Validar archivos obligatorios antes de continuar
required_files = ['jugadores_aggregated', 'teams_aggregated', 'clutch_lineups']
required_file_paths = {k: v for k, v in file_paths.items() if k in required_files}

if not validate_files(required_file_paths):
    st.error("❌ **No se pueden cargar los archivos necesarios.** Por favor, verifica la configuración anterior.")
    st.stop()

# Obtener rutas de archivos
players_file = file_paths.get('jugadores_aggregated')
teams_file = file_paths.get('teams_aggregated')
clutch_lineups_file = file_paths.get('clutch_lineups')
assists_file = file_paths.get('assists')  # Puede ser None si no está disponible

# Importar configuración centralizada
from config import TEAM_REPORTS_DIR

# Define constants
BASE_OUTPUT_DIR = TEAM_REPORTS_DIR

# --- Carga datos para multiselect ---
try:
    df_players = pd.read_excel(players_file)
    st.success(f"✅ Datos cargados: {df_players.shape[0]} jugadores encontrados")
except Exception as e:
    st.error(f"❌ Error cargando datos: {str(e)}")
    st.stop()

equipos = sorted(df_players['EQUIPO'].dropna().unique().tolist())
jugadores = sorted(df_players['JUGADOR'].dropna().unique().tolist())

# --- Widgets ---
st.subheader("Opciones de filtrado")

# Crear dos columnas para los widgets principales
col1, col2 = st.columns(2)

with col1:
    sel_equipo = st.selectbox(
        "🏀 Equipo:", 
        options=[""] + equipos, 
        index=0,
        placeholder="Selecciona un equipo"
    )

with col2:
    sel_jugadores = st.multiselect(
        "👥 Jugadores específicos:", 
        options=jugadores, 
        placeholder="Selecciona jugadores específicos (opcional)"
    )

# --- Filtros de localía ---
st.subheader("📍 Filtros de localía")

col_home1, col_home2 = st.columns(2)

with col_home1:
    home_away_filter = st.radio(
        "🏠 Filtro general de localía:",
        options=["Todos", "Local", "Visitante"],
        index=0,
        help="Filtra todos los partidos del equipo según donde jugó (afecta estadísticas generales)",
        horizontal=True
    )

with col_home2:
    home_away_filter_display = {
        "Todos": "🌍 Todos los partidos",
        "Local": "🏠 Solo partidos como local",
        "Visitante": "✈️ Solo partidos como visitante"
    }
    st.info(f"**Filtro activo:** {home_away_filter_display[home_away_filter]}")

# --- Head to Head Configuration ---
st.subheader("🆚 Configuración Head-to-Head (opcional)")

col_h2h1, col_h2h2 = st.columns([2, 1])

with col_h2h1:
    # Obtener lista de equipos disponibles para H2H (excluyendo el equipo seleccionado)
    equipos_disponibles_h2h = [eq for eq in equipos if eq != sel_equipo] if sel_equipo else equipos
    
    # Buscar "GRUPO EGIDO PINTOBASKET" como equipo por defecto
    default_rival_idx = 0  # Fallback al primero
    default_rival_name = "GRUPO EGIDO PINTOBASKET"
    
    if default_rival_name in equipos_disponibles_h2h:
        default_rival_idx = equipos_disponibles_h2h.index(default_rival_name)
    elif equipos_disponibles_h2h:
        default_rival_idx = 0
    else:
        default_rival_idx = None
    
    rival_team = st.selectbox(
        "🏆 Equipo rival para comparación:",
        options=equipos_disponibles_h2h,
        index=default_rival_idx,
        help="Este equipo aparecerá en la página de comparación head-to-head del informe"
    )

with col_h2h2:
    h2h_home_away_filter = st.radio(
        "📍 Localía H2H:",
        options=["Todos", "Local", "Visitante"],
        index=0,
        help="Filtra los enfrentamientos directos según donde jugó tu equipo"
    )

# Información sobre H2H
if rival_team:
    h2h_info_display = {
        "Todos": "todos los enfrentamientos",
        "Local": "solo enfrentamientos como local",
        "Visitante": "solo enfrentamientos como visitante"
    }
    st.info(f"🆚 Se generará comparación H2H con **{rival_team}** ({h2h_info_display[h2h_home_away_filter]})")
else:
    st.warning("⚠️ No se generará página H2H (no hay rival seleccionado)")

# --- Configuración de filtros mínimos ---
st.subheader("⚙️ Configuración de filtros mínimos")
st.info("🎯 Ajusta los valores mínimos para filtrar jugadores en los gráficos según su participación.")

# Crear tres columnas para los filtros
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    min_games = st.slider(
        "🏀 Partidos mínimos",
        min_value=0,
        max_value=20,
        value=5,
        step=1,
        help="Número mínimo de partidos jugados para aparecer en los gráficos"
    )

with filter_col2:
    min_minutes = st.slider(
        "⏱️ Minutos mínimos",
        min_value=0,
        max_value=200,
        value=50,
        step=10,
        help="Número mínimo de minutos totales jugados para aparecer en los gráficos"
    )

with filter_col3:
    min_shots = st.slider(
        "🎯 Tiros mínimos",
        min_value=0,
        max_value=100,
        value=20,
        step=5,
        help="Número mínimo de tiros realizados para aparecer en gráficos de tiro"
    )

# Mostrar resumen de filtros activos
with st.expander("📊 Resumen de filtros activos", expanded=False):
    st.write(f"""
    **Filtros configurados:**
    - **Partidos mínimos:** {min_games} partidos
    - **Minutos mínimos:** {min_minutes} minutos totales
    - **Tiros mínimos:** {min_shots} tiros (para gráficos de tiro)
    
    **Efecto:** Solo aparecerán jugadores que cumplan estos criterios en los gráficos correspondientes.
    """)

# Información sobre el filtrado
if sel_equipo and sel_jugadores:
    st.info("🔄 Se usarán los jugadores seleccionados, ignorando el filtro de equipo.")
elif sel_equipo:
    # Mostrar cuántos jugadores tiene el equipo
    jugadores_equipo = df_players[df_players['EQUIPO'] == sel_equipo]['JUGADOR'].nunique()
    st.info(f"📊 El equipo '{sel_equipo}' tiene {jugadores_equipo} jugadores.")
elif sel_jugadores:
    st.info(f"👥 Se analizarán {len(sel_jugadores)} jugadores seleccionados.")
else:
    st.warning("⚠️ Selecciona un equipo o jugadores específicos para generar el informe.")

# --- Botón de generación ---
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("📄 Generar informe individual", type="primary", use_container_width=True):
        # Validar que hay algo seleccionado
        if not sel_equipo and not sel_jugadores:
            st.error("❌ Por favor, selecciona un equipo o jugadores específicos.")
        else:
            with st.spinner("Generando PDF con gráficos de equipo..."):
                try:
                    # Determinar los parámetros para build_team_report
                    if sel_jugadores:
                        # Prioridad a jugadores específicos
                        pdf_path = build_team_report(
                            team_filter=None, 
                            player_filter=sel_jugadores,
                            players_file=str(players_file),
                            teams_file=str(teams_file),
                            clutch_lineups_file=str(clutch_lineups_file),
                            assists_file=str(assists_file) if assists_file else None,
                            rival_team=rival_team if rival_team else None,
                            home_away_filter=home_away_filter,
                            h2h_home_away_filter=h2h_home_away_filter,
                            min_games=min_games,
                            min_minutes=min_minutes,
                            min_shots=min_shots
                        )
                        filter_info = f"{len(sel_jugadores)} jugadores seleccionados"
                    else:
                        # Usar filtro de equipo
                        pdf_path = build_team_report(
                            team_filter=sel_equipo, 
                            player_filter=None,
                            players_file=str(players_file),
                            teams_file=str(teams_file),
                            clutch_lineups_file=str(clutch_lineups_file),
                            assists_file=str(assists_file) if assists_file else None,
                            rival_team=rival_team if rival_team else None,
                            home_away_filter=home_away_filter,
                            h2h_home_away_filter=h2h_home_away_filter,
                            min_games=min_games,
                            min_minutes=min_minutes,
                            min_shots=min_shots
                        )
                        filter_info = f"equipo '{sel_equipo}'"

                    # Read the generated PDF
                    if pdf_path and Path(pdf_path).exists():
                        pdf_bytes = Path(pdf_path).read_bytes()
                        st.success(f"✅ Informe listo para {filter_info}: `{Path(pdf_path).name}`")
                        
                        # Store the PDF data in session state to persist the download button
                        st.session_state['pdf_data'] = pdf_bytes
                        st.session_state['pdf_name'] = Path(pdf_path).name
                        st.session_state['filter_info'] = filter_info
                    else:
                        st.error("😞 Algo falló: no se ha encontrado el PDF.")
                        
                except Exception as e:
                    st.error(f"❌ Error al generar el informe: {str(e)}")

with col_btn2:
    if st.button("🚀 Generar informes de TODOS los equipos", type="secondary", use_container_width=True):
        # Obtener lista de equipos únicos
        equipos_disponibles = sorted(df_players['EQUIPO'].dropna().unique().tolist())
        
        st.info(f"🎯 Iniciando generación de informes para **{len(equipos_disponibles)} equipos**...")
        
        with st.spinner("🚀 Generando informes para todos los equipos... Esto puede tardar varios minutos."):
            try:
                import time
                import zipfile
                import shutil
                from datetime import datetime
                
                # Crear directorio temporal para PDFs
                temp_dir = BASE_OUTPUT_DIR / "temp_batch"
                temp_dir.mkdir(exist_ok=True)
                
                pdf_paths = []
                
                # Contenedores para mostrar progreso
                progress_bar = st.progress(0)
                status_container = st.empty()
                log_container = st.empty()
                
                total_equipos = len(equipos_disponibles)
                equipos_exitosos = 0
                equipos_fallidos = []
                logs = []
                
                for i, equipo in enumerate(equipos_disponibles):
                    try:
                        # Actualizar estado
                        status_msg = f"🔄 Procesando {equipo} ({i+1}/{total_equipos})..."
                        status_container.text(status_msg)
                        logs.append(f"[{i+1}/{total_equipos}] Iniciando: {equipo}")
                        
                        # Mostrar últimos 5 logs
                        if len(logs) > 5:
                            log_text = "\n".join(logs[-5:])
                        else:
                            log_text = "\n".join(logs)
                        log_container.text_area("📋 Progreso detallado:", value=log_text, height=100, key=f"log_{i}")
                        
                        # Generar informe para este equipo
                        pdf_path = build_team_report(
                            team_filter=equipo, 
                            player_filter=None,
                            players_file=str(players_file),
                            teams_file=str(teams_file),
                            clutch_lineups_file=str(clutch_lineups_file),
                            assists_file=str(assists_file) if assists_file else None,
                            rival_team=None,  # No usar rival en generación masiva
                            home_away_filter=home_away_filter,
                            h2h_home_away_filter="Todos",  # Todos por defecto en masivo
                            min_games=min_games,
                            min_minutes=min_minutes,
                            min_shots=min_shots
                        )
                        
                        if pdf_path and Path(pdf_path).exists():
                            # Renombrar PDF con nombre del equipo
                            equipo_safe = "".join(c for c in equipo if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            new_name = f"Informe_{equipo_safe.replace(' ', '_')}.pdf"
                            new_path = temp_dir / new_name
                            
                            # Copiar a directorio temporal con nuevo nombre
                            shutil.copy2(pdf_path, new_path)
                            pdf_paths.append(new_path)
                            equipos_exitosos += 1
                            logs.append(f"✅ {equipo}: Completado")
                        else:
                            equipos_fallidos.append(equipo)
                            logs.append(f"❌ {equipo}: Falló (sin PDF)")
                        
                        # Actualizar barra de progreso
                        progress_bar.progress((i + 1) / total_equipos)
                        
                        # Pequeña pausa para permitir actualización de UI
                        time.sleep(0.1)
                        
                    except Exception as e:
                        error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
                        equipos_fallidos.append(f"{equipo} (Error: {error_msg})")
                        logs.append(f"❌ {equipo}: Error - {error_msg}")
                        continue
                
                # Crear ZIP con todos los PDFs exitosos
                if pdf_paths:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_path = temp_dir / f"Informes_Equipos_{timestamp}.zip"
                    
                    status_container.text("📦 Creando archivo ZIP...")
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for pdf_path in pdf_paths:
                            zipf.write(pdf_path, pdf_path.name)
                    
                    # Leer ZIP para descarga
                    zip_bytes = zip_path.read_bytes()
                    
                    # Limpiar UI de progreso
                    status_container.empty()
                    log_container.empty()
                    progress_bar.progress(1.0)
                    
                    # Mostrar resultados finales
                    st.success(f"🎉 **Proceso completado!**")
                    st.success(f"✅ **{equipos_exitosos}/{total_equipos}** informes generados exitosamente")
                    
                    if equipos_fallidos:
                        st.warning(f"⚠️ **Equipos con errores ({len(equipos_fallidos)}):**")
                        for eq_error in equipos_fallidos[:5]:  # Mostrar máximo 5
                            st.write(f"- {eq_error}")
                        if len(equipos_fallidos) > 5:
                            st.write(f"... y {len(equipos_fallidos) - 5} más")
                    
                    # Botón de descarga del ZIP
                    st.download_button(
                        label=f"📦 Descargar ZIP con {equipos_exitosos} informes ({len(pdf_paths)} archivos)",
                        data=zip_bytes,
                        file_name=f"Informes_Equipos_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True,
                        key="download_batch_zip"
                    )
                    
                    # Limpiar archivos temporales
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception as cleanup_error:
                        st.warning(f"⚠️ No se pudieron limpiar archivos temporales: {cleanup_error}")
                        
                else:
                    st.error("❌ No se pudo generar ningún informe exitosamente.")
                    if equipos_fallidos:
                        st.error("**Todos los equipos fallaron:**")
                        for eq_error in equipos_fallidos:
                            st.write(f"- {eq_error}")
                        
            except Exception as e:
                st.error(f"❌ Error crítico en el proceso masivo: {str(e)}")
                st.error("**Detalles del error para depuración:**")
                st.code(str(e))

# Show download button if PDF data is available in session state
if 'pdf_data' in st.session_state and 'pdf_name' in st.session_state:
    st.markdown("---")
    st.subheader("📥 Descargar Informe")
    
    # Mostrar información del informe generado
    if 'filter_info' in st.session_state:
        st.info(f"📋 Informe generado para: {st.session_state['filter_info']}")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.download_button(
            label="⬇️ Descargar Informe PDF",
            data=st.session_state['pdf_data'],
            file_name=st.session_state['pdf_name'],
            mime="application/pdf",
            use_container_width=True,
            key="download_team_pdf_button"  # Unique key to prevent conflicts
        )
    
    with col2:
        if st.button("🗑️ Limpiar", help="Limpiar PDF actual"):
            # Clear all session state related to PDF
            for key in ['pdf_data', 'pdf_name', 'filter_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# --- Información adicional ---
st.markdown("---")
st.subheader("ℹ️ Información")

with st.expander("📊 Contenido del informe"):
    st.write("""
    El informe de equipo incluye los siguientes gráficos:
    
    1. **OE (Offensive Efficiency)** - Eficiencia ofensiva por jugador
    2. **EPS (Efficiency Per Shot)** - Eficiencia por tiro
    3. **Top Shooters** - Mejores tiradores (TS% vs EFG%)
    4. **Top Turnovers** - Análisis de pérdidas (Plays vs TOV%)
    5. **Top PPP** - Puntos por posesión (Plays vs PPP)
    6. **Finalización Plays** - Distribución de tipos de jugadas
    
    **🔧 Filtros personalizables:**
    - **Partidos mínimos:** Número mínimo de partidos para aparecer en gráficos
    - **Minutos mínimos:** Minutos totales mínimos para análisis de eficiencia
    - **Tiros mínimos:** Tiros mínimos para gráficos de tiro (Top Shooters)
    """)

with st.expander("⚙️ Configuración de filtros avanzada"):
    st.write("""
    **🎯 Filtros mínimos configurables:**
    
    **🏀 Partidos mínimos (0-20):**
    - Controla qué jugadores aparecen según participación en partidos
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 3-5 para análisis completo, 8-10 para jugadores regulares
    
    **⏱️ Minutos mínimos (0-200):**
    - Filtra por tiempo total de juego en la temporada
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 50-100 para análisis de eficiencia, 150+ para titulares
    
    **🎯 Tiros mínimos (0-100):**
    - Específico para gráficos de tiro (Top Shooters)
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 15-25 para muestras representativas, 50+ para especialistas
    
    **💡 Consejos de configuración:**
    - **Valores bajos:** Incluye más jugadores, análisis más amplio
    - **Valores altos:** Enfoque en jugadores principales, datos más fiables
    - **Ajuste dinámico:** Cambia según el objetivo del análisis
    """)

with st.expander("🎯 Cómo usar"):
    st.write("""
    **📄 Informe individual:**
    - **Opción 1: Análisis por equipo** - Selecciona un equipo en el desplegable
    - **Opción 2: Análisis de jugadores específicos** - Selecciona jugadores específicos (tiene prioridad sobre equipo)
    
    **🚀 Generación masiva de informes:**
    - **Procesa TODOS los equipos** encontrados en los datos cargados
    - **Genera un ZIP** con todos los informes PDF
    - **Ideal para análisis completo** de una competición o liga
    - **Nombres automáticos** por equipo para fácil identificación
    
    **⚠️ Consideraciones para generación masiva:**
    - El proceso puede tardar varios minutos (depende del número de equipos)
    - Se requiere confirmación antes de iniciar
    - Los equipos con errores se reportan al final
    - Los archivos se descargan en un solo ZIP comprimido
    """)

with st.expander("📊 Análisis temporal de equipos"):
    st.write("""
    **🎯 Ventajas del filtrado por jornadas:**
    - **Progresión del equipo:** Evaluar mejora a lo largo de la temporada
    - **Impacto de cambios:** Medir efectos de fichajes, lesiones o cambios tácticos
    - **Análisis de rachas:** Estudiar períodos de buen/mal rendimiento
    - **Preparación de partidos:** Analizar tendencias recientes del rival
    
    **📈 Métricas clave por período:**
    - Eficiencia ofensiva y defensiva temporal
    - Evolución de sistemas de juego
    - Rendimiento individual en contexto temporal
    
    **🚀 Generación masiva temporal:**
    - Aplica los mismos filtros de jornadas a TODOS los equipos
    - Perfecto para análisis comparativo entre equipos en períodos específicos
    - Ideal para reportes de competición por fases
    """)

with st.expander("💡 Casos de uso de la generación masiva"):
    st.write("""
    **🏀 Para entrenadores y directivos:**
    - **Análisis de competición completa:** Estudiar todos los rivales de la liga
    - **Reportes de fin de temporada:** Generar informes de todos los equipos
    - **Scouting masivo:** Analizar múltiples equipos de una vez
    
    **📊 Para analistas:**
    - **Comparativas liga/grupo:** Análisis estadístico de toda la competición
    - **Benchmarking:** Comparar rendimiento del equipo con toda la liga
    - **Estudios longitudinales:** Analizar evolución de múltiples equipos
    
    **📋 Para organizadores:**
    - **Informes oficiales:** Generar documentación para federaciones
    - **Historiales completos:** Archivar datos de temporadas completas
    - **Análisis de competición:** Estudios globales de rendimiento
    """)

# Eliminar el expander duplicado
# with st.expander("🎯 Cómo usar"):
st.markdown("---")
st.caption("🏀 Generador de informes de equipo desarrollado con herramientas de análisis de baloncesto y filtrado temporal.")
