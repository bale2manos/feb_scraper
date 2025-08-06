import streamlit as st
import pandas as pd
from PIL import Image
from pathlib import Path
import shutil

# Import the report generation function and constants
from player_report.player_report_gen import generate_report, DATA_PATH, COL_NAME

@st.cache_data
def load_data():
    return pd.read_excel(DATA_PATH)

# Adjust columns if needed
player_col = COL_NAME
team_col = 'EQUIPO'

df = load_data()
players_df = df[[player_col, team_col]].dropna()
all_players = sorted(players_df[player_col].unique().tolist())
all_teams = sorted(players_df[team_col].unique().tolist())

def gen_single(player_name):
    # Generate and display a single report
    status = st.empty()
    status.info(f'🔄 Generando informe para {player_name}…')
    path = generate_report(player_name)
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
                gen_single(entity)
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
                        orig_path = generate_report(player_name)
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
