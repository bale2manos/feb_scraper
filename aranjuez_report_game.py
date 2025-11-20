#!/usr/bin/env python3
"""
Script para generar reporte de equipo usando datos de BasketAranjuez.
Convierte el formato de datos de BasketAranjuez al formato esperado por build_team_report.
También genera informes individuales para cada jugador.
"""

import pandas as pd
from pathlib import Path
from team_report.build_team_report import build_team_report
from player_report.player_report_gen import generate_report

def read_team_stats_sheet(file_path):
    """
    Lee las estadísticas del rival desde la hoja 'Stats_Rival' del archivo agregado.
    
    Returns:
        dict: Diccionario con las estadísticas de equipo y rival
    """
    try:
        # Intentar leer desde la hoja Stats_Rival (nuevo formato)
        df_rival = pd.read_excel(file_path, sheet_name='Stats_Rival')
        
        team_stats = {
            'puntos_locales': df_rival['PUNTOS_LOCAL'].iloc[0] if 'PUNTOS_LOCAL' in df_rival.columns else 0,
            'puntos_oponente': df_rival['PUNTOS_RIVAL'].iloc[0],
            'rebotes_locales': df_rival['REB_LOCAL'].iloc[0],
            'rebotes_rival': df_rival['REB_RIVAL'].iloc[0],
            'rebotes_ofensivos_locales': df_rival['OREB_LOCAL'].iloc[0],
            'rebotes_ofensivos_rival': df_rival['OREB_RIVAL'].iloc[0],
            'rebotes_defensivos_locales': df_rival['DREB_LOCAL'].iloc[0],
            'rebotes_defensivos_rival': df_rival['DREB_RIVAL'].iloc[0],
        }
        
        print(f"[OK] Estadisticas leidas desde hoja 'Stats_Rival':")
        print(f"   • Puntos locales: {team_stats['puntos_locales']}")
        print(f"   • Puntos oponente: {team_stats['puntos_oponente']}")
        print(f"   • Rebotes locales: {team_stats['rebotes_locales']}")
        print(f"   • Rebotes rival: {team_stats['rebotes_rival']}")
        
        return team_stats
        
    except Exception as e:
        print(f"[AVISO] No se pudo leer hoja 'Stats_Rival': {e}")
        print(f"[INFO] Intentando leer desde hoja 'Team Stats' (formato individual)...")
        
        # Fallback: intentar leer desde Team Stats (formato de archivo individual)
        try:
            df_team_stats = pd.read_excel(file_path, sheet_name='Team Stats', header=None)
            
            # Función auxiliar para convertir a numérico
            def to_numeric(value):
                """Convierte valores a numérico, manejando strings y valores inválidos."""
                try:
                    if pd.isna(value):
                        return 0
                    # Si es string, limpiar y convertir
                    if isinstance(value, str):
                        cleaned = value.strip().replace(',', '.')
                        return float(cleaned) if cleaned else 0
                    return float(value)
                except (ValueError, AttributeError):
                    return 0
            
            team_stats = {
                'puntos_locales': to_numeric(df_team_stats.iloc[1, 5]),  # F2 - puntos locales
                'puntos_oponente': to_numeric(df_team_stats.iloc[2, 5]),  # F3 - puntos rival
                'rebotes_locales': to_numeric(df_team_stats.iloc[20, 0]),  # A21
                'rebotes_rival': to_numeric(df_team_stats.iloc[20, 2]),    # C21
                'rebotes_ofensivos_locales': to_numeric(df_team_stats.iloc[18, 0]),  # OREB locales
                'rebotes_ofensivos_rival': to_numeric(df_team_stats.iloc[18, 2]),    # OREB rival
                'rebotes_defensivos_locales': to_numeric(df_team_stats.iloc[19, 0]), # DREB locales
                'rebotes_defensivos_rival': to_numeric(df_team_stats.iloc[19, 2]),   # DREB rival
            }
            
            print(f"[OK] Estadisticas leidas desde hoja 'Team Stats':")
            print(f"   • Puntos locales: {team_stats['puntos_locales']}")
            print(f"   • Puntos oponente: {team_stats['puntos_oponente']}")
            print(f"   • Rebotes locales: {team_stats['rebotes_locales']}")
            print(f"   • Rebotes rival: {team_stats['rebotes_rival']}")
            
            return team_stats
            
        except Exception as e2:
            print(f"[ERROR] No se pudieron leer estadisticas del rival: {e2}")
            return {
                'puntos_locales': 0,
                'puntos_oponente': 0,
                'rebotes_locales': 0,
                'rebotes_rival': 0,
                'rebotes_ofensivos_locales': 0,
                'rebotes_ofensivos_rival': 0,
                'rebotes_defensivos_locales': 0,
                'rebotes_defensivos_rival': 0,
            }

