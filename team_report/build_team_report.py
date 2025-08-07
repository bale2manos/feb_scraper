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
PLAYERS_FILE  = Path("data/jugadores_aggregated.xlsx")
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

def build_team_report(team_filter=None, player_filter:list=None):
    # Setup fonts
    setup_montserrat_pdf_fonts()
    
    # 1) Load data
    df_players = pd.read_excel(PLAYERS_FILE)

    # 2) Prepare player stats for individual analysis
    # Filter players data
    if team_filter is not None:
        df_players_filtered = df_players[df_players['EQUIPO'] == team_filter]
    elif player_filter is not None:
        df_players_filtered = df_players[df_players['JUGADOR'].isin(player_filter)]
    else:
        raise ValueError("Must provide either team_filter or player_filter")

    # Compute advanced stats for players
    stats_list = []
    for _, row in df_players_filtered.iterrows():
        player_stats = compute_advanced_stats(row)
        stats_list.append(player_stats)
    
    df_players_stats = pd.DataFrame(stats_list)
    # Add team info back
    df_players_stats['EQUIPO'] = df_players_filtered['EQUIPO'].values

    # 4) Generate all figures
    figs = [
        # Player analysis charts - using available team_report tools
        plot_player_OE_bar(df_players_stats),
        plot_player_EPS_bar(df_players_stats),
        plot_top_shooters(df_players_stats),
        plot_top_turnovers(df_players_stats),
        plot_top_ppp(df_players_stats),
        plot_player_finalizacion_plays(df_players_stats)
    ]

    # 5) Prepare PDF canvas (A4 landscape) with compression
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
        c.drawString(margin, page_h-35, f"Informe de equipo ({idx}/{total})")

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
    print(f"✅ Informe de equipo generado en {OUTPUT_PDF}")
    print(f"📄 Tamaño del archivo: {file_size_mb:.2f} MB")
    print(f"📊 {total} gráficos procesados con optimización PNG")
    
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
        team_filter=None,
        player_filter=players
    )
