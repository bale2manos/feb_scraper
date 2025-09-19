# -*- coding: utf-8 -*-
"""
Top-3 quintetos clutch (imagen) — versión pulida
------------------------------------------------
- Lee el Excel de quintetos (salida del scraper de lineups clutch).
- Ranking por **NET_RTG ponderado por minutos**:
      NET_RTG_ADJ = NET_RTG * (MIN_CLUTCH / (MIN_CLUTCH + K_MIN))
  (K_MIN=5.0 min por defecto).
- Dibuja una lámina con 3 filas:
    • 5 fotos circulares con etiqueta “DORSAL - NombreCorto”
    • A la derecha: **NET adj (grande y azul)** y **Min clutch (pequeño)**
- Evita solapes de textos ampliando la columna de métricas y separando verticalmente.

Uso directo (ejemplo):
    python top3_clutch_lineups_card.py
        --team "BALONCESTO ALCALA"
        --lineups-xlsx ./data/clutch_lineups.xlsx
        --roster-xlsx  ./data/jugadores_aggregated_24_25.xlsx
        --out ./output/top3_clutch_BALONCESTO_ALCALA.png
"""

import os
import re
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from PIL import Image, ImageOps, ImageDraw
import requests
from io import BytesIO
from rembg import remove

# Importar configuración centralizada
from config import GENERIC_PLAYER_IMAGE, JUGADORES_AGGREGATED_FILE

# ------------------------- Config visual -------------------------
FIG_W, FIG_H = 13.0, 7.5
DPI = 200
BG_COLOR = (1, 1, 1)
TITLE_COLOR = (0.10, 0.10, 0.12)
SUBTITLE_COLOR = (0.33, 0.33, 0.36)
ACCENT_COLOR = (0.08, 0.35, 0.80)  # azul para el NET ajustado
K_MIN = 5.0                         # shrinkage de minutos

GENERIC_IMG = str(GENERIC_PLAYER_IMAGE)  # fallback

# ------------------- Utilidades de nombres ----------------------
_ACENTS = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN")

def canon_key(name: str) -> str:
    """
    Clave canónica para matchear:
      lineup: 'J. ATIENZA PEREA' -> 'J ATIENZA PEREA'
      roster: 'ATIENZA PEREA, JOSE' -> 'J ATIENZA PEREA'
    """
    s = (name or "").strip().translate(_ACENTS)
    s = re.sub(r"\s+", " ", s.replace(".", " ")).upper()

    if "," in s:
        surnames, names = [x.strip() for x in s.split(",", 1)]
        first = names.split()[0] if names else ""
        return f"{first[:1]} {surnames}".strip()

    parts = s.split()
    if not parts:
        return s
    if len(parts[0]) == 1:
        initial = parts[0]
        surnames = " ".join(parts[1:])
    else:
        initial = parts[0][:1]
        surnames = " ".join(parts[1:])
    return f"{initial} {surnames}".strip()

def short_label(original_name: str) -> str:
    s = re.sub(r"\s+", " ", (original_name or "").strip())
    parts = s.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else s

# ------------------- Carga roster (fotos y dorsales) ------------
def load_roster_lookup(roster_xlsx: str, team: str):
    if not os.path.exists(roster_xlsx):
        raise FileNotFoundError(f"No existe roster: {roster_xlsx}")
    df = pd.read_excel(roster_xlsx)

    if "JUGADOR" not in df.columns:
        raise ValueError("El roster no contiene columna 'JUGADOR'.")

    if "EQUIPO" in df.columns:
        df = df[df["EQUIPO"].astype(str).str.strip().str.upper() == team.strip().upper()]

    df = df.copy()
    df["__KEY__"] = df["JUGADOR"].astype(str).apply(canon_key)

    image_lookup = {}
    dorsal_lookup = {}

    if "IMAGEN" in df.columns:
        image_lookup = df.dropna(subset=["IMAGEN"]).drop_duplicates("__KEY__").set_index("__KEY__")["IMAGEN"].to_dict()
    if "DORSAL" in df.columns:
        dorsal_lookup = df.drop_duplicates("__KEY__").set_index("__KEY__")["DORSAL"].to_dict()

    return image_lookup, dorsal_lookup

# ------------------- Lineups del equipo -------------------------
def mmss_from_minutes(m: float) -> str:
    s = int(round((m or 0) * 60))
    mm, ss = divmod(s, 60)
    return f"{mm:02d}:{ss:02d}"