def convert_aranjuez_to_standard_format(df_aranjuez, is_aggregated=False):
    """
    Convierte el formato de datos de BasketAranjuez al formato estándar esperado.
    
    Args:
        df_aranjuez: DataFrame con datos de BasketAranjuez
        is_aggregated: Si True, los datos son promedios y se convierten a totales (multiplicando por PJ)
                      Si False, los datos son totales de un partido individual
    
    Mapeo de columnas:
    BasketAranjuez -> Formato estándar
    - Jugador -> JUGADOR
    - Nº -> DORSAL
    - MIN -> MINUTOS JUGADOS (convertir de MM:SS a segundos)
    - PTS -> PUNTOS
    - 2PM -> T2 CONVERTIDO
    - 2PA -> T2 INTENTADO
    - 3PM -> T3 CONVERTIDO
    - 3PA -> T3 INTENTADO
    - FTM -> TL CONVERTIDOS
    - FTA -> TL INTENTADOS
    - OREB -> REB OFFENSIVO
    - DREB -> REB DEFENSIVO
    - AST -> ASISTENCIAS
    - STL -> RECUPEROS
    - TOV -> PERDIDAS
    - PF -> FaltasCOMETIDAS
    - PFD -> FaltasRECIBIDAS
    """
    
    def convert_minutes_to_decimal_minutes(time_str):
        """Convierte formato MM:SS a minutos decimales para promedio por partido"""
        if pd.isna(time_str) or time_str == 0 or time_str == '':
            return 0.0
        
        try:
            if isinstance(time_str, str):
                # Dividir por ':' para obtener minutos y segundos
                parts = time_str.strip().split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    # Convertir a minutos decimales
                    decimal_minutes = minutes + (seconds / 60.0)
                    return decimal_minutes
                elif len(parts) == 1:
                    # Solo minutos
                    minutes = int(parts[0])
                    return float(minutes)
            elif isinstance(time_str, (int, float)):
                # Ya es un número (minutos)
                return float(time_str)
        except (ValueError, IndexError, AttributeError) as e:
            print(f"[ERROR] Error convirtiendo tiempo: {time_str} -> {e}")
            return 0.0
        
        return 0.0
    
    # Crear DataFrame convertido
    df_converted = pd.DataFrame()
    
    # Mapeo directo de columnas
    column_mapping = {
        'Jugador': 'JUGADOR',
        'Nº': 'DORSAL',
        'PJ': 'PJ',  # Partidos jugados (importante para datos agregados)
        'PTS': 'PUNTOS',
        '2PM': 'T2 CONVERTIDO',
        '2PA': 'T2 INTENTADO', 
        '3PM': 'T3 CONVERTIDO',
        '3PA': 'T3 INTENTADO',
        'FTM': 'TL CONVERTIDOS',
        'FTA': 'TL INTENTADOS',
        'OREB': 'REB OFFENSIVO',
        'DREB': 'REB DEFENSIVO',
        'AST': 'ASISTENCIAS',
        'STL': 'RECUPEROS',
        'TOV': 'PERDIDAS',
        'PF': 'FaltasCOMETIDAS',
        'PFD': 'FaltasRECIBIDAS'
    }
    
    # Aplicar mapeo directo
    for aranjuez_col, standard_col in column_mapping.items():
        if aranjuez_col in df_aranjuez.columns:
            df_converted[standard_col] = df_aranjuez[aranjuez_col]
    
    # Conversión especial para minutos - convertir a minutos decimales
    if 'MIN' in df_aranjuez.columns:
        # Para BasketAranjuez (datos de un solo partido), guardamos minutos decimales directamente
        # ya que Avg. MIN = MINUTOS JUGADOS / PJ, y PJ = 1
        df_converted['MINUTOS JUGADOS'] = df_aranjuez['MIN'].apply(convert_minutes_to_decimal_minutes)
    
    # NOTA: Si los datos vienen de basket_aranjuez.xlsx (archivo agregado),
    # ya vienen como TOTALES desde aranjuez_aggregate.py (sumados excepto PERDIDAS que se promedia)
    # Por tanto, NO necesitamos multiplicar ni dividir nada aquí.
    
    # Añadir columnas faltantes con valores por defecto
    if is_aggregated:
        # Para archivos agregados, mantener el PJ del archivo original
        default_values = {
            'EQUIPO': 'BASKET ARANJUEZ',
            'FASE': 'TEMPORADA 24-25',
            'IMAGEN': '',
            'FECHA NACIMIENTO': '',
            'NACIONALIDAD': 'ESP',
            'URL JUGADOR': ''
        }
    else:
        # Para archivos individuales, PJ = 1
        default_values = {
            'EQUIPO': 'BASKET ARANJUEZ',
            'PJ': 1,
            'FASE': 'TEMPORADA 24-25',
            'IMAGEN': '',
            'FECHA NACIMIENTO': '',
            'NACIONALIDAD': 'ESP',
            'URL JUGADOR': ''
        }
    
    for col, default_val in default_values.items():
        if col not in df_converted.columns:
            df_converted[col] = default_val
    
    # Reordenar columnas para que coincidan con el formato estándar
    standard_columns = [
        'JUGADOR', 'DORSAL', 'FASE', 'IMAGEN', 'JUGADOR', 'EQUIPO', 'PJ', 
        'MINUTOS JUGADOS', 'PUNTOS', 'T2 CONVERTIDO', 'T2 INTENTADO', 
        'T3 CONVERTIDO', 'T3 INTENTADO', 'TL CONVERTIDOS', 'TL INTENTADOS',
        'REB OFFENSIVO', 'REB DEFENSIVO', 'ASISTENCIAS', 'RECUPEROS', 
        'PERDIDAS', 'FaltasCOMETIDAS', 'FaltasRECIBIDAS', 'FECHA NACIMIENTO',
        'NACIONALIDAD', 'URL JUGADOR'
    ]
    
    # Crear DataFrame final con columnas ordenadas
    df_final = pd.DataFrame()
    for col in standard_columns:
        if col in df_converted.columns:
            df_final[col] = df_converted[col]
        else:
            df_final[col] = ''
    
    # Duplicar columna JUGADOR como JUGADOR.1 (parece ser requerido por el formato)
    df_final['JUGADOR.1'] = df_final['JUGADOR']
    
    return df_final

