import io
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt

# FORZAR RECARGA - VERSIÓN CORREGIDA SIN INVERSIÓN
print("[BUILD_TEAM_REPORT] 🔄 Módulo cargado - VERSIÓN SIN INVERSIÓN DE COLUMNAS")
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
from .tools.top_assists_vs_turnovers  import plot_top_assists_vs_turnovers
from .tools.utils                     import setup_montserrat_font, compute_advanced_stats, compute_team_stats
import pandas as pd

# Importar configuración centralizada
from config import TEAMS_AGGREGATED_FILE, JUGADORES_AGGREGATED_FILE
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# === NUEVO: import del informe de asistencias ===
from team_report_assists.build_team_report_assists import build_team_report_assists

# === NUEVO: import de head-to-head comparison ===
from team_report_overview.tools.plot_head_to_head import generate_head_to_head_comparison

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

# OUTPUT_PDF will be dynamically generated in build_team_report() based on team filter

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

def _apply_home_away_filter(df_team, prefix):
    """
    Aplica filtro de local/visitante reemplazando columnas con las de prefijo.
    VERSIÓN CORREGIDA - SIN INVERSIÓN
    
    Args:
        df_team: DataFrame original con todas las columnas
        prefix: "LOCAL_" o "VISITANTE_"
    
    Returns:
        DataFrame con columnas originales reemplazadas por las del prefijo
    """
    df_result = df_team.copy()
    
    # Usar el prefijo directamente SIN INVERTIR (CORREGIDO)
    if prefix == "LOCAL_":
        actual_prefix = "LOCAL_"
        actual_pj_col = "PJ_LOCAL"
        print(f"[DEBUG] ✅✅✅ Filtro LOCAL → Usando LOCAL_* (NO INVERTIDO)")
    else:  # "VISITANTE_"
        actual_prefix = "VISITANTE_"
        actual_pj_col = "PJ_VISITANTE"
        print(f"[DEBUG] ✅✅✅ Filtro VISITANTE → Usando VISITANTE_* (NO INVERTIDO)")
    
    # Actualizar PJ con el correcto
    if actual_pj_col in df_team.columns:
        df_result["PJ"] = df_team[actual_pj_col]
        print(f"[DEBUG] Actualizando PJ con {actual_pj_col} (valor: {df_team[actual_pj_col].sum()})")
    
    # Buscar columnas con el prefijo
    prefixed_cols = [col for col in df_team.columns if col.startswith(actual_prefix)]
    print(f"[DEBUG] Encontradas {len(prefixed_cols)} columnas con prefijo {actual_prefix}")
    
    for prefixed_col in prefixed_cols:
        # Obtener nombre original (sin prefijo)
        original_name = prefixed_col.replace(actual_prefix, "", 1)
        
        # Si la columna original existe, reemplazarla con la del prefijo
        if original_name in df_result.columns:
            df_result[original_name] = df_team[prefixed_col]
            print(f"[DEBUG] Reemplazando {original_name} con {prefixed_col}")
    
    return df_result

def build_team_report(team_filter=None, player_filter:list=None, players_file=None, teams_file=None, assists_file=None, clutch_lineups_file=None, rival_team=None, home_away_filter="Todos", h2h_home_away_filter="Todos", min_games=5, min_minutes=50, min_shots=20):
    # Setup fonts
    setup_montserrat_pdf_fonts()

    # 1) Load data - usar archivos pasados como parámetros o usar defaults
    players_path = Path(players_file) if players_file else PLAYERS_FILE
    teams_path = Path(teams_file) if teams_file else TEAM_FILE
    
    df_players = pd.read_excel(players_path)
    df_team_raw = pd.read_excel(teams_path)
    
    # Aplicar filtro de local/visitante a df_team
    if home_away_filter == "Local":
        print("[DEBUG] Aplicando filtro LOCAL: usando columnas LOCAL_*")
        df_team = _apply_home_away_filter(df_team_raw, "LOCAL_")
    elif home_away_filter == "Visitante":
        print("[DEBUG] Aplicando filtro VISITANTE: usando columnas VISITANTE_*")
        df_team = _apply_home_away_filter(df_team_raw, "VISITANTE_")
    else:
        print("[DEBUG] Sin filtro de localía: usando todas las columnas")
        df_team = df_team_raw
    
    # Debug: Verificar porcentajes de rebote después del filtro
    if not df_team.empty and 'EB FELIPE ANTÓN' in df_team['EQUIPO'].values:
        felipe_row = df_team[df_team['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
        print(f"\n[DEBUG] ════════════════════════════════════════")
        print(f"[DEBUG] 🏀 EB FELIPE ANTÓN DESPUÉS FILTRO GENERAL ({home_away_filter}):")
        print(f"[DEBUG] ════════════════════════════════════════")
        print(f"[DEBUG]   PJ: {felipe_row.get('PJ', 'N/A')}")
        print(f"[DEBUG]   T3 CONVERTIDO: {felipe_row.get('T3 CONVERTIDO', 'N/A')}")
        print(f"[DEBUG]   T3 INTENTADO: {felipe_row.get('T3 INTENTADO', 'N/A')}")
        if felipe_row.get('T3 INTENTADO', 0) > 0:
            print(f"[DEBUG]   T3%: {felipe_row.get('T3 CONVERTIDO', 0) / felipe_row.get('T3 INTENTADO', 1) * 100:.2f}%")
        print(f"[DEBUG]   REB OFFENSIVO: {felipe_row.get('REB OFFENSIVO', 'N/A')}")
        print(f"[DEBUG]   REB DEFENSIVO: {felipe_row.get('REB DEFENSIVO', 'N/A')}")
        print(f"[DEBUG]   %OREB: {felipe_row.get('%OREB', 'N/A')}")
        print(f"[DEBUG]   %DREB: {felipe_row.get('%DREB', 'N/A')}")
        print(f"[DEBUG]   %REB: {felipe_row.get('%REB', 'N/A')}")
        print(f"[DEBUG] ════════════════════════════════════════\n")
    
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

    # 2.1) Generate dynamic filename based on team and jornada
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    
    # Normalizar nombre del equipo para el archivo
    equipo_safe = "".join(c for c in team_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    equipo_safe = equipo_safe.replace(' ', '_')[:50]  # Limitar longitud
    
    # Detectar jornadas únicas en los datos del equipo
    jornadas_str = "ACUMULADO"
    if 'JORNADA' in df_players_filtered.columns:
        jornadas_unicas = sorted(df_players_filtered['JORNADA'].dropna().unique())
        if len(jornadas_unicas) == 1:
            jornadas_str = f"J{int(jornadas_unicas[0]):02d}"
        elif len(jornadas_unicas) > 1:
            jornadas_str = "ACUMULADO"
    
    # Añadir sufijo de local/visitante si aplica
    home_away_suffix = ""
    if home_away_filter == "Local":
        home_away_suffix = "_LOCAL"
    elif home_away_filter == "Visitante":
        home_away_suffix = "_VISITANTE"
    
    # Construir nombre del archivo: EQUIPO_JORNADA_LOCAL/VISITANTE_fecha.pdf
    filename = f"{equipo_safe}_{jornadas_str}{home_away_suffix}_{timestamp}.pdf"
    OUTPUT_PDF = BASE_OUTPUT_DIR / filename

    # Después de filtrar por equipo/jugadores, añadir filtro por partidos mínimos
    # Usar los parámetros configurables recibidos en la función

    # Filtrar jugadores con partidos mínimos
    if 'PARTIDOS' in df_players_filtered.columns:
        df_players_filtered = df_players_filtered[df_players_filtered['PARTIDOS'] >= min_games]
    elif 'PJ' in df_players_filtered.columns:
        df_players_filtered = df_players_filtered[df_players_filtered['PJ'] >= min_games]

    print(f"[DEBUG] After minimum games filter: {df_players_filtered.shape[0]} players")
    print(f"[DEBUG] Available columns: {list(df_players_filtered.columns)}")

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
    print(f"[DEBUG] df_players_stats columns: {list(df_players_stats.columns)}")
    
    # Add team info and original columns back
    df_players_stats['EQUIPO'] = df_players_filtered['EQUIPO'].values
    df_players_stats['JUGADOR'] = df_players_filtered['JUGADOR'].values
    df_players_stats['DORSAL'] = df_players_filtered['DORSAL'].values
    df_players_stats['PJ'] = df_players_filtered['PJ'].values
    df_players_stats['MINUTOS JUGADOS'] = df_players_filtered['MINUTOS JUGADOS'].values
    print(f"[DEBUG] Added original columns to df_players_stats")

    # --- Generate report pages depending on filter ---
    figs = []
    add_overview_and_bars = team_filter is not None and str(team_filter).strip() != "" and (player_filter is None or len(player_filter) == 0)
    print(f"[DEBUG] add_overview_and_bars: {add_overview_and_bars}")

    overview_fig = None
    bars_fig = None
    head_to_head_fig = None  # <<< NUEVO: página head-to-head
    assists_fig = None  # <<< NUEVO
    clutch_fig = None
    if add_overview_and_bars:
        print("[DEBUG] Generating single overview page...")
        from team_report_overview.build_team_report_overview import build_team_report_overview, compute_advanced_stats_overview
        
        # Debug antes de compute_advanced_stats_overview
        if not df_team_filtered.empty and 'EB FELIPE ANTÓN' in df_team_filtered['EQUIPO'].values:
            felipe = df_team_filtered[df_team_filtered['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
            print(f"\n[DEBUG] ════════════════════════════════════════")
            print(f"[DEBUG] 📊 DATOS PARA OVERVIEW (antes compute_advanced_stats):")
            print(f"[DEBUG] ════════════════════════════════════════")
            print(f"[DEBUG]   PJ: {felipe.get('PJ', 'N/A')}")
            print(f"[DEBUG]   T3 CONVERTIDO: {felipe.get('T3 CONVERTIDO', 'N/A')}")
            print(f"[DEBUG]   T3 INTENTADO: {felipe.get('T3 INTENTADO', 'N/A')}")
            print(f"[DEBUG]   %OREB: {felipe.get('%OREB', 'N/A')}")
            print(f"[DEBUG]   %DREB: {felipe.get('%DREB', 'N/A')}")
            print(f"[DEBUG]   %REB: {felipe.get('%REB', 'N/A')}")
            print(f"[DEBUG] ════════════════════════════════════════\n")
        
        df_advanced = compute_advanced_stats_overview(df_team_filtered)
        
        # Debug después de compute_advanced_stats_overview
        if not df_advanced.empty and 'EB FELIPE ANTÓN' in df_advanced['EQUIPO'].values:
            felipe_adv = df_advanced[df_advanced['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
            print(f"\n[DEBUG] ════════════════════════════════════════")
            print(f"[DEBUG] 📊 DATOS PARA OVERVIEW (después compute_advanced_stats):")
            print(f"[DEBUG] ════════════════════════════════════════")
            print(f"[DEBUG]   PJ: {felipe_adv.get('PJ', 'N/A')}")
            print(f"[DEBUG]   T3 CONVERTIDO: {felipe_adv.get('T3 CONVERTIDO', 'N/A')}")
            print(f"[DEBUG]   T3 INTENTADO: {felipe_adv.get('T3 INTENTADO', 'N/A')}")
            print(f"[DEBUG]   %OREB: {felipe_adv.get('%OREB', 'N/A')}")
            print(f"[DEBUG]   %DREB: {felipe_adv.get('%DREB', 'N/A')}")
            print(f"[DEBUG]   %REB: {felipe_adv.get('%REB', 'N/A')}")
            print(f"[DEBUG] ════════════════════════════════════════\n")
        
        print(f"[DEBUG] df_advanced shape: {df_advanced.shape}")
        print(f"[DEBUG] team name: {team_name}")
        overview_fig = build_team_report_overview(team_name, df_advanced, dpi=180, players_file=str(players_path), min_games=min_games)
        print("[DEBUG] Saving image to ./team_overview_test.png")
        overview_fig.savefig("./team_overview_test.png", dpi=180, bbox_inches=None, facecolor='white', edgecolor='none')
        
        # === NUEVO: Generar head-to-head con el rival seleccionado ===
        print("[DEBUG] ========================================")
        print("[DEBUG] GENERANDO HEAD-TO-HEAD COMPARISON")
        print("[DEBUG] ========================================")
        print(f"[DEBUG] Equipo principal: {team_name}")
        print(f"[DEBUG] Filtro GENERAL (mi equipo): {home_away_filter}")
        print(f"[DEBUG] Filtro H2H (rival): {h2h_home_away_filter}")
        
        try:
            # IMPORTANTE: El equipo principal (izquierda) usa el FILTRO GENERAL
            # El filtro H2H se aplica solo al RIVAL (derecha)
            print("[DEBUG] H2H: Equipo principal usa FILTRO GENERAL (ya aplicado)")
            df_team_filtered_h2h = df_team_filtered  # Ya tiene el filtro general aplicado
            
            # DEBUG: Verificar datos del equipo principal ANTES de pasar al H2H
            print(f"[DEBUG] ========================================")
            print(f"[DEBUG] DATOS EQUIPO PRINCIPAL ({team_name})")
            print(f"[DEBUG] ========================================")
            if len(df_team_filtered_h2h) > 0:
                row = df_team_filtered_h2h.iloc[0]
                print(f"[DEBUG] PJ: {row.get('PJ', 'N/A')}")
                print(f"[DEBUG] PJ_LOCAL (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('PJ_LOCAL', 'N/A')}")
                print(f"[DEBUG] PJ_VISITANTE (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('PJ_VISITANTE', 'N/A')}")
                print(f"[DEBUG] T3 CONVERTIDO: {row.get('T3 CONVERTIDO', 'N/A')}")
                print(f"[DEBUG] T3 INTENTADO: {row.get('T3 INTENTADO', 'N/A')}")
                print(f"[DEBUG] LOCAL_T3 CONVERTIDO (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('LOCAL_T3 CONVERTIDO', 'N/A')}")
                print(f"[DEBUG] LOCAL_T3 INTENTADO (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('LOCAL_T3 INTENTADO', 'N/A')}")
                print(f"[DEBUG] VISITANTE_T3 CONVERTIDO (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('VISITANTE_T3 CONVERTIDO', 'N/A')}")
                print(f"[DEBUG] VISITANTE_T3 INTENTADO (original): {df_team_raw[df_team_raw['EQUIPO'] == team_name].iloc[0].get('VISITANTE_T3 INTENTADO', 'N/A')}")
            
            # Para el rival, aplicar el FILTRO H2H
            print("[DEBUG] ========================================")
            print(f"[DEBUG] H2H: Aplicando filtro {h2h_home_away_filter} al RIVAL")
            
            # Aplicar filtro H2H al rival
            if h2h_home_away_filter == "Local":
                df_rival_source = _apply_home_away_filter(df_team_raw, "LOCAL_")
            elif h2h_home_away_filter == "Visitante":
                df_rival_source = _apply_home_away_filter(df_team_raw, "VISITANTE_")
            else:
                df_rival_source = df_team_raw  # Sin filtro
            
            # Determinar el rival a usar
            otros_equipos = df_rival_source[df_rival_source['EQUIPO'] != team_name]
            
            if not otros_equipos.empty:
                # Si se especificó un rival y existe en los datos, usarlo
                if rival_team and rival_team in otros_equipos['EQUIPO'].values:
                    rival_name = rival_team
                    rival_count = len(otros_equipos[otros_equipos['EQUIPO'] == rival_name])
                    print(f"[DEBUG] Usando rival especificado: {rival_name} ({rival_count} partidos)")
                else:
                    # Fallback: Intentar con GRUPO EGIDO PINTOBASKET por defecto
                    default_rival = "GRUPO EGIDO PINTOBASKET"
                    if default_rival in otros_equipos['EQUIPO'].values:
                        rival_name = default_rival
                        rival_count = len(otros_equipos[otros_equipos['EQUIPO'] == rival_name])
                        print(f"[DEBUG] Usando rival por defecto: {rival_name} ({rival_count} partidos)")
                    else:
                        # Último recurso: usar el más frecuente
                        rival_counts = otros_equipos['EQUIPO'].value_counts()
                        rival_name = rival_counts.index[0]
                        print(f"[DEBUG] Usando rival más frecuente: {rival_name} ({rival_counts.iloc[0]} partidos)")
                
                df_rival = df_rival_source[df_rival_source['EQUIPO'] == rival_name]
                
                # DEBUG: Verificar datos del rival ANTES de pasar al H2H
                print(f"[DEBUG] ========================================")
                print(f"[DEBUG] DATOS RIVAL ({rival_name})")
                print(f"[DEBUG] ========================================")
                if len(df_rival) > 0:
                    rival_row = df_rival.iloc[0]
                    print(f"[DEBUG] PJ: {rival_row.get('PJ', 'N/A')}")
                    print(f"[DEBUG] T3 CONVERTIDO: {rival_row.get('T3 CONVERTIDO', 'N/A')}")
                    print(f"[DEBUG] T3 INTENTADO: {rival_row.get('T3 INTENTADO', 'N/A')}")
                
                # Debug datos para H2H
                if not df_team_filtered_h2h.empty and 'EB FELIPE ANTÓN' in df_team_filtered_h2h['EQUIPO'].values:
                    felipe_h2h = df_team_filtered_h2h[df_team_filtered_h2h['EQUIPO'] == 'EB FELIPE ANTÓN'].iloc[0]
                    print(f"\n[DEBUG] ════════════════════════════════════════")
                    print(f"[DEBUG] 🔄 DATOS PARA HEAD-TO-HEAD:")
                    print(f"[DEBUG] ════════════════════════════════════════")
                    print(f"[DEBUG]   PJ: {felipe_h2h.get('PJ', 'N/A')}")
                    print(f"[DEBUG]   T3 CONVERTIDO: {felipe_h2h.get('T3 CONVERTIDO', 'N/A')}")
                    print(f"[DEBUG]   T3 INTENTADO: {felipe_h2h.get('T3 INTENTADO', 'N/A')}")
                    if felipe_h2h.get('T3 INTENTADO', 0) > 0:
                        print(f"[DEBUG]   T3%: {felipe_h2h.get('T3 CONVERTIDO', 0) / felipe_h2h.get('T3 INTENTADO', 1) * 100:.2f}%")
                    print(f"[DEBUG]   %OREB: {felipe_h2h.get('%OREB', 'N/A')}")
                    print(f"[DEBUG]   %DREB: {felipe_h2h.get('%DREB', 'N/A')}")
                    print(f"[DEBUG]   %REB: {felipe_h2h.get('%REB', 'N/A')}")
                    print(f"[DEBUG] ════════════════════════════════════════\n")
                
                print(f"[DEBUG] ========================================")
                print(f"[DEBUG] LLAMANDO A generate_head_to_head_comparison")
                print(f"[DEBUG] ========================================")
                
                head_to_head_fig = generate_head_to_head_comparison(
                    df_main=df_team_filtered_h2h,
                    df_rival=df_rival,
                    main_team_name=team_name,
                    rival_team_name=rival_name
                )
                print("[DEBUG] head_to_head_fig created")
            else:
                print("[DEBUG] No rival teams found in dataset")
                head_to_head_fig = None
        except Exception as e:
            print(f"[DEBUG] Error generating head-to-head page: {e}")
            head_to_head_fig = None
        
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
        
        # Crear stats_media con los porcentajes reales de anotación (anotados/intentados)
        stats_media = {
            "T1 %": float(df_advanced_bars['T1 %'].mean()),
            "T2 %": float(df_advanced_bars['T2 %'].mean()),
            "T3 %": float(df_advanced_bars['T3 %'].mean())
        }
        print(f"[DEBUG] stats_media: {stats_media}")
        
        bars_fig = build_team_report_bars(stats_puntos, stats_finalizacion, stats_media, dpi=180)
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
        figs.append(plot_player_OE_bar(df_players_stats, min_games=min_games, min_minutes=min_minutes))
        print("[DEBUG] plot_player_OE_bar done")
        figs.append(plot_player_EPS_bar(df_players_stats, min_games=min_games, min_minutes=min_minutes))
        print("[DEBUG] plot_player_EPS_bar done")
        figs.append(plot_top_shooters(df_players_stats, min_games=min_games, min_shots=min_shots))
        print("[DEBUG] plot_top_shooters done")
        figs.append(plot_top_turnovers(df_players_stats, min_games=min_games, min_minutes=min_minutes))
        print("[DEBUG] plot_top_turnovers done")
        figs.append(plot_top_ppp(df_players_stats, min_games=min_games, min_minutes=min_minutes))
        print("[DEBUG] plot_top_ppp done")
        figs.append(plot_top_assists_vs_turnovers(df_players_stats, min_games=min_games, min_minutes=min_minutes))
        print("[DEBUG] plot_top_assists_vs_turnovers done")
        figs.append(plot_player_finalizacion_plays(df_players_stats, min_games=min_games, min_minutes=min_minutes))
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
        
        # HEAD-TO-HEAD
        if head_to_head_fig is not None:
            h2h_png_path = "./team_head_to_head_pdf_direct.png"
            head_to_head_fig.savefig(h2h_png_path, dpi=180, bbox_inches='tight', facecolor='white', edgecolor='none', pad_inches=0.2)
            img_h2h = Image.open(h2h_png_path)
            h2h_w, h2h_h = img_h2h.size
            # Calcular escala para que ocupe la mayor parte de la página manteniendo aspecto
            available_w = page_w - 2*margin
            available_h = page_h - 2*margin
            scale_w = available_w / h2h_w
            scale_h = available_h / h2h_h
            h2h_scale = min(scale_w, scale_h) * 0.9  # 90% del espacio disponible
            h2h_draw_w = h2h_w * h2h_scale
            h2h_draw_h = h2h_h * h2h_scale
            # Centrar en la página
            h2h_x = (page_w - h2h_draw_w) / 2
            h2h_y = (page_h - h2h_draw_h) / 2
            h2h_reader = ImageReader(h2h_png_path)
            c.drawImage(h2h_reader, h2h_x, h2h_y, width=h2h_draw_w, height=h2h_draw_h, preserveAspectRatio=True, mask='auto')
            c.showPage()
        else:
            print("[DEBUG] Head-to-head figure missing; skipping head-to-head page.")

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
        pages = ["overview"]
        if head_to_head_fig is not None:
            pages.append("head-to-head")
        pages.append("bars")
        if clutch_fig is not None:
            pages.append("clutch")
        if assists_fig is not None:
            pages.append("asistencias")
        print(f"📊 PDF con {', '.join(pages)} + main report")
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
