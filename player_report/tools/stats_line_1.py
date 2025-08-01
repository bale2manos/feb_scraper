# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow
import plotly.graph_objects as go
from PIL import Image
import io

def plot_stats_table_plotly(stats: dict,
                            out_png: str   = "player_stats.png",
                            width_px: int  = 800,
                            height_px: int = 150) -> str:
    """
    Genera un PNG con una tabla de 2 filas (cabecera + datos) usando Plotly:
      • Montserrat
      • Cabecera en gris claro
      • Única línea horizontal oscura entre filas
      • Sin líneas verticales
      • Salida nítida a `width_px`×`height_px` píxeles
    """
    # 1) Datos en el orden fijo
    columns = ["PJ", "Avg. MIN", "PPP", "USG %"]
    row = [stats.get(col, "") for col in columns]
    
    # 2) Crear tabla con configuración específica para eliminar bordes no deseados
    fig = go.Figure(data=[go.Table(
        # Configuración de cabecera
        header=dict(
            values=columns,
            fill_color='#E0E0E0',
            font=dict(
                family="Montserrat",
                size=18,  # Aumentado de 14 a 18
                color='black'
            ),
            align="center",
            height=50,
            line=dict(color='rgba(0,0,0,0)', width=0)  # Sin bordes en header
        ),
        # Configuración de celdas de datos
        cells=dict(
            values=[[row[i]] for i in range(len(row))],  # Transponer correctamente
            fill_color='white',
            font=dict(
                family="Montserrat", 
                size=18,  # Aumentado de 14 a 18
                color='black'
            ),
            align="center",
            height=50,
            line=dict(color='rgba(0,0,0,0)', width=0)  # Sin bordes en celdas
        )
    )])
    
    # 3) Añadir línea horizontal manualmente
    fig.add_shape(
        type="line",
        x0=0, y0=0.5, x1=1, y1=0.5,  # Línea horizontal en el medio
        xref="paper", yref="paper",
        line=dict(color="#666666", width=1)
    )
    
    # 4) Configurar layout sin márgenes ni ejes
    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False
    )
    
    # 5) Guardar como PNG
    fig.write_image(out_png, width=width_px, height=height_px, scale=1)
    
    return out_png

# Alternativa más simple usando solo shapes y annotations
def plot_stats_table_simple(stats: dict,
                           out_png: str   = None, 
                           width_px: int  = 800,
                           height_px: int = 80) -> Image.Image:
    """
    Versión más simple usando shapes y text annotations.
    Returns PIL Image directly instead of saving to file.
    """
    columns = ["PJ", "Avg. MIN", "PPP", "USG %"]
    row = [stats.get(col, "") for col in columns]
    
    fig = go.Figure()
    
    # Fondo gris para la cabecera (50% superior)
    fig.add_shape(
        type="rect",
        x0=0, y0=0.5, x1=1, y1=1,  # 50% superior para header
        xref="paper", yref="paper",
        fillcolor="#E0E0E0",
        line=dict(color="rgba(0,0,0,0)", width=0)
    )
    
    # Línea separadora entre filas (en el medio)
    fig.add_shape(
        type="line",
        x0=0, y0=0.5, x1=1, y1=0.5,  # Línea en el medio
        xref="paper", yref="paper",
        line=dict(color="#A9A9A9", width=1)
    )

    
    # Línea inferior de la tabla
    fig.add_shape(
        type="line",
        x0=0, y0=0, x1=1, y1=0,
        xref="paper", yref="paper",
        line=dict(color="#A9A9A9", width=1)
    )
    
    # Añadir texto de cabecera
    for i, col in enumerate(columns):
        fig.add_annotation(
            text=f"<b>{col}</b>",
            x=(i + 0.5) / len(columns),
            y=0.75,  # Centrado en la fila gris (0.5 a 1.0, centro = 0.75)
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(family="Montserrat", size=8, color="black"),
            xanchor="center",  # Forzar centrado horizontal
            yanchor="middle"   # Forzar centrado vertical
        )
    
    # Añadir texto de datos
    for i, val in enumerate(row):
        fig.add_annotation(
            text=str(val),
            x=(i + 0.5) / len(columns),
            y=0.25,  # Centrado en la fila blanca (0.0 a 0.5, centro = 0.25)
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(family="Montserrat", size=8, color="black"),
            xanchor="center",  # Forzar centrado horizontal
            yanchor="middle"   # Forzar centrado vertical
        )
    
    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=0, r=0, t=2, b=2),  # Márgenes mínimos: solo 2px arriba y abajo
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False
    )
    
    # Generate image as bytes and convert to PIL Image
    img_bytes = fig.to_image(format="png", width=width_px, height=height_px, scale=4)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    
    # Optionally save to file if out_png is provided
    if out_png:
        img.save(out_png)
    
    return img

# ───────── Ejemplo de uso ─────────
if __name__ == "__main__":
    sample_stats = {
        "PJ":       "6",
        "Avg. MIN": "28,11",
        "PPP":      "0,61",
        "USG %":    "24,00%"
    }
    
    # Usar la versión simple (más control)
    img = plot_stats_table_simple(
        sample_stats,
        out_png     = "player_stats_plotly.png",
        width_px    = 700,
        height_px   = 80  # Mucho más compacto
    )
    print("PIL Image generado:", type(img))
    print("Tamaño:", img.size)