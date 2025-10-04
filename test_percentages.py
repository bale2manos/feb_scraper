#!/usr/bin/env python3
"""
Script de prueba para verificar que los porcentajes de tiros se muestran correctamente
"""

import pandas as pd
import sys
import os

# Agregar el directorio padre al path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from team_report_bars.build_team_report_bars import compute_advanced_stats_bars

def test_shooting_percentages():
    """
    Probar que los porcentajes de tiros se calculan correctamente
    """
    # Datos de prueba que simulan stats de un jugador
    test_stats = pd.Series({
        'TL CONVERTIDOS': 8,     # 8 tiros libres convertidos
        'TL INTENTADOS': 10,     # 10 tiros libres intentados = 80%
        'T2 CONVERTIDO': 15,     # 15 tiros de 2 convertidos
        'T2 INTENTADO': 25,      # 25 tiros de 2 intentados = 60%
        'T3 CONVERTIDO': 6,      # 6 tiros de 3 convertidos  
        'T3 INTENTADO': 20,      # 20 tiros de 3 intentados = 30%
        'REBOTES DEFENSIVOS': 5,
        'REBOTES OFENSIVOS': 2,
        'ASISTENCIAS': 8,
        'PP': 5,
        'ROBOS': 2,
        'TAPONES': 1
    })
    
    result = compute_advanced_stats_bars(test_stats)
    
    print("=== RESULTADOS DE PORCENTAJES DE TIROS ===")
    print(f"T1% (Tiros libres): {result['T1 %']:.1f}% (esperado: 80.0%)")
    print(f"T2% (Tiros de 2): {result['T2 %']:.1f}% (esperado: 60.0%)")
    print(f"T3% (Tiros de 3): {result['T3 %']:.1f}% (esperado: 30.0%)")
    
    print("\n=== RESULTADOS DE PORCENTAJES DE PLAYS ===")
    print(f"F1 Plays%: {result['F1 Plays%']:.1f}%")
    print(f"F2 Plays%: {result['F2 Plays%']:.1f}%")
    print(f"F3 Plays%: {result['F3 Plays%']:.1f}%")
    
    # Verificar que los porcentajes son diferentes
    if (abs(result['T1 %'] - 80.0) < 0.1 and 
        abs(result['T2 %'] - 60.0) < 0.1 and 
        abs(result['T3 %'] - 30.0) < 0.1):
        print("\n✅ ÉXITO: Los porcentajes de tiros se calculan correctamente!")
        return True
    else:
        print("\n❌ ERROR: Los porcentajes de tiros no coinciden con los esperados.")
        return False

if __name__ == "__main__":
    test_shooting_percentages()