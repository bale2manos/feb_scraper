# -*- coding: utf-8 -*-
"""
Generador automático de informes individuales – modo Notebook y CLI
=====================================================================

Este script genera una lámina PNG con el informe de un jugador de baloncesto
siguiendo tu plantilla `player_template.png` (esquinas negra y naranja).

Requisitos:
    - Python ≥3.8
    - pandas, pillow, matplotlib, ipywidgets
      pip install pandas pillow matplotlib ipywidgets

Uso:
    - Notebook: %run report_generator.py -> ui()
    - CLI: python report_generator.py -p "Nombre Jugador"

"""
import argparse
from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import io

# Para Notebook UI
import ipywidgets as widgets
from IPython.display import display, clear_output

from tools.finalizacion_plays_plot import plot_finalizacion_plays
from tools.media_lanzamientos_plot import plot_media_pct
from tools.distribucion_puntos_plot import plot_distribucion_puntos
from tools.ppt_plays import plot_ppt_indicators
from tools.stats_line_1 import plot_stats_table_simple
from tools.stats_line_2 import plot_generic_stats_table

# === RUTAS ===
DATA_PATH      = Path("data/jugadores_aggregated.xlsx")
TEAMS_DATA_PATH = Path("data/teams_aggregated.xlsx")
TEMPLATE_PATH  = Path("images/templates/player_template.png")
DEFAULT_PHOTO   = Path("images/templates/generic_player.png")
CLUB_LOGO_PATH = Path("images/clubs/")
REPORT_DIR     = Path("output")

# === CONFIG COLUMNAS ===
# Ajusta si tu Excel usa otros nombres de col.
COL_NAME       = 'JUGADOR'
COL_STATS      = ['PJ','Avg. MIN','PPP','USG %','PUNTOS','RT','RD','RO','ASISTENCIAS','PERDIDAS','TO %','TCC','TCI','P. Anot. %']
COL_PPT        = ['PPT1','PPT2','PPT3']
COL_BARS       = {'T1 %':'T1 %','T2 %':'T2 %','T3 %':'T3 %','EFG %':'EFG %','TS %':'TS %'}

# === COORDS (ajusta según plantilla) ===
COORDS = {
    'photo':      (60, 180),
    'photo_size': (200, 280),
    'club_logo':  (1640, 40),  # esquina sup-dcha
    'logo_size':  (190, 190),  # tamaño del logo del club
    'name':       (60, 480),
    'table_start':(600, 155),  # punto inicial tabla stats
    'ppt':        (1000, 400),  # posición de PPT trio
    'bars_start': (-80, 570),   # eje Y donde comienzan barras
    'finalizacion': (820, 610),  # posición de la sección de finalización
    'distribucion': (820, 950),  # posición de la distribución de puntos
}

# Ajusta esta ruta al .ttf de Montserrat que tengas instalado
FONT_PATH      = Path("fonts/Montserrat-Regular.ttf")
FONT_LARGE     = 48
FONT_MED       = 28
FONT_SMALL     = 20

def compute_usg(team_name, minutes, t1_attempts, t2_attempts, t3_attempts, turnovers):
    df_teams = pd.read_excel(TEAMS_DATA_PATH)
    team_totals = df_teams.rename(columns={
        "MINUTOS JUGADOS": "team_MP",
        "T2 INTENTADO":    "team_T2I",
        "T3 INTENTADO":    "team_T3I",
        "TL INTENTADOS":   "team_FTA",   # Free throws attempted
        "PERDIDAS":        "team_TOV",
    })
    
    team_totals['team_FGA'] = team_totals['team_T2I'] + team_totals['team_T3I']
    team_row = team_totals[team_totals['EQUIPO'] == team_name]
    if team_row.empty:
        print(f"⚠️ Equipo '{team_name}' no encontrado en los datos.")
        return 0.0
    
    team_row = team_row.iloc[0]
    team_MP = team_row['team_MP']
    team_FGA = team_row['team_FGA']
    team_FTA = team_row['team_FTA']
    team_TOV = team_row['team_TOV']
    player_FTA = t1_attempts
    player_FGA = t2_attempts + t3_attempts
    player_TOV = turnovers
    player_minutes = minutes

    num = (player_FGA + 0.44 * player_FTA + player_TOV) * (team_MP / 5)
    den = player_minutes * (team_FGA + 0.44 * team_FTA + team_TOV)
    usg = (num / den) if den else 0.0
    
    return round(usg * 100, 2)  # Devuelve en porcentaje
    
    


