import io
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Plotting functions from team_report tools
from .tools.top_shooters              import plot_top_shooters
from .tools.top_turnovers             import plot_top_turnovers
from .tools.top_ppp                   import plot_top_ppp
from .tools.finalizacion_plays        import plot_player_finalizacion_plays
from .tools.oe                        import plot_player_OE_bar
from .tools.eps                       import plot_player_EPS_bar
from .tools.utils                     import setup_montserrat_font, compute_advanced_stats, compute_team_stats
import pandas as pd

# Importar configuración centralizada
from config import TEAMS_AGGREGATED_FILE, JUGADORES_AGGREGATED_FILE
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# === NUEVO: import del informe de asistencias ===
from team_report_assists.build_team_report_assists import build_team_report_assists

# === IMPORT CLUTCH (opcional, puede fallar por dependencias) ===
try:
    from team_report_clutch.build_clutch_lineups import build_top3_card, load_roster_lookup, load_lineups_for_team
    CLUTCH_AVAILABLE = True
    print("[DEBUG] Clutch module loaded successfully")
except ImportError as e:
    print(f"[DEBUG] Clutch module not available: {e}")
    CLUTCH_AVAILABLE = False
    # Define dummy functions to avoid NameError
    def load_roster_lookup(*args, **kwargs):
        return {}, {}
    def load_lineups_for_team(*args, **kwargs):
        raise ImportError("Clutch module not available")
    def build_top3_card(*args, **kwargs):
        raise ImportError("Clutch module not available")

# Setup Montserrat font for matplotlib
setup_montserrat_font()

# Register Montserrat fonts for ReportLab
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
                print(f"Warning: Could not register font {font_name}: {e}")

# === Configuration ===
TEAM_FILE       = Path(str(TEAMS_AGGREGATED_FILE))
PLAYERS_FILE    = Path(str(JUGADORES_AGGREGATED_FILE))
ASSISTS_FILE    = Path("data/assists.xlsx")  # <<< NUEVO
BASE_OUTPUT_DIR = Path("output/reports/team_reports/")

# Create output directory if it doesn't exist
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Add a timestamp to the output PDF to avoid overwriting
OUTPUT_PDF = BASE_OUTPUT_DIR / f"team_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf"

# Convert matplotlib Figure to PNG buffer with optimization
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

