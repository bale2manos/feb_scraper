# -*- coding: utf-8 -*-
"""
Configuración centralizada para el sistema de scraping de FEB
=============================================================

Este archivo contiene todas las constantes del proyecto para facilitar
su modificación y mantenimiento centralizados.
"""

from pathlib import Path

# =============================================================================
# CONFIGURACIÓN DE TEMPORADA Y COMPETICIÓN
# =============================================================================

# Temporada actual
TEMPORADA_TXT = "2024/2025"
TEMPORADA_CORTA = "24_25"  # Para nombres de archivos
TEMPORADA_ANTERIOR = "23_24"  # Para archivos de temporada anterior

# Fases de competición (Tercera FEB por defecto para compatibilidad)
FASES_PRINCIPALES = [
    'Liga Regular "B-A"', 
    'Liga Regular "B-B"',
    'Liga Regular "C-A"',

]

# Todas las fases disponibles en Tercera FEB (mantenido para compatibilidad)
TODAS_LAS_FASES = [
    'Liga Regular "A-A"',
    'Liga Regular "A-B"',
    'Liga Regular "B-A"',
    'Liga Regular "B-B"',
    'Liga Regular "C-A"',
    'Liga Regular "C-B"',
    'Liga Regular "D-A"',
    'Liga Regular "D-B"',
    'Liga Regular "E-A"',
    'Liga Regular "E-B"'
]

# Temporadas disponibles para la app de scraping
TEMPORADAS_DISPONIBLES = [
    "2022/2023",
    "2023/2024", 
    "2024/2025"
]

# Fase por defecto para pruebas
FASE_DEFAULT = 'Liga Regular "B-A"'

# =============================================================================
# CONFIGURACIÓN WEB SCRAPING
# =============================================================================

# Configuración de ligas
LIGAS_DISPONIBLES = {
    "Primera FEB": {
        "url_template": "https://baloncestoenvivo.feb.es/resultados/primerafeb/1/{year}",
        "categoria_id": 1,
        "fases": ["Liga Regular Único"],
        "nombre_corto": "1FEB"
    },
    "Segunda FEB": {
        "url_template": "https://baloncestoenvivo.feb.es/resultados/segundafeb/2/{year}",
        "categoria_id": 2,
        "fases": ["Liga Regular \"ESTE\"", "Liga Regular \"OESTE\""],
        "nombre_corto": "2FEB"
    },
    "Tercera FEB": {
        "url_template": "https://baloncestoenvivo.feb.es/resultados/tercerafeb/3/{year}",
        "categoria_id": 3,
        "fases": [
            "Liga Regular \"A-A\"",
            "Liga Regular \"A-B\"",
            "Liga Regular \"B-A\"",
            "Liga Regular \"B-B\"",
            "Liga Regular \"C-A\"",
            "Liga Regular \"C-B\"",
            "Liga Regular \"D-A\"",
            "Liga Regular \"D-B\"",
            "Liga Regular \"E-A\"",
            "Liga Regular \"E-B\""
        ],
        "nombre_corto": "3FEB"
    }
}

# Liga por defecto
LIGA_DEFAULT = "Tercera FEB"

# URLs base (mantenido para compatibilidad)
BASE_URL = "https://baloncestoenvivo.feb.es/resultados/tercerafeb/3/2024"
BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"

# Selectores HTML
SELECT_ID_TEMPORADA = "_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"
SELECT_ID_FASE = "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"
SELECT_ID_JORNADA = "_ctl0_MainContentPlaceHolderMaster_jornadasDropDownList"

# Configuración de cookies
COOKIE_BTN_XPATH = (
    "//button[normalize-space()='CONSENTIR TODO' or "
    "normalize-space()='ACEPTAR TODO' or "
    "normalize-space()='Acepto']"
)

# Configuración del driver
DRIVER_PATH = None  # None = usar PATH del sistema
WEBDRIVER_TIMEOUT = 15  # segundos

# Configuración de scraping paralelo
MAX_WORKERS = 2  # Threads para procesamiento paralelo (reducido para evitar errores de conexión)
MAX_WORKERS_BIO = 3  # Threads para biografías de jugadores (reducido para estabilidad)

