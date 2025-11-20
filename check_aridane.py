import pandas as pd

df = pd.read_excel('f:/PyCharm/feb_scraper/data/3FEB_25_26/teams_25_26_3FEB.xlsx')
aridane = df[df['EQUIPO'].str.contains('ARIDANE', na=False)]

print('CB ARIDANE - Valores LOCAL en consolidado:')
print(f'LOCAL_REB OFFENSIVO: {aridane["LOCAL_REB OFFENSIVO"].values[0]}')
print(f'LOCAL_REB DEFENSIVO: {aridane["LOCAL_REB DEFENSIVO"].values[0]}')
print(f'LOCAL_%OREB: {aridane["LOCAL_%OREB"].values[0]:.6f}')
print(f'LOCAL_%DREB: {aridane["LOCAL_%DREB"].values[0]:.6f}')
print(f'LOCAL_%REB: {aridane["LOCAL_%REB"].values[0]:.6f}')

print('\nValores esperados de J2 (único partido local):')
print('REB OFFENSIVO: 10')
print('REB DEFENSIVO: 24')
print('%OREB: 0.294118')
print('%DREB: 0.774194')
print('%REB: 0.523077')

print('\nVerificando cálculo manual:')
print(f'%OREB calculado = 10 / (10 + ?) [necesitamos REB DEF rival]')
print(f'Si LOCAL_%OREB = {aridane["LOCAL_%OREB"].values[0]:.6f}')
print(f'Entonces: 10 / (10 + X) = {aridane["LOCAL_%OREB"].values[0]:.6f}')