def create_team_stats_for_aranjuez(df_players, team_stats_data, is_aggregated=False):
    """
    Crear estadísticas de equipo agregadas a partir de estadísticas de jugadores
    y datos adicionales de la hoja Team Stats.
    
    Args:
        df_players: DataFrame con estadísticas de jugadores
        team_stats_data: Dict con estadísticas adicionales (rebotes rival, puntos oponente, etc.)
        is_aggregated: bool indicando si el archivo es agregado (promedios) o individual (partido único)
    """
    
    # Calcular porcentajes de rebote CORRECTAMENTE
    # %OREB = reb_of_locales / (reb_of_locales + reb_def_rival)
    # %DREB = reb_def_locales / (reb_def_locales + reb_of_rival)
    
    oportunidades_oreb = team_stats_data['rebotes_ofensivos_locales'] + team_stats_data['rebotes_defensivos_rival']
    oportunidades_dreb = team_stats_data['rebotes_defensivos_locales'] + team_stats_data['rebotes_ofensivos_rival']
    rebotes_totales_partido = team_stats_data['rebotes_locales'] + team_stats_data['rebotes_rival']
    
    # Calcular porcentajes
    pct_oreb = (team_stats_data['rebotes_ofensivos_locales'] / oportunidades_oreb * 100) if oportunidades_oreb > 0 else 0
    pct_dreb = (team_stats_data['rebotes_defensivos_locales'] / oportunidades_dreb * 100) if oportunidades_dreb > 0 else 0  
    pct_reb = (team_stats_data['rebotes_locales'] / rebotes_totales_partido * 100) if rebotes_totales_partido > 0 else 0
    
    # Calcular otras métricas avanzadas
    # Para archivos agregados, usar los puntos de Stats_Rival (ya son promedios)
    # Para archivos individuales, sumar los puntos de jugadores
    if is_aggregated:
        puntos_locales = team_stats_data['puntos_locales']
    else:
        puntos_locales = df_players['PUNTOS'].sum()
    
    plays_locales = (df_players['TL INTENTADOS'].sum() * 0.44 + 
                    df_players['T2 INTENTADO'].sum() + 
                    df_players['T3 INTENTADO'].sum() + 
                    df_players['PERDIDAS'].sum())
    
    ppp = puntos_locales / plays_locales if plays_locales > 0 else 0
    
    # Agregar todas las estadísticas numéricas
    team_stats = {
        'EQUIPO': 'BASKET ARANJUEZ',
        'FASE': 'TEMPORADA 24-25',
        'PJ': 1,  # Un partido
        'PUNTOS +': puntos_locales,  # Puntos a favor
        'PUNTOS -': team_stats_data['puntos_oponente'],  # Puntos en contra
        'T2 CONVERTIDO': df_players['T2 CONVERTIDO'].sum(),
        'T2 INTENTADO': df_players['T2 INTENTADO'].sum(),
        'T3 CONVERTIDO': df_players['T3 CONVERTIDO'].sum(),
        'T3 INTENTADO': df_players['T3 INTENTADO'].sum(),
        'TL CONVERTIDOS': df_players['TL CONVERTIDOS'].sum(),
        'TL INTENTADOS': df_players['TL INTENTADOS'].sum(),
        'REB OFFENSIVO': df_players['REB OFFENSIVO'].sum(),
        'REB DEFENSIVO': df_players['REB DEFENSIVO'].sum(),
        'ASISTENCIAS': df_players['ASISTENCIAS'].sum(),
        'RECUPEROS': df_players['RECUPEROS'].sum(),
        'PERDIDAS': df_players['PERDIDAS'].sum(),
        'FaltasCOMETIDAS': df_players['FaltasCOMETIDAS'].sum(),
        'FaltasRECIBIDAS': df_players['FaltasRECIBIDAS'].sum(),
        'MINUTOS JUGADOS': df_players['MINUTOS JUGADOS'].sum(),
        
        # Métricas avanzadas calculadas
        'PPP': round(ppp, 2),
        'PPP OPP': 0,  # No tenemos datos suficientes para calcular
        'OFFRTG': round((puntos_locales / plays_locales * 100), 2) if plays_locales > 0 else 0,
        'DEFRTG': 0,  # Necesitaríamos más datos del oponente
        'NETRTG': 0,  # OFFRTG - DEFRTG
        
        # Porcentajes de rebote calculados con datos del rival (en escala 0-1 para el overview)
        '%OREB': round(pct_oreb / 100, 4),  # Convertir a escala 0-1
        '%DREB': round(pct_dreb / 100, 4),  # Convertir a escala 0-1 
        '%REB': round(pct_reb / 100, 4),    # Convertir a escala 0-1
        
        'PLAYS': round(plays_locales, 1),
        'POSS': round(plays_locales, 1),  # Aproximación
    }
    
    print(f"📈 Métricas avanzadas calculadas:")
    print(f"   • PPP: {team_stats['PPP']}")
    print(f"   • Cálculo %OREB: {team_stats_data['rebotes_ofensivos_locales']}/({team_stats_data['rebotes_ofensivos_locales']}+{team_stats_data['rebotes_defensivos_rival']}) = {pct_oreb:.2f}%")
    print(f"   • Cálculo %DREB: {team_stats_data['rebotes_defensivos_locales']}/({team_stats_data['rebotes_defensivos_locales']}+{team_stats_data['rebotes_ofensivos_rival']}) = {pct_dreb:.2f}%") 
    print(f"   • %REB: {pct_reb:.2f}% (guardado como {team_stats['%REB']:.4f})")
    
    return pd.DataFrame([team_stats])

