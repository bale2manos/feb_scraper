# -*- coding: utf-8 -*-
"""
PBP ➜ Minutos por sustituciones (robusto)
-----------------------------------------
- Abre partido, pestaña 'keyfacts', marca 4 cuartos y espera estabilización.
- Guarda snapshot del widget y, si hace falta, snapshot por filas (fallback).
- Parsea OFFLINE con BeautifulSoup de forma robusta:
    • Detecta filas por [data-cuarto] (no solo .fila[data-cuarto]).
    • Extrae periodo con regex (primer número que aparezca).
    • Extrae reloj buscando cualquier mm:ss en el texto de la fila.
    • Texto del evento = join de todos los textos de la fila (stripped_strings).
    • Equipo/Jugador/Detalle mediante varios patrones; si falla, al menos jugador.
    • Sustituciones detectadas sobre el TEXTO COMPLETO de la fila (no solo detail).
- Construye intervalos Entra→Sale (con inferencia de titulares Q1).
- Exporta minutos por jugador a Excel.

Uso rápido:
    python scraper_minutes.py                       # scrapea y exporta
    python scraper_minutes.py --partido 2413778     # fuerza partido
    python scraper_minutes.py --snapshot ./data/pbp_snapshot_2413778.html  # solo parsea offline
    python scraper_minutes.py --dump events.csv     # vuelca eventos crudos para debug

Requisitos:
    pip install bs4 lxml selenium pandas
"""

import os
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import argparse

import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Si ya tienes estos helpers en tu repo, se usan tal cual:
from utils.web_scraping import init_driver, accept_cookies

BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"
WIDGET_SEL = "div.widget-keyfacts"

# ----------------------------
# Config
# ----------------------------
@dataclass
class GameConfig:
    q_secs: int = 10 * 60
    ot_secs: int = 5 * 60

def period_len(period: int, cfg: GameConfig) -> int:
    return cfg.ot_secs if period >= 5 else cfg.q_secs

def parse_clock_to_seconds_anywhere(text: str) -> Optional[int]:
    """Busca mm:ss en cualquier parte del texto."""
    if not text:
        return None
    m = re.search(r'(\d{1,2}):([0-5]\d)', text)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))

def absolute_elapsed_seconds(period: Optional[int], clock_seconds: Optional[int], cfg: GameConfig) -> Optional[float]:
    if period is None or clock_seconds is None:
        return None
    elapsed = 0
    for p in range(1, period):
        elapsed += period_len(p, cfg)
    elapsed += (period_len(period, cfg) - clock_seconds)
    return float(elapsed)

def seconds_to_mmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s//60:02d}:{s%60:02d}"

# ----------------------------
# Clasificación de acciones
# ----------------------------
SUB_IN_RE  = re.compile(r"Sustituci[oó]n\s*\(.*Entra.*\)", re.IGNORECASE)
SUB_OUT_RE = re.compile(r"Sustituci[oó]n\s*\(.*Sale.*\)",  re.IGNORECASE)

def classify_action(full_text: str) -> str:
    t = (full_text or "").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if SUB_IN_RE.search(t):   return "SUB_IN"
    if SUB_OUT_RE.search(t):  return "SUB_OUT"
    return "OTHER"

# ----------------------------
# Selenium helpers
# ----------------------------
def ensure_keyfacts_tab(driver):
    try:
        tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-tab[data-action='keyfacts']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tab)
        driver.execute_script("arguments[0].click()", tab)
    except Exception:
        pass  # si ya está

def check_all_quarters(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.selector.inline.de.checkboxes input.checkbox"))
        )
        driver.execute_script("""
            const boxes = document.querySelectorAll('div.selector.inline.de.checkboxes input.checkbox');
            boxes.forEach(cb => {
                if (!cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', {bubbles:true}));
                }
            });
        """)
    except Exception:
        pass

def get_widget_row_count(driver) -> int:
    try:
        return int(driver.execute_script(
            "var w=document.querySelector(arguments[0]);"
            "return w? w.querySelectorAll('[data-cuarto]').length: 0;", WIDGET_SEL))
    except Exception:
        return 0

