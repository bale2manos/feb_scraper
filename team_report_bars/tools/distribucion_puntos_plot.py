# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow

import plotly.graph_objects as go
from PIL import Image
import io

# ─────────── CONFIGURACIÓN ────────────────────────────────────────────────
FONT       = "Montserrat, sans-serif"
COLS_ORDER = ["T1C", "T2C", "T3C"]
COLORS     = {
    "T1C": "#9b59b6",  # azul
    "T2C": "#3498db",  # verde turquesa
    "T3C": "#1abc9c"   # rojo
}

def plot_distribucion_puntos(stats: dict,
                             out_png: str = None,
                             width_px: int = 1000,
                             height_px: int = 300,
                             resize_px: int = 300) -> Image.Image:
    # ── preparar datos ────────────────────────────────────────────────────
    # T1C vale 1, T2C vale 2, T3C vale 3
    vals = [stats.get("T1C", 0)*1, stats.get("T2C", 0)*2, stats.get("T3C", 0)*3]
    names = [f"Puntos {k}" for k in COLS_ORDER]
    total = sum(vals) if sum(vals) > 0 else 1

    # ── construir figura ──────────────────────────────────────────────────
    fig = go.Figure()
    for name, val, key in zip(names, vals, COLS_ORDER):
        percent = (val / total) * 100
        fig.add_trace(go.Bar(
            y=[""], x=[val],
            name=name,
            orientation="h",
            marker=dict(color=COLORS[key]),
            width=0.6,
            text=f"<b>{percent:.1f}%</b>",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=32, color="white", family=FONT),
            hoverinfo="none"
        ))

    # ── layout y ejes ──────────────────────────────────────────────────────
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="white",
        plot_bgcolor="white",
        title=dict(
            text="<b>DISTRIBUCIÓN DE PUNTOS</b>",
            x=0.5, xanchor="center", y=0.9,
            font=dict(family=FONT, size=28, color="#222")
        ),
        margin=dict(l=20, r=2, t=40, b=10),
        width=width_px, height=height_px,
        xaxis=dict(
            showline=True, linecolor="black", linewidth=3,
            showticklabels=False, showgrid=False, zeroline=False
        ),
        yaxis=dict(
            showline=True, linecolor="black", linewidth=3,
            showticklabels=False, showgrid=False, zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.1,  # Leyenda debajo del eje X
            xanchor="center", x=0.5,
            font=dict(size=22),
            traceorder="normal"
        )
    )

    # ── Generate PIL Image directly ──────────────────────────────────────
    img_bytes = fig.to_image(format="png", width=width_px, height=height_px, engine="kaleido", scale=4)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    
    # Optionally save to file if out_png is provided
    if out_png:
        img.save(out_png)
    
    # Scale the image to 300 height, maintaining aspect ratio
    resize_px = resize_px
    height_ratio = resize_px / img.height
    width_px = int(img.width * height_ratio)
    img = img.resize((width_px, resize_px), Image.LANCZOS)
    
    return img


if __name__ == "__main__":
    sample = {
        "T1C": 3,
        "T2C": 20,
        "T3C": 36
    }
    # Ejemplo de llamado: muy ancho y bajo, igual que tu mockup
    print("PNG generado:",
          plot_distribucion_puntos(sample,
                                  out_png="distribucion_puntos.png",
                                  width_px=1000,
                                  height_px=300))
