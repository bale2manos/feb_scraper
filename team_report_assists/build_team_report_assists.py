# -*- coding: utf-8 -*-
"""
Asistencias · Informe Overview (A4 apaisado)
--------------------------------------------
- Valida jugadores contra ./data/jugadores_aggregated_24_25.xlsx (descarta filas fuera del roster del equipo).
- Etiquetas con DORSAL + nombre corto (p.ej. "14 - G. DÍAZ").
- Grafo a la izquierda ocupando casi TODA la altura (nota inferior opcional).
- Derecha: Heatmap + Top-10; mayor separación entre ambos y respecto al grafo.
- % en el Top-10 = % sobre el **total de asistencias del equipo**.
- Heatmap:
    • Intensidad de color = **CONTEO BRUTO** de asistencias por pareja (PASADOR→ANOTADOR).
    • Ejes X e Y con el **mismo orden**; celdas inexistentes se muestran como 0.
    • Anotación en celdas: **solo %** y **solo si ≥ 5%** (por defecto). Nada por debajo del 5%.
      En celdas oscuras el texto va en **blanco con borde negro fino** para máxima legibilidad.
- Montserrat desde ./fonts si está disponible (o instalada).
- Si la salida es .pdf -> 2 páginas (P1: grafo; P2: heatmap+top). Si es imagen -> 1 lámina.

Requisitos:
  pip install pandas matplotlib networkx pillow openpyxl
"""

import os
import re
import argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import networkx as nx
from PIL import Image
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.backends.backend_pdf import PdfPages


# =========================
# Fuente Montserrat
# =========================
def _ensure_montserrat():
    try:
        fm.findfont("Montserrat", fallback_to_default=False)
        plt.rcParams['font.family'] = 'Montserrat'
        return
    except Exception:
        pass
    font_dir = os.path.join(os.path.dirname(__file__), "fonts")
    for cand in ("Montserrat-Regular.ttf", "Montserrat-VariableFont_wght.ttf", "Montserrat.ttf"):
        p = os.path.join(font_dir, cand)
        if os.path.exists(p):
            fm.fontManager.addfont(p)
    b = os.path.join(font_dir, "Montserrat-Bold.ttf")
    if os.path.exists(b):
        fm.fontManager.addfont(b)
    plt.rcParams['font.family'] = 'Montserrat'


_ensure_montserrat()


# =========================
# Logo / color de club
# =========================
def get_team_logo(team_name: str):
    fn = (team_name.lower()
          .replace(' ', '_')
          .replace('.', '')
          .replace(',', '')
          .replace('á', 'a')
          .replace('é', 'e')
          .replace('í', 'i')
          .replace('ó', 'o')
          .replace('ú', 'u')
          .replace('ñ', 'n')
          .replace('ü', 'u'))
    path = os.path.join(os.path.dirname(__file__), '..', 'images', 'clubs', f'{fn}.png')
    if os.path.exists(path):
        return Image.open(path).convert('RGBA'), path
    print(f"⚠️ Logo not found for team: {team_name} (looking for {path})")
    return None, None


def extract_logo_color_from_image(im_rgba: Image.Image, thumb_size=(50, 50)):
    im = im_rgba.copy()
    im.thumbnail(thumb_size)
    arr = np.asarray(im)
    alpha_mask = arr[:, :, 3] > 128
    if not np.any(alpha_mask):
        return (0.5, 0.5, 0.5)
    rgb = arr[alpha_mask][:, :3]
    r, g, b = rgb[:, 0].mean(), rgb[:, 1].mean(), rgb[:, 2].mean()
    return (r / 255.0, g / 255.0, b / 255.0)


# =========================
# Nombres / roster
# =========================
_ACENTS = str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUN")