# =============================================================================
# RUTAS DE ARCHIVOS Y DIRECTORIOS
# =============================================================================

# Directorio base de datos
DATA_DIR = Path("./data")

# Archivos de datos principales
JUGADORES_AGGREGATED_FILE = DATA_DIR / f"jugadores_aggregated_{TEMPORADA_CORTA}.xlsx"
JUGADORES_PER_GAME_FILE = DATA_DIR / f"jugadores_per_game_{TEMPORADA_CORTA}.xlsx"
TEAMS_AGGREGATED_FILE = DATA_DIR / "teams_aggregated.xlsx"
CLUTCH_AGGREGATED_FILE = DATA_DIR / "clutch_aggregated.xlsx"
GAMES_AGGREGATED_FILE = DATA_DIR / "games_aggregated.xlsx"
ASSISTS_FILE = DATA_DIR / "assists.xlsx"

# Archivos de temporada anterior (para comparaciones)
JUGADORES_AGGREGATED_ANTERIOR = DATA_DIR / f"jugadores_aggregated_{TEMPORADA_ANTERIOR}.xlsx"
JUGADORES_PER_GAME_ANTERIOR = DATA_DIR / f"jugadores_per_game_{TEMPORADA_ANTERIOR}.xlsx"
TEAMS_AGGREGATED_ANTERIOR = DATA_DIR / f"teams_aggregated_{TEMPORADA_ANTERIOR}.xlsx"

# Archivos de salida por defecto
OUTPUT_PHASES_FILE = DATA_DIR / "all_phases_boxscores.xlsx"
OUTPUT_RESULTADOS_FILE = DATA_DIR / "resultados_completos.csv"

# Directorios de recursos
IMAGES_DIR = Path("./images")
FONTS_DIR = Path("./fonts")
OUTPUT_DIR = Path("./output")
LIB_DIR = Path("./lib")

# Subdirectorios de imágenes
CLUBS_DIR = IMAGES_DIR / "clubs"
FLAGS_CACHE_DIR = IMAGES_DIR / "flags_cache"
TEMPLATES_DIR = IMAGES_DIR / "templates"

# Archivos de plantillas
TEMPLATE_BACKGROUND = TEMPLATES_DIR / "background_template.png"
GENERIC_PLAYER_IMAGE = TEMPLATES_DIR / "generic_player.png"
GENERIC_CLUB_LOGO = CLUBS_DIR / "generic_club.png"

# Directorio de reportes
REPORTS_DIR = OUTPUT_DIR / "reports"
PLAYER_REPORTS_DIR = REPORTS_DIR / "player_reports"
TEAM_REPORTS_DIR = REPORTS_DIR / "team_reports"
PHASE_REPORTS_DIR = REPORTS_DIR / "phase_reports"

# Fuentes
FONT_REGULAR = FONTS_DIR / "Montserrat-Regular.ttf"
FONT_BOLD = FONTS_DIR / "Montserrat-Bold.ttf"
FONT_BLACK = FONTS_DIR / "Montserrat-Black.ttf"

# Archivos de log
ERROR_LOG = "errors.log"
SCRAPER_LOG = "scraper.log"
CLUTCH_SEASON_LOG = "clutch_season.log"
BIO_SCRAPE_ERRORS_LOG = "bio_scrape_errors.log"

# =============================================================================
# CONFIGURACIÓN DE FILTROS Y UMBRALES
# =============================================================================

# Filtros de jugadores
MIN_PARTIDOS = 5
MIN_MINUTOS_PROMEDIO = 10
MIN_MINUTOS_TOTALES = 150
MIN_CLUTCH_MINUTOS = 1.0

# Filtros de tiros y estadísticas
MIN_SHOTS = 50  # Mínimo de tiros para análisis de eficiencia

# Umbrales para visualizaciones
LOW_THRESH = 0.36  # Umbral para valores "bajos" en gráficos

# =============================================================================
# CONFIGURACIÓN DE VISUALIZACIONES
# =============================================================================

# Colores principales para gráficos
COLORS_PRIMARY = ["#e74c3c", "#de9826", "#1abc9c", "#3498db", "#9b59b6"]
COLORS_CLUTCH = ["#c0392b", "#ca8322", "#16a085", "#2e86c1", "#7d3c98"]

