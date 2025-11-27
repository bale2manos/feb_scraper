def get_team_crest_path(team_name):
    import re
    from pathlib import Path
    norm = re.sub(r'[^a-z0-9]+', '_', team_name.lower()).strip('_')
    crest_dir = Path(__file__).parent.parent / 'images' / 'clubs'
    crest_path = crest_dir / f'{norm}.png'
    if crest_path.exists():
        return str(crest_path)
    print(f"INFO: No se encontró escudo para '{team_name}'. Path buscado: {crest_path}")
    generic_path = crest_dir / 'generic_club.png'
    if generic_path.exists():
        return str(generic_path)
    return None
# presentation.py
# MÓDULO 4 — Presentación textual del análisis

import io
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def format_pct(x):
    return f"{100*x:.1f}%"


def format_name_full(name: str) -> str:
    """Convertir nombres con formato 'APELLIDO1 APELLIDO2, NOMBRE' a 'Nombre Apellido1 Apellido2'."""
    try:
        if ',' in name:
            apellidos, nombre = name.split(',', 1)
            apellidos = apellidos.strip()
            nombre = nombre.strip()
            return f"{nombre.title()} {apellidos.title()}"
        else:
            return name.title()
    except Exception:
        return name


def generate_text_report(analysis: dict) -> str:
    """
    Recibe el output completo del MÓDULO 3 (stats_engine.analyze_game)
    y devuelve un informe textual listo para imprimir o guardar.
    """

    L = analysis["four_factors"]["local"]
    V = analysis["four_factors"]["visitor"]
    D = analysis["four_factors"]["deltas"]

    NP = analysis["net_points"]
    mixL = analysis["mix"]["local"]
    mixV = analysis["mix"]["visitor"]

    score_local = analysis["score"]["local"]
    score_visit = analysis["score"]["visitor"]
    
    # Obtener nombres de equipos
    team_local = analysis.get("team_names", {}).get("local", "Local")
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")

    alerts = analysis["alerts"]
    players = analysis["players_analysis"]

    status = analysis["status"] or "—"

    # ============================================================
    # 1. ENCABEZADO
    # ============================================================
    report = []
    report.append("====================================")
    report.append("      📊 INFORME DEL PARTIDO")
    report.append("====================================")
    report.append(f"Estado del partido: {status}")
    report.append(f"Marcador: {team_local} {score_local} — {score_visit} {team_visit}")
    report.append("")

    # ============================================================
    # 2. FOUR FACTORS
    # ============================================================
    report.append("────────── FOUR FACTORS ──────────")
    report.append("Ofensivos / Defensivos")

    report.append(f"eFG%:     L {format_pct(L['eFG'])}   |   V {format_pct(V['eFG'])}   (Δ {format_pct(D['ΔeFG'])})")
    report.append(f"TOV%:     L {format_pct(L['TOV%'])}   |   V {format_pct(V['TOV%'])}   (Δ {format_pct(D['ΔTOV'])})")
    report.append(f"ORB%:     L {format_pct(L['ORB%'])}   |   V {format_pct(V['ORB%'])}   (Δ {format_pct(D['ΔORB'])})")
    report.append(f"FTr:      L {format_pct(L['FTr'])}    |   V {format_pct(V['FTr'])}    (Δ {format_pct(D['ΔFTr'])})")
    report.append("")

    # ============================================================
    # 3. NET POINTS (aportación por factor)
    # ============================================================
    report.append("────────── NET POINTS (Dean Oliver) ──────────")
    report.append(f"eFG:   {NP['NP_eFG']:+.2f} pts")
    report.append(f"TOV:   {NP['NP_TOV']:+.2f} pts")
    report.append(f"ORB:   {NP['NP_ORB']:+.2f} pts")
    report.append(f"FT:    {NP['NP_FT']:+.2f} pts")
    report.append("--------------------------------------")
    report.append(f"TOTAL: {NP['NP_total']:+.2f} pts explicados")
    report.append("")

    # ============================================================
    # 4. MIX DE FINALIZACIÓN
    # ============================================================
    report.append("────────── MIX DE FINALIZACIÓN ──────────")
    report.append(f"{team_local}:")
    report.append(f"  SC={mixL['SC']:.1f} | 2PA {format_pct(mixL['share_2PA'])}  | 3PA {format_pct(mixL['share_3PA'])}  | TO {format_pct(mixL['share_TO'])}  | FT {format_pct(mixL['share_FT'])}")
    report.append(f"{team_visit}:")
    report.append(f"  SC={mixV['SC']:.1f} | 2PA {format_pct(mixV['share_2PA'])}  | 3PA {format_pct(mixV['share_3PA'])}  | TO {format_pct(mixV['share_TO'])}  | FT {format_pct(mixV['share_FT'])}")
    report.append("")

    # ============================================================
    # 5. ALERTAS TÁCTICAS (RESUMEN PARA EL MÍSTER)
    # ============================================================
    report.append("────────── ALERTAS TÁCTICAS ──────────")
    if alerts:
        for a in alerts:
            report.append(f"• {a}")
    else:
        report.append("No hay alertas críticas.")
    report.append("")

    # ============================================================
    # 6. JUGADORES CALIENTES / FRÍOS
    # ============================================================
    report.append("────────── JUGADORES DESTACADOS ──────────")

    hot_loc = players["local_hot"]
    cold_loc = players["local_cold"]
    hot_vis = players["visitor_hot"]
    cold_vis = players["visitor_cold"]

    if hot_loc:
        report.append(f"🔥 {team_local} en racha:")
        for h in hot_loc:
            report.append(f"  - {h['name']} (TS {format_pct(h['TS'])}, volumen {h['vol']:.1f})")

    if cold_loc:
        report.append(f"❄ {team_local} con baja eficiencia:")
        for c in cold_loc:
            report.append(f"  - {c['name']} (TS {format_pct(c['TS'])}, volumen {c['vol']:.1f})")

    if hot_vis:
        report.append("🔥 Rivales en racha:")
        for h in hot_vis:
            report.append(f"  - {h['name']} (TS {format_pct(h['TS'])}, vol {h['vol']:.1f})")

    if cold_vis:
        report.append("❄ Rivales con baja eficiencia:")
        for c in cold_vis:
            report.append(f"  - {c['name']} (TS {format_pct(c['TS'])}, vol {c['vol']:.1f})")

    # ============================================================
    # 7. MALOS TIRADORES DEL RIVAL
    # ============================================================
    report.append("────────── MALOS TIRADORES (RIVAL) ──────────")

    poor = analysis.get("poor_ft_shooters", [])
    if not poor:
        report.append("No hay jugadores indicados especialmente.")
    else:
        for p in poor:
            if p["FT_today"] is None:
                today_txt = "—"
            else:
                today_txt = f"{p['FT_today']*100:.1f}%"

            formatted_name = format_name_full(p['name'])

            report.append(
                f"• {p['dorsal']} - {formatted_name} "
                f"(FT comb {p['FT_final']*100:.1f}%, "
                f"hoy {today_txt}, "
                f"hist {p['FT_hist']*100:.1f}%)"
            )

    report.append("")


    report.append("")
    report.append("====================================")
    report.append("     FIN DEL INFORME EN VIVO")
    report.append("====================================")

    return "\n".join(report)


