#!/usr/bin/env python3
"""
Script to consolidate jornada data into main folders.

This script automatically detects folders with pattern like "3FEB_25_26_jX" 
and consolidates the data into the main folder "3FEB_25_26".

For aggregated files (clutch_aggregated, players, teams): Performs aggregation (sum/average as appropriate)
For other files: Appends/concatenates the data

Usage: python consolidate_journadas.py
"""

import os
import re
import pandas as pd
from pathlib import Path
import logging
from typing import List, Dict, Tuple
import shutil
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('consolidate_journadas.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JornadaConsolidator:
    def __init__(self, data_dir: str = "data", target_pattern: str = None):
        self.data_dir = Path(data_dir)
        self.target_pattern = target_pattern
        self.aggregated_files = {
            'clutch_aggregated': 'sum',  # Sum stats for clutch
            'players': 'sum',           # Sum player stats 
            'teams': 'sum'              # Sum team stats
        }
        self.append_files = [
            'assists', 'boxscores', 'clutch_data', 
            'clutch_lineups', 'players_games'
        ]
        # Cache for home/away mappings
        self._home_away_cache = {}
    
    def find_jornada_patterns(self) -> Dict[str, List[str]]:
        """Find all folders matching jornada patterns and group by base name."""
        pattern = re.compile(r'^(.+)_j(\d+)$')
        groups = {}
        
        for folder in self.data_dir.iterdir():
            if folder.is_dir():
                match = pattern.match(folder.name)
                if match:
                    base_name = match.group(1)
                    jornada_num = int(match.group(2))
                    
                    # Filter by target pattern if specified
                    if self.target_pattern and self.target_pattern not in base_name:
                        continue
                    
                    if base_name not in groups:
                        groups[base_name] = []
                    groups[base_name].append((folder.name, jornada_num))
        
        # Sort jornadas by number
        for base_name in groups:
            groups[base_name].sort(key=lambda x: x[1])
        
        return groups
    
    def backup_main_folder(self, main_folder: Path):
        """Create backup of main folder before consolidation."""
        if main_folder.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = main_folder.parent / f"{main_folder.name}_backup_{timestamp}"
            logger.info(f"Creating backup: {backup_path}")
            shutil.copytree(main_folder, backup_path)
            return backup_path
        return None
    
    def get_file_matches(self, folder: Path) -> Dict[str, Path]:
        """Get all Excel files in folder and categorize them."""
        files = {}
        for file_path in folder.glob("*.xlsx"):
            file_name = file_path.stem
            
            # First check for players_games specifically (must come before players check)
            if 'players' in file_name and 'games' in file_name:
                files['players_games'] = file_path
                continue
            
            # Check for boxscores (needed for home/away detection)
            if 'boxscores' in file_name:
                files['boxscores'] = file_path
                continue
            
            # Then check aggregated files patterns
            matched = False
            for pattern in self.aggregated_files.keys():
                if pattern in file_name:
                    files[pattern] = file_path
                    matched = True
                    break
            
            # If not matched in aggregated, check append patterns
            if not matched:
                for pattern in self.append_files:
                    if pattern in file_name and pattern != 'players_games' and pattern != 'boxscores':
                        files[pattern] = file_path
                        break
        return files
    
    def determine_home_away_from_boxscores(self, boxscores_path: Path) -> Dict[str, Dict]:
        """
        Determine which team is home/away for each game from boxscores.
        Returns dict: {(jornada, team1, team2): {'home': str, 'away': str}}
        Uses normalized team order (alphabetical) to handle duplicate game entries.
        Determines home team based on which group appears first in the file.
        """
        try:
            df = pd.read_excel(boxscores_path)
            
            if 'EQUIPO LOCAL' not in df.columns or 'EQUIPO RIVAL' not in df.columns:
                logger.warning(f"Missing required columns in {boxscores_path}")
                return {}
            
            home_away_map = {}
            
            # Group by game (JORNADA, EQUIPO LOCAL, EQUIPO RIVAL)
            game_groups = df.groupby(['JORNADA', 'EQUIPO LOCAL', 'EQUIPO RIVAL'])
            
            logger.info(f"\nAnalizando partidos en {boxscores_path.name}:")
            
            # Track games we've already processed (to avoid duplicates)
            # Store: {(jornada, team1, team2): (first_row_index, home_team, away_team)}
            processed_games = {}
            
            for (jornada, equipo_local_col, equipo_rival_col), group in game_groups:
                # Create normalized key (alphabetical order) to detect duplicates
                teams_sorted = tuple(sorted([equipo_local_col, equipo_rival_col]))
                game_key = (jornada, teams_sorted[0], teams_sorted[1])
                
                # The first team that appears is the actual home team
                first_team = group.iloc[0]['EQUIPO LOCAL']
                
                # Determine home and away for this group
                if first_team == equipo_local_col:
                    home_team = equipo_local_col
                    away_team = equipo_rival_col
                else:
                    home_team = equipo_rival_col
                    away_team = equipo_local_col
                
                # Get the actual row index in the original DataFrame
                first_row_index = group.index[0]
                
                # If we haven't seen this game yet, or if this group appears earlier in file
                if game_key not in processed_games or first_row_index < processed_games[game_key][0]:
                    processed_games[game_key] = (first_row_index, home_team, away_team)
            
            # Convert to final format and log
            for game_key, (first_row_idx, home_team, away_team) in processed_games.items():
                jornada = game_key[0]
                home_away_map[game_key] = {
                    'home': home_team,
                    'away': away_team
                }
                
                # Log especial para GRUPO EGIDO PINTOBASKET
                if 'EGIDO' in home_team or 'EGIDO' in away_team:
                    logger.info(f"  J{jornada}: {home_team} (local) vs {away_team} (visitante)")
            
            logger.info(f"Extracted home/away info for {len(home_away_map)} unique games from {boxscores_path.name}")
            return home_away_map
            
        except Exception as e:
            logger.error(f"Error reading boxscores {boxscores_path}: {e}")
            return {}
    
    def aggregate_dataframe(self, dfs: List[pd.DataFrame], agg_type: str, file_type: str, home_away_map: Dict = None) -> pd.DataFrame:
        """Aggregate multiple dataframes based on type."""
        if not dfs:
            return pd.DataFrame()
        
        if len(dfs) == 1:
            return dfs[0]
        
        # Combine all dataframes
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # For teams file, add home/away columns if we have the mapping
        if file_type == 'teams' and home_away_map:
            combined_df = self._add_home_away_columns(combined_df, home_away_map)
        
        if agg_type == 'sum':
            if file_type in ['clutch_aggregated', 'players', 'teams']:
                # For stats files, group by key columns and sum numeric columns
                if file_type == 'players':
                    group_cols = ['JUGADOR', 'EQUIPO']
                    if 'FASE' in combined_df.columns:
                        group_cols.append('FASE')
                    # DORSAL no se usa como clave de agrupación, se tomará el último
                elif file_type == 'teams':
                    group_cols = ['EQUIPO']
                    if 'FASE' in combined_df.columns:
                        group_cols.append('FASE')
                elif file_type == 'clutch_aggregated':
                    group_cols = ['JUGADOR', 'EQUIPO']
                    if 'FASE' in combined_df.columns:
                        group_cols.append('FASE')
                    # DORSAL no se usa como clave de agrupación, se tomará el último
                
                # Define columns that should be averaged instead of summed
                # NOTE: Use exact column names to avoid partial matches (e.g., 'PER' in 'PERDIDAS', 'RECUPEROS')
                average_cols_exact = [
                    'PER',                     # Player Efficiency Rating (exact match only)
                    'PACE'                     # Pace factor (exact match only)
                ]
                
                average_cols_contains = [
                    '%REB', '%OREB', '%DREB',  # Rebound percentages
                    'PPP', 'PPP OPP',          # Points per possession
                    'OFFRTG', 'DEFRTG', 'NETRTG',  # Ratings
                    'TS%', 'EFG%',             # Shooting percentages
                    'TOV%',                    # Turnover percentage
                    '%AST',                    # Assist percentage
                    'USG%',                    # Usage percentage
                    'FG%', '2P%', '3P%', 'FT%',  # Field goal percentages
                    'ORB%', 'DRB%', 'TRB%',   # Additional rebound percentages
                    'AST%', 'STL%', 'BLK%',   # Additional stat percentages
                ]
                
                # Identify numeric columns to sum or average
                numeric_cols = combined_df.select_dtypes(include=['number']).columns.tolist()
                # Remove group columns from numeric columns
                numeric_cols = [col for col in numeric_cols if col not in group_cols]
                
                if numeric_cols:
                    # Create aggregation dictionary
                    agg_dict = {}
                    
                    for col in numeric_cols:
                        # Check if this column should be averaged
                        # First check exact matches, then check if pattern is contained in column name
                        should_average = (col in average_cols_exact or 
                                        any(pattern in col for pattern in average_cols_contains))
                        if should_average:
                            agg_dict[col] = 'mean'
                        else:
                            agg_dict[col] = 'sum'
                    
                    # Sort by JORNADA before aggregation to ensure 'last' means latest jornada
                    if 'JORNADA' in combined_df.columns:
                        combined_df = combined_df.sort_values('JORNADA')
                    
                    # For DORSAL, take the last two unique values only if different in recent games
                    if 'DORSAL' in combined_df.columns and 'DORSAL' not in group_cols:
                        def get_last_two_dorsals(series):
                            # Take last 5 values (most recent games)
                            recent_dorsals = series.dropna().tail(5)
                            if len(recent_dorsals) == 0:
                                return ''
                            
                            # Get unique dorsals in last 5 games
                            unique_recent = recent_dorsals.unique()
                            
                            # If only one dorsal in last 5 games, return just that one
                            if len(unique_recent) == 1:
                                return str(unique_recent[-1])
                            
                            # If multiple dorsals in last 5 games, get last two unique from full series
                            all_unique_dorsals = series.dropna().unique()
                            if len(all_unique_dorsals) <= 1:
                                return str(all_unique_dorsals[-1]) if len(all_unique_dorsals) > 0 else ''
                            else:
                                # Return last two in format: most_recent/second_most_recent
                                return f"{all_unique_dorsals[-1]}/{all_unique_dorsals[-2]}"
                        agg_dict['DORSAL'] = get_last_two_dorsals
                    
                    # For non-numeric, non-group columns, take first value
                    other_cols = [col for col in combined_df.columns 
                                if col not in group_cols and col not in numeric_cols and col != 'DORSAL']
                    for col in other_cols:
                        agg_dict[col] = 'first'
                    
                    result_df = combined_df.groupby(group_cols, as_index=False).agg(agg_dict)
                    
                    # Log what was summed vs averaged
                    summed_cols = [col for col, agg in agg_dict.items() if agg == 'sum']
                    averaged_cols = [col for col, agg in agg_dict.items() if agg == 'mean']
                    
                    logger.info(f"Aggregated {len(combined_df)} rows to {len(result_df)} rows for {file_type}")
                    if summed_cols:
                        logger.info(f"  SUMMED ({len(summed_cols)} cols): {', '.join(summed_cols[:5])}{'...' if len(summed_cols) > 5 else ''}")
                    if averaged_cols:
                        logger.info(f"  AVERAGED ({len(averaged_cols)} cols): {', '.join(averaged_cols)}")
                    
                    return result_df
        
        # If aggregation logic doesn't apply, return combined dataframe
        logger.warning(f"No specific aggregation logic for {file_type}, returning combined data")
        return combined_df
    
    def _add_home_away_columns(self, df: pd.DataFrame, home_away_map: Dict) -> pd.DataFrame:
        """
        Add LOCAL_ and VISITANTE_ prefixed columns to teams dataframe.
        This should be called BEFORE aggregation on the combined dataframe.
        """
        logger.info("Adding home/away split columns to teams data...")
        
        # Check required columns
        required_cols = ['EQUIPO', 'JORNADA']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"Required columns {required_cols} not found, skipping home/away split")
            return df
        
        # Identify numeric columns to split (exclude identifying columns)
        exclude_cols = ['EQUIPO', 'FASE', 'JORNADA', 'DORSAL', 'PJ']
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        cols_to_split = [col for col in numeric_cols if col not in exclude_cols]
        
        if not cols_to_split:
            logger.warning("No numeric columns found to split")
            return df
        
        # Initialize new columns with NaN (not 0) so mean() only averages actual values
        # Use the same dtype as the original column to ensure numeric columns stay numeric
        for col in cols_to_split:
            original_dtype = df[col].dtype
            # For numeric types, use nullable versions (Int64, Float64)
            if pd.api.types.is_integer_dtype(original_dtype):
                df[f'LOCAL_{col}'] = pd.Series([pd.NA] * len(df), dtype='Int64')
                df[f'VISITANTE_{col}'] = pd.Series([pd.NA] * len(df), dtype='Int64')
            elif pd.api.types.is_float_dtype(original_dtype):
                df[f'LOCAL_{col}'] = pd.Series([pd.NA] * len(df), dtype='Float64')
                df[f'VISITANTE_{col}'] = pd.Series([pd.NA] * len(df), dtype='Float64')
            else:
                # For non-numeric types, use object dtype
                df[f'LOCAL_{col}'] = pd.NA
                df[f'VISITANTE_{col}'] = pd.NA
        
        # Create a helper to find home/away status for each row
        def get_home_away_status(row):
            equipo = row['EQUIPO']
            jornada = row['JORNADA']
            
            # Search in home_away_map (keys are normalized: jornada, team1_alpha, team2_alpha)
            for (map_jornada, team1, team2), teams in home_away_map.items():
                if map_jornada == jornada:
                    # Check if this team is in this game
                    if equipo == teams['home']:
                        return 'home'
                    elif equipo == teams['away']:
                        return 'away'
            
            # Debug: si no se encontró y es EGIDO, mostrar qué partidos hay en esta jornada
            if 'EGIDO' in str(equipo):
                logger.warning(f"    No match found for '{equipo}' in J{jornada}")
                logger.warning(f"    Available games in J{jornada}:")
                for (map_jornada, team1, team2), teams in home_away_map.items():
                    if map_jornada == jornada:
                        logger.warning(f"      - {teams['home']} (local) vs {teams['away']} (visitante)")
            
            return None
        
        # Initialize counters columns
        df['PJ_LOCAL'] = 0
        df['PJ_VISITANTE'] = 0
        
        # Process each row
        home_count = 0
        away_count = 0
        unknown_count = 0
        
        logger.info(f"\n🔍 Clasificando partidos por localía:")
        
        for idx, row in df.iterrows():
            status = get_home_away_status(row)
            equipo = row['EQUIPO']
            jornada = row['JORNADA']
            
            # Log especial para GRUPO EGIDO PINTOBASKET
            if 'EGIDO' in str(equipo):
                logger.info(f"  📌 {equipo} - J{jornada}: status='{status}'")
            
            if status == 'home':
                home_count += 1
                df.at[idx, 'PJ_LOCAL'] = 1
                for col in cols_to_split:
                    value = row[col]
                    if pd.notna(value):
                        df.at[idx, f'LOCAL_{col}'] = value
            elif status == 'away':
                away_count += 1
                df.at[idx, 'PJ_VISITANTE'] = 1
                for col in cols_to_split:
                    value = row[col]
                    if pd.notna(value):
                        df.at[idx, f'VISITANTE_{col}'] = value
            else:
                unknown_count += 1
                if 'EGIDO' in str(equipo):
                    logger.warning(f"  ⚠️  {equipo} - J{jornada}: NO SE PUDO DETERMINAR localía")
        
        logger.info(f"\nAdded {len(cols_to_split)} LOCAL_ and {len(cols_to_split)} VISITANTE_ columns")
        logger.info(f"Columns split: {', '.join(cols_to_split[:5])}{'...' if len(cols_to_split) > 5 else ''}")
        logger.info(f"Classified: {home_count} home games, {away_count} away games, {unknown_count} unknown")
        
        return df
    
    def append_dataframes(self, dfs: List[pd.DataFrame]) -> pd.DataFrame:
        """Simply concatenate dataframes for append operations."""
        if not dfs:
            return pd.DataFrame()
        
        result_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Appended {len(dfs)} files with total {len(result_df)} rows")
        return result_df
    
    def consolidate_group(self, base_name: str, jornada_folders: List[Tuple[str, int]]):
        """Consolidate a group of jornada folders into the main folder."""
        logger.info(f"\n=== Consolidating {base_name} ===")
        logger.info(f"Jornadas found: {[f[0] for f in jornada_folders]}")
        
        main_folder = self.data_dir / base_name
        
        # Create backup if main folder exists
        backup_path = self.backup_main_folder(main_folder)
        
        # Ensure main folder exists
        main_folder.mkdir(exist_ok=True)
        
        # Build home/away mapping from all boxscores
        home_away_map = {}
        for folder_name, jornada_num in jornada_folders:
            folder_path = self.data_dir / folder_name
            if not folder_path.exists():
                continue
            
            boxscores_files = list(folder_path.glob("*boxscores*.xlsx"))
            if boxscores_files:
                map_data = self.determine_home_away_from_boxscores(boxscores_files[0])
                home_away_map.update(map_data)
        
        logger.info(f"Built home/away mapping with {len(home_away_map)} games")
        
        # Collect all files from jornada folders
        all_files = {}  # file_type -> list of dataframes
        
        for folder_name, jornada_num in jornada_folders:
            folder_path = self.data_dir / folder_name
            if not folder_path.exists():
                logger.warning(f"Folder {folder_path} not found, skipping")
                continue
            
            files = self.get_file_matches(folder_path)
            logger.info(f"Found {len(files)} files in {folder_name}: {list(files.keys())}")
            
            for file_type, file_path in files.items():
                try:
                    df = pd.read_excel(file_path)
                    logger.info(f"Loaded {file_path.name}: {len(df)} rows")
                    
                    # For teams file, add JORNADA column if not present (since it's per-jornada data)
                    if file_type == 'teams' and 'JORNADA' not in df.columns:
                        df['JORNADA'] = jornada_num
                        logger.info(f"  Added JORNADA={jornada_num} to teams data")
                    
                    if file_type not in all_files:
                        all_files[file_type] = []
                    all_files[file_type].append(df)
                    
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        # Process each file type
        for file_type, dfs in all_files.items():
            try:
                if file_type in self.aggregated_files:
                    # Aggregate
                    agg_type = self.aggregated_files[file_type]
                    result_df = self.aggregate_dataframe(dfs, agg_type, file_type, home_away_map)
                    operation = "aggregated"
                else:
                    # Append
                    result_df = self.append_dataframes(dfs)
                    operation = "appended"
                
                if not result_df.empty:
                    # Find a sample file to get the correct filename pattern
                    sample_folder = self.data_dir / jornada_folders[0][0]
                    sample_files = list(sample_folder.glob(f"*{file_type}*.xlsx"))
                    
                    if sample_files:
                        # Use the same filename pattern as the sample
                        output_filename = sample_files[0].name
                        output_path = main_folder / output_filename
                        
                        result_df.to_excel(output_path, index=False)
                        logger.info(f"SUCCESS {operation} {file_type}: {len(result_df)} rows -> {output_path}")
                    else:
                        logger.warning(f"No sample file found for {file_type}")
                else:
                    logger.warning(f"Empty result for {file_type}")
                    
            except Exception as e:
                logger.error(f"Error processing {file_type}: {e}")
        
        logger.info(f"Consolidation complete for {base_name}")
        if backup_path:
            logger.info(f"Backup created at: {backup_path}")
    
    def run(self):
        """Main execution method."""
        logger.info("Starting jornada consolidation process")
        
        if not self.data_dir.exists():
            logger.error(f"Data directory {self.data_dir} does not exist")
            return
        
        groups = self.find_jornada_patterns()
        
        if not groups:
            logger.info("No jornada patterns found to consolidate")
            return
        
        logger.info(f"Found {len(groups)} groups to consolidate:")
        for base_name, jornadas in groups.items():
            logger.info(f"  {base_name}: {len(jornadas)} jornadas")
        
        for base_name, jornadas in groups.items():
            try:
                self.consolidate_group(base_name, jornadas)
            except Exception as e:
                logger.error(f"Error consolidating {base_name}: {e}")
        
        logger.info("Consolidation process completed!")