# Fuentes para gráficos
FONT_FAMILY = "Montserrat, sans-serif"

# Tamaños de texto
TEXT_SIZE_LARGE = 22
TEXT_SIZE_MEDIUM = 18
TEXT_SIZE_SMALL = 14

# Configuración de reportes de jugador
FONT_LARGE = 72
MAX_NAME_WIDTH = 880

# Configuración de gráficos de tiro
CIRCLE_SIZE_PX = 40
PAD_UNITS = 0.05

# Dimensiones de gráficos
DEFAULT_WIDTH_PX = 2000
DEFAULT_HEIGHT_PX = 2000
DEFAULT_RESIZE_PX = 2000

# Configuración de barras clutch
MEDIA_WIDTH_Y = 0.90
CLUTCH_WIDTH_Y = 0.6
ROW_STEP = 2.0
CENTER_TOP = 10.0

# =============================================================================
# CONFIGURACIÓN DE CLUTCH TIME
# =============================================================================

# Nombres de columnas en clutch_aggregated.xlsx
CLUTCH_COLUMNS = {
    'games': 'GAMES',
    'fga': 'FGA',
    'fgm': 'FGM',
    'tpa': '3PA',
    'tpm': '3PM',
    'fta': 'FTA',
    'ftm': 'FTM',
    'min_clutch': 'MIN_CLUTCH',
    'jugador': 'JUGADOR'
}

# =============================================================================
# CONFIGURACIÓN DE EQUIPOS Y COMPETICIÓN
# =============================================================================

# Columnas importantes para agregación
TEAM_COLUMNS = ['FASE', 'JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL']
PLAYER_COLUMNS = ['DORSAL', 'FASE', 'IMAGEN', 'JUGADOR', 'EQUIPO LOCAL']

# Jornada por defecto para pruebas
JORNADA_DEFAULT_IDX = 5  # 0-based (corresponde a Jornada 6)

# =============================================================================
# FUNCIONES DE DETECCIÓN AUTOMÁTICA DE ARCHIVOS
# =============================================================================

def scan_available_files(file_pattern: str = "*") -> list:
    """
    Escanea el directorio data para encontrar archivos disponibles.
    Busca tanto en el directorio raíz como en subdirectorios (nueva estructura).
    
    Args:
        file_pattern: Patrón de archivos a buscar
    
    Returns:
        Lista de archivos encontrados con sus rutas completas
    """
    import glob
    
    files = []
    
    # Buscar en el directorio raíz (estructura antigua)
    pattern_root = str(DATA_DIR / f"{file_pattern}.xlsx")
    files_root = glob.glob(pattern_root)
    files.extend([Path(f).name for f in files_root])
    
    # Buscar en subdirectorios (nueva estructura)
    pattern_subdirs = str(DATA_DIR / f"*/{file_pattern}.xlsx")
    files_subdirs = glob.glob(pattern_subdirs)
    files.extend([str(Path(f).relative_to(DATA_DIR)) for f in files_subdirs])
    
    return files

