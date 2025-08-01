import pandas as pd
import numpy as np

def aggregate_players_stats(file_path='./data/jugadores_per_game.xlsx'):
    """
    Aggregates player statistics from the Excel file.
    
    Args:
        file_path (str): Path to the Excel file containing player data
        
    Returns:
        pandas.DataFrame: Aggregated statistics by player
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
    first_columns = ['DORSALES', 'Fase', 'Local']
    
    # Check if all required columns exist
    missing_columns = []
    for col in sum_columns + first_columns + ['JUGADOR']:
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
    
    print("Aggregating data by JUGADOR...")
    
    # Group by JUGADOR and aggregate
    aggregated_df = df.groupby('JUGADOR').agg(agg_dict).reset_index()
    
    # Add count for games played (number of rows per player)
    games_count = df.groupby('JUGADOR').size().reset_index(name='PJ')
    aggregated_df = aggregated_df.merge(games_count, on='JUGADOR')
    
    # Reorder columns: JUGADOR first, then first_columns, then PJ, then sum_columns
    column_order = ['JUGADOR'] + first_columns + ['PJ'] + sum_columns

    # Only include columns that exist in the dataframe
    final_columns = [col for col in column_order if col in aggregated_df.columns]
    aggregated_df = aggregated_df[final_columns]
    
    # Rename column Local to 'EQUIPO' for consistency
    if 'Local' in aggregated_df.columns:
        aggregated_df.rename(columns={'Local': 'EQUIPO'}, inplace=True)
    
    
    print(f"Aggregation complete. Results for {len(aggregated_df)} players.")
    
    return aggregated_df

def save_aggregated_data(df, output_path='./data/jugadores_aggregated.xlsx'):
    """
    Save the aggregated data to an Excel file.
    
    Args:
        df (pandas.DataFrame): Aggregated data
        output_path (str): Path where to save the output file
    """
    print(f"Saving aggregated data to {output_path}...")
    df.to_excel(output_path, index=False)
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
        aggregated_df = aggregate_players_stats()
        
        # Display summary
        display_summary(aggregated_df)
        
        # Save the aggregated data
        save_aggregated_data(aggregated_df)
        
        # Optionally save as CSV as well
        csv_path = './data/jugadores_aggregated.csv'
        print(f"\nAlso saving as CSV: {csv_path}")
        aggregated_df.to_csv(csv_path, index=False)
        
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
