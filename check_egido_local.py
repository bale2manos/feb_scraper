import pandas as pd

# Archivo consolidado
df = pd.read_excel('f:/PyCharm/feb_scraper/data/3FEB_25_26/teams_25_26_3FEB.xlsx')
egido = df[df['EQUIPO'].str.contains('EGIDO', na=False)]

print('=== GRUPO EGIDO PINTOBASKET ===')
print(f'\nPartidos jugados:')
print(f'  PJ total: {egido["PJ"].values[0]}')
print(f'  PJ_LOCAL: {egido["PJ_LOCAL"].values[0]}')
print(f'  PJ_VISITANTE: {egido["PJ_VISITANTE"].values[0]}')

print(f'\n=== REBOTES DEFENSIVOS ===')
print(f'REB DEFENSIVO total: {egido["REB DEFENSIVO"].values[0]}')
print(f'LOCAL_REB DEFENSIVO (suma de 3 partidos): {egido["LOCAL_REB DEFENSIVO"].values[0] if "LOCAL_REB DEFENSIVO" in egido.columns else "No existe"}')

if "LOCAL_REB DEFENSIVO" in egido.columns:
    local_reb_def = egido["LOCAL_REB DEFENSIVO"].values[0]
    pj_local = egido["PJ_LOCAL"].values[0]
    print(f'\nPROMEDIO CORRECTO por partido local: {local_reb_def} / {pj_local} = {local_reb_def / pj_local:.2f}')

print(f'\n=== PUNTOS ===')
print(f'PUNTOS + total: {egido["PUNTOS +"].values[0]}')
if 'LOCAL_PUNTOS +' in egido.columns:
    local_puntos = egido["LOCAL_PUNTOS +"].values[0]
    pj_local = egido["PJ_LOCAL"].values[0]
    print(f'LOCAL_PUNTOS + (suma de 3 partidos): {local_puntos}')
    print(f'\nPROMEDIO CORRECTO por partido local: {local_puntos} / {pj_local} = {local_puntos / pj_local:.2f}')

# Verificar en partidos individuales
print(f'\n=== VERIFICACIÓN EN PARTIDOS INDIVIDUALES (LOCALES) ===')
total_reb_def_local = 0
total_puntos_local = 0
partidos_local = 0

for j in [1, 3, 6]:  # Jornadas donde EGIDO es local
    try:
        df_j = pd.read_excel(f'f:/PyCharm/feb_scraper/data/3FEB_25_26_j{j}/teams_25_26_3FEB.xlsx')
        egido_j = df_j[df_j['EQUIPO'].str.contains('EGIDO', na=False)]
        if not egido_j.empty:
            reb_def = egido_j["REB DEFENSIVO"].values[0]
            puntos = egido_j["PUNTOS +"].values[0]
            total_reb_def_local += reb_def
            total_puntos_local += puntos
            partidos_local += 1
            print(f'J{j}: REB DEF = {reb_def}, PUNTOS = {puntos}')
    except:
        pass

if partidos_local > 0:
    print(f'\nSUMA REAL de partidos locales:')
    print(f'  Total REB DEF local: {total_reb_def_local}')
    print(f'  Total PUNTOS local: {total_puntos_local}')
    print(f'  Promedio REB DEF: {total_reb_def_local / partidos_local:.2f}')
    print(f'  Promedio PUNTOS: {total_puntos_local / partidos_local:.2f}')
