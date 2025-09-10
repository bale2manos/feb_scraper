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
    format_player_name,
    compute_advanced_stats
)

def plot_top_ppp(
    df: pd.DataFrame,
):
    """
    TOP-20 Offensive Efficiency: scatter PPP vs Plays, bubble size ~ minutes,
    color = team's main logo color, median reference lines.
    Filters: PJ>2, MINUTOS JUGADOS>10.
    """
    # 0) load + Montserrat
    setup_montserrat_font()
    
    # Filter out those with less than 1 TCC
    df = df[df['TCC'] >0].reset_index(drop=True)
    
    # 4) prepare data arrays
    x = df['Plays'].to_numpy()
    y = df['PPP'].to_numpy()
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
        

    # 6) bubble size based on TCC (Total Converted shots)
    # Get TCC values - total field goals made
    tcc_values = df['Avg. MIN']  # Assuming TCC is already computed in df

    # Scale bubble sizes based on TCC with minimum size for visibility
    min_size = 200  # Minimum bubble size
    max_size = 1500  # Maximum bubble size
    
    # Normalize TCC values to bubble sizes
    if tcc_values.max() > tcc_values.min():
        tcc_normalized = (tcc_values - tcc_values.min()) / (tcc_values.max() - tcc_values.min())
        s = min_size + (max_size - min_size) * tcc_normalized
    else:
        s = np.full(len(tcc_values), (min_size + max_size) / 2)  # All same size if all TCC equal

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
        
        # Convert bubble radius directly to pixels using DPI
        bubble_radius_pixels = bubble_radius
        
        # Get logo dimensions
        logo_width, logo_height = logo.size
        logo_aspect_ratio = logo_width / logo_height
        
        # Calculate target logo size as percentage of bubble diameter in pixels
        # Use 40% of bubble diameter for good visibility without overflow
        target_diameter_pixels = bubble_radius_pixels * 2 * 0.6
        
        # Determine which dimension (width or height) is the limiting factor
        if logo_aspect_ratio > 1:  # Logo is wider than tall
            # Width is the limiting factor
            target_width_pixels = target_diameter_pixels
            target_height_pixels = target_width_pixels / logo_aspect_ratio
        else:  # Logo is taller than wide (or square)
            # Height is the limiting factor
            target_height_pixels = target_diameter_pixels
            target_width_pixels = target_height_pixels * logo_aspect_ratio
        
        # Calculate zoom directly from pixel dimensions
        zoom = target_width_pixels / logo_width
        
        # Calculate zoom directly from pixel dimensions
        zoom = target_width_pixels / logo_width
        
        # Add safety constraint to prevent extremely large logos
        max_zoom = 2.0  # Maximum zoom factor
        zoom = min(zoom, max_zoom)
        
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
        
        avg_min = df['Avg. MIN'].iloc[i]
        
        # Create formatted text with TCC count in green
        player_text = f"{formatted_name} - {avg_min:.1f} MIN"
        
        # Default position: casi tocando la burbuja
        text_x = xi
        text_y = yi - bubble_radius_data - 0.003  # Extremadamente cerca: casi tocando
        
        # Get team color from the color_map we already built
        team_color = color_map.get(team, (0, 0, 0))  # Default to black if not found
        text_color = get_text_color(team_color)
        
        # Create text object with team color for player name and green for TCC
        text_obj = ax.text(text_x, text_y, player_text,
                          ha='center', va='top', 
                          fontsize=8, fontweight='bold',
                          color=text_color)
        texts.append(text_obj)
    
    # Use adjustText to automatically avoid overlaps with bubbles and other text
    adjust_text(
        texts,
        x=x, y=y,  # Bubble positions to avoid
        expand_points=(1.02, 1.02),  # Extremadamente reducido: casi sin expansión
        expand_text=(1.02, 1.02),   # Extremadamente reducido: casi sin expansión
        expand_objects=(1.02, 1.02), # Extremadamente reducido: casi sin expansión
        arrowprops=dict(arrowstyle='->', color='gray', alpha=0.4, lw=0.4, shrinkA=1, shrinkB=1),
        force_points=(0.05, 0.05),  # Extremadamente reducido: casi sin fuerza
        force_text=(0.2, 0.2),    # Muy reducido: mínima fuerza para evitar otro texto
        force_objects=(0.1, 0.1), # Extremadamente reducido: casi sin fuerza
        lim=150,  # Muy pocas iteraciones para mantener posiciones iniciales
        precision=0.05,  # Muy poca precisión para permitir posiciones súper cercanas
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
            f'Mediana PPP {ym:.1f}',
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
            'Poco relevante →\nbajo impacto e\nineficiente',
            fontsize=10, fontweight='bold', 
            ha='left', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral', alpha=0.7),
            color='darkred')
    
    # Bottom-right quadrant (High Plays, Low PPP)
    ax.text(x_max - padding_x, y_min + padding_y,
            'Alto volumen →\nmucho juego pero\nineficiente',
            fontsize=10, fontweight='bold',
            ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7),
            color='darkorange')
    
    # Top-left quadrant (Low Plays, High PPP)
    ax.text(x_min + padding_x, y_max - padding_y,
            'Rol específico →\npocas posesiones\npero eficiente',
            fontsize=10, fontweight='bold',
            ha='left', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7),
            color='darkblue')
    
    # Top-right quadrant (High Plays, High PPP)
    ax.text(x_max - padding_x, y_max - padding_y,
            'Estrella →\nabsorbe mucho juego\ny es eficiente',
            fontsize=10, fontweight='bold',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7),
            color='darkgreen')

    # 12) labels & title
    ax.set_xlabel('Plays', fontsize=14)
    ax.set_ylabel('PPP', fontsize=14)
    # Main title and subtitle, both centered
    fig.suptitle(
        'PPP (Puntos por play)',
        fontsize=20,
        weight='bold',
        x=0.5,      # center horizontally
        y=0.99      # a little higher
    )

    plt.tight_layout()
    return fig



if __name__ == "__main__":
    PATH = './data/jugadores_aggregated_24_25.xlsx'
    df_demo = pd.read_excel(PATH)
    # Filtramos solo un equipo...
    df_demo = df_demo[df_demo['EQUIPO'] == 'UROS DE RIVAS']
    
    stats_dicts = df_demo.apply(compute_advanced_stats, axis=1)
    stats_df = pd.DataFrame(stats_dicts.tolist())
    
    # añadimos la columna 'EQUIPO' para el logo
    stats_df['EQUIPO'] = df_demo['EQUIPO'].values

    fig = plot_top_ppp(stats_df)
    fig.savefig("top_ppp.png", dpi=300)
