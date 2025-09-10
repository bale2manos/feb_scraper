import pandas as pd
import numpy as np
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.scrape_player_bio import obtener_datos_jugador
from utils.web_scraping import accept_cookies, init_driver

def scrape_player_bio_parallel(players_data, max_workers=4):
    """
    Scrape biographical data for multiple players in parallel.
    
    Args:
        players_data: List of tuples (idx, jugador_nombre, url_jugador)
        max_workers: Number of parallel threads
        
    Returns:
        dict: {idx: bio_data} mapping
    """
    results = {}
    results_lock = threading.Lock()
    error_log_lock = threading.Lock()
    
    def process_single_player(player_info):
        idx, jugador_nombre, url_jugador = player_info
        driver = None
        
        try:
            print(f"  📋 Procesando: {jugador_nombre}")
            driver = init_driver()
            datos_bio = obtener_datos_jugador(driver, url_jugador)
            
            with results_lock:
                results[idx] = datos_bio
                
            if datos_bio['NOMBRE'] is None or datos_bio['NOMBRE'] == '':
                datos_bio['NOMBRE'] = jugador_nombre
                
            return idx, datos_bio
            
        except Exception:
            print(f"  ❌ Error obteniendo datos de {jugador_nombre}")
            
            # Thread-safe error logging
            with error_log_lock:
                with open("bio_scrape_errors.log", "a", encoding="utf-8") as logf:
                    logf.write(f"{jugador_nombre}\t{url_jugador}\n")
            
            return idx, [jugador_nombre,None, None]
            
        finally:
            if driver:
                driver.quit()
    
    # Process players in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_player = {
            executor.submit(process_single_player, player_info): player_info 
            for player_info in players_data
        }
        
        # Process completed tasks
        for future in as_completed(future_to_player):
            try:
                idx, bio_data = future.result()
                if bio_data:
                    print(f"  ✅ Completado: {players_data[idx][1]}")
            except Exception as e:
                player_info = future_to_player[future]
                print(f"  💥 Falló completamente: {player_info[1]} - {e}")
    
    return results

def aggregate_players_stats(file_path='./data/jugadores_per_game.xlsx'):
    """
    Aggregates player statistics from the Excel file with parallel bio scraping.
    """
    
    # Read the Excel file
    print(f"Reading data from {file_path}...")
    df = pd.read_excel(file_path)
    
    # Print column names to verify they match expected format
    print("Columns in the file:")
    print(df.columns.tolist())
    
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
        print(f"Warning: Missing columns: {missing_columns}")
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
    
    print("Aggregating data by URL JUGADOR...")
    
    # Group by URL JUGADOR
    aggregated_df = df.groupby(['URL JUGADOR']).agg(agg_dict).reset_index()
    
    # Add count for games played
    games_count = df.groupby(['URL JUGADOR']).size().reset_index(name='PJ')
    aggregated_df = aggregated_df.merge(games_count, on=['URL JUGADOR'], how='left')

    # 🚀 PARALLEL BIOGRAPHICAL DATA SCRAPING
    print("Obteniendo datos biográficos de jugadores (paralelo)...")
    
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
            print(f"  ⚠️  Sin URL para {jugador_nombre}")
    
    print(f"📊 Procesando {len(players_to_process)} jugadores en paralelo...")
    start_time = time.time()
    
    # Process players in parallel (adjust max_workers based on your system)
    bio_results = scrape_player_bio_parallel(players_to_process, max_workers=6)
    
    processing_time = time.time() - start_time
    print(f"⏱️  Scraping biográfico completado en {processing_time:.2f} segundos")
    print(f"⚡ Velocidad: {len(players_to_process)/processing_time:.2f} jugadores/segundo")
    
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
    
    print(f"Aggregation complete. Results for {len(aggregated_df)} players.")
    print(f"✅ Datos biográficos obtenidos para {len(bio_results)} jugadores")
    
    return aggregated_df

def save_aggregated_data(df, output_path='./data/jugadores_aggregated_24_25.xlsx'):
    """
    Save the aggregated data to an Excel file.
    
    Args:
        df (pandas.DataFrame): Aggregated data
        output_path (str): Path where to save the output file
    """
    print(f"Saving aggregated data to {output_path}...")
    try:
        df.to_excel(output_path, index=False)
    except Exception as e:
        df.to_excel('./data/alt_jugadores_aggregated_24_25.xlsx', index=False, engine='openpyxl')
    print("Data saved successfully!")

