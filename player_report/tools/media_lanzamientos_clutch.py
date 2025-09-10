# -*- coding: utf-8 -*-
# pip install plotly kaleido pillow pandas openpyxl unidecode

import io, re
from PIL import Image
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from unidecode import unidecode

# --- CONFIG (tu estilo) ---
FONT            = "Montserrat, sans-serif"
COLORS          = ["#e74c3c", "#de9826", "#1abc9c", "#3498db", "#9b59b6"] 
LOW_THRESH      = 0.36
TEXT_SIZE_IN    = 22
TEXT_SIZE_OUT   = 22

# Clutch
CLUTCH_XLSX_PATH = "./data/clutch_aggregated.xlsx"
ROSTER_XLSX_PATH = "./data/jugadores_aggregated_24_25.xlsx"
ROSTER_NAME_COL  = "JUGADOR"
MIN_CLUTCH_MIN   = 1.0

# Estilo CLUTCH (mismo tono algo más oscuro)
COLORS_CLUTCH        = ["#c0392b", "#ca8322", "#16a085", "#2e86c1", "#7d3c98"]

TEXT_SIZE_IN_CLUTCH  = 18

# Geometría vertical (control total)
ROW_STEP        = 2.0      # distancia entre métricas
CENTER_TOP      = 10.0     # centro Y de la primera métrica (T1)
MEDIA_WIDTH_Y   = 0.90     # grosor de la barra MEDIA (en unidades Y)
CLUTCH_WIDTH_Y  = 0.6     # grosor de la barra CLUTCH
PAIR_DELTA      = (MEDIA_WIDTH_Y + CLUTCH_WIDTH_Y) / 2 - 0.02  # separación entre centros (pegadas)

# --- helpers nombre + lectura clutch ---
def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()) if isinstance(s, str) else ""

def _format_name_to_clutch(roster_name: str) -> str:
    if not isinstance(roster_name, str) or not roster_name.strip(): return ""
    name = _normalize_spaces(unidecode(roster_name).upper())
    if re.match(r"^[A-Z]\.\s", name): return name
    if "," in name:
        apellidos, nombres = [p.strip() for p in name.split(",", 1)]
        ini = nombres.split()[0][0] if nombres else ""
        return f"{ini}. {apellidos}".strip()
    parts = name.split()
    if len(parts) == 1: return f"{parts[0][0]}. {parts[0]}".upper()
    ini = parts[0][0]; apellidos = " ".join(parts[1:])
    return f"{ini}. {apellidos}".upper()

