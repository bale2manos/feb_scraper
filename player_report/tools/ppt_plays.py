# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow

import plotly.graph_objects as go
from PIL import Image
import io

# ─────────── CONFIGURACIÓN ────────────────────────────────────────────────
FONT   = "Montserrat, sans-serif"
COLS   = ["PPT1", "PPT2", "PPT3"]
COLORS = {
    "PPT1": "#9b59b6",  # azul
    "PPT2": "#3498db",  # naranja
    "PPT3": "#1abc9c",  # rojo
}

def plot_ppt_indicators(stats: dict,
                        out_png: str = None,
                        width_px: int = 800,
                        height_px: int = 150) -> Image.Image:
    """
    Dibuja tres indicadores tipo 'card' con PPT1, PPT2 y PPT3
    y retorna una PIL Image directamente.
    """
    fig = go.Figure()

    # fondo tipo "card" con gris y borde negro (con margen)
    fig.add_shape(
        type="rect",
        x0=0.05, y0=0.05, x1=0.95, y1=1,  # Margen del 5% en todos los lados
        xref="paper", yref="paper",
        fillcolor="#E8E8E8",  # Gris claro
        line=dict(color="black", width=1),  # Borde negro
        layer="below"         # ← este es el cambio clave
    )

    # tres indicadores
    for i, key in enumerate(COLS):
        val = stats.get(key, 0)
        fig.add_trace(go.Indicator(
            mode="number",
            value=val,
            number=dict(
                valueformat=".2f",
                font=dict(color=COLORS[key], size=16, family=FONT),
                # Ajusta el padding inferior del número para acercarlo al título
                # (no hay padding directo, pero puedes usar 'prefix' o 'suffix' con un salto de línea)
                suffix="<br>",  # Esto reduce el espacio entre número y título
            ),
            title=dict(
                text=key,
                font=dict(size=8, family=FONT, color="#222"),
                # Puedes intentar usar 'align' si quieres alinear diferente
            ),
            domain=dict(
                x=[0.08 + i/3 * 0.84, 0.08 + (i+1)/3 * 0.84],
                y=[0, 0.75],
            )
        ))

    # layout y exportación
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        width=width_px,
        height=height_px,
        paper_bgcolor="white",
        separators=",."  # coma decimal, punto de miles
    )

    # Generate image as bytes and convert to PIL Image
    img_bytes = fig.to_image(format="png", width=width_px, height=height_px, scale=4, engine="kaleido")
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    
    # Optionally save to file if out_png is provided
    if out_png:
        img.save(out_png)
    
    return img


if __name__ == "__main__":
    sample = {"PPT1": 0.50, "PPT2": 0.50, "PPT3": 0.95}
    img = plot_ppt_indicators(
        sample,
        out_png="./player_report/mis_ppt_cards.png",
        width_px=800,
        height_px=150
    )
    print("PIL Image generado:", type(img))
    print("Tamaño:", img.size)
