# -*- coding: utf-8 -*-
"""
Clutch Lineups (temporada) — HARD-CODED 1 minuto mínimo
------------------------------------------------------
- Reconstruye quintetos on-floor por partido.
- Limita a CLUTCH (últimos 5:00 de Q4 y TODAS las prórrogas con |margen| ≤ 5).
- Agrega a nivel temporada por EQUIPO + QUINTETO.
- Calcula minutos, puntos a favor/en contra, posesiones (on-floor) y Off/Def/Net Rating.
- **Filtra quintetos con tiempo total clutch acumulado >= 60.0 s (1 minuto) — HARD-CODED.**
- Exporta un Excel con **una pestaña por equipo** (ordenado por NetRTG).

Uso:
    python clutch_lineups_season.py --out ./data/clutch_lineups.xlsx --workers 4 --retries 2
"""

import os
import re
import time
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import set_start_method, freeze_support

# === utils propios del proyecto ===
from utils.web_scraping import init_driver, accept_cookies
from .scraper_all_games import scrape_all  # devuelve [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]

# ==========================
# Config y helpers base
# ==========================
BASE_PLAY_URL = "https://baloncestoenvivo.feb.es/partido/{}"
WIDGET_SEL = "div.widget-keyfacts"
MIN_SEC_HARDCODED = 60.0  # *** 1 minuto mínimo acumulado de clutch por quinteto ***

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

# ==========================
# Regex (FEB ES)
# ==========================
RE_SCORE = re.compile(r'(\d+)\s*[-:]\s*(\d+)')
RE_TO    = re.compile(r'P[eé]rdid', re.IGNORECASE)
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
# Selenium snapshot
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
# Parseo snapshot ➜ rows
# ==========================
def classify_action(full_text: str) -> str:
    t = re.sub(r"\s+", " ", (full_text or "").replace("\xa0", " ")).strip()
    if SUB_IN_RE.search(t):   return "SUB_IN"
    if SUB_OUT_RE.search(t):  return "SUB_OUT"
    return "OTHER"

def parse_pbp_rows_from_html(html: str, cfg: GameConfig) -> List[Dict]:
    from bs4 import BeautifulSoup
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
                if team and (not starters_opened[team]):
                    intervals[key].append((0.0, r["elapsed"], {
                        "period_in": 1, "clock_in": "10:00",
                        "period_out": r["period"], "clock_out": r["clock_str"],
                        "motivo_cierre": "INFERIDO_TITULAR"
                    }))

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
# Clutch ventanas + utilidades
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

def is_turnover(detail: str) -> bool:
    return bool(RE_TO.search(detail or ""))

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

def on_court_set(intervals_team: Dict[str, List[Tuple[float,float,Dict]]], t: float) -> Set[str]:
    s = set()
    for player, ivals in intervals_team.items():
        for a,b,_ in ivals:
            if a <= t < b:
                s.add(player)
                break
    return s

def lineup_key(team: str, players_set: Set[str]) -> Tuple[str, Tuple[str,...]]:
    players = tuple(sorted([p for p in players_set if p]))
    return (team, players)

# ==========================
# Core: lineups por PARTIDO
# ==========================
def compute_lineups_for_game(rows: List[Dict], cfg: GameConfig) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    ts = teams_in_game(rows)
    if len(ts) != 2:
        return pd.DataFrame()
    teamA, teamB = ts

    intervals = build_player_intervals(rows, cfg)
    intervals_by_team: Dict[str, Dict[str, List[Tuple[float,float,Dict]]]] = defaultdict(dict)
    for (team, player), ivals in intervals.items():
        if team:
            intervals_by_team[team][player] = ivals

    windows = build_clutch_windows(rows, cfg)

    change_times: Set[float] = set([0.0])
    if rows:
        max_p = max(r["period"] for r in rows if r.get("period") is not None)
        t_end = absolute_elapsed_seconds(max_p, 0, cfg) or rows[-1]["elapsed"]
    else:
        t_end = 0.0
    change_times.add(t_end)

    for ivals in intervals.values():
        for a,b,_ in ivals:
            change_times.add(a); change_times.add(b)

    cps = sorted(change_times)

    L: Dict[Tuple[str,Tuple[str,...]], Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # 1) Duración por lineup (clutch)
    for i in range(len(cps)-1):
        a, b = cps[i], cps[i+1]
        for w in windows:
            s = max(a, w[0]); e = min(b, w[1])
            if e <= s:
                continue
            mid = s + 1e-6
            ocA = on_court_set(intervals_by_team[teamA], mid)
            ocB = on_court_set(intervals_by_team[teamB], mid)
            kA = lineup_key(teamA, ocA)
            kB = lineup_key(teamB, ocB)
            L[kA]["SEC_CLUTCH"] += (e - s)
            L[kB]["SEC_CLUTCH"] += (e - s)

    # 2) Eventos (posesiones y puntos) por lineup
    last_miss_team: Optional[str] = None
    for r in rows:
        t = r["elapsed"]; team = r.get("team") or ""
        opp = teamB if team == teamA else teamA
        detail = r.get("detail") or ""

        if not any(w[0] <= t < w[1] for w in windows):
            if is_shot_attempt(detail)[0] and is_missed(detail): last_miss_team = team
            elif is_rebound(detail): last_miss_team = None
            continue

        ocA = on_court_set(intervals_by_team[teamA], t + 1e-6)
        ocB = on_court_set(intervals_by_team[teamB], t + 1e-6)
        kA = lineup_key(teamA, ocA)
        kB = lineup_key(teamB, ocB)

        is_t = bool(RE_T3_A.search(detail) or RE_T2_A.search(detail) or RE_DK_A.search(detail) or RE_TL_A.search(detail))
        base = 3 if RE_T3_A.search(detail) else (2 if (RE_T2_A.search(detail) or RE_DK_A.search(detail)) else (1 if RE_TL_A.search(detail) else None))
        made = bool(RE_T3_M.search(detail) or RE_T2_M.search(detail) or RE_DK_M.search(detail) or RE_TL_M.search(detail))
        pts = 3 if RE_T3_M.search(detail) else (2 if (RE_T2_M.search(detail) or RE_DK_M.search(detail)) else (1 if RE_TL_M.search(detail) else 0))

        k_off = kA if team == teamA else kB
        k_def = kB if team == teamA else kA

        if is_t and base in (2,3):
            L[k_off]["FGA_on"] += 1
        if base == 1:
            L[k_off]["FTA_on"] += 1
        if RE_TO.search(detail or ""):
            L[k_off]["TO_on"] += 1
        if RE_REB.search(detail or "") and (last_miss_team is not None) and (team == last_miss_team):
            L[k_off]["ORB_on"] += 1

        if is_t and base in (2,3):
            L[k_def]["OPP_FGA_on"] += 1
        if base == 1:
            L[k_def]["OPP_FTA_on"] += 1
        if RE_TO.search(detail or ""):
            L[k_def]["OPP_TO_on"] += 1
        if RE_REB.search(detail or "") and (last_miss_team is not None) and (team == last_miss_team):
            L[k_def]["OPP_ORB_on"] += 1

        if made:
            L[k_off]["POINTS_FOR"] += pts
            L[k_def]["POINTS_AGAINST"] += pts

        if is_t and is_missed(detail):
            last_miss_team = team
        elif RE_REB.search(detail or ""):
            last_miss_team = None

    recs = []
    for (team, players), d in L.items():
        sec = d.get("SEC_CLUTCH", 0.0)
        if sec <= 0:
            continue

        pts_for = d.get("POINTS_FOR", 0.0)
        pts_against = d.get("POINTS_AGAINST", 0.0)

        FGA = d.get("FGA_on", 0.0); FTA = d.get("FTA_on", 0.0)
        ORB = d.get("ORB_on", 0.0); TO  = d.get("TO_on", 0.0)
        OPP_FGA = d.get("OPP_FGA_on", 0.0); OPP_FTA = d.get("OPP_FTA_on", 0.0)
        OPP_ORB = d.get("OPP_ORB_on", 0.0); OPP_TO  = d.get("OPP_TO_on", 0.0)

        off_poss = (FGA - ORB + TO + 0.44*FTA)
        def_poss = (OPP_FGA - OPP_ORB + OPP_TO + 0.44*OPP_FTA)

        off_rtg = 100.0 * (pts_for / off_poss) if off_poss > 0 else float('nan')
        def_rtg = 100.0 * (pts_against / def_poss) if def_poss > 0 else float('nan')
        net_rtg = off_rtg - def_rtg if not (pd.isna(off_rtg) or pd.isna(def_rtg)) else float('nan')

        lineup_str = " | ".join(players) if players else "(incompleto)"

        recs.append({
            "EQUIPO": team,
            "LINEUP": lineup_str,
            "N_JUG": len(players),
            "SEC_CLUTCH": round(sec, 2),
            "MIN_CLUTCH": round(sec/60.0, 2),
            "POINTS_FOR": int(pts_for),
            "POINTS_AGAINST": int(pts_against),
            "OFF_POSSESSIONS": round(off_poss, 2),
            "DEF_POSSESSIONS": round(def_poss, 2),
            "OFF_RTG": round(off_rtg, 2) if not pd.isna(off_rtg) else float('nan'),
            "DEF_RTG": round(def_rtg, 2) if not pd.isna(def_rtg) else float('nan'),
            "NET_RTG": round(net_rtg, 2) if not pd.isna(net_rtg) else float('nan'),
            # contadores auditables:
            "FGA_on": int(FGA), "FTA_on": int(FTA), "TO_on": int(TO), "ORB_on": int(ORB),
            "OPP_FGA_on": int(OPP_FGA), "OPP_FTA_on": int(OPP_FTA), "OPP_TO_on": int(OPP_TO), "OPP_ORB_on": int(OPP_ORB),
        })

    df = pd.DataFrame(recs)
    df = df.sort_values(["EQUIPO","N_JUG","MIN_CLUTCH"], ascending=[True, False, False])
    return df

# ==========================
# Scrape partido ➜ lineups
# ==========================
def lineups_for_game(partido_id: str, retries: int = 2, keep_snapshot: bool = False) -> pd.DataFrame:
    cfg = GameConfig()
    SNAP_PATH = f"./data/pbp_snapshot_{partido_id}.html"
    SNAP_ROWS = f"./data/pbp_snapshot_{partido_id}__rows.html"

    try:
        attempt = 0
        rows: List[Dict] = []
        while attempt <= retries and not rows:
            attempt += 1
            driver = init_driver()
            driver.get(BASE_PLAY_URL.format(partido_id))
            accept_cookies(driver)
            driver.execute_script("const o = document.querySelector('.stpd_cmp_wrapper'); if (o) o.remove();")
            ensure_keyfacts_tab(driver)
            check_all_quarters(driver)
            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"{WIDGET_SEL} [data-cuarto]")))
            wait_widget_stable(driver, min_rows=10, stable_cycles=3, poll=0.6, timeout=25.0)

            take_widget_snapshot(driver, SNAP_PATH)
            with open(SNAP_PATH, "r", encoding="utf-8") as f:
                html = f.read()
            rows = parse_pbp_rows_from_html(html, cfg)

            if len(rows) == 0:
                take_rows_snapshot(driver, SNAP_ROWS)
                with open(SNAP_ROWS, "r", encoding="utf-8") as f:
                    html_rows = f.read()
                rows = parse_pbp_rows_from_html(html_rows, cfg)

            driver.quit()
            if not rows and attempt <= retries:
                time.sleep(0.8)

        if not rows:
            print(f"[ERROR] {partido_id}: 0 filas PBP")
            return pd.DataFrame()

        df_lineups = compute_lineups_for_game(rows, cfg)
        if df_lineups.empty:
            print(f"[WARN] {partido_id}: sin lineups en clutch")
            return pd.DataFrame()
        df_lineups.insert(0, "PARTIDO_ID", partido_id)
        return df_lineups

    finally:
        # snapshots efímeros (se eliminan siempre)
        for p in [SNAP_PATH, SNAP_ROWS]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception as e:
                print(f"[WARN] No se pudo eliminar snapshot {p}: {e}")

