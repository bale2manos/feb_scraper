#!/usr/bin/env python3
"""
Script to aggregate player statistics from BasketAranjuez folder.

This script reads all Excel files in the BasketAranjuez folder,
calculates the average statistics for each player across all games,
and saves the result to basket_aranjuez.xlsx

Usage: python aggregate_basketaranjuez.py
"""
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aggregate_basketaranjuez.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BasketAranjuezAggregator:
    def __init__(self, data_dir: str = './data/BasketAranjuez'):
        self.data_dir = Path(data_dir)
        self.output_file = self.data_dir / 'basket_aranjuez.xlsx'
        
        # Columnas que deben SUMARSE (totales acumulados)
        # Las herramientas de reporte dividirán por PJ para obtener promedios
        self.sum_columns = [
            # Nombres estándar
            'MINUTOS JUGADOS', 'PUNTOS',
            'T2C', 'T2I', 'T3C', 'T3I', 'T1C', 'T1I',
            'TCC', 'TCI',
            'OREB', 'DREB', 'REB OFFENSIVO', 'REB DEFENSIVO',
            'AST', 'ASISTENCIAS',
            'ROB', 'RECUPEROS', 'STL',
            'FaltasCOMETIDAS', 'FaltasRECIBIDAS',
            'PLAYS', 'POSS', 'BLK',
            # Nombres alternativos (BasketAranjuez)
            'MIN', 'PTS',
            '2PM', '2PA', '3PM', '3PA',
            'FGM', 'FGA', 'FTM', 'FTA',
            'ORB', 'DRB', 'TRB',
            'FP', 'FC', 'FD'
        ]
        
        # Columnas que deben PROMEDIARSE (excepciones y porcentajes)
        # PERDIDAS es una excepción: se promedia directamente
        self.avg_columns = [
            'TOV', 'PERDIDAS',  # Excepción: se promedian
            # Porcentajes y ratings (siempre se promedian)
            'PPP', 'OFFRTG', 'TS%', 'EFG%', 
            'FG%', '2P%', '3P%', 'FT%',
            '%REB', '%OREB', '%DREB',
            'ORB%', 'DRB%', 'TRB%',
            'TOV%', 'AST%', 'USG%', 'STL%', 'BLK%',
            'PER', 'PACE'
        ]
    
    def find_excel_files(self) -> List[Path]:
        """Encuentra todos los archivos Excel en la carpeta BasketAranjuez."""
        excel_files = list(self.data_dir.glob('*.xlsx')) + list(self.data_dir.glob('*.xls'))
        
        # Excluir el archivo de salida si ya existe
        excel_files = [f for f in excel_files if f.name != 'basket_aranjuez.xlsx']
        
        logger.info(f"Encontrados {len(excel_files)} archivos Excel en {self.data_dir}")
        for f in excel_files:
            logger.info(f"  - {f.name}")
        
        return excel_files
    
    def clean_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia y convierte columnas numéricas con formato de texto."""
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    # Crear serie limpia
                    cleaned = df[col].astype(str).copy()
                    
                    # Caso especial: Columna MIN con formato MM:SS
                    if col == 'MIN' or 'MINUTOS' in col.upper():
                        # Verificar si tiene formato MM:SS
                        if cleaned.str.contains(':', na=False).any():
                            def time_to_minutes(time_str):
                                """Convierte formato MM:SS a minutos decimales."""
                                try:
                                    if pd.isna(time_str) or time_str == 'nan':
                                        return pd.NA
                                    parts = str(time_str).split(':')
                                    if len(parts) == 2:
                                        mins = float(parts[0])
                                        secs = float(parts[1])
                                        return mins + (secs / 60)
                                    return pd.NA
                                except:
                                    return pd.NA
                            
                            df[col] = cleaned.apply(time_to_minutes)
                            logger.debug(f"Columna '{col}' convertida de MM:SS a minutos decimales")
                            continue
                    
                    # Detectar si hay valores con múltiples porcentajes concatenados (ej: '28,6%37,5%')
                    has_multiple_percentages = cleaned.str.contains(r'%.*%', na=False).any()
                    
                    if has_multiple_percentages:
                        # Si hay múltiples valores concatenados, tomar solo el primero
                        # Extraer el primer número con posible coma decimal y porcentaje
                        cleaned = cleaned.str.extract(r'([\d,]+)%?', expand=False)
                        logger.debug(f"Columna '{col}' tiene valores concatenados, usando solo el primero")
                    
                    # Remover símbolos de porcentaje y convertir comas a puntos
                    cleaned = cleaned.str.replace('%', '', regex=False)
                    cleaned = cleaned.str.replace(',', '.', regex=False)
                    cleaned = cleaned.str.strip()
                    
                    # Intentar conversión a numérico
                    numeric_series = pd.to_numeric(cleaned, errors='coerce')
                    
                    # Si más del 70% de los valores no-nulos se convirtieron, usar la versión numérica
                    non_null_count = df[col].notna().sum()
                    converted_count = numeric_series.notna().sum()
                    
                    if non_null_count > 0 and (converted_count / non_null_count) > 0.7:
                        df[col] = numeric_series
                        logger.debug(f"Columna '{col}' convertida a numérica ({converted_count}/{non_null_count} valores)")
                except Exception as e:
                    logger.debug(f"No se pudo convertir columna '{col}' a numérica: {e}")
                    pass
        
        return df
    
    def load_all_data(self, files: List[Path]) -> tuple:
        """Carga y concatena todos los archivos Excel, incluyendo estadísticas del rival.
        
        Returns:
            tuple: (df_players, df_rival_stats) - DataFrames de jugadores y stats del rival
        """
        dfs_players = []
        rival_stats_list = []
        
        for file in files:
            try:
                # Cargar datos de jugadores
                df = pd.read_excel(file)
                df = self.clean_numeric_columns(df)
                logger.info(f"Cargado {file.name}: {len(df)} filas, {len(df.columns)} columnas")
                dfs_players.append(df)
                
                # Intentar leer estadísticas del rival desde la hoja "Team Stats"
                try:
                    df_team_stats = pd.read_excel(file, sheet_name='Team Stats', header=None)
                    
                    # Función para convertir valores a numérico
                    def to_numeric_safe(value):
                        """Convierte valores a numérico, manejando strings."""
                        try:
                            if pd.isna(value):
                                return 0.0
                            if isinstance(value, str):
                                cleaned = value.strip().replace(',', '.')
                                return float(cleaned) if cleaned else 0.0
                            return float(value)
                        except (ValueError, AttributeError, TypeError):
                            logger.warning(f"  [ARCHIVO: {file.name}] No se pudo convertir valor: {value}")
                            return 0.0
                    
                    rival_stats = {
                        'PUNTOS_LOCAL': to_numeric_safe(df_team_stats.iloc[1, 5]),  # F2 - puntos locales
                        'PUNTOS_RIVAL': to_numeric_safe(df_team_stats.iloc[2, 5]),  # F3 - puntos rival
                        'OREB_LOCAL': to_numeric_safe(df_team_stats.iloc[18, 0]),   # A19
                        'DREB_LOCAL': to_numeric_safe(df_team_stats.iloc[19, 0]),   # A20
                        'REB_LOCAL': to_numeric_safe(df_team_stats.iloc[20, 0]),    # A21
                        'OREB_RIVAL': to_numeric_safe(df_team_stats.iloc[18, 2]),   # C19
                        'DREB_RIVAL': to_numeric_safe(df_team_stats.iloc[19, 2]),   # C20
                        'REB_RIVAL': to_numeric_safe(df_team_stats.iloc[20, 2]),    # C21
                    }
                    rival_stats_list.append(rival_stats)
                    logger.info(f"  [OK] Stats de {file.name}: PTS_L={rival_stats['PUNTOS_LOCAL']:.0f}, "
                               f"PTS_R={rival_stats['PUNTOS_RIVAL']:.0f}, REB_L={rival_stats['REB_LOCAL']:.0f}")
                except Exception as e:
                    logger.warning(f"  No se pudieron leer stats del rival de {file.name}: {e}")
                    rival_stats_list.append({
                        'PUNTOS_LOCAL': 0, 'PUNTOS_RIVAL': 0,
                        'OREB_LOCAL': 0, 'DREB_LOCAL': 0, 'REB_LOCAL': 0,
                        'OREB_RIVAL': 0, 'DREB_RIVAL': 0, 'REB_RIVAL': 0
                    })
                    
            except Exception as e:
                logger.error(f"Error al cargar {file.name}: {e}")
                continue
        
        if not dfs_players:
            raise ValueError("No se pudo cargar ningún archivo")
        
        combined_df = pd.concat(dfs_players, ignore_index=True)
        logger.info(f"Datos combinados: {len(combined_df)} filas totales")
        
        # Crear DataFrame con estadísticas del rival
        df_rival = pd.DataFrame(rival_stats_list)
        logger.info(f"Estadísticas del rival: {len(df_rival)} partidos")
        
        return combined_df, df_rival
    
    def aggregate_player_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega las estadísticas por jugador.
        
        - La mayoría de las columnas se SUMAN (totales acumulados)
        - PERDIDAS y porcentajes se PROMEDIAN
        - Las herramientas de reporte dividirán por PJ para obtener promedios
        """
        
        # Identificar columnas numéricas disponibles
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        # Separar columnas según tipo de agregación
        available_sum_cols = [col for col in self.sum_columns if col in numeric_cols]
        available_avg_cols = [col for col in self.avg_columns if col in numeric_cols]
        
        logger.info(f"Columnas numéricas detectadas: {len(numeric_cols)}")
        logger.info(f"Columnas a SUMAR: {len(available_sum_cols)}")
        logger.info(f"Columnas a PROMEDIAR: {len(available_avg_cols)}")
        
        # Determinar la columna de identificación del jugador
        player_col = None
        for col in ['JUGADOR', 'NOMBRE', 'Jugador', 'Nombre']:
            if col in df.columns:
                player_col = col
                break
        
        if player_col is None:
            raise ValueError("No se encontró columna de identificación del jugador")
        
        logger.info(f"Usando columna '{player_col}' como identificador de jugador")
        
        # Columnas de agrupación: SOLO nombre del jugador (sin dorsal)
        group_cols = [player_col]
        
        # Añadir EQUIPO si existe (pero NO el dorsal)
        for col in ['EQUIPO', 'EQUIPO LOCAL', 'Equipo']:
            if col in df.columns and col not in group_cols:
                group_cols.append(col)
        
        # Construir diccionario de agregación
        agg_dict = {}
        
        # Columnas que se SUMAN (totales acumulados)
        for col in available_sum_cols:
            agg_dict[col] = 'sum'
        
        # Columnas que se PROMEDIAN (PERDIDAS y porcentajes)
        for col in available_avg_cols:
            agg_dict[col] = 'mean'
        
        # Para el dorsal (Nº), tomar el ÚLTIMO (más reciente)
        if 'Nº' in df.columns:
            agg_dict['Nº'] = 'last'
        if 'DORSAL' in df.columns:
            agg_dict['DORSAL'] = 'last'
        
        # Contar partidos jugados
        df['PJ'] = 1
        agg_dict['PJ'] = 'sum'
        
        # Si hay columnas de fase o jornada, tomar las primeras
        for col in ['FASE', 'JORNADA', 'Fase', 'Jornada']:
            if col in df.columns and col not in group_cols:
                agg_dict[col] = 'first'
        
        # Agregar
        aggregated = df.groupby(group_cols, as_index=False).agg(agg_dict)
        
        logger.info(f"Jugadores agregados: {len(aggregated)}")
        
        # Redondear columnas numéricas
        for col in aggregated.select_dtypes(include=['float64']).columns:
            aggregated[col] = aggregated[col].round(2)
        
        return aggregated
    
    def aggregate_rival_stats(self, df_rival: pd.DataFrame) -> Dict:
        """Agrega las estadísticas del rival calculando promedios.
        
        Returns:
            dict: Diccionario con estadísticas promediadas del rival
        """
        if df_rival.empty:
            logger.warning("No hay estadísticas del rival para agregar")
            return {
                'PUNTOS_LOCAL': 0, 'PUNTOS_RIVAL': 0,
                'OREB_LOCAL': 0, 'DREB_LOCAL': 0, 'REB_LOCAL': 0,
                'OREB_RIVAL': 0, 'DREB_RIVAL': 0, 'REB_RIVAL': 0
            }
        
        # Verificar y convertir tipos de datos antes de promediar
        logger.info("Verificando tipos de datos...")
        for col in df_rival.columns:
            dtype = df_rival[col].dtype
            logger.debug(f"  Columna '{col}': dtype={dtype}")
            
            # Convertir a numérico si es necesario
            if df_rival[col].dtype == 'object':
                logger.warning(f"  Columna '{col}' es tipo object, convirtiendo a numérico...")
                df_rival[col] = pd.to_numeric(df_rival[col], errors='coerce').fillna(0)
        
        # Calcular promedios y asegurar que son float
        rival_stats_avg = {
            'PUNTOS_LOCAL': float(df_rival['PUNTOS_LOCAL'].mean()),
            'PUNTOS_RIVAL': float(df_rival['PUNTOS_RIVAL'].mean()),
            'OREB_LOCAL': float(df_rival['OREB_LOCAL'].mean()),
            'DREB_LOCAL': float(df_rival['DREB_LOCAL'].mean()),
            'REB_LOCAL': float(df_rival['REB_LOCAL'].mean()),
            'OREB_RIVAL': float(df_rival['OREB_RIVAL'].mean()),
            'DREB_RIVAL': float(df_rival['DREB_RIVAL'].mean()),
            'REB_RIVAL': float(df_rival['REB_RIVAL'].mean()),
        }
        
        logger.info(f"Estadísticas promediadas:")
        logger.info(f"  Puntos local promedio: {rival_stats_avg['PUNTOS_LOCAL']:.1f}")
        logger.info(f"  Puntos rival promedio: {rival_stats_avg['PUNTOS_RIVAL']:.1f}")
        logger.info(f"  Rebotes local promedio: {rival_stats_avg['REB_LOCAL']:.1f}")
        logger.info(f"  Rebotes rival promedio: {rival_stats_avg['REB_RIVAL']:.1f}")
        
        return rival_stats_avg
    
    def recalculate_derived_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Recalcula estadísticas derivadas basadas en totales agregados."""
        
        # Recalcular PPP si existe PLAYS
        if 'PLAYS' in df.columns and 'PUNTOS' in df.columns:
            df['PPP'] = (df['PUNTOS'] / df['PLAYS'].replace(0, pd.NA)).round(3)
            logger.info("Recalculado PPP")
        
        # Recalcular OFFRTG si existe POSS
        if 'POSS' in df.columns and 'PUNTOS' in df.columns:
            df['OFFRTG'] = (100 * df['PUNTOS'] / df['POSS'].replace(0, pd.NA)).round(1)
            logger.info("Recalculado OFFRTG")
        
        # Recalcular TS% (True Shooting %)
        if all(col in df.columns for col in ['PUNTOS', 'T2I', 'T3I', 'T1I']):
            tsa = df['T2I'] + df['T3I'] + 0.44 * df['T1I']
            df['TS%'] = (df['PUNTOS'] / (2 * tsa.replace(0, pd.NA)) * 100).round(1)
            logger.info("Recalculado TS%")
        
        # Recalcular EFG% (Effective Field Goal %)
        if all(col in df.columns for col in ['T2C', 'T3C', 'T2I', 'T3I']):
            fga = df['T2I'] + df['T3I']
            df['EFG%'] = ((df['T2C'] + 1.5 * df['T3C']) / fga.replace(0, pd.NA) * 100).round(1)
            logger.info("Recalculado EFG%")
        
        return df
    
    def save_aggregated_data(self, df: pd.DataFrame, rival_stats: Dict):
        """Guarda el DataFrame agregado en Excel junto con estadísticas del rival."""
        try:
            # Crear un ExcelWriter para escribir múltiples hojas
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                # Guardar estadísticas de jugadores en la primera hoja
                df.to_excel(writer, sheet_name='Jugadores', index=False)
                
                # Crear DataFrame con estadísticas del rival y guardarlo en segunda hoja
                df_rival_output = pd.DataFrame([rival_stats])
                df_rival_output.to_excel(writer, sheet_name='Stats_Rival', index=False)
            
            logger.info(f"[OK] Archivo guardado exitosamente: {self.output_file}")
            logger.info(f"   - {len(df)} jugadores")
            logger.info(f"   - {len(df.columns)} columnas de jugadores")
            logger.info(f"   - Estadísticas del rival incluidas")
        except Exception as e:
            logger.error(f"[ERROR] Error al guardar archivo: {e}")
            raise
    
    def run(self):
        """Ejecuta el proceso completo de agregación."""
        try:
            logger.info("=" * 60)
            logger.info("INICIANDO AGREGACIÓN DE BASKET ARANJUEZ")
            logger.info("=" * 60)
            
            # 1. Encontrar archivos
            files = self.find_excel_files()
            
            if not files:
                logger.warning("[AVISO] No se encontraron archivos para procesar")
                return
            
            # 2. Cargar todos los datos
            logger.info("\n" + "=" * 60)
            logger.info("CARGANDO DATOS")
            logger.info("=" * 60)
            combined_df, df_rival = self.load_all_data(files)
            
            # 3. Agregar por jugador
            logger.info("\n" + "=" * 60)
            logger.info("AGREGANDO ESTADÍSTICAS POR JUGADOR")
            logger.info("=" * 60)
            
            # VERIFICACIÓN: Seleccionar un jugador aleatorio para análisis detallado
            import random
            player_col = None
            for col in ['JUGADOR', 'NOMBRE', 'Jugador', 'Nombre']:
                if col in combined_df.columns:
                    player_col = col
                    break
            
            if player_col:
                # Buscar jugadores específicos: Subrá y Pete
                unique_players = combined_df[player_col].unique()
                players_to_check = []
                for p in unique_players:
                    if 'subr' in str(p).lower() or 'pete' in str(p).lower():
                        players_to_check.append(p)
                
                # Si no encontramos Subrá o Pete, elegir uno aleatorio
                if not players_to_check:
                    players_to_check = [random.choice(unique_players)]
                
                for random_player in players_to_check:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"🔍 VERIFICACIÓN DETALLADA - Jugador: {random_player}")
                    logger.info(f"{'='*60}")
                    
                    player_data = combined_df[combined_df[player_col] == random_player]
                    logger.info(f"📊 Partidos encontrados: {len(player_data)}")
                    logger.info(f"\n{'─'*60}")
                    logger.info("DATOS POR PARTIDO:")
                    logger.info(f"{'─'*60}")
                    
                    for idx, row in player_data.iterrows():
                        logger.info(f"\n  Partido #{idx+1}:")
                        stats_to_show = ['MIN', 'MINUTOS JUGADOS', 'MINUTOS', 'PTS', 'PUNTOS', 
                                       'OREB', 'DREB', 'REB', 'TOV', 'AST', 'PERDIDAS', 'ASISTENCIAS',
                                       'REB OFFENSIVO', 'REB DEFENSIVO', 
                                       'T2 CONVERTIDO', 'T2 INTENTADO', 'T3 CONVERTIDO', 'T3 INTENTADO',
                                       'TL CONVERTIDOS', 'TL INTENTADOS', 'Nº', 'DORSAL']
                        for stat in stats_to_show:
                            if stat in row.index:
                                logger.info(f"    {stat:20s}: {row[stat]}")
            
            aggregated_df = self.aggregate_player_stats(combined_df)
            
            # 3.5. Agregar estadísticas del rival
            logger.info("\n" + "=" * 60)
            logger.info("AGREGANDO ESTADÍSTICAS DEL RIVAL")
            logger.info("=" * 60)
            rival_stats_avg = self.aggregate_rival_stats(df_rival)
            
            # 3.7. Mostrar estadísticas agregadas de los jugadores seleccionados
            if player_col and players_to_check:
                for random_player in players_to_check:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"📊 DESPUÉS DE AGREGAR - Jugador: {random_player}")
                    logger.info(f"{'='*60}")
                    
                    player_data = combined_df[combined_df[player_col] == random_player]
                    player_agg = aggregated_df[aggregated_df[player_col] == random_player]
                    
                    if len(player_agg) > 0:
                        row = player_agg.iloc[0]
                        logger.info(f"  Partidos jugados (PJ): {row.get('PJ', 'N/A')}")
                        logger.info(f"\n  PROMEDIOS CALCULADOS:")
                        for stat in stats_to_show:
                            if stat in row.index and stat not in ['Nº', 'DORSAL']:
                                logger.info(f"    {stat:20s}: {row[stat]:.2f}")
                            elif stat in row.index:
                                logger.info(f"    {stat:20s}: {row[stat]}")
                        
                        # Verificar cálculos manualmente
                        logger.info(f"\n  VERIFICACIÓN MANUAL (debe coincidir con promedios):")
                        
                        # PUNTOS
                        if 'PUNTOS' in player_data.columns or 'PTS' in player_data.columns:
                            pts_col = 'PUNTOS' if 'PUNTOS' in player_data.columns else 'PTS'
                            manual_avg_pts = player_data[pts_col].mean()
                            manual_values = player_data[pts_col].tolist()
                            logger.info(f"    PUNTOS por partido: {manual_values}")
                            logger.info(f"    Promedio PUNTOS manual: {manual_avg_pts:.2f}")
                        
                        # PÉRDIDAS (TOV)
                        tov_col = 'TOV' if 'TOV' in player_data.columns else 'PERDIDAS'
                        if tov_col in player_data.columns:
                            manual_avg_tov = player_data[tov_col].mean()
                            manual_values_tov = player_data[tov_col].tolist()
                            logger.info(f"    PERDIDAS (TOV) por partido: {manual_values_tov}")
                            logger.info(f"    Promedio PERDIDAS manual: {manual_avg_tov:.2f}")
                        
                        # REBOTES OFENSIVOS (OREB)
                        oreb_col = 'OREB' if 'OREB' in player_data.columns else 'REB OFFENSIVO'
                        if oreb_col in player_data.columns:
                            manual_avg_oreb = player_data[oreb_col].mean()
                            manual_values_oreb = player_data[oreb_col].tolist()
                            logger.info(f"    REB OFFENSIVO (OREB) por partido: {manual_values_oreb}")
                            logger.info(f"    Promedio REB OFFENSIVO manual: {manual_avg_oreb:.2f}")
                        
                        # REBOTES DEFENSIVOS (DREB)
                        dreb_col = 'DREB' if 'DREB' in player_data.columns else 'REB DEFENSIVO'
                        if dreb_col in player_data.columns:
                            manual_avg_dreb = player_data[dreb_col].mean()
                            manual_values_dreb = player_data[dreb_col].tolist()
                            logger.info(f"    REB DEFENSIVO (DREB) por partido: {manual_values_dreb}")
                            logger.info(f"    Promedio REB DEFENSIVO manual: {manual_avg_dreb:.2f}")
                        
                        # REBOTES TOTALES (REB)
                        if 'REB' in player_data.columns:
                            manual_avg_reb = player_data['REB'].mean()
                            manual_values_reb = player_data['REB'].tolist()
                            logger.info(f"    REB TOTALES por partido: {manual_values_reb}")
                            logger.info(f"    Promedio REB TOTALES manual: {manual_avg_reb:.2f}")
                        
                        # ASISTENCIAS (AST)
                        ast_col = 'AST' if 'AST' in player_data.columns else 'ASISTENCIAS'
                        if ast_col in player_data.columns:
                            manual_avg_ast = player_data[ast_col].mean()
                            manual_values_ast = player_data[ast_col].tolist()
                            logger.info(f"    ASISTENCIAS (AST) por partido: {manual_values_ast}")
                            logger.info(f"    Promedio ASISTENCIAS manual: {manual_avg_ast:.2f}")
                        
                        # MINUTOS
                        min_col = None
                        for col in ['MIN', 'MINUTOS JUGADOS', 'MINUTOS']:
                            if col in player_data.columns:
                                min_col = col
                                break
                        if min_col:
                            manual_avg_min = player_data[min_col].mean()
                            manual_values_min = player_data[min_col].tolist()
                            logger.info(f"    MINUTOS por partido: {manual_values_min}")
                            logger.info(f"    Promedio MINUTOS manual: {manual_avg_min:.2f}")
            
            # 4. Recalcular estadísticas derivadas
            logger.info("\n" + "=" * 60)
            logger.info("RECALCULANDO ESTADÍSTICAS DERIVADAS")
            logger.info("=" * 60)
            aggregated_df = self.recalculate_derived_stats(aggregated_df)
            
            # 5. Guardar resultado
            logger.info("\n" + "=" * 60)
            logger.info("GUARDANDO RESULTADO")
            logger.info("=" * 60)
            self.save_aggregated_data(aggregated_df, rival_stats_avg)
            
            # 6. Resumen final
            logger.info("\n" + "=" * 60)
            logger.info("RESUMEN FINAL")
            logger.info("=" * 60)
            logger.info(f"[OK] Archivos procesados: {len(files)}")
            logger.info(f"[OK] Jugadores agregados: {len(aggregated_df)}")
            logger.info(f"[OK] Archivo generado: {self.output_file.name}")
            
            # Mostrar muestra de jugadores
            if len(aggregated_df) > 0:
                logger.info("\n[DATOS] Muestra de jugadores (top 5 por minutos):")
                
                # Buscar columna de jugador (case-insensitive)
                player_col = None
                for col in aggregated_df.columns:
                    if col.upper() in ['JUGADOR', 'NOMBRE', 'PLAYER']:
                        player_col = col
                        break
                
                # Buscar columna de minutos
                minutes_col = None
                for col in ['MIN', 'MINUTOS JUGADOS', 'MINUTOS']:
                    if col in aggregated_df.columns:
                        minutes_col = col
                        break
                
                # Buscar columna de puntos
                points_col = None
                for col in ['PTS', 'PUNTOS', 'POINTS']:
                    if col in aggregated_df.columns:
                        points_col = col
                        break
                
                if player_col and minutes_col:
                    top_players = aggregated_df.nlargest(5, minutes_col)
                    for _, player in top_players.iterrows():
                        pts = player[points_col] if points_col else 0
                        logger.info(f"   - {player[player_col]}: {player[minutes_col]:.0f} min, "
                                  f"{pts:.0f} pts, "
                                  f"{player.get('PJ', 0):.0f} partidos")
                else:
                    logger.info(f"   Columnas disponibles: {', '.join(aggregated_df.columns[:5])}")
            
            logger.info("\n[COMPLETADO] Proceso finalizado exitosamente")
            
        except Exception as e:
            logger.error(f"\n[ERROR] Error en el proceso: {e}")
            raise


def main():
    """Función principal."""
    aggregator = BasketAranjuezAggregator()
    aggregator.run()


if __name__ == "__main__":
    main()