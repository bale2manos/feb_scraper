import streamlit as st
import pandas as pd
from PIL import Image
from pathlib import Path
import shutil

# Import the report generation function and constants
from player_report.player_report_gen import generate_report, COL_NAME

# Import file configuration utilities
from utils.file_config_ui import render_file_config_ui, validate_files

# Import config functions
from config import find_best_file, get_available_files_by_type

st.set_page_config(
    page_title="🏀 Generador de Reportes de Jugador",
    page_icon="🏀", 
    layout="wide"
)

st.title("🏀 Generador de Reportes de Jugador")
st.markdown("Genera reportes individuales personalizados para jugadores con estadísticas detalladas.")

# Configuración de archivos
file_paths = render_file_config_ui(
    file_types=['jugadores_aggregated', 'teams_aggregated', 'clutch_aggregated'],
    key_prefix="player_report"
)

# Validar archivos esenciales
essential_files = {k: v for k, v in file_paths.items() if k in ['jugadores_aggregated', 'teams_aggregated']}
if not validate_files(essential_files):
    st.error("❌ **No se pueden cargar los archivos esenciales.** Por favor, verifica la configuración anterior.")
    st.stop()

# Obtener archivos
players_file = file_paths.get('jugadores_aggregated')
teams_file = file_paths.get('teams_aggregated')
clutch_file = file_paths.get('clutch_aggregated')

# Verificar archivo clutch
if clutch_file and clutch_file.exists():
    st.info(f"✅ **Archivo clutch encontrado:** {clutch_file.name}")
else:
    st.warning("⚠️ **Archivo clutch no disponible** - Algunas funcionalidades pueden estar limitadas.")
    clutch_file = None

@st.cache_data
def load_data(file_path):
    """Carga datos desde el archivo especificado."""
    return pd.read_excel(file_path)

# Cargar datos
try:
    df = load_data(players_file)
    st.success(f"✅ Datos cargados: {df.shape[0]} jugadores encontrados")
except Exception as e:
    st.error(f"❌ Error cargando datos: {str(e)}")
    st.stop()

# Adjust columns if needed
player_col = COL_NAME
team_col = 'EQUIPO'

players_df = df[[player_col, team_col]].dropna()
all_players = sorted(players_df[player_col].unique().tolist())
all_teams = sorted(players_df[team_col].unique().tolist())

def gen_single(player_name, data_file, teams_file, clutch_file):
    # Generate and display a single report
    status = st.empty()
    status.info(f'🔄 Generando informe para {player_name}…')
    
    # Pasar los archivos de datos al generador de reportes
    path = generate_report(player_name, data_file=str(data_file), teams_file=str(teams_file), clutch_file=str(clutch_file) if clutch_file else None)
    status.success(f'✅ Generado: {path}')
    try:
        img = Image.open(path)
        st.image(img, use_container_width=True)
    except Exception as e:
        st.error(f'Error al cargar la imagen: {e}')

# App title
st.title("🔧 Generación de informes de jugadores")

# Mode selector
mode = st.radio('Buscar por:', ['Jugador', 'Equipo'], index=0)

# Single selectbox with filtering
if mode == 'Jugador':
    selected = st.selectbox(
        label='Jugador:',
        options=[''] + all_players,
        help='Escribe para filtrar la lista de jugadores'
    )
    entity = selected
else:
    selected = st.selectbox(
        label='Equipo:',
        options=[''] + all_teams,
        help='Escribe para filtrar la lista de equipos'
    )
    entity = selected

# Generate report(s)
if st.button('Generar informe'):
    if not entity:
        st.warning(f'⚠️ Por favor selecciona un {mode.lower()} válido')
    else:
        if mode == 'Jugador':
            if entity in all_players:
                gen_single(entity, players_file, teams_file, clutch_file)
            else:
                st.warning('⚠️ Jugador no encontrado')
        else:
            if entity in all_teams:
                team_players = players_df[players_df[team_col] == entity][player_col].tolist()
                total = len(team_players)
                if total > 0:
                    out_dir = Path("output/player_reports") / entity
                    out_dir.mkdir(parents=True, exist_ok=True)

                    # Preparar contenedores para progreso y texto dinámico
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for i, player_name in enumerate(team_players, start=1):
                        # Actualizar texto de estado
                        status_text.write(f"📄 Informe {i}/{total} en cola: {player_name}")
                        # Generar y mover informe
                        orig_path = generate_report(player_name, data_file=str(players_file), teams_file=str(teams_file), clutch_file=str(clutch_file) if clutch_file else None)
                        dest = out_dir / Path(orig_path).name
                        shutil.move(orig_path, dest)
                        st.success(f'✅ {player_name}: {dest}')
                        try:
                            img = Image.open(dest)
                            st.image(img, caption=player_name, use_container_width=True)
                        except Exception as e:
                            st.error(f'Error al cargar la imagen de {player_name}: {e}')
                        # Actualizar progress bar
                        progress_bar.progress(i/total)
            else:
                st.warning('⚠️ Equipo no encontrado')
