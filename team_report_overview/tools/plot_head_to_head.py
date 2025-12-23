import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from PIL import Image
from .utils import setup_montserrat_font, get_team_logo, extract_logo_color, COLORS
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

def generate_head_to_head_comparison(
    df_main: pd.DataFrame,
    df_rival: pd.DataFrame,
    main_team_name: str,
    rival_team_name: str,
    main_color: str = None,
    rival_color: str = None
):
    """
    Genera un gráfico de comparación cara a cara entre dos equipos.
    
    Parámetros:
    - df_main: DataFrame con los datos del equipo principal (izquierda)
    - df_rival: DataFrame con los datos del equipo rival (derecha)
    - main_team_name: Nombre del equipo principal
    - rival_team_name: Nombre del equipo rival
    - main_color: Color para el equipo principal (hex/tuple). Si es None, extrae del logo
    - rival_color: Color para el equipo rival (hex/tuple). Si es None, extrae del logo
    """
    setup_montserrat_font()
    
    # Función auxiliar para normalizar nombre de equipo a path de logo
    def get_logo_path(team_name: str):
        fn = (team_name.lower()
                   .replace(' ', '_')
                   .replace('.', '')
                   .replace(',', '')
                   .replace('á', 'a')
                   .replace('é', 'e')
                   .replace('í', 'i')
                   .replace('ó', 'o')
                   .replace('ú', 'u')
                   .replace('ñ', 'n')
                   .replace('ü', 'u'))
        path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'images', 'clubs',
            f'{fn}.png'
        )
        return path if os.path.exists(path) else None
    
    # Extraer colores de los logos si no se especifican
    if main_color is None:
        logo_path = get_logo_path(main_team_name)
        if logo_path:
            main_color = extract_logo_color(logo_path)
            # Convertir numpy floats a floats normales
            main_color = tuple(float(c) for c in main_color)
        else:
            main_color = (0.18, 0.49, 0.20)  # Verde por defecto (RGB normalizado)
    
    if rival_color is None:
        logo_path = get_logo_path(rival_team_name)
        if logo_path:
            rival_color = extract_logo_color(logo_path)
            # Convertir numpy floats a floats normales
            rival_color = tuple(float(c) for c in rival_color)
        else:
            rival_color = (0.78, 0.16, 0.16)  # Rojo por defecto (RGB normalizado)
    
    # Agregar estadísticas por equipo
    print(f"\n[DEBUG H2H] 🔍 DataFrame df_main antes del groupby:")
    print(f"[DEBUG H2H]   Shape: {df_main.shape}")
    if 'EB FELIPE ANTÓN' in df_main['EQUIPO'].values:
        felipe_pre = df_main[df_main['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
        print(f"[DEBUG H2H]   EB FELIPE ANTÓN PRE-GROUPBY:")
        print(f"[DEBUG H2H]     T3 CONVERTIDO: {felipe_pre.get('T3 CONVERTIDO', 'N/A')}")
        print(f"[DEBUG H2H]     T3 INTENTADO: {felipe_pre.get('T3 INTENTADO', 'N/A')}")
        print(f"[DEBUG H2H]     %OREB: {felipe_pre.get('%OREB', 'N/A')}")
        print(f"[DEBUG H2H]     %REB: {felipe_pre.get('%REB', 'N/A')}")
    
    main_stats = df_main.groupby('EQUIPO').agg({
        'TL INTENTADOS': 'sum',
        'TL CONVERTIDOS': 'sum',
        'T2 INTENTADO': 'sum',
        'T2 CONVERTIDO': 'sum',
        'T3 INTENTADO': 'sum',
        'T3 CONVERTIDO': 'sum',
        'REB OFFENSIVO': 'sum',
        'REB DEFENSIVO': 'sum',
        '%OREB': 'mean',
        '%DREB': 'mean',
        'PERDIDAS': 'sum',
        'PUNTOS +': 'sum',
        'PUNTOS -': 'sum',
        'PJ': 'first'
    }).iloc[0]
    
    print(f"\n[DEBUG H2H] 🔍 main_stats DESPUÉS del groupby:")
    print(f"[DEBUG H2H]   T3 CONVERTIDO: {main_stats.get('T3 CONVERTIDO', 'N/A')}")
    print(f"[DEBUG H2H]   T3 INTENTADO: {main_stats.get('T3 INTENTADO', 'N/A')}")
    print(f"[DEBUG H2H]   T3%: {(main_stats['T3 CONVERTIDO'] / main_stats['T3 INTENTADO'] * 100) if main_stats['T3 INTENTADO'] > 0 else 0:.2f}%")
    print(f"[DEBUG H2H]   %OREB: {main_stats.get('%OREB', 'N/A')}")
    print(f"[DEBUG H2H]   %REB (si existe): {main_stats.get('%REB', 'N/A')}\n")
    
    rival_stats = df_rival.groupby('EQUIPO').agg({
        'TL INTENTADOS': 'sum',
        'TL CONVERTIDOS': 'sum',
        'T2 INTENTADO': 'sum',
        'T2 CONVERTIDO': 'sum',
        'T3 INTENTADO': 'sum',
        'T3 CONVERTIDO': 'sum',
        'REB OFFENSIVO': 'sum',
        'REB DEFENSIVO': 'sum',
        '%OREB': 'mean',
        '%DREB': 'mean',
        'PERDIDAS': 'sum',
        'PUNTOS +': 'sum',
        'PUNTOS -': 'sum',
        'PJ': 'first'
    }).iloc[0]
    
    # Calcular métricas
    metrics_data = []
    
    # % T1 (promedio intentos)
    main_t1_pct = (main_stats['TL CONVERTIDOS'] / main_stats['TL INTENTADOS'] * 100) if main_stats['TL INTENTADOS'] > 0 else 0
    rival_t1_pct = (rival_stats['TL CONVERTIDOS'] / rival_stats['TL INTENTADOS'] * 100) if rival_stats['TL INTENTADOS'] > 0 else 0
    main_t1_avg = main_stats['TL INTENTADOS'] / main_stats['PJ']
    rival_t1_avg = rival_stats['TL INTENTADOS'] / rival_stats['PJ']
    metrics_data.append({
        'label': '% T1',
        'main_value': main_t1_pct,
        'rival_value': rival_t1_pct,
        'main_extra': f"({main_t1_avg:.1f} intentos)",
        'rival_extra': f"({rival_t1_avg:.1f} intentos)"
    })
    
    # % T2 (promedio intentos)
    main_t2_pct = (main_stats['T2 CONVERTIDO'] / main_stats['T2 INTENTADO'] * 100) if main_stats['T2 INTENTADO'] > 0 else 0
    rival_t2_pct = (rival_stats['T2 CONVERTIDO'] / rival_stats['T2 INTENTADO'] * 100) if rival_stats['T2 INTENTADO'] > 0 else 0
    main_t2_avg = main_stats['T2 INTENTADO'] / main_stats['PJ']
    rival_t2_avg = rival_stats['T2 INTENTADO'] / rival_stats['PJ']
    metrics_data.append({
        'label': '% T2',
        'main_value': main_t2_pct,
        'rival_value': rival_t2_pct,
        'main_extra': f"({main_t2_avg:.1f} intentos)",
        'rival_extra': f"({rival_t2_avg:.1f} intentos)"
    })
    
    # % T3 (promedio intentos)
    main_t3_pct = (main_stats['T3 CONVERTIDO'] / main_stats['T3 INTENTADO'] * 100) if main_stats['T3 INTENTADO'] > 0 else 0
    rival_t3_pct = (rival_stats['T3 CONVERTIDO'] / rival_stats['T3 INTENTADO'] * 100) if rival_stats['T3 INTENTADO'] > 0 else 0
    main_t3_avg = main_stats['T3 INTENTADO'] / main_stats['PJ']
    rival_t3_avg = rival_stats['T3 INTENTADO'] / rival_stats['PJ']
    metrics_data.append({
        'label': '% T3',
        'main_value': main_t3_pct,
        'rival_value': rival_t3_pct,
        'main_extra': f"({main_t3_avg:.1f} intentos)",
        'rival_extra': f"({rival_t3_avg:.1f} intentos)"
    })
    
    # %OREB (promedio)
    main_oreb_avg = main_stats['REB OFFENSIVO'] / main_stats['PJ']
    rival_oreb_avg = rival_stats['REB OFFENSIVO'] / rival_stats['PJ']
    metrics_data.append({
        'label': '%OREB',
        'main_value': main_stats['%OREB'] * 100,
        'rival_value': rival_stats['%OREB'] * 100,
        'main_extra': f"({main_oreb_avg:.1f} rebotes)",
        'rival_extra': f"({rival_oreb_avg:.1f} rebotes)"
    })
    
    # %DREB (promedio)
    main_dreb_avg = main_stats['REB DEFENSIVO'] / main_stats['PJ']
    rival_dreb_avg = rival_stats['REB DEFENSIVO'] / rival_stats['PJ']
    metrics_data.append({
        'label': '%DREB',
        'main_value': main_stats['%DREB'] * 100,
        'rival_value': rival_stats['%DREB'] * 100,
        'main_extra': f"({main_dreb_avg:.1f} rebotes)",
        'rival_extra': f"({rival_dreb_avg:.1f} rebotes)"
    })
    
    # %TOV (promedio) - Las PERDIDAS son totales, dividir por PJ
    main_tov_avg = main_stats['PERDIDAS'] / main_stats['PJ']  # Dividir por PJ para obtener promedio
    rival_tov_avg = rival_stats['PERDIDAS'] / rival_stats['PJ']  # Dividir por PJ para obtener promedio
    
    # DEBUG - Pérdidas
    print(f"\n🔍 DEBUG %TOV - {main_team_name}:")
    print(f"  PERDIDAS totales: {main_stats['PERDIDAS']}")
    print(f"  PJ: {main_stats['PJ']}")
    print(f"  PERDIDAS/partido: {main_tov_avg:.2f}")
    print(f"  T2 intentados totales: {main_stats['T2 INTENTADO']}")
    print(f"  T3 intentados totales: {main_stats['T3 INTENTADO']}")
    print(f"  TL intentados totales: {main_stats['TL INTENTADOS']}")
    
    # Calcular %TOV (necesitamos posesiones aproximadas promediadas por partido)
    main_poss_per_game = (main_stats['T2 INTENTADO'] + main_stats['T3 INTENTADO'] + main_stats['TL INTENTADOS'] * 0.44) / main_stats['PJ'] + main_tov_avg
    rival_poss_per_game = (rival_stats['T2 INTENTADO'] + rival_stats['T3 INTENTADO'] + rival_stats['TL INTENTADOS'] * 0.44) / rival_stats['PJ'] + rival_tov_avg
    
    print(f"  Posesiones/partido: {main_poss_per_game:.2f}")
    
    main_tov_pct = (main_tov_avg / main_poss_per_game * 100) if main_poss_per_game > 0 else 0
    rival_tov_pct = (rival_tov_avg / rival_poss_per_game * 100) if rival_poss_per_game > 0 else 0
    
    print(f"  %TOV: {main_tov_pct:.2f}%")
    
    print(f"\n🔍 DEBUG %TOV - {rival_team_name}:")
    print(f"  PERDIDAS totales: {rival_stats['PERDIDAS']}")
    print(f"  PJ: {rival_stats['PJ']}")
    print(f"  PERDIDAS/partido: {rival_tov_avg:.2f}")
    print(f"  T2 intentados totales: {rival_stats['T2 INTENTADO']}")
    print(f"  T3 intentados totales: {rival_stats['T3 INTENTADO']}")
    print(f"  TL intentados totales: {rival_stats['TL INTENTADOS']}")
    print(f"  Posesiones/partido: {rival_poss_per_game:.2f}")
    print(f"  %TOV: {rival_tov_pct:.2f}%\n")
    
    metrics_data.append({
        'label': '%TOV',
        'main_value': main_tov_pct,
        'rival_value': rival_tov_pct,
        'main_extra': f"({main_tov_avg:.1f} pérdidas)",
        'rival_extra': f"({rival_tov_avg:.1f} pérdidas)"
    })
    
    # PUNTOS + / PJ
    main_pts_plus = main_stats['PUNTOS +'] / main_stats['PJ']
    rival_pts_plus = rival_stats['PUNTOS +'] / rival_stats['PJ']
    metrics_data.append({
        'label': 'PUNTOS + / PJ',
        'main_value': main_pts_plus,
        'rival_value': rival_pts_plus,
        'main_extra': "",
        'rival_extra': ""
    })
    
    # PUNTOS - / PJ
    main_pts_minus = main_stats['PUNTOS -'] / main_stats['PJ']
    rival_pts_minus = rival_stats['PUNTOS -'] / rival_stats['PJ']
    metrics_data.append({
        'label': 'PUNTOS - / PJ',
        'main_value': main_pts_minus,
        'rival_value': rival_pts_minus,
        'main_extra': "",
        'rival_extra': ""
    })
    
    # Crear figura
    n_metrics = len(metrics_data)
    fig_height = max(8, n_metrics * 0.8)
    fig = plt.figure(figsize=(12, fig_height))
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # Configurar límites - extendidos verticalmente para logos
    ax.set_xlim(-110, 110)
    ax.set_ylim(-1, n_metrics + 1.5)  # Espacio extra arriba para logos
    
    # Título
    ax.text(0, n_metrics + 1.2, 'CARA A CARA', 
            ha='center', va='center', fontsize=24, weight='bold', color='black')
    
    # Añadir logos de equipos - posicionados arriba, con tamaño fijo
    logo_size_px = 80  # Tamaño fijo en píxeles
    
    try:
        main_logo = get_team_logo(main_team_name)
        if main_logo:
            # Redimensionar a tamaño fijo manteniendo aspect ratio
            aspect_ratio = main_logo.width / main_logo.height
            if aspect_ratio > 1:
                # Ancho mayor que alto
                new_width = logo_size_px
                new_height = int(logo_size_px / aspect_ratio)
            else:
                # Alto mayor que ancho
                new_height = logo_size_px
                new_width = int(logo_size_px * aspect_ratio)
            
            main_logo_resized = main_logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
            im_main = OffsetImage(main_logo_resized, zoom=1.0)  # zoom=1 porque ya redimensionamos
            ab_main = AnnotationBbox(
                im_main,
                (-70, n_metrics + 1.2),  # Misma altura que el título pero a la izquierda
                xycoords='data',
                frameon=False
            )
            ax.add_artist(ab_main)
    except Exception as e:
        print(f"⚠️  Error cargando logo principal: {e}")
    
    try:
        rival_logo = get_team_logo(rival_team_name)
        if rival_logo:
            # Redimensionar a tamaño fijo manteniendo aspect ratio
            aspect_ratio = rival_logo.width / rival_logo.height
            if aspect_ratio > 1:
                # Ancho mayor que alto
                new_width = logo_size_px
                new_height = int(logo_size_px / aspect_ratio)
            else:
                # Alto mayor que ancho
                new_height = logo_size_px
                new_width = int(logo_size_px * aspect_ratio)
            
            rival_logo_resized = rival_logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
            im_rival = OffsetImage(rival_logo_resized, zoom=1.0)  # zoom=1 porque ya redimensionamos
            ab_rival = AnnotationBbox(
                im_rival,
                (70, n_metrics + 1.2),  # Misma altura que el título pero a la derecha
                xycoords='data',
                frameon=False
            )
            ax.add_artist(ab_rival)
    except Exception as e:
        print(f"⚠️  Error cargando logo rival: {e}")
    
    # Dibujar barras enfrentadas para cada métrica
    bar_height = 0.6
    
    for i, metric in enumerate(metrics_data):
        y_pos = n_metrics - i - 1
        
        # Normalizar valores para que las barras sean proporcionales
        max_val = max(metric['main_value'], metric['rival_value'])
        if max_val > 0:
            main_normalized = (metric['main_value'] / max_val) * 100
            rival_normalized = (metric['rival_value'] / max_val) * 100
        else:
            main_normalized = 0
            rival_normalized = 0
        
        # Barra izquierda (equipo principal) - va hacia la izquierda
        ax.barh(y_pos, -main_normalized, height=bar_height, 
                color=main_color, alpha=0.8, edgecolor='white', linewidth=2)
        
        # Barra derecha (equipo rival) - va hacia la derecha
        ax.barh(y_pos, rival_normalized, height=bar_height, 
                color=rival_color, alpha=0.8, edgecolor='white', linewidth=2)
        
        # Etiqueta de la métrica en el centro
        ax.text(0, y_pos, metric['label'], 
                ha='center', va='center', fontsize=14, weight='bold', 
                color='black', bbox=dict(boxstyle='round,pad=0.5', 
                facecolor='white', edgecolor='black', linewidth=1.5))
        
        # Texto del equipo principal (izquierda) - todo en una línea
        if metric['label'].startswith('%') or metric['label'] == '%TOV':
            value_text = f"{metric['main_value']:.1f}%"
        else:
            value_text = f"{metric['main_value']:.1f}"
        
        if metric['main_extra']:
            full_text = f"{value_text} {metric['main_extra']}"
        else:
            full_text = value_text
        
        ax.text(-main_normalized/2, y_pos, full_text, 
                ha='center', va='center', fontsize=14, weight='bold', color='white')
        
        # Texto del equipo rival (derecha) - todo en una línea
        if metric['label'].startswith('%') or metric['label'] == '%TOV':
            value_text = f"{metric['rival_value']:.1f}%"
        else:
            value_text = f"{metric['rival_value']:.1f}"
        
        if metric['rival_extra']:
            full_text = f"{value_text} {metric['rival_extra']}"
        else:
            full_text = value_text
        
        ax.text(rival_normalized/2, y_pos, full_text, 
                ha='center', va='center', fontsize=14, weight='bold', color='white')
    
    # Ajustar layout
    plt.tight_layout(pad=1.0)
    plt.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05)
    
    return fig


def add_head_to_head_to_axes(
    ax: plt.Axes,
    df_main: pd.DataFrame,
    df_rival: pd.DataFrame,
    main_team_name: str,
    rival_team_name: str,
    main_color: str = None,
    rival_color: str = None,
    position: tuple = (0.5, 0.5),
    size: tuple = (0.8, 0.8),
    dpi: int = 100
):
    """
    Añade el gráfico de comparación cara a cara a los ejes dados como una imagen incrustada.
    
    Parámetros:
    - ax: ejes de matplotlib donde añadir el gráfico
    - df_main: DataFrame con los datos del equipo principal
    - df_rival: DataFrame con los datos del equipo rival
    - main_team_name: Nombre del equipo principal
    - rival_team_name: Nombre del equipo rival
    - main_color: Color para el equipo principal (hex)
    - rival_color: Color para el equipo rival (hex)
    - position: (x, y) posición en coordenadas de fracción de ejes
    - size: (width, height) tamaño en coordenadas de fracción de ejes
    - dpi: resolución
    """
    import io
    from PIL import Image
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    
    # Generar el gráfico de comparación
    comparison_fig = generate_head_to_head_comparison(
        df_main, df_rival, main_team_name, rival_team_name, main_color, rival_color
    )
    
    # Convertir a imagen
    buf = io.BytesIO()
    comparison_fig.savefig(buf, format='png', dpi=150, bbox_inches=None,
                          pad_inches=0.0, facecolor='white', edgecolor='none')
    plt.close(comparison_fig)
    buf.seek(0)
    
    # Cargar imagen
    comparison_img = Image.open(buf)
    
    # Calcular zoom para ajustar al tamaño deseado
    fig = ax.get_figure()
    fig_width_px = fig.get_size_inches()[0] * dpi
    fig_height_px = fig.get_size_inches()[1] * dpi
    
    target_w_px = size[0] * fig_width_px
    target_h_px = size[1] * fig_height_px
    
    zoom_w = target_w_px / comparison_img.width
    zoom_h = target_h_px / comparison_img.height
    zoom = min(zoom_w, zoom_h)
    
    # Añadir como imagen incrustada
    comparison_offset_img = OffsetImage(comparison_img, zoom=zoom)
    comparison_ab = AnnotationBbox(
        comparison_offset_img,
        position,
        xycoords='axes fraction',
        box_alignment=(0.5, 0.5),
        frameon=False
    )
    ax.add_artist(comparison_ab)
    
    return comparison_ab


if __name__ == '__main__':
    # Ejemplo de uso
    import sys, os
    sys.path.append('../..')
    
    FILE = './data/3FEB_25_26/teams_25_26_3FEB.xlsx'
    MAIN_TEAM = "BALONCESTO TELDE"
    RIVAL_TEAM = "GRUPO EGIDO PINTOBASKET"
    
    print("Current working directory:", os.getcwd() )
    
    df = pd.read_excel(FILE)
    df_main = df[df['EQUIPO'] == MAIN_TEAM]
    df_rival = df[df['EQUIPO'] == RIVAL_TEAM]
    
    fig = generate_head_to_head_comparison(
        df_main, df_rival, MAIN_TEAM, RIVAL_TEAM
        # No especificamos colores para probar la extracción automática
    )
    
    fig.savefig('head_to_head_comparison.png', 
                bbox_inches='tight',
                pad_inches=0.2,
                dpi=300,
                facecolor='white',
                edgecolor='none',
                format='png')
    
    print(f"Comparación generada: {MAIN_TEAM} vs {RIVAL_TEAM}")
