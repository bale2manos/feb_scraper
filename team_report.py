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

# Define constants
PLAYERS_FILE = Path("data/jugadores_aggregated.xlsx")
BASE_OUTPUT_DIR = Path("output/reports/team_reports/")

# --- Página ---
st.set_page_config(page_title="Generador de Informe de Equipo", layout="wide")
st.title("🏀 Generador de Informe de Equipo")
st.write("Selecciona un equipo o jugadores específicos, y luego pulsa **Generar informe**.")

# --- Carga datos para multiselect ---
df_players = pd.read_excel(PLAYERS_FILE)

equipos = sorted(df_players['EQUIPO'].dropna().unique().tolist())
jugadores = sorted(df_players['JUGADOR'].dropna().unique().tolist())

# --- Widgets ---
st.subheader("Opciones de filtrado")

# Crear dos columnas para los widgets
col1, col2 = st.columns(2)

with col1:
    sel_equipo = st.selectbox(
        "Equipo:", 
        options=[""] + equipos, 
        index=0,
        placeholder="Selecciona un equipo"
    )

with col2:
    sel_jugadores = st.multiselect(
        "Jugadores específicos:", 
        options=jugadores, 
        placeholder="Selecciona jugadores específicos (opcional)"
    )

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
if st.button("📄 Generar informe", type="primary", use_container_width=True):
    # Validar que hay algo seleccionado
    if not sel_equipo and not sel_jugadores:
        st.error("❌ Por favor, selecciona un equipo o jugadores específicos.")
    else:
        with st.spinner("Generando PDF con gráficos de equipo..."):
            try:
                # Determinar los parámetros para build_team_report
                if sel_jugadores:
                    # Prioridad a jugadores específicos
                    pdf_path = build_team_report(team_filter=None, player_filter=sel_jugadores)
                    filter_info = f"{len(sel_jugadores)} jugadores seleccionados"
                else:
                    # Usar filtro de equipo
                    pdf_path = build_team_report(team_filter=sel_equipo, player_filter=None)
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
    """)

with st.expander("🎯 Cómo usar"):
    st.write("""
    **Opción 1: Análisis por equipo**
    - Selecciona un equipo en el desplegable
    - Se analizarán todos los jugadores del equipo
    
    **Opción 2: Análisis de jugadores específicos**
    - Selecciona jugadores específicos en el multiselect
    - Puedes elegir jugadores de diferentes equipos
    - Esta opción tiene prioridad sobre el filtro de equipo
    """)

# --- Pie de página ---
st.markdown("---")
st.caption("🏀 Generador de informes de equipo desarrollado con herramientas de análisis de baloncesto y ReportLab.")
