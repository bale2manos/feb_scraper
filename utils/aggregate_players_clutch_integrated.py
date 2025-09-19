# -*- coding: utf-8 -*-
"""
Aggregate Players Clutch Integrado
===================================

Versión integrada para agregar estadísticas clutch a los datos de jugadores.
Combina datos de temporada regular con estadísticas de momentos clutch.
"""

import sys
import os
from typing import Callable, Optional
import pandas as pd
from pathlib import Path
import logging

# Configurar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging_clutch_agg(log_file: str = "aggregate_clutch.log") -> None:
    """Configura logging para la agregación clutch."""
    logger = logging.getLogger('aggregate_clutch')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers
    if logger.handlers:
        return
        
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def aggregate_clutch_to_players(
    players_file: str,
    clutch_file: str,
    output_file: str,
    progress_callback: Callable[[str, str], None] = None
) -> pd.DataFrame:
    """
    Agrega estadísticas clutch a los datos de jugadores.
    
    Args:
        players_file: Archivo con datos de jugadores (por juego)
        clutch_file: Archivo con datos clutch
        output_file: Archivo de salida
        progress_callback: Función para reportar progreso
    
    Returns:
        DataFrame con datos combinados
    """
    if progress_callback is None:
        progress_callback = lambda t, m: print(f"[{t}] {m}")
    
    # Configurar logging
    log_file = str(Path(output_file).parent / "aggregate_clutch.log")
    setup_logging_clutch_agg(log_file)
    logger = logging.getLogger('aggregate_clutch')
    
    progress_callback("info", "🔥 Iniciando agregación de datos clutch")
    logger.info("Starting clutch aggregation")
    
    try:
        # Cargar datos de jugadores
        progress_callback("info", "📖 Cargando datos de jugadores...")
        players_df = pd.read_excel(players_file)
        logger.info(f"Loaded {len(players_df)} player records")
        
        # Cargar datos clutch
        progress_callback("info", "🔥 Cargando datos clutch...")
        clutch_df = pd.read_excel(clutch_file)
        logger.info(f"Loaded {len(clutch_df)} clutch records")
        
        # Agregar estadísticas clutch por jugador
        progress_callback("info", "📊 Agregando estadísticas clutch por jugador...")
        
        clutch_agg = clutch_df.groupby(['JUGADOR', 'EQUIPO']).agg({
            'MINUTOS_CLUTCH': 'sum',
            'PUNTOS_CLUTCH': 'sum',
            'REBOTES_CLUTCH': 'sum',
            'ASISTENCIAS_CLUTCH': 'sum',
            'FG_MADE_CLUTCH': 'sum',
            'FG_ATT_CLUTCH': 'sum',
            'FT_MADE_CLUTCH': 'sum',
            'FT_ATT_CLUTCH': 'sum',
            'T3_MADE_CLUTCH': 'sum',
            'T3_ATT_CLUTCH': 'sum',
        }).reset_index()
        
        # Calcular porcentajes clutch
        clutch_agg['FG_PCT_CLUTCH'] = (clutch_agg['FG_MADE_CLUTCH'] / 
                                       clutch_agg['FG_ATT_CLUTCH'].replace(0, 1) * 100).round(1)
        clutch_agg['FT_PCT_CLUTCH'] = (clutch_agg['FT_MADE_CLUTCH'] / 
                                       clutch_agg['FT_ATT_CLUTCH'].replace(0, 1) * 100).round(1)
        clutch_agg['T3_PCT_CLUTCH'] = (clutch_agg['T3_MADE_CLUTCH'] / 
                                       clutch_agg['T3_ATT_CLUTCH'].replace(0, 1) * 100).round(1)
        
        # Agregar datos de jugadores por temporada
        progress_callback("info", "📈 Agregando estadísticas de temporada...")
        
        players_agg = players_df.groupby(['JUGADOR', 'EQUIPO']).agg({
            'PARTIDOS': 'sum',
            'MINUTOS': 'sum',
            'PUNTOS': 'sum',
            'REBOTES': 'sum',
            'ASISTENCIAS': 'sum',
            'FG_MADE': 'sum',
            'FG_ATT': 'sum',
            'FT_MADE': 'sum',
            'FT_ATT': 'sum',
            'T3_MADE': 'sum',
            'T3_ATT': 'sum',
            'ROBOS': 'sum',
            'PERDIDAS': 'sum',
            'TAPONES': 'sum',
            'FALTAS': 'sum',
            'VALORACION': 'sum',
        }).reset_index()
        
        # Calcular promedios por partido
        players_agg['MINUTOS_PPG'] = (players_agg['MINUTOS'] / players_agg['PARTIDOS']).round(1)
        players_agg['PUNTOS_PPG'] = (players_agg['PUNTOS'] / players_agg['PARTIDOS']).round(1)
        players_agg['REBOTES_PPG'] = (players_agg['REBOTES'] / players_agg['PARTIDOS']).round(1)
        players_agg['ASISTENCIAS_PPG'] = (players_agg['ASISTENCIAS'] / players_agg['PARTIDOS']).round(1)
        players_agg['VALORACION_PPG'] = (players_agg['VALORACION'] / players_agg['PARTIDOS']).round(1)
        
        # Calcular porcentajes de temporada
        players_agg['FG_PCT'] = (players_agg['FG_MADE'] / 
                                 players_agg['FG_ATT'].replace(0, 1) * 100).round(1)
        players_agg['FT_PCT'] = (players_agg['FT_MADE'] / 
                                 players_agg['FT_ATT'].replace(0, 1) * 100).round(1)
        players_agg['T3_PCT'] = (players_agg['T3_MADE'] / 
                                 players_agg['T3_ATT'].replace(0, 1) * 100).round(1)
        
        # Combinar datos
        progress_callback("info", "🔄 Combinando datos de temporada con clutch...")
        
        combined_df = players_agg.merge(
            clutch_agg,
            on=['JUGADOR', 'EQUIPO'],
            how='left'
        )
        
        # Rellenar valores nulos en columnas clutch
        clutch_columns = [col for col in combined_df.columns if 'CLUTCH' in col]
        combined_df[clutch_columns] = combined_df[clutch_columns].fillna(0)
        
        # Calcular ratios clutch vs regular
        progress_callback("info", "📊 Calculando ratios clutch...")
        
        # Ratio de efectividad clutch
        combined_df['CLUTCH_FG_RATIO'] = (
            (combined_df['FG_PCT_CLUTCH'] / combined_df['FG_PCT'].replace(0, 1))
            .replace([float('inf'), -float('inf')], 0).round(2)
        )
        
        combined_df['CLUTCH_EFFICIENCY'] = (
            (combined_df['PUNTOS_CLUTCH'] / combined_df['MINUTOS_CLUTCH'].replace(0, 1))
            .replace([float('inf'), -float('inf')], 0).round(2)
        )
        
        # Porcentaje de minutos clutch vs totales
        combined_df['PCT_MINUTOS_CLUTCH'] = (
            (combined_df['MINUTOS_CLUTCH'] / combined_df['MINUTOS'] * 100)
            .replace([float('inf'), -float('inf')], 0).round(1)
        )
        
        # Reordenar columnas
        column_order = [
            'JUGADOR', 'EQUIPO', 'PARTIDOS',
            # Estadísticas regulares
            'MINUTOS', 'PUNTOS', 'REBOTES', 'ASISTENCIAS', 'VALORACION',
            'FG_MADE', 'FG_ATT', 'FG_PCT',
            'FT_MADE', 'FT_ATT', 'FT_PCT',
            'T3_MADE', 'T3_ATT', 'T3_PCT',
            'ROBOS', 'PERDIDAS', 'TAPONES', 'FALTAS',
            # Promedios por partido
            'MINUTOS_PPG', 'PUNTOS_PPG', 'REBOTES_PPG', 'ASISTENCIAS_PPG', 'VALORACION_PPG',
            # Estadísticas clutch
            'MINUTOS_CLUTCH', 'PUNTOS_CLUTCH', 'REBOTES_CLUTCH', 'ASISTENCIAS_CLUTCH',
            'FG_MADE_CLUTCH', 'FG_ATT_CLUTCH', 'FG_PCT_CLUTCH',
            'FT_MADE_CLUTCH', 'FT_ATT_CLUTCH', 'FT_PCT_CLUTCH',
            'T3_MADE_CLUTCH', 'T3_ATT_CLUTCH', 'T3_PCT_CLUTCH',
            # Ratios y análisis
            'PCT_MINUTOS_CLUTCH', 'CLUTCH_FG_RATIO', 'CLUTCH_EFFICIENCY'
        ]
        
        # Reordenar solo las columnas que existen
        existing_columns = [col for col in column_order if col in combined_df.columns]
        combined_df = combined_df[existing_columns]
        
        # Guardar archivo
        progress_callback("info", "💾 Guardando archivo final...")
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_df.to_excel(output_file, index=False)
        
        progress_callback("success", f"✅ Agregación clutch completada: {len(combined_df)} jugadores")
        logger.info(f"Saved {len(combined_df)} players with clutch stats to {output_file}")
        
        return combined_df
        
    except Exception as e:
        error_msg = f"Error en agregación clutch: {str(e)}"
        progress_callback("error", f"❌ {error_msg}")
        logger.error(error_msg)
        raise

if __name__ == "__main__":
    # Test independiente
    players_file = "./data/jugadores_per_game_24_25.xlsx"
    clutch_file = "./data/clutch_season_test.xlsx"
    output_file = "./data/jugadores_clutch_aggregated_test.xlsx"
    
    df = aggregate_clutch_to_players(players_file, clutch_file, output_file)
    print(f"✅ Test completado: {len(df)} jugadores con stats clutch en {output_file}")