def parse_filename_info(filename: str) -> dict:
    """
    Extrae información de temporada, liga y fases de un nombre de archivo.
    Maneja tanto la estructura antigua como la nueva con subdirectorios.
    
    Args:
        filename: Nombre del archivo o ruta relativa (ej: "3FEB_24_25/players_24_25_3FEB.xlsx")
    
    Returns:
        Dict con información extraída: {'tipo', 'liga', 'temporada', 'fases', 'path'}
    """
    import re
    
    # Determinar si es ruta con subdirectorio (nueva estructura) o archivo directo (antigua)
    if '/' in filename or '\\' in filename:
        # Nueva estructura: subdirectorio/archivo.xlsx
        path_parts = filename.replace('\\', '/').split('/')
        directory = path_parts[0]  # ej: "3FEB_24_25_j1"
        file_name = path_parts[-1]  # ej: "players_24_25_3FEB.xlsx"
        
        # Extraer info del directorio: liga_temporada[_jornadas]
        dir_match = re.match(r'(\w+FEB)_(\d{2}_\d{2})(?:_(.+))?', directory)
        if dir_match:
            liga = dir_match.group(1)
            temporada = dir_match.group(2)
            jornadas = dir_match.group(3) if dir_match.group(3) else None
        else:
            liga = '3FEB'  # Default
            temporada = '24_25'  # Default
            jornadas = None
        
        # Extraer tipo del nombre de archivo
        file_base = file_name.replace('.xlsx', '')
        tipo_patterns = {
            'jugadores_aggregated': r'players_',
            'teams_aggregated': r'teams_',
            'games_aggregated': r'games_',
            'boxscores': r'boxscores_',
            'assists': r'assists_',
            'clutch_data': r'clutch_data_',
            'clutch_aggregated': r'clutch_aggregated_',
            'clutch_lineups': r'clutch_lineups_',
            'clutch_season': r'clutch_season_'
        }
        
        tipo = None
        for tipo_key, pattern in tipo_patterns.items():
            if re.search(pattern, file_base):
                tipo = tipo_key
                break
        
        if not tipo:
            tipo = 'unknown'
            
        return {
            'tipo': tipo,
            'liga': liga,
            'temporada': temporada,
            'fases': [jornadas] if jornadas else [],
            'path': filename
        }
    
    else:
        # Estructura antigua: archivo directo
        # Eliminar extensión
        name = filename.replace('.xlsx', '')
        
        # Patrones más comprehensivos para todos los tipos de archivos
        # Primero intentamos patrones específicos con liga
        specific_patterns = {
            'jugadores_aggregated': r'players_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'teams_aggregated': r'teams_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'games_aggregated': r'games_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'boxscores': r'boxscores_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'assists': r'assists_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'clutch_aggregated': r'clutch_aggregated_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'clutch_lineups': r'clutch_lineups_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
            'clutch_season': r'clutch_season_(\d{2}_\d{2})_(\w+FEB)(?:_(.+))?',
        }
        
        # Patrones secundarios sin liga específica
        general_patterns = {
            'jugadores_aggregated': r'jugadores_aggregated_(\d{2}_\d{2})(?:_(.+))?',
            'teams_aggregated': r'teams_aggregated_(\d{2}_\d{2})(?:_(.+))?',
            'games_aggregated': r'games_aggregated_(\d{2}_\d{2})(?:_(.+))?',
            'boxscores': r'boxscores_(\d{2}_\d{2})(?:_(.+))?',
            'assists': r'assists_(\d{2}_\d{2})(?:_(.+))?',
            'clutch_aggregated': r'clutch_aggregated_(\d{2}_\d{2})(?:_(.+))?',
            'clutch_lineups': r'clutch_lineups_(\d{2}_\d{2})(?:_(.+))?',
            'clutch_season': r'clutch_season_(\d{2}_\d{2})(?:_(.+))?',
        }
        
        info = {'tipo': None, 'liga': None, 'temporada': None, 'fases': [], 'path': filename}
        
        # Intentar primero patrones específicos (con liga)
        for tipo, pattern in specific_patterns.items():
            match = re.match(pattern, name)
            if match:
                info['tipo'] = tipo
                info['temporada'] = match.group(1)  # temporada viene primero ahora
                info['liga'] = match.group(2)       # liga viene segundo ahora
                info['fases'] = match.group(3).split('_') if match.group(3) else []
                return info
        
        # Si no hay coincidencia, intentar patrones generales (sin liga)
        for tipo, pattern in general_patterns.items():
            match = re.match(pattern, name)
            if match:
                info['tipo'] = tipo
                info['liga'] = '3FEB'  # Default
                info['temporada'] = match.group(1)
                info['fases'] = match.group(2).split('_') if match.group(2) else []
                return info
        
        # Patrones de nombres sin temporada específica (archivos legacy)
        legacy_patterns = {
            'assists': r'^assists$',
            'jugadores_aggregated': r'^jugadores_aggregated_\d{2}_\d{2}$',
            'teams_aggregated': r'^teams_aggregated$',
            'games_aggregated': r'^games_aggregated$',
            'clutch_lineups': r'^clutch_lineups$',
            'clutch_season': r'^clutch_season_report$',
        }
        
        for tipo, pattern in legacy_patterns.items():
            if re.match(pattern, name):
                info['tipo'] = tipo if tipo != 'unknown' else 'unknown'
                info['liga'] = '3FEB'  # Default para archivos legacy
                info['temporada'] = '24_25'  # Default temporada actual
                info['fases'] = []
                return info
        
        # Si no coincide con nada, marcar como unknown
        info['tipo'] = 'unknown'
        info['liga'] = '3FEB'
        info['temporada'] = '24_25'
        
        return info

