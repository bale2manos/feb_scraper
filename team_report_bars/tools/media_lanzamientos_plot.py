# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow

import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont

# ─────────── CONFIGURACIÓN ────────────────────────────────────────────────
FONT_PATH = "fonts/Montserrat-Bold.ttf"
COLORS = ["#9b59b6", "#3498db", "#1abc9c"]
CIRCLE_SIZE_PX = 44
BAR_HEIGHT = 44
BAR_PAD = 10
TEXT_SIZE = 24
LABEL_PAD = 20

def plot_media_pct(stats: dict, out_png: str = None, width_px: int = 2800, height_px: int = 1000
                   ) -> Image.Image:
    labels = list(stats.keys())
    pct = list(stats.values())
    n_bars = len(labels)
    bar_area_height = BAR_HEIGHT * n_bars + BAR_PAD * (n_bars - 1)
    top_margin = (height_px - bar_area_height) // 2

    # Crear imagen base
    img = Image.new("RGBA", (width_px, height_px), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, TEXT_SIZE)
    except Exception:
        font = ImageFont.load_default()

    for i, (label, value) in enumerate(zip(labels, pct)):
        print(f"[DEBUG] Dibujando barra {i}: {label} = {value}")
        if value < 20:
            color_string = "black"
        else:
            color_string = "white"
        print(f"[DEBUG] color_string para valor {value}: {color_string}")
        y = top_margin + i * (BAR_HEIGHT + BAR_PAD)
        # Barra horizontal
        bar_w = int((width_px - 2 * LABEL_PAD) * value / 100)
        bar_x = LABEL_PAD
        bar_y = y
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + BAR_HEIGHT], fill=COLORS[i % len(COLORS)])
        # Texto dentro de la barra
        text = f"{label} – {value:.2f} %"  
        try:
            text_w, text_h = font.getsize(text)
            ascent, descent = font.getmetrics()
        except AttributeError:
            # PIL >= 10.0.0
            bbox = font.getbbox(text)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ascent, descent = bbox[3], 0
        text_x = bar_x + (bar_w - text_w) // 2 if bar_w > text_w else bar_x + 10
        # Centrado vertical real usando ascent y descent
        text_y = bar_y + (BAR_HEIGHT - (ascent + descent)) // 2
        draw.text((text_x, text_y), text, font=font, fill=color_string)
    
    
    # Add title
    # Calcula la posición Y de la primera barra
    first_bar_y = top_margin
    # Increase title text size
    TITLE_TEXT_SIZE = TEXT_SIZE + 10
    try:
        title_font = ImageFont.truetype(FONT_PATH, TITLE_TEXT_SIZE)
    except Exception:
        title_font = ImageFont.load_default()
    title_y = first_bar_y - TITLE_TEXT_SIZE - 20  # 4px de separación opcional
    if title_y < LABEL_PAD:
        title_y = LABEL_PAD
    draw.text((LABEL_PAD + 1250, title_y), "MEDIAS % LANZAMIENTOS", font=title_font, fill="black")

    if out_png:
        img.save(out_png)
    return img

# ── prueba rápida ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_stats = {
        "T1 %": 60.0,
        "T2 %": 100,
        "T3 %": 45.1,
    }
    print("PNG generado:", plot_media_pct(sample_stats,
                                         "./media_lanzamientos.png", width_px=2800, height_px=1000))