def scroll_widget_to_bottom(driver):
    driver.execute_script(
        "var w=document.querySelector(arguments[0]); if(w){w.scrollTop = w.scrollHeight;}", WIDGET_SEL
    )
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    driver.execute_script("window.scrollTo(0, 0)")

def wait_widget_stable(driver, min_rows:int=10, stable_cycles:int=3, poll:float=0.6, timeout:float=25.0) -> int:
    t0 = time.time()
    last = -1
    stable = 0
    while time.time() - t0 < timeout:
        scroll_widget_to_bottom(driver)
        cnt = get_widget_row_count(driver)
        if cnt == last:
            stable += 1
        else:
            stable = 0
        last = cnt
        if cnt >= min_rows and stable >= stable_cycles:
            return cnt
        time.sleep(poll)
    return max(0, last)

def take_widget_snapshot(driver, path_html: str) -> str:
    widget = driver.find_element(By.CSS_SELECTOR, WIDGET_SEL)
    html = widget.get_attribute("outerHTML")
    os.makedirs(os.path.dirname(path_html) or ".", exist_ok=True)
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)
    return html

def take_rows_snapshot(driver, path_html_rows: str) -> str:
    rows_html_list = driver.execute_script("""
        const nodes = document.querySelectorAll('[data-cuarto]');
        return Array.from(nodes).map(n => n.outerHTML);
    """) or []
    html = "<div class='widget-keyfacts-snapshot'>\n" + "\n".join(rows_html_list) + "\n</div>"
    os.makedirs(os.path.dirname(path_html_rows) or ".", exist_ok=True)
    with open(path_html_rows, "w", encoding="utf-8") as f:
        f.write(html)
    return html

# ----------------------------
# Parseo offline (ROBUSTO)
# ----------------------------
BASE_ROW_RE = re.compile(
    r"\((?P<team>[^)]+)\)\s*(?P<player>[^:]+):\s*(?P<detail>.+)",
    re.IGNORECASE
)

ALT_ROW_RE_1 = re.compile(  # (TEAM) PLAYER - DETAIL
    r"\((?P<team>[^)]+)\)\s*(?P<player>[^-:]+)\s*[-:]\s*(?P<detail>.+)",
    re.IGNORECASE
)

ALT_ROW_RE_2 = re.compile(  # PLAYER: DETAIL (sin equipo)
    r"^(?P<player>[^:]{2,}?)\s*:\s*(?P<detail>.+)$",
    re.IGNORECASE
)

def first_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r'(\d+)', s)
    return int(m.group(1)) if m else None