# ============================================================
# FUNCIONES AUXILIARES PARA PDF
# ============================================================

def setup_montserrat_font():
    """Register Montserrat fonts for matplotlib."""
    font_dir = Path(__file__).parent.parent / "fonts"
    try:
        from matplotlib import font_manager
        font_files = [
            "Montserrat-Regular.ttf",
            "Montserrat-Bold.ttf",
            "Montserrat-Medium.ttf",
            "Montserrat-SemiBold.ttf",
        ]
        for font_file in font_files:
            font_path = font_dir / font_file
            if font_path.exists():
                font_manager.fontManager.addfont(str(font_path))
        plt.rcParams['font.family'] = 'Montserrat'
    except Exception as e:
        print(f"[WARNING] No se pudo cargar Montserrat para matplotlib: {e}")


def setup_montserrat_pdf_fonts():
    """Register Montserrat fonts for ReportLab PDF generation."""
    font_dir = Path(__file__).parent.parent / "fonts"
    
    fonts_to_register = [
        ("Montserrat-Regular", "Montserrat-Regular.ttf"),
        ("Montserrat-Bold", "Montserrat-Bold.ttf"),
        ("Montserrat-Medium", "Montserrat-Medium.ttf"),
        ("Montserrat-SemiBold", "Montserrat-SemiBold.ttf"),
    ]
    
    for font_name, font_file in fonts_to_register:
        font_path = font_dir / font_file
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            except Exception as e:
                print(f"[WARNING] No se pudo registrar {font_name}: {e}")


