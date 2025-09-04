# -*- coding: utf-8 -*-
"""
Clutch Time · PBP ➜ Métricas por jugador (con snapshot efímero)
- Snapshot del widget (y fallback por filas), PARSEO OFFLINE y BORRADO al final.
- Reconstruye quintetos/minutos desde inicio con tus reglas (SUB_IN 10:00 + inferencia por SUB_OUT previo).
- CLUTCH: últimos 5:00 de Q4 y TODAS las prórrogas con |margen| ≤ 5 (margen evaluado ANTES de la jugada).
- Reconstruye marcador a partir de eventos anotados (2, 3, 1; mate=2).
- Métricas por jugador en clutch: MIN_CLUTCH, PTS, FGA/FGM, 3PA/3PM, FTA/FTM, eFG%, TS%, AST, TO, STL,
  REB, REB_O/REB_D (inferidos), USG%, PLUS_MINUS, NET_RTG (con posesiones del rival on-floor).
- Modo debug por jugador: --player-debug "Nombre" imprime cómo se construyen su ± y USG paso a paso.

Uso:
    python clutch_time.py --partido 2413697 --out ./clutch_report_2413697.xlsx --events ./clutch_events_2413697.csv
    python clutch_time.py --partido 2413697 --player-debug "S. RAMOS DA CONCEIÇAO"
"""

import os
import re
import time
import random
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.web_scraping import init_driver, accept_cookies

BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"
WIDGET_SEL = "div.widget-keyfacts"

# ==========================
# Config
# ==========================
@dataclass
class GameConfig:
    q_secs: int = 10 * 60
    ot_secs: int = 5 * 60
    clutch_margin: int = 5
    clutch_last_secs: int = 5 * 60  # 5:00

def period_len(period: int, cfg: GameConfig) -> int:
    return cfg.ot_secs if period >= 5 else cfg.q_secs

def absolute_elapsed_seconds(period: Optional[int], clock_seconds: Optional[int], cfg: GameConfig) -> Optional[float]:
    if period is None or clock_seconds is None:
        return None
    elapsed = 0
    for p in range(1, period):
        elapsed += period_len(p, cfg)
    elapsed += (period_len(period, cfg) - clock_seconds)
    return float(elapsed)

def parse_clock_to_seconds_anywhere(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'(\d{1,2}):([0-5]\d)', text)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))

def first_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r'(\d+)', s)
    return int(m.group(1)) if m else None

def seconds_to_mmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s//60:02d}:{s%60:02d}"

# ==========================
# Regex (FEB ES)
# ==========================
RE_SCORE = re.compile(r'(\d+)\s*[-:]\s*(\d+)')
RE_AST   = re.compile(r'\bAsistenc', re.IGNORECASE)
RE_TO    = re.compile(r'P[eé]rdid', re.IGNORECASE)
RE_STL   = re.compile(r'Robo', re.IGNORECASE)
RE_BLK   = re.compile(r'Tap[oó]n', re.IGNORECASE)
RE_REB   = re.compile(r'Rebote', re.IGNORECASE)

RE_T3_M  = re.compile(r'TIRO\s*DE\s*3\s*ANOTADO|Triple\s*.*(anot|conv)', re.IGNORECASE)
RE_T3_A  = re.compile(r'TIRO\s*DE\s*3|Triple', re.IGNORECASE)

RE_T2_M  = re.compile(r'TIRO\s*DE\s*2\s*ANOTADO|Canasta\s*de\s*2\s*.*(anot|conv)', re.IGNORECASE)
RE_T2_A  = re.compile(r'TIRO\s*DE\s*2|Canasta\s*de\s*2', re.IGNORECASE)

RE_DK_M  = re.compile(r'MATE\s*ANOTADO', re.IGNORECASE)
RE_DK_A  = re.compile(r'MATE', re.IGNORECASE)

RE_TL_M  = re.compile(r'TIRO\s*DE\s*1\s*ANOTADO', re.IGNORECASE)
RE_TL_A  = re.compile(r'TIRO\s*DE\s*1', re.IGNORECASE)

SUB_IN_RE  = re.compile(r'Sustituci[oó]n\s*\(.*Entra.*\)', re.IGNORECASE)
SUB_OUT_RE = re.compile(r'Sustituci[oó]n\s*\(.*Sale.*\)',  re.IGNORECASE)

ROW_PATTERNS = [
    re.compile(r"\((?P<team>[^)]+)\)\s*(?P<player>[^:]+):\s*(?P<detail>.+)", re.IGNORECASE),
    re.compile(r"\((?P<team>[^)]+)\)\s*(?P<player>[^-:]+)\s*[-:]\s*(?P<detail>.+)", re.IGNORECASE),
    re.compile(r"^(?P<player>[^:]{2,}?)\s*:\s*(?P<detail>.+)$", re.IGNORECASE),
]

# ==========================
# Selenium (snapshot)
# ==========================
def ensure_keyfacts_tab(driver):
    try:
        tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-tab[data-action='keyfacts']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tab)
        driver.execute_script("arguments[0].click()", tab)
    except Exception:
        pass

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

