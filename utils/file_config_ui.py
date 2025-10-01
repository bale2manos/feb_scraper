# -*- coding: utf-8 -*-
"""
Interfaz de configuración de archivos para aplicaciones de reportes
==================================================================

Proporciona una interfaz consistente para seleccionar archivos de datos
en todas las aplicaciones de reportes.
"""

import streamlit as st
from pathlib import Path
import re
from config import (
    get_available_seasons,
    get_available_leagues, 
    get_available_files_by_type,
    find_best_file,
    season_short_to_full,
    DATA_DIR
)
from utils.filename_utils import get_liga_short, format_jornadas_display

def get_available_jornadas_options(season: str, league: str) -> dict:
    """
    Obtiene las opciones de jornadas disponibles para una temporada y liga.
    
    Args:
        season: Temporada (ej: "24_25")
        league: Liga (ej: "Primera FEB")
    
    Returns:
        Dict con opciones disponibles:
        {
            'all': Path,  # Carpeta con todas las jornadas
            'specific': {1: Path, 2: Path, ...}  # Carpetas con jornadas específicas
        }
    """
    liga_short = get_liga_short(league)
    options = {'all': None, 'specific': {}}
    
    # Buscar carpetas en DATA_DIR
    data_dir = Path(DATA_DIR)
    if not data_dir.exists():
        return options
    
    # Patrón para carpetas: LIGA_SEASON o LIGA_SEASON_jX
    base_pattern = f"{liga_short}_{season}"
    
    for folder in data_dir.iterdir():
        if not folder.is_dir():
            continue
            
        folder_name = folder.name
        
        # Carpeta con todas las jornadas (sin sufijo _j)
        if folder_name == base_pattern:
            options['all'] = folder
        
        # Carpetas con jornadas específicas (_jX o _jX_Y_Z)
        elif folder_name.startswith(f"{base_pattern}_j"):
            # Extraer números de jornada del sufijo
            jornada_part = folder_name[len(f"{base_pattern}_j"):]
            try:
                # Puede ser _j1 o _j1_2_3
                jornadas = [int(x) for x in jornada_part.split('_') if x.isdigit()]
                if jornadas:
                    # Usar la primera jornada como clave principal
                    key = jornadas[0] if len(jornadas) == 1 else tuple(sorted(jornadas))
                    options['specific'][key] = folder
            except ValueError:
                continue
    
    return options

def render_jornadas_selector(season: str, league: str, key_prefix: str) -> tuple:
    """
    Renderiza el selector de jornadas.
    
    Args:
        season: Temporada seleccionada
        league: Liga seleccionada
        key_prefix: Prefijo para las claves
    
    Returns:
        Tuple (jornadas_option, selected_folder)
        jornadas_option: 'all' o 'specific'
        selected_folder: Path de la carpeta seleccionada
    """
    jornadas_options = get_available_jornadas_options(season, league)
    
    # Inicializar session state
    if f"{key_prefix}_jornadas_option" not in st.session_state:
        st.session_state[f"{key_prefix}_jornadas_option"] = "all"
    
    # Verificar qué opciones están disponibles
    has_all = jornadas_options['all'] is not None
    has_specific = len(jornadas_options['specific']) > 0
    
    if not has_all and not has_specific:
        st.error(f"❌ No se encontraron datos para {league} - {season}")
        return None, None
    
    # Crear opciones para el radio button
    radio_options = []
    if has_all:
        radio_options.append("all")
    if has_specific:
        radio_options.append("specific")
    
    # Selector de tipo de jornadas
    col1, col2 = st.columns([1, 2])
    
    with col1:
        jornadas_option = st.radio(
            "📅 Jornadas:",
            options=radio_options,
            format_func=lambda x: {
                "all": "🔄 Todas las jornadas",
                "specific": "📌 Jornadas específicas"
            }.get(x, x),
            key=f"{key_prefix}_jornadas_radio",
            index=radio_options.index(st.session_state[f"{key_prefix}_jornadas_option"]) 
                  if st.session_state[f"{key_prefix}_jornadas_option"] in radio_options 
                  else 0
        )
        
        st.session_state[f"{key_prefix}_jornadas_option"] = jornadas_option
    
    with col2:
        if jornadas_option == "all":
            selected_folder = jornadas_options['all']
            if selected_folder:
                st.info(f"✅ Usando: `{selected_folder.name}`")
            else:
                st.error("❌ Carpeta 'todas las jornadas' no disponible")
        
        elif jornadas_option == "specific":
            if has_specific:
                # Crear opciones para el selectbox
                specific_options = []
                for key, folder in jornadas_options['specific'].items():
                    if isinstance(key, tuple):
                        display_name = f"Jornadas {', '.join(map(str, key))} ({folder.name})"
                    else:
                        display_name = f"Jornada {key} ({folder.name})"
                    specific_options.append((display_name, folder))
                
                if specific_options:
                    selected_display, selected_folder = st.selectbox(
                        "Selecciona jornada(s):",
                        options=specific_options,
                        format_func=lambda x: x[0],
                        key=f"{key_prefix}_specific_jornadas_select"
                    )
                    st.info(f"✅ Usando: `{selected_folder.name}`")
                else:
                    st.error("❌ No hay jornadas específicas disponibles")
                    selected_folder = None
            else:
                st.error("❌ No hay jornadas específicas disponibles")
                selected_folder = None
    
    return jornadas_option, selected_folder

