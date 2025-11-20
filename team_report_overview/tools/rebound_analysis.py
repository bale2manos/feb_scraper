import os
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image

from utils import get_team_logo, setup_montserrat_font

def add_rebound_analysis_to_axes(
    ax: plt.Axes,
    df: pd.DataFrame,
    position: tuple = (0.02, 0.02),  # (x, y) en coordenadas de fracción de ejes
    size: tuple = (0.4, 0.3),        # (width, height) en coordenadas de fracción de ejes
    dpi: int = 100
):
    """
    Añade el gráfico de análisis de rebotes a los ejes dados como una imagen incrustada.
    
    Parámetros:
    - ax: ejes de matplotlib donde añadir el gráfico
    - df: DataFrame con los datos de rebotes
    - position: (x, y) posición en coordenadas de fracción de ejes
    - size: (width, height) tamaño en coordenadas de fracción de ejes
    - dpi: resolución
    """
    import io
    from PIL import Image
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    
    # Generar el gráfico de rebotes
    rebound_fig = generate_team_rebound_analysis(df)
    
    # Convertir a imagen
    buf = io.BytesIO()
    rebound_fig.savefig(buf, format='png', dpi=150, bbox_inches=None,  # Cambiar de 'tight' a None
                        pad_inches=0.0, facecolor='white', edgecolor='none')  # Sin padding
    plt.close(rebound_fig)  # Cerrar para liberar memoria
    buf.seek(0)
    
    # Cargar imagen
    rebound_img = Image.open(buf)
    
    # Calcular zoom para ajustar al tamaño deseado
    fig = ax.get_figure()
    fig_width_px = fig.get_size_inches()[0] * dpi
    fig_height_px = fig.get_size_inches()[1] * dpi
    
    target_w_px = size[0] * fig_width_px
    target_h_px = size[1] * fig_height_px
    
    zoom_w = target_w_px / rebound_img.width
    zoom_h = target_h_px / rebound_img.height
    zoom = min(zoom_w, zoom_h)  # Usar el menor para mantener proporción
    
    # Añadir como imagen incrustada
    rebound_offset_img = OffsetImage(rebound_img, zoom=zoom)
    rebound_ab = AnnotationBbox(
        rebound_offset_img,
        position,
        xycoords='axes fraction',
        box_alignment=(0, 0),  # anclar esquina inferior izquierda
        frameon=False
    )
    ax.add_artist(rebound_ab)
    
    return rebound_ab

