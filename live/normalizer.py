# normalizer.py
# MÓDULO 2 — Normalizador / Agregador

def aggregate_team_stats(team_json: dict) -> dict:
    """
    Recibe la estructura:
        {
            "team": "...",
            "score": ...,
            "players": [ {...}, {...} ]
        }
    Devuelve estadísticas agregadas por equipo listas para el motor estadístico.
    """

    players = team_json["players"]

    FGM = 0
    FGA = 0
    TPM = 0
    TPA = 0
    FTM = 0
    FTA = 0
    ORB = 0
    DRB = 0
    AST = 0
    STL = 0
    TO  = 0
    PF  = 0
    FD  = 0
    MIN = 0.0

    for p in players:

        # Tiros
        t2c = p["t2c"]
        t2i = p["t2i"]
        t3c = p["t3c"]
        t3i = p["t3i"]
        tlc = p["tlc"]
        tli = p["tli"]

        FGM += t2c + t3c
        FGA += t2i + t3i
        TPM += t3c
        TPA += t3i
        FTM += tlc
        FTA += tli

        # Rebote
        ORB += p["orb"]
        DRB += p["drb"]

        # Manejo balón
        AST += p["ast"]
        STL += p["stl"]
        TO  += p["to"]

        # Faltas
        PF += p["pf"]
        FD += p["fd"]

        # Minutos
        MIN += p["min"]

    # Derivados directos
    team_stats = {
        "team": team_json["team"],
        "score": team_json["score"],

        "FGA": FGA,
        "FGM": FGM,

        "3PA": TPA,
        "3PM": TPM,
        "2PA": FGA - TPA,
        "2PM": FGM - TPM,

        "FTA": FTA,
        "FTM": FTM,

        "ORB": ORB,
        "DRB": DRB,

        "AST": AST,
        "STL": STL,
        "TO":  TO,

        "PF": PF,
        "FD": FD,

        "MIN": MIN,

        # dejamos los jugadores tal cual
        "players": players
    }

    return team_stats


def normalize_game_data(scraped_json: dict) -> dict:
    """
    Toma el JSON crudo del scraper y devuelve:
       {
         "local": {team_stats...},
         "visitor": {team_stats...}
       }
    """
    MAIN_TEAM = "GRUPO EGIDO PINTOBASKET"
    local_team = scraped_json["local"]["team"].strip().upper()
    visitor_team = scraped_json["visitor"]["team"].strip().upper()
    if local_team == MAIN_TEAM.upper():
        return {
            "game_id": scraped_json["game_id"],
            "status": scraped_json["status"],
            "local": aggregate_team_stats(scraped_json["local"]),
            "visitor": aggregate_team_stats(scraped_json["visitor"])
        }
    elif visitor_team == MAIN_TEAM.upper():
        # Intercambiar para que Pintobasket sea local
        return {
            "game_id": scraped_json["game_id"],
            "status": scraped_json["status"],
            "local": aggregate_team_stats(scraped_json["visitor"]),
            "visitor": aggregate_team_stats(scraped_json["local"])
        }
    else:
        # Si no está Pintobasket, dejar como está
        return {
            "game_id": scraped_json["game_id"],
            "status": scraped_json["status"],
            "local": aggregate_team_stats(scraped_json["local"]),
            "visitor": aggregate_team_stats(scraped_json["visitor"])
        }