def fig_to_png_buffer(fig, dpi=180):
    """Convert matplotlib figure to optimized PNG buffer."""
    fig.set_tight_layout(True)
    FigureCanvas(fig).draw()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                transparent=False, facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def optimize_png_buffer(buf, max_width=1400):
    """Optimize PNG image buffer while maintaining quality."""
    buf.seek(0)
    img = Image.open(buf)
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    optimized_buf = io.BytesIO()
    img.save(optimized_buf, format='PNG', optimize=True, compress_level=6)
    optimized_buf.seek(0)
    return optimized_buf


# ============================================================
# VISUALIZACIONES PARA CADA PÁGINA DEL PDF
# ============================================================

def plot_malos_tiradores_page(analysis: dict) -> plt.Figure:
    """
    Página visual dedicada a los malos tiradores de tiros libres del rival.
    Combina FT de hoy + histórico.
    """
    setup_montserrat_font()

    poor = analysis.get("poor_ft_shooters", [])
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")

    fig = plt.figure(figsize=(16, 10), facecolor='white')
    ax = fig.add_subplot(111)
    ax.axis('off')

    if not poor:
        # Sin jugadores
        fig.text(
            0.5, 0.50,
            "No hay jugadores indicados especialmente.",
            ha='center', va='center',
            fontsize=22, fontweight='bold',
            color='#27ae60',
            bbox=dict(boxstyle='round,pad=1.3', facecolor='#d5f4e6', edgecolor='#27ae60', linewidth=3)
        )
        return fig

    # Configuración de layout
    y_start = 0.90
    y_step = 0.12
    badge_color = '#e74c3c'

    for i, p in enumerate(poor):
        y = y_start - i * y_step

        # Caja fondo
        rect = mpatches.FancyBboxPatch(
            (0.08, y - 0.06), 0.84, 0.08,
            transform=fig.transFigure,
            boxstyle="round,pad=0.02",
            facecolor='#fdecea',
            edgecolor='#e74c3c',
            linewidth=2
        )
        fig.patches.append(rect)

        # Texto principal
        formatted_name = format_name_full(p['name'])
        fig.text(
            0.10, y,
            f"{p['dorsal']} - {formatted_name}",
            ha='left', va='center',
            fontsize=17, fontweight='bold', color='#e74c3c'
        )

        # Datos FT combinados
        if p["FT_today"] is None:
            today_val = "—"
        else:
            today_val = f"{p['FT_today']*100:.1f}%"

        info = (
            f"% combinado {p['FT_final']*100:.1f}%   |   "
            f"Hoy {today_val} ({p['att_today']} TLI)   |   "
            f"Histórico {p['FT_hist']*100:.1f}% ({p['att_hist']} TLI)"
        )


        fig.text(
            0.10, y - 0.035,
            info,
            fontsize=13, color='#222222', ha='left', va='center'
        )

    return fig


