import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from .utils import get_team_logo, setup_montserrat_font

def draw_ppp_quadrant(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Dibuja PPP (eje X) vs PPP OPP (eje Y).
    Por cada equipo:
      - carga su logo y lo coloca en (PPP, PPP OPP)
      - encima escribe el PPP en verde
      - debajo escribe el PPP OPP en rojo
    Añade líneas de media y etiquetas en las 4 esquinas.
    """
    # Configure Montserrat font
    setup_montserrat_font()
    
    # 1) Filtrado opcional
    if phase is not None:
        df = df[df['FASE'].isin(phase)]
    if teams is not None and len(teams) > 0:
        df = df[df['EQUIPO'].isin(teams)]

    # 2) Agregamos PPP y PPP OPP por equipo (promedio)
    agg = df.groupby('EQUIPO')[['PPP', 'PPP OPP']].mean()

    # 3) Medias
    mean_ppp     = agg['PPP'].mean()
    mean_ppp_opp = agg['PPP OPP'].mean()


    # 4) Lienzo y medias - BIGGER CANVAS
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    
    # ── NEW: Equal scale and range for both axes ───────────────
    x_min, x_max = agg['PPP'].min(),     agg['PPP'].max()
    y_min, y_max = agg['PPP OPP'].min(), agg['PPP OPP'].max()
    
    # Find the overall range to make both axes equal
    overall_min = min(x_min, y_min)
    overall_max = max(x_max, y_max)
    
    # Add padding
    range_size = overall_max - overall_min
    padding = range_size * 0.15  # Increased padding for better separation
    
    # Set equal limits for both axes
    ax.set_xlim(overall_min - padding, overall_max + padding)
    ax.set_ylim(overall_min - padding, overall_max + padding)
    ax.invert_yaxis()   # como en tu ejemplo, PPP OPP más bajo arriba
    
    # Add average lines with labels (after setting limits)
    ax.axvline(mean_ppp,     linestyle='--', color='gray', alpha=0.7)
    ax.axhline(mean_ppp_opp, linestyle='--', color='gray', alpha=0.7)
    
    # Add labels for the average lines
    x_lim_min, x_lim_max = ax.get_xlim()
    y_lim_min, y_lim_max = ax.get_ylim()
    
    # Vertical line label INSIDE the graph, above X-axis
    ax.text(mean_ppp, y_lim_min + (y_lim_max - y_lim_min) * 0.05, f'Promedio PPP: {mean_ppp:.2f}', 
            rotation=0, ha='center', va='bottom', fontsize=10, fontweight='bold',
            backgroundcolor='white', alpha=0.8)
    # Horizontal line label at left extreme
    ax.text(x_lim_min + 0.01, mean_ppp_opp, f'Promedio PPP OPP: {mean_ppp_opp:.2f}', 
            ha='left', va='center', fontsize=10, fontweight='bold',
            backgroundcolor='white', alpha=0.8)
    # ──────────────────────────────────────────────────

    # 5) Dibujar cada logo y sus textos
    # Much bigger logos and larger text with more separation
    logo_h = 0.08 * (overall_max - overall_min)  # Much bigger logos (increased from 0.03)
    text_offset = 0.025 * (overall_max - overall_min)  # Much more separation from logos

    for team, row in agg.iterrows():
        x, y = row['PPP'], row['PPP OPP']
        logo = get_team_logo(team)
        if logo is not None:
            ow, oh = logo.size
            ar = ow / oh
            logo_w = logo_h * ar
            arr = np.array(logo)
            ax.imshow(
                arr,
                extent=[x-logo_w/2, x+logo_w/2,
                        y-logo_h/2, y+logo_h/2],
                aspect='equal',
                interpolation='bilinear',  # Better quality
                origin='lower'  # Correct origin for matplotlib
            )

        ax.text( x, y + logo_h/2 + text_offset, f"{x:.2f}",
                 color='green', ha='center', va='bottom',
                 fontsize=12, fontweight='bold')  # Increased font size
        ax.text( x, y - logo_h/2 - text_offset, f"{y:.2f}",
                 color='red',   ha='center', va='top',
                 fontsize=12, fontweight='bold')  # Increased font size


    # 6) Etiquetas en las 4 esquinas - IMPROVED STYLING
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    pad_x = (x_max - x_min) * 0.02
    pad_y = (y_max - y_min) * 0.02
    
    tag_font_size = 10

    # Top-left: Poor offense, Good defense (Mixed - Light Blue)
    ax.text(
        x_min + pad_x, y_max - pad_y,
        "Mejor defensa\n– Peor ataque",
        va='top', ha='left',
        fontsize=tag_font_size,
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', alpha=0.8, edgecolor='darkblue'),
        color='darkblue'
    )
    
    # Top-right: Good offense, Good defense (Excellent - Light Green)
    ax.text(
        x_max - pad_x, y_max - pad_y,
        "Mejor defensa\n– Mejor ataque",
        va='top', ha='right',
        fontsize=tag_font_size, 
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightgreen', alpha=0.8, edgecolor='darkgreen'),
        color='darkgreen'
    )
    
    # Bottom-left: Poor offense, Poor defense (Bad - Light Red)
    ax.text(
        x_min + pad_x, y_min + pad_y,
        "Peor defensa\n– Peor ataque",
        va='bottom', ha='left',
        fontsize=tag_font_size, 
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightcoral', alpha=0.8, edgecolor='darkred'),
        color='darkred'
    )
    
    # Bottom-right: Good offense, Poor defense (Mixed - Light Yellow)
    ax.text(
        x_max - pad_x, y_min + pad_y,
        "Peor defensa\n– Mejor ataque",
        va='bottom', ha='right',
        fontsize=tag_font_size, 
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.8, edgecolor='darkorange'),
        color='darkorange'
    )

    # 7) Etiquetas de ejes
    ax.set_xlabel('PPP',     fontsize=12, fontweight='bold')
    ax.set_ylabel('PPP OPP', fontsize=12, fontweight='bold')

    plt.tight_layout()
    return fig


if __name__ == '__main__':
    # Ejemplo de uso:
    FILE = './data/teams_aggregated.xlsx'
    MIS_EQUIPOS = ['BALONCESTO TALAVERA', 'C.B. TRES CANTOS', 'CB ARIDANE',
                   'CB LA MATANZA', 'EB FELIPE ANTÓN', 'LUJISA GUADALAJARA BASKET',
                   'REAL CANOE N.C.', 'UROS DE RIVAS', 'ZENTRO BASKET MADRID'
    ]

    FASE = "Liga Regular \"B-A\""
    df = pd.read_excel(FILE)
    
    print(f"Los equipos en el dataset son: {df['EQUIPO'].unique()}")

    board = draw_ppp_quadrant(df, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('ppp_quadrant.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format

