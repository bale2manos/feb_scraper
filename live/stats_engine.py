# stats_engine.py
# MÓDULO 3 — motor estadístico avanzado

import math


# ================================
# UTILIDADES
# ================================

def poss(FGA, ORB, TO, FTA, k=0.475):
    return FGA - ORB + TO + k * FTA


def efg(FGM, TPM, FGA):
    return (FGM + 0.5 * TPM) / FGA if FGA > 0 else 0


def tov_rate(TO, FGA, FTA, k=0.475):
    denom = FGA + k * FTA + TO
    return TO / denom if denom > 0 else 0


def orb_rate(ORB, opp_DRB):
    return ORB / (ORB + opp_DRB) if (ORB + opp_DRB) > 0 else 0


def ftr(FTA, FGA):
    return FTA / FGA if FGA > 0 else 0


def ts(PTS, FGA, FTA, k=0.475):
    denom = 2 * (FGA + k * FTA)
    return PTS / denom if denom > 0 else 0


import pandas as pd
import unicodedata

def normalize_name(name: str) -> str:
    # Quitar comas -> "ALARCON ORTIZ MIGUEL"
    name = name.replace(",", " ").upper()
    # Quitar tildes
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    # Quitar espacios duplicados
    name = " ".join(name.split())
    return name

def load_historical_ft(path="./data/3FEB_25_26/players_25_26_3FEB.xlsx"):
    df = pd.read_excel(path)
    df["JUGADOR_NORM"] = df["JUGADOR"].apply(normalize_name)
    hist = {}

    for _, row in df.iterrows():
        made = row["TL CONVERTIDOS"]
        att = row["TL INTENTADOS"]
        if att > 0:
            hist[row["JUGADOR_NORM"]] = (made, att)

    return hist


# ================================
# NET POINTS APPROX (Dean Oliver style)
# ================================

def net_points_for_factors(local, visitor):
    """
    Calcula Net Points aproximados por factor.
    Basado en diferencias y sensibilidad lineal.
    """

    # Medias
    Poss_L = poss(local["FGA"], local["ORB"], local["TO"], local["FTA"])
    Poss_V = poss(visitor["FGA"], visitor["ORB"], visitor["TO"], visitor["FTA"])
    Poss_mean = (Poss_L + Poss_V) / 2 if (Poss_L + Poss_V) > 0 else 1

    PTS_L = local["score"]
    PTS_V = visitor["score"]
    PPP = (PTS_L + PTS_V) / (Poss_L + Poss_V) if (Poss_L + Poss_V) > 0 else 1

    FGA_mean = (local["FGA"] + visitor["FGA"]) / 2
    misses_mean = (
        (local["FGA"] - local["FGM"]) + (visitor["FGA"] - visitor["FGM"])
    ) / 2

    FTr_mean = (ftr(local["FTA"], local["FGA"]) +
                ftr(visitor["FTA"], visitor["FGA"])) / 2

    FTp_mean = (
        (local["FTM"] + visitor["FTM"]) /
        (local["FTA"] + visitor["FTA"])
        if local["FTA"] + visitor["FTA"] > 0 else 0
    )

    PPS_nonTO = 2 * ((efg(local["FGM"], local["3PM"], local["FGA"]) +
                      efg(visitor["FGM"], visitor["3PM"], visitor["FGA"])) / 2) \
                + FTp_mean * FTr_mean

    # Deltas
    ΔeFG = (
        efg(local["FGM"], local["3PM"], local["FGA"])
        - efg(visitor["FGM"], visitor["3PM"], visitor["FGA"])
    )

    ΔTOV = (
        tov_rate(local["TO"], local["FGA"], local["FTA"])
        - tov_rate(visitor["TO"], visitor["FGA"], visitor["FTA"])
    )

    ΔORB = (
        orb_rate(local["ORB"], visitor["DRB"])
        - orb_rate(visitor["ORB"], local["DRB"])
    )

    ΔFTr = (
        ftr(local["FTA"], local["FGA"])
        - ftr(visitor["FTA"], visitor["FGA"])
    )

    # Net Points lineales
    NP_eFG = 2 * ΔeFG * FGA_mean
    NP_TOV = - ΔTOV * Poss_mean * PPP
    NP_ORB = ΔORB * misses_mean * PPS_nonTO
    NP_FT = ΔFTr * FTp_mean * FGA_mean

    NP_total = NP_eFG + NP_TOV + NP_ORB + NP_FT

    return {
        "NP_eFG": NP_eFG,
        "NP_TOV": NP_TOV,
        "NP_ORB": NP_ORB,
        "NP_FT": NP_FT,
        "NP_total": NP_total,
        "deltas": {
            "ΔeFG": ΔeFG,
            "ΔTOV": ΔTOV,
            "ΔORB": ΔORB,
            "ΔFTr": ΔFTr
        }
    }


