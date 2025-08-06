import os
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image

from .utils import get_team_logo, setup_montserrat_font

def generate_team_rebound_analysis(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Gráfica de Análisis del Rebote (%) por equipo:
    Para cada equipo, tres barras horizontales (una por %OREB, %REB, %DREB),
    ejes de 0 a 1, con nombres y logos a la izquierda.
    """
    # Montserrat
    setup_montserrat_font()

    # Filtrar
    if phase is not None:
        df = df[df['FASE'].isin(phase)]
    if teams is not None and len(teams) > 0:
        df = df[df['EQUIPO'].isin(teams)]

    # Agregar medias por equipo
    stats = df.groupby('EQUIPO')[['%OREB','%REB','%DREB']].mean()
    stats = stats.sort_values('EQUIPO', ascending=True)

    # Wrapped team names
    max_chars = 18
    wrapped = {
        team: '\n'.join(textwrap.wrap(team, max_chars))
        for team in stats.index
    }

    # Colors & legend labels
    metrics = ['%DREB','%REB','%OREB']
    colors  = ['#3498DB','#E74C3C','#F39C12']  # naranja, rojo, azul
    labels  = ['Rebote Ofensivo %','Rebotes Totales %','Rebote Defensivo %']

    n = len(stats)
    fig = plt.figure(figsize=(16, n*1.2))
    gs = fig.add_gridspec(1,3, width_ratios=[1.0,0.6,4], wspace=0.02)

    ax_text = fig.add_subplot(gs[0]); ax_text.axis('off')
    ax_logo = fig.add_subplot(gs[1]); ax_logo.axis('off')
    ax_bar  = fig.add_subplot(gs[2]); ax_bar.axis('off')

    # Shared y-scale [0..n-1]
    ax_text.set_ylim(-0.5, n-0.5)
    ax_logo.set_ylim(-0.5, n-0.5)
    ax_bar.set_ylim(-0.5, n-0.5)
    # x-range fixed 0..1
    ax_bar.set_xlim(0,1)

    # Add vertical grid lines at every 10%
    for x in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        ax_bar.axvline(x, color='lightgray', linestyle='--', alpha=0.5, linewidth=1)

    # Title + legend
    fig.suptitle('Análisis del Rebote (%)', fontsize=32, weight='bold', y=0.96)
    patches = [Patch(color=c,label=l) for c,l in zip(colors,labels)]
    ax_bar.legend(handles=patches,
                  loc='upper center',
                  bbox_to_anchor=(0.5,1.05),
                  ncol=3, frameon=False, fontsize=14)

    # Bar settings
    bar_height = 0.3  # Increased from 0.25 to make bars a little bit thicker
    offsets = [ bar_height, 0, -bar_height ]  # three rows per team

    # Plot each team
    for i,(team,row) in enumerate(stats.iterrows()):
        y_center = n-1-i

        # 1) Team name
        ax_text.text(0.01, y_center, wrapped[team],
                     va='center', ha='left', fontsize=15)

        # 2) Logo
        logo = get_team_logo(team)
        if logo is not None:
            ar = logo.width/logo.height
            h = 0.8  # height in data units
            w = h*ar
            pix_h = int(h*fig.dpi)
            pix_w = int(w*fig.dpi)
            logo_small = logo.resize((pix_w,pix_h), Image.Resampling.LANCZOS)
            logo_arr = np.array(logo_small)
            y0 = y_center - h/2
            y1 = y_center + h/2
            x0 = 0.5-w/2
            x1 = 0.5+w/2
            ax_logo.imshow(logo_arr, extent=[x0,x1,y0,y1], aspect='equal')

        # 3) Three bars
        for off, m, c in zip(offsets, metrics, colors):
            y = y_center + off
            val = row[m]
            ax_bar.barh(y, val, height=bar_height*0.95, color=c, edgecolor='white')  # Increased from 0.9 to 0.95
            # Move text inside the bar, positioned at 50% of bar width
            ax_bar.text(val/2, y, f"{row[m]*100:.2f}%",
                        va='center', ha='center', color='white', fontsize=14, weight='bold')  # Changed to white, centered, bold

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

    board = generate_team_rebound_analysis(df, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('rebound_analysis.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format

