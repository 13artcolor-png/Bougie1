"""Analyse de la direction de depart des bougies.

Objectif : predire si le premier mouvement significatif apres l'open
est vers le HAUT ou vers le BAS.

Direction de depart determinee par l'ordre high/low :
- order_type = "HL" -> le high arrive avant le low -> depart HAUT
- order_type = "LH" -> le low arrive avant le high -> depart BAS

Facteurs analyses :
1. Close ratio de la bougie precedente (position du close dans le range)
2. Session (ASIE, EUROPE, US, NUIT)
3. Jour de la semaine
4. Sequence des 3 dernieres directions
5. Taille relative de la bougie precedente
"""

import sqlite3
import os
from datetime import datetime, timezone
from utils.logger import get_logger

logger = get_logger("rhythm.direction")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")

# Noms des jours en francais
JOURS = {0: "LUN", 1: "MAR", 2: "MER", 3: "JEU", 4: "VEN", 5: "SAM", 6: "DIM"}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _close_ratio(row: dict) -> str:
    """Calcule la position du close dans le range high-low.
    Retourne une zone : BAS (0-33%), MILIEU (33-66%), HAUT (66-100%)."""
    h = row["candle_high"]
    l = row["candle_low"]
    c = row["candle_close"]
    if h == l:
        return "MILIEU"
    ratio = (c - l) / (h - l)
    if ratio < 0.33:
        return "BAS"
    elif ratio < 0.66:
        return "MILIEU"
    else:
        return "HAUT"


def _candle_size_ratio(row: dict, avg_size: float) -> str:
    """Compare la taille de la bougie a la moyenne.
    Retourne : PETITE (<0.5x), NORMALE (0.5-1.5x), GRANDE (>1.5x)."""
    size = row["candle_high"] - row["candle_low"]
    if avg_size == 0:
        return "NORMALE"
    ratio = size / avg_size
    if ratio < 0.5:
        return "PETITE"
    elif ratio < 1.5:
        return "NORMALE"
    else:
        return "GRANDE"


def _direction(order_type: str) -> str:
    """Convertit order_type en direction de depart."""
    return "HAUT" if order_type == "HL" else "BAS"


def _day_of_week(candle_time: int) -> str:
    """Retourne le jour de la semaine a partir du timestamp."""
    # Le timestamp est en broker time (UTC+3), on convertit en UTC
    utc_time = candle_time - 3 * 3600
    dt = datetime.fromtimestamp(utc_time, tz=timezone.utc)
    return JOURS.get(dt.weekday(), "?")


def analyze_direction(symbol: str, timeframe: str, lookback: int = 0) -> dict:
    """Analyse complete de la direction de depart.

    Retourne les statistiques de direction croisees avec chaque facteur.
    """
    conn = _get_conn()

    # Recuperer toutes les bougies avec leurs donnees
    if lookback > 0:
        rows = conn.execute("""
            SELECT * FROM signatures
            WHERE symbol = ? AND timeframe = ?
            ORDER BY candle_time DESC
            LIMIT ?
        """, (symbol, timeframe, lookback)).fetchall()
        rows = list(reversed(rows))  # Remettre en ordre chronologique
    else:
        rows = conn.execute("""
            SELECT * FROM signatures
            WHERE symbol = ? AND timeframe = ?
            ORDER BY candle_time ASC
        """, (symbol, timeframe)).fetchall()

    conn.close()

    rows = [dict(r) for r in rows]
    if len(rows) < 10:
        return {"error": "Pas assez de donnees", "total": len(rows)}

    # Calcul de la taille moyenne des bougies
    sizes = [r["candle_high"] - r["candle_low"] for r in rows]
    avg_size = sum(sizes) / len(sizes) if sizes else 1

    # --- Stats globales ---
    total = len(rows)
    haut_count = sum(1 for r in rows if r["order_type"] == "HL")
    bas_count = total - haut_count

    result = {
        "total": total,
        "global": {
            "HAUT": round(haut_count / total * 100, 1),
            "BAS": round(bas_count / total * 100, 1),
            "count_haut": haut_count,
            "count_bas": bas_count,
        },
        "facteurs": {},
    }

    # --- Facteur 1 : Close ratio de la bougie precedente ---
    close_ratio_stats = {}
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]
        cr = _close_ratio(prev)
        direction = _direction(curr["order_type"])
        if cr not in close_ratio_stats:
            close_ratio_stats[cr] = {"HAUT": 0, "BAS": 0, "total": 0}
        close_ratio_stats[cr][direction] += 1
        close_ratio_stats[cr]["total"] += 1

    result["facteurs"]["close_ratio_precedent"] = _format_stats(close_ratio_stats)

    # --- Facteur 2 : Session ---
    session_stats = {}
    for r in rows:
        session = r["session"]
        direction = _direction(r["order_type"])
        if session not in session_stats:
            session_stats[session] = {"HAUT": 0, "BAS": 0, "total": 0}
        session_stats[session][direction] += 1
        session_stats[session]["total"] += 1

    result["facteurs"]["session"] = _format_stats(session_stats)

    # --- Facteur 3 : Jour de la semaine ---
    jour_stats = {}
    for r in rows:
        jour = _day_of_week(r["candle_time"])
        direction = _direction(r["order_type"])
        if jour not in jour_stats:
            jour_stats[jour] = {"HAUT": 0, "BAS": 0, "total": 0}
        jour_stats[jour][direction] += 1
        jour_stats[jour]["total"] += 1

    result["facteurs"]["jour"] = _format_stats(jour_stats)

    # --- Facteur 4 : Sequence des 3 dernieres directions ---
    seq_stats = {}
    for i in range(3, len(rows)):
        seq = "".join(_direction(rows[j]["order_type"])[0] for j in range(i - 3, i))
        # seq = "HHH", "HHB", "HBH", etc.
        direction = _direction(rows[i]["order_type"])
        if seq not in seq_stats:
            seq_stats[seq] = {"HAUT": 0, "BAS": 0, "total": 0}
        seq_stats[seq][direction] += 1
        seq_stats[seq]["total"] += 1

    result["facteurs"]["sequence_3"] = _format_stats(seq_stats)

    # --- Facteur 5 : Taille de la bougie precedente ---
    taille_stats = {}
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]
        taille = _candle_size_ratio(prev, avg_size)
        direction = _direction(curr["order_type"])
        if taille not in taille_stats:
            taille_stats[taille] = {"HAUT": 0, "BAS": 0, "total": 0}
        taille_stats[taille][direction] += 1
        taille_stats[taille]["total"] += 1

    result["facteurs"]["taille_precedente"] = _format_stats(taille_stats)

    # --- Meilleur facteur predictif ---
    result["meilleur_facteur"] = _find_best_factor(result["facteurs"])

    # --- Prediction pour la prochaine bougie ---
    if len(rows) >= 3:
        last_row = rows[-1]
        result["prediction"] = _predict_next(rows, avg_size)

    return result


