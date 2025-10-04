#!/usr/bin/env python3
"""
Script simple para verificar las columnas de los datos
"""

import pandas as pd
import sys
import os

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_columns():
    """
    Verificar las columnas disponibles en los archivos de datos
    """
    try:
        # Buscar archivos disponibles
        data_dirs = ['./data/1FEB_24_25', './data/2FEB_24_25', './data/3FEB_24_25']
        
        print("=== VERIFICANDO COLUMNAS EN DATOS ===")
        
        for data_dir in data_dirs:
            if os.path.exists(data_dir):
                print(f"\n📁 Directorio: {data_dir}")
                files = os.listdir(data_dir)
                for file in files:
                    if 'players' in file.lower() or 'jugadores' in file.lower():
                        file_path = os.path.join(data_dir, file)
                        print(f"\n📄 Archivo encontrado: {file}")
                        
                        if file.endswith('.xlsx'):
                            df = pd.read_excel(file_path)
                            print(f"Shape: {df.shape}")
                            print("\nColumnas disponibles:")
                            for i, col in enumerate(df.columns, 1):
                                print(f"{i:2d}. {col}")
                            
                            # Buscar columnas relacionadas con minutos
                            print("\n=== COLUMNAS RELACIONADAS CON MINUTOS ===")
                            minutos_cols = [col for col in df.columns if 'MINUTO' in col.upper()]
                            if minutos_cols:
                                for col in minutos_cols:
                                    print(f"- {col}")
                            else:
                                print("No se encontraron columnas relacionadas con 'MINUTO'")
                            
                            # Buscar columnas relacionadas con partidos
                            print("\n=== COLUMNAS RELACIONADAS CON PARTIDOS ===")
                            partidos_cols = [col for col in df.columns if 'PJ' in col.upper() or 'PARTIDO' in col.upper()]
                            if partidos_cols:
                                for col in partidos_cols:
                                    print(f"- {col}")
                            else:
                                print("No se encontraron columnas relacionadas con 'PJ' o 'PARTIDO'")
                            
                            return  # Solo mostrar el primer archivo encontrado
                
        print("❌ No se encontraron archivos de jugadores en los directorios de datos")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_columns()