def find_file_in_folder(folder: Path, file_type: str, season: str, league: str) -> Path:
    """
    Busca un archivo específico en una carpeta dada.
    
    Args:
        folder: Carpeta donde buscar
        file_type: Tipo de archivo a buscar
        season: Temporada
        league: Liga
    
    Returns:
        Path del archivo encontrado o None
    """
    if not folder or not folder.exists():
        return None
    
    liga_short = get_liga_short(league)
    
    # Mapeo de tipos de archivo a patrones de nombre
    file_patterns = {
        'jugadores_aggregated': f'players_{season}_{liga_short}.xlsx',
        'teams_aggregated': f'teams_{season}_{liga_short}.xlsx', 
        'clutch_aggregated': f'clutch_aggregated_{season}_{liga_short}.xlsx',
        'clutch_lineups': f'clutch_lineups_{season}_{liga_short}.xlsx',
        'assists': f'assists_{season}_{liga_short}.xlsx',
        'boxscores': f'boxscores_{season}_{liga_short}.xlsx',
        'clutch_data': f'clutch_data_{season}_{liga_short}.xlsx'
    }
    
    # Buscar archivo específico
    if file_type in file_patterns:
        file_path = folder / file_patterns[file_type]
        if file_path.exists():
            return file_path
    
    # Buscar por patrón más flexible
    for file in folder.glob("*.xlsx"):
        if file_type.replace('_aggregated', '') in file.name.lower():
            return file
    
    return None

def format_jornadas_display_from_folder(folder: Path) -> str:
    """
    Formatea la información de jornadas basada en el nombre de la carpeta.
    
    Args:
        folder: Carpeta de datos
    
    Returns:
        String describiendo las jornadas
    """
    if not folder:
        return "No definidas"
    
    folder_name = folder.name
    
    # Si tiene _j en el nombre, extraer las jornadas
    if '_j' in folder_name:
        # Extraer la parte después de _j
        jornada_part = folder_name.split('_j')[-1]
        try:
            jornadas = [int(x) for x in jornada_part.split('_') if x.isdigit()]
            if len(jornadas) == 1:
                return f"Jornada {jornadas[0]}"
            elif len(jornadas) > 1:
                return f"Jornadas {', '.join(map(str, sorted(jornadas)))}"
        except ValueError:
            pass
    
    return "Todas las jornadas"