def generate_team_rebound_analysis(
    df: pd.DataFrame,
):
    """
    Gráfica de Análisis del Rebote (%) por equipo:
    Tres barras horizontales (una por %OREB, %REB, %DREB),
    ejes de 0 a 1, sin títulos ni logos.
    """
    # Montserrat
    setup_montserrat_font()


    # IMPORTANTE: df ya viene filtrado (1 fila por equipo), NO agrupar
    # Si agrupamos con mean(), estamos promediando valores ya filtrados incorrectamente
    stats = df[['EQUIPO', '%OREB','%REB','%DREB','REB OFFENSIVO','REB DEFENSIVO','PJ']].copy()
    
    # Debug: Mostrar valores para EB FELIPE ANTÓN si existe
    if 'EB FELIPE ANTÓN' in stats['EQUIPO'].values:
        felipe = stats[stats['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
        print(f"[DEBUG REBOUND_ANALYSIS] 🏀 EB FELIPE ANTÓN:")
        print(f"[DEBUG REBOUND_ANALYSIS]   %OREB: {felipe['%OREB']}")
        print(f"[DEBUG REBOUND_ANALYSIS]   %DREB: {felipe['%DREB']}")
        print(f"[DEBUG REBOUND_ANALYSIS]   %REB: {felipe['%REB']}")
        print(f"[DEBUG REBOUND_ANALYSIS]   REB OFFENSIVO: {felipe['REB OFFENSIVO']}")
        print(f"[DEBUG REBOUND_ANALYSIS]   REB DEFENSIVO: {felipe['REB DEFENSIVO']}")
    
    stats = stats.sort_values('EQUIPO', ascending=True)
    stats = stats.set_index('EQUIPO')  # Para mantener compatibilidad con el resto del código
    stats['REB'] = stats[['REB OFFENSIVO', 'REB DEFENSIVO']].sum(axis=1)

    # Colors & metric labels
    metrics = ['%DREB','%REB','%OREB']
    colors  = ['#3498DB','#E74C3C','#F39C12']  # azul, rojo, naranja
    # Corresponding mean columns for each metric
    mean_cols = ['REB DEFENSIVO','REB','REB OFFENSIVO']

    n = len(stats)
    # Crear figura más estrecha y alta para el análisis de rebotes
    fig = plt.figure(figsize=(4, 10))  # Más estrecho (4) y más alto (10)
    ax = fig.add_subplot(111)
    ax.axis('off')

    # Calcular el valor máximo para ajustar el eje Y
    max_value = stats[['%OREB','%REB','%DREB']].max().max()
    y_limit = max_value * 1.01  # Solo 1% más que el valor máximo para reducir margen blanco

    # Bar settings - ajustados para dimensiones fijas
    bar_width = 0.35  # Más ancho para mejor visibilidad
    offsets = [-bar_width, 0, bar_width]  # tres barras por equipo

    # x-scale ajustado para centrar el contenido
    total_width = (n-1) + bar_width*3  # ancho total necesario
    ax.set_xlim(-bar_width*2, n-1+bar_width*2)  # márgenes simétricos
    # y-range adjusted to max value + minimal margin, with bottom extension for labels
    ax.set_ylim(-0.15, y_limit)

    # Plot each team (simplified - just bars)
    for i,(team,row) in enumerate(stats.iterrows()):
        x_center = i  # Posición X del centro del grupo de barras

        # Three vertical bars with labels at the bottom
        for idx, (off, m, c) in enumerate(zip(offsets, metrics, colors)):
            x = x_center + off
            val = row[m]
            # Media por partido de la estadística correspondiente
            mean_val = row[mean_cols[idx]]
            pj = row['PJ'] if 'PJ' in row else 1
            mean_per_game = mean_val / pj if pj > 0 else 0

            # Label at the bottom of the bar (below, outside)
            ax.text(x, -0.02, m, va='top', ha='center', 
                   fontsize=10, weight='bold', color='black', rotation=0)

            # Vertical bar starting at y=0
            ax.bar(x, val, width=bar_width, color=c, edgecolor='white', bottom=0)

            # Percentage text inside the bar (rotated for better readability)
            ax.text(x, val/2, f"{row[m]*100:.1f}%",  # Reducido a 1 decimal
                    va='center', ha='center', color='white', fontsize=20, weight='bold', rotation=90)

            # Media por partido sobre la barra, en negro
            ax.text(x, val + 0.01, f"{mean_per_game:.2f}", va='bottom', ha='center', color='black', fontsize=13, weight='bold')

    # Ajustar espaciado para eliminar margen blanco innecesario
    plt.tight_layout(pad=0.1)  # Padding mínimo
    plt.subplots_adjust(left=0.1, right=0.9, top=0.95, bottom=0.2)  # Margen superior reducido de 0.9 a 0.95
    return fig


if __name__ == '__main__':
    # Ejemplo de uso:
    FILE = './data/teams_aggregated.xlsx'
    EQUIPO = "UROS DE RIVAS"
    df = pd.read_excel(FILE)
    df_filtrado = df[df['EQUIPO'] == EQUIPO]    


    board = generate_team_rebound_analysis(df_filtrado)
    # save the figure con configuración para evitar recortes
    board.savefig('rebound_analysis.png', 
              bbox_inches='tight',        # Ajustar automáticamente los límites
              pad_inches=0.2,            # Padding adicional para evitar recortes
              dpi=300,                   # High resolution
              facecolor='white',         # White background
              edgecolor='none',          # No edge color
              format='png')              # PNG format