def get_available_seasons() -> list:
    """
    Obtiene todas las temporadas disponibles desde archivos existentes.
    
    Returns:
        Lista de temporadas en formato corto (ej: ['24_25', '23_24'])
    """
    files = scan_available_files("*")
    seasons = set()
    
    for file in files:
        info = parse_filename_info(file)
        if info['temporada']:
            seasons.add(info['temporada'])
    
    return sorted(list(seasons), reverse=True)  # Más reciente primero

def get_available_leagues() -> list:
    """
    Obtiene todas las ligas disponibles desde archivos existentes.
    
    Returns:
        Lista de ligas disponibles
    """
    files = scan_available_files("*")
    leagues = set()
    
    for file in files:
        info = parse_filename_info(file)
        if info['liga']:
            leagues.add(info['liga'])
    
    # Mapear códigos cortos a nombres completos
    league_map = {
        '1FEB': 'Primera FEB',
        '2FEB': 'Segunda FEB', 
        '3FEB': 'Tercera FEB'
    }
    
    full_names = []
    for league in leagues:
        full_name = league_map.get(league, league)
        full_names.append(full_name)
    
    return sorted(full_names)

def get_available_files_by_type(file_type: str, season: str = None, league: str = None) -> list:
    """
    Obtiene archivos disponibles de un tipo específico.
    
    Args:
        file_type: Tipo de archivo ('jugadores_aggregated', 'teams_aggregated', etc.)
        season: Filtrar por temporada (formato corto, ej: '24_25')
        league: Filtrar por liga (nombre completo, ej: 'Tercera FEB')
    
    Returns:
        Lista de archivos que coinciden con los filtros
    """
    # Ampliar búsqueda para diferentes patrones de nombres según el tipo
    search_patterns = {
        'jugadores_aggregated': ['jugadores_aggregated*', 'players_*'],
        'teams_aggregated': ['teams_aggregated*', 'teams_*'],
        'games_aggregated': ['games_aggregated*', 'games_*'],
        'boxscores': ['boxscores*'],
        'assists': ['assists*'],
        'clutch_data': ['clutch_data*'],
        'clutch_lineups': ['clutch_lineups*'],
        'clutch_season': ['clutch_season*']
    }
    
    patterns = search_patterns.get(file_type, [f"{file_type}*"])
    all_files = []
    
    # Buscar con todos los patrones posibles
    for pattern in patterns:
        files = scan_available_files(pattern)
        all_files.extend(files)
    
    # Remover duplicados manteniendo el orden
    seen = set()
    unique_files = []
    for file in all_files:
        if file not in seen:
            seen.add(file)
            unique_files.append(file)
    
    filtered_files = []
    
    # Mapear nombre de liga a código corto
    league_map = {
        'Primera FEB': '1FEB',
        'Segunda FEB': '2FEB',
        'Tercera FEB': '3FEB'
    }
    league_code = league_map.get(league) if league else None
    
    for file in unique_files:
        info = parse_filename_info(file)
        
        # Filtrar por tipo - incluir variaciones equivalentes
        if info['tipo'] != file_type and not (
            file_type == 'jugadores_aggregated' and info['tipo'] == 'jugadores_aggregated'
        ):
            continue
            
        # Filtrar por temporada si se especifica
        if season and info['temporada'] != season:
            continue
            
        # Filtrar por liga si se especifica
        if league_code and info['liga'] != league_code:
            continue
            
        filtered_files.append(file)
    
    return sorted(filtered_files, key=lambda x: (
        # Priorizar archivos sin _games para datos agregados
        '_games' in x if file_type == 'jugadores_aggregated' else False,
        # Priorizar estructura nueva sobre older
        'older' in x,
        # Orden alfabético inverso (más recientes primero)
        x
    ), reverse=False)  # Mejor prioridad primero