def render_file_config_ui(file_types: list, key_prefix: str = "default") -> dict:
    """
    Renderiza la interfaz de configuración de archivos.
    
    Args:
        file_types: Lista de tipos de archivos necesarios 
                   (ej: ['jugadores_aggregated', 'teams_aggregated'])
        key_prefix: Prefijo para las claves de session_state
    
    Returns:
        Dict con las rutas de archivos seleccionados
    """
    
    # Inicializar session_state si no existe
    if f"{key_prefix}_season" not in st.session_state:
        seasons = get_available_seasons()
        st.session_state[f"{key_prefix}_season"] = seasons[0] if seasons else "24_25"
    
    if f"{key_prefix}_league" not in st.session_state:
        leagues = get_available_leagues()
        st.session_state[f"{key_prefix}_league"] = leagues[0] if leagues else "Tercera FEB"
    
    # Crear contenedor para configuración
    config_container = st.container()
    
    with config_container:
        st.subheader("⚙️ Configuración de Archivos de Datos")
        
        # Obtener datos disponibles
        available_seasons = get_available_seasons()
        available_leagues = get_available_leagues()
        
        if not available_seasons:
            st.error("❌ No se encontraron archivos de datos en el directorio ./data/")
            st.info("💡 Ejecuta primero el scraper para generar archivos de datos")
            st.stop()
        
        # Layout en columnas
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Selector de temporada
            selected_season = st.selectbox(
                "📅 Temporada:",
                options=available_seasons,
                index=available_seasons.index(st.session_state[f"{key_prefix}_season"]) 
                      if st.session_state[f"{key_prefix}_season"] in available_seasons else 0,
                key=f"{key_prefix}_season_select",
                help="Selecciona la temporada de los datos"
            )
            
            # Actualizar session_state
            st.session_state[f"{key_prefix}_season"] = selected_season
        
        with col2:
            # Selector de liga
            selected_league = st.selectbox(
                "🏀 Liga:",
                options=available_leagues,
                index=available_leagues.index(st.session_state[f"{key_prefix}_league"]) 
                      if st.session_state[f"{key_prefix}_league"] in available_leagues else 0,
                key=f"{key_prefix}_league_select",
                help="Selecciona la liga de los datos"
            )
            
            # Actualizar session_state
            st.session_state[f"{key_prefix}_league"] = selected_league
        
        # Selector de jornadas
        st.markdown("---")
        jornadas_option, selected_folder = render_jornadas_selector(
            selected_season, selected_league, key_prefix
        )
        
        if not selected_folder:
            st.error("❌ No se pudo seleccionar una carpeta de datos válida")
            st.stop()
        
        # Información sobre archivos
        st.markdown("---")
        st.write("**📊 Archivos que se utilizarán:**")
        
        # Encontrar archivos en la carpeta seleccionada
        file_paths = {}
        file_status = []
        
        for file_type in file_types:
            # Buscar archivo específico en la carpeta seleccionada
            file_path = find_file_in_folder(selected_folder, file_type, selected_season, selected_league)
            file_paths[file_type] = file_path
            
            # Verificar si el archivo existe
            if file_path and file_path.exists():
                file_status.append(f"✅ {file_path.name}")
            else:
                file_status.append(f"❌ {file_type}: No disponible en {selected_folder.name}")
        
        # Mostrar estado de archivos en columnas
        col1, col2 = st.columns(2)
        mid_point = len(file_status) // 2
        
        with col1:
            for status in file_status[:mid_point]:
                if "❌" in status:
                    st.error(status)
                else:
                    st.success(status)
        
        with col2:
            for status in file_status[mid_point:]:
                if "❌" in status:
                    st.error(status)
                else:
                    st.success(status)
        
        # Información adicional
        st.info(f"""
        📋 **Configuración actual:**
        - **Temporada:** {season_short_to_full(selected_season)}
        - **Liga:** {selected_league}
        - **Jornadas:** {format_jornadas_display_from_folder(selected_folder)}
        - **Archivos disponibles:** {len([p for p in file_paths.values() if p and p.exists()])} de {len(file_types)}
        """)
        
        # Verificar que todos los archivos necesarios estén disponibles
        missing_files = [ft for ft, path in file_paths.items() if not path or not path.exists()]
        
        if missing_files:
            st.error(f"❌ **Archivos faltantes:** {', '.join(missing_files)}")
            st.warning("⚠️ La aplicación podría no funcionar correctamente sin estos archivos.")
            
            with st.expander("🔧 Opciones de solución"):
                st.write("**Para resolver este problema:**")
                st.write("1. Ejecuta el scraper con la temporada, liga y jornadas seleccionadas")
                st.write("2. O selecciona una temporada/liga/jornadas diferente que tenga archivos disponibles")
                st.write("3. Verifica que los archivos estén en el directorio `./data/`")
        
        st.divider()
    
    return file_paths

def get_file_selector_for_type(file_type: str, season: str, league: str, key: str) -> Path:
    """
    Renderiza un selector específico para un tipo de archivo.
    
    Args:
        file_type: Tipo de archivo
        season: Temporada seleccionada
        league: Liga seleccionada  
        key: Clave única para el componente
    
    Returns:
        Path del archivo seleccionado
    """
    available_files = get_available_files_by_type(file_type, season, league)
    
    if not available_files:
        st.error(f"No hay archivos de tipo '{file_type}' disponibles")
        return None
    
    selected_file = st.selectbox(
        f"Archivo {file_type}:",
        options=available_files,
        key=key,
        help=f"Selecciona el archivo específico de {file_type}"
    )
    
    return DATA_DIR / selected_file

def validate_files(file_paths: dict) -> bool:
    """
    Valida que todos los archivos existan y sean accesibles.
    
    Args:
        file_paths: Dict con rutas de archivos
    
    Returns:
        True si todos los archivos son válidos
    """
    for file_type, path in file_paths.items():
        if not path or not path.exists():
            return False
        
        # Intentar leer el archivo para verificar que no esté corrupto
        try:
            import pandas as pd
            pd.read_excel(path, nrows=1)  # Leer solo la primera fila para validar
        except Exception as e:
            st.error(f"❌ Error leyendo {path.name}: {str(e)}")
            return False
    
    return True