def compute_advanced_stats(stats_base):
    """
    Compute advanced basketball statistics from base stats.
    
    Args:
        stats_base: pandas Series with base statistics
        
    Returns:
        dict: Dictionary with all computed advanced statistics
    """
    import pandas as pd
    import numpy as np
    
    def per100(numerator, denominator):
        """Calculate per 100 possessions stat, handling division by zero"""
        if denominator == 0 or pd.isna(denominator):
            return 0.0
        return (numerator / denominator) * 100
    
    # Create a copy to work with
    stats = stats_base.copy()
    
    # Map column names to shorter variables for easier calculations
    # Base stats mapping
    G = stats.get('PJ', stats.get('GAMES', 0))  # Games played
    Min = stats.get('MINUTOS JUGADOS', 0)       # Minutes played
    Puntos = stats.get('PUNTOS', 0)             # Points
    
    # Shooting stats
    T1C = stats.get('TL CONVERTIDOS', 0)        # Free throws made
    T1I = stats.get('TL INTENTADOS', 0)         # Free throws attempted
    T2C = stats.get('T2 CONVERTIDO', 0)         # 2-point field goals made
    T2I = stats.get('T2 INTENTADO', 0)          # 2-point field goals attempted
    T3C = stats.get('T3 CONVERTIDO', 0)         # 3-point field goals made
    T3I = stats.get('T3 INTENTADO', 0)          # 3-point field goals attempted
    
    # Other stats
    RO = stats.get('REB OFFENSIVO', 0)          # Offensive rebounds
    RD = stats.get('REB DEFENSIVO', 0)          # Defensive rebounds
    AS = stats.get('ASISTENCIAS', 0)            # Assists
    ROB = stats.get('RECUPEROS', 0)             # Steals
    TOV = stats.get('PERDIDAS', 0)               # Turnovers
    FC = stats.get('FaltasCOMETIDAS', 0)        # Fouls committed
    FR = stats.get('FaltasRECIBIDAS', 0)        # Fouls received
    
    # --- BASIC CALCULATED STATS ---
    result = {}
    
    # Copy original data first
    result['JUGADOR'] = stats.get('JUGADOR', 'Unknown Player')
    result['DORSAL'] = stats.get('DORSALES', '')
    result['Fase'] = stats.get('Fase', '')
    result['EQUIPO'] = stats.get('EQUIPO', '')
    result['PUNTOS_TOTALES'] = Puntos
    result['ASISTENCIAS'] = AS
    result['PERDIDAS'] = TOV
    
    result['PJ'] = G  # Games played
    result['Avg. MIN'] = Min / G if G > 0 else 0  # Average minutes per game
    result['PUNTOS'] = Puntos / G if G > 0 else 0  # Average points per game

    
    # Plays calculation (possessions used)
    Plays = T1I * 0.44 + T2I + T3I + TOV
    result['Plays'] = Plays
    
    # Points per play
    result['PPP'] = Puntos / Plays
    
    # Per 100 possessions stats
    result['RT'] = (RO + RD) / G if G > 0 else 0  # Total rebounds
    result['RD'] = RD / G if G > 0 else 0  # Defensive rebounds
    result['RO'] = RO / G if G > 0 else 0  # Offensive rebounds
    result['AS'] = AS / G if G > 0 else 0  # Assists
    result['ROB'] = ROB / G if G > 0 else 0  # Steals
    result['TOV'] = TOV / G if G > 0 else 0  # Turnovers
    result['TOV %'] = per100(TOV, Plays)
    result['FC'] = FC / G if G > 0 else 0  # Fouls committed
    result['FR'] = FR / G if G > 0 else 0  # Fouls received

    # Total field goals
    TCC = T2C + T3C  # Total field goals made
    TCI = T2I + T3I  # Total field goals attempted
    result['TCC'] = TCC / G if G > 0 else 0  # Total field goals per game
    result['TCI'] = TCI / G if G > 0 else 0  # Total field goals attempted per game

    # --- ADVANCED METRICS ---
    
    # Effective Field Goal percentage
    result['EFG %'] = ((TCC + 0.5 * T3C) / TCI * 100) if TCI > 0 else 0
    
    # True Shooting percentage
    TSA = TCI + 0.44 * T1I  # True shooting attempts
    result['TS %'] = (Puntos / (2 * TSA) * 100) if TSA > 0 else 0
    
    # Free throw rate
    result['RTL'] = (T1I / Plays) if Plays > 0 else 0
    
    # Points per shot type
    result['PT1'] = T1C if T1I > 0 else 0  # Points from free throws
    result['PT2'] = T2C * 2 if T2I > 0 else 0  # Points from 2-point shots
    result['PT3'] = T3C * 3 if T3I > 0 else 0  # Points from 3-point shots
    
    # Points per attempt by shot type
    result['PPT1'] = (T1C / T1I) if T1I > 0 else 0
    result['PPT2'] = (T2C * 2 / T2I) if T2I > 0 else 0
    result['PPT3'] = (T3C * 3 / T3I) if T3I > 0 else 0
    
    # Percentage of points from each shot type relative to PPP
    PPP = result['PPP'] if result['PPP'] > 0 else 1  # Avoid division by zero
    result['PPPT1'] = ((T1C / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    result['PPPT2'] = ((T2C * 2 / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    result['PPPT3'] = ((T3C * 3 / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    
    # Play distribution percentages
    result['F1 Plays%'] = (T1I * 0.44 / Plays * 100) if Plays > 0 else 0
    result['F2 Plays%'] = (T2I / Plays * 100) if Plays > 0 else 0
    result['F3 Plays%'] = (T3I / Plays * 100) if Plays > 0 else 0
    result['TO Plays%'] = (TOV / Plays * 100) if Plays > 0 else 0
    
    # Possession Scoring percentage (complex formula)
    if TCC > 0 and T1I > 0:
        FT_miss_impact = (1 - (1 - T1C/T1I)**2) * 0.44 * T1I
        PS_numerator = TCC + FT_miss_impact
    else:
        PS_numerator = TCC
    
    result['PS%'] = (PS_numerator / Plays * 100) if Plays > 0 else 0
    
    # Offensive Efficiency
    OE_denominator = TCI - RO + AS + TOV
    result['OE'] = ((TCC + AS) / OE_denominator) if OE_denominator > 0 else 0
    
    # Efficient Points Scored
    result['EPS'] = Puntos * result['OE']
    
    # Additional calculated stats for the report
    # TODO calcular USG
    result['USG %'] = compute_usg(result['EQUIPO'], Min, T1I, T2I, T3I, TOV)
    
    # PS%: Possession Scoring percentage (using the provided formula)
    if TCC != 0 and T1I > 0:
        PS_numerator = TCC + (1 - (1 - T1C / T1I) ** 2) * 0.44 * T1I
    else:
        PS_numerator = 0
    result['P. Anot. %'] = (PS_numerator / Plays * 100) if Plays > 0 else 0
    
    # Individual shooting percentages
    result['T1 %'] = (T1C / T1I * 100) if T1I > 0 else 0
    result['T2 %'] = (T2C / T2I * 100) if T2I > 0 else 0
    result['T3 %'] = (T3C / T3I * 100) if T3I > 0 else 0
    
    # Round all percentage values to 2 decimal places
    for key, value in result.items():
        if isinstance(value, (int, float)) and not pd.isna(value):
            if '%' in str(key) or key in ['PPP', 'PPT1', 'PPT2', 'PPT3', 'eFG', 'TS', 'PS', 'OE']:
                result[key] = round(float(value), 2)
            else:
                result[key] = round(float(value), 1)
    
    return result


def generate_report(player_name, output_dir=REPORT_DIR, overwrite=False):
    # cargar datos
    df = pd.read_excel(DATA_PATH)
    stats_base = df[df[COL_NAME] == player_name].iloc[0]
    
    stats = compute_advanced_stats(stats_base)
    
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{player_name.replace(' ', '_')}_report.png"
    """
    if out_file.exists() and not overwrite:
        return out_file
    """
    # --- BASE TEMPLATE ---
    base = Image.open(TEMPLATE_PATH).convert('RGBA')
    draw = ImageDraw.Draw(base)

    # --- FUENTES Montserrat ---
    font_large = ImageFont.truetype(str(FONT_PATH), FONT_LARGE)
    font_med   = ImageFont.truetype(str(FONT_PATH), FONT_MED)
    font_small = ImageFont.truetype(str(FONT_PATH), FONT_SMALL)

    # --- FOTO DEL JUGADOR ---
    # Se busca un archivo con su nombre, si no existe usamos la genérica
    photo_path = Path("photos") / f"{player_name.replace(' ', '_')}.png"
    if photo_path.exists():
        photo = Image.open(photo_path).convert('RGBA')
    else:
        photo = Image.open(DEFAULT_PHOTO).convert('RGBA')

    photo = photo.resize(COORDS['photo_size'], Image.LANCZOS)
    base.paste(photo, COORDS['photo'], photo)

    # --- ESCUDO DEL CLUB ---
    equipo_raw = stats.get('EQUIPO', '')
    equipo = equipo_raw.strip().replace(' ', '_').lower()
    # Also substitute special characters if needed, á, etc --> a and ñ --> n
    equipo = equipo.replace('ñ', 'n').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    try:
        if equipo:
            logo_path = CLUB_LOGO_PATH / f"{equipo}.png"
        else:
            logo_path = CLUB_LOGO_PATH / "generic_club.png"
        
        logo = Image.open(logo_path).convert('RGBA')
    except FileNotFoundError:
        print(f"⚠️ Logo not found for {equipo} at {logo_path}. Using default logo.")
        logo_path = CLUB_LOGO_PATH / "generic_club.png"
        logo = Image.open(logo_path).convert('RGBA')

    logo = logo.resize(COORDS['logo_size'], Image.LANCZOS)
    base.paste(logo, COORDS['club_logo'], logo)

    # --- NOMBRE DEL JUGADOR ---
    x_name, y_name = COORDS['name']
    dorsal = stats.get('DORSAL', '')
    if dorsal:
        name_and_dorsal = f"{dorsal} - {player_name} "
    else:
        name_and_dorsal = player_name
    draw.text((x_name, y_name), name_and_dorsal, font=font_large, fill="black")

    # --- TABLA ESTADÍSTICA (líneas 1 y 2) ---
    # Generate the stats tables as PIL Images directly
    stats_line_1 = {
        "PJ": str(stats.get('PJ', 0)),
        "Avg. MIN": f"{stats.get('Avg. MIN', 0):.1f}",
        "PPP": f"{stats.get('PPP', 0):.2f}",
        "USG %": f"{stats.get('USG %', 0):.2f}%",
    }

    tbl1 = plot_stats_table_simple(stats_line_1, width_px=200, height_px=25)
    base.paste(tbl1, (COORDS['table_start'][0], COORDS['table_start'][1]), tbl1)

    
    # Prepare stats for second table (line 2)
    stats_line_2 = {
        "Puntos": str(stats.get('PUNTOS', 0)),
        "RT": str(stats.get('RT', 0)),
        "RD": str(stats.get('RD', 0)),
        "RO": str(stats.get('RO', 0)),
        "AST": str(stats.get('AS', 0)),
        "TOV": str(stats.get('TOV', 0)),
        "TOV %": f"{stats.get('TOV %', 0):.1f}%",
        "TCC": str(stats.get('TCC', 0)),
        "TCI": str(stats.get('TCI', 0)),
        "P. Anot. %": f"{stats.get('P. Anot. %', 0):.1f}%"
    }
    tbl2 = plot_generic_stats_table(stats_line_2, width_px=1300, height_px=85)

    base.paste(tbl2, (COORDS['table_start'][0]-200, COORDS['table_start'][1] + 120), tbl2)


    # --- MEDIA % LANZAMIENTOS ---
    bars_stats = {
        "T1 %": stats.get('T1 %', 0),
        "T2 %": stats.get('T2 %', 0), 
        "T3 %": stats.get('T3 %', 0),
        "EFG %": stats.get('EFG %', 0),
        "TS %": stats.get('TS %', 0)
    }
    bars = plot_media_pct(bars_stats, width_px=3000, resize_px=690)
    base.paste(bars, (COORDS['bars_start'][0], COORDS['bars_start'][1]), bars)

    # --- PPT INDICATORS ---
    ppt_img = plot_ppt_indicators(stats, width_px=200, height_px=40)
    base.paste(ppt_img, COORDS['ppt'], ppt_img)
    
       # --- FINALIZACIÓN PLAYS + DISTRIBUCIÓN DE PUNTOS ---
    fin_stats = {
        "T1 %": stats.get('F1 Plays%', 0),
        "T2 %": stats.get('F2 Plays%', 0),
        "T3 %": stats.get('F3 Plays%', 0),
        "PP %": stats.get('TO Plays%', 0)  # Turnovers mapped to PP %
    }
    fin = plot_finalizacion_plays(fin_stats, resize_px = 320)
    base.paste(fin, COORDS['finalizacion'], fin)


    dist_stats = {
        "T1C": stats.get('PT1', 0),
        "T2C": stats.get('PT2', 0),
        "T3C": stats.get('PT3', 0)
    }
    dist = plot_distribucion_puntos(dist_stats, resize_px=320)
    # Ajusta posiciones X/Y según tu layout:

    base.paste(dist, COORDS['distribucion'], dist)

    # --- GUARDAR ---
    base.save(out_file)
    return out_file


def ui():
    # 1) Cargo datos y lista de jugadores
    df      = pd.read_excel(DATA_PATH)
    players = sorted(df[COL_NAME].dropna().unique().tolist())

    # 2) Campo de texto para escribir
    search = widgets.Text(
        placeholder='Escribe para buscar…',
        description='Jugador:',
        layout=widgets.Layout(width='300px')
    )

    # 3) “Dropdown” de sugerencias (un Select de pocas filas)
    suggest = widgets.Select(
        options=[],
        rows=5,
        layout=widgets.Layout(width='300px')
    )

    # 4) Botón y área de salida
    button = widgets.Button(description='Generar informe', button_style='primary')
    out    = widgets.Output()

    # 5) Al escribir en el text, filtrar la lista
    def on_type(change):
        txt = change['new'].lower()
        if txt:
            matches = [p for p in players if txt in p.lower()]
        else:
            matches = []
        suggest.options = matches[:10]  # máximo 10 sugerencias
    search.observe(on_type, names='value')

    # 6) Cuando seleccionas de la lista, lo pones en el campo de texto
    def on_select(change):
        if change['new']:
            search.value = change['new']
    suggest.observe(on_select, names='value')

    # 7) Al pulsar “Generar”, feedback y ejecución
    def on_click(b):
        out.clear_output()
        with out:
            print("🔄 Generando informe…")
            display(widgets.HTML("<i></i>"))  # fuerza redraw
            nombre = search.value
            if nombre not in players:
                clear_output()
                print("⚠️ Jugador no encontrado")
                return
            path = generate_report(nombre)
            clear_output()
            print(f"✅ Generado: {path}")
            display(Image.open(path))
    button.on_click(on_click)

    # 8) Compongo la UI
    controls = widgets.HBox([search, button], layout=widgets.Layout(gap='10px'))
    display(widgets.VBox([controls, suggest, out]))
    
    
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generar informe jugador')
    parser.add_argument('-p', '--player', help='Nombre completo del jugador')
    parser.add_argument('-a', '--all', action='store_true', help='Generar para todos los jugadores')
    parser.add_argument('-o', '--output-dir', default=str(REPORT_DIR), help='Carpeta de salida')
    parser.add_argument('--overwrite', action='store_true', help='Sobrescribir si existe')
    args = parser.parse_args()
    out_dir = Path(args.output_dir)

    if args.all:
        df = pd.read_excel(DATA_PATH)
        for nm in df[COL_NAME].dropna().unique():
            generate_report(nm, output_dir=out_dir, overwrite=args.overwrite)
    elif args.player:
        generate_report(args.player, output_dir=out_dir, overwrite=args.overwrite)
    else:
        print("Usa -p 'Nombre' o -a para todos")
  
