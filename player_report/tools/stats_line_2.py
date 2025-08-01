# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow

import plotly.graph_objects as go
from PIL import Image
import io

def plot_generic_stats_table(stats: dict,
                             out_png: str   = None,
                             width_px: int  = 800,
                             height_px: int = 100,
                             font_size: int = 30) -> Image.Image:
    """
    Dibuja un PNG con una tabla de 2 filas:
      • Cabecera (gris claro)  • Datos (blanco)
      • Solo una línea horizontal oscura entre ambas filas
      • Sin líneas verticales
      • Texto Montserrat centrado
      • Ancho x Alto = width_px x height_px
    stats : dict
        Clave=etiqueta columna, Valor=texto de la celda (string).
    """
    cols  = list(stats.keys())
    vals  = list(stats.values())
    ncol  = len(cols)
    
    fig = go.Figure()
    
    # 1) Fondo cabecera (50–100% en Y)
    fig.add_shape(
        type="rect",
        x0=0, y0=0.5, x1=1, y1=1,
        xref="paper", yref="paper",
        fillcolor="#E0E0E0",
        line=dict(color="rgba(0,0,0,0)", width=0)
    )
    
    # 2) Línea separadora (en y=0.5)
    fig.add_shape(
        type="line",
        x0=0, y0=0.5, x1=1, y1=0.5,
        xref="paper", yref="paper",
        line=dict(color="#A9A9A9", width=5)  # Increased width from 1 to 3
    )
    
    # Línea inferior de la tabla
    fig.add_shape(
        type="line",
        x0=0, y0=0, x1=1, y1=0,
        xref="paper", yref="paper",
        line=dict(color="#A9A9A9", width=5)  # Increased width from 1 to 3
    )
    
    # 4) Anotaciones de cabecera y datos
    for i, col in enumerate(cols):
        if i== 0:
            x_center = (i + 0.6) / ncol
        elif i == 1:
            x_center = (i + 0.5) / ncol
        elif i == 8:
            x_center = (i + 0.2) / ncol
        elif i == 9:
            x_center = (i + 0.35) / ncol
        else:
            x_center = (i + 0.4) / ncol

        # header
        fig.add_annotation(
            text=f"<b>{col}</b>",
            x=x_center, y=0.75,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(family="Montserrat", size=font_size, color="black"),
            xanchor="center", yanchor="middle"
        )
        # dato
        fig.add_annotation(
            text=str(vals[i]),
            x=x_center, y=0.25,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(family="Montserrat", size=font_size, color="black"),
            xanchor="center", yanchor="middle"
        )
    
    # 5) Layout final
    fig.update_layout(
        width= width_px,
        height= height_px,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False
    )
    
    # 6) Exportar PNG
    # Generate image as bytes and convert to PIL Image
    img_bytes = fig.to_image(format="png", width=width_px, height=height_px, scale=1)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    
    # Optionally save to file if out_png is provided
    if out_png:
        img.save(out_png)
    
    return img


if __name__ == "__main__":
    # ejemplo con tus 10 columnas (los valores dan igual)
    stats = {
        "Puntos":   "11,83",
        "RT":       "4,33",
        "RD":       "21,00%",
        "RO":       "3,50",
        "AST":      "0,50",
        "PP":       "3,33",
        "TO %":     "7,17",
        "TCC":      "10,50%",
        "TCI":      "31,10%",
        "P. Anot. %":"--"   # si falta, puedes dejar cualquier placeholder
    }
    img = plot_generic_stats_table(
        stats,
        out_png   = "tabla_stats_generica.png",
        width_px  = 1000,
        height_px = 100,
        font_size = 16
    )
    print("PIL Image generado:", type(img))
    print("Tamaño:", img.size)
