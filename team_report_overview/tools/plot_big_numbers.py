import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from utils import setup_montserrat_font

def add_big_numbers_to_axes(
    ax: plt.Axes,
    df: pd.DataFrame,
    position: tuple = (0.5, 0.5),  # (x, y) en coordenadas de fracción de ejes - centro por defecto
    fontsize_number: int = 36,      # Tamaño grande para los números
    fontsize_label: int = 14,       # Tamaño pequeño para las etiquetas
    line_spacing: float = 0.12      # Más espacio entre líneas para mejor legibilidad
):
    """
    Añade las métricas principales del equipo en números grandes al centro del canvas.
    
    Parámetros:
    - ax: ejes de matplotlib donde añadir los números
    - df: DataFrame con los datos del equipo (debe contener las columnas necesarias)
    - position: (x, y) posición central en coordenadas de fracción de ejes
    - fontsize_number: tamaño de fuente para los números grandes
    - fontsize_label: tamaño de fuente para las etiquetas pequeñas
    - line_spacing: espaciado vertical entre líneas
    """
    # Configurar fuente Montserrat
    setup_montserrat_font()
    
    # Obtener los datos del equipo (asumiendo que hay una sola fila o tomar la primera)
    if len(df) == 0:
        return
    
    team_data = df.iloc[0]  # Tomar la primera fila
    
    # Definir las métricas a mostrar con sus nombres, formateo y colores
    metrics = [
        ("PUNTOS + / PJ", team_data.get('PUNTOS +', 0) / team_data.get('PJ', 1), "{:.1f}", "#2E8B57"),  # Verde océano
        ("PUNTOS - / PJ", team_data.get('PUNTOS -', 0) / team_data.get('PJ', 1), "{:.1f}", "#DC143C"),  # Rojo carmesí
        ("TS %", team_data.get('TS %', 0), "{:.1f}%", "#4169E1"),     # Azul real
        ("EFG %", team_data.get('EFG %', 0), "{:.1f}%", "#FF6347"),   # Tomate
        ("RTL %", team_data.get('RTL %', 0), "{:.1f}%", "#9932CC"),  # Violeta oscuro
        ("TOV", team_data.get('PERDIDAS', 0) / team_data.get('PJ', 1), "{:.1f}", "#FF8C00"),  # Naranja oscuro
    ]
    
    # Calcular posición inicial (centrada verticalmente para todas las métricas)
    total_height = (len(metrics) - 1) * line_spacing
    start_y = position[1] + total_height / 2
    
    # Dibujar cada métrica con formato mejorado
    for i, (name, value, format_str, color) in enumerate(metrics):
        y_pos = start_y - i * line_spacing
        
        # Formatear el valor
        formatted_value = format_str.format(value * 100 if '%' in format_str and '%' not in format_str else value)
        
        # Añadir la etiqueta pequeña más cerca del número (solo 0.005 de separación)
        ax.text(
            position[0], y_pos + 0.005,
            name,
            transform=ax.transAxes,
            va='bottom', ha='center',
            fontsize=fontsize_label,
            weight='normal',
            color='#666666',
            fontfamily='Montserrat'
        )
        
        # Añadir el número grande más cerca de la etiqueta
        ax.text(
            position[0], y_pos - 0.005,
            formatted_value,
            transform=ax.transAxes,
            va='top', ha='center',
            fontsize=fontsize_number,
            weight='bold',
            color=color,
            fontfamily='Montserrat'
        )

def generate_big_numbers_plot(
    df: pd.DataFrame,
    figsize: tuple = (8, 10)
) -> plt.Figure:
    """
    Genera una figura standalone con las métricas principales del equipo.
    
    Parámetros:
    - df: DataFrame con datos del equipo
    - figsize: tuple (width, height) para el tamaño de la figura
    
    Devuelve:
    - fig: figura de matplotlib
    """
    # Configurar fuente Montserrat
    setup_montserrat_font()
    
    # Crear figura
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # Añadir las métricas con nuevo formato
    add_big_numbers_to_axes(ax, df, position=(0.5, 0.5), fontsize_number=42, fontsize_label=16)
    
    # Ajustar márgenes
    plt.tight_layout(pad=0.1)
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    
    return fig

if __name__ == '__main__':
    # Ejemplo de uso
    FILE = './data/teams_aggregated.xlsx'  # Ruta relativa al directorio padre
    EQUIPO = "UROS DE RIVAS"
    
    try:
        # Cargar datos
        df = pd.read_excel(FILE)
        df_filtrado = df[df['EQUIPO'] == EQUIPO]
        
        if df_filtrado.empty:
            print(f"No se encontraron datos para el equipo: {EQUIPO}")
        else:
            # Generar gráfico
            fig = generate_big_numbers_plot(df_filtrado)
            
            # Guardar
            fig.savefig('big_numbers_test.png', 
                       bbox_inches='tight',
                       pad_inches=0.2,
                       dpi=300,
                       facecolor='white',
                       edgecolor='none',
                       format='png')
            print("Gráfico de números grandes guardado como 'big_numbers_test.png'")
            
    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo de datos. {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")
