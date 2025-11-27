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

def plot_offensive_efficiency(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None,
    min_games: int = 5,
    min_minutes: int = 50
):
    """
    TOP-20 Offensive Efficiency: scatter PPP vs Plays, bubble size ~ minutes,
    color = team's main logo color, median reference lines.
    Filters: PJ>min_games, MINUTOS JUGADOS>min_minutes (configurable).
    """
    # 0) load + Montserrat
    setup_montserrat_font()

    # 1) optional filters
    df = apply_phase_filter(df, phase)
    df = apply_teams_filter(df, teams)

    # 2) apply configurable PJ and minutes filters
    df = apply_basic_filters(df, min_games=min_games, min_minutes_avg=10, min_total_minutes=min_minutes)

    # 3) compute plays and PPP
    df['PLAYS'] = compute_plays(df)
    df['PPP'] = compute_ppp(df)
    
    # Quiero que aqui para debugger imprimas el PPP del jugador que en al apellido tenga "RUEDA"
    for index, row in df.iterrows():
        if "RUEDA" in row['JUGADOR'].upper():
            print(f"DEBUG: Jugador con 'RUEDA' encontrado: {row['JUGADOR']} - PPP: {row['PPP']}")
    
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
        

    # 6) guard against empty arrays: create an informative placeholder figure
    if x.size == 0 or y.size == 0:
        fig, ax = plt.subplots(figsize=(13, 11))
        ax.text(
            0.5, 0.5,
            'No hay suficientes datos para mostrar el TOP20\nRevisa filtros o archivos seleccionados',
            ha='center', va='center', fontsize=16, weight='bold'
        )
        ax.axis('off')
        return fig

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
    
    # 8.1) Add team logos inside bubbles with fixed maximum size
    from PIL import Image as PILImage
    
    fig.canvas.draw()  # Draw figure to get correct bbox
    x_data_range = ax.get_xlim()[1] - ax.get_xlim()[0]
    y_data_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    bbox = ax.get_window_extent()
    
    for i, (xi, yi, team) in enumerate(zip(x, y, teams)):
        logo = get_team_logo(team)
        if logo is None:
            continue
            
        # Calculate target size: percentage of bubble radius
        bubble_area = s[i]  # Area in points^2
        bubble_radius_points = np.sqrt(bubble_area / np.pi)  # Radius in points
        logo_radius_points = bubble_radius_points * 0.4  # 40% of bubble radius
        target_size_points = logo_radius_points * 2  # Diameter in points
        
        # Convert to pixels (assuming 72 DPI for points-to-pixels)
        target_size_px = int(target_size_points)
        
        # Apply maximum size constraint
        max_logo_size_px = 60  # Maximum logo size in pixels
        target_size_px = min(target_size_px, max_logo_size_px)
        
        # Resize logo to fixed size maintaining aspect ratio
        logo_width, logo_height = logo.size
        aspect_ratio = logo_width / logo_height
        
        if aspect_ratio > 1:
            # Wider than tall
            new_width = target_size_px
            new_height = int(target_size_px / aspect_ratio)
        else:
            # Taller than wide
            new_height = target_size_px
            new_width = int(target_size_px * aspect_ratio)
        
        # Resize the logo
        logo_resized = logo.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
        
        img_box = OffsetImage(logo_resized, zoom=1.0)  # zoom=1 since we already resized
        
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
        
        # Default position: below the bubble with very minimal distance
        text_x = xi
        text_y = yi - bubble_radius_data - 0.001  # Almost touching the bubble
        
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
        expand_points=(1.05, 1.05),  # Minimal expansion around bubbles for very close positioning
        expand_text=(1.05, 1.05),   # Minimal expansion around text
        expand_objects=(1.05, 1.05), # Minimal expansion around other objects
        arrowprops=dict(arrowstyle='->', color='gray', alpha=0.7, lw=0.8, shrinkA=5, shrinkB=5),
        force_points=(0.1, 0.1),  # Very low force to allow extremely close positioning to bubbles
        force_text=(0.4, 0.4),    # Reduced force between texts
        force_objects=(0.2, 0.2), # Very low force for other objects
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
    
    # Label for vertical line (Plays median) - positioned near x-axis
    ax.text(xm, y_min + (y_max - y_min) * 0.02, 
            f'Mediana Plays\n{xm:.1f}',
            fontsize=9, fontweight='bold',
            ha='center', va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='gray'),
            color='gray')
    
    # Label for horizontal line (PPP median) - positioned on y-axis
    ax.text(x_min + (x_max - x_min) * 0.02, ym,
            f'Mediana PPP {ym:.2f}',
            fontsize=9, fontweight='bold',
            ha='left', va='center',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='gray'),
            color='gray')

    # 11.1) Add quadrant labels for interpretation
    # Calculate positions for quadrant labels (with some padding from edges)
    padding_x = (x_max - x_min) * 0.02
    padding_y = (y_max - y_min) * 0.02
    
    # Bottom-left quadrant (Low Plays, Low PPP)
    ax.text(x_min + padding_x, y_min + padding_y, 
            'Poco volumen y\nbaja eficiencia;\nimpacto mínimo\nen el juego',
            fontsize=10, fontweight='bold', 
            ha='left', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral', alpha=0.7),
            color='darkred')
    
    # Bottom-right quadrant (High Plays, Low PPP)
    ax.text(x_max - padding_x, y_min + padding_y,
            'Mucho volumen con\nbaja eficiencia;\no termina de rendir',
            fontsize=10, fontweight='bold',
            ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7),
            color='darkorange')
    
    # Top-left quadrant (Low Plays, High PPP)
    ax.text(x_min + padding_x, y_max - padding_y,
            'Muy eficiente,\npero poco usado;\noportunidad de\naumentar su\nprotagonismo',
            fontsize=10, fontweight='bold',
            ha='left', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7),
            color='darkblue')
    
    # Top-right quadrant (High Plays, High PPP)
    ax.text(x_max - padding_x, y_max - padding_y,
            'Alta eficiencia\ny mucho volumen;\nel motor ofensivo\ndel equipo',
            fontsize=10, fontweight='bold',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7),
            color='darkgreen')

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
    FILE = './data/jugadores_aggregated_24_25.xlsx'
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