def discover_available_patterns(data_dir: Path) -> Dict[str, List[str]]:
    """Discover all available category/season patterns."""
    pattern = re.compile(r'^(.+)_j(\d+)$')
    base_names = set()
    
    for folder in data_dir.iterdir():
        if folder.is_dir():
            match = pattern.match(folder.name)
            if match:
                base_names.add(match.group(1))
    
    # Group by category and season
    categories = {}
    for base_name in sorted(base_names):
        # Extract category and season info
        # Examples: 3FEB_25_26, 1FEB_24_25, 2FEB_24_25
        parts = base_name.split('_')
        if len(parts) >= 3:
            category = parts[0]  # 3FEB, 1FEB, 2FEB
            season = '_'.join(parts[1:])  # 25_26, 24_25
            
            if category not in categories:
                categories[category] = []
            if season not in categories[category]:
                categories[category].append(season)
    
    # Sort seasons
    for category in categories:
        categories[category].sort(reverse=True)  # Most recent first
    
    return categories

def select_target_pattern() -> str:
    """Interactive selection of target pattern."""
    data_dir = Path("data")
    
    if not data_dir.exists():
        print("❌ Data directory not found")
        return None
    
    patterns = discover_available_patterns(data_dir)
    
    if not patterns:
        print("❌ No jornada patterns found in data directory")
        return None
    
    print("📂 Available categories and seasons:")
    print()
    
    all_options = []
    option_num = 1
    
    for category in sorted(patterns.keys()):
        print(f"  🎯 {category}:")
        for season in patterns[category]:
            full_pattern = f"{category}_{season}"
            print(f"    {option_num:2d}. {full_pattern}")
            all_options.append(full_pattern)
            option_num += 1
    
    print()
    print("  0. Process ALL categories/seasons")
    print()
    
    # Set default
    default_pattern = "3FEB_25_26"
    default_num = None
    if default_pattern in all_options:
        default_num = all_options.index(default_pattern) + 1
        print(f"💡 Default: {default_num} ({default_pattern})")
    
    while True:
        prompt = f"❓ Select option (0-{len(all_options)})"
        if default_num:
            prompt += f" [default: {default_num}]"
        prompt += ": "
        
        choice = input(prompt).strip()
        
        # Use default if empty
        if not choice and default_num:
            choice = str(default_num)
        
        try:
            choice_num = int(choice)
            if choice_num == 0:
                return None  # Process all
            elif 1 <= choice_num <= len(all_options):
                selected = all_options[choice_num - 1]
                print(f"✅ Selected: {selected}")
                return selected
            else:
                print(f"❌ Please enter a number between 0 and {len(all_options)}")
        except ValueError:
            print("❌ Please enter a valid number")

def main():
    """Main function."""
    print("🏀 FEB Jornada Data Consolidator")
    print("=" * 50)
    
    # Select target pattern
    target_pattern = select_target_pattern()
    
    consolidator = JornadaConsolidator(target_pattern=target_pattern)
    
    # Show what will be processed
    groups = consolidator.find_jornada_patterns()
    if not groups:
        if target_pattern:
            print(f"❌ No jornada patterns found for '{target_pattern}'")
        else:
            print("❌ No jornada patterns found to consolidate")
        return
    
    print("\n📋 Found the following groups to consolidate:")
    for base_name, jornadas in groups.items():
        print(f"  🎯 {base_name}:")
        for folder_name, jornada_num in jornadas:
            print(f"    📁 {folder_name}")
    
    print("\n📊 File processing strategy:")
    print("  🔢 AGGREGATE (sum): clutch_aggregated, players, teams")
    print("  📝 APPEND (concatenate): assists, boxscores, clutch_data, clutch_lineups, players_games")
    
    # Ask for confirmation
    response = input("\n❓ Do you want to proceed? (Y/n): ").strip().lower()
    if response == 'n':
        print("❌ Operation cancelled")
        return
    
    # Run consolidation
    consolidator.run()

if __name__ == "__main__":
    main()