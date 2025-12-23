"""
Utility functions for basketball analytics visualizations.
Contains common functions for data processing, color manipulation, 
logo handling, and player name formatting.
"""

import os
import numpy as np
from PIL import Image
import pandas as pd


def format_player_name(jugador: str, dorsal: str | int) -> str:
    """
    Format player name from 'SURNAMES, NAME' or 'I. SURNAMES' to 'DORSAL - NAME FIRST_SURNAME'
    If there are 3+ names, show only the first two.
    Handles dorsal in 'recent/previous' format (e.g., '15/16') by using the first number.
    """
    # Convert dorsal to string and extract first number if in 'recent/previous' format
    dorsal_str = str(dorsal)
    if '/' in dorsal_str:
        dorsal_str = dorsal_str.split('/')[0]
    
    if ', ' in jugador:
        # Format: SURNAMES, NAME
        surnames, name = jugador.split(', ', 1)
        # Take only the first surname if there are multiple
        first_surname = surnames.split()[0]
        # If name has multiple parts, take only first two
        name_parts = name.split()
        if len(name_parts) >= 2:
            name = ' '.join(name_parts[:2])
        return f"{dorsal_str} - {name} {first_surname}"
    elif '. ' in jugador and len(jugador.split('. ')[0]) == 1:
        # Format: I. SURNAMES (initial and surnames)
        initial, surnames = jugador.split('. ', 1)
        # Take only the first surname if there are multiple
        first_surname = surnames.split()[0]
        return f"{dorsal_str} - {initial}. {first_surname}"
    else:
        # Fallback for other formats - limit to first two words
        parts = jugador.split()
        if len(parts) >= 2:
            jugador = ' '.join(parts[:2])
        return f"{dorsal_str} - {jugador}"


def lighten_color(hex_color: str, factor: float = 0.3) -> str:
    """Lighten a hex color by a given factor (0.0 to 1.0), but never reach pure white."""
    # Remove '#' and convert to RGB
    hex_color = hex_color.lstrip('#')
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    
    # Lighten by moving towards light grey (230) instead of pure white (255)
    target = 230  # Light grey instead of white
    lightened = [min(target, int(c + (target - c) * factor)) for c in rgb]
    
    return f"#{lightened[0]:02x}{lightened[1]:02x}{lightened[2]:02x}"


def darken_color(hex_color: str, factor: float = 0.3) -> str:
    """Darken a hex color by a given factor (0.0 to 1.0)."""
    # Remove '#' and convert to RGB
    hex_color = hex_color.lstrip('#')
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    
    # Darken by moving towards black (0), but not too much
    darkened = [max(50, int(c * (1 - factor))) for c in rgb]  # Min value 50 to avoid too dark
    
    return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"


def lighten_color_rgb(rgb_color, factor=0.6):
    """Lighten an RGB color tuple by a given factor."""
    r, g, b = rgb_color
    # Lighten by moving towards white
    lightened = (
        min(1.0, r + (1.0 - r) * factor),
        min(1.0, g + (1.0 - g) * factor),
        min(1.0, b + (1.0 - b) * factor)
    )
    return lightened


def is_dark_color(hex_color: str) -> bool:
    """Check if a color is dark (luminance < 0.5)."""
    hex_color = hex_color.lstrip('#')
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    
    # Calculate luminance
    luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    return luminance < 0.5


def get_team_logo(team_name: str):
    """Load team logo image from images/clubs/ directory."""
    fn = (team_name.lower()
               .replace(' ', '_')
               .replace('.', '')
               .replace(',', '')
               .replace('á', 'a')
               .replace('é', 'e')
               .replace('í', 'i')
               .replace('ó', 'o')
               .replace('ú', 'u')
               .replace('ñ', 'n')
               .replace('ü', 'u'))
    path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'images', 'clubs',
        f'{fn}.png'
    )
    if os.path.exists(path):
        return Image.open(path).convert('RGBA')
    else:
        print(f"⚠️ Logo not found for team: {team_name} (looking for {path})")
    return None



