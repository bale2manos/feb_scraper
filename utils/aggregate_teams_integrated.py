# -*- coding: utf-8 -*-
"""
Agregador de estadísticas de equipos - Versión integrada para scraper_app
=========================================================================

Versión modificada para trabajar con archivos de boxscores personalizados
y integrarse con la aplicación Streamlit.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR

def aggregate_games(input_file_path, progress_callback=None):
    """
    Agrupa los datos de jugadores por equipo y fase, sumando las estadísticas de cada partido.
    
    Args:
        input_file_path: Ruta al archivo Excel con los datos de boxscores
        progress_callback: Function to call with progress updates
        
    Returns:
        DataFrame con los totales por equipo y fase (partidos agregados)
    """
    if progress_callback:
        progress_callback("info", f"📖 Leyendo boxscores para agregación de equipos: {Path(input_file_path).name}")
    
    # Leer el archivo Excel
    df = pd.read_excel(input_file_path)
    
    if progress_callback:
        progress_callback("info", f"📊 Procesando {len(df)} registros de boxscores")
        
    # Definir las columnas a sumar
    sum_columns = [
        'MINUTOS JUGADOS',
        'PUNTOS', 
        'T2 CONVERTIDO',
        'T2 INTENTADO',
        'T3 CONVERTIDO', 
        'T3 INTENTADO',
        'TL CONVERTIDOS',
        'TL INTENTADOS',
        'REB OFFENSIVO',
        'REB DEFENSIVO',
        'ASISTENCIAS',
        'RECUPEROS',
        'PERDIDAS',
        'FaltasCOMETIDAS',
        'FaltasRECIBIDAS'
    ]
    
    # Verificar columnas faltantes
    missing_columns = [col for col in sum_columns if col not in df.columns]
    if missing_columns and progress_callback:
        progress_callback("warning", f"⚠️ Columnas faltantes en agregación de equipos: {missing_columns}")
    
    # Filtrar solo columnas disponibles
    available_sum_columns = [col for col in sum_columns if col in df.columns]
    
    if progress_callback:
        progress_callback("info", "🔄 Agrupando por equipo y partido...")
    
    # Agrupar por Fase, Jornada, Equipo Local y Rival, sumar las columnas especificadas y el primer resultado de PTS_RIVAL
    if 'PTS_RIVAL' in df.columns:
        df['PTS_RIVAL'] = df['PTS_RIVAL'].astype(int)  # Asegurarse de que PTS_RIVAL es numérico
        agg_dict = {**{col: 'sum' for col in available_sum_columns}, 'PTS_RIVAL': 'first'}
    else:
        agg_dict = {col: 'sum' for col in available_sum_columns}
        if progress_callback:
            progress_callback("warning", "⚠️ Columna PTS_RIVAL no encontrada")
    
    games_df = df.groupby(['FASE', 'JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL'], as_index=False).agg(agg_dict)
    
    if progress_callback:
        progress_callback("info", "⚙️ Calculando métricas avanzadas...")
    
    # Calcular plays jugados por equipo
    games_df['PLAYS']= games_df['TL INTENTADOS']*0.44 + games_df['T2 INTENTADO'] + games_df['T3 INTENTADO'] + games_df['PERDIDAS']
    games_df['PPP'] = games_df['PUNTOS'] / games_df['PLAYS'].replace(0, pd.NA)  # Evitar división por cero
    games_df['POSS'] = games_df['PLAYS'] - games_df['REB OFFENSIVO']
    games_df['OFFRTG'] =  (100*games_df['PUNTOS']) / games_df['POSS'].replace(0, pd.NA)  # Calcular rating ofensivo

    # Calcular PPP del rival (opponent)
    # Para cada partido, encontrar los datos del equipo rival
    games_df['PPP OPP'] = pd.NA
    games_df['DEFRTG'] = pd.NA
    games_df['%OREB'] = pd.NA
    games_df['%DREB'] = pd.NA
    games_df['%REB'] = pd.NA

    if progress_callback:
        progress_callback("info", "🔄 Calculando estadísticas de rivales...")

    total_games = len(games_df)
    processed = 0
    
    for index, row in games_df.iterrows():
        processed += 1
        if progress_callback and processed % 50 == 0:  # Progress every 50 games
            progress_callback("info", f"📊 Procesando rivales: {processed}/{total_games}")
            
        fase = row['FASE']
        jornada = row['JORNADA']
        equipo_local = row['EQUIPO LOCAL']
        equipo_rival = row['EQUIPO RIVAL']
        team_def_rebound = row['REB DEFENSIVO']
        team_off_rebound = row['REB OFFENSIVO']
        team_total_rebound = team_def_rebound + team_off_rebound
        
        # Buscar la fila donde el equipo rival es el equipo local en el mismo partido
        opponent_row = games_df[
            (games_df['FASE'] == fase) & 
            (games_df['JORNADA'] == jornada) & 
            (games_df['EQUIPO LOCAL'] == equipo_rival) & 
            (games_df['EQUIPO RIVAL'] == equipo_local)
        ]
        
        if not opponent_row.empty:
            opp_offrebound = opponent_row.iloc[0]['REB OFFENSIVO']
            opp_defrebound = opponent_row.iloc[0]['REB DEFENSIVO']
            opp_total_rebound = opp_offrebound + opp_defrebound
            
            games_df.at[index, 'PPP OPP'] = opponent_row.iloc[0]['PPP']
            games_df.at[index, 'DEFRTG'] = opponent_row.iloc[0]['OFFRTG']
            games_df.at[index, '%OREB'] = team_off_rebound / (opp_defrebound + team_off_rebound) if opp_total_rebound > 0 else 0
            games_df.at[index, '%DREB'] = team_def_rebound / (opp_offrebound + team_def_rebound) if opp_total_rebound > 0 else 0
            games_df.at[index, '%REB'] = team_total_rebound / (opp_total_rebound + team_total_rebound) if opp_total_rebound > 0 else 0
    
    games_df['NETRTG'] = games_df['OFFRTG'] - games_df['DEFRTG']  # Calcular Net Rating

    if progress_callback:
        progress_callback("success", f"✅ Agregación de partidos completada: {len(games_df)} partidos")

    return games_df

def aggregate_teams(games_df, progress_callback=None):
    """
    Agrupa los datos de equipos, sumando las estadísticas de cada partido y contando el número de partidos jugados.
    
    Args:
        games_df: DataFrame con los datos agregados por partido
        progress_callback: Function to call with progress updates
        
    Returns:
        DataFrame con los totales por equipo
    """
    if progress_callback:
        progress_callback("info", "🏀 Agregando estadísticas por equipo...")
    
    not_sum_columns = ['FASE', 'JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL', 
                       'PPP', 'PPP OPP', 'OFFRTG', 'DEFRTG', 'NETRTG',
                       '%OREB', '%DREB', '%REB']
    
    # Agrupar por equipo y sumar las columnas especificadas
    aggregated = games_df.groupby('EQUIPO LOCAL').agg({
        'FASE': 'first',
        'PPP': 'mean',  # Promedio de PPP por equipo
        'PPP OPP': 'mean',  # Promedio de PPP del rival
        'OFFRTG': 'mean',  # Promedio de rating ofensivo
        'DEFRTG': 'mean',  # Promedio de rating defensivo
        'NETRTG': 'mean',  # Promedio de Net Rating
        '%OREB': 'mean',  # Promedio de %OREB
        '%DREB': 'mean',  # Promedio de %DREB
        '%REB': 'mean',  # Promedio de %REB

        **{col: 'sum' for col in games_df.columns if col in games_df.columns and col not in not_sum_columns}
    }).reset_index()
    
    # Contar el número de partidos jugados
    aggregated['PJ'] = games_df[games_df['EQUIPO LOCAL'].isin(aggregated['EQUIPO LOCAL'])].groupby('EQUIPO LOCAL').size().values
    
    # Rename columns for consistency
    rename_dict = {'EQUIPO LOCAL': 'EQUIPO'}
    if 'PTS_RIVAL' in aggregated.columns:
        rename_dict.update({'PTS_RIVAL': 'PUNTOS -', 'PUNTOS': 'PUNTOS +'})
    
    aggregated.rename(columns=rename_dict, inplace=True)

    if progress_callback:
        progress_callback("success", f"✅ Agregación de equipos completada: {len(aggregated)} equipos")

    return aggregated

def save_aggregated_teams(games_df, teams_df, games_output_path, teams_output_path, progress_callback=None):
    """
    Save both aggregated DataFrames to Excel files.
    
    Args:
        games_df: DataFrame with games aggregated data
        teams_df: DataFrame with teams aggregated data
        games_output_path: Path to save games file
        teams_output_path: Path to save teams file
        progress_callback: Function to call with progress updates
    """
    try:
        if progress_callback:
            progress_callback("info", f"💾 Guardando agregación de partidos: {Path(games_output_path).name}")
        games_df.to_excel(games_output_path, index=False)
        
        if progress_callback:
            progress_callback("info", f"💾 Guardando agregación de equipos: {Path(teams_output_path).name}")
        teams_df.to_excel(teams_output_path, index=False)
        
        if progress_callback:
            progress_callback("success", "✅ Archivos de equipos y partidos guardados correctamente")
            
    except Exception as e:
        if progress_callback:
            progress_callback("error", f"❌ Error guardando archivos de equipos: {str(e)}")
        raise

def aggregate_teams_main(input_boxscores_path, games_output_path, teams_output_path, progress_callback=None):
    """
    Main function to execute the teams aggregation process.
    
    Args:
        input_boxscores_path: Path to the boxscores Excel file
        games_output_path: Path to save the aggregated games file
        teams_output_path: Path to save the aggregated teams file
        progress_callback: Function to call with progress updates
        
    Returns:
        tuple: (games_df, teams_df) or (None, None) if error
    """
    try:
        # Aggregate games data
        games_df = aggregate_games(input_boxscores_path, progress_callback)
        
        # Aggregate teams data
        teams_df = aggregate_teams(games_df, progress_callback)
        
        # Save both DataFrames
        save_aggregated_teams(games_df, teams_df, games_output_path, teams_output_path, progress_callback)
        
        return games_df, teams_df
        
    except FileNotFoundError:
        if progress_callback:
            progress_callback("error", f"❌ No se encontró el archivo: {input_boxscores_path}")
        return None, None
    except Exception as e:
        if progress_callback:
            progress_callback("error", f"❌ Error en agregación de equipos: {str(e)}")
        return None, None

if __name__ == "__main__":
    # Standalone execution for testing
    def dummy_callback(msg_type, message):
        print(f"[{msg_type.upper()}] {message}")
    
    input_file = DATA_DIR / "boxscores_24_25_B-A_B-B.xlsx"
    games_file = DATA_DIR / "games_aggregated_24_25_B-A_B-B.xlsx"
    teams_file = DATA_DIR / "teams_aggregated_24_25_B-A_B-B.xlsx"
    
    games_result, teams_result = aggregate_teams_main(input_file, games_file, teams_file, dummy_callback)
    if games_result is not None and teams_result is not None:
        print(f"✅ Agregación completada: {len(games_result)} partidos, {len(teams_result)} equipos")
    else:
        print("❌ Error en la agregación")