def _canon_key(name: str) -> str:
    """
    Clave canónica para emparejar:
      - "ATIENZA PEREA, JUAN" -> "J ATIENZA PEREA"
      - "J. ATIENZA PEREA"    -> "J ATIENZA PEREA"
      - "JUAN ATIENZA PEREA"  -> "J ATIENZA PEREA"
    """
    s = (name or "").upper().translate(_ACENTS)
    s = re.sub(r"\s+", " ", s.replace(".", "").strip())
    if "," in s:
        surnames, names = [x.strip() for x in s.split(",", 1)]
        first = names.split()[0] if names else ""
        initial = first[:1] if first else ""
        return f"{initial} {surnames}".strip()
    parts = s.split()
    if len(parts) >= 2:
        if len(parts[0]) == 1:  # "J ATIENZA PEREA"
            initial = parts[0]
            surnames = " ".join(parts[1:])
        else:  # "JUAN ATIENZA PEREA"
            initial = parts[0][:1]
            surnames = " ".join(parts[1:])
        return f"{initial} {surnames}".strip()
    return s


def _load_roster(roster_path: str, team_name: str):
    """
    Devuelve (valid_keys, dorsal_lookup)
      valid_keys: set de claves canónicas de jugadores del equipo
      dorsal_lookup: dict {clave_canónica -> dorsal}
    """
    if not os.path.exists(roster_path):
        print(f"⚠️ No se encontró {roster_path}. No se validará roster ni dorsales.")
        return set(), {}

    df_r = pd.read_excel(roster_path)
    if 'JUGADOR' not in df_r.columns:
        print("⚠️ jugadores_aggregated_24_25.xlsx sin columna 'JUGADOR'.")
        return set(), {}

    if 'EQUIPO' in df_r.columns:
        df_r = df_r[df_r['EQUIPO'].astype(str).str.strip() == str(team_name).strip()]

    df_r = df_r.copy()
    df_r['__KEY__'] = df_r['JUGADOR'].astype(str).apply(_canon_key)
    valid_keys = set(df_r['__KEY__'].unique())

    dorsal_lookup = {}
    if 'DORSAL' in df_r.columns:
        df_tmp = df_r.dropna(subset=['DORSAL']).drop_duplicates(subset='__KEY__')
        dorsal_lookup = df_tmp.set_index('__KEY__')['DORSAL'].to_dict()

    return valid_keys, dorsal_lookup


def _format_player_label(original_name: str, dorsal_lookup: dict) -> str:
    """Etiqueta 'DORSAL - Nombre Apellido' (dos primeras palabras del nombre original)."""
    key = _canon_key(original_name)
    dorsal = dorsal_lookup.get(key, None)
    dorsal_txt = f"{int(dorsal)} - " if (isinstance(dorsal, (int, float)) and not np.isnan(dorsal)) else ""
    parts = original_name.strip().split()
    short = " ".join(parts[:2]) if len(parts) >= 2 else original_name.strip()
    return f"{dorsal_txt}{short}".strip()