def find_best_file(file_type: str, season: str = None, league: str = None) -> Path:
    """
    Encuentra el mejor archivo disponible según los criterios especificados.
    
    Args:
        file_type: Tipo de archivo buscado
        season: Temporada preferida (formato corto)
        league: Liga preferida (nombre completo)
    
    Returns:
        Path del mejor archivo encontrado
    
    Raises:
        FileNotFoundError: Si no se encuentra ningún archivo
    """
    # Buscar archivos que coincidan exactamente
    files = get_available_files_by_type(file_type, season, league)
    
    if files:
        return DATA_DIR / files[0]
    
    # Si no hay coincidencia exacta, buscar sin filtros de liga
    files = get_available_files_by_type(file_type, season)
    if files:
        return DATA_DIR / files[0]
    
    # Si no hay coincidencia, buscar sin filtros de temporada
    files = get_available_files_by_type(file_type)
    if files:
        return DATA_DIR / files[0]
    
    # No se encontró ningún archivo
    raise FileNotFoundError(f"No se encontró ningún archivo de tipo '{file_type}'")

def season_short_to_full(season_short: str) -> str:
    """
    Convierte temporada de formato corto a completo.
    
    Args:
        season_short: Temporada en formato "24_25"
    
    Returns:
        Temporada en formato "2024/2025"
    """
    if "_" in season_short:
        years = season_short.split("_")
        return f"20{years[0]}/20{years[1]}"
    return season_short

# =============================================================================
# FUNCIONES DE UTILIDAD PARA RUTAS
# =============================================================================

def get_season_file(base_name: str, season: str = None) -> Path:
    """
    Genera el nombre de archivo con la temporada incluida.
    
    Args:
        base_name: Nombre base del archivo (ej: "jugadores_aggregated")
        season: Temporada (ej: "24_25"), por defecto usa TEMPORADA_CORTA
    
    Returns:
        Path del archivo con temporada
    """
    if season is None:
        season = TEMPORADA_CORTA
    return DATA_DIR / f"{base_name}_{season}.xlsx"

