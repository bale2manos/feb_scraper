import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from adjustText import adjust_text

from .utils import (
    lighten_color_rgb,
    get_team_logo,
    extract_logo_color,
    setup_montserrat_font,
    apply_basic_filters,
    apply_phase_filter,
    apply_teams_filter,
    compute_plays,
    compute_ppp,
    format_player_name
)

def plot_top_shooters(
    df: pd.DataFrame,
    MIN_SHOTS: int = 150,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    TOP-20 Offensive Efficiency: scatter PPP vs Plays, bubble size ~ minutes,
    color = team's main logo color, median reference lines.
    Filters: PJ>2, MINUTOS JUGADOS>10.
    """
    # 0) load + Montserrat
    setup_montserrat_font()

    # 1) optional filters
    df = apply_phase_filter(df, phase)
    df = apply_teams_filter(df, teams)
    
    # 3) Filter those with less than 50 shots attempted
    df = df[(df['T2 INTENTADO'] + df['T3 INTENTADO']) >= MIN_SHOTS]

    # 3) compute TS % and EFG %
    TCI = df['T2 INTENTADO'] + df['T3 INTENTADO']  # Total attempted shots (2s + 3s)
    TCC = df['T2 CONVERTIDO'] + df['T3 CONVERTIDO']  # Total converted shots (2s + 3s)
    df['EFG %'] = np.where(TCI > 0, (TCC + 0.5 * df['T3 CONVERTIDO']) / TCI * 100, 0)
    TSA = TCI + 0.44 * df['TL INTENTADOS']  # Total shots attempted (including free throws)
    df['TS %'] = np.where(TSA > 0, df['PUNTOS'] / (2*TSA) * 100, 0)

    # 4) prepare data arrays
    x = df['TS %'].to_numpy()
    y = df['EFG %'].to_numpy()
    mins = df['MINUTOS JUGADOS'].to_numpy()
    names = df['JUGADOR'].to_numpy()
    dorsals = df['DORSAL'].to_numpy()
    teams = df['EQUIPO'].to_numpy()
    
    # Format player names using the utility function
    formatted_names = [format_player_name(name, dorsal) for name, dorsal in zip(names, dorsals)]

    # 5) extract colors per row (cache by team)
    color_map = {}
    colors = []
    for team in teams:
        if team not in color_map:
            fn = team.lower().replace(' ','_').replace('.','').replace(',','')
            path = os.path.join(os.path.dirname(__file__),
                                '..','..','images','clubs', f'{fn}.png')
            if os.path.exists(path):
                color_map[team] = extract_logo_color(path)
            else:
                color_map[team] = (0.5,0.5,0.5)
        # If the team color is very dark, lighten it
        if color_map[team] and (sum(color_map[team]) < 1.5):  # Dark color check
            color_map[team] = lighten_color_rgb(color_map[team], factor=0.5)
        
        colors.append(color_map[team])
        

    # 6) guard against empty arrays: return a placeholder figure if no data
    if x.size == 0 or y.size == 0:
        fig, ax = plt.subplots(figsize=(13, 11))
        ax.text(
            0.5, 0.5,
            'No hay suficientes datos para mostrar los Top Shooters\nRevisa filtros o archivos seleccionados',
            ha='center', va='center', fontsize=16, weight='bold'
        )
        ax.axis('off')
        return fig

    # 6) bubble size based on EFG% (50%) and TS% (50%)
    # Higher EFG% = bigger bubbles (50% weight), higher TS% = bigger bubbles (50% weight)
    efg_factor = (y / y.max()) ** 4.0  # Very strong EFG% influence for dramatic differences (50% weight)
    ts_factor = (x / x.max()) ** 4.0  # Same strong TS% influence for dramatic differences (50% weight)
    s = (0.5 * efg_factor + 0.5 * ts_factor) * 1500  # Equal weighting between EFG% and TS%

    # 7) compute medians
    xm, ym = np.median(x), np.median(y)

    # 8) plot with team-colored circles as bubble backgrounds
    fig, ax = plt.subplots(figsize=(13,11))
    # Draw circles with original team colors (no lightening)
    ax.scatter(x, y, s=s, c=colors, alpha=0.7, edgecolor='k', linewidth=0.5, zorder=2)
    
    # 8.1) Add team logos inside bubbles (using the working logic from top20_off_eff.py)
    fig.canvas.draw()  # Draw figure to get correct bbox
    x_data_range = ax.get_xlim()[1] - ax.get_xlim()[0]
    y_data_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    bbox = ax.get_window_extent()
    
    for i, (xi, yi, team) in enumerate(zip(x, y, teams)):
        logo = get_team_logo(team)
        if logo is None:
            continue
            
        # Calculate bubble size in data coordinates
        bubble_radius = np.sqrt(s[i] / np.pi)  # Radius from area in points
        
        # Convert bubble radius to data coordinates
        data_to_pixel_ratio = bbox.height / y_data_range
        bubble_radius_data = bubble_radius / data_to_pixel_ratio
        
        # Get logo dimensions
        logo_width, logo_height = logo.size
        logo_aspect_ratio = logo_width / logo_height
        
        # Calculate target size based on bubble diameter (use 25% of bubble diameter, same as top20_off_eff)
        target_diameter_data = bubble_radius_data * 2 * 0.01
        
        # Determine which dimension (width or height) is the limiting factor
        if logo_aspect_ratio > 1:  # Logo is wider than tall
            # Width is the limiting factor
            target_width_data = target_diameter_data
            target_height_data = target_width_data / logo_aspect_ratio
        else:  # Logo is taller than wide (or square)
            # Height is the limiting factor
            target_height_data = target_diameter_data
            target_width_data = target_height_data * logo_aspect_ratio
        
        # Convert target size back to pixels and calculate zoom
        target_width_pixels = target_width_data * data_to_pixel_ratio * (bbox.width / x_data_range)
        zoom = target_width_pixels / logo_width
        
        img_box = OffsetImage(logo, zoom=zoom)
        
        ab = AnnotationBbox(
            img_box,
            (xi, yi),
            frameon=False,
            xycoords='data',
            pad=0
        )
        ax.add_artist(ab)

    # 9) professional text positioning using adjustText library
    texts = []
    
    # Pre-calculate bubble radii for reference
    bubble_radii_data = []
    fig.canvas.draw()
    bbox = ax.get_window_extent()
    y_data_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    
    for i in range(len(x)):
        bubble_area_pixels = s[i]
        bubble_radius_pixels = np.sqrt(bubble_area_pixels / np.pi)
        bubble_radius_data = bubble_radius_pixels / (bbox.height / y_data_range)
        bubble_radii_data.append(bubble_radius_data)
    
    # Helper function to darken light colors for better text readability
    def get_text_color(team_color):
        """Get appropriate text color - darken if too light"""
        if team_color is None:
            return 'black'
        
        # Calculate brightness (perceived luminance)
        r, g, b = team_color
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        
        # If color is too light (brightness > 0.6), darken it significantly
        if brightness > 0.6:
            # Darken by 70% for better readability
            return (r * 0.3, g * 0.3, b * 0.3)
        # If moderately light (brightness > 0.4), darken more
        elif brightness > 0.4:
            # Darken by 50%
            return (r * 0.5, g * 0.5, b * 0.5)
        else:
            # Color is dark enough, use as is
            return team_color
    
    # Create all text objects first (positioned below bubbles by default)
    for i, (xi, yi, formatted_name, team) in enumerate(zip(x, y, formatted_names, teams)):
        bubble_radius_data = bubble_radii_data[i]
        
        # Default position: below the bubble with more distance
        text_x = xi
        text_y = yi - bubble_radius_data - 0.025  # Increased distance from 0.01 to 0.025
        
        # Get team color from the color_map we already built
        team_color = color_map.get(team, (0, 0, 0))  # Default to black if not found
        text_color = get_text_color(team_color)
        
        # Create text object with team color
        text_obj = ax.text(text_x, text_y, formatted_name,
                          ha='center', va='top', 
                          fontsize=8, fontweight='bold',
                          color=text_color)
        texts.append(text_obj)
    
    # Use adjustText to automatically avoid overlaps with bubbles and other text
    adjust_text(
        texts,
        x=x, y=y,  # Bubble positions to avoid
        expand_points=(1.5, 1.5),  # How much to expand around bubbles
        expand_text=(1.2, 1.2),   # How much to expand around text
        expand_objects=(1.3, 1.3), # How much to expand around other objects
        arrowprops=dict(arrowstyle='->', color='gray', alpha=0.7, lw=0.8, shrinkA=5, shrinkB=5),
        force_points=(0.3, 0.3),  # Force to avoid bubbles
        force_text=(0.8, 0.8),    # Force to avoid other text
        force_objects=(0.5, 0.5), # Force to avoid other objects
        lim=1000,  # Maximum iterations
        precision=0.01,
        only_move={'points': 'y', 'text': 'xy', 'objects': 'xy'}  # Allow text to move in all directions
    )

    # 10) add margins to axes for more breathing room
    x_range = x.max() - x.min()
    y_range = y.max() - y.min()
    x_margin = x_range * 0.15  # 15% margin on each side
    y_margin = y_range * 0.15  # 15% margin on each side
    
    ax.set_xlim(x.min() - x_margin, x.max() + x_margin)
    ax.set_ylim(y.min() - y_margin, y.max() + y_margin)

    # 11) median lines
    ax.axvline(xm, color='gray', ls='--', lw=1)
    ax.axhline(ym, color='gray', ls='--', lw=1)
    
    # 11.0) Add labels for median lines
    # Get current axis limits after margins are set
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    
    # Label for vertical line (TS% median) - positioned near x-axis
    ax.text(xm, y_min + (y_max - y_min) * 0.02, 
            f'Mediana TS%\n{xm:.1f}%',
            fontsize=9, fontweight='bold',
            ha='center', va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='gray'),
            color='gray')
    
    # Label for horizontal line (eFG% median) - positioned on y-axis
    ax.text(x_min + (x_max - x_min) * 0.02, ym,
            f'Mediana eFG% {ym:.1f}%',
            fontsize=9, fontweight='bold',
            ha='left', va='center',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='gray'),
            color='gray')

    # 11.1) Add quadrant labels for interpretation
    # Calculate positions for quadrant labels (with some padding from edges)
    padding_x = (x_max - x_min) * 0.02
    padding_y = (y_max - y_min) * 0.02
    
    # Bottom-left quadrant (Low TS%, Low eFG%)
    ax.text(x_min + padding_x, y_min + padding_y, 
            'Ambos bajos →\nbaja eficiencia neta',
            fontsize=10, fontweight='bold', 
            ha='left', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral', alpha=0.7),
            color='darkred')
    
    # Bottom-right quadrant (High TS%, Low eFG%)
    ax.text(x_max - padding_x, y_min + padding_y,
            'TS% – eFG% positivo →\njuega vía FT',
            fontsize=10, fontweight='bold',
            ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7),
            color='darkorange')
    
    # Top-left quadrant (Low TS%, High eFG%)
    ax.text(x_min + padding_x, y_max - padding_y,
            'eFG% alto – TS% bajo →\nnumerosos TC, pocos FT',
            fontsize=10, fontweight='bold',
            ha='left', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7),
            color='darkblue')
    
    # Top-right quadrant (High TS%, High eFG%)
    ax.text(x_max - padding_x, y_max - padding_y,
            'Ambos altos →\nnivel alto de\nanotación por tiro',
            fontsize=10, fontweight='bold',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7),
            color='darkgreen')

    # 12) labels & title
    ax.set_xlabel('TS %', fontsize=14)
    ax.set_ylabel('EFG %', fontsize=14)
    # Main title and subtitle, both centered
    fig.suptitle(
        'TOP SHOOTERS - Eficiencia de Tiro',
        fontsize=20,
        weight='bold',
        x=0.5,      # center horizontally
        y=1.03      # a little higher
    )
    fig.text(
        0.5,        # center horizontally
        0.99,       # just below the suptitle
        f'Mínimo {MIN_SHOTS} tiros intentados (T2 + T3)',
        ha='center',
        va='top',
        fontsize=12,
        weight='bold'
    )

    plt.tight_layout()
    return fig



if __name__ == '__main__':
    # Ejemplo de uso:
    FILE = './data/jugadores_aggregated_24_25.xlsx'
    MIS_EQUIPOS = ['BALONCESTO TALAVERA', 'C.B. TRES CANTOS', 'CB ARIDANE',
                   'CB LA MATANZA', 'EB FELIPE ANTÓN', 'LUJISA GUADALAJARA BASKET',
                   'REAL CANOE N.C.', 'UROS DE RIVAS', 'ZENTRO BASKET MADRID'
    ]

    FASE = "Liga Regular \"B-A\""
    df = pd.read_excel(FILE)
    
    print(f"Los equipos en el dataset son: {df['EQUIPO'].unique()}")

    board = plot_top_shooters(df, teams=MIS_EQUIPOS,  MIN_SHOTS=150, phase=None)
    # save the figure
    board.savefig('top_150_shots.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format
    
    board = plot_top_shooters(df, teams=MIS_EQUIPOS,  MIN_SHOTS=200, phase=None)
    # save the figure
    board.savefig('top_200_shots.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format
