import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from PIL import Image
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

def get_team_logo(team_name: str):
    """Carga logo desde images/clubs/, igual que en draw_team_board."""
    fn = team_name.lower().replace(' ', '_').replace('.', '').replace(',', '').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    path = os.path.join(os.path.dirname(__file__), '..', '..',
                        'images', 'clubs', f'{fn}.png')
    if os.path.exists(path):
        return Image.open(path).convert('RGBA')
    else:
        print(f"❌ Logo no encontrado: {path}")
        return None


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

def plot_net_rating_vertical_with_stickers(df, value_col: str = 'NETRTG'):
    """
    Minimalist vertical Net Rating bar chart + logo "stickers" at each bar tip.
    Canvas, bars, text, title, etc. remain exactly as the clean version.
    Logos are drawn as AnnotationBbox with a fixed fraction of bar width
    and preserve their aspect ratio.
    """
    # Set up Montserrat font
    montserrat_path = os.path.join(os.path.dirname(__file__), '..', '..', 'fonts', 'Montserrat-Regular.ttf')
    if os.path.exists(montserrat_path):
        montserrat_prop = fm.FontProperties(fname=montserrat_path)
        plt.rcParams['font.family'] = montserrat_prop.get_name()
    
    # 1) Prepare data & colors
    plot_df = (df[['EQUIPO', value_col]]
               .groupby('EQUIPO').mean()
               .sort_values(by=value_col))
    teams = plot_df.index.to_list()
    values = plot_df[value_col].to_numpy()
    n = len(values)
    min_val, max_val = values.min(), values.max()
    span = max_val - min_val

    colors = []
    for v in values:
        if v == max_val:
            colors.append('#FBC02D')
        elif v >= 0:
            colors.append('#388E3C')
        elif v >= -10:
            colors.append('#E64A19')
        else:
            colors.append('#EF5350')

    # 2) Draw chart (exactly as your clean function)
    fig, ax = plt.subplots(figsize=(max(8, n*1.2), 6))
    x = np.arange(n)
    bars = ax.bar(x, values, color=colors)
    ax.axhline(0, color='black', linestyle=(0, (1, 2)), lw=3)
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(min(min_val * 1.1, -1), max_val * 1.1)

    # annotate values - centered in middle of bars
    for bar, v in zip(bars, values):
        cx = bar.get_x() + bar.get_width()/2
        ty = bar.get_height() / 2  # Middle of the bar
        ax.text(cx, ty, f"{v:.2f}",
                ha='center', va='center',
                color='white', weight='bold', fontsize=12)

    ax.set_title('NET RANKING', fontsize=20, weight='bold', pad=20)
    ax.text(0.5, 1.02,
            'Net Rating = Puntos anotados por 100 posesiones - '
            'Puntos permitidos por 100 posesiones',
            ha='center', va='bottom',
            transform=ax.transAxes, fontsize=10)

    # --- 3) Draw logos as fixed-size stickers ---
    # Must draw the figure to get correct bbox
    fig.canvas.draw()
    # Compute pixels per data-unit in x
    x0, x1 = ax.get_xlim()
    bbox = ax.get_window_extent()
    pix_per_data_x = bbox.width / (x1 - x0)

    for bar, team, v in zip(bars, teams, values):
        logo = get_team_logo(team)
        if logo is None:
            continue

        # Desired sticker width = 80% of bar width (data units → pixels)
        bar_w = bar.get_width()
        disp_w_px = bar_w * 0.5 * pix_per_data_x
        # Compute zoom factor for OffsetImage
        orig_w_px = logo.width
        zoom = disp_w_px / orig_w_px

        # Create the OffsetImage
        img_box = OffsetImage(logo, zoom=zoom)

        # Position just above/below the bar tip
        cx = bar.get_x() + bar.get_width()/2
        ty = bar.get_height()
        
        # Dynamic offset: larger for smaller bars to avoid overlap with centered numbers
        base_offset = span * 0.02
        bar_height_ratio = abs(ty) / max(abs(max_val), abs(min_val))
        # If bar is small (less than 30% of max), increase offset slightly
        if bar_height_ratio < 0.15:
            print("Team with small bar:", team, "Value:", bar_height_ratio)
            offset_multiplier = 3  # 1.3x larger offset for small bars
        elif bar_height_ratio < 0.4:
            print("Team with medium bar:", team, "Value:", bar_height_ratio)
            offset_multiplier = 1  # 1.15x larger offset for medium bars
        else:
            print("Team with large bar:", team, "Value:", bar_height_ratio)
            offset_multiplier = -0.75  # Normal offset for large bars
            
        y_offset = base_offset * offset_multiplier if v >= 0 else -base_offset * offset_multiplier
        
        ab = AnnotationBbox(
            img_box,
            (cx, ty + y_offset),
            frameon=False,
            xycoords='data',
            pad=0
        )
        ax.add_artist(ab)

    # 4) Clean axes
    ax.axis('off')
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
    

    board = plot_net_rating_vertical_with_stickers(stats)
    # save the figure with exact dimensions (no tight bbox to avoid resizing)
    board.savefig('./net_rtg_chart.png', 
              dpi=300,                    # Control DPI explicitly 
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png',               # PNG format
              bbox_inches='tight'  # Use tight layout to avoid clipping
              )               

    print("Figure saved with this dimensions:", board.get_size_inches() * 100)  # Use same DPI for calculation
