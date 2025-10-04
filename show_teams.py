#!/usr/bin/env python3
"""
Ver equipos disponibles en los datos
"""

import pandas as pd
import os

def show_teams():
    """
    Mostrar equipos disponibles
    """
    try:
        players_file = "./data/1FEB_24_25/players_24_25_1FEB.xlsx"
        
        if os.path.exists(players_file):
            df = pd.read_excel(players_file)
            equipos = sorted(df['EQUIPO'].dropna().unique().tolist())
            
            print("=== EQUIPOS DISPONIBLES ===")
            for i, equipo in enumerate(equipos, 1):
                jugadores_count = df[df['EQUIPO'] == equipo].shape[0]
                print(f"{i:2d}. {equipo} ({jugadores_count} jugadores)")
                
        else:
            print(f"❌ No se encontró el archivo: {players_file}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_teams()