def ensure_directories():
    """Crea todos los directorios necesarios si no existen."""
    directories = [
        DATA_DIR,
        IMAGES_DIR,
        CLUBS_DIR,
        FLAGS_CACHE_DIR,
        TEMPLATES_DIR,
        OUTPUT_DIR,
        REPORTS_DIR,
        PLAYER_REPORTS_DIR,
        TEAM_REPORTS_DIR,
        PHASE_REPORTS_DIR,
        FONTS_DIR,
        LIB_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_phase_filter(phase_name: str = None) -> list:
    """
    Devuelve una lista con la fase especificada o la fase por defecto.
    
    Args:
        phase_name: Nombre de la fase, None para usar la por defecto
    
    Returns:
        Lista con la fase para filtrar
    """
    if phase_name is None:
        return [FASE_DEFAULT]
    return [phase_name]

def get_liga_config(liga_name: str) -> dict:
    """
    Obtiene la configuración de una liga específica.
    
    Args:
        liga_name: Nombre de la liga
    
    Returns:
        Diccionario con la configuración de la liga
    """
    return LIGAS_DISPONIBLES.get(liga_name, LIGAS_DISPONIBLES[LIGA_DEFAULT])

def get_liga_url(liga_name: str, year: int = 2024) -> str:
    """
    Genera la URL para una liga y año específicos.
    
    Args:
        liga_name: Nombre de la liga
        year: Año de la temporada
    
    Returns:
        URL completa para la liga
    """
    config = get_liga_config(liga_name)
    return config["url_template"].format(year=year)

def get_liga_fases(liga_name: str) -> list:
    """
    Obtiene las fases disponibles para una liga.
    
    Args:
        liga_name: Nombre de la liga
    
    Returns:
        Lista de fases disponibles para la liga
    """
    config = get_liga_config(liga_name)
    return config["fases"]

def get_liga_short_name(liga_name: str) -> str:
    """
    Obtiene el nombre corto de una liga.
    
    Args:
        liga_name: Nombre completo de la liga
    
    Returns:
        Nombre corto de la liga
    """
    config = get_liga_config(liga_name)
    return config["nombre_corto"]

def extract_phase_letters(phase_name: str) -> str:
    """
    Extrae las letras de la fase adaptándose a diferentes ligas.
    
    Args:
        phase_name: Nombre completo de la fase
    
    Returns:
        Solo las letras/identificador de la fase
    """
    import re
    
    # Para Tercera FEB: 'Liga Regular "B-A"' -> 'B-A'
    match = re.search(r'"([A-E]-[AB])"', phase_name)
    if match:
        return match.group(1)
    
    # Para Segunda FEB: 'Liga Regular "ESTE"' -> 'ESTE'
    match = re.search(r'"(ESTE|OESTE)"', phase_name)
    if match:
        return match.group(1)
    
    # Para Primera FEB: 'Liga Regular Único' -> 'UNICO'
    if "Único" in phase_name:
        return "UNICO"
    
    # Fallback: devolver el nombre completo
    return phase_name

def format_season_short(season_full: str) -> str:
    """
    Convierte temporada completa a formato corto.
    
    Args:
        season_full: Temporada en formato "2024/2025"
    
    Returns:
        Temporada en formato "24_25"
    """
    if "/" in season_full:
        years = season_full.split("/")
        return f"{years[0][-2:]}_{years[1][-2:]}"
    return season_full

def get_scraper_output_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para el scraper.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de salida
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"stats_games_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"stats_games_{season_short}_{phases_str}.xlsx"

def get_boxscores_output_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para boxscores completos.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de boxscores de salida
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"boxscores_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"boxscores_{season_short}_{phases_str}.xlsx"

def get_players_aggregated_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para jugadores agregados.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de jugadores agregados
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"jugadores_aggregated_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"jugadores_aggregated_{season_short}_{phases_str}.xlsx"

def get_teams_aggregated_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para equipos agregados.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de equipos agregados
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"teams_aggregated_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"teams_aggregated_{season_short}_{phases_str}.xlsx"

def get_games_aggregated_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para partidos agregados.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de partidos agregados
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"games_aggregated_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"games_aggregated_{season_short}_{phases_str}.xlsx"

def get_assists_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para asistencias.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de asistencias
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"assists_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"assists_{season_short}_{phases_str}.xlsx"

def get_clutch_season_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para datos de clutch por temporada.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de clutch por temporada
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"clutch_season_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"clutch_season_{season_short}_{phases_str}.xlsx"

def get_clutch_aggregated_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para clutch agregado por jugadores.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de clutch agregado
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"clutch_aggregated_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"clutch_aggregated_{season_short}_{phases_str}.xlsx"

def get_clutch_lineups_filename(season: str, phases: list, liga: str = None) -> str:
    """
    Genera nombre de archivo para clutch lineups.
    
    Args:
        season: Temporada (ej: "2024/2025")
        phases: Lista de fases seleccionadas
        liga: Nombre de la liga (ej: "Tercera FEB")
    
    Returns:
        Nombre del archivo de clutch lineups
    """
    season_short = format_season_short(season)
    phase_letters = [extract_phase_letters(phase) for phase in phases]
    phases_str = "_".join(phase_letters)
    
    if liga:
        liga_short = get_liga_short_name(liga)
        return f"clutch_lineups_{liga_short}_{season_short}_{phases_str}.xlsx"
    else:
        return f"clutch_lineups_{season_short}_{phases_str}.xlsx"

# =============================================================================
# VALIDACIÓN DE CONFIGURACIÓN
# =============================================================================

def validate_config():
    """Valida que la configuración sea consistente."""
    errors = []
    
    # Validar que las rutas importantes existan o se puedan crear
    try:
        ensure_directories()
    except Exception as e:
        errors.append(f"Error creando directorios: {e}")
    
    # Validar que las fases sean strings no vacías
    if not all(isinstance(fase, str) and fase.strip() for fase in FASES_PRINCIPALES):
        errors.append("Todas las fases deben ser strings no vacías")
    
    # Validar configuración de workers
    if not isinstance(MAX_WORKERS, int) or MAX_WORKERS < 1:
        errors.append("MAX_WORKERS debe ser un entero >= 1")
    
    if errors:
        raise ValueError("Errores de configuración:\n" + "\n".join(errors))
    
    return True

# Validar configuración al importar
if __name__ != "__main__":
    validate_config()