# =========================
# Función principal
# =========================
def build_team_report_assists(
    df_assists_team: pd.DataFrame,
    output_path: str = None,
    dpi: int = 180,
    edge_threshold: int = 2,
    roster_path: str = "./data/jugadores_aggregated_24_25.xlsx",
    fig_width: float = 13.5,  # más ancho que A4 para ganar aire (A4≈11.69)
    fig_height: float = 8.27,
    pct_cell_threshold: float = 0.05  # Mostrar % solo si ≥ 5%
):
    """
    Devuelve:
      - Figure si genera 1 lámina (png/jpg).
      - None si guarda PDF multipágina.
    """

    # --- Validación columnas
    req = {'PASADOR', 'ANOTADOR', 'N_ASISTENCIAS'}
    miss = req - set(df_assists_team.columns)
    if miss:
        raise ValueError(f"Faltan columnas requeridas: {miss}")

    # --- Equipo
    team_name = df_assists_team['EQUIPO'].iloc[0] if 'EQUIPO' in df_assists_team.columns and not df_assists_team['EQUIPO'].isna().all() else "Equipo"

    # --- Roster
    valid_keys, dorsal_lookup = _load_roster(roster_path, team_name)

    # --- Limpieza / validación de filas
    df = df_assists_team[df_assists_team['PASADOR'] != df_assists_team['ANOTADOR']].copy()
    df['PASADOR'] = df['PASADOR'].astype(str).str.strip()
    df['ANOTADOR'] = df['ANOTADOR'].astype(str).str.strip()
    df['__KP'] = df['PASADOR'].apply(_canon_key)
    df['__KA'] = df['ANOTADOR'].apply(_canon_key)

    mask_p = df['__KP'].isin(valid_keys) if valid_keys else True
    mask_a = df['__KA'].isin(valid_keys) if valid_keys else True
    df = df.loc[mask_p & mask_a].copy()

    # --- Etiquetas con dorsal
    df['PASADOR_LBL'] = df['PASADOR'].apply(lambda s: _format_player_label(s, dorsal_lookup))
    df['ANOTADOR_LBL'] = df['ANOTADOR'].apply(lambda s: _format_player_label(s, dorsal_lookup))

    # --- Agregaciones
    agg = (df.groupby(['PASADOR', 'ANOTADOR', 'PASADOR_LBL', 'ANOTADOR_LBL'], as_index=False)['N_ASISTENCIAS']
           .sum()
           .sort_values('N_ASISTENCIAS', ascending=False))

    total_by_p = agg.groupby('PASADOR_LBL')['N_ASISTENCIAS'].sum().sort_values(ascending=False)
    total_by_a = agg.groupby('ANOTADOR_LBL')['N_ASISTENCIAS'].sum().sort_values(ascending=False)
    total_team = int(agg['N_ASISTENCIAS'].sum())

    # ---- ORDEN UNIFICADO para filas y columnas (mismo set de jugadores en ambos ejes)
    # --- Ordenar por dorsal de menor a mayor
    # --- Helper para extraer dorsal del label
    def _get_dorsal(lbl):
        # Extrae dorsal del formato 'DORSAL - Nombre Apellido'
        m = re.match(r"^(\d+)\s*-", lbl)
        return int(m.group(1)) if m else 999

    total_combined = (total_by_p.add(total_by_a, fill_value=0)).sort_values(ascending=False)
    players_order = sorted(total_combined.index, key=_get_dorsal)

    # --- Matrices de CONTEOS y de % por pasador
    pivot_counts = (agg.pivot_table(index='PASADOR_LBL', columns='ANOTADOR_LBL',
                                    values='N_ASISTENCIAS', aggfunc='sum', fill_value=0)
                    .reindex(index=players_order, columns=players_order)
                    .fillna(0).astype(int))

    row_sums = pivot_counts.sum(axis=1).replace(0, np.nan)
    pivot_pct = (pivot_counts.div(row_sums, axis=0)).fillna(0.0)

    # --- Paleta desde logo
    logo_img, _ = get_team_logo(team_name)
    team_color = extract_logo_color_from_image(logo_img) if logo_img is not None else (0.10, 0.35, 0.80)
    primary = team_color
    edge_color = (*team_color, 0.75)
    node_face = (*team_color, 0.20)
    node_edge = (*team_color, 0.95)
    cmap_heat = mpl.colormaps.get_cmap('Blues')

    # ---------------- Grafo ----------------
    G = nx.DiGraph()
    for _, r in agg.iterrows():
        w = int(r['N_ASISTENCIAS'])
        if w >= edge_threshold:
            G.add_edge(r['PASADOR_LBL'], r['ANOTADOR_LBL'], weight=w)

    node_weights = {n: total_by_p.get(n, 0) + total_by_a.get(n, 0) for n in G.nodes}
    if node_weights:
        nw = np.array(list(node_weights.values()), dtype=float)
        vmin, vmax = nw.min(), nw.max()

        def _scale(x, smin=450, smax=2300):
            if vmax == vmin:
                return (smin + smax) / 2.0
            return smin + (smax - smin) * (x - vmin) / (vmax - vmin)

        node_sizes = [_scale(node_weights[n]) for n in G.nodes]
    else:
        node_sizes = [800 for _ in G.nodes]

    eweights = [G[u][v]['weight'] for u, v in G.edges]
    if eweights:
        ew = np.array(eweights, dtype=float)
        emin, emax = ew.min(), ew.max()

        def _e(w, smin=0.9, smax=6.2):
            if emax == emin:
                return (smin + smax) / 2.0
            return smin + (smax - smin) * (w - emin) / (emax - emin)

        edge_widths = [_e(w) for w in eweights]
    else:
        edge_widths = []

    pos = nx.kamada_kawai_layout(G) if len(G) else {}
    # Padding interno para que no toque bordes del eje
    if pos:
        xs = np.array([p[0] for p in pos.values()])
        ys = np.array([p[1] for p in pos.values()])
        xmin, xmax = xs.min(), xs.max()
        ymin, ymax = ys.min(), ys.max()
        pad = 0.07
        for n, (x, y) in pos.items():
            xn = (x - xmin) / (xmax - xmin + 1e-9)
            yn = (y - ymin) / (ymax - ymin + 1e-9)
            pos[n] = (pad + xn * (1 - 2 * pad), pad + yn * (1 - 2 * pad))

    # ---------------- Helper: Top-10 con % sobre el TOTAL DEL EQUIPO ----------------
    def _top10_teamshare(agg_df, pivot_counts_df, total_team_assists):
        row_sum_map = pivot_counts_df.sum(axis=1).to_dict()
        tmp = agg_df.copy()
        tmp['PCT_PASADOR'] = tmp.apply(
            lambda r: (r['N_ASISTENCIAS'] / row_sum_map.get(r['PASADOR_LBL'], 0))
            if row_sum_map.get(r['PASADOR_LBL'], 0) else 0.0, axis=1
        )
        topN = tmp.sort_values(['N_ASISTENCIAS', 'PCT_PASADOR'], ascending=[False, False]).head(10)
        labels = [f"{p} --→ {a}" for p, a in zip(topN['PASADOR_LBL'], topN['ANOTADOR_LBL'])]
        counts = topN['N_ASISTENCIAS'].astype(int).tolist()
        pct_team = [(c / total_team_assists * 100.0) if total_team_assists else 0.0 for c in counts]
        return labels, counts, pct_team

    # === Helpers de anotación con contraste automático ===
    def _perceived_luma(r, g, b):
        return 0.299 * r + 0.587 * g + 0.114 * b

    def _annotate_heatmap(ax, im, counts_mat, pct_mat, pct_threshold=pct_cell_threshold, font_size=8):
        """
        Escribe etiqueta en cada celda:
          - Solo se anota si pct >= pct_threshold (por defecto 5%).
          - Formato: 'XX%'.
          - En cada fila, el mayor porcentaje va en negrita, el resto en normal.
        """
        H, W = counts_mat.shape
        norm = im.norm
        cmap = im.cmap
        for i in range(H):
            row_pcts = [float(pct_mat[i, j]) for j in range(W)]
            max_j = np.argmax(row_pcts)
            for j in range(W):
                pct = row_pcts[j]
                if pct < pct_threshold:
                    continue
                count = counts_mat[i, j]
                rgba = cmap(norm(count))
                r, g, b, _ = rgba
                is_dark = _perceived_luma(r, g, b) < 0.5
                color = 'white' if is_dark else 'black'
                weight = 'bold' if j == max_j else 'normal'
                ax.text(j, i, f"{pct*100:.0f}%", ha='center', va='center',
                        fontsize=font_size, color=color, fontweight=weight)

    # ---------------- Helpers de dibujo ----------------
    note_txt = (f"Total asistencias: {total_team}   \n"
                f"Jugadores (en grafo): {len(G.nodes)}   \n"
                f"Enlaces: {len(G.edges)}   \n"
                f"Nota: sólo enlaces con ≥ {edge_threshold} asistencias")

    def _draw_graph_with_note(fig):
        # Subdiseño: 2 filas -> grafo (~92%) + (nota desactivada aquí por simplicidad)
        left = GridSpec(2, 1, figure=fig, height_ratios=[1.0, 0.0], hspace=0.06)
        ax = fig.add_subplot(left[0, 0])
        nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_color,
                               arrows=True, arrowsize=12, arrowstyle='-|>', alpha=0.7,
                               connectionstyle='arc3,rad=0.10', ax=ax,
                               min_source_margin=10, min_target_margin=10)
        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=[node_face] * len(G),
                               edgecolors=node_edge, linewidths=1.2, ax=ax)
        lbls = nx.draw_networkx_labels(G, pos, labels={n: n for n in G.nodes},
                                       font_weight='semibold', font_family='Montserrat', font_size=10, ax=ax)
        for t in lbls.values():
            t.set_path_effects([pe.withStroke(linewidth=3.0, foreground='white')])
        ax.axis('off')
        if logo_img is not None:
            ax_logo = ax.inset_axes([0.015, 0.64, 0.18, 0.32])
            ax_logo.imshow(logo_img)
            ax_logo.axis('off')

    def _draw_heatmap_top(fig):
        # Derecha: heatmap (arriba) + top-10 (abajo)
        right = GridSpec(2, 1, figure=fig, height_ratios=[1.00, 1.00], hspace=0.40)

        # ===== Heatmap: color por CONTEO BRUTO; etiquetas % solo si ≥5% =====
        ax_hm = fig.add_subplot(right[0, 0])
        vmax_counts = pivot_counts.values.max() if pivot_counts.values.size else 1
        im = ax_hm.imshow(pivot_counts.values, cmap=cmap_heat, aspect='auto', vmin=0, vmax=vmax_counts)

        ax_hm.set_title("% Asistencias a anotador en función del pasador",
                        fontsize=12, fontweight='bold', pad=10)

        ax_hm.set_xticks(np.arange(len(players_order)))
        ax_hm.set_yticks(np.arange(len(players_order)))
        ax_hm.set_xticklabels(players_order, rotation=35, ha='right', fontsize=9)
        ax_hm.set_yticklabels(players_order, fontsize=9)
        ax_hm.set_xlabel("ANOTADOR")
        ax_hm.set_ylabel("PASADOR")

        _annotate_heatmap(ax_hm, im, pivot_counts.values, pivot_pct.values,
                          pct_threshold=pct_cell_threshold, font_size=8)

        cbar = fig.colorbar(im, ax=ax_hm, fraction=0.035, pad=0.02)
        cbar.set_label("Número de asistencias -> Intensidad del color", rotation=90)

        # ===== Top-10 — % sobre TOTAL DEL EQUIPO =====
        ax_top = fig.add_subplot(right[1, 0])
        labels, counts, pcts_team = _top10_teamshare(agg, pivot_counts, total_team)

        y = np.arange(len(labels))
        bars = ax_top.barh(y, counts, color=node_face, edgecolor=node_edge, linewidth=1.0)

        # >>>>> CAMBIO: etiquetas centradas dentro de la barra (número + %), con trazo fino <<<<<
        for i, (bar, c, pct) in enumerate(zip(bars, counts, pcts_team)):
            xpos = bar.get_width() / 2.0
            ax_top.text(
                xpos, i,
                f"{c} ({pct:.1f}%)",
                ha='center', va='center',
                fontsize=10, color='black', fontweight='bold'
            )

        ax_top.set_yticks(y)
        ax_top.set_yticklabels(labels, fontsize=9)
        ax_top.invert_yaxis()
        ax_top.set_xlabel("Asistencias (total) · % sobre total equipo")
        ax_top.grid(axis='x', linestyle=':', alpha=0.35)

    # ---------------- Salida multipágina o 1 lámina ----------------
    is_pdf = isinstance(output_path, str) and output_path.lower().endswith(".pdf")

    if is_pdf and output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # P1: grafo
        fig1 = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
        _draw_graph_with_note(fig1)
        fig1.subplots_adjust(left=0.04, right=0.99, top=0.96, bottom=0.05)
        # P2: heatmap + top-10
        fig2 = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
        _draw_heatmap_top(fig2)
        fig2.subplots_adjust(left=0.06, right=0.985, top=0.93, bottom=0.08)
        with PdfPages(output_path) as pdf:
            pdf.savefig(fig1, bbox_inches='tight'); plt.close(fig1)
            pdf.savefig(fig2, bbox_inches='tight'); plt.close(fig2)
        return None

    # ---- Lámina única: 1 fila × 2 columnas (izq: grafo; dcha: heatmap+top) ----
    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
    outer = GridSpec(nrows=1, ncols=2, figure=fig, width_ratios=[1.70, 1.00], wspace=0.42)

    # Izquierda (grafo)
    left = GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[0, 0],
                                   height_ratios=[1.0, 0.0], hspace=0.06)
    ax_graph = fig.add_subplot(left[0, 0])
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_color,
                           arrows=True, arrowsize=12, arrowstyle='-|>', alpha=0.7,
                           connectionstyle='arc3,rad=0.10', ax=ax_graph,
                           min_source_margin=10, min_target_margin=10)
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=[node_face] * len(G),
                           edgecolors=node_edge, linewidths=1.2, ax=ax_graph)
    lbls = nx.draw_networkx_labels(G, pos, labels={n: n for n in G.nodes},
                                   font_weight='semibold', font_family='Montserrat', font_size=9, ax=ax_graph)
    for t in lbls.values():
        t.set_path_effects([pe.withStroke(linewidth=3.0, foreground='white')])
    ax_graph.axis('off')
    if logo_img is not None:
        ax_logo = ax_graph.inset_axes([0.015, 0.64, 0.18, 0.32])
        ax_logo.imshow(logo_img)
        ax_logo.axis('off')

    # Derecha (heatmap + top-10)
    right = GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[0, 1],
                                    height_ratios=[1.00, 1.00], hspace=0.40)

    # Heatmap: color por CONTEO BRUTO; etiquetas % solo si ≥5%
    ax_hm = fig.add_subplot(right[0, 0])
    vmax_counts = pivot_counts.values.max() if pivot_counts.values.size else 1
    im = ax_hm.imshow(pivot_counts.values, cmap=cmap_heat, aspect='auto', vmin=0, vmax=vmax_counts)

    ax_hm.set_title("% Asistencias a jugador en función del anotador",
                    fontsize=12, fontweight='bold', pad=10)

    ax_hm.set_xticks(np.arange(len(players_order)))
    ax_hm.set_yticks(np.arange(len(players_order)))
    ax_hm.set_xticklabels(players_order, rotation=35, ha='right', fontsize=8)
    ax_hm.set_yticklabels(players_order, fontsize=8)
    ax_hm.set_xlabel("ANOTADOR")
    ax_hm.set_ylabel("PASADOR")

    _annotate_heatmap(ax_hm, im, pivot_counts.values, pivot_pct.values,
                      pct_threshold=pct_cell_threshold, font_size=8)

    cbar = fig.colorbar(im, ax=ax_hm, fraction=0.046, pad=0.04)
    cbar.set_label("Número de asistencias -> Intensidad del color", rotation=90)

    # Top-10 — % sobre TOTAL DEL EQUIPO
    ax_top = fig.add_subplot(right[1, 0])
    labels, counts, pcts_team = _top10_teamshare(agg, pivot_counts, total_team)
    y = np.arange(len(labels))
    bars = ax_top.barh(y, counts, color=node_face, edgecolor=node_edge, linewidth=1.0)

    # >>>>> CAMBIO: etiquetas centradas dentro de la barra (número + %), con trazo fino <<<<<
    for i, (bar, c, pct) in enumerate(zip(bars, counts, pcts_team)):
        xpos = bar.get_width() / 2.0
        txt = ax_top.text(
            xpos, i,
            f"{c} ({pct:.1f}%)",
            ha='center', va='center',
            fontsize=9, color='black', fontweight='bold'
        )

    ax_top.set_yticks(y)
    ax_top.set_yticklabels(labels, fontsize=8)
    ax_top.invert_yaxis()
    ax_top.set_xlabel("Asistencias (total) · % sobre total equipo")
    ax_top.grid(axis='x', linestyle=':', alpha=0.35)

    # Márgenes generales
    fig.subplots_adjust(top=0.92, left=0.05, right=0.985, bottom=0.07)

    # Guardado opcional
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches='tight')

    return fig


