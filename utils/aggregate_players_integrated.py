# -*- coding: utf-8 -*-
"""
Agregador de estadísticas de jugadores - Versión integrada para scraper_app
===========================================================================

Versión modificada para trabajar con archivos de boxscores personalizados
y integrarse con la aplicación Streamlit.
"""

import pandas as pd
import numpy as np
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.scrape_player_bio import obtener_datos_jugador
from utils.web_scraping import accept_cookies, init_driver
from config import MAX_WORKERS_BIO, DATA_DIR, BIO_SCRAPE_ERRORS_LOG

def scrape_player_bio_parallel(players_data, max_workers=None, progress_callback=None):
    """
    Scrape biographical data for multiple players in parallel.
    
    Args:
        players_data: List of tuples (idx, jugador_nombre, url_jugador)
        max_workers: Number of parallel threads
        progress_callback: Function to call with progress updates
        
    Returns:
        dict: {idx: bio_data} mapping
    """
    if max_workers is None:
        max_workers = MAX_WORKERS_BIO
        
    results = {}
    results_lock = threading.Lock()
    error_log_lock = threading.Lock()
    
    def process_single_player(player_info):
        idx, jugador_nombre, url_jugador = player_info
        driver = None
        
        try:
            if progress_callback:
                progress_callback("info", f"📋 Procesando biografía: {jugador_nombre}")
                
            driver = init_driver()
            datos_bio = obtener_datos_jugador(driver, url_jugador)
            
            with results_lock:
                results[idx] = datos_bio
                
            if datos_bio['NOMBRE'] is None or datos_bio['NOMBRE'] == '':
                datos_bio['NOMBRE'] = jugador_nombre
                
            return idx, datos_bio
            
        except Exception as e:
            if progress_callback:
                progress_callback("warning", f"⚠️ Error obteniendo datos de {jugador_nombre}: {str(e)}")
            
            # Thread-safe error logging
            with error_log_lock:
                with open(BIO_SCRAPE_ERRORS_LOG, "a", encoding="utf-8") as logf:
                    logf.write(f"{jugador_nombre}\t{url_jugador}\t{str(e)}\n")
            
            return idx, {'NOMBRE': jugador_nombre, 'FECHA NACIMIENTO': None, 'NACIONALIDAD': None}
            
        finally:
            if driver:
                driver.quit()
    
    # Process players in parallel
    completed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_player = {
            executor.submit(process_single_player, player_info): player_info 
            for player_info in players_data
        }
        
        # Process completed tasks
        for future in as_completed(future_to_player):
            completed_count += 1
            try:
                idx, bio_data = future.result()
                if bio_data and progress_callback:
                    player_name = players_data[idx][1] if idx < len(players_data) else "Jugador"
                    progress_callback("success", f"✅ Biografía completada: {player_name} ({completed_count}/{len(players_data)})")
            except Exception as e:
                player_info = future_to_player[future]
                if progress_callback:
                    progress_callback("error", f"💥 Error crítico en biografía: {player_info[1]} - {e}")
    
    return results

