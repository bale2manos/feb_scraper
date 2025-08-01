# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow

import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import io

# ─────────── CONFIGURACIÓN ────────────────────────────────────────────────
FONT            = "Montserrat, sans-serif"
COLORS          = ["#9b59b6", "#3498db", "#1abc9c", "#de9826", "#e74c3c"]
LOW_THRESH      = 0.20     # <15% of the max ⇒ etiqueta pequeña
BAR_WIDTH       = 0.55     # grosor de la barra (0–1)
CIRCLE_SIZE_PX  = 70       # diámetro del círculo en px
TEXT_SIZE_IN    = 22       # texto dentro de la barra
TEXT_SIZE_OUT   = 22       # texto en las bolas pequeñas
PAD_UNITS       = 0.05     # 3% del max_val como padding lateral extra
TEXT_INSET      = 0.2      # fracción del radio para inset de texto en la bola

def _circle_radius_units(fig_w: int, max_val: float) -> float:
    """Radio en unidades del eje X."""
    return (CIRCLE_SIZE_PX / 2) * max_val / fig_w

def plot_media_pct(stats: dict,
                   out_png: str = None,
                   width_px: int = 2000,
                   resize_px: int = 2000) -> Image.Image:
    # ── preparar datos ─────────────────────────────────────────────────────
    labels = list(stats.keys())
    pct    = list(stats.values())
    max_val = max(pct)
    low_mask = [p < max_val * LOW_THRESH for p in pct]
    r_units = _circle_radius_units(width_px, max_val)

    # ── traza de barras ───────────────────────────────────────────────────
    # usamos directamente listas en lugar de DataFrame
    fig = px.bar(
        x=pct, y=labels, orientation="h",
        color=labels, color_discrete_sequence=COLORS,
        template="presentation"
    )
    fig.update_traces(width=BAR_WIDTH, marker_line_width=0)

    # ── círculos al final de cada barra ──────────────────────────────────
    fig.add_trace(go.Scatter(
        x=pct, y=labels,
        mode="markers",
        marker=dict(
            symbol="circle",
            size=CIRCLE_SIZE_PX,
            color=COLORS[:len(labels)]
        ),
        hoverinfo="skip",
        showlegend=False
    ))

    # ── etiquetas grandes (dentro de barras altas) ──────────────────────
    big_x = [(v / 2 + 2 * r_units) for v, low in zip(pct, low_mask) if not low]
    big_y = [lab for lab, low in zip(labels, low_mask) if not low]
    big_text = [f"<b>{lab} – {v:.1f} %</b>" for lab, v, low in zip(labels, pct, low_mask) if not low]
    fig.add_trace(go.Scatter(
        x=big_x, y=big_y,
        mode="text",
        text=big_text,
        textfont=dict(family=FONT, size=TEXT_SIZE_IN, color="white"),
        textposition="middle center",
        showlegend=False,
        hoverinfo="skip"
    ))

    # ── etiquetas pequeñas (al lado de círculos pequeños) ───────────────
    # replicamos la misma lógica de offsets que en el original
    small_x = [9 + v * 0.15 for v, low in zip(pct, low_mask) if low]
    small_y = [lab for lab, low in zip(labels, low_mask) if low]
    small_text = [f"<b>{lab} – {v:.1f} %</b>" for lab, v, low in zip(labels, pct, low_mask) if low]
    fig.add_trace(go.Scatter(
        x=small_x, y=small_y,
        mode="text",
        text=small_text,
        textfont=dict(family=FONT, size=TEXT_SIZE_OUT, color="black"),
        textposition="middle center",
        showlegend=False,
        hoverinfo="skip"
    ))

    # ── ajustar rango X ───────────────────────────────────────────────────
    x_min = -(r_units + PAD_UNITS * max_val)
    x_max = max_val + (2 * r_units) + (PAD_UNITS * max_val)
    fig.update_layout(
        showlegend=False,
        font=dict(family=FONT),
        height=500,
        width=width_px,
        margin=dict(l=60, r=60, t=30, b=0),  # Reduced top margin from 90 to 40
        title=dict(
            text="<b>MEDIAS % LANZAMIENTOS</b>",
            x=0.5,
            y=0.95,
            font=dict(family=FONT, size=27, color="black")
        ),
        xaxis=dict(visible=False, range=[x_min, x_max]),
        yaxis=dict(visible=False, categoryorder='array', categoryarray=labels[::-1])  # Added spacing control
    )
    
    # Add spacing between bars by updating the bar traces
    fig.update_traces(marker_line_width=0)
    fig.update_yaxes(categoryorder='array', categoryarray=labels[::-1])

    # ── Generate PIL Image directly ──────────────────────────────────────
    img_bytes = fig.to_image(format="png", engine="kaleido", scale=4)
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

# ── prueba rápida ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_stats = {
        "T1 %": 100.0,
        "T2 %": 14.9,
        "T3 %": 15.1,
        "EFG %":   3.3,
        "TS %":  10.6
    }
    print("PNG generado:", plot_media_pct(sample_stats,
                                         "./player_report/media_lanzamientos.png",))
