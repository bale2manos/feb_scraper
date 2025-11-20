import os, textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Patch
from PIL import Image

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

    # Normalizar todos los valores por partido jugado
    PJ = df.get('PJ', 1)
    T1I_per_game = T1I / PJ
    T2I_per_game = T2I / PJ
    T3I_per_game = T3I / PJ
    TOV_per_game = TOV / PJ  # TOV también son totales, no promedios
    
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
        print(f"🔍 DEBUG compute_team_stats - EQUIPO: {df.loc[idx, 'EQUIPO']}")
        print(f"{'='*80}")
        print(f"PJ: {df.loc[idx, 'PJ']}")
        print(f"T1I total: {df.loc[idx, 'T1I']}, T2I total: {df.loc[idx, 'T2I']}, T3I total: {df.loc[idx, 'T3I']}")
        print(f"TOV total: {df.loc[idx, 'TOV']}")
        print(f"\nValores por partido:")
        print(f"  T1I_per_game: {T1I_per_game.iloc[0]:.2f}")
        print(f"  T2I_per_game: {T2I_per_game.iloc[0]:.2f}")
        print(f"  T3I_per_game: {T3I_per_game.iloc[0]:.2f}")
        print(f"  TOV_per_game: {TOV_per_game.iloc[0]:.2f}")
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

def generate_team_play_distribution(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Generates a figure with 3 columns:
    1) Team name text
    2) Team logo
    3) Horizontal stacked bar chart of play distribution percentages
    """
    # Configure Montserrat font
    font_path = os.path.join(os.path.dirname(__file__), '..', '..', 'fonts', 'Montserrat-Regular.ttf')
    if os.path.exists(font_path):
        montserrat_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = montserrat_prop.get_name()

    # Filter
    if phase is not None:
        df = df[df['FASE'].isin(phase)]
    if teams is not None and len(teams) > 0:
        df = df[df['EQUIPO'].isin(teams)]

    # Columns to plot
    play_cols = ['F1 Plays%', 'F2 Plays%', 'F3 Plays%', 'TO Plays%']
    plot_df = df.groupby('EQUIPO')[play_cols].mean().sort_values(by='EQUIPO', ascending=True)

    # Wrap team names
    max_chars = 18
    wrapped_names = {team: '\n'.join(textwrap.wrap(team, max_chars)) for team in plot_df.index}

    # Figure layout - WIDER CANVAS
    n_teams = len(plot_df)
    fig = plt.figure(figsize=(16, n_teams*1.2))  # Increased width from 12 to 16
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 0.6, 4], wspace=0.02)  # Reduced text column from 1.5 to 1.0

    # Left text column
    ax_text = fig.add_subplot(gs[0])
    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, n_teams)
    ax_text.axis('off')

    # Logo column
    ax_logo = fig.add_subplot(gs[1])
    ax_logo.set_xlim(0, 1)
    ax_logo.set_ylim(0, n_teams)
    ax_logo.axis('off')

    # Stacked bar chart column
    ax_bar = fig.add_subplot(gs[2])
    ax_bar.set_xlim(0, 100)
    ax_bar.set_ylim(-0.5, n_teams-0.5)
    ax_bar.axis('off')

    # Color map (match your reference example)
    colors = ['#9b59b6', '#3498db', '#1abc9c', '#D0234E']
    labels = ['Tiros de 1', 'Tiros de 2', 'Tiros de 3', 'Pérdidas']

    # Iterate teams from top to bottom
    for i, (team, row) in enumerate(reversed(list(plot_df.iterrows()))):
        y = i

        # --- 1) Team Name (centered to row) ---
        ax_text.text(
            0.01, y + 0.5, wrapped_names[team],
            fontsize=14,
            va='center', ha='left'
        )

        # --- 2) Team Logo (centered to row) ---
        logo_fn = (
            team.lower().replace(' ', '_')
            .replace('.', '').replace(',', '')
            .replace('á','a').replace('é','e').replace('í','i')
            .replace('ó','o').replace('ú','u')
        )
        logo_path = os.path.join(os.path.dirname(__file__), '..','..','images','clubs',f'{logo_fn}.png')
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert('RGBA')
            ar = logo.width / logo.height
            logo_plot_h = 0.8    # 80% of row
            logo_plot_w = logo_plot_h * ar

            target_h_px = int(logo_plot_h * fig.dpi)
            target_w_px = int(target_h_px * ar)
            logo_resized = logo.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
            logo_arr = np.array(logo_resized)

            y0 = y + 0.5 - logo_plot_h / 2
            y1 = y + 0.5 + logo_plot_h / 2
            x0 = 0.5 - logo_plot_w / 2
            x1 = 0.5 + logo_plot_w / 2
            ax_logo.imshow(logo_arr, extent=[x0,x1,y0,y1], aspect='equal')  # Fixed aspect ratio

        # --- 3) Stacked bars (same row center) ---
        start = 0
        for val, color in zip(row, colors):
            ax_bar.barh(y, val, left=start, color=color, edgecolor='white')
            if val > 4:  # only label large segments
                ax_bar.text(start+val/2, y, f"{val:.1f}%", ha='center', va='center',
                            color='white', fontsize=14, weight='bold')
            start += val

    # --- 4) Title and Legend ---
    fig.suptitle('Finalización de Plays (%)', fontsize=40, weight='bold', y=1)

    legend_handles = [Patch(facecolor=c, label=l) for c,l in zip(colors, labels)]
    ax_bar.legend(handles=legend_handles, loc='lower center',
                  bbox_to_anchor=(0.5, 1), ncol=4, fontsize=12, frameon=False)

    plt.tight_layout()
    return fig

if __name__ == '__main__':
    # Ejemplo de uso:
    FILE = 'f:/PyCharm/feb_scraper/data/older/teams_aggregated.xlsx'
    MIS_EQUIPOS = ['BALONCESTO TALAVERA', 'C.B. TRES CANTOS', 'CB ARIDANE',
                   'CB LA MATANZA', 'EB FELIPE ANTÓN', 'LUJISA GUADALAJARA BASKET',
                   'REAL CANOE N.C.', 'UROS DE RIVAS', 'ZENTRO BASKET MADRID'
    ]

    FASE = "Liga Regular \"B-A\""
    df = pd.read_excel(FILE)
    
    stats = compute_team_stats(df, teams=MIS_EQUIPOS, phase=None)
    

    board = generate_team_play_distribution(stats, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('play_distribution.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format