def parse_snapshot_to_rows(html: str, cfg: GameConfig, debug_dump: Optional[str]=None) -> List[Dict]:
    # BeautifulSoup parser fallback
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    filas = soup.select("[data-cuarto]")  # más laxo que .fila[data-cuarto]
    rows: List[Dict] = []
    dbg = {"total_nodes": len(filas), "no_period":0, "no_clock":0, "no_elapsed":0, "with_elapsed":0, "no_player":0}

    for fila in filas:
        try:
            # Periodo
            p_raw = fila.get("data-cuarto")
            period = first_int(p_raw)

            # Texto completo (más robusto que seleccionar spans concretos)
            full_text = " ".join(list(fila.stripped_strings))
            full_text = re.sub(r"\s+", " ", full_text)

            # Reloj: busca mm:ss en cualquier parte
            clock_seconds = parse_clock_to_seconds_anywhere(full_text)
            clock_str = None
            if clock_seconds is not None:
                clock_str = f"{clock_seconds//60:02d}:{clock_seconds%60:02d}"

            # Equipo, jugador, detalle
            team = player = detail = None
            m = BASE_ROW_RE.search(full_text) or ALT_ROW_RE_1.search(full_text) or ALT_ROW_RE_2.search(full_text)
            if m:
                team = (m.groupdict().get("team") or "").strip() or None
                player = (m.groupdict().get("player") or "").strip() or None
                detail = (m.groupdict().get("detail") or "").strip() or None

            action = classify_action(full_text)

            elapsed = absolute_elapsed_seconds(period, clock_seconds, cfg)

            dbg["no_period"] += int(period is None)
            dbg["no_clock"]  += int(clock_seconds is None)
            dbg["no_player"] += int(not player)

            row = {
                "period": period,
                "clock_str": clock_str or "",
                "clock_seconds": clock_seconds,
                "elapsed": elapsed,
                "team": team,
                "player": player,
                "detail": detail if detail else full_text,  # conserva algo legible
                "action": action,
                "raw": full_text
            }
            rows.append(row)

            if elapsed is None:
                dbg["no_elapsed"] += 1
            else:
                dbg["with_elapsed"] += 1

        except Exception:
            continue

    # Ordena por tiempo si lo tenemos; si no, deja el orden de aparición
    rows_with_t = [r for r in rows if r["elapsed"] is not None]
    rows_without_t = [r for r in rows if r["elapsed"] is None]
    rows_with_t.sort(key=lambda r: (r["elapsed"], r["period"] or 0), reverse=False)
    rows = rows_with_t + rows_without_t

    # Debug métricas
    print(f"[DEBUG] Nodos con data-cuarto: {dbg['total_nodes']}")
    print(f"[DEBUG] Sin periodo: {dbg['no_period']} · Sin reloj: {dbg['no_clock']} · Sin elapsed: {dbg['no_elapsed']} · Con elapsed: {dbg['with_elapsed']}")
    print(f"[DEBUG] Sin jugador parseado: {dbg['no_player']}")

    # Dump opcional de eventos crudos
    if debug_dump:
        df_dbg = pd.DataFrame(rows)
        df_dbg.to_csv(debug_dump, index=False, encoding="utf-8")
        print(f"[DEBUG] Dump de eventos crudos: {debug_dump}")

    # Devuelve al menos los que tienen tiempo (son los útiles para intervalos)
    return [r for r in rows if r.get("elapsed") is not None]

def game_end_absolute(rows: List[Dict], cfg: GameConfig) -> float:
    if not rows:
        return 0.0
    max_p = max((r["period"] or 0) for r in rows)
    return absolute_elapsed_seconds(max_p if max_p else 4, 0, cfg) or 0.0

