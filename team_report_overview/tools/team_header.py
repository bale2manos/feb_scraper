import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from utils import get_team_logo, setup_montserrat_font

def create_team_header(
    ax: plt.Axes,
    team_name: str,
    logo_size: float = 0.04,
    dpi: int = 180
) -> None:
    """
    Añade solo el logo del equipo a los ejes dados.

    Parámetros:
    - ax: ejes de matplotlib donde dibujar
    - team_name: nombre del equipo
    - logo_size: tamaño relativo del logo (fracción del ancho de la figura)
    - dpi: resolución de la figura
    No devuelve nada.
    """
    setup_montserrat_font()

    logo = get_team_logo(team_name)
    if logo is None:
        raise FileNotFoundError(f"No se encontró logo para el equipo '{team_name}'")

    fig = ax.get_figure()
    fig_width_px = fig.get_size_inches()[0] * dpi

    target_w_px = logo_size * fig_width_px
    zoom = target_w_px / logo.width

    im = OffsetImage(logo, zoom=zoom)
    ab = AnnotationBbox(
        im,
        (0.02, 0.98),
        xycoords='axes fraction',
        box_alignment=(0, 1),
        frameon=False
    )
    ax.add_artist(ab)

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