def wait_widget_stable(driver, min_rows:int=10, stable_cycles:int=3, poll:float=0.6, timeout:float=25.0) -> int:
    t0 = time.time()
    last = -1
    stable = 0
    while time.time() - t0 < timeout:
        driver.execute_script("var w=document.querySelector(arguments[0]); if(w){w.scrollTop = w.scrollHeight;}", WIDGET_SEL)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        driver.execute_script("window.scrollTo(0, 0)")
        try:
            cnt = int(driver.execute_script(
                "var w=document.querySelector(arguments[0]);"
                "return w? w.querySelectorAll('[data-cuarto]').length: 0;", WIDGET_SEL))
        except Exception:
            cnt = 0
        if cnt == last:
            stable += 1
        else:
            stable = 0
        last = cnt
        if cnt >= min_rows and stable >= stable_cycles:
            return cnt
        time.sleep(poll)
    return max(0, last)

def take_widget_snapshot(driver, path_html: str) -> None:
    widget = driver.find_element(By.CSS_SELECTOR, WIDGET_SEL)
    html = widget.get_attribute("outerHTML")
    os.makedirs(os.path.dirname(path_html) or ".", exist_ok=True)
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)

def take_rows_snapshot(driver, path_html_rows: str) -> None:
    rows_html_list = driver.execute_script("""
        const nodes = document.querySelectorAll('[data-cuarto]');
        return Array.from(nodes).map(n => n.outerHTML);
    """) or []
    html = "<div class='widget-keyfacts-snapshot'>\n" + "\n".join(rows_html_list) + "\n</div>"
    os.makedirs(os.path.dirname(path_html_rows) or ".", exist_ok=True)
    with open(path_html_rows, "w", encoding="utf-8") as f:
        f.write(html)

# ==========================
# Parseo offline
# ==========================
def classify_action(full_text: str) -> str:
    t = re.sub(r"\s+", " ", (full_text or "").replace("\xa0", " ")).strip()
    if SUB_IN_RE.search(t):   return "SUB_IN"
    if SUB_OUT_RE.search(t):  return "SUB_OUT"
    return "OTHER"

def parse_pbp_rows_from_html(html: str, cfg: GameConfig) -> List[Dict]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    nodes = soup.select("[data-cuarto]")
    rows: List[Dict] = []

    for nd in nodes:
        try:
            period = first_int(nd.get("data-cuarto"))
            full_text = " ".join(list(nd.stripped_strings))
            full_text = re.sub(r"\s+", " ", full_text)

            clock_seconds = parse_clock_to_seconds_anywhere(full_text)
            clock_str = f"{clock_seconds//60:02d}:{clock_seconds%60:02d}" if clock_seconds is not None else ""

            team = player = detail = None
            for pat in ROW_PATTERNS:
                m = pat.search(full_text)
                if m:
                    gd = m.groupdict()
                    team   = (gd.get("team") or "").strip() or None
                    player = (gd.get("player") or "").strip() or None
                    detail = (gd.get("detail") or "").strip() or None
                    break

            # marcador si aparece (no lo usamos para la lógica, solo info)
            sh = sa = None
            msc = RE_SCORE.search(full_text)
            if msc:
                sh, sa = int(msc.group(1)), int(msc.group(2))

            elapsed = absolute_elapsed_seconds(period, clock_seconds, cfg)
            if elapsed is None:
                continue

            rows.append({
                "period": period,
                "clock_str": clock_str,
                "clock_seconds": clock_seconds,
                "elapsed": elapsed,
                "team": team,
                "player": player,
                "detail": detail if detail else full_text,
                "action": classify_action(full_text),
                "raw": full_text,
                "score_home": sh, "score_away": sa,
            })
        except Exception:
            continue

    rows.sort(key=lambda r: r["elapsed"])
    return rows