def compute_team_stats(df: pd.DataFrame, teams: list[str] | None = None, phase: str | None = None) -> pd.DataFrame:
    """
    Compute aggregated statistics for teams from the provided DataFrame.
    
    Parameters:
    - df: DataFrame containing player statistics.
    - teams: Optional list of teams to filter. If None, all teams are included.
    - phase: Optional phase to filter by (e.g., 'Liga Regular').
    
    Returns:
    - DataFrame with aggregated team statistics.
    """
    # 1) Filter by phase if provided
    if phase is not None:
        df = df[df['FASE'].isin(phase)]
    
    # 2) Filter by teams if provided
    if teams is not None and len(teams) > 0:
        df = df[df['EQUIPO'].isin(teams)]
        
    T1C = df.get('TL CONVERTIDOS', 0)        # Free throws made
    T1I = df.get('TL INTENTADOS', 0)         # Free throws attempted
    T2C = df.get('T2 CONVERTIDO', 0)         # 2-point field goals made
    T2I = df.get('T2 INTENTADO', 0)          # 2-point field goals attempted
    T3C = df.get('T3 CONVERTIDO', 0)         # 3-point field goals made
    T3I = df.get('T3 INTENTADO', 0)          # 3-point field goals attempted

    RO = df.get('REB OFFENSIVO', 0)          # Offensive rebounds
    RD = df.get('REB DEFENSIVO', 0)          # Defensive rebounds
    AS = df.get('ASISTENCIAS', 0)            # Assists
    ROB = df.get('RECUPEROS', 0)             # Steals
    TOV = df.get('PERDIDAS', 0)               # Turnovers
    FC = df.get('FaltasCOMETIDAS', 0)        # Fouls committed
    FR = df.get('FaltasRECIBIDAS', 0)        # Fouls received
    Plays = df.get('PLAYS', 0)
        
    # 3) Rename columns for clarity
    df.rename(columns={
        'T2 CONVERTIDO': 'T2C',
        'T2 INTENTADO': 'T2I',
        'T3 CONVERTIDO': 'T3C',
        'T3 INTENTADO': 'T3I',
        'TL CONVERTIDOS': 'T1C',
        'TL INTENTADOS': 'T1I',
        'PTS_RIVAL': 'PUNTOS -',
        'REB OFFENSIVO': 'OREB',
        'REB DEFENSIVO': 'DREB',
        'ASISTENCIAS': 'AST',
        'RECUPEROS': 'ROB',
        'PERDIDAS': 'TOV',
        'FaltasCOMETIDAS': 'FC',
        'FaltasRECIBIDAS': 'FR'
    }, inplace=True)
    
    # Además de esas, el dataset contiene:
    # 'EQUIPO', 'FASE', 'MINUTOS JUGADOS', 'PUNTOS +', 'PPP', 'PPP OPP', 'PJ', 'PLAYS'
    # 'OFFRTG', 'DEFRTG', 'NETRTG', '%OREB', '%DREB', '%REB'

    # Tiros de campo
    df['TCC'] = T2C + T3C  # Total field goals made
    df['TCI'] = T2I + T3I  # Total field goals

    # Normalizar intentos de tiro por partido jugado (TOV ya está promediado en este dataset)
    PJ = df.get('PJ', 1)
    T1I_per_game = T1I / PJ
    T2I_per_game = T2I / PJ
    T3I_per_game = T3I / PJ
    TOV_per_game = TOV  # TOV ya está promediado por partido en este dataset
    
    # Recalcular Plays por partido para consistencia
    Plays_per_game = T1I_per_game * 0.44 + T2I_per_game + T3I_per_game + TOV_per_game

    # Play distribution percentages - Using vectorized operations
    df['F1 Plays%'] = np.where(Plays_per_game > 0, (T1I_per_game * 0.44 / Plays_per_game * 100), 0)
    df['F2 Plays%'] = np.where(Plays_per_game > 0, (T2I_per_game / Plays_per_game * 100), 0)
    df['F3 Plays%'] = np.where(Plays_per_game > 0, (T3I_per_game / Plays_per_game * 100), 0)
    df['TO Plays%'] = np.where(Plays_per_game > 0, (TOV_per_game / Plays_per_game * 100), 0)
    
    # DEBUG: Mostrar cálculos para la primera fila
    if len(df) > 0:
        idx = df.index[0]
        print(f"\n{'='*80}")
        print(f"🔍 DEBUG utils.compute_team_stats - EQUIPO: {df.loc[idx, 'EQUIPO']}")
        print(f"{'='*80}")
        print(f"PJ: {df.loc[idx, 'PJ']}")
        print(f"T1I total: {df.loc[idx, 'T1I']}, T2I total: {df.loc[idx, 'T2I']}, T3I total: {df.loc[idx, 'T3I']}")
        print(f"TOV (ya promediado): {df.loc[idx, 'TOV']}")
        print(f"\nValores por partido:")
        print(f"  T1I_per_game: {T1I_per_game.iloc[0]:.2f}")
        print(f"  T2I_per_game: {T2I_per_game.iloc[0]:.2f}")
        print(f"  T3I_per_game: {T3I_per_game.iloc[0]:.2f}")
        print(f"  TOV_per_game (sin dividir): {TOV_per_game.iloc[0]:.2f}")
        print(f"\nPlays calculadas por partido: {Plays_per_game.iloc[0]:.2f}")
        print(f"  = {T1I_per_game.iloc[0]:.2f} * 0.44 + {T2I_per_game.iloc[0]:.2f} + {T3I_per_game.iloc[0]:.2f} + {TOV_per_game.iloc[0]:.2f}")
        print(f"\nPorcentajes calculados:")
        print(f"  F1 Plays%: {df.loc[idx, 'F1 Plays%']:.2f}%")
        print(f"  F2 Plays%: {df.loc[idx, 'F2 Plays%']:.2f}%")
        print(f"  F3 Plays%: {df.loc[idx, 'F3 Plays%']:.2f}%")
        print(f"  TO Plays%: {df.loc[idx, 'TO Plays%']:.2f}%")
        total = df.loc[idx, 'F1 Plays%'] + df.loc[idx, 'F2 Plays%'] + df.loc[idx, 'F3 Plays%'] + df.loc[idx, 'TO Plays%']
        print(f"  TOTAL: {total:.2f}%")
        print(f"{'='*80}\n")
    
    # Points per shot type
    df['PT1'] = T1C
    df['PT2'] = T2C *2
    df['PT3'] = T3C *3

    return df

