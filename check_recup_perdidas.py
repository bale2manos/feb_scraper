import pandas as pd

# Jornada 2 (único partido local de CB ARIDANE)
df_j2 = pd.read_excel('f:/PyCharm/feb_scraper/data/3FEB_25_26_j2/teams_25_26_3FEB.xlsx')
aridane_j2 = df_j2[df_j2['EQUIPO'].str.contains('ARIDANE', na=False)]

print('=== JORNADA 2 (único partido local de CB ARIDANE) ===')
if 'RECUPEROS' in aridane_j2.columns:
    print(f'RECUPEROS en J2: {aridane_j2["RECUPEROS"].values[0]}')
if 'PERDIDAS' in aridane_j2.columns:
    print(f'PERDIDAS en J2: {aridane_j2["PERDIDAS"].values[0]}')

# Archivo consolidado
df = pd.read_excel('f:/PyCharm/feb_scraper/data/3FEB_25_26/teams_25_26_3FEB.xlsx')
aridane = df[df['EQUIPO'].str.contains('ARIDANE', na=False)]

print('\n=== ARCHIVO CONSOLIDADO ===')
print(f'RECUPEROS total (promedio de 7 partidos): {aridane["RECUPEROS"].values[0]:.2f}')
print(f'PERDIDAS total (promedio de 7 partidos): {aridane["PERDIDAS"].values[0]:.2f}')
if 'LOCAL_RECUPEROS' in aridane.columns:
    print(f'LOCAL_RECUPEROS: {aridane["LOCAL_RECUPEROS"].values[0]}')
if 'LOCAL_PERDIDAS' in aridane.columns:
    print(f'LOCAL_PERDIDAS: {aridane["LOCAL_PERDIDAS"].values[0]}')