# ----------------------------
# Intervalos Entra→Sale
# ----------------------------
def build_player_intervals(rows: List[Dict], cfg: GameConfig) -> Dict[Tuple[str,str], List[Tuple[float,float,Dict]]]:
    intervals: Dict[Tuple[str,str], List[Tuple[float,float,Dict]]] = defaultdict(list)
    open_in: Dict[Tuple[str,str], Dict] = {}

    starters_seen_in_Q1_at_10: Dict[str, Set[str]] = defaultdict(set)
    starters_opened: Dict[str, bool] = defaultdict(lambda: False)

    # Detecta (TEAM, PLAYER) por SUB_IN a 10:00 en Q1
    for r in rows:
        if r.get("period") == 1 and (r.get("clock_seconds") == 600 or r.get("clock_str") == "10:00"):
            if r["action"] == "SUB_IN" and r.get("team") and r.get("player"):
                starters_seen_in_Q1_at_10[r["team"]].add(r["player"])

    for r in rows:
        team = r.get("team") or ""  # permite vacío si no se pudo parsear
        player = r.get("player") or ""
        if not player:
            # si no hay jugador, no podemos computar intervalos; saltamos
            continue

        key = (team, player)

        # Abrir titulares de un equipo al primer evento con reloj < 10:00 en Q1
        if (team and not starters_opened[team]) and r.get("period") == 1 and (r.get("clock_seconds") is not None) and r["clock_seconds"] < 600:
            for p in starters_seen_in_Q1_at_10[team]:
                k = (team, p)
                if k not in open_in:
                    open_in[k] = {"t": 0.0, "period": 1, "clock": "10:00"}
            starters_opened[team] = True

        if r["action"] == "SUB_IN":
            if key in open_in:
                info = open_in.pop(key)
                intervals[key].append((
                    info["t"], r["elapsed"],
                    {"period_in": info["period"], "clock_in": info["clock"],
                     "period_out": r["period"], "clock_out": r["clock_str"],
                     "motivo_cierre": "SUB_IN_sin_sale_previo (autocierre)"}
                ))
            open_in[key] = {"t": r["elapsed"], "period": r["period"], "clock": r["clock_str"]}

        elif r["action"] == "SUB_OUT":
            if key in open_in:
                info = open_in.pop(key)
                intervals[key].append((
                    info["t"], r["elapsed"],
                    {"period_in": info["period"], "clock_in": info["clock"],
                     "period_out": r["period"], "clock_out": r["clock_str"],
                     "motivo_cierre": "SUB_OUT"}
                ))
            else:
                # INFERENCIA SOLO titulares Q1 (antes de abrir titulares)
                if team and (not starters_opened[team]):
                    intervals[key].append((
                        0.0, r["elapsed"],
                        {"period_in": 1, "clock_in": "10:00",
                         "period_out": r["period"], "clock_out": r["clock_str"],
                         "motivo_cierre": "INFERIDO_TITULAR"}
                    ))
                else:
                    # fuera de Q1 no inferimos
                    pass

    # Cierra al final del partido lo que siga abierto
    tend = game_end_absolute(rows, cfg)
    for key, info in list(open_in.items()):
        intervals[key].append((
            info["t"], tend,
            {"period_in": info["period"], "clock_in": info["clock"],
             "period_out": None, "clock_out": "FIN", "motivo_cierre": "FIN_PARTIDO"}
        ))
        open_in.pop(key, None)

    return intervals

def debug_print_player_trace(rows: List[Dict], intervals: Dict[Tuple[str,str], List[Tuple[float,float,Dict]]], pick: Optional[Tuple[str,str]]=None):
    keys = [k for k, v in intervals.items() if v]
    if not keys:
        print("[DEBUG] No hay intervalos para ningún jugador.")
        return
    if pick is None:
        pick = random.choice(keys)
    team, player = pick
    print(f"\n=== DEBUG JUGADOR ===\nJugador: {player} · Equipo: {team or '(sin equipo)'}")

    evs = [r for r in rows if r.get("player")==player and r.get("action") in ("SUB_IN","SUB_OUT")]
    if not evs:
        print("No hay eventos de sustitución para este jugador.")
    else:
        print("\nEventos de sustitución (orden cronológico):")
        for r in evs:
            print(f"  [P{r['period']} {r['clock_str']}] {r['action']} (t={r['elapsed']:.1f}s) · texto='{r['raw'][:120]}...'")

    print("\nIntervalos entra→sale construidos:")
    total = 0.0
    for (tin, tout, meta) in intervals[(team,player)]:
        dur = max(0.0, tout - tin)
        total += dur
        pin, pout = meta.get("period_in"), meta.get("period_out")
        cin, cout = meta.get("clock_in"), meta.get("clock_out")
        motivo = meta.get("motivo_cierre")
        print(f"  [P{pin} {cin}]  →  [P{pout if pout is not None else '-'} {cout}]   Δ={seconds_to_mmss(dur)}   ({dur:.1f}s)  · {motivo}")

    print(f"\nTOTAL en pista: {seconds_to_mmss(total)} ({total:.1f}s)\n")

