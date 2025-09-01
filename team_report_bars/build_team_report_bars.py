import matplotlib.pyplot as plt
from PIL import Image
import io

import pandas as pd
# Cambia los imports relativos por absolutos para ejecución directa
from .tools.distribucion_puntos_plot import plot_distribucion_puntos
from .tools.finalizacion_plays_plot import plot_finalizacion_plays
from .tools.media_lanzamientos_plot import plot_media_pct


def compute_advanced_stats_bars(stats_base):
    """
    Compute advanced basketball statistics from base stats.
    
    Args:
        stats_base: pandas Series with base statistics
        
    Returns:
        dict: Dictionary with all computed advanced statistics
    """
    
    # Create a copy to work with
    stats = stats_base.copy()

    # Shooting stats
    T1C = stats.get('TL CONVERTIDOS', 0)        # Free throws made
    T1I = stats.get('TL INTENTADOS', 0)         # Free throws attempted
    T2C = stats.get('T2 CONVERTIDO', 0)         # 2-point field goals made
    T2I = stats.get('T2 INTENTADO', 0)          # 2-point field goals attempted
    T3C = stats.get('T3 CONVERTIDO', 0)         # 3-point field goals made
    T3I = stats.get('T3 INTENTADO', 0)          # 3-point field goals attempted
    
    TOV = stats.get('PERDIDAS', 0)               # Turnovers
    Plays = T1I * 0.44 + T2I + T3I + TOV

    # --- BASIC CALCULATED STATS ---
    result = {}
    
    # Adapt
    result['T1C'] = T1C
    result['T2C'] = T2C
    result['T3C'] = T3C

    # Play distribution percentages
    result['F1 Plays%'] = (T1I * 0.44 / Plays * 100) if Plays > 0 else 0
    result['F2 Plays%'] = (T2I / Plays * 100) if Plays > 0 else 0
    result['F3 Plays%'] = (T3I / Plays * 100) if Plays > 0 else 0
    result['TO Plays%'] = (TOV / Plays * 100) if Plays > 0 else 0

    # Individual shooting percentages
    result['T1 %'] = (T1C / T1I * 100) if T1I > 0 else 0
    result['T2 %'] = (T2C / T2I * 100) if T2I > 0 else 0
    result['T3 %'] = (T3C / T3I * 100) if T3I > 0 else 0
    
    # Round all percentage values to 2 decimal places
    for key, value in result.items():
        if isinstance(value, (int, float)) and not pd.isna(value):
            if '%' in str(key) or key in ['PPP', 'PPT1', 'PPT2', 'PPT3', 'eFG', 'TS', 'PS', 'OE']:
                result[key] = round(float(value), 2)
            else:
                result[key] = round(float(value), 1)
    
    return result