# ==========================
# Temporada (paralelo) ➜ Excel
# ==========================
def aggregate_season_lineups(workers: int, retries: int, out_xlsx: str):
    games = scrape_all()  # [Fase, Jornada, IdPartido, IdEquipo, Local, Rival, Resultado]
    unique_by_pid = {}
    for fase, jornada, pid, idequipo, local, rival, resultado in games:
        if pid not in unique_by_pid:
            unique_by_pid[pid] = (fase, jornada, pid, idequipo, local, rival, resultado)
    metas = list(unique_by_pid.values())

    all_game_dfs: List[pd.DataFrame] = []
    with ProcessPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(lineups_for_game, meta[2], retries, False): meta[2] for meta in metas}
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    all_game_dfs.append(df)
                    print(f"[OK] {pid}: {len(df)} lineups")
                else:
                    print(f"[INFO] {pid}: sin datos")
            except Exception as e:
                print(f"[ERR] {pid}: {e!r}")

    if not all_game_dfs:
        print("[ERROR] No se obtuvieron lineups de ningún partido.")
        return

    df_all = pd.concat(all_game_dfs, ignore_index=True)

    grp_cols = ["EQUIPO","LINEUP","N_JUG"]
    sum_cols = ["SEC_CLUTCH","POINTS_FOR","POINTS_AGAINST",
                "FGA_on","FTA_on","TO_on","ORB_on","OPP_FGA_on","OPP_FTA_on","OPP_TO_on","OPP_ORB_on"]
    G = df_all.groupby(grp_cols, dropna=False)[sum_cols].sum().reset_index()

    # métricas desde totales
    G["MIN_CLUTCH"] = G["SEC_CLUTCH"] / 60.0
    G["OFF_POSSESSIONS"] = (G["FGA_on"] - G["ORB_on"] + G["TO_on"] + 0.44*G["FTA_on"])
    G["DEF_POSSESSIONS"] = (G["OPP_FGA_on"] - G["OPP_ORB_on"] + G["OPP_TO_on"] + 0.44*G["OPP_FTA_on"])
    G["OFF_RTG"] = (100.0 * G["POINTS_FOR"] / G["OFF_POSSESSIONS"]).where(G["OFF_POSSESSIONS"] > 0)
    G["DEF_RTG"] = (100.0 * G["POINTS_AGAINST"] / G["DEF_POSSESSIONS"]).where(G["DEF_POSSESSIONS"] > 0)
    G["NET_RTG"] = G["OFF_RTG"] - G["DEF_RTG"]

    # *** FILTRO HARDCODED: mínimo 1 minuto acumulado y quintetos de 5 ***
    G = G[(G["SEC_CLUTCH"] >= MIN_SEC_HARDCODED) & (G["N_JUG"] == 5)].copy()

    # ordenar por NET_RTG dentro de cada equipo
    G.sort_values(["EQUIPO","NET_RTG","MIN_CLUTCH"], ascending=[True, False, False], inplace=True)

    # export: una hoja por equipo
    os.makedirs(os.path.dirname(out_xlsx) or ".", exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
        for team, df_team in G.groupby("EQUIPO", dropna=False):
            sheet = (team[:28] or "Equipo")
            df_team.to_excel(xw, index=False, sheet_name=sheet)

    print(f"[OK] Guardado: {out_xlsx}")
    print(f"Equipos: {G['EQUIPO'].nunique()}  ·  Quintetos: {len(G)}  ·  MinSec HARD-CODED: {MIN_SEC_HARDCODED}")

# ==========================
# CLI
# ==========================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4, help="Procesos en paralelo")
    ap.add_argument("--retries", type=int, default=2, help="Reintentos por partido si 0 filas")
    ap.add_argument("--out", default="./data/clutch_lineups.xlsx", help="Excel destino (una hoja por equipo)")
    args = ap.parse_args()

    aggregate_season_lineups(workers=args.workers, retries=args.retries, out_xlsx=args.out)

if __name__ == "__main__":
    try:
        set_start_method("spawn")
    except RuntimeError:
        pass
    freeze_support()
    main()
