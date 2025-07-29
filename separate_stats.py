import pandas as pd
import openpyxl
from openpyxl import load_workbook

def separate_player_team_stats():
    """
    Reads the estadisticas_manu.xlsx file and creates new sheets separating
    player statistics from team totals.
    """
    
    # Load the Excel file
    file_path = 'estadisticas_manu.xlsx'
    
    try:
        # Read the existing sheets
        df_bb_historico = pd.read_excel(file_path, sheet_name='EBA BB HISTORICO')
        df_ba_historico = pd.read_excel(file_path, sheet_name='EBA BA HISTORICO')
        
        print("Original sheets loaded successfully!")
        print(f"EBA BB Historico shape: {df_bb_historico.shape}")
        print(f"EBA BA Historico shape: {df_ba_historico.shape}")
        
        # Check the structure of the data
        print("\nColumns in EBA BB Historico:")
        print(df_bb_historico.columns.tolist())
        
        print("\nFirst few rows of EBA BB Historico:")
        print(df_bb_historico.head(10))
        
        print("\nUnique values in JUGADOR column (first 20):")
        print(df_bb_historico['JUGADOR'].unique()[:20])
        
        # Separate players from team totals for BB Historico
        # Players have names in JUGADOR column, team totals have '0'
        bb_players = df_bb_historico[df_bb_historico['JUGADOR'] != 0].copy()
        bb_totals = df_bb_historico[df_bb_historico['JUGADOR'] == 0].copy()
        
        # Separate players from team totals for BA Historico
        ba_players = df_ba_historico[df_ba_historico['JUGADOR'] != 0].copy()
        ba_totals = df_ba_historico[df_ba_historico['JUGADOR'] == 0].copy()
        
        print(f"\nBB Players: {len(bb_players)} rows")
        print(f"BB Totals: {len(bb_totals)} rows")
        print(f"BA Players: {len(ba_players)} rows")
        print(f"BA Totals: {len(ba_totals)} rows")
        
        # Create a new Excel file with separated data
        output_file = 'estadisticas_manu_separated.xlsx'
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Write the original sheets
            df_bb_historico.to_excel(writer, sheet_name='EBA BB Historico', index=False)
            df_ba_historico.to_excel(writer, sheet_name='EBA BA Historico', index=False)
            
            # Write the separated sheets
            bb_players.to_excel(writer, sheet_name='EBA BB Players', index=False)
            bb_totals.to_excel(writer, sheet_name='EBA BB Totals', index=False)
            ba_players.to_excel(writer, sheet_name='EBA BA Players', index=False)
            ba_totals.to_excel(writer, sheet_name='EBA BA Totals', index=False)
        
        print(f"\nNew file created: {output_file}")
        print("Sheets created:")
        print("- EBA BB Historico (original)")
        print("- EBA BA Historico (original)")
        print("- EBA BB Players (players only)")
        print("- EBA BB Totals (team totals only)")
        print("- EBA BA Players (players only)")
        print("- EBA BA Totals (team totals only)")
        
        return output_file
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    separate_player_team_stats()