# ==========================
# Intervalos on-court (minutos)
# ==========================
def build_player_intervals(rows: List[Dict], cfg: GameConfig) -> Dict[Tuple[str,str], List[Tuple[float,float,Dict]]]:
    intervals: Dict[Tuple[str,str], List[Tuple[float,float,Dict]]] = defaultdict(list)
    open_in: Dict[Tuple[str,str], Dict] = {}

    starters_seen_in_Q1_at_10: Dict[str, Set[str]] = defaultdict(set)
    starters_opened: Dict[str, bool] = defaultdict(lambda: False)

    for r in rows:
        if r["period"] == 1 and (r.get("clock_seconds") == cfg.q_secs):
            if r["action"] == "SUB_IN" and r.get("team") and r.get("player"):
                starters_seen_in_Q1_at_10[r["team"]].add(r["player"])

    for r in rows:
        team = r.get("team"); player = r.get("player"); action = r.get("action")
        if not player:
            continue
        key = (team or "", player)

        # abre titulares al primer evento con reloj < 10:00 en Q1
        if team and (not starters_opened[team]) and r["period"] == 1 and (r.get("clock_seconds") is not None) and r["clock_seconds"] < cfg.q_secs:
            for p in starters_seen_in_Q1_at_10[team]:
                k = (team, p)
                if k not in open_in:
                    open_in[k] = {"t": 0.0, "period": 1, "clock": "10:00"}
            starters_opened[team] = True

        if action == "SUB_IN":
            if key in open_in:
                info = open_in.pop(key)
                intervals[key].append((info["t"], r["elapsed"], {
                    "period_in": info["period"], "clock_in": info["clock"],
                    "period_out": r["period"], "clock_out": r["clock_str"],
                    "motivo_cierre": "SUB_IN_sin_sale_previo"
                }))
            open_in[key] = {"t": r["elapsed"], "period": r["period"], "clock": r["clock_str"]}

        elif action == "SUB_OUT":
            if key in open_in:
                info = open_in.pop(key)
                intervals[key].append((info["t"], r["elapsed"], {
                    "period_in": info["period"], "clock_in": info["clock"],
                    "period_out": r["period"], "clock_out": r["clock_str"],
                    "motivo_cierre": "SUB_OUT"
                }))
            else:
                # tu regla: SUB_OUT antes de abrir titulares => titular inferido desde 0
                if team and (not starters_opened[team]):
                    intervals[key].append((0.0, r["elapsed"], {
                        "period_in": 1, "clock_in": "10:00",
                        "period_out": r["period"], "clock_out": r["clock_str"],
                        "motivo_cierre": "INFERIDO_TITULAR"
                    }))

    # cierre a fin de partido
    if rows:
        max_p = max(r["period"] for r in rows if r.get("period") is not None)
        tend = absolute_elapsed_seconds(max_p, 0, cfg) or 0.0
    else:
        tend = 0.0

    for key, info in list(open_in.items()):
        intervals[key].append((info["t"], tend, {
            "period_in": info["period"], "clock_in": info["clock"],
            "period_out": None, "clock_out": "FIN", "motivo_cierre": "FIN_PARTIDO"
        }))
        open_in.pop(key, None)

    return intervals

# ==========================
# Utilidades clutch
# ==========================
def teams_in_game(rows: List[Dict]) -> List[str]:
    ts = []
    for r in rows:
        t = r.get("team")
        if t and t not in ts:
            ts.append(t)
        if len(ts) == 2:
            break
    return ts

def is_scoring_made(detail: str) -> Tuple[bool, int]:
    d = detail or ""
    if RE_T3_M.search(d): return True, 3
    if RE_T2_M.search(d): return True, 2
    if RE_DK_M.search(d): return True, 2
    if RE_TL_M.search(d): return True, 1
    return False, 0

def is_shot_attempt(detail: str) -> Tuple[bool, Optional[int]]:
    d = detail or ""
    if RE_T3_A.search(d): return True, 3
    if RE_T2_A.search(d): return True, 2
    if RE_DK_A.search(d): return True, 2
    if RE_TL_A.search(d): return True, 1
    return False, None

def is_missed(detail: str) -> bool:
    return bool(re.search(r'FALLAD', detail or "", re.IGNORECASE))

def is_assist(detail: str) -> bool:
    return bool(RE_AST.search(detail or ""))

def is_turnover(detail: str) -> bool:
    return bool(RE_TO.search(detail or ""))

def is_steal(detail: str) -> bool:
    return bool(RE_STL.search(detail or ""))

def is_block(detail: str) -> bool:
    return bool(RE_BLK.search(detail or ""))

def is_rebound(detail: str) -> bool:
    return bool(RE_REB.search(detail or ""))

def build_clutch_windows(rows: List[Dict], cfg: GameConfig) -> List[Tuple[float, float]]:
    if not rows:
        return []
    ts = teams_in_game(rows)
    if len(ts) != 2:
        return []
    tA, tB = ts[0], ts[1]
    score = {tA: 0, tB: 0}

    def in_last5(period: int, clock_seconds: Optional[int]) -> bool:
        if clock_seconds is None:
            return False
        return (period == 4 and clock_seconds <= cfg.clutch_last_secs) or \
               (period >= 5 and clock_seconds <= cfg.clutch_last_secs)

    segments: List[Tuple[float, bool]] = []
    prev_t = 0.0
    prev_state = False

    for r in rows:
        t = r["elapsed"]; p = r["period"]; cs = r.get("clock_seconds")
        team = r.get("team"); detail = r.get("detail") or ""

        margin = abs(score[tA] - score[tB])
        now_state = in_last5(p, cs) and (margin <= cfg.clutch_margin)

        if now_state != prev_state:
            segments.append((prev_t, prev_state))
            prev_t = t
            prev_state = now_state

        made, pts = is_scoring_made(detail)
        if made and team in score:
            score[team] += pts

    max_p = max(r["period"] for r in rows if r.get("period") is not None)
    t_end = absolute_elapsed_seconds(max_p, 0, cfg) or (rows[-1]["elapsed"])
    segments.append((prev_t, prev_state))
    segments.append((t_end, None))

    windows: List[Tuple[float,float]] = []
    for i in range(0, len(segments)-1):
        t0, st = segments[i]
        t1, _  = segments[i+1]
        if st:
            windows.append((t0, t1))
    return windows

