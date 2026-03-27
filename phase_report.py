# app.py
import streamlit as st
from pathlib import Path
import pandas as pd
import os
import re
from phase_report.build_phase_report import build_phase_report

# Import file configuration utilities
from utils.file_config_ui import render_file_config_ui, validate_files
from config import DATA_DIR

# --- Página ---
st.set_page_config(page_title="🏀 Generador de Informe de Fase", layout="wide")
st.title("🏀 Generador de Informe de Fase")
st.markdown("""
Genera informes por fases de competición con análisis detallado de equipos.

**🆕 Nueva funcionalidad:**
- ✨ **Filtrado por jornadas:** Analiza rendimiento por fases en jornadas específicas
- 📊 **Análisis temporal:** Compara diferentes momentos de cada fase
- 🎯 **Segmentación avanzada:** Combina filtros de fase y jornada para análisis precisos
- 🌐 **Modo multi-fuente:** Combina equipos de diferentes temporadas, fases y grupos
""")

# --- MODO AVANZADO: Múltiples fuentes ---
st.subheader("⚙️ Modo de Selección de Datos")
advanced_mode = st.checkbox(
    "🌐 Activar Modo Multi-fuente",
    help="Combina equipos de diferentes temporadas, ligas y grupos en un solo informe"
)


def scan_data_sources():
    """Escanea data/ y devuelve lista de fuentes disponibles con sus archivos."""
    data_dir = Path(DATA_DIR)
    sources = []

    if not data_dir.exists():
        return sources

    LIGA_NAMES = {'1FEB': 'Primera FEB', '2FEB': 'Segunda FEB', '3FEB': 'Tercera FEB'}

    for folder in sorted(data_dir.iterdir()):
        if not folder.is_dir():
            continue

        # Detectar archivos de teams y players
        teams_file = None
        players_file = None
        for f in folder.glob("teams_*.xlsx"):
            teams_file = f
        for f in folder.glob("players_*.xlsx"):
            # Excluir players_*_games.xlsx
            if '_games' not in f.name:
                players_file = f

        if not teams_file:
            continue

        # Parsear nombre de carpeta para extraer metadatos
        name = folder.name
        # Patrón: XFEB_YY_ZZ o XFEB_YY_ZZ_jN_M o XFEB_YY_ZZ_aa_bb
        m = re.match(r'^(\dFEB)_(\d{2}_\d{2})(.*)?$', name)
        if not m:
            continue

        liga_code = m.group(1)
        season = m.group(2)
        suffix = m.group(3) or ''

        liga_name = LIGA_NAMES.get(liga_code, liga_code)
        season_display = f"20{season.replace('_', '/')}"

        # Determinar descripción del sufijo
        if not suffix:
            detail = "Todas las jornadas"
        elif suffix.startswith('_j'):
            jornadas = suffix[2:].split('_')
            detail = f"Jornadas {', '.join(jornadas)}"
        elif suffix == '_old':
            detail = "Datos antiguos"
        else:
            detail = f"Grupo {suffix.lstrip('_').upper()}"

        label = f"{liga_name} {season_display} — {detail}"

        sources.append({
            'label': label,
            'folder': folder,
            'liga': liga_name,
            'liga_code': liga_code,
            'season': season,
            'detail': detail,
            'teams_file': teams_file,
            'players_file': players_file,
        })

    return sources


