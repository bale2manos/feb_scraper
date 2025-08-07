import os
import textwrap
import requests
from io import BytesIO

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
from rembg import remove

from .utils import (
    setup_montserrat_font,
    format_player_name,
    get_team_logo,
    compute_advanced_stats
)

def plot_player_finalizacion_plays(df: pd.DataFrame) -> plt.Figure:
    """
    Gráfico de 'Finalización de Plays (%)' por jugador:
      1) logo del club
      2) nombre formateado
      3) foto del jugador
      4) barra apilada con F1, F2, F3 y TO Plays%

    Input: df con columnas ['JUGADOR','DORSAL','IMAGEN','EQUIPO',
                            'F1 Plays%','F2 Plays%','F3 Plays%','TO Plays%']
    """
    setup_montserrat_font()

    # --- 1) Prepara y filtra datos ---
    df = df.copy()
    df['FORMATTED'] = df.apply(
        lambda r: format_player_name(r['JUGADOR'], r['DORSAL']), axis=1
    )
    # Elimina nulos o ceros
    df = df[
        df[['F1 Plays%','F2 Plays%','F3 Plays%','TO Plays%']].notnull().all(axis=1)
    ].reset_index(drop=True)
    n = len(df)
    if n == 0:
        raise ValueError("No hay datos válidos para graficar.")

    # Orden por dorsal
    df = df.sort_values('DORSAL', ascending=False).reset_index(drop=True)
    df['TOTAL'] = df[['F1 Plays%', 'F2 Plays%', 'F3 Plays%', 'TO Plays%']].sum(axis=1)

    # --- 2) Calcula ratios de columna según texto más largo ---
    max_chars = df['FORMATTED'].str.len().max()
    # [logo, texto, foto, barras]
    width_ratios = [1, max_chars/12, 1, 6]

    # --- 3) Monta figura y gridspec ---
    fig = plt.figure(figsize=(22, n*0.6 + 1))
    gs = fig.add_gridspec(
        n, 4,
        width_ratios=width_ratios,
        wspace=0.05, hspace=0.3
    )

    # Colores y etiquetas de la barra
    bar_cols = ['F1 Plays%', 'F2 Plays%', 'F3 Plays%', 'TO Plays%']
    bar_colors = ['#9b59b6', '#3498db', '#1abc9c', '#D0234E']

    bar_labels = ['T1', 'T2', 'T3', 'Pelotas Perdidas']

    # --- 4) Dibuja cada fila ---
    for i, (_, row) in enumerate(df.iterrows()):
        y = n - 1 - i  # invertido para que el primero quede arriba

        # 4.1 Logo del club
        ax_logo = fig.add_subplot(gs[y, 0])
        logo = get_team_logo(row['EQUIPO'])
        if logo is not None:
            # escala a 80% de la altura de fila
            h_fig = fig.get_size_inches()[1] / n * 0.8
            h_px = int(h_fig * fig.dpi)
            ar = logo.width / logo.height
            w_px = int(h_px * ar)
            logo_resized = logo.resize((w_px, h_px), Image.LANCZOS)
            ax_logo.imshow(logo_resized)
        ax_logo.axis('off')

        # 4.2 Nombre formateado
        ax_text = fig.add_subplot(gs[y, 1])
        ax_text.text(
            0, 0.5, row['FORMATTED'],
            va='center', ha='left', fontsize=12
        )
        ax_text.axis('off')

        # 4.3 Foto del jugador
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
            # Use images/templates/generic_player.png if no image
            img = Image.open('images/templates/generic_player.png').convert('RGBA')

        if img is not None:
            img = remove(img)  # quita fondo
            # misma altura que logo
            h_fig = fig.get_size_inches()[1] / n * 0.8
            h_px = int(h_fig * fig.dpi)
            ar = img.width / img.height
            w_px = int(h_px * ar)
            img_resized = img.resize((w_px, h_px), Image.LANCZOS)
            ax_img.imshow(img_resized)
        ax_img.axis('off')

        # 4.4 Barras apiladas
        ax_bar = fig.add_subplot(gs[y, 3])
        start = 0
        for col, color in zip(bar_cols, bar_colors):
            val = float(row[col])
            ax_bar.barh(0, val, left=start, color=color, edgecolor='white')
            if val > 3:  # etiqueta sólo si espacio
                ax_bar.text(
                    start + val/2, 0,
                    f"{val:.1f}%",
                    ha='center', va='center',
                    color='white', fontsize=10, fontweight='bold'
                )
            start += val
        ax_bar.set_xlim(0, df['TOTAL'].max()*1.05)
        ax_bar.axis('off')

    # --- 5) Títulos y leyenda ---
    fig.suptitle(
        "Finalización de Plays (%)",
        fontsize=40, weight='bold', y=0.97
    )

    # leyenda manual - posicionada encima de todas las barras
    legend_handles = [
        Patch(color=c, label=l) for c, l in zip(bar_colors, bar_labels)
    ]
    # Crear un axes invisible para posicionar la leyenda encima de la primera barra
    ax_legend = fig.add_axes([0, 0, 1, 1])  # Invisible axes covering the whole figure
    ax_legend.axis('off')
    ax_legend.legend(
        handles=legend_handles,
        loc='upper center',
        bbox_to_anchor=(0.65, 0.92),  # Moved left from 0.75 to 0.7 to center over bars
        ncol=4, frameon=False, fontsize=12
    )

    plt.tight_layout(rect=[0,0,1,0.95])
    return fig

# === EJEMPLO DE USO ===
if __name__ == "__main__":
    PATH = './data/jugadores_aggregated.xlsx'
    df = pd.read_excel(PATH)
    # Filtramos un equipo de ejemplo
    df_eq = df[df['EQUIPO']=='UROS DE RIVAS']

    # Calculamos stats avanzadas
    stats_list = df_eq.apply(lambda r: compute_advanced_stats(r), axis=1)
    stats_df   = pd.DataFrame(stats_list.tolist())
    stats_df[['JUGADOR','DORSAL','IMAGEN','EQUIPO']] = df_eq[['JUGADOR','DORSAL','IMAGEN','EQUIPO']].values

    fig = plot_player_finalizacion_plays(stats_df)
    fig.savefig("finalizacion_plays_por_jugador.png", dpi=300)