def _format_stats(stats: dict) -> list:
    """Formate les stats pour chaque valeur d'un facteur.
    Trie par biais (ecart au 50/50) decroissant."""
    formatted = []
    for key, val in stats.items():
        total = val["total"]
        if total < 5:
            continue  # Pas assez de donnees pour ce sous-groupe
        pct_haut = round(val["HAUT"] / total * 100, 1)
        pct_bas = round(val["BAS"] / total * 100, 1)
        biais = abs(pct_haut - 50)  # Ecart au 50/50
        formatted.append({
            "valeur": key,
            "pct_haut": pct_haut,
            "pct_bas": pct_bas,
            "biais": round(biais, 1),
            "direction_probable": "HAUT" if pct_haut > 50 else "BAS",
            "total": total,
        })
    # Trier par biais decroissant (le plus predictif en premier)
    formatted.sort(key=lambda x: x["biais"], reverse=True)
    return formatted


def _find_best_factor(facteurs: dict) -> dict:
    """Trouve le facteur avec le plus fort biais moyen."""
    best_name = ""
    best_avg_biais = 0
    for name, values in facteurs.items():
        if not values:
            continue
        # Biais moyen pondere par le nombre d'occurrences
        total_weight = sum(v["total"] for v in values)
        if total_weight == 0:
            continue
        avg_biais = sum(v["biais"] * v["total"] for v in values) / total_weight
        if avg_biais > best_avg_biais:
            best_avg_biais = avg_biais
            best_name = name
    return {
        "nom": best_name,
        "biais_moyen": round(best_avg_biais, 1),
    }


def _predict_next(rows: list, avg_size: float) -> dict:
    """Genere une prediction pour la prochaine bougie.

    Combine les facteurs pour donner une probabilite HAUT/BAS.
    """
    last = rows[-1]

    # Calculer chaque facteur pour la situation actuelle
    cr = _close_ratio(last)
    session = last["session"]
    jour = _day_of_week(last["candle_time"])
    taille = _candle_size_ratio(last, avg_size)

    # Sequence des 3 dernieres directions
    seq = ""
    if len(rows) >= 3:
        seq = "".join(_direction(rows[j]["order_type"])[0] for j in range(-3, 0))

    # Calculer les probabilites pour chaque facteur
    votes_haut = 0.0
    votes_bas = 0.0
    details = []

    # Analyser chaque facteur en parcourant les donnees
    facteurs_actuels = {
        "close_ratio": cr,
        "session": session,
        "jour": jour,
        "taille": taille,
        "sequence": seq,
    }

    # Recalculer les stats pour chaque facteur avec la valeur actuelle
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]
        direction = _direction(curr["order_type"])

        match_cr = _close_ratio(prev) == cr
        match_session = curr["session"] == session
        match_jour = _day_of_week(curr["candle_time"]) == jour
        match_taille = _candle_size_ratio(prev, avg_size) == taille

        for match, name in [
            (match_cr, "close_ratio"),
            (match_session, "session"),
            (match_jour, "jour"),
            (match_taille, "taille"),
        ]:
            if match:
                if direction == "HAUT":
                    votes_haut += 1
                else:
                    votes_bas += 1

    # Sequence des 3 dernieres (facteur separe car necessite i >= 3)
    if seq:
        for i in range(3, len(rows)):
            s = "".join(_direction(rows[j]["order_type"])[0] for j in range(i - 3, i))
            if s == seq:
                direction = _direction(rows[i]["order_type"])
                if direction == "HAUT":
                    votes_haut += 1
                else:
                    votes_bas += 1

    total_votes = votes_haut + votes_bas
    if total_votes == 0:
        return {"direction": "NEUTRE", "confiance": 0, "facteurs": facteurs_actuels}

    pct_haut = round(votes_haut / total_votes * 100, 1)
    pct_bas = round(votes_bas / total_votes * 100, 1)
    confiance = round(abs(pct_haut - 50), 1)

    return {
        "direction": "HAUT" if pct_haut > pct_bas else "BAS",
        "pct_haut": pct_haut,
        "pct_bas": pct_bas,
        "confiance": confiance,
        "facteurs": facteurs_actuels,
        "total_votes": int(total_votes),
    }
