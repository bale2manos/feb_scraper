import pandas as pd

def aggregate_teams():
    # Read the Excel file
    df = pd.read_excel('data/equipos_per_game.xlsx')
    
    # Define columns to sum
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
    
    # Group by Local, get first Fase, and sum the specified columns, count the number of games
    aggregated = df.groupby('Local').agg({
        'Fase': 'first',
        **{col: 'sum' for col in sum_columns}
    }).reset_index()

    # Count the number of games
    aggregated['PJ'] = df[df['Local'].isin(aggregated['Local'])].groupby('Local').size().values
    aggregated.rename(columns={'Local': 'EQUIPO'}, inplace=True)
    
    
    return aggregated

if __name__ == "__main__":
    # Run the aggregation
    result = aggregate_teams()
    
    # Display the results
    print("Aggregated Team Data:")
    print(result)
    
    # Optionally save to a new Excel file
    result.to_excel('data/teams_aggregated.xlsx', index=False)
    print("\nResults saved to 'data/teams_aggregated.xlsx'")