def plot_four_factors_page(analysis: dict) -> plt.Figure:
    """
    Genera un gráfico de Four Factors con barras comparativas entre Local y Visitante.
    """
    setup_montserrat_font()
    
    L = analysis["four_factors"]["local"]
    V = analysis["four_factors"]["visitor"]
    D = analysis["four_factors"]["deltas"]
    
    fig = plt.figure(figsize=(16, 10), facecolor='white')
    
    # Preparar datos primero
    score_local = analysis["score"]["local"]
    score_visit = analysis["score"]["visitor"]
    team_local = analysis.get("team_names", {}).get("local", "Local")
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")
    
    factors = ['eFG%', 'TOV%', 'ORB%', 'FTr']
    local_vals = [L['eFG']*100, L['TOV%']*100, L['ORB%']*100, L['FTr']*100]
    visit_vals = [V['eFG']*100, V['TOV%']*100, V['ORB%']*100, V['FTr']*100]
    deltas = [D['ΔeFG']*100, D['ΔTOV']*100, D['ΔORB']*100, D['ΔFTr']*100]
    
    # Net Points
    NP = analysis["net_points"]
    np_vals = [NP['NP_eFG'], NP['NP_TOV'], NP['NP_ORB'], NP['NP_FT']]
    
    # Crear 4 subplots (uno por factor)
    for i, factor in enumerate(factors):
        ax = fig.add_subplot(2, 2, i+1)
        
        # Barras horizontales comparativas
        y_pos = [0, 1]
        values = [local_vals[i], visit_vals[i]]
        colors = ['#3498db', '#e74c3c']
        
        bars = ax.barh(y_pos, values, color=colors, alpha=0.8, height=0.5)
        
        # Añadir valores en las barras
        for j, (bar, val) in enumerate(zip(bars, values)):
            ax.text(val + 1, j, f'{val:.1f}%', 
                   va='center', fontsize=14, fontweight='bold')
        
        # Título del factor
        ax.text(0.5, 1.15, factor, transform=ax.transAxes,
               ha='center', va='top', fontsize=18, fontweight='bold',
               color='#222222')
        
        # Delta y Net Points
        delta_text = f'Δ {deltas[i]:+.1f}%'
        np_text = f'NP: {np_vals[i]:+.1f} pts'
        ax.text(0.5, -0.25, f'{delta_text}  |  {np_text}', 
               transform=ax.transAxes,
               ha='center', va='top', fontsize=13, color='#666666',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#f0f0f0', alpha=0.8))
        
        ax.set_yticks(y_pos)
        # Usar wrap para nombres largos (máximo 20 caracteres por línea)
        # Mostrar escudo en vez de nombre del equipo, en tamaño reducido
        from matplotlib.offsetbox import OffsetImage, AnnotationBbox
        from PIL import Image
        crest_local_path = get_team_crest_path(team_local)
        crest_visit_path = get_team_crest_path(team_visit)
        crest_size = 32  # px, reducido para no afectar el layout
        # Limpiar etiquetas
        ax.set_yticklabels(['', ''])
        crest_paths = [
            (team_local, crest_local_path),
            (team_visit, crest_visit_path)
        ]
        for idx, (team_name, crest_path) in enumerate(crest_paths):
            if crest_path:
                try:
                    img = Image.open(crest_path)
                    img = img.resize((crest_size, crest_size), Image.LANCZOS)
                    imagebox = OffsetImage(img, zoom=1, resample=True)
                    ab = AnnotationBbox(imagebox, (0, idx), frameon=False, box_alignment=(0.5,0.5), xycoords='data')
                    ax.add_artist(ab)
                except Exception as e:
                    print(f"INFO: No se pudo cargar el escudo para '{team_name}' en '{crest_path}' (error: {e})")
            else:
                # Si no se encuentra el escudo, mostrar INFO con el path intentado
                norm = team_name.lower().replace(' ', '_')
                crest_dir = Path(__file__).parent.parent / 'images' / 'clubs'
                attempted_path = crest_dir / f'{norm}.png'
                print(f"INFO: No se encontró escudo para '{team_name}'. Path buscado: {attempted_path}")
        ax.set_xlabel('Porcentaje (%)', fontsize=11)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Sin títulos en el gráfico - se añadirán en el PDF
    plt.tight_layout()
    
    return fig


def plot_net_points_page(analysis: dict) -> plt.Figure:
    """
    Genera un gráfico visual de Net Points (Dean Oliver) mostrando la contribución
    de cada factor al diferencial de puntos.
    """
    setup_montserrat_font()
    
    NP = analysis["net_points"]
    
    fig = plt.figure(figsize=(16, 10), facecolor='white')
    
    # Preparar datos
    factors = ['eFG%', 'TOV%', 'ORB%', 'FT']
    np_vals = [NP['NP_eFG'], NP['NP_TOV'], NP['NP_ORB'], NP['NP_FT']]
    total = NP['NP_total']
    
    # Colores según si es positivo o negativo
    colors = ['#27ae60' if val > 0 else '#e74c3c' for val in np_vals]
    
    # Crear gráfico principal de barras horizontales
    ax_main = fig.add_subplot(2, 1, 1)
    
    y_pos = range(len(factors))
    bars = ax_main.barh(y_pos, np_vals, color=colors, alpha=0.85, height=0.6)
    
    # Añadir valores en las barras
    for i, (bar, val) in enumerate(zip(bars, np_vals)):
        if abs(val) > 6:
            # Texto dentro de la barra
            x_pos = val / 2
            ax_main.text(x_pos, i, f'{val:+.2f} pts',
                         va='center', ha='center', fontsize=16, fontweight='bold',
                         color='white')
        else:
            # Texto fuera de la barra
            x_pos = val + (0.5 if val > 0 else -0.5)
            ha = 'left' if val > 0 else 'right'
            ax_main.text(x_pos, i, f'{val:+.2f} pts',
                         va='center', ha=ha, fontsize=16, fontweight='bold',
                         color='#222222')
    
    # Añadir línea vertical en x=0
    ax_main.axvline(x=0, color='#222222', linewidth=2, linestyle='-', alpha=0.8)
    
    ax_main.set_yticks(y_pos)
    ax_main.set_yticklabels(factors, fontsize=18, fontweight='bold')
    ax_main.set_xlabel('Puntos de diferencia', fontsize=14, fontweight='bold')
    ax_main.grid(axis='x', alpha=0.3, linestyle='--')
    ax_main.spines['top'].set_visible(False)
    ax_main.spines['right'].set_visible(False)
    ax_main.spines['left'].set_visible(False)
    
    # Título del gráfico de barras
    ax_main.set_title('Contribución individual de cada factor', 
                     fontsize=18, fontweight='bold', pad=15, color='#222222')
    
    # Área de resumen total
    ax_summary = fig.add_subplot(2, 1, 2)
    ax_summary.axis('off')
    
    # Calcular posiciones para visualización de cascada (waterfall)
    y_waterfall = 0.7
    x_start = 0.15
    x_width = 0.7

    # Reducir el padding superior del resumen
    # Antes: (0.1, 0.15), 0.8, 0.7
    # Ahora: (0.1, 0.10), 0.8, 0.7 para acercar la caja al gráfico superior
    summary_rect = mpatches.FancyBboxPatch(
        (0.1, 0.10), 0.8, 0.7,
        transform=ax_summary.transAxes,
        boxstyle="round,pad=0.02",
        facecolor='#f8f9fa',
        edgecolor='#222222',
        linewidth=3
    )
    ax_summary.add_patch(summary_rect)

    # Título del resumen
    ax_summary.text(0.5, 0.83, 'RESUMEN DE CONTRIBUCIONES', 
                   ha='center', va='center', fontsize=20, fontweight='bold',
                   color='#222222', transform=ax_summary.transAxes)
    
    # Detalles de cada factor
    y_detail = 0.72
    for factor, val in zip(factors, np_vals):
        color = '#27ae60' if val > 0 else '#e74c3c'
        symbol = '▲' if val > 0 else '▼'
        
        ax_summary.text(0.25, y_detail, f'{symbol} {factor}:', 
                       ha='left', va='center', fontsize=16, fontweight='bold',
                       color='#222222', transform=ax_summary.transAxes)
        
        ax_summary.text(0.75, y_detail, f'{val:+.2f} pts', 
                       ha='right', va='center', fontsize=16, fontweight='bold',
                       color=color, transform=ax_summary.transAxes)
        
        y_detail -= 0.13
    
    # Línea separadora
    ax_summary.plot([0.2, 0.8], [0.28, 0.28], 'k-', linewidth=2, 
                   transform=ax_summary.transAxes)
    
    # Total
    total_color = '#27ae60' if total > 0 else '#e74c3c'
    total_bg = '#d5f4e6' if total > 0 else '#fadbd8'
    
    total_rect = mpatches.FancyBboxPatch(
        (0.15, 0.08), 0.7, 0.15,
        transform=ax_summary.transAxes,
        boxstyle="round,pad=0.01",
        facecolor=total_bg,
        edgecolor=total_color,
        linewidth=3
    )
    ax_summary.add_patch(total_rect)
    
    ax_summary.text(0.25, 0.155, 'TOTAL EXPLICADO:', 
                   ha='left', va='center', fontsize=18, fontweight='bold',
                   color='#222222', transform=ax_summary.transAxes)
    
    ax_summary.text(0.75, 0.155, f'{total:+.2f} pts', 
                   ha='right', va='center', fontsize=22, fontweight='bold',
                   color=total_color, transform=ax_summary.transAxes)
    
    plt.tight_layout()
    return fig


def plot_finalizacion_page(analysis: dict) -> plt.Figure:
    """
    Genera un gráfico del mix de finalización de ambos equipos.
    """
    setup_montserrat_font()
    
    mixL = analysis["mix"]["local"]
    mixV = analysis["mix"]["visitor"]
    team_local = analysis.get("team_names", {}).get("local", "Local")
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")
    
    fig = plt.figure(figsize=(16, 10), facecolor='white')
    
    # Preparar datos
    categories = ['2PA', '3PA', 'TO', 'FT']
    local_shares = [
        mixL['share_2PA']*100,
        mixL['share_3PA']*100,
        mixL['share_TO']*100,
        mixL['share_FT']*100
    ]
    visit_shares = [
        mixV['share_2PA']*100,
        mixV['share_3PA']*100,
        mixV['share_TO']*100,
        mixV['share_FT']*100
    ]
    
    colors = ['#3498db', '#1abc9c', '#e74c3c', '#9b59b6']
    
    # LOCAL (izquierda)
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.set_title(f'{team_local.upper()} (poss={mixL["SC"]:.1f})', 
                 fontsize=20, fontweight='bold', pad=20, color='#222222')
    
    wedges1, texts1, autotexts1 = ax1.pie(
        local_shares, labels=categories, colors=colors, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 14, 'fontweight': 'bold'},
        wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
    )
    
    for autotext in autotexts1:
        autotext.set_color('white')
        autotext.set_fontsize(13)
        autotext.set_fontweight('bold')
    
    # VISITANTE (derecha)
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_title(f'{team_visit.upper()} (poss={mixV["SC"]:.1f})', 
                 fontsize=20, fontweight='bold', pad=20, color='#222222')
    
    wedges2, texts2, autotexts2 = ax2.pie(
        visit_shares, labels=categories, colors=colors, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 14, 'fontweight': 'bold'},
        wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
    )
    
    for autotext in autotexts2:
        autotext.set_color('white')
        autotext.set_fontsize(13)
        autotext.set_fontweight('bold')
    
    # Leyenda explicativa
    legend_text = (
        "2PA: Tiros de 2 puntos intentados  |  "
        "3PA: Tiros de 3 puntos intentados  |  "
        "TO: Pérdidas  |  "
        "FT: Tiros libres"
    )
    fig.text(0.5, 0.05, legend_text, 
            ha='center', va='center', fontsize=11, color='#666666',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#f5f5f5', alpha=0.9))
    
    plt.tight_layout()
    return fig


def plot_alertas_tacticas_page(analysis: dict) -> plt.Figure:
    """
    Genera una página visual con las alertas tácticas.
    """
    setup_montserrat_font()
    
    alerts = analysis["alerts"]
    
    fig = plt.figure(figsize=(16, 10), facecolor='white')
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    if not alerts:
        # Sin alertas
        fig.text(0.5, 0.5, '✅ No hay alertas críticas detectadas', 
                ha='center', va='center', fontsize=22, color='#27ae60',
                bbox=dict(boxstyle='round,pad=1.5', facecolor='#d5f4e6', 
                         edgecolor='#27ae60', linewidth=3))
    else:
        # Mostrar alertas en una lista visual
        y_start = 0.88
        y_spacing = 0.12
        
        for i, alert in enumerate(alerts[:6]):  # Máximo 6 alertas
            y_pos = y_start - (i * y_spacing)
            
            # Fondo para cada alerta
            rect = mpatches.FancyBboxPatch(
                (0.1, y_pos - 0.05), 0.8, 0.09,
                transform=fig.transFigure,
                boxstyle="round,pad=0.01",
                facecolor='#fff3cd',
                edgecolor='#ff6600',
                linewidth=2
            )
            fig.patches.append(rect)
            
            # Texto de la alerta
            fig.text(0.12, y_pos, f'• {alert}', 
                    ha='left', va='center', fontsize=15, color='#222222',
                    wrap=True, transform=fig.transFigure)
    
    return fig


def plot_jugadores_destacados_page(analysis: dict) -> plt.Figure:
    """
    Genera una página con los jugadores destacados (hot/cold) en formato horizontal con 3 jugadores por fila.
    """
    setup_montserrat_font()

    players = analysis["players_analysis"]
    team_local = analysis.get("team_names", {}).get("local", "Local")
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")

    fig = plt.figure(figsize=(16, 10), facecolor='white')

    # Dividir en 2 secciones: Local y Visitante
    # LOCAL
    fig.text(0.25, 0.93, team_local.upper(), 
             ha='center', va='top', fontsize=20, fontweight='bold',
             color='#3498db', fontname='Montserrat')

    hot_loc = players["local_hot"]
    cold_loc = players["local_cold"]

    # VISITANTE
    fig.text(0.75, 0.93, team_visit.upper(), 
             ha='center', va='top', fontsize=20, fontweight='bold',
             color='#e74c3c', fontname='Montserrat')

    hot_vis = players["visitor_hot"]
    cold_vis = players["visitor_cold"]

    def draw_players(ax, players, x_start, y_start, color, title):
        """Dibuja jugadores en formato horizontal con 3 por fila."""
        # Espaciado horizontal y vertical entre celdas (ajustado ligeramente)
        x_spacing = 0.14  # antes 0.25 -> un poco más compactos
        y_spacing = 0.15  # antes 0.18 -> filas más juntas
        max_per_row = 3

        # Título de la sección
        ax.text(x_start + 0.15, y_start + 0.05, title, 
                ha='center', va='center', fontsize=16, fontweight='bold', color=color)

        x_pos = x_start
        y_pos = y_start

        for i, player in enumerate(players):
            if i > 0 and i % max_per_row == 0:
                x_pos = x_start
                y_pos -= y_spacing

            # Número grande
            ax.text(x_pos, y_pos, player['name'].split('-')[0], 
                    ha='center', va='center', fontsize=24, fontweight='bold', color=color)

            # Nombre y estadísticas debajo (ligeramente más abajo para evitar solapamiento)
            stats = f"{player['name'].split('-')[1]}\nTS {player['TS']:.1%}, Vol {player['vol']:.1f}"
            ax.text(x_pos, y_pos - 0.07, stats,
                    ha='center', va='center', fontsize=12, color='#222222')

            x_pos += x_spacing

    ax = fig.add_subplot(111)
    ax.axis('off')

    # Dibujar jugadores locales
    draw_players(ax, hot_loc, x_start=0.1, y_start=0.8, color='#e67e22', title="Jugadores en racha")
    draw_players(ax, cold_loc, x_start=0.1, y_start=0.6, color='#3498db', title="Jugadores helados")

    # Dibujar jugadores visitantes
    draw_players(ax, hot_vis, x_start=0.6, y_start=0.8, color='#e67e22', title="Jugadores en racha")
    draw_players(ax, cold_vis, x_start=0.6, y_start=0.6, color='#3498db', title="Jugadores helados")

    # Leyenda
    legend_text = "TS: True Shooting %  |  Vol: Volumen de posesiones usadas"
    fig.text(0.5, 0.05, legend_text, 
            ha='center', va='center', fontsize=12, color='#666666',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#f5f5f5', alpha=0.9))

    return fig


# ============================================================
# FUNCIÓN PRINCIPAL: GENERACIÓN DEL PDF
# ============================================================

def presentation_pdf(analysis: dict, output_path: str = None) -> Path:
    """
    Genera un PDF de presentación del análisis del partido en vivo.
    
    Args:
        analysis: Diccionario con el análisis completo del partido (output de stats_engine.analyze_game)
        output_path: Ruta opcional para el PDF de salida
    
    Returns:
        Path: Ruta del archivo PDF generado
    """
    print("[DEBUG] Iniciando generación de PDF de presentación...")
    
    # Setup de fuentes
    setup_montserrat_pdf_fonts()
    
    # Determinar ruta de salida
    if output_path is None:
        output_dir = Path(__file__).parent.parent / "output" / "live_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = output_dir / f"live_report_{timestamp}.pdf"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generar las 5 páginas principales
    print("[DEBUG] Generando página de Four Factors...")
    fig_four_factors = plot_four_factors_page(analysis)
    
    print("[DEBUG] Generando página de Net Points...")
    fig_net_points = plot_net_points_page(analysis)
    
    print("[DEBUG] Generando página de Finalización...")
    fig_finalizacion = plot_finalizacion_page(analysis)
    
    print("[DEBUG] Generando página de Alertas Tácticas...")
    fig_alertas = plot_alertas_tacticas_page(analysis)
    
    print("[DEBUG] Generando página de Jugadores Destacados...")
    fig_jugadores = plot_jugadores_destacados_page(analysis)
    print("[DEBUG] Generando página de Malos Tiradores...")
    fig_malos = plot_malos_tiradores_page(analysis)

    figs = [
        fig_four_factors,
        fig_net_points,
        fig_finalizacion,
        fig_alertas,
        fig_jugadores,
        fig_malos
    ]
    
    # Títulos para cada página
    team_local = analysis.get("team_names", {}).get("local", "Local")
    team_visit = analysis.get("team_names", {}).get("visitor", "Visitante")
    score_local = analysis["score"]["local"]
    score_visit = analysis["score"]["visitor"]
    malos_tiradores_title = f"MALOS TIRADORES — {team_visit.upper()}"
    
    page_titles = [
        "FOUR FACTORS",
        "NET POINTS",
        "MIX DE FINALIZACIÓN",
        "ALERTAS",
        "JUGADORES DESTACADOS",
        malos_tiradores_title
    ]
    
    # Crear PDF
    print("[DEBUG] Creando PDF...")
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h), pageCompression=1)
    
    margin = 30
    color_black = '#222222'
    color_orange = '#ff6600'
    
    # Añadir cada página
    for idx, (fig, title) in enumerate(zip(figs, page_titles), start=1):
        print(f"[DEBUG] Añadiendo página {idx} al PDF...")
        
        # Fondo blanco
        c.setFillColor('white')
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        
        # Barra superior (header)
        bar_h = 50
        c.setFillColor(color_black)
        c.rect(0, page_h - bar_h, page_w, bar_h, fill=1, stroke=0)
        
        # Título en la barra negra: solo escudos
        crest_local = get_team_crest_path(team_local)
        crest_visit = get_team_crest_path(team_visit)
        crest_size = 44  # tamaño fijo para todos los escudos
        crest_y = page_h - bar_h/2 - crest_size/2
        # Reducir la distancia entre los escudos y añadir el título centrado
        crest_margin = 100  # margen reducido para acercar los escudos
        title_font_size = 22
        # Local escudo a la izquierda
        if crest_local:
            c.drawImage(crest_local, crest_margin, crest_y, width=crest_size, height=crest_size, mask='auto')
        # Visitante escudo a la derecha
        if crest_visit:
            c.drawImage(crest_visit, page_w - crest_margin - crest_size, crest_y, width=crest_size, height=crest_size, mask='auto')
        # Puntos junto a cada escudo
        try:
            c.setFont('Montserrat-Bold', title_font_size)
        except:
            c.setFont('Helvetica-Bold', title_font_size)
        c.setFillColor('white')
        c.drawRightString(crest_margin - 10, crest_y + crest_size/2 - 10, str(score_local))
        c.drawString(page_w - crest_margin - crest_size + crest_size + 10, crest_y + crest_size/2 - 10, str(score_visit))
        # Título centrado entre los escudos
        title_x = (crest_margin + crest_size + (page_w - crest_margin - crest_size)) / 2
        c.drawCentredString(title_x, crest_y + crest_size/2 - 10, title)
        
        # Barra inferior (footer)
        footer_h = 30
        c.setFillColor(color_orange)
        c.rect(0, 0, page_w, footer_h, fill=1, stroke=0)
        
        # Texto en footer
        c.setFillColor('white')
        try:
            c.setFont('Montserrat-Bold', 12)
        except:
            c.setFont('Helvetica-Bold', 12)
        
        quarter = analysis.get("quarter", 4)
        time_str = analysis.get("time", analysis.get("status", "00:00"))
        if not time_str:
            time_str = "00:00"
        c.drawString(margin, footer_h/2 - 5, f"Análisis en vivo - Q{quarter} - {time_str}")
        
        # Área del gráfico
        chart_y0 = footer_h + margin
        chart_h = page_h - bar_h - footer_h - 2*margin
        chart_x0 = margin
        chart_w = page_w - 2*margin
        
        # Borde del gráfico
        c.setLineWidth(3)
        c.setStrokeColor(color_black)
        c.rect(chart_x0 - 3, chart_y0 - 3, chart_w + 6, chart_h + 6, stroke=1, fill=0)
        
        # Convertir figura a imagen y añadirla
        buf = fig_to_png_buffer(fig, dpi=180)
        optimized_buf = optimize_png_buffer(buf, max_width=1400)
        img = ImageReader(optimized_buf)
        c.drawImage(img, chart_x0, chart_y0, width=chart_w, height=chart_h, 
                   preserveAspectRatio=True, mask='auto')
        
        c.showPage()
    
    # Guardar PDF
    c.save()
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✅ PDF de presentación generado en {output_path}")
    print(f"📄 Tamaño del archivo: {file_size_mb:.2f} MB")
    print(f"📊 Páginas: Four Factors, Net Points, Finalización, Alertas Tácticas, Jugadores Destacados")
    
    return output_path
