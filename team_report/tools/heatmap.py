import textwrap
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.font_manager as fm
import os
from PIL import Image
import numpy as np


STATS_NAME_MAPPING = {
    'T2C': 'T2 CONVERTIDO',
    'T2I': 'T2 INTENTADO',
    'T3C': 'T3 CONVERTIDO',
    'T3I': 'T3 INTENTADO',
    'T1C': 'TL CONVERTIDOS',
    'T1I': 'TL INTENTADOS',
    'OREB': 'REB OFFENSIVO',
    'DREB': 'REB DEFENSIVO',
    'AST': 'ASISTENCIAS',
    'ROB': 'RECUPEROS',
    'TOV': 'PERDIDAS',
}

def make_discrete_cmap(n: int, anchor_hexes: list[str]):
    """
    Given n ranks and a list of anchor colors, returns:
      - cmap: a ListedColormap with n colors sampled from the anchors
      - norm: a BoundaryNorm mapping integers 1..n → those colors
    """
    # 1) build a continuous colormap from your 8 anchors:
    cont_cmap = LinearSegmentedColormap.from_list("custom_cont", anchor_hexes, N=256)
    # 2) sample exactly n colors, evenly spaced from it:
    if n == 1:
        # degenerate case: just take the middle color
        palette = [cont_cmap(0.5)]
    else:
        palette = [cont_cmap(i/(n-1)) for i in range(n)]
    # 3) turn that into a discrete ListedColormap
    cmap = ListedColormap(palette)
    # 4) build a norm so that 1→palette[0], 2→palette[1], …, n→palette[n-1]
    boundaries = list(range(1, n+2))   # [1,2,…,n+1]
    norm = BoundaryNorm(boundaries, ncolors=n)
    return cmap, norm


