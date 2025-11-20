import pandas as pd

df = pd.read_excel('f:/PyCharm/feb_scraper/data/3FEB_25_26/teams_25_26_3FEB.xlsx')
aridane = df[df['EQUIPO'].str.contains('ARIDANE', na=False)]

print('CB ARIDANE - Comparación de valores:')
print(f'PJ total: {aridane["PJ"].values[0]}')
print(f'PJ_LOCAL: {aridane["PJ_LOCAL"].values[0]}')
print(f'PJ_VISITANTE: {aridane["PJ_VISITANTE"].values[0]}')

print('\n=== TIROS DE 2 ===')
print(f'T2 CONVERTIDO total: {aridane["T2 CONVERTIDO"].values[0]}')
print(f'T2 INTENTADO total: {aridane["T2 INTENTADO"].values[0]}')

col_names = [col for col in aridane.columns if 'T2' in col and 'LOCAL' in col]
print(f'\nColumnas LOCAL con T2: {col_names[:5]}')

if 'LOCAL_T2 CONVERTIDO' in aridane.columns:
    print(f'LOCAL_T2 CONVERTIDO: {aridane["LOCAL_T2 CONVERTIDO"].values[0]}')
    print(f'LOCAL_T2 INTENTADO: {aridane["LOCAL_T2 INTENTADO"].values[0]}')

print('\n=== REBOTES ===')
print(f'REB OFFENSIVO total: {aridane["REB OFFENSIVO"].values[0]}')
print(f'LOCAL_REB OFFENSIVO: {aridane["LOCAL_REB OFFENSIVO"].values[0] if "LOCAL_REB OFFENSIVO" in aridane.columns else "No existe"}')

print('\n=== PUNTOS ===')
print(f'PUNTOS + total: {aridane["PUNTOS +"].values[0]}')
if 'LOCAL_PUNTOS +' in aridane.columns:
    print(f'LOCAL_PUNTOS +: {aridane["LOCAL_PUNTOS +"].values[0]}')
