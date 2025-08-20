import matplotlib.pyplot as plt
import pandas as pd
import sys
import os
import io
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image


# Añadir la carpeta tools al path para importar los módulos
tools_path = os.path.join(os.path.dirname(__file__), 'tools')
sys.path.insert(0, tools_path)

from team_header import create_team_header
from rebound_analysis import add_rebound_analysis_to_axes
from plot_big_numbers import add_big_numbers_to_axes
from plot_top_scorers import plot_top_scorers
from plot_top_minutes import plot_top_minutes
from plot_top_assists import plot_top_assists
from plot_top_shooter import plot_top_shooter

def build_team_report_overview(
    team_name: str,
    df_rebound_data: pd.DataFrame,
    output_path: str = None,
    dpi: int = 180  # Usar mismo DPI que build_team_report.py para consistencia
) -> plt.Figure:
    """
    Genera el reporte overview del equipo con header y análisis de rebotes.
    
    Parámetros:
    - team_name: nombre del equipo
    - df_rebound_data: DataFrame con datos de rebotes del equipo
    - output_path: ruta donde guardar la imagen (opcional)
    - dpi: resolución de la figura
    
    Devuelve:
    - fig: figura de matplotlib
    """
    
    # Crear figura con proportions A4 landscape para consistencia con PDF
    fig = plt.figure(figsize=(11.69, 8.27), dpi=dpi)  # A4 landscape proportions
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # 1. Añadir encabezado del equipo (logo + nombre)
    text_y, text_bottom_y = create_team_header(ax, team_name, dpi=dpi)
    
    # 2. Ajustar layout con márgenes consistentes con PDF ANTES de añadir más elementos
    fig.subplots_adjust(left=0.025, right=0.975, top=0.975, bottom=0.025)

    
    # 3b. Añadir máximos anotadores en la esquina superior derecha
    df_jugadores = pd.read_excel('./data/jugadores_aggregated.xlsx')
    
    # Fijar tamaño constante para las figuras de los módulos de jugadores
    fixed_figsize = (4, 3.5)
    top_minutes_fig = plot_top_minutes(df_jugadores, team_name, figsize=fixed_figsize)
    buf = io.BytesIO()
    top_minutes_fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.0)
    plt.close(top_minutes_fig)
    buf.seek(0)
    img_top = Image.open(buf)
    # Posición y tamaño en la esquina superior derecha
    offset_img = OffsetImage(img_top, zoom=0.4)
    ab = AnnotationBbox(offset_img, (0.68, 0.99), xycoords='axes fraction', box_alignment=(1,1), frameon=False)
    ax.add_artist(ab)
    
    # Fijar tamaño constante para las figuras de los módulos de jugadores
    fixed_figsize = (4, 3.5)
    top_scorers_fig = plot_top_scorers(df_jugadores, team_name, figsize=fixed_figsize)
    buf = io.BytesIO()
    top_scorers_fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.0)
    plt.close(top_scorers_fig)
    buf.seek(0)
    img_top = Image.open(buf)
    # Posición y tamaño en la esquina superior derecha
    offset_img = OffsetImage(img_top, zoom=0.4)
    ab = AnnotationBbox(offset_img, (1.02, 0.99), xycoords='axes fraction', box_alignment=(1,1), frameon=False)
    ax.add_artist(ab)
    
    # 4. Añadir análisis de rebotes en el extremo inferior derecho
    # Posición X: extremo derecho con margen más conservador
    rebound_width = 0.18   # Más estrecho: reducido de 25% a 18% del ancho de la figura
    rebound_x = -rebound_width+0.13  # Más margen desde el borde derecho
    
    # Posición Y: extremo inferior con altura más grande (más largo)
    rebound_height = 0.41   # Más largo: aumentado de 1 a 1.3 de la altura del lienzo
    rebound_y = -0.3      # Ajustar posición Y para acomodar mayor altura
    
    # Añadir el gráfico de rebotes
    add_rebound_analysis_to_axes(
        ax=ax,
        df=df_rebound_data,
        position=(rebound_x, rebound_y),
        size=(rebound_width, rebound_height),
        dpi=dpi
    )

        
    # 5. Añadir números grandes en el centro
    add_big_numbers_to_axes(
        ax=ax,
        df=df_rebound_data,
        position=(0.26, 0.5),  # Centro del canvas
        fontsize_number=32,   # Aumentado de 28 a 36 para mayor prominencia
        fontsize_label=14,    # También aumentado ligeramente de 12 a 14
        line_spacing=0.12     # Aumentado el espaciado para acomodar el texto más grande
    )
    

    # 6. Guardar si se especifica una ruta
    if output_path:
        fig.savefig(
            output_path,
            dpi=dpi,
            bbox_inches=None,  # Mantener dimensiones exactas del canvas
            pad_inches=0.0,    # Sin padding adicional
            facecolor='white',
            edgecolor='none',
            format='png'
        )
        print(f"Reporte guardado en: {output_path}")
    
    return fig

def main():
    """
    Función principal para testing del módulo.
    """
    # Datos de ejemplo
    FILE = './data/teams_aggregated.xlsx'  # Ruta relativa al directorio padre
    EQUIPO = "C.B. TRES CANTOS"
    
    try:
        # Cargar datos
        df = pd.read_excel(FILE)
        df_filtrado = df[df['EQUIPO'] == EQUIPO]
        
        if df_filtrado.empty:
            print(f"No se encontraron datos para el equipo: {EQUIPO}")
            return
        
        # Generar reporte
        fig = build_team_report_overview(
            team_name=EQUIPO,
            df_rebound_data=df_filtrado,
            output_path="team_report_overview.png",
            dpi=180  # Usar mismo DPI para consistencia
        )

        
    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo de datos. {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
