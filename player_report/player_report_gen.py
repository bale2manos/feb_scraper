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
    - Notebook: %run report_generator.ipynb
    - CLI: python report_generator.py -p "Nombre Jugador"

"""
import argparse
import io
from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from rembg import remove

# Para Notebook UI
import ipywidgets as widgets
from IPython.display import display, clear_output
import requests
from ipywidgets.widgets.widget import CallbackDispatcher


from player_report.tools.finalizacion_plays_plot     import plot_finalizacion_plays
from player_report.tools.media_lanzamientos_clutch import plot_media_pct_with_clutch
from player_report.tools.distribucion_puntos_plot    import plot_distribucion_puntos
from player_report.tools.ppt_plays                   import plot_ppt_indicators
from player_report.tools.stats_line_1                import plot_stats_table_simple
from player_report.tools.stats_line_2                import plot_generic_stats_table
from player_report.tools.nacionalidad                import load_countries_data, get_country_flag_image
from config import (
    JUGADORES_AGGREGATED_FILE as DATA_PATH,
    TEAMS_AGGREGATED_FILE as TEAMS_DATA_PATH,
    TEMPLATE_BACKGROUND as TEMPLATE_PATH,
    GENERIC_PLAYER_IMAGE as DEFAULT_PHOTO,
    CLUBS_DIR as CLUB_LOGO_PATH,
    PLAYER_REPORTS_DIR as REPORT_DIR,
    FONT_REGULAR as FONT_PATH,
    FONT_LARGE,
    MAX_NAME_WIDTH
)

# === CONFIG COLUMNAS ===
# Ajusta si tu Excel usa otros nombres de col.
COL_NAME       = 'JUGADOR'
COL_STATS      = ['PJ','Avg. MIN','PPP','USG %','PUNTOS','RT','RD','RO','ASISTENCIAS','PERDIDAS','TO %','TCC','TCI','P. Anot. %']
COL_PPT        = ['PPT1','PPT2','PPT3']
COL_BARS       = {'T1 %':'T1 %','T2 %':'T2 %','T3 %':'T3 %','EFG %':'EFG %','TS %':'TS %'}

# === COORDS (ajusta según plantilla) ===
COORDS = {
    'photo':      (60, 175),
    'photo_size': (225, 315),
    'club_logo':  (1640, 40),  # esquina sup-dcha
    'logo_size':  (190, 190),  # tamaño del logo del club
    'name':       (60, 500),
    'flag':       (60, 560),  # posición de la bandera
    'table_start':(600, 155),  # punto inicial tabla stats
    'ppt':        (930, 400),  # posición de PPT trio
    'bars_start': (-80, 620),   # eje Y donde comienzan barras
    'finalizacion': (820, 640),  # posición de la sección de finalización
    'distribucion': (820, 980),  # posición de la distribución de puntos
}

# Configuración de fuentes
FONT_BIG       = 36
FONT_MED       = 28
FONT_SMALL     = 20

def compute_usg(team_name, minutes, t1_attempts, t2_attempts, t3_attempts, turnovers, teams_file=None):
    teams_path = teams_file if teams_file else TEAMS_DATA_PATH
    df_teams = pd.read_excel(teams_path)
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
    

def compute_advanced_stats(stats_base, teams_file=None):
    """
    Compute advanced basketball statistics from base stats.
    
    Args:
        stats_base: pandas Series with base statistics
        teams_file: Path to teams data file (optional)
        
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
    result['DORSAL'] = stats.get('DORSAL', '')
    result['Fase'] = stats.get('Fase', '')
    result['IMAGEN'] = stats.get('IMAGEN', '')
    result['NACIONALIDAD'] = stats.get('NACIONALIDAD', '')
    bdate_raw = stats.get('FECHA NACIMIENTO', '')
    # Handle NaN values properly (both float NaN and string 'nan')
    if pd.isna(bdate_raw) or bdate_raw == 'nan' or bdate_raw == '':
        bdate_year = ""
    else:
        # Get the year (last part after the last /)
        bdate_year = str(bdate_raw).split("/")[-1]
    result['FECHA NACIMIENTO'] = bdate_year
    result['EQUIPO'] = stats.get('EQUIPO', '')
    result['PUNTOS_TOTALES'] = Puntos
    result['ASISTENCIAS'] = AS
    result['PERDIDAS'] = TOV
    
    result['PJ'] = G  # Games played
    
    # CONVERTIR ESTADÍSTICAS A PROMEDIOS POR PARTIDO
    # NOTA: RECUPEROS y PERDIDAS ya vienen promediados del archivo aggregated
    # El resto vienen como TOTALES y hay que dividir por PJ
    if G > 0:
        Min_avg = Min / G
        Puntos_avg = Puntos / G
        T1C_avg = T1C / G
        T1I_avg = T1I / G
        T2C_avg = T2C / G
        T2I_avg = T2I / G
        T3C_avg = T3C / G
        T3I_avg = T3I / G
        RO_avg = RO / G
        RD_avg = RD / G
        AS_avg = AS / G
        ROB_avg = ROB  # Ya es promedio
        TOV_avg = TOV  # Ya es promedio
        FC_avg = FC / G
        FR_avg = FR / G
    else:
        Min_avg = Puntos_avg = T1C_avg = T1I_avg = T2C_avg = T2I_avg = 0
        T3C_avg = T3I_avg = RO_avg = RD_avg = AS_avg = 0
        ROB_avg = TOV_avg = FC_avg = FR_avg = 0
    
    result['Avg. MIN'] = Min_avg
    result['PUNTOS'] = Puntos_avg
    
    # Plays calculation (possessions used) - usando promedios
    Plays = T1I_avg * 0.44 + T2I_avg + T3I_avg + TOV_avg
    result['Plays'] = Plays
    
    # Points per play
    result['PPP'] = Puntos_avg / Plays if Plays > 0 else 0
    
    # Estadísticas por partido (promedios)
    result['RT'] = RO_avg + RD_avg  # Total rebounds
    result['RD'] = RD_avg  # Defensive rebounds
    result['RO'] = RO_avg  # Offensive rebounds
    result['AS'] = AS_avg  # Assists
    result['ROB'] = ROB_avg  # Steals
    result['TOV'] = TOV_avg  # Turnovers
    result['TOV %'] = per100(TOV_avg, Plays)
    result['FC'] = FC_avg  # Fouls committed
    result['FR'] = FR_avg  # Fouls received

    # Total field goals - promedios por partido
    TCC_avg = T2C_avg + T3C_avg  # Total field goals made per game
    TCI_avg = T2I_avg + T3I_avg  # Total field goals attempted per game
    result['TCC'] = TCC_avg
    result['TCI'] = TCI_avg

    # --- ADVANCED METRICS ---
    
    # Effective Field Goal percentage (usa valores originales para porcentajes)
    result['EFG %'] = ((TCC_avg + 0.5 * T3C_avg) / TCI_avg * 100) if TCI_avg > 0 else 0
    
    # True Shooting percentage
    TSA_avg = TCI_avg + 0.44 * T1I_avg  # True shooting attempts per game
    result['TS %'] = (Puntos_avg / (2 * TSA_avg) * 100) if TSA_avg > 0 else 0
    
    # Free throw rate
    result['RTL'] = (T1I_avg / Plays) if Plays > 0 else 0
    
    # Points per shot type (promedios por partido)
    result['PT1'] = T1C_avg if T1I_avg > 0 else 0  # Points from free throws per game
    result['PT2'] = T2C_avg * 2 if T2I_avg > 0 else 0  # Points from 2-point shots per game
    result['PT3'] = T3C_avg * 3 if T3I_avg > 0 else 0  # Points from 3-point shots per game
    
    # Points per attempt by shot type (porcentajes, no necesitan conversión)
    result['PPT1'] = (T1C_avg / T1I_avg) if T1I_avg > 0 else 0
    result['PPT2'] = (T2C_avg * 2 / T2I_avg) if T2I_avg > 0 else 0
    result['PPT3'] = (T3C_avg * 3 / T3I_avg) if T3I_avg > 0 else 0
    
    # Percentage of points from each shot type relative to PPP
    PPP = result['PPP'] if result['PPP'] > 0 else 1  # Avoid division by zero
    result['PPPT1'] = ((T1C_avg / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    result['PPPT2'] = ((T2C_avg * 2 / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    result['PPPT3'] = ((T3C_avg * 3 / Plays) / PPP) if Plays > 0 and PPP > 0 else 0
    
    # Play distribution percentages (usar promedios)
    result['F1 Plays%'] = (T1I_avg * 0.44 / Plays * 100) if Plays > 0 else 0
    result['F2 Plays%'] = (T2I_avg / Plays * 100) if Plays > 0 else 0
    result['F3 Plays%'] = (T3I_avg / Plays * 100) if Plays > 0 else 0
    result['TO Plays%'] = (TOV_avg / Plays * 100) if Plays > 0 else 0
    
    # Possession Scoring percentage (complex formula) - usar promedios
    if TCC_avg > 0 and T1I_avg > 0:
        FT_miss_impact = (1 - (1 - T1C_avg/T1I_avg)**2) * 0.44 * T1I_avg
        PS_numerator = TCC_avg + FT_miss_impact
    else:
        PS_numerator = TCC_avg
    
    result['PS%'] = (PS_numerator / Plays * 100) if Plays > 0 else 0
    
    # Offensive Efficiency - usar promedios
    OE_denominator = TCI_avg - RO_avg + AS_avg + TOV_avg
    result['OE'] = ((TCC_avg + AS_avg) / OE_denominator) if OE_denominator > 0 else 0
    
    # Efficient Points Scored
    result['EPS'] = Puntos_avg * result['OE']
    
    # Additional calculated stats for the report
    # USG usa TOTALES, no promedios
    result['USG %'] = compute_usg(result['EQUIPO'], Min, T1I, T2I, T3I, TOV, teams_file)
    
    # PS%: Possession Scoring percentage (using the provided formula) - usar promedios
    if TCC_avg > 0 and T1I_avg > 0:
        PS_numerator = TCC_avg + (1 - (1 - T1C_avg / T1I_avg) ** 2) * 0.44 * T1I_avg
    else:
        PS_numerator = 0
    result['P. Anot. %'] = (PS_numerator / Plays * 100) if Plays > 0 else 0
    
    # Individual shooting percentages (porcentajes, usan totales)
    result['T1 %'] = (T1C / T1I * 100) if T1I > 0 else 0
    result['T2 %'] = (T2C / T2I * 100) if T2I > 0 else 0
    result['T3 %'] = (T3C / T3I * 100) if T3I > 0 else 0
    
    # Intentos: ya convertidos a promedios arriba
    result['T1I'] = T1I_avg
    result['T2I'] = T2I_avg
    result['T3I'] = T3I_avg
    
    # Round all percentage values to 2 decimal places
    for key, value in result.items():
        if isinstance(value, (int, float)) and not pd.isna(value):
            if '%' in str(key) or key in ['PPP', 'PPT1', 'PPT2', 'PPT3', 'eFG', 'TS', 'PS', 'OE']:
                result[key] = round(float(value), 2)
            else:
                result[key] = round(float(value), 1)
    
    return result


def fit_font_size(text, font_path, base_size, max_width):
    # measure at base size
    font = ImageFont.truetype(font_path, base_size)
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    # if it already fits, return it
    if text_width <= max_width:
        return font

    # compute new size by proportional scaling
    new_size = int(base_size * max_width / text_width)
    # guard against zero or negative
    new_size = max(new_size, 1)

    # load and then fine-tune (in case of rounding issues)
    font = ImageFont.truetype(font_path, new_size)
    while True:
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_width or new_size <= 1:
            break
        new_size -= 1
        font = ImageFont.truetype(font_path, new_size)

    return font

def generate_report(player_name, data_file=None, teams_file=None, clutch_file=None, output_dir=REPORT_DIR, overwrite=False):
    # cargar datos
    data_path = data_file if data_file else DATA_PATH
    df = pd.read_excel(data_path)
    
    print(f"🔍 Generando informe para {player_name}...")
    print(f"📄 Usando archivo de jugadores: {data_path}")
    if teams_file:
        print(f"📄 Usando archivo de equipos: {teams_file}")
    if clutch_file:
        print(f"📄 Usando archivo clutch: {clutch_file}")
        
    stats_base = df[df[COL_NAME] == player_name].iloc[0]
    
    stats = compute_advanced_stats(stats_base, teams_file)
    
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Standardize filename format: always "SURNAMES NAME"
    if ',' in player_name:
        # Format: "SURNAMES, NAME" -> "SURNAMES NAME" (remove comma, keep order)
        formatted_name = player_name.replace(',', '')
    else:
        # Format: "NAME SURNAMES" -> "SURNAMES NAME" (reverse order)
        parts = player_name.strip().split()
        if len(parts) >= 2:
            # Take first part as name, rest as surnames
            name = parts[0]
            surnames = ' '.join(parts[1:])
            formatted_name = f"{surnames} {name}"
        else:
            # Single name, keep as is
            formatted_name = player_name
    
    # Clean the filename: replace spaces with underscores, remove dots and special characters
    clean_filename = formatted_name.replace(' ', '_').replace('.', '_').replace(',', '').strip('_')
    out_file = output_dir / f"{clean_filename}.png"
    """
    if out_file.exists() and not overwrite:
        return out_file
    """
    # --- BASE TEMPLATE ---
    base = Image.open(TEMPLATE_PATH).convert('RGBA')
    draw = ImageDraw.Draw(base)

    # --- FUENTES Montserrat ---
    font_large = ImageFont.truetype(str(FONT_PATH), FONT_LARGE)
    font_big   = ImageFont.truetype(str(FONT_PATH), FONT_BIG)
    font_med   = ImageFont.truetype(str(FONT_PATH), FONT_MED)
    font_small = ImageFont.truetype(str(FONT_PATH), FONT_SMALL)

    # --- FOTO DEL JUGADOR ---
    photo_url = stats.get('IMAGEN', '')
    # Convert to string and handle NaN/empty values
    if pd.notna(photo_url) and str(photo_url).strip():
        photo_url_str = str(photo_url).strip()
        # Check if the photo URL is a valid path or URL
        if photo_url_str.startswith('http'):
            # Download the image from the URL
            try:
                response = requests.get(photo_url_str, timeout=10)
                response.raise_for_status()
                photo = Image.open(io.BytesIO(response.content)).convert('RGBA')
            except Exception as e:
                print(f"⚠️ Error downloading photo from {photo_url_str}: {e}")
                photo = Image.open(DEFAULT_PHOTO).convert('RGBA')
        else:
            # Try to load as local file
            try:
                photo = Image.open(photo_url_str).convert('RGBA')
            except Exception as e:
                print(f"⚠️ Error loading photo from {photo_url_str}: {e}")
                photo = Image.open(DEFAULT_PHOTO).convert('RGBA')
    else:
        photo = Image.open(DEFAULT_PHOTO).convert('RGBA')
        
    photo_no_bg = remove(photo)  # Remove background using rembg

    photo_no_bg = photo_no_bg.resize(COORDS['photo_size'], Image.LANCZOS)
    base.paste(photo_no_bg, COORDS['photo'], photo_no_bg)

    # --- ESCUDO DEL CLUB ---
    equipo_raw = stats.get('EQUIPO', '')
    equipo = equipo_raw.strip().replace(' ', '_').replace('.', '').lower()
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

    # Resize logo preserving aspect ratio, max height 200
    ratio = logo.width / logo.height
    height = COORDS['logo_size'][1]
    width = int(height * ratio)
    logo = logo.resize((width, height), Image.LANCZOS)
    base.paste(logo, COORDS['club_logo'], logo)

    # --- NOMBRE DEL JUGADOR ---
    x_name, y_name = COORDS['name']
    dorsal = stats.get('DORSAL', '')
    if dorsal:
        name_and_dorsal = f"{dorsal} - {player_name} "
    else:
        name_and_dorsal = player_name
    font = fit_font_size(name_and_dorsal, FONT_PATH, FONT_LARGE, MAX_NAME_WIDTH)

    draw.text((x_name, y_name), name_and_dorsal, font=font, fill="black")

    # --- FECHA DE NACIMIENTO ---
    fecha_nacimiento = stats.get('FECHA NACIMIENTO', '')
    if fecha_nacimiento:
        # Draw the birth date below the name
        draw.text((x_name + 75, y_name + 63), f"{fecha_nacimiento}", font=font_med, fill="black")
    
    # --- NACIONALIDAD ---
    nacionalidad = stats.get('NACIONALIDAD')
    if nacionalidad:
        # Load countries data once
        countries_data = load_countries_data()
        
        # Get flag as PIL Image
        flag_image = get_country_flag_image(nacionalidad, countries_data, flag_size=(60, 40))

        if flag_image:          
            # Paste the flag image
            base.paste(flag_image, COORDS['flag'], flag_image)
            print(f"🏁 Added SVG flag for {nacionalidad}")
        else:
            print(f"⚠️ No flag found for {nacionalidad}")

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

    
    # Prepare stats for second table (line 2) - todos son promedios por partido
    stats_line_2 = {
        "Puntos": f"{stats.get('PUNTOS', 0):.1f}",
        "RT": f"{stats.get('RT', 0):.1f}",
        "RD": f"{stats.get('RD', 0):.1f}",
        "RO": f"{stats.get('RO', 0):.1f}",
        "AST": f"{stats.get('AS', 0):.1f}",
        "TOV": f"{stats.get('TOV', 0):.1f}",
        "TCC": f"{stats.get('TCC', 0):.1f}",
        "TCI": f"{stats.get('TCI', 0):.1f}",
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
    
    # Attempt data for the bars (only for T1, T2, T3)
    # Los intentos ya vienen como promedios por partido desde compute_advanced_stats
    bars_attempts = {
        "T1I": stats.get('T1I', 0),  # Ya es promedio por partido
        "T2I": stats.get('T2I', 0),  # Ya es promedio por partido
        "T3I": stats.get('T3I', 0),  # Ya es promedio por partido
        "EFGI": 0,  # EFG % and TS % don't have direct attempts
        "TSI": 0
    }
    
    bars = plot_media_pct_with_clutch(bars_stats, bars_attempts, player_name_roster=player_name, clutch_file=clutch_file, width_px=3000, resize_px=690)
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
    print("🔧 Iniciando UI para generación de informes de jugadores…")
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
    print("🔘 Preparando controles de UI…")
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

    # 7) Callback de “Generar informe”
    def on_click_fun(b):
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

    # ——————— Evitamos callbacks duplicados ———————
    # Reemplazamos el dispatcher interno por uno nuevo y vacío
    button._click_handlers = CallbackDispatcher()
    # Ahora registramos solo UNA vez nuestro handler
    button.on_click(on_click_fun)

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

