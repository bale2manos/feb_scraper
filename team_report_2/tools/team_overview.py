import os
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patches as patches
from utils import get_team_logo, setup_montserrat_font
from rebound_analysis import generate_team_rebound_analysis
import io
from PIL import Image
import pandas as pd

def plot_team_header(
    team_name: str,
    df_rebound_data: pd.DataFrame = None,  # Datos para el gráfico de rebotes
    logo_size: float = 0.08,  # Reducido de 0.15 a 0.08 para hacer el escudo más pequeño
    dpi: int = 100
) -> plt.Figure:
    """
    Dibuja un lienzo con el escudo de `team_name` en la esquina superior izquierda
    y su nombre justo debajo.

    Parámetros:
    - team_name: nombre del equipo, usado para buscar el logo con get_team_logo().
    - logo_size: tamaño relativo del logo (fracción del ancho de la figura).
    - dpi: resolución de la figura.

    Devuelve:
    - fig: objeto matplotlib.figure.Figure listo para seguir añadiendo elementos.
    """
    # 0) configuración de fuente
    setup_montserrat_font()

    # 1) carga del logo
    logo = get_team_logo(team_name)
    if logo is None:
        raise FileNotFoundError(f"No se encontró logo para el equipo '{team_name}'")

    # 2) crear figura y ejes - tamaño A4 horizontal (11.69 x 8.27 pulgadas)
    fig = plt.figure(figsize=(11.69, 8.27), dpi=dpi)
    ax = fig.add_subplot(111)
    ax.axis('off')  # sin ejes

    # 3) colocar logo en coordenadas de ejes (0,1) esquina superior izquierda
    #    OffsetImage escala en pixeles, así que calculamos zoom
    fig_width_px = fig.get_size_inches()[0] * dpi
    # Queremos que el logo mida logo_size*fig_width_px píxeles de ancho
    target_w_px = logo_size * fig_width_px
    zoom = target_w_px / logo.width

    im = OffsetImage(logo, zoom=zoom)
    ab = AnnotationBbox(
        im,
        (0.02, 0.98),           # posición en axes coords
        xycoords='axes fraction',
        box_alignment=(0,1),    # anclar la esquina superior izquierda
        frameon=False
    )
    ax.add_artist(ab)

    # 4) texto con el nombre del equipo justo debajo del escudo
    # Calculamos la posición Y del texto basándonos en la posición del escudo
    # El escudo está en (0.02, 0.98) y tiene una altura proporcional al zoom
    logo_height_px = logo.height * zoom
    fig_height_px = fig.get_size_inches()[1] * dpi
    logo_height_relative = logo_height_px / fig_height_px
    
    # Posicionamos el texto justo debajo del escudo con un pequeño espaciado
    text_y = 0.98 - logo_height_relative - 0.06  # 6% de espaciado debajo del escudo

    ax.text(
        0.02, text_y,            # Misma X que el escudo, Y calculada debajo del escudo
        team_name,
        transform=ax.transAxes,
        va='top', ha='left',     # Alineado desde arriba hacia abajo
        fontsize=14, weight='bold',
        color='#222222'
    )

    # 5) agregar gráfico de rebotes en la esquina inferior izquierda
    if df_rebound_data is not None:
        # Generar el gráfico de rebotes
        rebound_fig = generate_team_rebound_analysis(df_rebound_data)
        
        # Convertir el gráfico a imagen
        buf = io.BytesIO()
        rebound_fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', 
                            pad_inches=0.2, facecolor='white', edgecolor='none')
        plt.close(rebound_fig)  # Cerrar la figura para liberar memoria
        buf.seek(0)
        
        # Cargar la imagen desde el buffer
        rebound_img = Image.open(buf)
        
        # Calcular posición y tamaño para la esquina inferior izquierda
        # Posición: esquina inferior izquierda con margen
        rebound_x = 0.02  # Mismo margen que el logo
        rebound_y = 0.02  # Margen desde abajo
        
        # Calcular la altura máxima: desde abajo hasta el bottom del texto del equipo
        # text_y es la posición Y del texto, queremos llegar hasta ahí
        max_rebound_height = text_y - rebound_y - 0.02  # Pequeño margen entre texto y gráfico
        
        # Calcular el ancho del gráfico manteniendo proporción
        # Usar un ancho fijo de 40% de la figura
        rebound_width_fraction = 0.4  # 40% del ancho de la figura
        fig_width_px = fig.get_size_inches()[0] * dpi
        target_rebound_w_px = rebound_width_fraction * fig_width_px
        
        # Calcular zoom basado en el ancho deseado
        rebound_zoom_w = target_rebound_w_px / rebound_img.width
        
        # Calcular zoom basado en la altura máxima
        fig_height_px = fig.get_size_inches()[1] * dpi
        max_rebound_h_px = max_rebound_height * fig_height_px
        rebound_zoom_h = max_rebound_h_px / rebound_img.height
        
        # Usar el zoom menor para que quepa en ambas dimensiones
        rebound_zoom = min(rebound_zoom_w, rebound_zoom_h)
        
        # Añadir el gráfico como imagen
        rebound_offset_img = OffsetImage(rebound_img, zoom=rebound_zoom)
        rebound_ab = AnnotationBbox(
            rebound_offset_img,
            (rebound_x, rebound_y),  # posición en axes coords
            xycoords='axes fraction',
            box_alignment=(0, 0),    # anclar la esquina inferior izquierda
            frameon=False
        )
        ax.add_artist(rebound_ab)

    # 6) márgenes en blanco para seguir dibujando
    fig.tight_layout()
    return fig

# === Ejemplo de uso ===
if __name__ == "__main__":
    
    FILE = './data/teams_aggregated.xlsx'
    EQUIPO = "UROS DE RIVAS"
    df = pd.read_excel(FILE)
    df_filtrado = df[df['EQUIPO'] == EQUIPO]    
    fig = plot_team_header("UROS DE RIVAS", df_rebound_data=df_filtrado)
    fig.savefig("team_header_demo.png", dpi=150, bbox_inches='tight')
