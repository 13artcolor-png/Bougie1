"""Matching partiel en temps reel - v2.

Utilise le nouveau systeme de classification par sequence U/D.
A chaque case completee, on connait une lettre de plus de la sequence
et on peut affiner la prediction.

Case A terminee : on connait la 1ere lettre (U ou D) -> 8 patterns possibles
Case B terminee : on connait 2 lettres (ex: DU) -> 4 patterns possibles
Case C terminee : on connait 3 lettres (ex: DUU) -> 2 patterns possibles
Case D terminee : on connait les 4 lettres -> 1 pattern (100%)

On ne predit rien avant la fin de la case A.
"""

import sqlite3
import os
from utils.logger import get_logger
from rhythm.classifier import _interpolate_prices, _price_to_row, TF_SECONDS

logger = get_logger("rhythm.partial_match")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def estimate_signature(
    current_candle: dict,
    micro_candles: list,
    timeframe: str,
    symbol: str,
) -> list:
    """Estime les signatures probables pour la bougie en cours.

    Retourne une liste triee par probabilite decroissante.
    Ne retourne rien avant la fin de la case A.
    """
    if not current_candle or not micro_candles or len(micro_candles) < 2:
        return []

    candle_start = current_candle["time"]
    candle_open = current_candle["open"]
    candle_high = current_candle["high"]
    candle_low = current_candle["low"]
    duration = TF_SECONDS.get(timeframe, 900)

    if candle_high == candle_low:
        return []

    # Progression basee sur la derniere micro-bougie
    last_micro_time = micro_candles[-1]["time"]
    elapsed = max(0, last_micro_time - candle_start)
    progress = min(elapsed / duration, 1.0) if duration > 0 else 0

    # Ne rien afficher avant 5% (besoin d'au moins quelques micro-bougies)
    if progress < 0.05:
        return []

    # Calculer les prix a la fin de chaque case completee
    case_prices = _interpolate_prices(current_candle, micro_candles, timeframe)

    # Construire la sequence connue :
    # - Cases completees : direction definitive
    # - Case en cours : direction actuelle (peut encore changer)
    prev_price = candle_open
    known_sequence = ""
    cases_completed = int(progress * 4)  # 0, 1, 2, 3 ou 4
    cases_completed = min(cases_completed, 4)

    for i in range(cases_completed):
        known_sequence += "U" if case_prices[i] >= prev_price else "D"
        prev_price = case_prices[i]

    # Ajouter la direction de la case EN COURS (pas encore terminee)
    # On utilise le close actuel comme prix temporaire
    if cases_completed < 4:
        current_close = current_candle["close"]
        known_sequence += "U" if current_close >= prev_price else "D"

    if not known_sequence:
        return []

    # Chercher dans la base toutes les bougies dont la signature commence pareil
    conn = _get_conn()

    # Compter le total pour le ratio
    total_in_db = conn.execute(
        "SELECT COUNT(*) FROM signatures WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe)
    ).fetchone()[0]

    if total_in_db < 10:
        conn.close()
        return []

    # --- PREDICTION basee sur le CONTEXTE (bougie precedente) ---
    # On cherche : apres une bougie de signature X, parmi celles qui
    # commencent par la meme sequence que maintenant, comment finissent-elles ?

    # Recuperer la signature de la bougie precedente
    prev_row = conn.execute("""
        SELECT signature FROM signatures
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC LIMIT 1
    """, (symbol, timeframe)).fetchone()

    prev_sig = prev_row["signature"] if prev_row else ""

    like_pattern = known_sequence + "%"

    # Avec contexte (bougie precedente + debut actuel)
    if prev_sig:
        rows = conn.execute("""
            SELECT s2.signature, COUNT(*) as count
            FROM signatures s1
            JOIN signatures s2
                ON s2.symbol = s1.symbol
                AND s2.timeframe = s1.timeframe
                AND s2.candle_time > s1.candle_time
                AND NOT EXISTS (
                    SELECT 1 FROM signatures s3
                    WHERE s3.symbol = s1.symbol
                    AND s3.timeframe = s1.timeframe
                    AND s3.candle_time > s1.candle_time
                    AND s3.candle_time < s2.candle_time
                )
            WHERE s1.symbol = ? AND s1.timeframe = ?
                AND s1.signature = ?
                AND s2.signature LIKE ?
            GROUP BY s2.signature
            ORDER BY count DESC
        """, (symbol, timeframe, prev_sig, like_pattern)).fetchall()

        # Si assez de resultats avec contexte, utiliser ca
        total_match = sum(r["count"] for r in rows)
        if total_match >= 15:
            conn.close()
            return [
                {
                    "signature": r["signature"],
                    "probability": round(r["count"] / total_match, 3),
                    "count": r["count"],
                    "context": prev_sig,
                }
                for r in rows
            ]

    # Fallback : sans contexte, juste le debut actuel
    rows = conn.execute("""
        SELECT signature, COUNT(*) as count
        FROM signatures
        WHERE symbol = ? AND timeframe = ? AND signature LIKE ?
        GROUP BY signature
        ORDER BY count DESC
    """, (symbol, timeframe, like_pattern)).fetchall()

    conn.close()

    total_match = sum(r["count"] for r in rows)
    if total_match == 0:
        return []

    return [
        {
            "signature": r["signature"],
            "probability": round(r["count"] / total_match, 3),
            "count": r["count"],
        }
        for r in rows
    ]