# ----------------------------
# MAIN
# ----------------------------
def run_scrape_and_parse(partido_id: str, dump: Optional[str]=None) -> pd.DataFrame:
    cfg = GameConfig()
    SNAP_PATH = f"./data/pbp_snapshot_{partido_id}.html"
    SNAP_ROWS = f"./data/pbp_snapshot_{partido_id}__rows.html"

    driver = init_driver()
    driver.get(BASE_PLAY_URL.format(partido_id))
    accept_cookies(driver)
    # quita overlays si existen
    driver.execute_script("const o = document.querySelector('.stpd_cmp_wrapper'); if (o) o.remove();")

    ensure_keyfacts_tab(driver)
    check_all_quarters(driver)
    WebDriverWait(driver, 12).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"{WIDGET_SEL} [data-cuarto]"))
    )
    final_count = wait_widget_stable(driver, min_rows=10, stable_cycles=3, poll=0.6, timeout=25.0)
    print(f"[INFO] Filas detectadas tras estabilizar: {final_count}")

    html = take_widget_snapshot(driver, SNAP_PATH)
    print(f"[INFO] Snapshot guardado en: {SNAP_PATH}")

    rows = parse_snapshot_to_rows(html, cfg, debug_dump=dump)
    print(f"[DEBUG] Total filas parseadas (widget, con elapsed): {len(rows)}")

    if len(rows) == 0:
        html_rows = take_rows_snapshot(driver, SNAP_ROWS)
        print(f"[INFO] Snapshot por filas guardado en: {SNAP_ROWS}")
        rows = parse_snapshot_to_rows(html_rows, cfg, debug_dump=dump)
        print(f"[DEBUG] Total filas parseadas (fallback filas, con elapsed): {len(rows)}")

    driver.quit()

    if not rows:
        print("[WARN] No se pudieron parsear filas ni con widget ni con fallback.")
        return pd.DataFrame()

    intervals = build_player_intervals(rows, cfg)
    print(f"[DEBUG] Total jugadores con intervalos: {len(intervals)}")
    debug_print_player_trace(rows, intervals)

    # Agregado
    records = []
    for (team, player), segs in intervals.items():
        if not player:
            continue
        sec_total = sum(max(0.0, tout - tin) for tin, tout, _ in segs)
        records.append({
            "EQUIPO": team or "",
            "JUGADOR": player,
            "SEC_TOTALES": round(sec_total, 1),
            "MIN_TOTALES": round(sec_total/60.0, 2),
            "MIN_MANUALES": seconds_to_mmss(sec_total),
        })

    df = pd.DataFrame(records).sort_values(["EQUIPO","SEC_TOTALES"], ascending=[True, False])
    return df

def run_parse_snapshot_only(snapshot_path: str, dump: Optional[str]=None) -> pd.DataFrame:
    cfg = GameConfig()
    if not os.path.exists(snapshot_path):
        raise FileNotFoundError(snapshot_path)
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html = f.read()
    rows = parse_snapshot_to_rows(html, cfg, debug_dump=dump)
    if not rows:
        print("[WARN] Snapshot parseado pero 0 filas con tiempo (elapsed).")
        return pd.DataFrame()
    intervals = build_player_intervals(rows, cfg)
    records = []
    for (team, player), segs in intervals.items():
        if not player:
            continue
        sec_total = sum(max(0.0, tout - tin) for tin, tout, _ in segs)
        records.append({
            "EQUIPO": team or "",
            "JUGADOR": player,
            "SEC_TOTALES": round(sec_total, 1),
            "MIN_TOTALES": round(sec_total/60.0, 2),
            "MIN_MANUALES": seconds_to_mmss(sec_total),
        })
    return pd.DataFrame(records).sort_values(["EQUIPO","SEC_TOTALES"], ascending=[True, False])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partido", default=os.environ.get("PARTIDO_ID", "").strip() or "2413778")
    parser.add_argument("--snapshot", default="", help="Parsear solo un HTML snapshot ya guardado")
    parser.add_argument("--out", default="./game_minutes_from_subs.xlsx")
    parser.add_argument("--dump", default="", help="CSV de eventos crudos para debug")
    args = parser.parse_args()

    if args.snapshot:
        df = run_parse_snapshot_only(args.snapshot, dump=args.dump or None)
    else:
        df = run_scrape_and_parse(args.partido, dump=args.dump or None)

    if df.empty:
        print("[WARN] No hay datos para exportar.")
        return

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    df.to_excel(args.out, index=False)
    print(f"[OK] Guardado {args.out} · {len(df)} jugadores")

if __name__ == "__main__":
    main()
