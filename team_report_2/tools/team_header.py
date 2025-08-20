import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from utils import get_team_logo, setup_montserrat_font

def create_team_header(
    ax: plt.Axes,
    team_name: str,
    logo_size: float = 0.04,
    dpi: int = 180  # Usar mismo DPI que build_team_report.py
) -> tuple[float, float]:
    """
    Añade el encabezado del equipo (logo + nombre) a los ejes dados.
    
    Parámetros:
    - ax: ejes de matplotlib donde dibujar
    - team_name: nombre del equipo
    - logo_size: tamaño relativo del logo (fracción del ancho de la figura)
    - dpi: resolución de la figura
    
    Devuelve:
    - tuple: (text_y, text_bottom_y) - posiciones Y del texto para referencia
    """
    # Configuración de fuente
    setup_montserrat_font()

    # Cargar logo
    logo = get_team_logo(team_name)
    if logo is None:
        raise FileNotFoundError(f"No se encontró logo para el equipo '{team_name}'")

    # Calcular dimensiones
    fig = ax.get_figure()
    fig_width_px = fig.get_size_inches()[0] * dpi
    fig_height_px = fig.get_size_inches()[1] * dpi
    
    # Calcular zoom del logo
    target_w_px = logo_size * fig_width_px
    zoom = target_w_px / logo.width

    # Colocar logo en esquina superior izquierda
    im = OffsetImage(logo, zoom=zoom)
    ab = AnnotationBbox(
        im,
        (0.02, 0.98),           # posición en axes coords
        xycoords='axes fraction',
        box_alignment=(0, 1),    # anclar la esquina superior izquierda
        frameon=False
    )
    ax.add_artist(ab)

    # Calcular posición del texto debajo del logo
    logo_height_px = logo.height * zoom
    logo_height_relative = logo_height_px / fig_height_px
    
    # Posición Y del texto (parte superior) - más cerca del logo
    text_y = 0.98 - logo_height_relative - 0.1  # 2% de espaciado debajo del escudo (antes era 6%)
    
    # Añadir texto del nombre del equipo
    text_obj = ax.text(
        0.02, text_y,            # Misma X que el escudo, Y calculada debajo del escudo
        team_name,
        transform=ax.transAxes,
        va='top', ha='left',     # Alineado desde arriba hacia abajo
        fontsize=14, weight='bold',
        color='#222222'
    )
    
    # Calcular la posición inferior del texto para referencia
    # Estimamos la altura del texto (aproximadamente 0.03 en coordenadas de ejes)
    text_height_estimate = 0.03
    text_bottom_y = text_y - text_height_estimate
    
    return text_y, text_bottom_y

def plot_team_header_standalone(
    team_name: str,
    logo_size: float = 0.04,
    dpi: int = 180  # Usar mismo DPI que build_team_report.py
) -> plt.Figure:
    """
    Crea una figura standalone con solo el encabezado del equipo.
    
    Parámetros:
    - team_name: nombre del equipo
    - logo_size: tamaño relativo del logo
    - dpi: resolución de la figura
    
    Devuelve:
    - fig: figura de matplotlib
    """
    # Crear figura con proportions A4 landscape para consistencia con PDF
    fig = plt.figure(figsize=(11.69, 8.27), dpi=dpi)  # A4 landscape proportions
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # Añadir encabezado
    create_team_header(ax, team_name, logo_size, dpi)
    
    # Usar márgenes consistentes con el sistema PDF
    fig.subplots_adjust(left=0.025, right=0.975, top=0.975, bottom=0.025)
    return fig

# === Ejemplo de uso ===
if __name__ == "__main__":
    fig = plot_team_header_standalone("UROS DE RIVAS")
    fig.savefig("team_header_standalone.png", dpi=180, bbox_inches='tight')