if advanced_mode:
    st.info("🌐 **Modo Multi-fuente:** Selecciona varias fuentes de datos y combina equipos de diferentes orígenes.")

    all_sources = scan_data_sources()

    if not all_sources:
        st.error("❌ No se encontraron carpetas con datos en `data/`")
        st.stop()

    # Agrupar por liga para mejor visualización
    sources_by_liga = {}
    for src in all_sources:
        sources_by_liga.setdefault(src['liga'], []).append(src)

    # Selector de fuentes
    st.write("**📁 Fuentes de datos disponibles:**")

    source_labels = [s['label'] for s in all_sources]
    selected_labels = st.multiselect(
        "Selecciona las fuentes a combinar:",
        options=source_labels,
        help="Puedes seleccionar varias temporadas, ligas y grupos a la vez",
        placeholder="Ej: Segunda FEB 2025/26, Tercera FEB 2025/26..."
    )

    if not selected_labels:
        # Mostrar resumen de lo disponible
        for liga, sources in sources_by_liga.items():
            with st.expander(f"🏀 {liga} ({len(sources)} fuentes)"):
                for src in sources:
                    has_players = "✅" if src['players_file'] else "❌"
                    st.write(f"  • **{src['detail']}** — `{src['folder'].name}/` (equipos ✅ | jugadores {has_players})")
        st.warning("⚠️ Selecciona al menos una fuente para continuar")
        st.stop()

    # Cargar datos de las fuentes seleccionadas
    selected_sources = [s for s in all_sources if s['label'] in selected_labels]

    all_teams_dfs = []
    all_players_dfs = []

    for src in selected_sources:
        try:
            df_t = pd.read_excel(src['teams_file'])
            df_t['_SOURCE'] = src['label']
            all_teams_dfs.append(df_t)
        except Exception as e:
            st.error(f"❌ Error cargando equipos de {src['label']}: {e}")

        if src['players_file']:
            try:
                df_p = pd.read_excel(src['players_file'])
                df_p['_SOURCE'] = src['label']
                all_players_dfs.append(df_p)
            except Exception as e:
                st.warning(f"⚠️ Error cargando jugadores de {src['label']}: {e}")

    if not all_teams_dfs:
        st.error("❌ No se pudieron cargar datos de equipos")
        st.stop()

    df_teams = pd.concat(all_teams_dfs, ignore_index=True)
    df_players = pd.concat(all_players_dfs, ignore_index=True) if all_players_dfs else pd.DataFrame()

    st.success(f"✅ **{len(df_teams)} registros** de equipos combinados de **{len(selected_sources)} fuente(s)**")

    # Mostrar resumen
    with st.expander("📊 Detalle de fuentes cargadas", expanded=False):
        for src in selected_sources:
            n_teams = len([d for d in all_teams_dfs if d['_SOURCE'].iloc[0] == src['label']])
            st.write(f"  • **{src['label']}** — `{src['folder'].name}/`")

    # Guardar a archivos temporales para compatibilidad
    teams_file = Path(DATA_DIR) / "_temp_combined_teams.xlsx"
    players_file = Path(DATA_DIR) / "_temp_combined_players.xlsx" if not df_players.empty else None

    df_teams.to_excel(teams_file, index=False)
    if players_file and not df_players.empty:
        df_players.to_excel(players_file, index=False)

else:
    # Modo normal — un solo archivo (flujo original)
    file_paths = render_file_config_ui(
        file_types=['teams_aggregated', 'jugadores_aggregated'],
        key_prefix="phase_report"
    )

    if not validate_files(file_paths):
        st.error("❌ **No se pueden cargar los archivos necesarios.** Por favor, verifica la configuración anterior.")
        st.stop()

    teams_file = file_paths.get('teams_aggregated')
    players_file = file_paths.get('jugadores_aggregated')

    try:
        df_teams = pd.read_excel(teams_file)
        st.success(f"✅ Datos cargados: {df_teams.shape[0]} equipos encontrados")
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        st.stop()

# --- Preparar opciones de selección ---
equipos_list = sorted(df_teams['EQUIPO'].dropna().unique().tolist())
fases = sorted(df_teams['FASE'].dropna().unique().tolist())

if advanced_mode and '_SOURCE' in df_teams.columns:
    # En modo multi-fuente, mostrar equipos con su origen
    equipos_with_source = df_teams[['EQUIPO', '_SOURCE']].drop_duplicates().sort_values(['_SOURCE', 'EQUIPO'])
    equipos_options = [
        f"{row['EQUIPO']}  ⸱  {row['_SOURCE']}"
        for _, row in equipos_with_source.iterrows()
    ]
    equipos_map = {
        f"{row['EQUIPO']}  ⸱  {row['_SOURCE']}": row['EQUIPO']
        for _, row in equipos_with_source.iterrows()
    }
    st.info("💡 Los equipos muestran su fuente de origen para distinguir entre ligas/temporadas")
else:
    equipos_options = equipos_list
    equipos_map = {e: e for e in equipos_options}

# --- Widgets ---
sel_equipos_display = st.multiselect(
    "Equipo(s):",
    options=equipos_options,
    placeholder="Selecciona equipos si es necesario"
)
sel_equipos = [equipos_map[e] for e in sel_equipos_display]

sel_fases = st.multiselect(
    "Fase(s):",
    options=fases,
    placeholder="Selecciona fases si es necesario"
)

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

with st.expander("🌐 Modo Multi-fuente"):
    st.write("""
    **🌐 Combina datos de múltiples fuentes automáticamente:**
    
    El sistema escanea la carpeta `data/` y detecta todas las fuentes disponibles:
    
    **📁 Detección automática:**
    - Temporadas (24/25, 25/26, etc.)
    - Ligas (Primera, Segunda, Tercera FEB)
    - Grupos (AA, BA, BB, etc.)
    - Jornadas específicas (j1, j2, j1_2_3, etc.)
    
    **🎯 Casos de uso:**
    - Comparar equipos de diferentes grupos de una misma liga
    - Analizar equipos de diferentes temporadas
    - Mezclar datos de Primera, Segunda y Tercera FEB
    - Combinar datos completos con datos de jornadas específicas
    """)

with st.expander("ℹ️ Información sobre el Análisis Temporal"):
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

