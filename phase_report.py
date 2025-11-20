# app.py
import streamlit as st
from pathlib import Path
import pandas as pd
from phase_report.build_phase_report import build_phase_report

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

# --- Botón de generación ---
if st.button("📄 Generar informe"):
    if not sel_equipos and not sel_fases:
        st.error("Por favor, selecciona al menos un equipo o una fase.")
    else:
        with st.spinner("Generando PDF..."):
            # Llamada a tu función con los archivos de datos (equipos y jugadores)
            # La función ahora retorna la ruta del PDF generado
            pdf_path = build_phase_report(
                teams=sel_equipos,
                phase=sel_fases or None,
                teams_file=str(teams_file) if teams_file else None,
                players_file=str(players_file) if players_file else None,
                min_games=min_games,
                min_minutes=min_minutes,
                min_shots=min_shots
            )

        # Leer el PDF generado
        if pdf_path and Path(pdf_path).exists():
            pdf_bytes = Path(pdf_path).read_bytes()
            st.success(f"✅ Informe listo: `{Path(pdf_path).name}`")

            # Store the PDF data in session state to persist the download button
            st.session_state['pdf_data'] = pdf_bytes
            st.session_state['pdf_name'] = Path(pdf_path).name
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

with st.expander("📊 Contenido del informe"):
    st.write("""
    El informe de fase incluye los siguientes análisis:
    
    1. **Team Heatmap** - Ranking de equipos por estadísticas
    2. **Hierarchy Score Boxplot** - Distribución de puntos por equipo
    3. **Net Rating Chart** - Rating ofensivo vs defensivo
    4. **Plays vs Possessions** - Análisis de posesiones
    5. **Play Distribution** - Distribución de tipos de jugadas
    6. **Points Distribution** - Distribución de puntos
    7. **PPP Quadrant** - Cuadrantes de eficiencia
    8. **Rebound Analysis** - Análisis de rebotes
    9. **Offensive Efficiency** - Top 20 eficiencia ofensiva
    10. **Top Shooters** - Mejores tiradores
    
    **🔧 Filtros personalizables:**
    - **Partidos mínimos:** Número mínimo de partidos para aparecer en gráficos de jugadores
    - **Minutos mínimos:** Minutos totales mínimos para análisis de eficiencia
    - **Tiros mínimos:** Tiros mínimos para gráficos de Top Shooters
    """)

with st.expander("⚙️ Configuración de filtros avanzada"):
    st.write("""
    **🎯 Filtros mínimos configurables:**
    
    **🏀 Partidos mínimos (0-20):**
    - Controla qué jugadores aparecen en análisis individuales según participación
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 3-5 para análisis completo, 8-10 para jugadores regulares
    
    **⏱️ Minutos mínimos (0-200):**
    - Filtra por tiempo total de juego en la temporada/fase
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 50-100 para análisis de eficiencia, 150+ para titulares
    
    **🎯 Tiros mínimos (0-100):**
    - Específico para gráfico Top Shooters
    - **0:** Incluye todos los jugadores (sin filtro)
    - **Recomendado:** 15-25 para muestras representativas, 50+ para especialistas
    
    **💡 Consejos de configuración:**
    - **Valores bajos:** Incluye más jugadores, análisis más amplio
    - **Valores altos:** Enfoque en jugadores principales, datos más fiables
    - **Ajuste por fase:** Ajusta según duración de la fase analizada
    """)

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

