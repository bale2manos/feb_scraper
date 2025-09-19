# -*- coding: utf-8 -*-
"""
Utility functions for filename generation with jornada support.
"""

import os
from typing import List, Optional


def generate_filename_with_jornadas(
    base_filename: str,
    selected_jornadas: Optional[List[int]] = None,
    extension: str = ".xlsx"
) -> str:
    """
    Genera un nombre de archivo con sufijo de jornadas si están seleccionadas.
    
    Args:
        base_filename: Nombre base del archivo (sin extensión)
        selected_jornadas: Lista de jornadas seleccionadas o None para todas
        extension: Extensión del archivo (por defecto .xlsx)
    
    Returns:
        Nombre de archivo completo con sufijo de jornadas si aplica
    
    Examples:
        >>> generate_filename_with_jornadas("boxscores_24_25_BA_BB_3FEB")
        "boxscores_24_25_BA_BB_3FEB.xlsx"
        
        >>> generate_filename_with_jornadas("boxscores_24_25_BA_BB_3FEB", [1, 2, 3])
        "boxscores_24_25_BA_BB_3FEB_j1_2_3.xlsx"
        
        >>> generate_filename_with_jornadas("assists_24_25_BA_BB_3FEB", [5])
        "assists_24_25_BA_BB_3FEB_j5.xlsx"
    """
    if selected_jornadas and len(selected_jornadas) > 0:
        # Crear sufijo con jornadas seleccionadas
        jornadas_str = "_".join(map(str, sorted(selected_jornadas)))
        filename = f"{base_filename}_j{jornadas_str}{extension}"
    else:
        # Sin jornadas seleccionadas, usar nombre base
        filename = f"{base_filename}{extension}"
    
    return filename


def generate_all_filenames_with_jornadas(
    base_path: str,
    temporada_short: str,
    liga_short: str,
    selected_jornadas: Optional[List[int]] = None
) -> dict:
    """
    Genera todos los nombres de archivo necesarios para el pipeline con sufijo de jornadas.
    Estructura nueva: data/category_season_groups_jornada/*.xlsx
    
    Args:
        base_path: Ruta base donde guardar los archivos
        temporada_short: Temporada abreviada (ej: "24_25")
        liga_short: Liga abreviada (ej: "3FEB", "2FEB", "1FEB")
        selected_jornadas: Lista de jornadas seleccionadas o None
    
    Returns:
        Diccionario con todas las rutas de archivos
    """
    # Generar sufijo de jornadas para el directorio
    if selected_jornadas and len(selected_jornadas) > 0:
        jornadas_str = "_".join(map(str, sorted(selected_jornadas)))
        jornadas_suffix = f"_j{jornadas_str}"
    else:
        jornadas_suffix = ""
    
    # Crear directorio con estructura: data/category_season_groups_jornada/
    directory_name = f"{liga_short}_{temporada_short}{jornadas_suffix}"
    target_directory = os.path.join(base_path, directory_name)
    
    # Crear directorio si no existe
    os.makedirs(target_directory, exist_ok=True)
    
    # Generar nombres individuales (sin sufijo de jornadas en el nombre, ya está en el directorio)
    base_name = f"{temporada_short}_{liga_short}"
    
    filenames = {
        "boxscores": f"boxscores_{base_name}.xlsx",
        "assists": f"assists_{base_name}.xlsx",
        "clutch_data": f"clutch_data_{base_name}.xlsx",
        "clutch_lineups": f"clutch_lineups_{base_name}.xlsx",
        "clutch_aggregated": f"clutch_aggregated_{base_name}.xlsx",
        "players": f"players_{base_name}.xlsx",
        "teams": f"teams_{base_name}.xlsx",
    }
    
    # Generar rutas completas dentro del directorio específico
    paths = {}
    for key, filename in filenames.items():
        paths[key] = os.path.join(target_directory, filename)
    
    return paths


def format_jornadas_display(selected_jornadas: Optional[List[int]]) -> str:
    """
    Formatea la lista de jornadas para mostrar en la UI.
    
    Args:
        selected_jornadas: Lista de jornadas seleccionadas o None
    
    Returns:
        String formateado para mostrar
    
    Examples:
        >>> format_jornadas_display(None)
        "todas las jornadas"
        
        >>> format_jornadas_display([1, 2, 3])
        "jornadas 1, 2, 3"
        
        >>> format_jornadas_display([5])
        "jornada 5"
    """
    if not selected_jornadas or len(selected_jornadas) == 0:
        return "todas las jornadas"
    elif len(selected_jornadas) == 1:
        return f"jornada {selected_jornadas[0]}"
    else:
        return f"jornadas {', '.join(map(str, sorted(selected_jornadas)))}"


def get_jornadas_suffix(selected_jornadas: Optional[List[int]]) -> str:
    """
    Obtiene solo el sufijo de jornadas para añadir a nombres.
    
    Args:
        selected_jornadas: Lista de jornadas seleccionadas o None
    
    Returns:
        Sufijo para añadir (incluye _ inicial si hay jornadas)
    
    Examples:
        >>> get_jornadas_suffix(None)
        ""
        
        >>> get_jornadas_suffix([1, 2, 3])
        "_j1_2_3"
        
        >>> get_jornadas_suffix([5])
        "_j5"
    """
    if selected_jornadas and len(selected_jornadas) > 0:
        jornadas_str = "_".join(map(str, sorted(selected_jornadas)))
        return f"_j{jornadas_str}"
    else:
        return ""


# Mapeo de ligas para nombres cortos
LIGA_SHORT_MAPPING = {
    "Primera FEB": "1FEB",
    "Segunda FEB": "2FEB", 
    "Tercera FEB": "3FEB"
}

def get_liga_short(liga_name: str) -> str:
    """
    Obtiene la abreviación de la liga.
    
    Args:
        liga_name: Nombre completo de la liga
    
    Returns:
        Abreviación de la liga
    """
    return LIGA_SHORT_MAPPING.get(liga_name, liga_name.replace(" ", "")[:4])