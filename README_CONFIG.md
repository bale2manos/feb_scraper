# Sistema de Configuración Centralizada

## 📋 Descripción

Este proyecto ahora incluye un sistema de configuración centralizada que permite gestionar todas las constantes (temporadas, fases, rutas de archivos, configuración de scraping, etc.) desde un único archivo: `config.py`.

## 🎯 Beneficios

- ✅ **Gestión centralizada**: Todas las constantes en un solo lugar
- ✅ **Fácil mantenimiento**: Cambiar temporada/fase desde un solo archivo
- ✅ **Consistencia**: Mismas rutas y configuración en todo el proyecto
- ✅ **Validación**: Verificación automática de configuración
- ✅ **Utilidades**: Funciones helper para casos comunes

## 📁 Estructura de Archivos

```
feb_scraper/
├── config.py                 # 🔧 Configuración centralizada
├── ejemplo_config.py         # 📖 Ejemplos de uso
├── migrar_config.py          # 🔄 Script de migración automática
├── utils/web_scraping.py     # ✅ Actualizado para usar config
├── scrapers/scrape_phase.py  # ✅ Actualizado para usar config
├── player_report/            # ✅ Actualizados para usar config
└── ...
```

## 🚀 Uso Básico

### Importar configuración

```python
# Opción 1: Importar todo
from config import *

# Opción 2: Importar selectivo
from config import (
    TEMPORADA_TXT,
    JUGADORES_AGGREGATED_FILE,
    FASES_PRINCIPALES,
    MAX_WORKERS
)
```

### Ejemplos comunes

```python
# Cargar datos de jugadores
import pandas as pd
from config import JUGADORES_AGGREGATED_FILE

df = pd.read_excel(JUGADORES_AGGREGATED_FILE)

# Configurar scraper
from config import BASE_URL, TEMPORADA_TXT, MAX_WORKERS

scraper_config = {
    'url': BASE_URL,
    'temporada': TEMPORADA_TXT,
    'workers': MAX_WORKERS
}

# Crear rutas dinámicas
from config import get_season_file

archivo_anterior = get_season_file("jugadores_aggregated", "23_24")
```

## ⚙️ Configuración Principal

### Temporadas y Competición

```python
TEMPORADA_TXT = "2024/2025"          # Temporada actual
TEMPORADA_CORTA = "24_25"            # Para nombres de archivos
FASES_PRINCIPALES = [                # Fases de competición
    'Liga Regular "C-A"',
    'Liga Regular "B-A"',
    'Liga Regular "B-B"'
]
```

### Rutas de Archivos

```python
# Archivos principales
JUGADORES_AGGREGATED_FILE = "./data/jugadores_aggregated_24_25.xlsx"
TEAMS_AGGREGATED_FILE = "./data/teams_aggregated.xlsx"
CLUTCH_AGGREGATED_FILE = "./data/clutch_aggregated.xlsx"

# Directorios
REPORTS_DIR = "./output/reports"
CLUBS_DIR = "./images/clubs"
FONTS_DIR = "./fonts"
```

### Web Scraping

```python
BASE_URL = "https://baloncestoenvivo.feb.es/resultados/tercerafeb/3/2024"
MAX_WORKERS = 4                      # Threads paralelos
WEBDRIVER_TIMEOUT = 15               # Timeout en segundos
```

### Visualizaciones

```python
COLORS_PRIMARY = ["#e74c3c", "#de9826", "#1abc9c", "#3498db", "#9b59b6"]
FONT_FAMILY = "Montserrat, sans-serif"
TEXT_SIZE_LARGE = 22
LOW_THRESH = 0.36                    # Umbral para valores "bajos"
```

## 🔄 Migración Automática

Para actualizar automáticamente archivos existentes:

```bash
# Solo analizar (no hacer cambios)
python migrar_config.py --dry-run

# Aplicar cambios automáticamente
python migrar_config.py

# Generar reporte personalizado
python migrar_config.py --output mi_reporte.txt
```

El script de migración:

- 🔍 Busca constantes hardcodeadas
- 🔄 Las reemplaza por referencias a config.py
- 💾 Crea backups automáticamente
- 📋 Genera reporte detallado

## 📖 Ejemplos Prácticos

### Cambiar Temporada

