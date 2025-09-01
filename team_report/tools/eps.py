import os
import textwrap
import requests
from io import BytesIO
from PIL import Image
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from .utils import COLORS, setup_montserrat_font, format_player_name, compute_advanced_stats, get_team_logo
from rembg import remove

def plot_player_EPS_bar(df: pd.DataFrame) -> plt.Figure:
    """
    Grafica barras horizontales de EPS con cuatro columnas:
      1) logo del club
      2) nombre formateado
      3) imagen del jugador
      4) barra con el valor de EPS

    Input df: columnas ['JUGADOR','DORSAL','IMAGEN','EQUIPO','EPS']
    """
    setup_montserrat_font()

    # 1) prepara datos
    df['FORMATTED'] = df.apply(lambda r: format_player_name(r['JUGADOR'], r['DORSAL']), axis=1)
    df = df.sort_values('EPS', ascending=True).reset_index(drop=True)
    df = df[(df['EPS'].notna()) & (df['EPS'] != 0)]
    n = len(df)


    # 2) calcula ancho absoluto de texto (column width) en caracteres
    max_chars = df['FORMATTED'].str.len().max()
    # ajusta width_ratios: logo=1, texto=max_chars, foto=1, barra fija=6
    wr = [1, max_chars/10, 1, 6]

    # 3) figura y gridspec
    fig = plt.figure(figsize=(19, n*0.6 + 4))  # Más altura para separar título, subtítulo y gráfico
    gs = fig.add_gridspec(n, 4, width_ratios=wr, wspace=0.05, hspace=0.3)

    # 4) preparar escala de colores verde a rojo
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.cm as cm
    
    # Crear colormap de rojo (peor) a verde (mejor)
    colors = COLORS  # red to green
    n_colors = len(colors)
    cmap = LinearSegmentedColormap.from_list('red_to_green', colors, N=256)

    # Normalizar valores EPS para el colormap (0 = peor, 1 = mejor)
    eps_min, eps_max = df['EPS'].min(), df['EPS'].max()
    if eps_max > eps_min:
        df['EPS_norm'] = (df['EPS'] - eps_min) / (eps_max - eps_min)
    else:
        df['EPS_norm'] = 0.5  # Si todos tienen el mismo valor

    for i, (_, row) in enumerate(df.iterrows()):
        y = n - 1 - i

        # --- 3.1) Logo del club ---
        ax_club = fig.add_subplot(gs[y, 0])
        logo = get_team_logo(row['EQUIPO'])
        if logo is not None:
            # escalar logo a misma altura que foto (0.8 fila)
            h_fig = fig.get_size_inches()[1] / n * 0.8
            h_px = int(h_fig * fig.dpi)
            ar = logo.width / logo.height
            w_px = int(h_px * ar)
            logo = logo.resize((w_px, h_px), Image.LANCZOS)
            ax_club.imshow(logo)
        ax_club.axis('off')

        # --- 3.2) Texto ---
        ax_text = fig.add_subplot(gs[y, 1])
        ax_text.text(0, 0.5, row['FORMATTED'], va='center', ha='left', fontsize=12)
        ax_text.axis('off')

        # --- 3.3) Imagen del jugador ---
        ax_img = fig.add_subplot(gs[y, 2])
        img = None
        try:
            src = str(row['IMAGEN'])
            if src.lower().startswith('http'):
                resp = requests.get(src, timeout=5)
                img = Image.open(BytesIO(resp.content)).convert('RGBA')
            else:
                img = Image.open(src).convert('RGBA')
        except:
            img = Image.open('images/templates/generic_player.png').convert('RGBA')

        if img is not None:
            img = remove(img)
            # misma altura que el logo
            h_px = int(fig.get_size_inches()[1]/n * fig.dpi * 0.8)
            ar = img.width / img.height
            w_px = int(h_px * ar)
            img = img.resize((w_px, h_px), Image.LANCZOS)
            ax_img.imshow(img)
        ax_img.axis('off')

        # --- 3.4) Barra EPS ---
        ax_bar = fig.add_subplot(gs[y, 3])
        val = row['EPS']  # Usar EPS en lugar de OE
        
        # Obtener color basado en el valor normalizado
        color = cmap(row['EPS_norm'])
        
        ax_bar.barh(0, val, color=color)
        
        # Determinar color del texto basado en el tamaño de la barra
        # Si la barra es muy pequeña (menos del 20% del máximo), usar texto negro
        max_eps = df['EPS'].max()
        text_color = 'black' if val < (max_eps * 0.2) else 'white'
        
        ax_bar.text(val/2, 0, f"{val/100:.2f}", va='center', ha='center',
                    color=text_color, fontsize=12, fontweight='bold')
        ax_bar.set_xlim(0, df['EPS'].max()*1.05)  # Usar el máximo EPS como límite
        ax_bar.axis('off')

    # 4) título y subtítulo explicativo
    fig.suptitle("EPS", fontsize=36, weight='bold', y=1)
    # Subtítulo explicativo para jugadores
    subtitle = (
        "¿Qué mide EPS? EPS combina cuántos puntos anota y qué tan eficientemente aprovecha sus oportunidades ofensivas.\n"
        "Un EPS alto significa que convierte sus puntos con pocas oportunidades perdidas: es efectivo y decisivo.\n"
        "Un EPS bajo significa que, aunque anote puntos, lo hace con muchas pérdidas/fallos; su impacto global es menor que el simple conteo de puntos sugiere.\n"
    )
    fig.text(0.5, 0.94, subtitle, ha='center', va='top', fontsize=15, color='#222', wrap=True)
    plt.tight_layout(rect=[0,0.03,1,0.96])  # Menos margen abajo, más altura total
    return fig

# === EJEMPLO DE USO ===
if __name__ == "__main__":
    PATH = './data/jugadores_aggregated.xlsx'
    df_demo = pd.read_excel(PATH)
    # Filtramos solo un equipo...
    df_demo = df_demo[df_demo['EQUIPO'] == 'UROS DE RIVAS']
    stats_dicts = df_demo.apply(compute_advanced_stats, axis=1)
    stats_df = pd.DataFrame(stats_dicts.tolist())
    # añadimos la columna 'EQUIPO' para el logo
    stats_df['EQUIPO'] = df_demo['EQUIPO'].values

    fig = plot_player_EPS_bar(stats_df)
    fig.savefig("eps_demo.png", dpi=300)
