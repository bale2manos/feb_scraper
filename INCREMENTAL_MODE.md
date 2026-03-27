# 🔄 Modo Incremental - Agregación de Datos

## Descripción

El scraper ahora opera en **modo incremental**, lo que significa que cuando scrapeas datos que van al mismo directorio (misma temporada, liga y jornadas), los nuevos datos se **agregan** a los archivos existentes en lugar de sobrescribirlos.

## ✅ Ventajas

### Para Tercera y Segunda FEB

Estas ligas tienen **múltiples grupos** (por ejemplo, Tercera FEB tiene grupos B-A, B-B, D-B, E-B, etc.). Con el modo incremental:

1. **Scrapea el Grupo B-A** → Los datos se guardan en `data/3FEB_24_25/`
2. **Scrapea el Grupo B-B** → Los datos se **agregan** al mismo directorio
3. **Resultado**: Un único conjunto de archivos con **todos los grupos combinados**

### Eliminación Automática de Duplicados

El sistema detecta y elimina automáticamente registros duplicados basándose en claves únicas:

- **Boxscores**: `IdPartido` + `IdJugador`
- **Asistencias**: `IdPartido` + `IdAsistente` + `IdAnotador`
- **Clutch Data**: `IdPartido` + `IdJugador`
- **Clutch Lineups**: `IdPartido` + jugadores del quinteto
- **Jugadores agregados**: `IdJugador`
- **Equipos agregados**: `IdEquipo`
- **Partidos agregados**: `IdPartido`
- **Clutch agregado**: `IdEquipo` + `IdJugador`

## 📁 Estructura de Directorios

```
data/
├── 3FEB_24_25/                    # Tercera FEB, temporada 24/25, todas las jornadas
│   ├── boxscores_24_25_3FEB.xlsx  # Datos de TODOS los grupos
│   ├── assists_24_25_3FEB.xlsx
│   ├── clutch_data_24_25_3FEB.xlsx
│   ├── clutch_lineups_24_25_3FEB.xlsx
│   ├── players_24_25_3FEB.xlsx
│   └── teams_24_25_3FEB.xlsx
│
├── 3FEB_24_25_j1_2_3/             # Tercera FEB, solo jornadas 1, 2 y 3
│   └── ...
│
└── 2FEB_24_25/                    # Segunda FEB, temporada 24/25
    └── ...
```

## 🔄 Workflow de Ejemplo

### Ejemplo 1: Scrapear Todos los Grupos de Tercera FEB

```
1. Selecciona: Tercera FEB → 2024/2025 → Fase "B-A"
   → Se generan archivos en data/3FEB_24_25/

2. Selecciona: Tercera FEB → 2024/2025 → Fase "B-B"
   → Los datos se AGREGAN a data/3FEB_24_25/ (mismo directorio)

3. Selecciona: Tercera FEB → 2024/2025 → Fase "D-B"
   → Los datos se AGREGAN a data/3FEB_24_25/ (mismo directorio)

Resultado: Archivos en data/3FEB_24_25/ contienen datos de B-A + B-B + D-B
```

### Ejemplo 2: Scrapear Jornadas Específicas

```
1. Selecciona: Tercera FEB → 2024/2025 → Jornadas [1, 2, 3] → Fase "B-A"
   → Se generan archivos en data/3FEB_24_25_j1_2_3/

2. Selecciona: Tercera FEB → 2024/2025 → Jornadas [1, 2, 3] → Fase "B-B"
   → Los datos se AGREGAN a data/3FEB_24_25_j1_2_3/ (mismo directorio)

Resultado: Archivos contienen jornadas 1, 2, 3 de B-A + B-B
```

## ⚠️ Consideraciones Importantes

### 1. Prioridad de Datos Nuevos

Cuando hay duplicados, **los datos nuevos tienen prioridad** sobre los existentes. Esto asegura que si vuelves a scrapear un partido, los datos más recientes sobrescriban los antiguos.

### 2. Diferentes Jornadas = Diferentes Directorios

Si scrapeas:

- Todas las jornadas → `data/3FEB_24_25/`
- Jornadas 1-3 → `data/3FEB_24_25_j1_2_3/`
- Jornadas 4-6 → `data/3FEB_24_25_j4_5_6/`

Estos son directorios **diferentes** y los datos **NO se combinarán** entre ellos.

### 3. Diferentes Ligas = Diferentes Directorios

- Tercera FEB → `data/3FEB_24_25/`
- Segunda FEB → `data/2FEB_24_25/`
- Primera FEB → `data/1FEB_24_25/`

Cada liga mantiene sus datos por separado.

## 🛠️ Implementación Técnica

### Archivos Modificados

1. **`utils/unified_scraper_integrated.py`**

   - Carga archivos existentes antes de guardar
   - Combina DataFrames (existentes + nuevos)
   - Elimina duplicados basados en claves primarias

2. **`utils/aggregate_players_integrated.py`**

   - Función `save_aggregated_players()` con lógica incremental

3. **`utils/aggregate_teams_integrated.py`**

   - Función `save_aggregated_teams()` con lógica incremental

4. **`utils/aggregate_players_clutch.py`**
   - Función `aggregate_clutch_from_file()` con lógica incremental

### Lógica de Combinación

```python
# Pseudocódigo
if archivo_existe:
    datos_existentes = cargar_excel(archivo)
    datos_combinados = concat(datos_existentes, datos_nuevos)
    datos_finales = eliminar_duplicados(datos_combinados, keep='last')
else:
    datos_finales = datos_nuevos

guardar_excel(datos_finales)
```

## 📝 Mensajes en la Interfaz

Cuando el modo incremental está activo, verás mensajes como:

```
📥 Cargando datos existentes: 150 registros
🔄 Combinando datos: 150 existentes + 80 nuevos = 200 finales (sin duplicados)
✅ Boxscores: 200 registros guardados
```

Esto confirma que los datos se están combinando correctamente.

## 🚀 Beneficios

1. **Eficiencia**: No necesitas re-scrapear todo si solo quieres agregar un grupo
2. **Organización**: Todos los datos de una liga/temporada en un único conjunto de archivos
3. **Flexibilidad**: Puedes scrapear grupos en diferentes momentos
4. **Seguridad**: Los duplicados se eliminan automáticamente
5. **Actualización**: Re-scrapear un partido actualiza sus datos (keep='last')

## ❓ FAQ

**P: ¿Qué pasa si quiero empezar desde cero?**  
R: Simplemente borra el directorio `data/LIGA_TEMPORADA/` antes de scrapear.

**P: ¿Puedo combinar datos de diferentes temporadas?**  
R: No, cada temporada tiene su propio directorio independiente.

**P: ¿Cómo sé si los datos se están agregando correctamente?**  
R: La interfaz muestra mensajes detallados durante el proceso de combinación.

**P: ¿Qué pasa si scrapeo el mismo grupo dos veces?**  
R: Los datos nuevos sobrescribirán los antiguos (porque los duplicados se eliminan con `keep='last'`).

**P: ¿Puedo desactivar el modo incremental?**  
R: Actualmente no, pero puedes lograr el mismo efecto borrando los archivos existentes antes de scrapear.
