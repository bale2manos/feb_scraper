import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

from utils import (
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

def plot_offensive_efficiency(
    df: pd.DataFrame,
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

    # 2) apply PJ and minutes filters
    df = apply_basic_filters(df, min_games=5, min_minutes_avg=10, min_total_minutes=150)

    # 3) compute plays and PPP
    df['PLAYS'] = compute_plays(df)
    df['PPP'] = compute_ppp(df)
    
    # 3) take top-20 by PPP
    df = df.nlargest(20, 'PPP').reset_index(drop=True)

    # 4) prepare data arrays
    x = df['PLAYS'].to_numpy()
    y = df['PPP'].to_numpy()
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
        

    # 6) bubble size based on PPP (70%) and plays volume (30%)
    # Higher PPP = bigger bubbles (70% weight), more plays = bigger bubbles (30% weight)
    ppp_factor = (y / y.max()) ** 4.0  # Very strong PPP influence for dramatic differences (70% weight)
    plays_factor = (x / x.max()) ** 0.5  # Moderate plays influence (30% weight)
    s = (0.7 * ppp_factor + 0.3 * plays_factor) * 1500  # Slightly larger max size for bigger top bubbles

    # 7) compute medians
    xm, ym = np.median(x), np.median(y)

    # 8) plot with team-colored circles as bubble backgrounds
    fig, ax = plt.subplots(figsize=(13,11))
    # Draw circles with original team colors (no lightening)
    ax.scatter(x, y, s=s, c=colors, alpha=0.7, edgecolor='k', linewidth=0.5, zorder=2)
    
    # 8.1) Add team logos inside bubbles
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
        
        # Calculate target size based on bubble diameter (use 70% of bubble diameter for padding)
        target_diameter_data = bubble_radius_data * 2 * 0.25
        
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

    # 9) simple text positioning - all text below bubbles
    placed_texts = []
    
    for i, (xi, yi, formatted_name) in enumerate(zip(x, y, formatted_names)):
        # Calculate bubble radius in data coordinates more accurately
        bubble_area_pixels = s[i]  # Area in points^2
        bubble_radius_pixels = np.sqrt(bubble_area_pixels / np.pi)
        
        # Convert to data coordinates
        fig.canvas.draw()
        bbox = ax.get_window_extent()
        y_data_range = ax.get_ylim()[1] - ax.get_ylim()[0]
        bubble_radius_data = bubble_radius_pixels / (bbox.height / y_data_range)
        
        # Always place below - simple and clean
        text_x = xi  
        text_y = yi - bubble_radius_data - 0.002
        va = 'top'
        
        # Add text
        ax.text(text_x, text_y, formatted_name,
                ha='center', va=va, 
                fontsize=8, fontweight='bold')
        
        placed_texts.append((text_x, text_y, formatted_name))

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

    # 12) labels & title
    ax.set_xlabel('Plays', fontsize=14)
    ax.set_ylabel('PPP', fontsize=14)
    # 11) Main title and subtitle, both centered
    fig.suptitle(
        'TOP 20 - Eficiencia Ofensiva',
        fontsize=20,
        weight='bold',
        x=0.5,      # center horizontally
        y=1.03      # a little higher
    )
    fig.text(
        0.5,        # center horizontally
        0.99,       # just below the suptitle
        'Mínimo 5 partidos jugados y 10 minutos de media',
        ha='center',
        va='top',
        fontsize=12,
        weight='bold'
    )

    plt.tight_layout()
    return fig



if __name__ == '__main__':
    # Ejemplo de uso:
    FILE = './data/jugadores_aggregated.xlsx'
    MIS_EQUIPOS = ['BALONCESTO TALAVERA', 'C.B. TRES CANTOS', 'CB ARIDANE',
                   'CB LA MATANZA', 'EB FELIPE ANTÓN', 'LUJISA GUADALAJARA BASKET',
                   'REAL CANOE N.C.', 'UROS DE RIVAS', 'ZENTRO BASKET MADRID'
    ]

    FASE = "Liga Regular \"B-A\""
    df = pd.read_excel(FILE)
    
    print(f"Los equipos en el dataset son: {df['EQUIPO'].unique()}")

    board = plot_offensive_efficiency(df, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('top20_offensive_efficiency.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format