```python
# En config.py, simplemente cambiar:
TEMPORADA_TXT = "2025/2026"
TEMPORADA_CORTA = "25_26"

# Todos los archivos automáticamente usarán la nueva temporada
```

### Agregar Nueva Fase

```python
# En config.py:
FASES_PRINCIPALES = [
    'Liga Regular "C-A"',
    'Liga Regular "B-A"',
    'Liga Regular "B-B"',
    'Playoffs',              # Nueva fase
    'Copa del Rey'           # Nueva fase
]
```

### Configurar Nuevo Scraper

```python
from config import (
    BASE_URL, TEMPORADA_TXT, FASES_PRINCIPALES,
    MAX_WORKERS, SELECT_ID_TEMPORADA, SELECT_ID_FASE
)

def nuevo_scraper():
    for fase in FASES_PRINCIPALES:
        # Usar configuración centralizada
        scraper = WebScraper(
            url=BASE_URL,
            temporada=TEMPORADA_TXT,
            fase=fase,
            workers=MAX_WORKERS
        )
        scraper.run()
```

## 🛠️ Funciones Útiles

### Gestión de Directorios

```python
from config import ensure_directories

# Crear todos los directorios necesarios
ensure_directories()
```

### Archivos por Temporada

```python
from config import get_season_file

# Generar nombre de archivo con temporada
archivo_actual = get_season_file("jugadores_aggregated")
archivo_anterior = get_season_file("jugadores_aggregated", "23_24")
```

### Filtros de Fase

```python
from config import get_phase_filter

# Usar fase por defecto
fases = get_phase_filter()

# Usar fase específica
fases = get_phase_filter("Liga Regular \"B-A\"")
```

### Validación

```python
from config import validate_config

try:
    validate_config()
    print("✅ Configuración válida")
except ValueError as e:
    print(f"❌ Error: {e}")
```

## 📊 Testing

Para probar la configuración:

```bash
python ejemplo_config.py
```

Este script:

- ✅ Valida toda la configuración
- 📁 Crea directorios necesarios
- 📊 Muestra ejemplos de uso
- 🔗 Prueba carga de datos

## 🔧 Personalización

### Agregar Nueva Constante

1. Agregar en `config.py`:

```python
MI_NUEVA_CONSTANTE = "valor"
```

2. Usar en código:

```python
from config import MI_NUEVA_CONSTANTE
```

### Agregar Nueva Ruta

1. En `config.py`:

```python
MI_DIRECTORIO = Path("./mi_directorio")
```

2. En `ensure_directories()`:

```python
directories = [
    # ... directorios existentes
    MI_DIRECTORIO
]
```

## 📋 Lista de Archivos Actualizados

### ✅ Completamente Migrados

- `utils/web_scraping.py`
- `scrapers/scrape_phase.py`
- `player_report/player_report_gen.py`
- `player_report/tools/media_lanzamientos_clutch.py`

### 🔄 Pendientes de Migración

Usar `migrar_config.py` para migrar automáticamente:

- `scrapers/scraper_all_games.py`
- `utils/aggregate_players_games.py`
- `utils/aggregate_teams.py`
- `team_report_overview/tools/`
- `phase_report/tools/`

## 🚨 Notas Importantes

1. **Backups**: La migración automática crea backups (.backup)
2. **Imports**: Revisar imports después de migración automática
3. **Paths**: Usar `str()` al convertir Path objects a strings
4. **Validación**: Ejecutar `validate_config()` tras cambios

## 🐛 Troubleshooting

### Error: "No module named 'config'"

```python
# Asegurar que config.py está en el directorio raíz del proyecto
# O agregar al PYTHONPATH
import sys
sys.path.append('.')
from config import *
```

### Error: "Path object has no attribute..."

```python
# Convertir Path a string cuando sea necesario
from config import JUGADORES_AGGREGATED_FILE
df = pd.read_excel(str(JUGADORES_AGGREGATED_FILE))
```

### Constante no encontrada

```python
# Verificar que está definida en config.py
# Y que está en el import
from config import MI_CONSTANTE  # ← Verificar nombre exacto
```

## 📞 Soporte

- 📖 Ver `ejemplo_config.py` para casos de uso
- 🔄 Usar `migrar_config.py --dry-run` para analizar archivos
- 📋 Revisar reportes de migración para detalles
- ✅ Ejecutar `validate_config()` para verificar configuración
