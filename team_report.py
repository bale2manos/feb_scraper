# app.py
import streamlit as st
from pathlib import Path
import pandas as pd
from team_report.build_team_report import build_team_report, OUTPUT_PDF, TEAM_FILE

# --- Página ---
st.set_page_config(page_title="Generador de Informe de Equipo", layout="wide")
st.title("🏀 Generador de Informe de Equipo")
st.write("Selecciona uno o más equipos y fases, y luego pulsa **Generar informe**.")

# --- Carga datos para multiselect ---
df_teams = pd.read_excel(TEAM_FILE)

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
            # Llamada a tu función
            build_team_report(teams=sel_equipos, phase=sel_fases or None)

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
st.caption("Trabajo desarrollado con tus herramientas de generación de gráficos y ReportLab.")