def build_team_report(team_filter=None, player_filter:list=None, players_file=None, teams_file=None, assists_file=None, clutch_lineups_file=None):
    # Setup fonts
    setup_montserrat_pdf_fonts()

    # 1) Load data - usar archivos pasados como parámetros o usar defaults
    players_path = Path(players_file) if players_file else PLAYERS_FILE
    teams_path = Path(teams_file) if teams_file else TEAM_FILE
    
    df_players = pd.read_excel(players_path)
    df_team    = pd.read_excel(teams_path)
    
    # === NUEVO: cargar asistencias ===
    if assists_file:
        try:
            df_assists = pd.read_excel(assists_file)
        except Exception as e:
            print(f"[DEBUG] No se pudo leer {assists_file}: {e}")
            df_assists = pd.DataFrame()
    else:
        print("[DEBUG] No se proporcionó archivo de assists, usando DataFrame vacío")
        df_assists = pd.DataFrame()

    # 2) Prepare player stats for individual analysis
    # Filter players data
    print(f"[DEBUG] team_filter: {team_filter}, player_filter: {player_filter}")
    if team_filter is not None and str(team_filter).strip() != "":
        print("[DEBUG] Filtering by team_filter")
        df_players_filtered = df_players[df_players['EQUIPO'] == team_filter]
        print(f"[DEBUG] df_players_filtered shape: {df_players_filtered.shape}")
        team_name = team_filter
        df_team_filtered = df_team[df_team['EQUIPO'] == team_name]
        # === NUEVO: asistencias del equipo ===
        df_assists_filtered = (
            df_assists[df_assists['EQUIPO'].astype(str).str.strip() == team_name]
            if not df_assists.empty and 'EQUIPO' in df_assists.columns else pd.DataFrame()
        )
        print(f"[DEBUG] df_assists_filtered shape: {df_assists_filtered.shape if not df_assists_filtered.empty else (0,0)}")
    elif player_filter is not None and len(player_filter) > 0:
        print("[DEBUG] Filtering by player_filter")
        df_players_filtered = df_players[df_players['JUGADOR'].isin(player_filter)]
        print(f"[DEBUG] df_players_filtered shape: {df_players_filtered.shape}")
        team_name = df_players_filtered['EQUIPO'].iloc[0] if not df_players_filtered.empty else ""
        df_team_filtered = df_team[df_team['EQUIPO'] == team_name]
        # === NUEVO: asistencias (si podemos inferir equipo) ===
        df_assists_filtered = (
            df_assists[df_assists['EQUIPO'].astype(str).str.strip() == team_name]
            if team_name and not df_assists.empty and 'EQUIPO' in df_assists.columns else pd.DataFrame()
        )
        print(f"[DEBUG] df_assists_filtered shape: {df_assists_filtered.shape if not df_assists_filtered.empty else (0,0)}")
    else:
        print("[DEBUG] No valid filter provided")
        raise ValueError("Must provide either a non-empty team_filter or a non-empty player_filter")

    # Compute advanced stats for players
    print("[DEBUG] Computing advanced stats for filtered players...")
    stats_list = []
    for idx, row in df_players_filtered.iterrows():
        print(f"[DEBUG] Computing stats for player row {idx}")
        player_stats = compute_advanced_stats(row)
        stats_list.append(player_stats)
    print(f"[DEBUG] stats_list length: {len(stats_list)}")

    df_players_stats = pd.DataFrame(stats_list)
    print(f"[DEBUG] df_players_stats shape: {df_players_stats.shape}")
    # Add team info back
    df_players_stats['EQUIPO'] = df_players_filtered['EQUIPO'].values
    print(f"[DEBUG] Added EQUIPO column to df_players_stats")

    # --- Generate report pages depending on filter ---
    figs = []
    add_overview_and_bars = team_filter is not None and str(team_filter).strip() != "" and (player_filter is None or len(player_filter) == 0)
    print(f"[DEBUG] add_overview_and_bars: {add_overview_and_bars}")

    overview_fig = None
    bars_fig = None
    assists_fig = None  # <<< NUEVO
    clutch_fig = None
    if add_overview_and_bars:
        print("[DEBUG] Generating single overview page...")
        from team_report_overview.build_team_report_overview import build_team_report_overview, compute_advanced_stats_overview
        df_advanced = compute_advanced_stats_overview(df_team_filtered)
        print(f"[DEBUG] df_advanced shape: {df_advanced.shape}")
        print(f"[DEBUG] team name: {team_name}")
        overview_fig = build_team_report_overview(team_name, df_advanced, dpi=180, players_file=str(players_path))
        print("[DEBUG] Saving image to ./team_overview_test.png")
        overview_fig.savefig("./team_overview_test.png", dpi=180, bbox_inches='tight')
        
        print("[DEBUG] Generating single bars page...")
        from team_report_bars.build_team_report_bars import build_team_report_bars,compute_advanced_stats_bars
        stats_advanced = df_team_filtered.apply(compute_advanced_stats_bars, axis=1)
        df_advanced_bars = pd.DataFrame(stats_advanced.tolist())

        print(f"[DEBUG] df_advanced_bars shape: {df_advanced_bars.shape}")
        stats_puntos = {
            "T1C": int(df_advanced_bars['T1C'].sum()),
            "T2C": int(df_advanced_bars['T2C'].sum()),
            "T3C": int(df_advanced_bars['T3C'].sum())
        }
        print(f"[DEBUG] stats_puntos: {stats_puntos}")
        stats_finalizacion = {
            "T1 %": float(df_advanced_bars['F1 Plays%'].mean()),
            "T2 %": float(df_advanced_bars['F2 Plays%'].mean()),
            "T3 %": float(df_advanced_bars['F3 Plays%'].mean()),
            "PP %": float(df_advanced_bars['TO Plays%'].mean())
        }
        print(f"[DEBUG] stats_finalizacion: {stats_finalizacion}")
        bars_fig = build_team_report_bars(stats_puntos, stats_finalizacion, dpi=180)
        print(f"[DEBUG] bars_fig created")
        
        print("[DEBUG] Generating single clutch lineup page...")
        clutch_fig = None
        
        if not CLUTCH_AVAILABLE:
            print("[DEBUG] Clutch module not available. Skipping clutch lineup page...")
            clutch_fig = None
        else:
            try:
                # lookups
                image_lookup, dorsal_lookup = load_roster_lookup(players_path, team_filter)
                # lineups - usar archivo dinámico o default
                clutch_lineups_path = clutch_lineups_file if clutch_lineups_file else "./data/clutch_lineups.xlsx"
                print(f"[DEBUG] Loading clutch lineups from: {clutch_lineups_path}")
                df_team = load_lineups_for_team(clutch_lineups_path, team_filter)
                print(f"[DEBUG] Found {len(df_team)} clutch lineups for team '{team_filter}'")
                clutch_fig = build_top3_card(df_team, team_filter, image_lookup, dorsal_lookup)
                print("[DEBUG] clutch_fig created successfully")
            except (FileNotFoundError, ValueError, SystemExit) as e:
                print(f"[DEBUG] No clutch data available for team '{team_filter}': {e}")
                print("[DEBUG] Skipping clutch lineup page...")
                clutch_fig = None
            except Exception as e:
                print(f"[DEBUG] Error generating clutch lineup page: {e}")
                print("[DEBUG] Skipping clutch lineup page...")
                clutch_fig = None


        # === NUEVO: Generar página de asistencias como tercera página ===
        assists_fig = None
        try:
            if not df_assists_filtered.empty:
                print("[DEBUG] Generating assists overview page...")
                assists_fig = build_team_report_assists(
                    df_assists_team=df_assists_filtered,
                    output_path=None,           # embebemos en PDF, no guardamos aquí
                    dpi=180,
                    edge_threshold=2,
                    roster_path=str(players_path),
                    fig_width=13.5,
                    fig_height=8.27,
                    pct_cell_threshold=0.05
                )
                print("[DEBUG] assists_fig created")
            else:
                print("[DEBUG] No assists data for this team. Skipping assists page.")
                assists_fig = None
        except Exception as e:
            print(f"[DEBUG] Error generating assists page: {e}")
            assists_fig = None

    # --- Generate main report pages (always) ---
    print("[DEBUG] Generating main report pages...")
    figs = []
    try:
        figs.append(plot_player_OE_bar(df_players_stats))
        print("[DEBUG] plot_player_OE_bar done")
        figs.append(plot_player_EPS_bar(df_players_stats))
        print("[DEBUG] plot_player_EPS_bar done")
        figs.append(plot_top_shooters(df_players_stats))
        print("[DEBUG] plot_top_shooters done")
        figs.append(plot_top_turnovers(df_players_stats))
        print("[DEBUG] plot_top_turnovers done")
        figs.append(plot_top_ppp(df_players_stats))
        print("[DEBUG] plot_top_ppp done")
        figs.append(plot_player_finalizacion_plays(df_players_stats))
        print("[DEBUG] plot_player_finalizacion_plays done")
    except Exception as e:
        print(f"[DEBUG] Error generating main report pages: {e}")

    # --- Prepare PDF canvas (A4 landscape) ---
    print("[DEBUG] Preparing PDF canvas...")
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=(page_w, page_h), pageCompression=1)
    margin = 30
    color_black  = '#222222'
    color_orange = '#ff6600'

    if add_overview_and_bars:
        print("[DEBUG] Adding overview and bars pages to PDF...")
        # OVERVIEW
        overview_png_path = "./team_overview_pdf_direct.png"
        overview_fig.savefig(overview_png_path, dpi=180, bbox_inches=None, facecolor='white', edgecolor='none')
        img = Image.open(overview_png_path)
        img_w, img_h = img.size
        scale = 0.37
        draw_w = img_w * scale
        draw_h = img_h * scale
        img_reader = ImageReader(overview_png_path)
        c.drawImage(img_reader, 0, page_h - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=False, mask='auto')
        c.showPage()

        # BARS
        bars_png_path = "./team_bars_pdf_direct.png"
        bars_fig.savefig(bars_png_path, dpi=180, bbox_inches=None, facecolor='white', edgecolor='none')
        img_bars = Image.open(bars_png_path)
        bars_w, bars_h = img_bars.size
        bars_scale = 0.4
        bars_draw_w = bars_w * bars_scale
        bars_draw_h = bars_h * bars_scale
        bars_reader = ImageReader(bars_png_path)
        c.drawImage(bars_reader, 0, page_h - bars_draw_h, width=bars_draw_w, height=bars_draw_h, preserveAspectRatio=False, mask='auto')
        c.showPage()
        
        # CLUTCH LINEUP (only if data is available)
        if clutch_fig is not None:
            clutch_png_path = "./team_clutch_pdf_direct.png"
            clutch_fig.savefig(clutch_png_path, dpi=180, bbox_inches=None, facecolor='white', edgecolor='none')
            img_clutch = Image.open(clutch_png_path)
            clutch_w, clutch_h = img_clutch.size
            clutch_scale = 0.35
            clutch_draw_w = clutch_w * clutch_scale
            clutch_draw_h = clutch_h * clutch_scale
            clutch_reader = ImageReader(clutch_png_path)
            c.drawImage(clutch_reader, 0, page_h - clutch_draw_h, width=clutch_draw_w, height=clutch_draw_h, preserveAspectRatio=False, mask='auto')
            c.showPage()
        else:
            print("[DEBUG] Clutch figure missing; skipping clutch lineup page.")

        # === NUEVO: ASSISTS (tercera página), reducción 40% ===
        if assists_fig is not None:
            assists_png_path = "./team_assists_pdf_direct.png"
            assists_fig.savefig(assists_png_path, dpi=180, bbox_inches=None, facecolor='white', edgecolor='none')
            img_assists = Image.open(assists_png_path)
            a_w, a_h = img_assists.size
            assists_scale = 0.35  # reducción 25%
            a_draw_w = a_w * assists_scale
            a_draw_h = a_h * assists_scale
            left_margin = int(page_w * 0.03)  # 8% del ancho de página como margen izquierdo
            assists_reader = ImageReader(assists_png_path)
            c.drawImage(assists_reader, -left_margin, page_h - a_draw_h, width=a_draw_w, height=a_draw_h, preserveAspectRatio=False, mask='auto')
            c.showPage()
        else:
            print("[DEBUG] Assists figure missing; skipping third page.")

    # Add main report pages
    print("[DEBUG] Adding main report pages to PDF...")
    for idx, fig in enumerate(figs, start=1):
        c.setFillColor('white')
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        bar_h = 50
        c.setFillColor(color_black)
        c.rect(0, page_h-bar_h, page_w, bar_h, fill=1, stroke=0)
        footer_h = 30
        c.setFillColor(color_orange)
        c.rect(0, 0, page_w, footer_h, fill=1, stroke=0)
        c.setFillColor('white')
        try:
            c.setFont('Montserrat-Bold', 18)
        except:
            c.setFont('Helvetica-Bold', 18)
        chart_y0 = footer_h + margin
        chart_h  = page_h - bar_h - footer_h - 2*margin
        chart_x0 = margin
        chart_w  = page_w - 2*margin
        c.setLineWidth(3)
        c.setStrokeColor(color_black)
        c.rect(chart_x0-3, chart_y0-3, chart_w+6, chart_h+6, stroke=1, fill=0)
        buf = fig_to_png_buffer(fig, dpi=180)
        optimized_buf = optimize_png_buffer(buf, max_width=1400)
        img = ImageReader(optimized_buf)
        c.drawImage(img, chart_x0, chart_y0, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')
        c.showPage()

    c.save()
    file_size_mb = OUTPUT_PDF.stat().st_size / (1024 * 1024)
    print(f"✅ Informe de equipo generado en {OUTPUT_PDF}")
    print(f"📄 Tamaño del archivo: {file_size_mb:.2f} MB")
    if add_overview_and_bars:
        if assists_fig is not None:
            print(f"📊 PDF con overview, bars y asistencias + main report")
        else:
            print(f"📊 PDF con overview, bars (sin asistencias) + main report")
    else:
        print(f"📊 PDF solo con main report (filtrado por jugadores)")
    print("[DEBUG] build_team_report finished.")
    return OUTPUT_PDF

if __name__ == '__main__':
    team = 'UROS DE RIVAS'  # Example team
    players = [
        'A. APARICIO IZQUIERDO',
        'A. ARREDONDO ROBLES',
        'BIERSACK LOPEZ, ALVARO',
        'I. MATAMOROS BUCH',
        'I. PÉREZ HERNÁNDEZ',
        'PEREZ GALVAN, ADRIAN',
        'PEREZ RINCON, MARIO',
        'VORONIN, MAKAR',
        'WRIGHT, KEDAR SALAM NKOSI'
    ]

    build_team_report(
        team_filter=team,      # puedes activar el flujo de overview/bars/assists
        player_filter=None
    )