def aggregate_players_stats(input_file_path, progress_callback=None):
    """
    Aggregates player statistics from the Excel file with parallel bio scraping.
    
    Args:
        input_file_path: Path to the boxscores Excel file
        progress_callback: Function to call with progress updates
        
    Returns:
        pandas.DataFrame: Aggregated player statistics
    """
    
    if progress_callback:
        progress_callback("info", f"📖 Leyendo datos de boxscores: {Path(input_file_path).name}")
    
    # Read the Excel file
    df = pd.read_excel(input_file_path)
    
    if progress_callback:
        progress_callback("info", f"📊 {len(df)} registros de boxscores cargados")
    
    # Define columns to sum
    sum_columns = [
        'MINUTOS JUGADOS', 'PUNTOS', 'T2 CONVERTIDO', 'T2 INTENTADO', 
        'T3 CONVERTIDO', 'T3 INTENTADO', 'TL CONVERTIDOS', 'TL INTENTADOS',
        'REB OFFENSIVO', 'REB DEFENSIVO', 'ASISTENCIAS', 'RECUPEROS', 
        'PERDIDAS', 'FaltasCOMETIDAS', 'FaltasRECIBIDAS'
    ]
    
    # Define columns to get first occurrence
    first_columns = ['DORSAL', 'FASE', 'IMAGEN', 'JUGADOR', 'EQUIPO LOCAL']
    
    # Check if all required columns exist
    missing_columns = []
    for col in sum_columns + first_columns + ['URL JUGADOR']:
        if col not in df.columns:
            missing_columns.append(col)
    
    if missing_columns:
        if progress_callback:
            progress_callback("warning", f"⚠️ Columnas faltantes: {missing_columns}")
        # Filter out missing columns
        sum_columns = [col for col in sum_columns if col in df.columns]
        first_columns = [col for col in first_columns if col in df.columns]
    
    # Create aggregation dictionary
    agg_dict = {}
    
    # Add sum aggregations
    for col in sum_columns:
        agg_dict[col] = 'sum'
    
    # Add first value aggregations
    for col in first_columns:
        agg_dict[col] = 'first'
    
    if progress_callback:
        progress_callback("info", "🔄 Agregando estadísticas por jugador...")
    
    # Group by URL JUGADOR
    aggregated_df = df.groupby(['URL JUGADOR']).agg(agg_dict).reset_index()
    
    # Add count for games played
    games_count = df.groupby(['URL JUGADOR']).size().reset_index(name='PJ')
    aggregated_df = aggregated_df.merge(games_count, on=['URL JUGADOR'], how='left')

    # 🚀 PARALLEL BIOGRAPHICAL DATA SCRAPING
    if progress_callback:
        progress_callback("info", "🧬 Iniciando extracción de datos biográficos...")
    
    # Crear columnas para datos biográficos
    bio_columns = ['NOMBRE', 'FECHA NACIMIENTO', 'NACIONALIDAD']
    for col in bio_columns:
        aggregated_df[col] = None
    
    # Prepare player data for parallel processing
    players_to_process = []
    for idx, row in aggregated_df.iterrows():
        url_jugador = row['URL JUGADOR']
        jugador_nombre = row['JUGADOR']
        
        if pd.notna(url_jugador):
            players_to_process.append((idx, jugador_nombre, url_jugador))
        else:
            if progress_callback:
                progress_callback("warning", f"⚠️ Sin URL para {jugador_nombre}")
    
    if progress_callback:
        progress_callback("info", f"👥 Procesando biografías de {len(players_to_process)} jugadores...")
    
    start_time = time.time()
    
    # Process players in parallel
    bio_results = scrape_player_bio_parallel(
        players_to_process, 
        max_workers=MAX_WORKERS_BIO,
        progress_callback=progress_callback
    )
    
    processing_time = time.time() - start_time
    if progress_callback:
        progress_callback("success", f"⚡ Biografías completadas en {processing_time:.2f}s ({len(players_to_process)/processing_time:.2f} jugadores/s)")
    
    # Apply the results to the DataFrame
    for idx, bio_data in bio_results.items():
        if bio_data:
            for key, value in bio_data.items():
                if key in bio_columns:
                    aggregated_df.at[idx, key] = value
    
    # Reorder columns
    # Si alguna fila tiene NOMBRE vacio, copiar el de JUGADOR
    aggregated_df['NOMBRE'] = aggregated_df['NOMBRE'].fillna(aggregated_df['JUGADOR'])
    
    column_order = ['NOMBRE'] + first_columns + ['PJ'] + sum_columns + bio_columns[1:] + ['URL JUGADOR']
    final_columns = [col for col in column_order if col in aggregated_df.columns]
    aggregated_df = aggregated_df[final_columns]
    
    # Rename column Local to 'EQUIPO' for consistency
    if 'EQUIPO LOCAL' in aggregated_df.columns:
        aggregated_df.rename(columns={'EQUIPO LOCAL': 'EQUIPO'}, inplace=True)
        
    if 'NOMBRE' in aggregated_df.columns:
        aggregated_df.rename(columns={'NOMBRE': 'JUGADOR'}, inplace=True)
    
    if progress_callback:
        progress_callback("success", f"✅ Agregación de jugadores completada: {len(aggregated_df)} jugadores")
    
    return aggregated_df

def save_aggregated_players(df, output_path, progress_callback=None):
    """
    Save the aggregated player data to an Excel file.
    
    Args:
        df (pandas.DataFrame): Aggregated data
        output_path (str): Path where to save the output file
        progress_callback: Function to call with progress updates
    """
    if progress_callback:
        progress_callback("info", f"💾 Guardando datos agregados de jugadores: {Path(output_path).name}")
    
    try:
        df.to_excel(output_path, index=False)
        if progress_callback:
            progress_callback("success", f"✅ Archivo de jugadores guardado: {Path(output_path).name}")
    except Exception as e:
        # Fallback path
        fallback_path = DATA_DIR / f"alt_{Path(output_path).name}"
        df.to_excel(fallback_path, index=False, engine='openpyxl')
        if progress_callback:
            progress_callback("warning", f"⚠️ Guardado en ruta alternativa: {fallback_path.name}")

def aggregate_players_main(input_boxscores_path, output_players_path, progress_callback=None):
    """
    Main function to execute the player aggregation process.
    
    Args:
        input_boxscores_path: Path to the boxscores Excel file
        output_players_path: Path to save the aggregated players file
        progress_callback: Function to call with progress updates
        
    Returns:
        pandas.DataFrame: Aggregated player data or None if error
    """
    try:
        # Aggregate the player statistics
        aggregated_df = aggregate_players_stats(input_boxscores_path, progress_callback)
        
        # Save the aggregated data
        save_aggregated_players(aggregated_df, output_players_path, progress_callback)
        
        return aggregated_df
        
    except FileNotFoundError:
        if progress_callback:
            progress_callback("error", f"❌ No se encontró el archivo: {input_boxscores_path}")
        return None
    except Exception as e:
        if progress_callback:
            progress_callback("error", f"❌ Error en agregación de jugadores: {str(e)}")
        return None

if __name__ == "__main__":
    # Standalone execution for testing
    def dummy_callback(msg_type, message):
        print(f"[{msg_type.upper()}] {message}")
    
    input_file = DATA_DIR / "boxscores_24_25_B-A_B-B.xlsx"
    output_file = DATA_DIR / "jugadores_aggregated_24_25_B-A_B-B.xlsx"
    
    result = aggregate_players_main(input_file, output_file, dummy_callback)
    if result is not None:
        print(f"✅ Agregación completada: {len(result)} jugadores")
    else:
        print("❌ Error en la agregación")