def overlap_seconds(a: Tuple[float,float], b: Tuple[float,float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

def is_time_inside(intervals: List[Tuple[float,float,Dict]], t: float) -> bool:
    for (a,b,_) in intervals:
        if a <= t < b:
            return True
    return False

# ==========================
# Métricas clutch (NET RTG afinado, sin AST/TO)
# ==========================
def compute_clutch_metrics(rows: List[Dict],
                           intervals: Dict[Tuple[str,str], List[Tuple[float,float,Dict]]],
                           cfg: GameConfig) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Devuelve (df_players, df_events_clutch, stats_raw_dict_por_jugador)
    stats_raw_dict_por_jugador contiene contadores usados para el modo debug.
    """
    if not rows:
        return pd.DataFrame(), pd.DataFrame(), {}

    ts = teams_in_game(rows)
    if len(ts) != 2:
        print("[WARN] No se pudieron determinar 2 equipos.")
        return pd.DataFrame(), pd.DataFrame(), {}
    teamA, teamB = ts[0], ts[1]

    clutch_windows = build_clutch_windows(rows, cfg)

    # índice intervals por equipo/jugador
    team_players: Dict[str, Dict[str, List[Tuple[float,float,Dict]]]] = defaultdict(dict)
    for (team, player), ivals in intervals.items():
        team_players[team or ""].setdefault(player, ivals)

    def on_court_set(team: str, t: float) -> Set[str]:
        res = set()
        for player, ivals in team_players.get(team, {}).items():
            if is_time_inside(ivals, t):
                res.add(player)
        return res

    score = {teamA: 0, teamB: 0}
    last_miss_team: Optional[str] = None

    S: Dict[Tuple[str,str], Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # recorrido
    for r in rows:
        t = r["elapsed"]; team = r.get("team") or ""
        opp = teamB if team == teamA else teamA
        detail = r.get("detail") or ""

        # ¿está t en clutch?
        in_clutch = any(w[0] <= t < w[1] for w in clutch_windows)
        oc_team = on_court_set(team, t)
        oc_opp  = on_court_set(opp, t)

        # shot/points flags
        is_tiro, base_pts = is_shot_attempt(detail)
        made, pts = is_scoring_made(detail)

        # ---- SOLO si estamos en clutch: acumular stats y posesiones on-floor ----
        if in_clutch:
            player = r.get("player")
            key = (team, player) if player else None

            # ---- Estadística individual ----
            if is_tiro:
                if base_pts == 3:
                    if key: S[key]["3PA"] += 1
                    if made and key: S[key]["3PM"] += 1
                elif base_pts == 2:
                    if key: S[key]["FGA2"] += 1
                    if made and key: S[key]["FGM2"] += 1
                elif base_pts == 1:
                    if key: S[key]["FTA"] += 1
                    if made and key: S[key]["FTM"] += 1

            if is_assist(detail) and key:
                S[key]["AST"] += 1
            if is_turnover(detail) and key:
                S[key]["TO"] += 1
            if is_steal(detail) and key:
                S[key]["STL"] += 1
            if is_rebound(detail) and key:
                S[key]["REB"] += 1
                if last_miss_team is not None:
                    if team == last_miss_team:
                        S[key]["REB_O"] += 1
                    else:
                        S[key]["REB_D"] += 1

            # ---- Posesiones on-floor del EQUIPO (para USG/OffRtg) ----
            if base_pts in (2,3) and is_tiro:
                for pl in oc_team:
                    S[(team, pl)]["FGA_onfloor"] += 1
            if is_rebound(detail) and (last_miss_team is not None) and team == last_miss_team:
                for pl in oc_team:
                    S[(team, pl)]["ORB_onfloor"] += 1
            if is_turnover(detail):
                for pl in oc_team:
                    S[(team, pl)]["TO_onfloor"] += 1
            if base_pts == 1:  # FTA
                for pl in oc_team:
                    S[(team, pl)]["FTA_onfloor"] += 1

            # ---- Posesiones on-floor del RIVAL (para DefRtg fino) ----
            if base_pts in (2,3) and is_tiro:
                for pl in oc_opp:
                    S[(opp, pl)]["OPP_FGA_onfloor"] += 1
            if is_rebound(detail) and (last_miss_team is not None) and team == last_miss_team:
                for pl in oc_opp:
                    S[(opp, pl)]["OPP_ORB_onfloor"] += 1
            if is_turnover(detail):
                for pl in oc_opp:
                    S[(opp, pl)]["OPP_TO_onfloor"] += 1
            if base_pts == 1:
                for pl in oc_opp:
                    S[(opp, pl)]["OPP_FTA_onfloor"] += 1

            # ---- PLUS/MINUS por evento anotado ----
            if made and team in score:
                for pl in oc_team:
                    S[(team, pl)]["PLUS_MINUS"] += pts
                    S[(team, pl)]["POINTS_FOR"] += pts
                for pl in oc_opp:
                    S[(opp, pl)]["PLUS_MINUS"] -= pts
                    S[(opp, pl)]["POINTS_AGAINST"] += pts

        # actualizar cronología para margen e inferencias, SIEMPRE
        if is_tiro and is_missed(detail):
            last_miss_team = team
        elif is_rebound(detail):
            last_miss_team = None

        if made and team in score:
            score[team] += pts

    # ---- MINUTOS CLUTCH (overlaps de on-court vs ventanas clutch) ----
    def overlap_total(ivals: List[Tuple[float,float,Dict]], wins: List[Tuple[float,float]]) -> float:
        tot = 0.0
        for (tin, tout, _meta) in ivals:
            for w in wins:
                tot += overlap_seconds((tin, tout), w)
        return tot

    for (team, player), ivals in intervals.items():
        sec = overlap_total(ivals, clutch_windows)
        if sec > 0:
            S[(team, player)]["SEC_CLUTCH"] += sec

    # ---- Consolidar métricas ----
    records = []
    raw_per_player: Dict[Tuple[str,str], Dict[str, float]] = {}

    for (team, player), d in S.items():
        if not player:
            continue

        sec = d.get("SEC_CLUTCH", 0.0)
        if sec <= 0:
            continue

        FGA2 = d.get("FGA2", 0.0); FGM2 = d.get("FGM2", 0.0)
        PA3  = d.get("3PA", 0.0);  PM3  = d.get("3PM", 0.0)
        FGA  = FGA2 + PA3
        FGM  = FGM2 + PM3
        FTA  = d.get("FTA", 0.0);  FTM  = d.get("FTM", 0.0)
        PTS  = d.get("PTS", 0.0)

        efg = (FGM + 0.5*PM3) / FGA if FGA > 0 else float('nan')
        ts  = PTS / (2.0 * (FGA + 0.44*FTA)) if (FGA + 0.44*FTA) > 0 else float('nan')

        AST = d.get("AST", 0.0)
        TO  = d.get("TO", 0.0)
        STL = d.get("STL", 0.0)
        REB = d.get("REB", 0.0); REB_O = d.get("REB_O", 0.0); REB_D = d.get("REB_D", 0.0)

        # USG%
        FGA_on = d.get("FGA_onfloor", 0.0)
        FTA_on = d.get("FTA_onfloor", 0.0)
        ORB_on = d.get("ORB_onfloor", 0.0)
        TO_on  = d.get("TO_onfloor", 0.0)
        poss_team_on = (FGA_on - ORB_on + TO_on + 0.44*FTA_on)
        usg = 100.0 * (FGA + 0.44*FTA + TO) / poss_team_on if poss_team_on > 0 else float('nan')

        # NetRtg (fino)
        pm = d.get("PLUS_MINUS", 0.0)
        pts_for     = d.get("POINTS_FOR", 0.0)
        pts_against = d.get("POINTS_AGAINST", 0.0)

        OPP_FGA_on = d.get("OPP_FGA_onfloor", 0.0)
        OPP_ORB_on = d.get("OPP_ORB_onfloor", 0.0)
        OPP_TO_on  = d.get("OPP_TO_onfloor", 0.0)
        OPP_FTA_on = d.get("OPP_FTA_onfloor", 0.0)
        poss_opp_on = (OPP_FGA_on - OPP_ORB_on + OPP_TO_on + 0.44 * OPP_FTA_on)

        off_rtg = 100.0 * (pts_for / poss_team_on) if poss_team_on > 0 else float('nan')
        def_rtg = 100.0 * (pts_against / poss_opp_on) if poss_opp_on > 0 else float('nan')
        net_rtg = (off_rtg - def_rtg) if not (pd.isna(off_rtg) or pd.isna(def_rtg)) else float('nan')

        # guardar crudos para modo debug
        raw_per_player[(team, player)] = {
            "FGA":FGA,"FGM":FGM,"3PA":PA3,"3PM":PM3,"FTA":FTA,"FTM":FTM,"PTS":PTS,
            "AST":AST,"TO":TO,"STL":STL,"REB":REB,"REB_O":REB_O,"REB_D":REB_D,
            "FGA_on":FGA_on,"FTA_on":FTA_on,"ORB_on":ORB_on,"TO_on":TO_on,"poss_team_on":poss_team_on,
            "OPP_FGA_on":OPP_FGA_on,"OPP_ORB_on":OPP_ORB_on,"OPP_TO_on":OPP_TO_on,"OPP_FTA_on":OPP_FTA_on,
            "poss_opp_on":poss_opp_on,"POINTS_FOR":pts_for,"POINTS_AGAINST":pts_against,
            "PLUS_MINUS":pm,"OFF_RTG":off_rtg,"DEF_RTG":def_rtg,"NET_RTG":net_rtg,"SEC_CLUTCH":sec
        }

        records.append({
            "EQUIPO": team,
            "JUGADOR": player,
            "MIN_CLUTCH": round(sec/60.0, 2),
            "PTS": int(PTS),
            "FGA": int(FGA), "FGM": int(FGM),
            "3PA": int(PA3), "3PM": int(PM3),
            "FTA": int(FTA), "FTM": int(FTM),
            "eFG%": round(efg, 3) if not pd.isna(efg) else float('nan'),
            "TS%": round(ts, 3) if not pd.isna(ts) else float('nan'),
            "AST": int(AST), "TO": int(TO),
            "STL": int(STL),
            "REB": int(REB), "REB_O": int(REB_O), "REB_D": int(REB_D),
            "USG%": round(usg, 2) if not pd.isna(usg) else float('nan'),
            "PLUS_MINUS": int(pm),
            "NET_RTG": round(net_rtg, 2) if not pd.isna(net_rtg) else float('nan'),
        })

    df_players = pd.DataFrame(records).sort_values(["EQUIPO","MIN_CLUTCH","PTS"], ascending=[True, False, False])

    # Eventos clutch para auditoría
    clutch_windows = build_clutch_windows(rows, cfg)
    ev_records = []
    for r in rows:
        t = r["elapsed"]
        if any(w[0] <= t < w[1] for w in clutch_windows):
            ev_records.append({
                "t": round(t, 2),
                "P": r.get("period"),
                "Reloj": r.get("clock_str"),
                "Equipo": r.get("team"),
                "Jugador": r.get("player"),
                "Detalle": r.get("detail"),
            })
    df_events = pd.DataFrame(ev_records).sort_values(["t"])

    return df_players, df_events, raw_per_player

# ==========================
# Debug: construir ± y USG para un jugador
# ==========================
def debug_player_clutch_pm_usg(player_query: str,
                               rows: List[Dict],
                               intervals: Dict[Tuple[str,str], List[Tuple[float,float,Dict]]],
                               cfg: GameConfig):
    """
    Imprime paso a paso cómo se construyen PLUS/MINUS y USG del jugador (clutch).
    Busca por substring case-insensitive en el nombre del jugador.
    """
    # localizar (team, player)
    cands = []
    names = set()
    for (team, player), ivals in intervals.items():
        if player and player_query.lower() in player.lower():
            cands.append((team, player))
            names.add(player)
    if not cands:
        print(f"[DEBUG] No se encontró jugador que contenga: {player_query}")
        return
    team, player = cands[0]
    ivals = intervals[(team, player)]

    # ventanas clutch
    windows = build_clutch_windows(rows, cfg)

    # helper on-floor
    def onfloor(t: float) -> bool:
        return is_time_inside(ivals, t) and any(w[0] <= t < w[1] for w in windows)

    # reconstrucción sets on-floor por equipo (para eventos)
    # construimos un índice simple tiempo→onfloor para el equipo del jugador y rival
    teams = teams_in_game(rows)
    if len(teams) != 2:
        print("[DEBUG] No hay 2 equipos.")
        return
    teamA, teamB = teams[0], teams[1]
    opp = teamB if team == teamA else teamA

    # indice on-floor por instante (muestreo en eventos)
    def oc_set(team_name: str, t: float) -> Set[str]:
        # buscamos intervals del team_name
        res = set()
        for (t0, p), ivs in [((k[0], k[1]), v) for k, v in intervals.items() if k[0] == team_name]:
            if is_time_inside(ivs, t):
                res.add(p)
        return res

    # acumuladores
    pm = 0
    pts_for = 0
    pts_against = 0
    # USG: numerador y denominador
    num_fga = 0; num_fta = 0; num_to = 0
    den_fga_on = 0; den_fta_on = 0; den_orb_on = 0; den_to_on = 0

    print(f"\n=== DEBUG CLUTCH · {player} ({team}) ===")
    print("Evento-by-evento dentro de clutch (solo si el jugador está on-floor):")
    print("t(s) | P reloj | Equipo | ¿On? | Δ± | Detalle")

    # para ORB inferido
    last_miss_team = None
    # reconstruimos marcador para margen (ya lo usa build_clutch_windows)
    # aquí no lo reusamos, solo mostramos PM/USG

    for r in rows:
        t = r["elapsed"]; d = r.get("detail") or ""; eq = r.get("team") or ""
        p = r.get("period"); clk = r.get("clock_str") or ""
        in_clutch = any(w[0] <= t < w[1] for w in windows)
        if not in_clutch:
            # mantener inferencia de ORB
            if is_shot_attempt(d)[0] and is_missed(d): last_miss_team = eq
            elif is_rebound(d): last_miss_team = None
            continue

        # ¿está el jugador en pista ahora?
        player_on = onfloor(t)

        # PLUS/MINUS delta
        delta_pm = 0
        made, pts = is_scoring_made(d)
        if made and player_on:
            if eq == team:
                delta_pm = +pts
                pm += pts; pts_for += pts
            elif eq == opp:
                delta_pm = -pts
                pm -= pts; pts_against += pts

        # USG (numerador) solo si el evento es suyo (jugador = actor)
        is_t, base = is_shot_attempt(d)
        if player_on and r.get("player") == player:
            if is_t and base in (2,3): num_fga += 1
            if base == 1: num_fta += 1
            if is_turnover(d): num_to += 1

        # USG (denominador) componentes del equipo mientras él está en pista
        if player_on and eq == team:
            if is_t and base in (2,3): den_fga_on += 1
            if is_rebound(d) and (last_miss_team is not None) and eq == last_miss_team:
                den_orb_on += 1
            if is_turnover(d): den_to_on += 1
            if base == 1: den_fta_on += 1

        # mantener inferencia ORB
        if is_t and is_missed(d): last_miss_team = eq
        elif is_rebound(d): last_miss_team = None

        if player_on and (made or is_t or is_turnover(d)):
            print(f"{t:6.1f} | P{p} {clk:>5} | {eq[:16]:<16} | {'Sí ':<3} | {delta_pm:+2d} | {d}")
        elif made:
            # anotación pero jugador off
            pass

    # finales
    poss_team_on = den_fga_on - den_orb_on + den_to_on + 0.44*den_fta_on
    usg = 100.0 * (num_fga + 0.44*num_fta + num_to) / poss_team_on if poss_team_on > 0 else float('nan')

    print("\n--- RESUMEN ± ---")
    print(f"PLUS/MINUS = +{pts_for} (a favor)  −{pts_against} (en contra)  = {pm:+d}")

    print("\n--- RESUMEN USG% ---")
    print(f"Numerador (FGA + 0.44*FTA + TO) = {num_fga} + 0.44*{num_fta} + {num_to} = {num_fga + 0.44*num_fta + num_to:.2f}")
    print(f"Denominador (FGA_on - ORB_on + TO_on + 0.44*FTA_on) = {den_fga_on} - {den_orb_on} + {den_to_on} + 0.44*{den_fta_on} = {poss_team_on:.2f}")
    print(f"USG% = 100 * Numerador / Denominador = {usg:.2f}%\n")

# ==========================
# Pipeline
# ==========================
def run_pipeline(partido_id: str,
                 out_xlsx: str,
                 out_events_csv: Optional[str],
                 keep_snapshot: bool,
                 retries: int = 2,
                 player_debug: Optional[str] = None):
    cfg = GameConfig()
    SNAP_PATH = f"./data/pbp_snapshot_{partido_id}.html"
    SNAP_ROWS = f"./data/pbp_snapshot_{partido_id}__rows.html"
    made_snapshots = []

    try:
        # SCRAPE + SNAPSHOT (con reintentos)
        attempt = 0
        rows = []
        while attempt <= retries and not rows:
            attempt += 1
            print(f"[INFO] Intento {attempt}/{retries+1} para scrapear {partido_id}")
            driver = init_driver()
            driver.get(BASE_PLAY_URL.format(partido_id))
            accept_cookies(driver)
            driver.execute_script("const o = document.querySelector('.stpd_cmp_wrapper'); if (o) o.remove();")

            ensure_keyfacts_tab(driver)
            check_all_quarters(driver)
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{WIDGET_SEL} [data-cuarto]"))
            )
            final_count = wait_widget_stable(driver, min_rows=10, stable_cycles=3, poll=0.6, timeout=25.0)
            print(f"[INFO] Filas detectadas tras estabilizar: {final_count}")

            # Snapshot principal
            take_widget_snapshot(driver, SNAP_PATH)
            made_snapshots.append(SNAP_PATH)

            # Parseo desde snapshot
            with open(SNAP_PATH, "r", encoding="utf-8") as f:
                html = f.read()
            rows = parse_pbp_rows_from_html(html, cfg)
            print(f"[DEBUG] Filas parseadas desde widget: {len(rows)}")

            # Fallback por filas si 0
            if len(rows) == 0:
                take_rows_snapshot(driver, SNAP_ROWS)
                made_snapshots.append(SNAP_ROWS)
                with open(SNAP_ROWS, "r", encoding="utf-8") as f:
                    html_rows = f.read()
                rows = parse_pbp_rows_from_html(html_rows, cfg)
                print(f"[DEBUG] Filas parseadas desde fallback filas: {len(rows)}")

            driver.quit()

            if not rows:
                print("[WARN] 0 filas tras parseo. Reintentando...")

        if not rows:
            print("[ERROR] No se pudieron obtener filas del PBP tras los reintentos.")
            return

        # INTERVALOS
        intervals = build_player_intervals(rows, cfg)
        print(f"[DEBUG] Total jugadores con intervalos: {len(intervals)}")

        # METRICAS
        df_players, df_events, raw_per_player = compute_clutch_metrics(rows, intervals, cfg)

        if df_players.empty:
            print("[WARN] No hay jugadores con minutos en clutch.")
        else:
            os.makedirs(os.path.dirname(out_xlsx) or ".", exist_ok=True)
            df_players.to_excel(out_xlsx, index=False)
            print(f"[OK] Guardado reporte: {out_xlsx} · {len(df_players)} jugadores")

        if out_events_csv:
            os.makedirs(os.path.dirname(out_events_csv) or ".", exist_ok=True)
            df_events.to_csv(out_events_csv, index=False, encoding="utf-8")
            print(f"[OK] Guardado eventos clutch: {out_events_csv} · {len(df_events)} filas")

        # DEBUG por jugador
        if player_debug:
            debug_player_clutch_pm_usg(player_debug, rows, intervals, cfg)

    finally:
        if keep_snapshot:
            print("[INFO] Conservando snapshots por --keep-snapshot")
        else:
            for p in [SNAP_PATH, SNAP_ROWS]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception as e:
                    print(f"[WARN] No se pudo eliminar snapshot {p}: {e}")

# ==========================
# CLI
# ==========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partido", default=os.environ.get("PARTIDO_ID", "").strip() or "2413778")
    parser.add_argument("--out", default="./clutch_report.xlsx", help="Excel métricas por jugador en clutch")
    parser.add_argument("--events", default="", help="CSV opcional con eventos clutch (auditoría)")
    parser.add_argument("--keep-snapshot", action="store_true", help="No borrar snapshots al terminar")
    parser.add_argument("--retries", type=int, default=2, help="Reintentos de scrapeo si 0 filas")
    parser.add_argument("--player-debug", default="", help="Nombre (o substring) de jugador para ver cómo se construye su ± y USG")
    args = parser.parse_args()

    out_events_csv = args.events if args.events else None
    player_debug = args.player_debug if args.player_debug else None

    run_pipeline(args.partido, args.out, out_events_csv, args.keep_snapshot, retries=args.retries, player_debug=player_debug)

# --- API para ejecutar por partido SIN escribir archivos ---
def clutch_for_game(partido_id: str, retries: int = 2, keep_snapshot: bool = False) -> pd.DataFrame:
    """
    Ejecuta el pipeline de clutch para un partido y devuelve el DataFrame de métricas por jugador.
    No escribe Excel/CSV y elimina los snapshots al terminar (salvo keep_snapshot=True).
    """
    cfg = GameConfig()
    SNAP_PATH = f"./data/pbp_snapshot_{partido_id}.html"
    SNAP_ROWS = f"./data/pbp_snapshot_{partido_id}__rows.html"

    made_snapshots = []
    df_players_final = pd.DataFrame()

    try:
        # SCRAPE + SNAPSHOT (con reintentos)
        attempt = 0
        rows = []
        while attempt <= retries and not rows:
            attempt += 1
            print(f"[INFO] (clutch_for_game) intento {attempt}/{retries+1} · partido {partido_id}")
            driver = init_driver()
            driver.get(BASE_PLAY_URL.format(partido_id))
            accept_cookies(driver)
            driver.execute_script("const o = document.querySelector('.stpd_cmp_wrapper'); if (o) o.remove();")

            ensure_keyfacts_tab(driver)
            check_all_quarters(driver)
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{WIDGET_SEL} [data-cuarto]"))
            )
            final_count = wait_widget_stable(driver, min_rows=10, stable_cycles=3, poll=0.6, timeout=25.0)
            print(f"[INFO] Filas detectadas tras estabilizar: {final_count}")

            # Snapshot principal
            take_widget_snapshot(driver, SNAP_PATH)
            made_snapshots.append(SNAP_PATH)

            # Parseo desde snapshot
            with open(SNAP_PATH, "r", encoding="utf-8") as f:
                html = f.read()
            rows = parse_pbp_rows_from_html(html, cfg)
            print(f"[DEBUG] Filas parseadas desde widget: {len(rows)}")

            # Fallback por filas si 0
            if len(rows) == 0:
                take_rows_snapshot(driver, SNAP_ROWS)
                made_snapshots.append(SNAP_ROWS)
                with open(SNAP_ROWS, "r", encoding="utf-8") as f:
                    html_rows = f.read()
                rows = parse_pbp_rows_from_html(html_rows, cfg)
                print(f"[DEBUG] Filas parseadas desde fallback filas: {len(rows)}")

            driver.quit()

            if not rows:
                print("[WARN] 0 filas tras parseo. Reintentando...")

        if not rows:
            print(f"[ERROR] No se pudieron obtener filas del PBP ({partido_id})")
            return pd.DataFrame()

        # INTERVALOS + METRICAS
        intervals = build_player_intervals(rows, cfg)
        df_players, _df_events, _raw = compute_clutch_metrics(rows, intervals, cfg)
        df_players_final = df_players.copy()

        return df_players_final

    finally:
        if keep_snapshot:
            print("[INFO] (clutch_for_game) conservando snapshots por keep_snapshot=True")
        else:
            for p in [SNAP_PATH, SNAP_ROWS]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception as e:
                    print(f"[WARN] No se pudo eliminar snapshot {p}: {e}")


if __name__ == "__main__":
    main()