def load_lineups_for_team(lineups_xlsx: str, team: str) -> pd.DataFrame:
    if not os.path.exists(lineups_xlsx):
        raise FileNotFoundError(f"No existe lineups: {lineups_xlsx}")

    xls = pd.ExcelFile(lineups_xlsx)
    frames = []
    for sh in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sh)
        if "EQUIPO" in df.columns:
            frames.append(df)
    if not frames:
        raise ValueError("No se encontraron hojas con columna 'EQUIPO'.")

    all_df = pd.concat(frames, ignore_index=True)
    df_team = all_df[all_df["EQUIPO"].astype(str).str.strip().str.upper() == team.strip().upper()].copy()
    if df_team.empty:
        raise SystemExit(f"⚠️ No hay quintetos para el equipo: {team}")

    for c in ["NET_RTG", "MIN_CLUTCH", "SEC_CLUTCH"]:
        if c in df_team.columns:
            df_team[c] = pd.to_numeric(df_team[c], errors="coerce")

    if "MIN_CLUTCH" not in df_team.columns and "SEC_CLUTCH" in df_team.columns:
        df_team["MIN_CLUTCH"] = df_team["SEC_CLUTCH"] / 60.0

    # mínimo 1:00 acumulado (por si el Excel no lo traía ya filtrado)
    df_team = df_team[df_team["MIN_CLUTCH"].fillna(0) >= 1.0].copy()

    # ranking por NET ajustado
    w = df_team["MIN_CLUTCH"].fillna(0) / (df_team["MIN_CLUTCH"].fillna(0) + K_MIN)
    df_team["NET_RTG_ADJ"] = df_team["NET_RTG"] * w

    df_team.sort_values(["NET_RTG_ADJ", "MIN_CLUTCH", "NET_RTG"],
                        ascending=[False, False, False], inplace=True)
    return df_team

# ------------------- Imagen / recorte circular ------------------
def load_player_image(src: str) -> Image.Image:
    img = None
    if isinstance(src, str) and src.strip():
        try:
            if src.lower().startswith("http"):
                resp = requests.get(src, timeout=6)
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
            else:
                img = Image.open(src).convert("RGBA")
            
            # Remove background using rembg
            img = remove(img)
            
            # Add white background
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
        except Exception:
            img = None
    if img is None:
        try:
            img = Image.open(GENERIC_IMG).convert("RGBA")
            # Also remove background from generic image
            img = remove(img)
            
            # Add white background
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
        except Exception:
            img = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
    return img

def circle_thumb(img: Image.Image, size: int = 240) -> Image.Image:
    img = ImageOps.fit(img, (size, size), method=Image.LANCZOS, centering=(0.5, 0.5))
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return img

def extract_logo_color(path, thumb_size=(50,50)):
    """Load image, downsize, and return its average RGB as a matplotlib color, excluding transparent pixels."""
    im = Image.open(path).convert('RGBA')  # Keep alpha channel
    im.thumbnail(thumb_size)
    arr = np.asarray(im)
    
    # Only consider non-transparent pixels (alpha > 128)
    alpha_mask = arr[:, :, 3] > 128
    if not np.any(alpha_mask):
        # If all pixels are transparent, return default color
        return (0.5, 0.5, 0.5)
    
    # Get RGB values only for non-transparent pixels
    non_transparent_pixels = arr[alpha_mask][:, :3]  # Take only RGB channels
    
    # Calculate average over non-transparent pixels only
    r, g, b = non_transparent_pixels[:, 0].mean(), non_transparent_pixels[:, 1].mean(), non_transparent_pixels[:, 2].mean()

    return (r/255, g/255, b/255)