# ================================
# ANALIZADOR PRINCIPAL
# ================================

def analyze_game(norm_json):
    local = norm_json["local"]
    visitor = norm_json["visitor"]

    # Posesiones
    Poss_L = poss(local["FGA"], local["ORB"], local["TO"], local["FTA"])
    Poss_V = poss(visitor["FGA"], visitor["ORB"], visitor["TO"], visitor["FTA"])

    # Four Factors
    ff_local = {
        "eFG": efg(local["FGM"], local["3PM"], local["FGA"]),
        "TOV%": tov_rate(local["TO"], local["FGA"], local["FTA"]),
        "ORB%": orb_rate(local["ORB"], visitor["DRB"]),
        "FTr": ftr(local["FTA"], local["FGA"])
    }

    ff_visitor = {
        "eFG": efg(visitor["FGM"], visitor["3PM"], visitor["FGA"]),
        "TOV%": tov_rate(visitor["TO"], visitor["FGA"], visitor["FTA"]),
        "ORB%": orb_rate(visitor["ORB"], local["DRB"]),
        "FTr": ftr(visitor["FTA"], visitor["FGA"])
    }

    # ORtg y DRtg
    ORtg_L = 100 * local["score"] / Poss_L if Poss_L > 0 else 0
    DRtg_L = 100 * visitor["score"] / Poss_V if Poss_V > 0 else 0

    ORtg_V = 100 * visitor["score"] / Poss_V if Poss_V > 0 else 0
    DRtg_V = 100 * local["score"] / Poss_L if Poss_L > 0 else 0

    # Net Points
    netp = net_points_for_factors(local, visitor)

    # Mix de finalización
    def finishing_mix(T):
        SC = T["FGA"] + T["TO"] + 0.44 * T["FTA"]
        if SC == 0:
            return {"SC": 0, "share_2PA": 0, "share_3PA": 0, "share_FT": 0, "share_TO": 0}

        return {
            "SC": SC,
            "share_2PA": (T["2PA"] / SC),
            "share_3PA": (T["3PA"] / SC),
            "share_FT": (0.44 * T["FTA"] / SC),
            "share_TO": (T["TO"] / SC)
        }

    mix_local = finishing_mix(local)
    mix_visitor = finishing_mix(visitor)
    # Función auxiliar para formatear nombres (se define antes para usarla en alertas)
    def format_player_name(name, dorsal):
        """
        Convierte 'APELLIDO1 APELLIDO2, NOMBRE' a 'Dorsal - Nombre Apellido1'
        """
        try:
            if ',' in name:
                apellidos, nombre = name.split(',', 1)
                apellidos = apellidos.strip()
                nombre = nombre.strip()
                # Tomar solo el primer apellido
                primer_apellido = apellidos.split()[0] if apellidos else ""
                # Formatear como título (primera letra mayúscula)
                nombre_formateado = nombre.title()
                primer_apellido_formateado = primer_apellido.title()
                return f"{dorsal} - {nombre_formateado} {primer_apellido_formateado}"
            else:
                # Si no tiene el formato esperado, devolver el nombre tal cual con dorsal
                return f"{dorsal} - {name}"
        except:
            return f"{dorsal} - {name}"

    # Panel de alertas
    alerts = []

    # eFG diferencial
    if ff_local["eFG"] - ff_visitor["eFG"] < -0.08:
        alerts.append("Tiramos peor que el rival (eFG inferior).")

    # TOV% nuestro (solo nosotros)
    if ff_local["TOV%"] > 0.18:
        tov_pct = ff_local["TOV%"] * 100
        tov_total = local["TO"]
        alerts.append(f"Estamos perdiendo demasiado el balón: {tov_total} pérdidas ({tov_pct:.1f}%).")

    # Rebote ofensivo rival
    if ff_visitor["ORB%"] > 0.30:
        oreb_pct = ff_visitor["ORB%"] * 100
        oreb_total = visitor["ORB"]
        alerts.append(f"El rival domina nuestro rebote defensivo: {oreb_total} rebotes ofensivos ({oreb_pct:.1f}%).")

    # FTr rival
    if ff_visitor["FTr"] - ff_local["FTr"] > 0.10:
        alerts.append("El rival está sacando más tiros libres.")

    # Faltas propias / rivales — ahora en función del cuarto actual
    # Si no viene el cuarto en norm_json, usar por defecto 4
    quarter = norm_json.get("quarter") if isinstance(norm_json.get("quarter"), int) else None
    if quarter is None:
        quarter = 4

    # Alerta si el número de faltas es >= cuarto actual
    foul_threshold = quarter

    local_pf = [format_player_name(p["name"], p.get("dorsal", "")) for p in local["players"] if p["pf"] >= foul_threshold]
    if local_pf:
        alerts.append(f"Nuestros jugadores con {foul_threshold} o más faltas (cuarto {quarter}): " + ", ".join(local_pf))

    visitor_pf = [format_player_name(p["name"], p.get("dorsal", "")) for p in visitor["players"] if p["pf"] >= foul_threshold]
    if visitor_pf:
        alerts.append(f"Jugadores rivales con {foul_threshold} o más faltas (cuarto {quarter}): " + ", ".join(visitor_pf))
    # Análisis jugadores
    players_analysis = {
        "local_hot": [],
        "local_cold": [],
        "visitor_hot": [],
        "visitor_cold": []
    }

    def evaluate_players(players, tag_hot, tag_cold):
        for p in players:
            FGA = p["t2i"] + p["t3i"]
            FGM = p["t2c"] + p["t3c"]
            TS = ts(p["pts"], FGA, p["tli"])
            vol = FGA + 0.475 * p["tli"] + p["to"]

            if vol >= 4:  # volumen suficiente
                formatted_name = format_player_name(p["name"], p.get("dorsal", ""))
                if TS > 0.60:
                    tag_hot.append({"name": formatted_name, "TS": TS, "vol": vol})
                elif TS < 0.40:
                    tag_cold.append({"name": formatted_name, "TS": TS, "vol": vol})

    evaluate_players(local["players"], players_analysis["local_hot"], players_analysis["local_cold"])
    evaluate_players(visitor["players"], players_analysis["visitor_hot"], players_analysis["visitor_cold"])

    # ============================================================
    # DETECCIÓN DE MALOS TIRADORES (RIVAL) - HISTÓRICO + DÍA
    # ============================================================
    historical = load_historical_ft()
    poor_ft = []

    for p in visitor["players"]:
        name_norm = normalize_name(p["name"])

        hoy_att = p["tli"]
        hoy_made = p["tlc"]
        minutos = p["min"]

        # Si no está en el histórico, lo ignoramos (como pediste)
        if name_norm not in historical:
            continue

        hist_made, hist_att = historical[name_norm]

        # Necesitamos volumen histórico mínimo
        if hist_att < 10:
            continue

        ft_hist = hist_made / hist_att if hist_att > 0 else 0

        # CASO A — Ha tirado HOY
        if hoy_att > 0:
            ft_today = hoy_made / hoy_att
            ft_final = 0.65 * ft_today + 0.35 * ft_hist

            if ft_final <= 0.60 and minutos >= 5:
                poor_ft.append({
                    "name": p["name"],
                    "dorsal": p.get("dorsal", ""),
                    "FT_final": ft_final,
                    "FT_today": ft_today,
                    "FT_hist": ft_hist,
                    "att_today": hoy_att,
                    "att_hist": hist_att
                })

        # CASO B — NO ha tirado hoy (hoy_att == 0)
        else:
            if ft_hist <= 0.60 and minutos >= 5:
                # ft_today = None cuando no ha tirado
                poor_ft.append({
                    "name": p["name"],
                    "dorsal": p.get("dorsal", ""),
                    "FT_final": ft_hist,   # uso hist puro
                    "FT_today": None,
                    "FT_hist": ft_hist,
                    "att_today": 0,
                    "att_hist": hist_att
                })

    # Ordenar malos tiradores por FT combinado (FT_final) descendente.
    # Priorizar ligeramente a los que han tirado hoy: en la clave, los que
    # tienen `FT_today` no nulo obtienen preferencia. Como desempate usamos
    # el número de intentos hoy (`att_today`) para preferir mayor volumen.
    poor_ft.sort(key=lambda x: (x.get('FT_final', 0), 1 if x.get('FT_today') is not None else 0, x.get('att_today', 0)), reverse=False)



    # Output final
    return {
        "game_id": norm_json["game_id"],
        "status": norm_json["status"],

        "score": {
            "local": local["score"],
            "visitor": visitor["score"]
        },
        
        "team_names": {
            "local": local.get("team", "Local"),
            "visitor": visitor.get("team", "Visitante")
        },

        "four_factors": {
            "local": ff_local,
            "visitor": ff_visitor,
            "deltas": {
                "ΔeFG": ff_local["eFG"] - ff_visitor["eFG"],
                "ΔTOV": ff_local["TOV%"] - ff_visitor["TOV%"],
                "ΔORB": ff_local["ORB%"] - ff_visitor["ORB%"],
                "ΔFTr": ff_local["FTr"] - ff_visitor["FTr"],
            }
        },

        "net_points": netp,

        "mix": {
            "local": mix_local,
            "visitor": mix_visitor
        },

        "ratings": {
            "local": {"ORtg": ORtg_L, "DRtg": DRtg_L, "NetRtg": ORtg_L - DRtg_L},
            "visitor": {"ORtg": ORtg_V, "DRtg": DRtg_V, "NetRtg": ORtg_V - DRtg_V}
        },

        "alerts": alerts,
        "players_analysis": players_analysis,
        "poor_ft_shooters": poor_ft
    }
