# -*- coding: utf-8 -*-
"""
Interfaz de configuración de archivos para aplicaciones de reportes
==================================================================

Proporciona una interfaz consistente para seleccionar archivos de datos
en todas las aplicaciones de reportes.
"""

import streamlit as st
from pathlib import Path
from config import (
    get_available_seasons,
    get_available_leagues, 
    get_available_files_by_type,
    find_best_file,
    season_short_to_full,
    DATA_DIR
)

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
        col1, col2, col3 = st.columns([1, 1, 2])
        
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
        
        with col3:
            # Información sobre archivos
            st.write("**📊 Archivos que se utilizarán:**")
            
            # Encontrar y mostrar archivos para cada tipo
            file_paths = {}
            file_status = []
            
            for file_type in file_types:
                try:
                    file_path = find_best_file(file_type, selected_season, selected_league)
                    file_paths[file_type] = file_path
                    
                    # Verificar si el archivo existe
                    if file_path.exists():
                        file_status.append(f"✅ {file_path.name}")
                    else:
                        file_status.append(f"❌ {file_path.name} (no encontrado)")
                        
                except FileNotFoundError:
                    file_status.append(f"❌ {file_type}: No disponible")
                    file_paths[file_type] = None
            
            # Mostrar estado de archivos
            for status in file_status:
                if "❌" in status:
                    st.error(status)
                else:
                    st.success(status)
        
        # Información adicional
        st.info(f"""
        📋 **Configuración actual:**
        - **Temporada:** {season_short_to_full(selected_season)}
        - **Liga:** {selected_league}
        - **Archivos disponibles:** {len([p for p in file_paths.values() if p and p.exists()])} de {len(file_types)}
        """)
        
        # Verificar que todos los archivos necesarios estén disponibles
        missing_files = [ft for ft, path in file_paths.items() if not path or not path.exists()]
        
        if missing_files:
            st.error(f"❌ **Archivos faltantes:** {', '.join(missing_files)}")
            st.warning("⚠️ La aplicación podría no funcionar correctamente sin estos archivos.")
            
            with st.expander("🔧 Opciones de solución"):
                st.write("**Para resolver este problema:**")
                st.write("1. Ejecuta el scraper con la temporada y liga seleccionadas")
                st.write("2. O selecciona una temporada/liga diferente que tenga archivos disponibles")
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