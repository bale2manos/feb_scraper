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

# Plotting functions
from .tools.heatmap                   import generate_team_heatmap
from .tools.hierarchy_score_boxplot   import plot_annotation_hierarchy
from .tools.net_rtg_chart             import plot_net_rating_vertical_with_stickers
from .tools.plays_vs_poss             import plot_plays_vs_poss
from .tools.play_distribution         import generate_team_play_distribution
from .tools.points_distribution       import generate_team_points_distribution
from .tools.ppp_quadrant              import draw_ppp_quadrant
from .tools.rebound_analysis          import generate_team_rebound_analysis
from .tools.top20_off_eff             import plot_offensive_efficiency
from .tools.top_shooters              import plot_top_shooters
from .tools.utils                  import compute_team_stats, setup_montserrat_font
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

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
TEAM_FILE     = Path("data/teams_aggregated.xlsx")
PLAYERS_FILE  = Path("data/jugadores_aggregated_24_25.xlsx")
BASE_OUTPUT_DIR = Path("output/reports/phase_reports/")

# Create output directory if it doesn't exist
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Add a timestamp to the output PDF to avoid overwriting
OUTPUT_PDF = BASE_OUTPUT_DIR / f"phase_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf"

# Convert matplotlib Figure to PNG buffer with optimization
def fig_to_png_buffer(fig, dpi=180):
    """Convert matplotlib figure to optimized PNG buffer."""
    fig.set_tight_layout(True)
    FigureCanvas(fig).draw()
    buf = io.BytesIO()
    
    # Slightly higher DPI for better quality
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', 
                transparent=False, facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf

def optimize_png_buffer(buf, max_width=1400):
    """Optimize PNG image buffer while maintaining quality."""
    buf.seek(0)
    img = Image.open(buf)
    
    # Only resize if significantly too large (maintain aspect ratio)
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    # Keep as PNG but optimize compression
    optimized_buf = io.BytesIO()
    img.save(optimized_buf, format='PNG', optimize=True, compress_level=6)
    optimized_buf.seek(0)
    return optimized_buf

def build_phase_report(teams=None, phase=None):
    # Setup fonts
    setup_montserrat_pdf_fonts()
    
    # 1) Load data
    df_teams   = pd.read_excel(TEAM_FILE)
    df_players = pd.read_excel(PLAYERS_FILE)

    # 2) Generate all figures
    stats = None
    try:
        stats = compute_team_stats(df_teams, teams=teams, phase=phase)
    except:
        stats = df_teams

    figs = [
        generate_team_heatmap(df_teams, teams=teams, phase=phase),
        plot_annotation_hierarchy(df_players, teams=teams, phase=phase),
        plot_net_rating_vertical_with_stickers(stats, teams=teams, phase=phase),
        plot_plays_vs_poss(df_teams, teams=teams, phase=phase),
        generate_team_play_distribution(stats, teams=teams, phase=phase),
        generate_team_points_distribution(stats, teams=teams, phase=phase),
        draw_ppp_quadrant(df_teams, teams=teams, phase=phase),
        generate_team_rebound_analysis(df_teams, teams=teams, phase=phase),
        plot_offensive_efficiency(df_players, teams=teams, phase=phase),
        plot_top_shooters(df_players, teams=teams, phase=phase, MIN_SHOTS=200)
    ]

    # 3) Prepare PDF canvas (A4 landscape) with compression
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=(page_w, page_h), pageCompression=1)
    total = len(figs)
    margin = 30  # wider margin

    # Design colors
    color_black  = '#222222'
    color_orange = '#ff6600'

    for idx, fig in enumerate(figs, start=1):
        # a) white background
        c.setFillColor('white')
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # b) top bar (black)
        bar_h = 50
        c.setFillColor(color_black)
        c.rect(0, page_h-bar_h, page_w, bar_h, fill=1, stroke=0)
        # bottom bar (orange)
        footer_h = 30
        c.setFillColor(color_orange)
        c.rect(0, 0, page_w, footer_h, fill=1, stroke=0)

        # c) header text
        c.setFillColor('white')
        try:
            c.setFont('Montserrat-Bold', 18)
        except:
            c.setFont('Helvetica-Bold', 18)  # Fallback
        c.drawString(margin, page_h-35, f"Informe de grupo ({idx}/{total})")

        # d) border around chart area
        chart_y0 = footer_h + margin
        chart_h  = page_h - bar_h - footer_h - 2*margin
        chart_x0 = margin
        chart_w  = page_w - 2*margin
        c.setLineWidth(3)
        c.setStrokeColor(color_black)
        c.rect(chart_x0-3, chart_y0-3, chart_w+6, chart_h+6, stroke=1, fill=0)

        # e) draw chart with optimized PNG
        buf = fig_to_png_buffer(fig, dpi=180)  # Balanced DPI for quality/size
        optimized_buf = optimize_png_buffer(buf, max_width=1400)
        img = ImageReader(optimized_buf)
        c.drawImage(
            img,
            chart_x0, chart_y0,
            width=chart_w, height=chart_h,
            preserveAspectRatio=True, mask='auto'
        )

        c.showPage()

    c.save()
    
    # Check file size
    file_size_mb = OUTPUT_PDF.stat().st_size / (1024 * 1024)
    print(f"✅ Informe generado en {OUTPUT_PDF}")
    print(f"📄 Tamaño del archivo: {file_size_mb:.2f} MB")
    print(f"📊 {total} gráficos procesados con optimización PNG")

if __name__ == '__main__':
    build_phase_report(
        teams=[
            'BALONCESTO TALAVERA','C.B. TRES CANTOS','CB ARIDANE',
            'CB LA MATANZA','EB FELIPE ANTÓN','LUJISA GUADALAJARA BASKET',
            'REAL CANOE N.C.','UROS DE RIVAS','ZENTRO BASKET MADRID'
        ],
        phase=None
    )
