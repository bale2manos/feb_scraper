import pandas as pd
import os

# Load consolidated file
consolidated_path = r'f:\PyCharm\feb_scraper\data\3FEB_25_26\teams_25_26_3FEB.xlsx'

if not os.path.exists(consolidated_path):
    print(f"ERROR: No se encuentra {consolidated_path}")
    exit(1)

df = pd.read_excel(consolidated_path)

# Filter to GRUPO EGIDO PINTOBASKET
egido = df[df['EQUIPO'] == 'GRUPO EGIDO PINTOBASKET']

print("=" * 80)
print("GRUPO EGIDO PINTOBASKET - CONSOLIDADO")
print("=" * 80)

if len(egido) == 0:
    print("ERROR: No se encuentra el equipo")
    exit(1)

if len(egido) > 1:
    print(f"⚠️ ATENCIÓN: Hay {len(egido)} filas para GRUPO EGIDO (debería ser 1):")
    for idx, row in egido.iterrows():
        print(f"  Fila {idx}: PJ={row['PJ']}, PJ_LOCAL={row.get('PJ_LOCAL', 'N/A')}")
    print()

egido_row = egido.iloc[0]

print(f"PJ total: {egido_row['PJ']}")
print(f"PJ_LOCAL: {egido_row.get('PJ_LOCAL', 'N/A')}")
print(f"PJ_VISITANTE: {egido_row.get('PJ_VISITANTE', 'N/A')}")
print()

print(f"REB DEFENSIVO total: {egido_row['REB DEFENSIVO']}")
print(f"LOCAL_REB DEFENSIVO: {egido_row.get('LOCAL_REB DEFENSIVO', 'N/A')}")
print(f"VISITANTE_REB DEFENSIVO: {egido_row.get('VISITANTE_REB DEFENSIVO', 'N/A')}")
print()

print(f"PUNTOS + total: {egido_row['PUNTOS +']}")
print(f"LOCAL_PUNTOS +: {egido_row.get('LOCAL_PUNTOS +', 'N/A')}")
print(f"VISITANTE_PUNTOS +: {egido_row.get('VISITANTE_PUNTOS +', 'N/A')}")
print()

# Check what columns exist
local_cols = [col for col in df.columns if col.startswith('LOCAL_')]
visitante_cols = [col for col in df.columns if col.startswith('VISITANTE_')]

print(f"Columnas LOCAL_: {len(local_cols)}")
print(f"Columnas VISITANTE_: {len(visitante_cols)}")
print()

# Show first few LOCAL_ columns
if local_cols:
    print(f"Primeras columnas LOCAL_:")
    for col in local_cols[:10]:
        val = egido_row.get(col, 'N/A')
        print(f"  {col}: {val}")
