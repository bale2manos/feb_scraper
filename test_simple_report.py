#!/usr/bin/env python3
"""
Test simple para verificar build_team_report
"""

import sys
import os

# Agregar el directorio al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simple():
    """
    Test simple para verificar que no hay errores básicos
    """
    try:
        from team_report.build_team_report import build_team_report
        
        print("=== TEST SIMPLE DE TEAM REPORT ===")
        
        # Usar archivos existentes
        players_file = "./data/1FEB_24_25/players_24_25_1FEB.xlsx"
        teams_file = "./data/1FEB_24_25/teams_24_25_1FEB.xlsx"
        clutch_lineups_file = "./data/1FEB_24_25/clutch_lineups_24_25_1FEB.xlsx"
        
        if not all(os.path.exists(f) for f in [players_file, teams_file, clutch_lineups_file]):
            print("❌ No se encontraron todos los archivos necesarios")
            return
        
        # Probar con un equipo simple y filtros en 0
        print("🔄 Probando generación con filtros en 0...")
        
        pdf_path = build_team_report(
            team_filter="ALIMERKA OVIEDO BALONCESTO",  # Usar un equipo que existe
            player_filter=None,
            players_file=players_file,
            teams_file=teams_file,
            clutch_lineups_file=clutch_lineups_file,
            assists_file=None,
            min_games=0,    # ← Probar con 0
            min_minutes=0,  # ← Probar con 0
            min_shots=0     # ← Probar con 0
        )
        
        if pdf_path:
            print(f"✅ PDF generado exitosamente: {pdf_path}")
        else:
            print("❌ No se generó el PDF")
            
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple()