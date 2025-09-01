# -*- coding: utf-8 -*-
# pip install plotly kaleido pandas pillow

import plotly.graph_objects as go
import pandas as pd
from PIL import Image
import io

# ─────────── CONFIGURACIÓN ────────────────────────────────────────────────
FONT       = "Montserrat, sans-serif"
COLS_ORDER = ["T1 %", "T2 %", "T3 %", "PP %"]
COLORS     = {
    "T1 %": "#9b59b6",
    "T2 %": "#3498db",
    "T3 %": "#1abc9c",
    "PP %": "#D0234E"
}

TEXT_COLORS = {
    "T1 %": "white",
    "T2 %": "white",
    "T3 %": "white",
    "PP %": "white"
}

def plot_finalizacion_plays(stats: dict,
                            out_png: str = None,
                            width_px: int = 1000,
                            height_px: int = 300,
                            resize_px: int = 300) -> Image.Image:
    # ── preparar datos ────────────────────────────────────────────────────
    vals  = [stats.get(k, 0) for k in COLS_ORDER]
    names = ["TOV" if k == "PP %" else k for k in COLS_ORDER]

    # ── construir figura ──────────────────────────────────────────────────
    fig = go.Figure()
    for name, val, key in zip(names, vals, COLS_ORDER):
        txt = f"<b>{val:.2f} %</b>" if val >= 6 else ""
        # Change text_size based on value, if less than 10
        if val >= 50:
            text_size = 36
        elif val >= 30:
            text_size = 30
        elif val >= 10:
            text_size = 24
        else:
            text_size = 18
        
        fig.add_trace(go.Bar(
            y=[""], x=[val],
            name=name,
            orientation="h",
            marker=dict(color=COLORS[key]),
            width=0.6,  # Barra mucho más gruesa
            text=txt,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=text_size, color=TEXT_COLORS[key], family=FONT),
            hoverinfo="none"
        ))

    # ── layout y ejes ──────────────────────────────────────────────────────
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="white",
        plot_bgcolor="white",
        title=dict(
            text="<b>FINALIZACIÓN PLAYS</b><br>"
                 "<span style='font-size:22px;'>(T1 – T2 – T3 – TOV)</span>",
            x=0.5, xanchor="center", y=0.9,
            font=dict(family=FONT, size=28, color="#222")
        ),
        margin=dict(l=20, r=2, t=40, b=10),
        width=width_px,
        height=height_px,
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
            yanchor="top", y=-0.01,  # Leyenda debajo del eje X
            xanchor="center", x=0.5,
            font=dict(size=22),
            traceorder="normal"
        )
    )

    # ── Generate PIL Image directly ──────────────────────────────────────
    img_bytes = fig.to_image(format="png", width=width_px, height=height_px, scale=4, engine="kaleido")
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
        "T1 %": 7.50,
        "T2 %": 3.00,
        "T3 %": 59.00,
        "PP %": 30.00
    }
    # Ejemplo: muy ancho y poco alto
    print("PNG generado:",
          plot_finalizacion_plays(sample,
                                  width_px=1000,
                                  height_px=300))
