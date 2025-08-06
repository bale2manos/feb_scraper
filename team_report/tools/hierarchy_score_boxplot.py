import os
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

from .utils import (
    format_player_name,
    lighten_color,
    darken_color,
    is_dark_color,
    get_team_main_color,
    get_team_logo,
    setup_montserrat_font,
    apply_phase_filter,
    apply_teams_filter
)

def plot_annotation_hierarchy(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    # Configure Montserrat font
    setup_montserrat_font()
    
    # 1) Filtrado opcional
    df = apply_phase_filter(df, phase)
    df = apply_teams_filter(df, teams)
        
    
    # 2) Agrupar puntos por equipo en orden alfabético
    df = df[['EQUIPO', 'JUGADOR', 'PUNTOS', 'DORSAL']].dropna()
    teams_sorted = sorted(df['EQUIPO'].unique())
    data = [df.loc[df['EQUIPO'] == t, 'PUNTOS'].values for t in teams_sorted]
    n = len(teams_sorted)
    
    # 3) Cálculo de estadísticas y rango para desplazamientos
    all_points = df['PUNTOS']
    span = all_points.max() - all_points.min()
    dy = span * 0.04

    # 4) Crear figura
    fig, ax = plt.subplots(figsize=(15, 8))
    x = np.arange(n)
    
    # 5) Boxplot sin outliers
    bp = ax.boxplot(
        data,
        positions=x,
        widths=0.65,
        patch_artist=True,
        showfliers=False,
        boxprops=dict(facecolor='none', edgecolor='none', linewidth=0),  # Hide original boxes
        whiskerprops=dict(color='grey', linewidth=1),
        capprops=dict(color='none', linewidth=0),  # Hide original caps, we'll draw custom ones
        medianprops=dict(color='black', linewidth=0)  # Hide median line
    )
    
    # 5.1) Custom colored box sections with team colors
    for i, team in enumerate(teams_sorted):
        team_data = data[i]
        q1 = np.percentile(team_data, 25)
        median = np.percentile(team_data, 50)
        q3 = np.percentile(team_data, 75)
        
        # Calculate whisker ends (not outliers)
        iqr = q3 - q1
        lower_whisker = max(team_data.min(), q1 - 1.5 * iqr)
        upper_whisker = min(team_data.max(), q3 + 1.5 * iqr)
        
        # Find actual whisker ends from data
        lower_whisker = team_data[team_data >= lower_whisker].min()
        upper_whisker = team_data[team_data <= upper_whisker].max()
        
        # Get team colors - two different levels of lightening
        main_color = get_team_main_color(team)
        less_light_color = lighten_color(main_color, 0.4)  # Q1 to median (less light)
        more_light_color = lighten_color(main_color, 0.7)  # Median to Q3 (more light)
        
        # Less light section: Q1 to median
        less_light_patch = plt.Rectangle(
            (x[i] - 0.325, q1), 0.65, median - q1,
            facecolor=less_light_color,
        )
        ax.add_patch(less_light_patch)
        
        # More light section: median to Q3
        more_light_patch = plt.Rectangle(
            (x[i] - 0.325, median), 0.65, q3 - median,
            facecolor=more_light_color,
        )
        ax.add_patch(more_light_patch)
        
        # Add horizontal lines for statistical values
        line_x_start = x[i] - 0.325
        line_x_end = x[i] + 0.325
        
        # Q1 line (perpendicular to whisker)
        ax.plot([line_x_start, line_x_end], [q1, q1], 
                color='black', linewidth=1, solid_capstyle='butt')
        
        # Q3 line (perpendicular to whisker)
        ax.plot([line_x_start, line_x_end], [q3, q3], 
                color='black', linewidth=1, solid_capstyle='butt')
        
        # Custom caps - full bar width for whisker ends (not outliers)
        ax.plot([line_x_start, line_x_end], [lower_whisker, lower_whisker], 
                color='black', linewidth=1, solid_capstyle='butt')
        
        ax.plot([line_x_start, line_x_end], [upper_whisker, upper_whisker], 
                color='black', linewidth=1, solid_capstyle='butt')
    
    # 6) Todos los puntos individuales with smart color logic
    for i, pts in enumerate(data):
        main_color = get_team_main_color(teams_sorted[i])
        # Use black dots unless the main color is dark, then use the main color
        dot_color = main_color if is_dark_color(main_color) else '#000000'
        
        ax.scatter(
            np.full_like(pts, i),
            pts,
            color=dot_color,
            s=20,
            alpha=0.8,
            zorder=5
        )
    
    # 7) Intelligent player annotation system
    for i, team in enumerate(teams_sorted):
        series = df.loc[df['EQUIPO'] == team, ['JUGADOR','PUNTOS','DORSAL']].sort_values('PUNTOS')
        pts = series['PUNTOS'].values
        n_players = len(pts)
        
        # Select key players using improved heuristic
        selected_players = []
        
        if n_players >= 8:
            # For larger teams, select more distributed players
            indices = [
                0,  # Lowest scorer
                n_players // 4,  # ~25th percentile
                n_players // 2,  # Median
                3 * n_players // 4,  # ~75th percentile
                n_players - 1,  # Highest scorer
            ]
            # Add a couple more for better distribution
            if n_players >= 12:
                indices.extend([
                    n_players // 8,  # ~12th percentile
                    7 * n_players // 8,  # ~87th percentile
                ])
        elif n_players >= 5:
            # For medium teams
            indices = [
                0,  # Lowest
                n_players // 3,  # ~33rd percentile
                2 * n_players // 3,  # ~66th percentile
                n_players - 1,  # Highest
            ]
        else:
            # For small teams, show all or most
            indices = list(range(n_players))
        
        # Remove duplicates and sort
        indices = sorted(list(set(indices)))
        
        # Get selected players data
        for idx in indices:
            player_idx = series.iloc[idx].name
            jugador = series.loc[player_idx, 'JUGADOR']
            dorsal = series.loc[player_idx, 'DORSAL']
            puntos = series.loc[player_idx, 'PUNTOS']
            
            selected_players.append({
                'name': format_player_name(jugador, int(dorsal)),
                'points': puntos,
                'original_idx': idx
            })
        
        # Sort by points for overlap resolution
        selected_players.sort(key=lambda x: x['points'])
        
        # Filter out overlapping players (keep only the highest scoring ones)
        min_spacing = span * 0.05  # Minimum spacing between annotations
        final_players = []
        
        for player in reversed(selected_players):  # Start with highest scorer
            # Check if this player overlaps with any already selected
            overlaps = any(abs(player['points'] - existing['points']) < min_spacing 
                          for existing in final_players)
            
            if not overlaps:
                final_players.append(player)
        
        # Sort final players by points for annotation
        final_players.sort(key=lambda x: x['points'])
        
        # Simply annotate each selected player directly above their point
        for player in final_players:
            y = player['points']
            text_y = y + dy * 0.2  # Closer to the dot
            
            ax.annotate(
                player['name'],
                xy=(i, y),
                xytext=(i, text_y),
                ha='center',
                va='bottom',
                fontsize=7,
                fontweight='bold',
                color='black',  # Always use black for player names
                zorder=10  # Higher z-index than dots to appear on top
            )
    
    # 8) Add team logos above the highest scoring player for each team
    fig.canvas.draw()  # Draw figure to get correct bbox
    x0, x1 = ax.get_xlim()
    bbox = ax.get_window_extent()
    pix_per_data_x = bbox.width / (x1 - x0)
    
    for i, team in enumerate(teams_sorted):
        logo = get_team_logo(team)
        if logo is None:
            continue
            
        # Find the highest scoring player for this team
        team_data = data[i]
        max_points = team_data.max()
        
        # Logo sizing (similar to net_rtg_chart)
        disp_w_px = 0.5 * pix_per_data_x  # Fixed width in pixels (increased from 0.3)
        orig_w_px = logo.width
        zoom = disp_w_px / orig_w_px
        
        # Create the OffsetImage
        img_box = OffsetImage(logo, zoom=zoom)
        
        # Position above the highest point with some spacing
        logo_y = max_points + span * 0.25  # 25% of total span above highest point
        
        ab = AnnotationBbox(
            img_box,
            (i, logo_y),
            frameon=False,
            xycoords='data',
            pad=0
        )
        ax.add_artist(ab)

    # 9) Adjust y-limits to accommodate logos
    current_ylim = ax.get_ylim()
    logo_space = span * 0.35  # Extra space for logos
    ax.set_ylim(current_ylim[0], current_ylim[1] + logo_space)

    # 10) Personalizar ejes y título
    ax.set_xticks([])  # Remove x-axis labels
    ax.set_ylabel('Puntos', fontsize=14)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1)
    ax.spines['bottom'].set_linewidth(1)
    ax.tick_params(left=True, bottom=False)
    
    ax.set_title(
        'Jerarquía de anotación',
        fontsize=40,
        weight='bold',
        pad=20
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

    board = plot_annotation_hierarchy(df, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('hierarchy_score_boxplot.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format
