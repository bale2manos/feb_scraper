# app.py
import streamlit as st
from pathlib import Path
import pandas as pd
from phase_report.build_phase_report import build_phase_report, OUTPUT_PDF

# Import file configuration utilities
from utils.file_config_ui import render_file_config_ui, validate_files

# --- Página ---
st.set_page_config(page_title="🏀 Generador de Informe de Fase", layout="wide")
st.title("🏀 Generador de Informe de Fase")
st.markdown("""
Genera informes por fases de competición con análisis detallado de equipos.

**🆕 Nueva funcionalidad:**
- ✨ **Filtrado por jornadas:** Analiza rendimiento por fases en jornadas específicas
- 📊 **Análisis temporal:** Compara diferentes momentos de cada fase
- 🎯 **Segmentación avanzada:** Combina filtros de fase y jornada para análisis precisos
""")

# Configuración de archivos con soporte para jornadas: necesitamos equipos y jugadores agregados
file_paths = render_file_config_ui(
    file_types=['teams_aggregated', 'jugadores_aggregated'],
    key_prefix="phase_report"
)

# Validar archivos antes de continuar
if not validate_files(file_paths):
    st.error("❌ **No se pueden cargar los archivos necesarios.** Por favor, verifica la configuración anterior.")
    st.stop()

# Obtener ruta de archivo de equipos y jugadores
teams_file = file_paths.get('teams_aggregated')
players_file = file_paths.get('jugadores_aggregated')

# --- Carga datos para multiselect ---
try:
    df_teams = pd.read_excel(teams_file)
    st.success(f"✅ Datos cargados: {df_teams.shape[0]} equipos encontrados")
except Exception as e:
    st.error(f"❌ Error cargando datos: {str(e)}")
    st.stop()

equipos = sorted(df_teams['EQUIPO'].dropna().unique().tolist())
fases   = sorted(df_teams['FASE'].dropna().unique().tolist())

# --- Widgets ---
sel_equipos = st.multiselect("Equipo(s):", options=equipos, placeholder="Selecciona equipos si es necesario")
sel_fases   = st.multiselect("Fase(s):",   options=fases,  placeholder="Selecciona fases si es necesario")

# --- Botón de generación ---
if st.button("📄 Generar informe"):
    if not sel_equipos and not sel_fases:
        st.error("Por favor, selecciona al menos un equipo o una fase.")
    else:
        with st.spinner("Generando PDF..."):
            # Llamada a tu función con los archivos de datos (equipos y jugadores)
            build_phase_report(
                teams=sel_equipos,
                phase=sel_fases or None,
                teams_file=str(teams_file) if teams_file else None,
                players_file=str(players_file) if players_file else None
            )

        # Leer el PDF generado
        pdf_path = Path(OUTPUT_PDF)
        if pdf_path.exists():
            pdf_bytes = pdf_path.read_bytes()
            st.success(f"✅ Informe listo: `{pdf_path.name}`")

            # Store the PDF data in session state to persist the download button
            st.session_state['pdf_data'] = pdf_bytes
            st.session_state['pdf_name'] = pdf_path.name
        else:
            st.error("😞 Algo falló: no se ha encontrado el PDF.")

# Show download button if PDF data is available in session state
if 'pdf_data' in st.session_state and 'pdf_name' in st.session_state:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.download_button(
            label="⬇️ Descargar Informe PDF",
            data=st.session_state['pdf_data'],
            file_name=st.session_state['pdf_name'],
            mime="application/pdf",
            use_container_width=True,
            key="download_pdf_button"  # Unique key to prevent conflicts
        )
    
    with col2:
        if st.button("🗑️ Limpiar", help="Limpiar PDF actual"):
            del st.session_state['pdf_data']
            del st.session_state['pdf_name']
            st.rerun()

# --- Pie de página ---
st.markdown("---")

st.subheader("ℹ️ Información sobre el Análisis Temporal")

with st.expander("🎯 Cómo usar el filtrado por jornadas"):
    st.write("""
    **🔄 Todas las jornadas:**
    - Análisis completo de toda la fase seleccionada
    - Visión general del rendimiento en la competición
    - Ideal para análisis de temporada completa
    
    **📌 Jornadas específicas:**
    - Enfoque en períodos concretos de la fase
    - Análisis de rachas o momentos clave
    - Comparación entre diferentes momentos de la competición
    
    **🎯 Combinación fase + jornadas:**
    - **Liga Regular + Jornadas 1-5:** Análisis de inicio de temporada
    - **Liga Regular + Jornadas 15-20:** Evaluación de mitad de temporada
    - **Playoffs + Jornadas específicas:** Rendimiento en eliminatorias concretas
    """)

with st.expander("📊 Casos de uso del análisis temporal"):
    st.write("""
    **🏀 Para entrenadores:**
    - Evaluar evolución táctica del equipo
    - Identificar patrones de rendimiento temporal
    - Comparar efectividad en diferentes momentos
    
    **📈 Para analistas:**
    - Estudiar tendencias de competición
    - Análisis de impacto de cambios reglamentarios
    - Comparación entre diferentes períodos competitivos
    
    **🎯 Para scouts:**
    - Evaluar consistencia de equipos a lo largo del tiempo
    - Identificar fortalezas/debilidades en diferentes momentos
    - Análisis de adaptación a la competición
    """)

st.caption("🏀 Generador de informes de fase desarrollado con herramientas de análisis temporal y ReportLab.")