def _to_pct_0_100(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return (s * 100.0) if s.max() <= 1.5 else s

def _read_clutch_for_player(player_name_roster: str) -> dict | None:
    clutch_df = pd.read_excel(CLUTCH_XLSX_PATH)

    name_col = None
    for c in clutch_df.columns:
        cn = unidecode(str(c)).strip().lower()
        if cn in ("jugador", "nombre", "player"):
            name_col = c; break
    if not name_col:
        raise KeyError("No encuentro columna de nombre en clutch_aggregated.xlsx.")

    def col(cands):
        for cand in cands:
            for c in clutch_df.columns:
                if unidecode(str(c)).strip().lower() == unidecode(cand).strip().lower():
                    return c
        return None

    cFGA = col(["FGA"]); cFGM = col(["FGM"])
    c3PA = col(["3PA"]); c3PM = col(["3PM"])
    cFTA = col(["FTA"]); cFTM = col(["FTM"])
    cEFG = col(["eFG%", "EFG"]); cTS  = col(["TS%", "TS"])
    cMIN = col(["MIN_CLUTCH", "MIN", "MINUTOS_CLUTCH"])

    for c in [cFGA,cFGM,c3PA,c3PM,cFTA,cFTM,cMIN]:
        if c: clutch_df[c] = pd.to_numeric(clutch_df[c], errors="coerce").fillna(0.0)
    if cEFG: clutch_df[cEFG] = _to_pct_0_100(clutch_df[cEFG])
    if cTS:  clutch_df[cTS]  = _to_pct_0_100(clutch_df[cTS])

    target = _normalize_spaces(unidecode(_format_name_to_clutch(player_name_roster)).upper())
    mask = clutch_df[name_col].astype(str).map(lambda s: _normalize_spaces(unidecode(s).upper())) == target
    if not mask.any(): return None
    row = clutch_df[mask].iloc[0]
    if not cMIN or float(row[cMIN]) < MIN_CLUTCH_MIN: return None

    FGA = float(row[cFGA] or 0.0) if cFGA else 0.0
    FGM = float(row[cFGM] or 0.0) if cFGM else 0.0
    PA3 = float(row[c3PA] or 0.0) if c3PA else 0.0
    PM3 = float(row[c3PM] or 0.0) if c3PM else 0.0
    FTA = float(row[cFTA] or 0.0) if cFTA else 0.0
    FTM = float(row[cFTM] or 0.0) if cFTM else 0.0

    pct = lambda n,d: (n/d*100.0) if d and d>0 else 0.0
    T1 = pct(FTM, FTA)
    T3 = pct(PM3, PA3)
    T2A = max(FGA - PA3, 0.0); T2M = max(FGM - PM3, 0.0)
    T2 = pct(T2M, T2A)
    EFG = float(row[cEFG]) if cEFG else pct((FGM + 0.5*PM3), FGA)
    TS  = float(row[cTS])  if cTS  else pct((2*FGM + FTM), (2*(FGA + 0.44*FTA)))
    return {"T1 %": T1, "T2 %": T2, "T3 %": T3, "EFG %": EFG, "TS %": TS}

def _read_clutch_attempts(player_name_roster: str) -> dict:
    clutch_df = pd.read_excel(CLUTCH_XLSX_PATH)

    name_col = None
    for c in clutch_df.columns:
        cn = unidecode(str(c)).strip().lower()
        if cn in ("jugador", "nombre", "player"):
            name_col = c; break
    if not name_col:
        raise KeyError("No encuentro columna de nombre en clutch_aggregated.xlsx.")

    def col(cands):
        for cand in cands:
            for c in clutch_df.columns:
                if unidecode(str(c)).strip().lower() == unidecode(cand).strip().lower():
                    return c
        return None

    cFGA = col(["FGA"]); c3PA = col(["3PA"]); cFTA = col(["FTA"])

    for c in [cFGA, c3PA, cFTA]:
        if c: clutch_df[c] = pd.to_numeric(clutch_df[c], errors="coerce").fillna(0.0)

    target = _normalize_spaces(unidecode(_format_name_to_clutch(player_name_roster)).upper())
    mask = clutch_df[name_col].astype(str).map(lambda s: _normalize_spaces(unidecode(s).upper())) == target
    if not mask.any(): return {}
    row = clutch_df[mask].iloc[0]

    FGA = float(row[cFGA] or 0.0) if cFGA else 0.0
    PA3 = float(row[c3PA] or 0.0) if c3PA else 0.0
    FTA = float(row[cFTA] or 0.0) if cFTA else 0.0

    T2A = max(FGA - PA3, 0.0)
    
    # Extract number of games
    cGAMES = col(["GAMES", "PARTIDOS"])
    if cGAMES:
        clutch_df[cGAMES] = pd.to_numeric(clutch_df[cGAMES], errors="coerce").fillna(0.0)
        games = float(row[cGAMES] or 0.0)
        if games > 0:
            FTA /= games
            T2A /= games
            PA3 /= games
    
    return {"T1A": FTA, "T2A": T2A, "T3A": PA3}

# --- plot con eje Y numérico (sin gaps y sin inversión) ---
def plot_media_pct_with_clutch(stats: dict,
                               attempts: dict = None,
                               clutch_attempts: dict = None,  # Added clutch_attempts
                               player_name_roster: str | None = None,
                               out_png: str = None,
                               width_px: int = 2000,
                               resize_px: int = 2000) -> Image.Image:
    labels = ["TS %", "EFG %", "T3 %", "T2 %", "T1 %"]  # Reversed order
    base_vals = [float(stats.get(k, 0.0) or 0.0) for k in labels]
    max_val = max(base_vals) if base_vals else 0.0
    low_mask = [v < max_val * LOW_THRESH for v in base_vals]

    # Leer clutch si procede
    clutch_vals = None
    if player_name_roster:
        try:
            c = _read_clutch_for_player(player_name_roster)
            if c:
                clutch_vals = [float(c.get(k, 0.0) or 0.0) for k in labels]
        except Exception:
            clutch_vals = None

    # Posiciones Y (controladas, media arriba, clutch debajo pegada)
    ROW_STEP, CENTER_TOP = 2.0, 10.0
    MEDIA_WIDTH_Y, CLUTCH_WIDTH_Y = 0.90, 0.6
    PAIR_DELTA = (MEDIA_WIDTH_Y + CLUTCH_WIDTH_Y) / 2 - 0.02

    y_media = []
    y_clutch = []
    for i in range(len(labels)):
        y_center = CENTER_TOP - i * ROW_STEP
        y_media.append(y_center + PAIR_DELTA/2)
        if clutch_vals is not None:
            y_clutch.append(y_center - PAIR_DELTA/2)

    fig = go.Figure()

    # === MEDIA: eliminar texto interno ===
    media_text_inside = ["" for _ in base_vals]  # Vaciar el texto interno

    fig.add_trace(go.Bar(
        x=base_vals, y=y_media, orientation="h",
        marker=dict(color=COLORS[:len(labels)]),
        width=[MEDIA_WIDTH_Y]*len(labels),
        text=media_text_inside,                  # <- texto interno vacío
        textposition="inside",
        textfont=dict(family=FONT, size=22, color="white"),
        insidetextanchor="middle",
        hoverinfo="skip",
        showlegend=False,
    ))

    # MEDIA: texto externo con posición fija solo para valores bajos
    small_x = []
    small_y = []
    small_text = []
    small_color = []
    small_position = []

    # Determinar el valor máximo considerando ambas series (media y clutch)
    combined_max_val = max(max_val, max(clutch_vals) if clutch_vals else 0.0)

    # Asegurar que el texto externo no se sobrescriba y se muestre correctamente
    # Verificar si small_text ya contiene valores antes de agregar nuevos
    if not small_text:
        for lab, v, y in zip(labels, base_vals, y_media):
            fixed_x = 20  # Posición fija para valores bajos
            small_x.append(fixed_x if v < combined_max_val * LOW_THRESH else v / 2)  # Fijo para valores bajos, centrado para altos
            small_y.append(y)  # Posición vertical: misma que la barra
            small_text.append(f"<b>{lab.replace(' %','')} {v:.1f}%</b>")
            small_color.append("black" if v < combined_max_val * LOW_THRESH else "white")  # Color dinámico
            small_position.append("middle left" if v < max_val * LOW_THRESH else "middle center")

    # Crear texto con intentos por partido si están disponibles
    if attempts:
        small_text = []
        for lab, v, low in zip(labels, base_vals, low_mask):
            attempt_key = lab.replace(' %', 'I')  # T1 % -> T1I, T2 % -> T2I, etc.
            attempt_val = attempts.get(attempt_key, 0)
            clean_label = lab.replace(' %', '')  # Remove % from label
            if attempt_val > 0:  # Only show attempts if they exist
                small_text.append(f"<b>{clean_label} {v:.1f}% ({attempt_val:.1f} tiros)</b>")
            else:
                small_text.append(f"<b>{clean_label} {v:.1f}%</b>")
    else:
        small_text = [f"<b>{lab.replace(' %', '')} {v:.1f}%</b>" for lab, v, low in zip(labels, base_vals, low_mask)]

    fig.add_trace(go.Scatter(
        x=small_x, y=small_y, mode="text", text=small_text,
        textfont=dict(family=FONT, size=22, color=small_color),
        textposition="middle center",  # Ajustar posición del texto
        hoverinfo="skip", showlegend=False
    ))

    # === CLUTCH (debajo, pegada) con texto dentro "NN.N% clutch" y tiros ===
    # Leer clutch attempts si procede
    clutch_attempts = None
    if player_name_roster:
        try:
            clutch_attempts = _read_clutch_attempts(player_name_roster)
        except Exception:
            clutch_attempts = {}

    if clutch_vals is not None:
        clutch_text = []
        for lab, v in zip(labels, clutch_vals):
            attempt_key = lab.replace(' %', 'A')  # T1 % -> T1A, T2 % -> T2A, etc.
            attempt_val = clutch_attempts.get(attempt_key, 0) if clutch_attempts else 0
            if attempt_val > 0:
                clutch_text.append(f"{v:.1f}% clutch ({attempt_val:.1f} tiros)")
            else:
                clutch_text.append(f"{v:.1f}% clutch")

        fig.add_trace(go.Bar(
            x=clutch_vals, y=y_clutch, orientation="h",
            marker=dict(color=COLORS_CLUTCH[:len(labels)]),
            width=[CLUTCH_WIDTH_Y]*len(labels),
            text=clutch_text,  # Updated text to include attempts
            textposition="inside",  # Centrar el texto dentro de la barra de clutch
            textfont=dict(family=FONT, size=18, color="white", weight="bold"),
            insidetextanchor="middle",
            hoverinfo="skip",
            showlegend=False,
        ))

    # Escala X basada en el valor máximo combinado
    x_max = combined_max_val + (0.10 * combined_max_val) + 0.01

    fig.update_layout(
        template="presentation",
        font=dict(family=FONT),
        title=dict(text="<b>MEDIAS % LANZAMIENTOS</b>", x=0.5, y=0.95,
                   font=dict(family=FONT, size=27, color="black")),
        height=560, width=width_px,
        margin=dict(l=60, r=30, t=30, b=0),  # Reduced right margin from 60 to 30
        xaxis=dict(visible=False, range=[-0.02*max_val, x_max]),
        yaxis=dict(visible=False, range=[CENTER_TOP + ROW_STEP, CENTER_TOP - ROW_STEP*(len(labels)-1) - ROW_STEP]),
        bargap=0.0, bargroupgap=0.0
    )

    img_bytes = fig.to_image(format="png", engine="kaleido", scale=4)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    if out_png: img.save(out_png)

    ratio = resize_px / img.height
    img = img.resize((int(img.width * ratio), resize_px), Image.LANCZOS)
    return img



if __name__ == "__main__":
    sample_stats = {"T1 %": 100.0, "T2 %": 26.9, "T3 %": 17.1, "EFG %": 14.3, "TS %": 5.6}
    attemps = {"T1I": 2.5, "T2I": 5.0, "T3I": 3.0}
    jugador_roster = "LARREA IBARBURU, JON"
    #jugador_roster = "LUCENTE, IVAN"
    plot_media_pct_with_clutch(
        sample_stats,
        attempts=attemps,
        player_name_roster=jugador_roster,
        out_png="./media_lanzamientos_con_clutch.png",
        width_px=2000, resize_px=2000
    )