def get_team_main_color(team_name: str):
    """Get the main color from team logo by finding the most common non-transparent color."""
    logo = get_team_logo(team_name)
    if logo is None:
        return '#2F5233'  # Default color
    
    # Convert to RGB array
    img_array = np.array(logo)
    
    # Remove transparent pixels (alpha < 128)
    if img_array.shape[2] == 4:  # RGBA
        non_transparent = img_array[img_array[:, :, 3] > 128]
        if len(non_transparent) == 0:
            return '#2F5233'
        rgb_pixels = non_transparent[:, :3]
    else:  # RGB
        rgb_pixels = img_array.reshape(-1, 3)
    
    # Find the most common color (simplified approach)
    # Group similar colors by rounding to reduce color variations
    rounded_colors = np.round(rgb_pixels / 32) * 32
    # Ensure values don't exceed 255
    rounded_colors = np.clip(rounded_colors, 0, 255)
    unique_colors, counts = np.unique(rounded_colors, axis=0, return_counts=True)
    
    # Get the most common color
    most_common_idx = np.argmax(counts)
    main_color = unique_colors[most_common_idx].astype(int)
    
    # Ensure values are within valid range [0, 255]
    main_color = np.clip(main_color, 0, 255)
    
    # Convert to hex
    return f"#{main_color[0]:02x}{main_color[1]:02x}{main_color[2]:02x}"


def extract_logo_color(path, thumb_size=(50,50)):
    """Load image, downsize, and return its average RGB as a matplotlib color, excluding transparent pixels."""
    im = Image.open(path).convert('RGBA')  # Keep alpha channel
    im.thumbnail(thumb_size)
    arr = np.asarray(im)
    
    # Only consider non-transparent pixels (alpha > 128)
    alpha_mask = arr[:, :, 3] > 128
    if not np.any(alpha_mask):
        # If all pixels are transparent, return default color
        return (0.5, 0.5, 0.5)
    
    # Get RGB values only for non-transparent pixels
    non_transparent_pixels = arr[alpha_mask][:, :3]  # Take only RGB channels
    
    # Calculate average over non-transparent pixels only
    r, g, b = non_transparent_pixels[:, 0].mean(), non_transparent_pixels[:, 1].mean(), non_transparent_pixels[:, 2].mean()

    return (r/255, g/255, b/255)


def compute_plays(df):
    """Compute plays from shooting and turnover data."""
    T1I = df['TL INTENTADOS'].to_numpy()
    T2I = df['T2 INTENTADO'].to_numpy()
    T3I = df['T3 INTENTADO'].to_numpy()
    TOV = df['PERDIDAS'].to_numpy()
    return (T1I * 0.44 + T2I + T3I + TOV)


def compute_ppp(df):
    """Compute Points Per Play (PPP)."""
    plays = compute_plays(df)
    points = df['PUNTOS'].to_numpy()
    return points / plays


def apply_basic_filters(df, min_games=5, min_minutes_avg=10, min_total_minutes=150):
    """Apply basic filters: minimum games played and minutes."""
    return df[
        (df['PJ'] >= min_games) &
        (
            (df['MINUTOS JUGADOS'] >= min_total_minutes) |
            ((df['MINUTOS JUGADOS'] / df['PJ']) >= min_minutes_avg)
        )
    ]


def apply_phase_filter(df, phase):
    """Filter by game phase if specified."""
    if phase is not None:
        return df[df['FASE'].isin(phase)]
    return df


def apply_teams_filter(df, teams):
    """Filter by teams if specified."""
    if teams is not None and len(teams) > 0:
        return df[df['EQUIPO'].isin(teams)]
    return df


def normalize_team_name_for_file(team_name: str) -> str:
    """Normalize team name for file system compatibility."""
    return (team_name.lower()
                     .replace(' ', '_')
                     .replace('.', '')
                     .replace(',', '')
                     .replace('á', 'a')
                     .replace('é', 'e')
                     .replace('í', 'i')
                     .replace('ó', 'o')
                     .replace('ú', 'u'))


def setup_montserrat_font():
    """Setup Montserrat font for matplotlib if available."""
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    
    font_path = os.path.join(os.path.dirname(__file__),
                             '..', '..', 'fonts', 'Montserrat-Regular.ttf')
    if os.path.exists(font_path):
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = prop.get_name()
        return prop
    return None
