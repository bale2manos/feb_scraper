import os
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

from .utils import get_team_logo, setup_montserrat_font


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
        df = df[df['FASE'] == phase]
    
    # 2) Filter by teams if provided
    if teams is not None:
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


    # Play distribution percentages - Using vectorized operations
    df['F1 Plays%'] = np.where(Plays > 0, (T1I * 0.44 / Plays * 100), 0)
    df['F2 Plays%'] = np.where(Plays > 0, (T2I / Plays * 100), 0)
    df['F3 Plays%'] = np.where(Plays > 0, (T3I / Plays * 100), 0)
    df['TO Plays%'] = np.where(Plays > 0, (TOV / Plays * 100), 0)
    
    # Points per shot type
    df['PT1'] = T1C
    df['PT2'] = T2C *2
    df['PT3'] = T3C *3

    return df




def generate_team_points_distribution(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Gráfica de Distribución de puntos por equipo:
     1) Texto (nombre)
     2) Logo
     3) Barras apiladas de PT1, PT2, PT3 con anotaciones y total al final
    """
    # Montserrat
    setup_montserrat_font()

    # Filtrar
    if phase is not None:
        df = df[df['FASE']==phase]
    if teams is not None:
        df = df[df['EQUIPO'].isin(teams)]

    # Agregar PT1, PT2, PT3
    pts = df.groupby('EQUIPO')[['PT1','PT2','PT3']].sum()
    pts['TOTAL'] = pts.sum(axis=1)
    pts = pts.sort_values('TOTAL', ascending=False)

    # Prepara nombres
    max_chars = 18
    wrapped = {t:'\n'.join(textwrap.wrap(t, max_chars)) for t in pts.index}

    # Colores y labels
    colors = ['#9b59b6','#3498db','#1abc9c']
    labels = ['Puntos de tiros de 1','Puntos de tiros de 2','Puntos de tiros de 3']

    # Layout figura
    n = len(pts)
    fig = plt.figure(figsize=(16, n*1.2))
    gs = fig.add_gridspec(1,3, width_ratios=[1.0,0.6,4], wspace=0.02)

    ax_text = fig.add_subplot(gs[0])
    ax_logo = fig.add_subplot(gs[1])
    ax_bar  = fig.add_subplot(gs[2])

    # FIX: make text & logo axes share same data-space y
    ax_text.set_xlim(0,1)
    ax_text.set_ylim(-0.5, n-0.5)
    ax_logo.set_xlim(0,1)
    ax_logo.set_ylim(-0.5, n-0.5)

    # bar axis
    ax_bar.set_xlim(0, pts['TOTAL'].max()*1.05)
    ax_bar.set_ylim(-0.5, n-0.5)

    # hide all spines/ticks
    for ax in (ax_text, ax_logo, ax_bar):
        ax.axis('off')

    # Title + legend
    fig.suptitle('Distribución de puntos por equipo', fontsize=32, weight='bold', y=1.02)
    patches = [Patch(color=c,label=l) for c,l in zip(colors,labels)]
    ax_bar.legend(handles=patches, loc='upper center',
                  bbox_to_anchor=(0.5,1.05), ncol=3, frameon=False, fontsize=14)

    # Dibujar filas
    for i,(team,row) in enumerate(pts.iterrows()):
        y = n-1-i  # invert order: top team at y=n-1
        # 1) texto
        ax_text.text(0.01, y, wrapped[team], va='center', ha='left', fontsize=16)
        # 2) logo
        logo = get_team_logo(team)
        if logo is not None:
            # compute zoom so logo is ~1.4 rows tall (much larger)
            zoom = 5 / logo.height * fig.dpi * (1/fig.get_size_inches()[1])
            img = OffsetImage(logo, zoom=zoom)
            ab  = AnnotationBbox(img, (0.5, y),
                                 frameon=False,
                                 xycoords='data')
            ax_logo.add_artist(ab)
        # 3) barras apiladas
        start = 0
        for val,c in zip(row[['PT1','PT2','PT3']], colors):
            ax_bar.barh(y, val, left=start, color=c, edgecolor='white')
            if val>0:
                ax_bar.text(start+val/2, y, f"{int(val)}",
                            ha='center', va='center',
                            color='white', fontsize=14, weight='bold')
            start += val
        # total al final
        ax_bar.text(start + pts['TOTAL'].max()*0.01, y,
                    f"{int(row['TOTAL'])}",
                    ha='left', va='center', fontsize=16)

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
    
    stats = compute_team_stats(df, teams=MIS_EQUIPOS, phase=None)

    board = generate_team_points_distribution(stats, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('points_distribution.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format

