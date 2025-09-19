# 🏀 Scraper FEB - Aplicación Streamlit para Boxscores

Aplicación web amigable para extraer **boxscores completos** de partidos de la Federación Española de Baloncesto usando `scrape_phase.py`.

## 🚀 Características

- **Interfaz intuitiva**: Diseñada para usuarios no expertos
- **Boxscores completos**: Extrae estadísticas detalladas de todos los jugadores
- **Selección flexible**: Elige temporada y múltiples fases
- **Procesamiento paralelo**: Utiliza múltiples threads para mayor velocidad
- **Validación automática**: Verifica dependencias y configuración
- **Progreso en tiempo real**: Muestra el estado del scraping con logs detallados
- **Descarga automática**: Genera y descarga archivos automáticamente
- **Nombres personalizados**: Archivos con formato `boxscores_TEMPORADA_FASES.xlsx`

## 📋 Requisitos

### Dependencias Python

```bash
pip install streamlit selenium pandas
```

### ChromeDriver

- Instalar ChromeDriver desde [https://chromedriver.chromium.org/](https://chromedriver.chromium.org/)
- Asegurar que esté en el PATH del sistema

## 🎯 Uso

### Ejecutar la aplicación

```bash
streamlit run scraper_app.py
```

### Interfaz paso a paso

1. **Verificación del sistema**: La app verifica automáticamente que todas las dependencias estén instaladas
2. **Selección de temporada**: Elige entre temporadas disponibles (2022/2023 en adelante)
3. **Selección de fases**:
   - Opción rápida: "Fases principales" (B-A, B-B)
   - Selección manual: Múltiples fases de la lista completa
4. **Configuración**: Revisa el resumen antes de iniciar
5. **Scraping**: Progreso en tiempo real con logs detallados
6. **Descarga**: Archivo generado automáticamente disponible para descarga

## 📁 Archivos de salida

Los archivos se generan con el formato:

```
boxscores_{TEMPORADA}_{FASES}.xlsx
```

### Ejemplos:

- `boxscores_24_25_B-A_B-B.xlsx` (Fases principales 2024/2025)
- `boxscores_23_24_A-A_A-B_B-A.xlsx` (Múltiples fases 2023/2024)
- `boxscores_22_23_E-A_E-B.xlsx` (Fases E 2022/2023)

### Contenido de los archivos:

Los boxscores incluyen estadísticas completas de cada jugador por partido:

- Información del partido (Fase, Jornada, Equipo)
- Datos del jugador (Nombre, Dorsal, Posición)
- Estadísticas de tiro (FG, 3P, FT con intentos y aciertos)
- Rebotes (Ofensivos, Defensivos, Totales)
- Asistencias, Robos, Tapones, Pérdidas
- Faltas personales y técnicas
- Minutos jugados
- Puntos totales

## ⚙️ Configuración

La aplicación usa las constantes definidas en `config.py`:

- `TEMPORADAS_DISPONIBLES`: Lista de temporadas seleccionables
- `TODAS_LAS_FASES`: Todas las fases disponibles (A-A hasta E-B)
- `FASES_PRINCIPALES`: Fases por defecto para selección rápida

## 🔧 Funciones técnicas

### Validaciones automáticas

- ✅ Selenium y ChromeDriver funcionando
- ✅ Dependencias Python instaladas
- ✅ Módulos del scraper disponibles

### Características técnicas

- **Threading**: Scraping en hilo separado para no bloquear la UI
- **Procesamiento paralelo**: Múltiples workers para extraer boxscores simultáneamente
- **Queue**: Comunicación en tiempo real entre procesos
- **Progress tracking**: Barra de progreso y logs timestamped
- **Error handling**: Manejo robusto de errores con reintentos automáticos
- **Validación de datos**: Verificación de consistencia en minutos totales

## 🐛 Solución de problemas

### Error de ChromeDriver

```
❌ Error con Selenium/ChromeDriver: ...
```

**Solución**: Instalar ChromeDriver y añadirlo al PATH

### Error de dependencias

```
❌ Dependencias faltantes: selenium
```

**Solución**: `pip install selenium pandas`

### Error de importación del scraper

```
❌ Dependencias faltantes: scraper_all_games: ...
```

**Solución**: Verificar que el módulo `scrapers.scraper_all_games` esté disponible

## 🔄 Flujo de trabajo

1. **Inicio** → Verificaciones del sistema
2. **Configuración** → Selección de temporada y fases
3. **Validación** → Revisión de parámetros
4. **Ejecución** → Scraping con progreso en tiempo real
5. **Finalización** → Descarga automática del archivo

## 💡 Consejos de uso

- **Fases principales**: Usa la opción rápida para B-A y B-B
- **Múltiples fases**: Selecciona manualmente para extracciones personalizadas
- **Progreso**: Los logs muestran el estado detallado del proceso
- **Archivos**: Se guardan en el directorio `data/` con nombres descriptivos
- **Rendimiento**: El scraping puede tardar varios minutos dependiendo del número de fases

## 📊 Datos extraídos

La aplicación extrae **boxscores completos** que incluyen:

- **Información del partido**: Fase, Jornada, IDs de equipos
- **Estadísticas de tiro**: Campo, triples y tiros libres (intentos y aciertos)
- **Rebotes**: Ofensivos, defensivos y totales por jugador
- **Jugadas**: Asistencias, robos, tapones, pérdidas de balón
- **Disciplina**: Faltas personales y técnicas
- **Tiempo**: Minutos jugados por jugador y partido
- **Puntuación**: Puntos anotados por cada jugador
- **Eficiencia**: Datos para calcular estadísticas avanzadas

### Diferencias con extracción básica:

- ✅ **Boxscores**: Estadísticas detalladas de cada jugador
- ✅ **Procesamiento paralelo**: Múltiples partidos simultáneamente
- ✅ **Validación de datos**: Verificación de consistencia
- ✅ **Reintentos**: Manejo automático de errores temporales
