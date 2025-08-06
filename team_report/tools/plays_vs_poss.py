import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib import font_manager as fm
from PIL import Image
from .utils import get_team_logo, setup_montserrat_font

def plot_plays_vs_poss(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Plot two lines: mean PLAYS and mean POSS per team.
    X‐axis: one column per team in provided order.
    Annotates each marker with its value, places team logos below,
    each logo spanning 70% of its column width (preserving aspect ratio).
    """
    setup_montserrat_font()
    if phase:
        df = df[df['FASE']==phase]
    if teams:
        df = df[df['EQUIPO'].isin(teams)]

    agg   = df.groupby('EQUIPO')[['PLAYS','POSS']].mean()
    order = [t for t in teams if t in agg.index] if teams else sorted(agg.index)
    plays = agg.loc[order,'PLAYS'].to_numpy()
    poss  = agg.loc[order,'POSS'].to_numpy()
    n     = len(order)
    x     = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(8,n*1.2), 7.5))  # Aumenté altura
    fig.subplots_adjust(left=0.07, right=0.75, bottom=0.18, top=0.85)  # Más margen superior

    # alternating background
    for i in range(n):
        if i % 2 == 0:
            ax.axvspan(i-0.5, i+0.5, color='lightgray', alpha=0.3, zorder=0)

    # plot lines & means
    ax.axhline(plays.mean(), color='#e8c810', lw=1, alpha=0.7, zorder=1)
    ax.axhline(poss.mean(),  color='#e8c810', lw=1, alpha=0.7, zorder=1)
    ax.plot(x, plays, '-o', color='#1f77b4', lw=2, markersize=8, zorder=3)
    ax.plot(x, poss,  '-o', color='#ff7f0e', lw=2, markersize=8, zorder=3)

    # diffs
    for xi, p, q in zip(x, plays, poss):
        ax.plot([xi,xi],[p,q], color='gray', lw=1, alpha=0.3, zorder=2)
        mid = (p+q)/2
        ax.text(xi+0.1, mid, f"{p-q:+.1f}",
                ha='left', va='center', fontsize=8, weight='bold', color='black')

    # values
    for xi, yv in zip(x, plays):
        ax.text(xi, yv+15, f"{yv:.2f}", ha='center', va='bottom',
                color='#1f77b4', fontsize=10)
    for xi, yv in zip(x, poss):
        ax.text(xi, yv-15, f"{yv:.2f}", ha='center', va='top',
                color='#ff7f0e', fontsize=10)

    # end labels
    ax.text(n-0.3, plays[-1], 'PLAYS', ha='left', va='center',
            color='#1f77b4', fontsize=12, weight='bold')
    ax.text(n-0.3, poss[-1], 'POSESIONES', ha='left', va='center',
            color='#ff7f0e', fontsize=12, weight='bold')

    # styling
    ax.set_xticks(x)
    ax.set_xticklabels([])      # no labels
    ax.set_xlim(-0.5, n-0.3)
    y0, y1 = ax.get_ylim()
    yr = y1 - y0
    ax.set_ylim(y0 - 0.2*yr, y1)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)  # hide x‐axis line
    ax.tick_params(bottom=False)

    # logos below via AnnotationBbox
    fig.canvas.draw()
    bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    width_inches = bbox.width
    inches_per_unit = width_inches / n
    logo_w_in = inches_per_unit * 0.7   # 70% of column width

    logo_y = y0 - 0.1*yr
    for xi, team in zip(x, order):
        logo = get_team_logo(team)
        if not logo: continue
        ar = logo.width / logo.height
        zoom = logo_w_in * fig.dpi / logo.width
        img = OffsetImage(logo, zoom=zoom)
        ab  = AnnotationBbox(img, (xi, logo_y),
                             frameon=False, xycoords='data', pad=0)
        ax.add_artist(ab)

    # titles and subtitle
    fig.suptitle('PLAYS vs POSESIONES por Equipo', fontsize=20, weight='bold', y=1.05)
    
    # Add subtitle with better readability and more spacing
    subtitle = "Muchas plays → ritmo alto  •  Pocas plays → ritmo lento  •  Gran diferencia → segundas oportunidades"
    fig.text(0.5, 1, subtitle, 
             ha='center', va='top', fontsize=12, 
             weight='normal', color='#333333')

    plt.tight_layout()
    return fig



if __name__ == '__main__':
    df = pd.read_excel('./data/teams_aggregated.xlsx')
    MIS_EQUIPOS = [
        'BALONCESTO TALAVERA', 'C.B. TRES CANTOS', 'CB ARIDANE',
        'CB LA MATANZA', 'EB FELIPE ANTÓN', 'LUJISA GUADALAJARA BASKET',
        'REAL CANOE N.C.', 'UROS DE RIVAS', 'ZENTRO BASKET MADRID'
    ]
    board = plot_plays_vs_poss(df, teams=MIS_EQUIPOS, phase=None)
    board.savefig('plays_vs_poss_with_brief_note.png', dpi=300,
                  bbox_inches='tight', facecolor='white', edgecolor='none')