# =========================
# CLI
# =========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar overview de asistencias para un equipo (A4 apaisado).")
    parser.add_argument("--team", type=str, required=True, help="Nombre EXACTO del equipo (columna EQUIPO).")
    parser.add_argument("--input", type=str, default="./data/assists.xlsx",
                        help="Excel de asistencias (por defecto ./data/assists.xlsx).")
    parser.add_argument("--sheet", type=str, default=0, help="Hoja de Excel (nombre o índice).")
    parser.add_argument("--output", type=str, default=None,
                        help="Ruta de salida. .pdf => 2 páginas; .png/.jpg => 1 lámina.")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--edge-threshold", type=int, default=2,
                        help="Umbral mínimo de asistencias para dibujar aristas.")
    parser.add_argument("--roster", type=str, default="./data/jugadores_aggregated_24_25.xlsx",
                        help="Excel con roster y dorsales.")
    parser.add_argument("--fig-width", type=float, default=13.5,
                        help="Ancho del lienzo en pulgadas (default 13.5).")
    parser.add_argument("--fig-height", type=float, default=8.27,
                        help="Alto del lienzo en pulgadas (default 8.27).")
    parser.add_argument("--cell-pct-threshold", type=float, default=0.05,
                        help="Umbral para mostrar % en celdas del heatmap (0-1).")
    args = parser.parse_args()

    # Leer asistencias
    df_all = pd.read_excel(args.input, sheet_name=args.sheet)
    if 'EQUIPO' not in df_all.columns:
        raise ValueError("El Excel de asistencias no contiene la columna 'EQUIPO'.")

    # Filtrar equipo
    df_team = df_all[df_all['EQUIPO'].astype(str).str.strip() == args.team].copy()
    if df_team.empty:
        raise SystemExit(f"⚠️ No hay registros para el equipo: {args.team}")

    # Ruta de salida por defecto
    if not args.output:
        safe_team = re.sub(r"[^a-zA-Z0-9_-]+", "_", args.team).strip("_")
        os.makedirs("./output", exist_ok=True)
        args.output = os.path.join("./output", f"assists_overview_{safe_team}.png")

    # Generar
    fig = build_team_report_assists(
        df_team,
        output_path=args.output,
        dpi=args.dpi,
        edge_threshold=args.edge_threshold,
        roster_path=args.roster,
        fig_width=args.fig_width,
        fig_height=args.fig_height,
        pct_cell_threshold=args.cell_pct_threshold
    )

    if fig is not None:
        fig.savefig(args.output, dpi=args.dpi, bbox_inches='tight')
        print(f"✅ Guardado: {args.output}")
    else:
        print(f"✅ Guardado multipágina: {args.output}")
