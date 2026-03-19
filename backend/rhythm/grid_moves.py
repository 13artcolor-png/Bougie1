"""Systeme de micro-mouvements base sur les franchissements de lignes de grille.

La grille a 4 lignes (1=haut, 2, 3, 4=bas).
A chaque fois que le prix change de ligne, on enregistre le mouvement :
- D = descend d'une ligne
- DD = descend de 2 lignes
- DDD = descend de 3 lignes
- U = monte d'une ligne
- UU = monte de 2 lignes
- UUU = monte de 3 lignes
- R = reste sur la meme ligne (apres un certain temps sans bouger)

La sequence de mouvements forme le "rythme" de la bougie.
On utilise les n-grams de ces mouvements pour predire le suivant.
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.grid_moves")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _price_to_row(price: float, low: float, high: float) -> int:
    """Convertit un prix en ligne (1-32). 1 = haut, 32 = bas."""
    if high == low:
        return 16
    ratio = (price - low) / (high - low)  # 0 = bas, 1 = haut
    row = 32 - int(ratio * 32)
    return max(1, min(32, row))


def compute_grid_moves(micro_candles: list, candle_high: float, candle_low: float) -> list:
    """Calcule la sequence de mouvements de grille.

    Les mouvements continus dans la meme direction sont regroupes :
    - Si le prix descend de ligne 1 a 2 puis de 2 a 4, c'est un seul mouvement "DDD"
    - Un nouveau mouvement commence quand la direction change

    Retourne une liste de mouvements : ["DDD", "UU", "D", "R", ...]
    """
    if not micro_candles or len(micro_candles) < 2 or candle_high == candle_low:
        return []

    # D'abord, collecter tous les franchissements de ligne bruts
    raw_changes = []  # liste de +1 (monte) ou -1 (descend)
    prev_row = _price_to_row(micro_candles[0]["close"], candle_low, candle_high)

    for mc in micro_candles[1:]:
        high_row = _price_to_row(mc["high"], candle_low, candle_high)
        low_row = _price_to_row(mc["low"], candle_low, candle_high)
        close_row = _price_to_row(mc["close"], candle_low, candle_high)

        # Ordre des checkpoints selon la direction de la micro-bougie
        if mc["close"] >= mc["open"]:
            checkpoints = [low_row, high_row, close_row]
        else:
            checkpoints = [high_row, low_row, close_row]

        for row in checkpoints:
            diff = prev_row - row  # positif = monte, negatif = descend
            if diff != 0:
                raw_changes.append((diff, row))
                prev_row = row

    if not raw_changes:
        return ["R"]

    # Regrouper les mouvements continus dans la meme direction
    # Pas de filtre de bruit - chaque changement de direction = nouveau mouvement
    moves = []
    current_direction = None  # "U" ou "D"
    current_count = 0

    for diff, row in raw_changes:
        direction = "U" if diff > 0 else "D"
        steps = abs(diff)

        if direction == current_direction:
            # Meme direction : on accumule
            current_count += steps
        else:
            # Direction change : on sauvegarde le mouvement precedent
            if current_direction is not None and current_count > 0:
                moves.append(current_direction * current_count)
            current_direction = direction
            current_count = steps

    # Sauvegarder le dernier mouvement
    if current_direction is not None and current_count > 0:
        moves.append(current_direction * current_count)

    if not moves:
        moves.append("R")

    return moves


def moves_to_string(moves: list) -> str:
    """Convertit la liste de mouvements en string separee par des virgules."""
    return ",".join(moves)


def init_grid_tables():
    """Cree les tables pour les mouvements de grille."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grid_sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            moves TEXT NOT NULL,
            move_count INTEGER NOT NULL,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grid_ngrams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            ngram TEXT NOT NULL,
            next_move TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(symbol, timeframe, ngram, next_move)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_grid_ngram
        ON grid_ngrams(symbol, timeframe, ngram)
    """)
    conn.commit()
    conn.close()


def extract_grid_ngrams(moves: list, sizes: list = None) -> list:
    """Extrait les n-grams de la liste de mouvements.

    Retourne une liste de tuples (ngram_string, next_move).
    Le ngram est une sequence de mouvements separee par des virgules.
    """
    if sizes is None:
        sizes = [2, 3, 4]

    results = []
    for n in sizes:
        for i in range(len(moves) - n):
            ngram = ",".join(moves[i:i + n])
            next_move = moves[i + n]
            results.append((ngram, next_move))
    return results


def save_grid_sequence(symbol: str, timeframe: str, candle_time: int, moves: list):
    """Sauvegarde une sequence de mouvements et ses n-grams."""
    if len(moves) < 3:
        return

    conn = _get_conn()

    moves_str = moves_to_string(moves)

    conn.execute("""
        INSERT OR IGNORE INTO grid_sequences
        (symbol, timeframe, candle_time, moves, move_count)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, timeframe, candle_time, moves_str, len(moves)))

    # Extraire et sauvegarder les n-grams
    ngrams = extract_grid_ngrams(moves)
    for ngram, next_move in ngrams:
        conn.execute("""
            INSERT INTO grid_ngrams (symbol, timeframe, ngram, next_move, count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(symbol, timeframe, ngram, next_move)
            DO UPDATE SET count = count + 1
        """, (symbol, timeframe, ngram, next_move))

    conn.commit()
    conn.close()


def predict_next_grid_move(symbol: str, timeframe: str, current_moves: list) -> dict:
    """Predit le prochain mouvement de grille.

    Teste les n-grams de taille 4, 3, 2 (du plus precis au moins precis).
    """
    if len(current_moves) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    for n in [4, 3, 2]:
        if len(current_moves) < n:
            continue

        ngram = ",".join(current_moves[-n:])

        rows = conn.execute("""
            SELECT next_move, count
            FROM grid_ngrams
            WHERE symbol = ? AND timeframe = ? AND ngram = ?
            ORDER BY count DESC
        """, (symbol, timeframe, ngram)).fetchall()

        total = sum(r["count"] for r in rows)

        if total >= 10:
            conn.close()

            # Regrouper par direction (U vs D)
            dir_counts = {"U": 0, "D": 0}
            details_raw = {}
            for r in rows:
                move = r["next_move"]
                direction = move[0]  # Premier caractere = U ou D
                dir_counts[direction] = dir_counts.get(direction, 0) + r["count"]
                details_raw[move] = {
                    "probability": round(r["count"] / total * 100, 1),
                    "count": r["count"],
                }

            # Probabilite par direction
            dir_details = {}
            for d, count in dir_counts.items():
                if count > 0:
                    dir_details[d] = {
                        "probability": round(count / total * 100, 1),
                        "count": count,
                    }

            # Amplitude moyenne par direction
            for d in dir_details:
                moves_in_dir = [(len(m), c["count"]) for m, c in details_raw.items() if m[0] == d]
                if moves_in_dir:
                    weighted_avg = sum(l * c for l, c in moves_in_dir) / sum(c for _, c in moves_in_dir)
                    dir_details[d]["avg_amplitude"] = round(weighted_avg, 1)

            best_dir = max(dir_details.items(), key=lambda x: x[1]["probability"])

            return {
                "prediction": best_dir[0],
                "confidence": best_dir[1]["probability"],
                "avg_amplitude": best_dir[1].get("avg_amplitude", 0),
                "ngram": ngram,
                "ngram_size": n,
                "total_samples": total,
                "details": dir_details,
                "details_raw": details_raw,
                "current_moves": current_moves,
            }

    conn.close()
    return {"prediction": None, "message": "Pas assez de donnees"}