# ------------------- Dibujo del panel ---------------------------
def build_top3_card(df_team: pd.DataFrame, team: str,
                    image_lookup: dict, dorsal_lookup: dict,
                    out_path: str = None):
    # Calculate dynamic ACCENT_COLOR based on team logo
    fn = team.lower().replace(' ', '_').replace('.', '').replace(',', '')
    path = os.path.join(os.path.dirname(__file__), '..', 'images', 'clubs', f'{fn}.png')
    if os.path.exists(path):
        ACCENT_COLOR = extract_logo_color(path)
    else:
        ACCENT_COLOR = (0.08, 0.35, 0.80)  # azul para el NET ajustado

    top3 = df_team.head(3).copy()
    if top3.empty:
        raise SystemExit("⚠️ No hay quintetos tras aplicar filtros.")

    # Desglosa jugadores y métricas de cada quinteto
    lineups = []
    for _, r in top3.iterrows():
        players = [p.strip() for p in str(r["LINEUP"]).split("|")]
        players = [p for p in players if p][:5]
        lineups.append({
            "players": players,
            "NET_RTG_RAW": float(r["NET_RTG"]) if pd.notna(r["NET_RTG"]) else np.nan,
            "NET_RTG_ADJ": float(r.get("NET_RTG_ADJ", np.nan)),
            "MIN_CLUTCH": float(r["MIN_CLUTCH"]) if pd.notna(r["MIN_CLUTCH"]) else 0.0
        })

    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI, facecolor=BG_COLOR)
    # Ampliamos ligeramente la columna de métricas y separaciones para evitar solapes
    gs = GridSpec(nrows=3, ncols=6, figure=fig,
                  height_ratios=[1, 1, 1],
                  width_ratios=[1, 1, 1, 1, 1, 1.25],  # métrica más ancha
                  wspace=0.55, hspace=0.80)

    # Títulos
    fig.text(0.03, 0.965, f"{team} — Top-3 Quintetos Clutch",
             fontsize=22, fontweight="bold", color=TITLE_COLOR, ha="left", va="top")
    fig.text(0.03, 0.920, f"Ranking por NET_RTG ponderado por minutos en el clutch.",
             fontsize=11.5, color=SUBTITLE_COLOR, ha="left", va="top")

    import matplotlib.patheffects as pe

    for y, item in enumerate(lineups):
        players = item["players"]
        net_adj = item["NET_RTG_ADJ"]
        net_raw = item["NET_RTG_RAW"]
        mins = item["MIN_CLUTCH"]

        # 5 fotos
        for x in range(5):
            ax = fig.add_subplot(gs[y, x]); ax.axis("off")
            name = players[x] if x < len(players) else ""
            key = canon_key(name)

            src = image_lookup.get(key)
            img = load_player_image(src) if src else load_player_image(None)
            ax.imshow(circle_thumb(img, size=260))
            ax.set_xticks([]); ax.set_yticks([])

            dorsal = dorsal_lookup.get(key, None)
            label = f"{int(dorsal)} - {short_label(name)}" if isinstance(dorsal, (int, float)) and not pd.isna(dorsal) else short_label(name)
            txt = ax.text(0.5, -0.12, label, ha="center", va="top", transform=ax.transAxes,
                          fontsize=10, color="black")
            txt.set_path_effects([pe.withStroke(linewidth=3, foreground="white")])

        # Columna de métricas (bien separada para evitar solapes)
        axm = fig.add_subplot(gs[y, 5]); axm.axis("off")

        # Línea 1: etiqueta + NET AJUSTADO (grande y azul) - movido más arriba
        axm.text(0.00, 0.85, "NET adj", fontsize=12, color=SUBTITLE_COLOR, ha="left", va="center")
        axm.text(1.30, 0.85, f"{net_adj:+.1f}", fontsize=24, fontweight="bold",
                 color=ACCENT_COLOR, ha="right", va="center")

        # Línea 2: minutos (pequeño, mm:ss) - centrado
        axm.text(0.00, 0.50, "Min clutch", fontsize=11, color=SUBTITLE_COLOR, ha="left", va="center")
        axm.text(1.30, 0.50, mmss_from_minutes(mins), fontsize=18, fontweight="bold",
                 color="black", ha="right", va="center")

        # Línea 3 (opcional): NET bruto pequeño en gris claro - movido más abajo
        if pd.notna(net_raw):
            axm.text(0.00, 0.15, "NET bruto", fontsize=10, color=SUBTITLE_COLOR, ha="left", va="center")
            axm.text(1.30, 0.15, f"{net_raw:+.1f}", fontsize=12, color=(0.25, 0.25, 0.28),
                     ha="right", va="center")

        # Separador entre filas
        if y < 2:
            fig.add_artist(plt.Line2D([0.04, 0.98], [0.67 - y*0.33, 0.67 - y*0.33],
                                      transform=fig.transFigure, color=(0, 0, 0, 0.06), linewidth=2))

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
        print(f"✅ Guardado: {out_path}")
    else:
        # return figure object for further manipulation
        return fig

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def main():
    roster_excel= str(JUGADORES_AGGREGATED_FILE)
    lineups_excel = "./data/clutch_lineups.xlsx"
    out_png       = "./top3_clutch.png"
    team = "LUJISA GUADALAJARA BASKET"

    # lookups
    image_lookup, dorsal_lookup = load_roster_lookup(roster_excel, team)
    # lineups
    df_team = load_lineups_for_team(lineups_excel, team)

    build_top3_card(df_team, team, image_lookup, dorsal_lookup, out_png)


if __name__ == "__main__":
    main()

# Function to extract average color from an image

def extract_logo_color(path, thumb_size=(50, 50)):
    """Load image, downsize, and return its average RGB as a matplotlib color, excluding transparent pixels."""
    im = Image.open(path).convert('RGBA')  # Keep alpha channel
    im.thumbnail(thumb_size)
    arr = np.asarray(im)

    # Only consider non-transparent pixels (alpha > 128)
    alpha_mask = arr[:, :, 3] > 128
    if not np.any(alpha_mask):
        # If all pixels are transparent, return default color
        return (0.5, 0.5, 0.5)

    # Get RGB values only for non-transparent pixels
    non_transparent_pixels = arr[alpha_mask][:, :3]  # Take only RGB channels

    # Calculate average over non-transparent pixels only
    r, g, b = non_transparent_pixels[:, 0].mean(), non_transparent_pixels[:, 1].mean(), non_transparent_pixels[:, 2].mean()

    return (r / 255, g / 255, b / 255)
