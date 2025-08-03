import pandas as pd

def aggregate_games(path='./data/jugadores_per_game.xlsx'):
    """
    Agrupa los datos de jugadores por equipo y fase, sumando las estadísticas de cada partido.
    
    :param path: Ruta al archivo Excel con los datos de jugadores por partido.
    :return: DataFrame con los totales por equipo y fase.
    """
    # Leer el archivo Excel
    df = pd.read_excel(path)
        
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
    
    # Agrupar por Fase, Jornada, Equipo Local y Rival, sumar las columnas especificadas y el primer resultado de PTS_RIVAL
    df['PTS_RIVAL'] = df['PTS_RIVAL'].astype(int)  # Asegurarse de que PTS_RIVAL es numérico
    df = df.groupby(['FASE', 'JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL'], as_index=False).agg({
        **{col: 'sum' for col in sum_columns},
        'PTS_RIVAL': 'first'  # Mantener el primer valor de PTS_RIVAL
    })
    
    # Calcular plays jugados por equipo
    df['PLAYS']= df['TL INTENTADOS']*0.44 + df['T2 INTENTADO'] + df['T3 INTENTADO'] + df['PERDIDAS']
    df['PPP'] = df['PUNTOS'] / df['PLAYS'].replace(0, pd.NA)  # Evitar división por cero
    df['POSS'] = df['PLAYS'] - df['REB OFFENSIVO']
    df['OFFRTG'] =  (100*df['PUNTOS']) / df['POSS'].replace(0, pd.NA)  # Calcular rating ofensivo

    # Calcular PPP del rival (opponent)
    # Para cada partido, encontrar los datos del equipo rival
    df['PPP OPP'] = pd.NA
    df['DEFRTG'] = pd.NA
    df['%OREB'] = pd.NA
    df['%DREB'] = pd.NA
    df['%REB'] = pd.NA

    for index, row in df.iterrows():
        fase = row['FASE']
        jornada = row['JORNADA']
        equipo_local = row['EQUIPO LOCAL']
        equipo_rival = row['EQUIPO RIVAL']
        team_def_rebound = row['REB DEFENSIVO']
        team_off_rebound = row['REB OFFENSIVO']
        team_total_rebound = team_def_rebound + team_off_rebound
        
        # Buscar la fila donde el equipo rival es el equipo local en el mismo partido
        opponent_row = df[
            (df['FASE'] == fase) & 
            (df['JORNADA'] == jornada) & 
            (df['EQUIPO LOCAL'] == equipo_rival) & 
            (df['EQUIPO RIVAL'] == equipo_local)
        ]
        
        if not opponent_row.empty:
            opp_offrebound = opponent_row.iloc[0]['REB OFFENSIVO']
            opp_defrebound = opponent_row.iloc[0]['REB DEFENSIVO']
            opp_total_rebound = opp_offrebound + opp_defrebound
            
            df.at[index, 'PPP OPP'] = opponent_row.iloc[0]['PPP']
            df.at[index, 'DEFRTG'] = opponent_row.iloc[0]['OFFRTG']
            df.at[index, '%OREB'] = team_off_rebound / (opp_defrebound + team_off_rebound) if opp_total_rebound > 0 else 0
            df.at[index, '%DREB'] = team_def_rebound / (opp_offrebound + team_def_rebound) if opp_total_rebound > 0 else 0
            df.at[index, '%REB'] = team_total_rebound / (opp_total_rebound + team_total_rebound) if opp_total_rebound > 0 else 0
    df['NETRTG'] = df['OFFRTG'] - df['DEFRTG']  # Calcular Net Rating

    return df


def aggregate_teams(df):
    """
    Agrupa los datos de equipos, sumando las estadísticas de cada partido y contando el número de partidos jugados.
    
    :param df: DataFrame con los datos de jugadores por partido.
    :return: DataFrame con los totales por equipo.
    """
    not_sum_columns = ['FASE', 'JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL', 
                       'PPP', 'PPP OPP', 'OFFRTG', 'DEFRTG', 'NETRTG',
                       '%OREB', '%DREB', '%REB']
    # Agrupar por equipo y sumar las columnas especificadas
    aggregated = df.groupby('EQUIPO LOCAL').agg({
        'FASE': 'first',
        'PPP': 'mean',  # Promedio de PPP por equipo
        'PPP OPP': 'mean',  # Promedio de PPP del rival
        'OFFRTG': 'mean',  # Promedio de rating ofensivo
        'DEFRTG': 'mean',  # Promedio de rating defensivo
        'NETRTG': 'mean',  # Promedio de Net Rating
        '%OREB': 'mean',  # Promedio de %OREB
        '%DREB': 'mean',  # Promedio de %DREB
        '%REB': 'mean',  # Promedio de %REB

        **{col: 'sum' for col in df.columns if col in df.columns and col not in not_sum_columns}
    }).reset_index()
    
    # Contar el número de partidos jugados
    aggregated['PJ'] = df[df['EQUIPO LOCAL'].isin(aggregated['EQUIPO LOCAL'])].groupby('EQUIPO LOCAL').size().values
    aggregated.rename(columns={'EQUIPO LOCAL': 'EQUIPO', 
                               'PTS_RIVAL': 'PUNTOS -',
                               'PUNTOS': 'PUNTOS +'}, inplace=True)

    return aggregated

if __name__ == "__main__":
    # Ejecutar la agregación
    result = aggregate_games()
    
    result.to_excel('./data/games_aggregated.xlsx', index=False)
    
    result_teams = aggregate_teams(result)
    
    
    # Guardar los resultados en un nuevo archivo Excel
    output_path = './data/teams_aggregated.xlsx'
    result_teams.to_excel(output_path, index=False)
    print(f"\nResultados guardados en '{output_path}'")