def display_summary(df):
    """
    Display a summary of the aggregated data.
    
    Args:
        df (pandas.DataFrame): Aggregated data
    """
    print("\n" + "="*50)
    print("AGGREGATED PLAYERS STATISTICS SUMMARY")
    print("="*50)
    
    print(f"Total number of players: {len(df)}")
    print(f"Columns in aggregated data: {len(df.columns)}")
    
    if 'PJ' in df.columns:
        print(f"Average games per player: {df['PJ'].mean():.2f}")
        print(f"Max games played: {df['PJ'].max()}")
        print(f"Min games played: {df['PJ'].min()}")
    
    if 'PUNTOS' in df.columns:
        print(f"Total points scored: {df['PUNTOS'].sum()}")
        print(f"Average points per player: {df['PUNTOS'].mean():.2f}")
    
    if 'MINUTOS JUGADOS' in df.columns:
        print(f"Total minutes played: {df['MINUTOS JUGADOS'].sum()}")
        print(f"Average minutes per player: {df['MINUTOS JUGADOS'].mean():.2f}")
    
    print("\nTop 5 players by total points:")
    if 'PUNTOS' in df.columns:
        top_scorers = df.nlargest(5, 'PUNTOS')[['JUGADOR', 'PUNTOS', 'PJ']]
        print(top_scorers.to_string(index=False))
    
    print("\nFirst 5 rows of aggregated data:")
    # Display only key columns for readability
    display_cols = ['JUGADOR', 'PJ', 'MINUTOS JUGADOS', 'PUNTOS', 'ASISTENCIAS', 'T2 CONVERTIDO', 'T3 CONVERTIDO']
    available_display_cols = [col for col in display_cols if col in df.columns]
    print(df[available_display_cols].head().to_string(index=False))

def analyze_player(df, player_name):
    """
    Analyze a specific player's statistics.
    
    Args:
        df (pandas.DataFrame): Aggregated data
        player_name (str): Name of the player to analyze
    """
    player_data = df[df['JUGADOR'].str.contains(player_name, case=False, na=False)]

    if len(player_data) == 0:
        print(f"No player found with name containing '{player_name}'")
        return
    
    if len(player_data) > 1:
        print(f"Multiple players found with name containing '{player_name}':")
        print(player_data['JUGADOR'].tolist())
        return
    
    player = player_data.iloc[0]
    print(f"\n{'='*50}")
    print(f"PLAYER ANALYSIS: {player['JUGADOR']}")
    print(f"{'='*50}")

    if 'PJ' in player:
        print(f"Games played: {player['PJ']}")
    if 'MINUTOS JUGADOS' in player:
        print(f"Total minutes: {player['MINUTOS JUGADOS']:.1f}")
        if 'PJ' in player and player['PJ'] > 0:
            print(f"Minutes per game: {player['MINUTOS JUGADOS']/player['PJ']:.1f}")

    if 'PUNTOS' in player:
        print(f"Total points: {player['PUNTOS']}")
        if 'PJ' in player and player['PJ'] > 0:
            print(f"Points per game: {player['PUNTOS']/player['PJ']:.1f}")

    shooting_stats = []
    if 'T2 CONVERTIDO' in player and 'T2 INTENTADO' in player:
        t2_pct = (player['T2 CONVERTIDO'] / player['T2 INTENTADO'] * 100) if player['T2 INTENTADO'] > 0 else 0
        shooting_stats.append(f"2P: {player['T2 CONVERTIDO']}/{player['T2 INTENTADO']} ({t2_pct:.1f}%)")
    
    if 'T3 CONVERTIDO' in player and 'T3 INTENTADO' in player:
        t3_pct = (player['T3 CONVERTIDO'] / player['T3 INTENTADO'] * 100) if player['T3 INTENTADO'] > 0 else 0
        shooting_stats.append(f"3P: {player['T3 CONVERTIDO']}/{player['T3 INTENTADO']} ({t3_pct:.1f}%)")
    
    if 'TL CONVERTIDOS' in player and 'TL INTENTADOS' in player:
        ft_pct = (player['TL CONVERTIDOS'] / player['TL INTENTADOS'] * 100) if player['TL INTENTADOS'] > 0 else 0
        shooting_stats.append(f"FT: {player['TL CONVERTIDOS']}/{player['TL INTENTADOS']} ({ft_pct:.1f}%)")
    
    if shooting_stats:
        print("Shooting: " + " | ".join(shooting_stats))
    
    other_stats = []
    for stat in ['ASISTENCIAS', 'REB OFFENSIVO', 'REB DEFENSIVO', 'RECUPEROS', 'PERDIDAS']:
        if stat in player:
            other_stats.append(f"{stat}: {player[stat]}")
    
    if other_stats:
        print("Other stats: " + " | ".join(other_stats))

def main():
    """
    Main function to execute the player aggregation process.
    """
    try:
        # Aggregate the player statistics
        excel_path_in = './data/jugadores_per_game_23_24_c.xlsx'
        aggregated_df = aggregate_players_stats(excel_path_in)
        
        # Display summary
        #display_summary(aggregated_df)
        
        # Save the aggregated data
        excel_path_out = './data/jugadores_aggregated_23_24_c.xlsx'
        save_aggregated_data(aggregated_df, excel_path_out)

        # Optionally save as CSV as well
        #csv_path = './data/jugadores_aggregated.csv'
        #print(f"\nAlso saving as CSV: {csv_path}")
        #aggregated_df.to_csv(csv_path, index=False)
        
        # Example: Analyze a specific player (uncomment to use)
        # analyze_player(aggregated_df, "GONZALEZ")
        
        return aggregated_df
        
    except FileNotFoundError:
        print("Error: Could not find the file './data/jugadores.xlsx'")
        print("Please make sure the file exists in the specified location.")
        return None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    result = main()
