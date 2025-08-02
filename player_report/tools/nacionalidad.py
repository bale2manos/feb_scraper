# -*- coding: utf-8 -*-
"""
Módulo para procesamiento de nacionalidades y banderas
====================================================

Este módulo maneja la carga de datos de países, mapeo de nacionalidades
y conversión de banderas SVG a imágenes PIL con sistema de caché local.

Funciones principales:
    - load_countries_data(): Carga datos de países desde JSON
    - get_country_data(): Obtiene datos de país por nacionalidad
    - download_and_convert_flag_svg(): Descarga y convierte banderas SVG
    - get_country_flag_image(): Función principal para obtener bandera como PIL Image

"""
import json
import io
import pandas as pd
import requests
import cairosvg
from pathlib import Path
from PIL import Image

# === RUTAS ===
COUNTRIES_PATH = Path("images/countries.json")
FLAGS_CACHE_PATH = Path("images/flags_cache/")

# Crear directorio de caché si no existe
FLAGS_CACHE_PATH.mkdir(parents=True, exist_ok=True)


def load_countries_data():
    """
    Load countries data from JSON file.
    
    Returns:
        dict: Dictionary mapping country names (uppercase) to country data
    """
    try:
        with open(COUNTRIES_PATH, 'r', encoding='utf-8') as f:
            countries_list = json.load(f)
        
        # Create a mapping from uppercase country names to country data
        countries_dict = {}
        for country in countries_list:
            country_name = country['country'].upper()
            countries_dict[country_name] = country
            
        return countries_dict
    except FileNotFoundError:
        print(f"⚠️ Countries file not found at {COUNTRIES_PATH}")
        return {}
    except json.JSONDecodeError:
        print(f"⚠️ Error parsing countries JSON file")
        return {}


def get_country_data(nationality, countries_data=None):
    """
    Get country data based on nationality for flag processing.
    
    Args:
        nationality: Player's nationality (e.g., "España", "Francia")
        countries_data: Pre-loaded countries dictionary (optional)
        
    Returns:
        dict: Contains 'flag_url', 'code' or None if not found
    """
    if not nationality or pd.isna(nationality):
        return None

    if countries_data is None:
        countries_data = load_countries_data()
    
    # Convert nationality to uppercase for matching
    nationality_upper = nationality.upper().strip()
    
    # Direct match
    if nationality_upper in countries_data:
        country = countries_data[nationality_upper]
        return {
            'flag_url': country.get('flag', ''),
            'code': country.get('code', '')
        }

    # Try partial matches for common variations
    nationality_variations = {
        'ESPAÑA': 'ESPAÑA',
        'SPAIN': 'ESPAÑA', 
        'FRANCE': 'FRANCIA',
        'USA': 'ESTADOS UNIDOS',
        'UNITED STATES': 'ESTADOS UNIDOS',
        'UK': 'REINO UNIDO',
        'ENGLAND': 'REINO UNIDO',
        'GREAT BRITAIN': 'REINO UNIDO'
    }
    
    if nationality_upper in nationality_variations:
        mapped_nationality = nationality_variations[nationality_upper]
        if mapped_nationality in countries_data:
            country = countries_data[mapped_nationality]
            return {
                'flag_url': country.get('flag', ''),
                'code': country.get('code', '')
            }
    
    # If no exact match, try partial search
    for country_name, country_data in countries_data.items():
        if nationality_upper in country_name or country_name in nationality_upper:
            return {
                'flag_url': country_data.get('flag', ''),
                'code': country_data.get('code', '')
            }
    
    return None


def download_and_convert_flag_svg(flag_url, size=(50, 40), country_code=""):
    """
    Download SVG flag and convert it to PIL Image with local caching.
    
    Args:
        flag_url: URL of the SVG flag
        size: Tuple (width, height) for the flag size
        country_code: Country code for cache filename
        
    Returns:
        PIL Image or None if failed
    """
    try:
        # Check if cached version exists
        cache_filename = f"{country_code.lower()}_{size[0]}x{size[1]}.png"
        cache_path = FLAGS_CACHE_PATH / cache_filename
        
        if cache_path.exists():
            # Load from cache
            return Image.open(cache_path).convert('RGBA')
        
        # Download SVG
        print(f"📥 Downloading flag from {flag_url}")
        response = requests.get(flag_url, timeout=10)
        response.raise_for_status()
        
        # Convert SVG to PNG bytes
        png_bytes = cairosvg.svg2png(
            bytestring=response.content,
            output_width=size[0],
            output_height=size[1]
        )
        
        # Convert to PIL Image
        flag_image = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        
        # Save to cache
        flag_image.save(cache_path, 'PNG')
        print(f"💾 Flag cached at {cache_path}")
        
        return flag_image
        
    except Exception as e:
        print(f"⚠️ Error downloading/converting flag from {flag_url}: {e}")
        return None


def get_country_flag_image(nationality, countries_data=None, flag_size=(40, 30)):
    """
    Get country flag as PIL Image based on nationality.
    
    Args:
        nationality: Player's nationality
        countries_data: Pre-loaded countries dictionary
        flag_size: Tuple (width, height) for flag size
        
    Returns:
        PIL Image or None if not found
    """
    country_info = get_country_data(nationality, countries_data)
    
    if pd.isna(country_info) or not country_info:
        return None
        
    flag_url = country_info.get('flag_url', '')
    country_code = country_info.get('code', '')
    
    if not flag_url:
        return None
        
    return download_and_convert_flag_svg(flag_url, flag_size, country_code)