def build_team_report_bars(stats_puntos: dict, stats_finalizacion: dict, dpi: int = 180) -> plt.Figure:
    """
    Genera un lienzo A4 horizontal con la barra de distribución de puntos arriba
    y la barra de finalización plays debajo, sin márgenes extra y respetando el diseño original.
    """
    # Crear figura A4 horizontal igual que build_team_report_overview
    fig = plt.figure(figsize=(11.69, 8.27), dpi=dpi)
    ax = fig.add_subplot(111)
    ax.axis('off')

    # Ajustar layout con márgenes consistentes con PDF
    fig.subplots_adjust(left=0.025, right=0.975, top=0.975, bottom=0.025)

    # Generar imágenes PIL de las barras con ancho 75% del lienzo
    bar_width_px = int(1490 * 0.75)
    img_puntos = plot_distribucion_puntos(stats_puntos, width_px=bar_width_px, height_px=260, resize_px=260)
    img_finalizacion = plot_finalizacion_plays(stats_finalizacion, width_px=bar_width_px, height_px=260, resize_px=260)

    # Añadir barra de medias lanzamientos debajo de finalización plays
    # Queremos que ocupe todo el ancho del lienzo y el hueco vertical disponible
    stats_media = {k: stats_finalizacion[k] for k in ["T1 %", "T2 %", "T3 %"] if k in stats_finalizacion}

    import numpy as np
    img_puntos_np = np.array(img_puntos)
    img_finalizacion_np = np.array(img_finalizacion)

    # Calcular el tamaño del lienzo en píxeles
    fig_w_px = int(fig.get_figwidth() * dpi)
    fig_h_px = int(fig.get_figheight() * dpi)
    print(f"[DEBUG] Tamaño lienzo: {fig_w_px}x{fig_h_px} px")

    # Definir zoom_factor antes de usarlo
    zoom_factor = bar_width_px / 1800

    # Calcular la posición y tamaño de la barra de finalización
    # La barra de finalización está centrada en y=0.67, zoom_factor*img_finalizacion_np.shape[0] es la altura
    barra_final_y_top = 0.67
    barra_final_h_frac = (img_finalizacion_np.shape[0] * zoom_factor) / fig_h_px
    barra_final_y_bottom = barra_final_y_top - barra_final_h_frac
    print(f"[DEBUG] Barra finalización: y_top={barra_final_y_top}, y_bottom={barra_final_y_bottom}, h_frac={barra_final_h_frac}")

    # Generar imagen de media lanzamientos con el tamaño fijo que se pase como parámetro
    media_w_px = 700
    media_h_px = 500
    img_media = plot_media_pct(stats_media, width_px=media_w_px, height_px=media_h_px)
    print(f"[DEBUG] Imagen media lanzamientos: {img_media.size}")

    # Insertar imágenes usando OffsetImage y AnnotationBbox para controlar tamaño y posición
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox

    # Barra de puntos: parte superior, ocupa 75% del ancho y centrada
    zoom_factor = bar_width_px / 1800
    offset_img_puntos = OffsetImage(img_puntos_np, zoom=zoom_factor)
    ab_puntos = AnnotationBbox(offset_img_puntos, (0.5, 0.99), xycoords='axes fraction', box_alignment=(0.5,1), frameon=False, pad=0)
    ax.add_artist(ab_puntos)

    # Barra de finalización: debajo, ocupa 75% del ancho y centrada
    offset_img_finalizacion = OffsetImage(img_finalizacion_np, zoom=zoom_factor)
    ab_finalizacion = AnnotationBbox(offset_img_finalizacion, (0.5, 0.67), xycoords='axes fraction', box_alignment=(0.5,1), frameon=False, pad=0)
    ax.add_artist(ab_finalizacion)

    # Barra de medias lanzamientos: ocupa el tamaño exacto, alineada al centro y pegada al borde inferior
    img_media_np = np.array(img_media)
    offset_img_media = OffsetImage(img_media_np, zoom=1)
    ab_media = AnnotationBbox(
        offset_img_media,
        (0.5, 0.6),  # centro horizontal, borde inferior
        xycoords='axes fraction',
        box_alignment=(0.5, 1),  # centro-abajo (base de la imagen en el borde)
        frameon=False,
        pad=0
    )
    ax.add_artist(ab_media)

    # Añadir título encima de la imagen de medias lanzamientos
    ax.text(
        0.5, 0.3,  # justo encima de la imagen insertada
        '% ACIERTO',
        fontsize=18,
        fontweight='bold',
        color='black',
        ha='center',
        va='bottom',
        transform=ax.transAxes
    )

    return fig

# === Ejemplo de uso ===

def main():
    """
    Función principal para testing del módulo.
    """
    FILE = './data/teams_aggregated.xlsx'
    EQUIPO = "C.B. TRES CANTOS"
    try:
        import pandas as pd
        df = pd.read_excel(FILE)
        df_filtrado = df[df['EQUIPO'] == EQUIPO]
        if df_filtrado.empty:
            print(f"No se encontraron datos para el equipo: {EQUIPO}")
            return

        # Calcular estadísticas avanzadas por jugador (aplicar row-wise)
        stats_advanced = df_filtrado.apply(compute_advanced_stats_bars, axis=1)
        stats_df = pd.DataFrame(stats_advanced.tolist())

        # Distribución de puntos (sumar por tipo, usar solo el número de tiros convertidos)
        stats_puntos = {
            "T1C": int(stats_df['T1C'].sum()),
            "T2C": int(stats_df['T2C'].sum()),
            "T3C": int(stats_df['T3C'].sum())
        }
        # Finalización plays (media por tipo)
        stats_finalizacion = {
            "T1 %": float(stats_df['F1 Plays%'].mean()),
            "T2 %": float(stats_df['F2 Plays%'].mean()),
            "T3 %": float(stats_df['F3 Plays%'].mean()),
            "PP %": float(stats_df['TO Plays%'].mean())
        }

        fig = build_team_report_bars(
            stats_puntos=stats_puntos,
            stats_finalizacion=stats_finalizacion,
            dpi=180
        )
        fig.savefig("team_report_bars.png", dpi=180)
        print("Reporte de barras guardado como team_report_bars.png")
    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo de datos. {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
