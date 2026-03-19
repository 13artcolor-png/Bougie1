"""Prediction du prochain micro-mouvement par n-grams.

Principe :
- Chaque bougie M15 est decomposee en ~14 micro-mouvements (U/D/R)
- On extrait tous les n-grams (sequences de N mouvements)
- Pour chaque n-gram, on compte ce qui suit (U, D ou R)
- A runtime, on prend les derniers N mouvements et on predit le suivant

Taille des n-grams : 3, 4 et 5 (on combine les 3 pour plus de precision)
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.micro_predict")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    """Cree les tables pour les n-grams si elles n'existent pas."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS micro_sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            sequence TEXT NOT NULL,
            threshold REAL NOT NULL,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ngrams (
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
        CREATE INDEX IF NOT EXISTS idx_ngram_lookup
        ON ngrams(symbol, timeframe, ngram)
    """)
    conn.commit()
    conn.close()


def compute_sequence(micro_candles: list, candle_high: float, candle_low: float) -> str:
    """Calcule la sequence U/D/R a partir des micro-bougies.

    U = close monte de plus de 5% du range
    D = close descend de plus de 5% du range
    R = range (mouvement < seuil)
    """
    rng = candle_high - candle_low
    if rng <= 0 or len(micro_candles) < 2:
        return ""

    threshold = rng * 0.05

    seq = ""
    prev_close = micro_candles[0]["close"]
    for i in range(1, len(micro_candles)):
        curr_close = micro_candles[i]["close"]
        diff = curr_close - prev_close
        if diff > threshold:
            seq += "U"
        elif diff < -threshold:
            seq += "D"
        else:
            seq += "R"
        prev_close = curr_close

    return seq


def extract_ngrams(sequence: str, sizes: list = None) -> list:
    """Extrait les n-grams d'une sequence.

    Retourne une liste de tuples (ngram, next_move).
    """
    if sizes is None:
        sizes = [3, 4, 5]

    results = []
    for n in sizes:
        for i in range(len(sequence) - n):
            ngram = sequence[i:i + n]
            next_move = sequence[i + n]
            results.append((ngram, next_move))
    return results


def save_sequence_and_ngrams(symbol: str, timeframe: str, candle_time: int,
                              sequence: str, threshold: float):
    """Sauvegarde une sequence et ses n-grams en base."""
    if len(sequence) < 4:
        return

    conn = _get_conn()

    # Sauvegarder la sequence complete
    conn.execute("""
        INSERT OR IGNORE INTO micro_sequences
        (symbol, timeframe, candle_time, sequence, threshold)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, timeframe, candle_time, sequence, threshold))

    # Extraire et sauvegarder les n-grams
    ngrams = extract_ngrams(sequence)
    for ngram, next_move in ngrams:
        conn.execute("""
            INSERT INTO ngrams (symbol, timeframe, ngram, next_move, count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(symbol, timeframe, ngram, next_move)
            DO UPDATE SET count = count + 1
        """, (symbol, timeframe, ngram, next_move))

    conn.commit()
    conn.close()


def predict_next_move(symbol: str, timeframe: str, current_sequence: str) -> dict:
    """Predit le prochain mouvement (U, D ou R) base sur les n derniers mouvements.

    Teste les n-grams de taille 5, 4, 3 (du plus precis au moins precis).
    Retourne le premier qui a assez de donnees.
    """
    if len(current_sequence) < 3:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    # Tester du n-gram le plus long au plus court
    for n in [5, 4, 3]:
        if len(current_sequence) < n:
            continue

        ngram = current_sequence[-n:]

        rows = conn.execute("""
            SELECT next_move, count
            FROM ngrams
            WHERE symbol = ? AND timeframe = ? AND ngram = ?
            ORDER BY count DESC
        """, (symbol, timeframe, ngram)).fetchall()

        total = sum(r["count"] for r in rows)

        if total >= 10:  # Assez de donnees
            conn.close()

            predictions = {}
            for r in rows:
                predictions[r["next_move"]] = {
                    "probability": round(r["count"] / total * 100, 1),
                    "count": r["count"],
                }

            # Trouver le mouvement le plus probable
            best = max(predictions.items(), key=lambda x: x[1]["probability"])

            return {
                "prediction": best[0],
                "confidence": best[1]["probability"],
                "ngram": ngram,
                "ngram_size": n,
                "total_samples": total,
                "details": predictions,
            }

    conn.close()
    return {"prediction": None, "message": "Pas assez de donnees"}


def predict_next_moves(symbol: str, timeframe: str, current_sequence: str,
                        horizon: int = 3) -> list:
    """Predit les N prochains mouvements en chaine.

    A chaque etape, on ajoute le mouvement le plus probable
    et on reutilise la sequence augmentee pour predire le suivant.
    """
    predictions = []
    seq = current_sequence

    for i in range(horizon):
        result = predict_next_move(symbol, timeframe, seq)
        if result["prediction"] is None:
            break
        predictions.append(result)
        seq += result["prediction"]

    return predictions
