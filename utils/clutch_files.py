#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades para archivos clutch en player report
==============================================
Maneja la búsqueda de archivos clutch alternativos
"""

from config import (
    get_available_files_by_type, 
    find_best_file, 
    DATA_DIR
)

def find_best_clutch_file(season: str = None, league: str = None):
    """
    Encuentra el mejor archivo clutch disponible.
    Prueba diferentes tipos de archivos clutch en orden de preferencia.
    
    Args:
        season: Temporada (formato corto)
        league: Liga (nombre completo)
    
    Returns:
        Path del mejor archivo clutch o None si no encuentra ninguno
    """
    # Orden de preferencia para archivos clutch
    clutch_types = ['clutch_data', 'clutch_season', 'clutch_lineups']
    
    for clutch_type in clutch_types:
        try:
            best_file = find_best_file(clutch_type, season, league)
            if best_file.exists():
                return best_file
        except FileNotFoundError:
            continue
    
    return None

def get_available_clutch_info(season: str = None, league: str = None):
    """
    Obtiene información sobre archivos clutch disponibles.
    
    Returns:
        dict con información sobre archivos clutch disponibles
    """
    clutch_types = ['clutch_data', 'clutch_season', 'clutch_lineups']
    available = {}
    
    for clutch_type in clutch_types:
        try:
            files = get_available_files_by_type(clutch_type, season, league)
            if files:
                best_file = find_best_file(clutch_type, season, league)
                available[clutch_type] = {
                    'file': best_file,
                    'relative_path': best_file.relative_to(DATA_DIR) if best_file.is_relative_to(DATA_DIR) else best_file,
                    'exists': best_file.exists()
                }
        except FileNotFoundError:
            continue
    
    return available

if __name__ == "__main__":
    # Prueba de las funciones
    print("🔍 PROBANDO BÚSQUEDA DE ARCHIVOS CLUTCH")
    print("=" * 45)
    
    from config import get_available_seasons, get_available_leagues
    
    seasons = get_available_seasons()
    leagues = get_available_leagues()
    
    for season in seasons:
        for league in leagues:
            print(f"\n🎯 {league} {season}:")
            
            # Buscar mejor archivo clutch
            best_clutch = find_best_clutch_file(season, league)
            if best_clutch:
                relative_path = best_clutch.relative_to(DATA_DIR) if best_clutch.is_relative_to(DATA_DIR) else best_clutch
                print(f"   ✅ Mejor clutch: {relative_path}")
            else:
                print(f"   ❌ No hay archivos clutch disponibles")
            
            # Mostrar todos los archivos clutch disponibles
            clutch_info = get_available_clutch_info(season, league)
            if clutch_info:
                print(f"   📊 Archivos clutch disponibles:")
                for clutch_type, info in clutch_info.items():
                    status = "✅" if info['exists'] else "❌"
                    print(f"      {status} {clutch_type}: {info['relative_path']}")
            else:
                print(f"   📊 No hay archivos clutch para esta configuración")