def main():
    """Función principal para ejecutar el reporte de BasketAranjuez"""
    
    print("🏀 GENERADOR DE REPORTE - BASKET ARANJUEZ")
    print("=" * 50)
    
    # 1. Leer datos de BasketAranjuez
    aranjuez_file = Path("data/BasketAranjuez/basket_aranjuez.xlsx")

    if not aranjuez_file.exists():
        print(f"❌ Error: No se encontró el archivo {aranjuez_file}")
        print("   Asegúrate de que el archivo existe en la carpeta data/BasketAranjuez/")
        return
    
    print("📊 Leyendo datos de BasketAranjuez...")
    
    # Detectar tipo de archivo: agregado (.xlsx con hoja 'Jugadores') o individual (.xls sin hoja)
    is_aggregated = aranjuez_file.suffix == '.xlsx' and aranjuez_file.name == 'basket_aranjuez.xlsx'
    
    if is_aggregated:
        print("[INFO] Detectado archivo agregado (basket_aranjuez.xlsx)")
        df_aranjuez = pd.read_excel(aranjuez_file, sheet_name='Jugadores')
    else:
        print(f"[INFO] Detectado archivo de partido individual ({aranjuez_file.name})")
        df_aranjuez = pd.read_excel(aranjuez_file)  # Sin especificar sheet_name
    
    print(f"✅ Datos leídos: {df_aranjuez.shape[0]} jugadores, {df_aranjuez.shape[1]} columnas")
    
    # 1.5. Leer datos adicionales de la hoja Team Stats
    print("📈 Leyendo estadísticas adicionales...")
    team_stats_data = read_team_stats_sheet(aranjuez_file)
    
    # 2. Convertir al formato estándar
    print("🔄 Convirtiendo formato de datos...")
    df_players_converted = convert_aranjuez_to_standard_format(df_aranjuez, is_aggregated=is_aggregated)
    
    # 3. Crear estadísticas de equipo (ahora con datos adicionales)
    print("📈 Generando estadísticas de equipo...")
    df_team_converted = create_team_stats_for_aranjuez(df_players_converted, team_stats_data, is_aggregated)
    
    # 4. Guardar archivos temporales convertidos
    temp_players_file = Path("temp_aranjuez_players.xlsx")
    temp_teams_file = Path("temp_aranjuez_teams.xlsx")
    
    df_players_converted.to_excel(temp_players_file, index=False)
    df_team_converted.to_excel(temp_teams_file, index=False)
    
    print(f"💾 Archivos temporales creados")
    
    # 5. Generar informes individuales de jugadores
    print("\n" + "=" * 50)
    print("👤 GENERANDO INFORMES INDIVIDUALES DE JUGADORES")
    print("=" * 50)
    
    player_reports_generated = []
    player_reports_failed = []
    
    # Obtener lista de jugadores
    player_col = 'JUGADOR'
    if player_col in df_players_converted.columns:
        players_list = df_players_converted[player_col].dropna().unique().tolist()
        print(f"📋 Jugadores a procesar: {len(players_list)}")
        
        for idx, player_name in enumerate(players_list, 1):
            try:
                print(f"\n  [{idx}/{len(players_list)}] Generando informe para: {player_name}")
                report_path = generate_report(
                    player_name=player_name,
                    data_file=str(temp_players_file),
                    teams_file=str(temp_teams_file),
                    overwrite=True
                )
                player_reports_generated.append((player_name, report_path))
                print(f"      ✅ Generado: {report_path.name}")
            except Exception as e:
                player_reports_failed.append((player_name, str(e)))
                print(f"      ❌ Error: {e}")
    else:
        print("⚠️  No se encontró la columna 'JUGADOR' en los datos")
    
    # 6. Generar reporte de equipo usando build_team_report
    print("\n" + "=" * 50)
    print("📑 GENERANDO REPORTE DE EQUIPO")
    print("=" * 50)
    try:
        output_pdf = build_team_report(
            team_filter="BASKET ARANJUEZ",
            players_file=str(temp_players_file),
            teams_file=str(temp_teams_file),
            min_games=0,  # Solo tenemos 1 partido
            min_minutes=0,  # Incluir todos los jugadores
            min_shots=0   # Incluir todos los jugadores
        )
        
        print("\n" + "=" * 50)
        print("✅ ¡REPORTES GENERADOS EXITOSAMENTE!")
        print("=" * 50)
        
        # Resumen de informes de jugadores
        print("\n👤 INFORMES INDIVIDUALES:")
        print(f"   ✅ Generados exitosamente: {len(player_reports_generated)}")
        if player_reports_failed:
            print(f"   ❌ Fallidos: {len(player_reports_failed)}")
            for player_name, error in player_reports_failed:
                print(f"      • {player_name}: {error}")
        
        if player_reports_generated:
            print(f"\n📁 Informes de jugadores guardados en: output/player_reports/")
            for player_name, report_path in player_reports_generated[:3]:  # Mostrar solo los primeros 3
                print(f"   • {report_path.name}")
            if len(player_reports_generated) > 3:
                print(f"   ... y {len(player_reports_generated) - 3} más")
        
        # Reporte de equipo
        print(f"\n📊 REPORTE DE EQUIPO:")
        print(f"   📄 Archivo: {output_pdf}")
        print(f"   📁 Ubicación: {output_pdf.absolute()}")
        
        # Mostrar resumen de datos procesados
        print("\n📊 RESUMEN DE DATOS:")
        print(f"   • Jugadores procesados: {df_aranjuez.shape[0]}")
        print(f"   • Puntos totales equipo: {df_team_converted['PUNTOS +'].iloc[0]}")
        print(f"   • Puntos del oponente: {df_team_converted['PUNTOS -'].iloc[0]}")
        print(f"   • Rebotes totales: {df_team_converted['REB OFFENSIVO'].iloc[0] + df_team_converted['REB DEFENSIVO'].iloc[0]}")
        print(f"   • % Rebotes: {df_team_converted['%REB'].iloc[0] * 100:.2f}%")
        print(f"   • % Rebotes ofensivos: {df_team_converted['%OREB'].iloc[0] * 100:.2f}%")
        print(f"   • % Rebotes defensivos: {df_team_converted['%DREB'].iloc[0] * 100:.2f}%")
        print(f"   • Asistencias totales: {df_team_converted['ASISTENCIAS'].iloc[0]}")
        print(f"   • PPP (Puntos por posesión): {df_team_converted['PPP'].iloc[0]}")
        
    except Exception as e:
        print("=" * 50)
        print(f"❌ ERROR AL GENERAR EL REPORTE:")
        print(f"   {e}")
        print("\n🔍 DETALLES DEL ERROR:")
        import traceback
        traceback.print_exc()
    
    finally:
        # Limpiar archivos temporales
        try:
            if temp_players_file.exists():
                temp_players_file.unlink()
            if temp_teams_file.exists():
                temp_teams_file.unlink()
            print("🧹 Archivos temporales eliminados")
        except Exception as e:
            print(f"⚠️  Error al limpiar archivos temporales: {e}")
        
        print("=" * 50)

if __name__ == "__main__":
    main()