def generate_team_heatmap(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    phase: str | None = None
):
    """
    Carga los datos de jugadores por partido, agrega por equipo,
    calcula el ranking de cada estadística (1 = mejor, N = peor),
    y dibuja un heatmap con código de color (verde=mejor, rojo=peor).
    Incluye logos de equipos a la izquierda.
    """
    # Configurar fuente Montserrat
    font_path = os.path.join(os.path.dirname(__file__), '..', '..', 'fonts', 'Montserrat-Regular.ttf')
    if os.path.exists(font_path):
        montserrat_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = montserrat_prop.get_name()
    
    metrics = [
        'PUNTOS +', 'PPP', 'PUNTOS -', 'PPP OPP',
        'T3C', 'T3I',
        'T2C', 'T2I',
        'T1C', 'T1I',
        'TOV', 'ROB', 'OREB', 'DREB',  'AST'
    ]
    
    
    # 2) Filtros opcionales
    if phase is not None:
        df = df[df['FASE'] == phase]
        print(f"Filtrando por fase: {phase}")
    if teams is not None:
        df = df[df['EQUIPO'].isin(teams)]
        print(f"Los equipos en el dataset son: {df['EQUIPO'].unique()}")
        print(f"Teams not found in dataset: {set(teams) - set(df['EQUIPO'].unique())}")
        
    
        
    
    # 3) Si las métricas no están en los datos, usar el mapping para renombrar
    for metric in metrics:
        if metric not in df.columns:
            if metric in STATS_NAME_MAPPING:
                df.rename(columns={STATS_NAME_MAPPING[metric]: metric}, inplace=True)
            else:
                raise ValueError(f"Métrica '{metric}' no encontrada en los datos y no tiene un mapeo definido.")

    team_stats = df.groupby('EQUIPO')[metrics].sum()

    team_stats['TCC'] = team_stats['T2C'] + team_stats['T3C']
    team_stats['TCI'] = team_stats['T2I'] + team_stats['T3I']

    # Ordenar columnas
    team_stats = team_stats[['PUNTOS +', 'PPP', 'PUNTOS -', 'PPP OPP',
                             'TCC', 'TCI',
                             'T3C', 'T3I',
                             'T1C', 'T1I',
                             'TOV', 'ROB', 'OREB', 'DREB',  'AST'
                             ]]

    # 4) Calcular ranking: el valor más alto recibe el puesto 1
    ranks = team_stats.rank(ascending=False, method='min').astype(int)
    
    # 5) Ordenar por 'PUNTOS +' si está en las métricas
    sort_col = 'PUNTOS +' if 'PUNTOS +' in ranks.columns else ranks.columns[0]
    ranks = ranks.sort_values(by=sort_col, ascending=True)

    # 6) Función para cargar logo del equipo
    def get_team_logo(team_name):
        """Carga el logo del equipo desde images/clubs/"""
        # Normalizar nombre: lowercase, espacios por _, quitar puntos
        logo_name = team_name.lower().replace(' ', '_').replace('.', '').replace(',', '').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') 
        logo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'clubs', f'{logo_name}.png')
        
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert('RGBA')
                return logo
            except Exception as e:
                print(f"⚠️ Error al cargar logo para '{team_name}' desde '{logo_path}': {e}")
                return None
        else:
            print(f"❌ Archivo no encontrado: {logo_path}")
            return None
        
    

    # 7) Crear figura con 3 columnas: TEXTO | LOGO | HEATMAP
    fig = plt.figure(figsize=(len(metrics)*0.5 + 6, len(ranks)*1.2 + 1))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 0.6, 4], wspace=0.02)

    # Eje 1: TEXTO alineado a la izquierda
    ax_text = fig.add_subplot(gs[0])
    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, len(ranks))
    ax_text.axis('off')

    # Eje 2: LOGO centrado
    ax_logo = fig.add_subplot(gs[1])
    ax_logo.set_xlim(0, 1)
    ax_logo.set_ylim(0, len(ranks))
    ax_logo.axis('off')

    # Eje 3: HEATMAP
    ax_heatmap = fig.add_subplot(gs[2])
    
    # --- Configuración de wrapping ---
    max_chars = 18  # máximo caracteres por línea antes de partir
    wrapped_names = {
        team: '\n'.join(textwrap.wrap(team, max_chars))
        for team in ranks.index
    }

    # 8) Pintar para cada equipo: texto en ax_text, logo en ax_logo
    for i, team in enumerate(reversed(ranks.index)):
        y_pos = i + 0.5

        # --- TEXTO ENVUELTO ---
        ax_text.text(
            0.01, y_pos, wrapped_names[team],
            fontsize=15,
            verticalalignment='center',
            horizontalalignment='left'
        )
        # --- LOGO ---
        logo = get_team_logo(team)
        if logo:
            # redimensionar manteniendo aspecto y calidad
            orig_w, orig_h = logo.size
            ar = orig_w / orig_h
            logo_h = 0.8   # proporción del espacio vertical
            logo_w = logo_h * ar

            # Calcular tamaño óptimo basado en DPI y tamaño original
            # Usar el tamaño original si es razonable, sino escalar inteligentemente
            target_height = max(100, min(orig_h, 300))  # Entre 100-300px
            target_width = int(target_height * ar)
            
            # Solo redimensionar si es necesario
            if orig_h != target_height:
                logo_resized = logo.resize(
                    (target_width, target_height),
                    Image.Resampling.LANCZOS
                )
            else:
                logo_resized = logo
                
            logo_arr = np.array(logo_resized)

            # centrar en ax_logo (x en [0.5-logo_w/2, 0.5+logo_w/2])
            x0 = (0.5 - logo_w/2)
            x1 = (0.5 + logo_w/2)
            y0 = y_pos - logo_h/2
            y1 = y_pos + logo_h/2

            ax_logo.imshow(logo_arr, extent=[x0, x1, y0, y1], aspect='equal', interpolation='bilinear')
            
    
    # 1) Define the exact 8‐step palette you sketched:
    colors = [
        '#2e7d32',  # 1 (dark green)
        '#4caf50',  # 2
        '#81c784',  # 3
        '#c8e6c9',  # 4 (very pale green)
        '#e0e0e0',  # 5 (grey)
        '#ef9a9a',  # 6 (light pink)
        '#e57373',  # 7
        '#f44336',  # 8 (red)
    ]      
    
    # number of teams/ranks you actually have:
    n = ranks.shape[0]  
    
    cmap, norm = make_discrete_cmap(n, colors)

    
    # 9) Pass both into your heatmap instead of `cmap='RdYlGn_r'`:
    sns.heatmap(
    ranks,
    annot=ranks,
    fmt='d',
    cmap=cmap,
    norm=norm,
    cbar=False,
    linewidths=1,
    linecolor='black',
    annot_kws={'size': 20, 'weight': 'bold'},
    ax=ax_heatmap
    )

    # 10) Ajustes finales - Modern approach for X-axis labels
    # For seaborn heatmap, labels should be centered on cells (0.5, 1.5, 2.5, ...)
    tick_positions = np.arange(len(ranks.columns)) + 0.5
    tick_labels = ranks.columns.tolist()
    
    # Set ticks and labels properly - center aligned
    ax_heatmap.set_xticks(ticks=tick_positions, labels=tick_labels, rotation=90, ha='center', weight='bold', fontsize=15)
    ax_heatmap.xaxis.tick_top()  # Move X-axis labels to top
    ax_heatmap.xaxis.set_label_position('top')  # Move X-axis label to top
    ax_heatmap.tick_params(top=False)  # Remove tick marks, keep labels
    
    # Clean Y-axis
    ax_heatmap.set_ylabel('')
    ax_heatmap.set_yticklabels([])
    ax_heatmap.tick_params(left=False)
    
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

    board = generate_team_heatmap(df, teams=MIS_EQUIPOS, phase=None)
    # save the figure
    board.savefig('team_board.png', 
              bbox_inches='tight', 
              dpi=300,                    # High resolution
              facecolor='white',          # White background
              edgecolor='none',           # No edge color
              format='png')               # PNG format

