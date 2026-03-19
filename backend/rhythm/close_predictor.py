"""Prediction de la couleur finale de la bougie (close > open = hausse, sinon baisse).

Basee sur le parcours actuel normalise :
- Chaque mouvement est categorise par direction (U/D) et amplitude (court/moyen/long)
- On cherche dans l'historique les bougies avec un parcours similaire
- On regarde comment elles ont cloture (hausse ou baisse)
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.close_predictor")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_move(move: str) -> str:
    """Normalise un mouvement en direction + amplitude.
    UUUUUUUUU -> U-long
    DDD -> D-court
    UUUUU -> U-moyen
    """
    direction = move[0]  # U ou D
    amplitude = len(move)
    if amplitude <= 4:
        size = "court"
    elif amplitude <= 10:
        size = "moyen"
    else:
        size = "long"
    return f"{direction}-{size}"


def _normalize_sequence(moves: list) -> list:
    """Normalise une sequence de mouvements."""
    return [_normalize_move(m) for m in moves if m and m[0] in ("U", "D")]


def init_close_table():
    """Cree la table pour les predictions de cloture."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS close_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            normalized_moves TEXT NOT NULL,
            move_count INTEGER NOT NULL,
            closed_bullish INTEGER NOT NULL,
            position_at_25 TEXT DEFAULT '',
            position_at_50 TEXT DEFAULT '',
            position_at_75 TEXT DEFAULT '',
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_close_pattern
        ON close_patterns(symbol, timeframe, normalized_moves)
    """)
    conn.commit()
    conn.close()


def save_close_pattern(symbol: str, timeframe: str, candle_time: int,
                        moves: list, closed_bullish: bool,
                        pos_25: str = "", pos_50: str = "", pos_75: str = ""):
    """Sauvegarde le pattern normalise avec le resultat de cloture."""
    normalized = _normalize_sequence(moves)
    if len(normalized) < 2:
        return

    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO close_patterns
        (symbol, timeframe, candle_time, normalized_moves, move_count,
         closed_bullish, position_at_25, position_at_50, position_at_75)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, timeframe, candle_time,
          ",".join(normalized), len(normalized),
          1 if closed_bullish else 0,
          pos_25, pos_50, pos_75))
    conn.commit()
    conn.close()


def predict_close(symbol: str, timeframe: str, current_moves: list,
                   progress: float) -> dict:
    """Predit si la bougie cloturera en hausse ou en baisse.

    Utilise le parcours normalise actuel et la progression pour
    chercher des bougies similaires dans l'historique.
    """
    if not current_moves or len(current_moves) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    normalized = _normalize_sequence(current_moves)
    if len(normalized) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    # Strategie : chercher les bougies dont le parcours CONTIENT la meme sequence recente
    # On utilise les derniers mouvements (les plus recents = les plus pertinents)
    # On teste du plus long au plus court
    best_result = None

    for length in range(min(len(normalized), 6), 1, -1):
        # Prendre les DERNIERS mouvements normalises
        suffix = ",".join(normalized[-length:])

        rows = conn.execute("""
            SELECT closed_bullish, COUNT(*) as count
            FROM close_patterns
            WHERE symbol = ? AND timeframe = ?
                AND normalized_moves LIKE ?
            GROUP BY closed_bullish
        """, (symbol, timeframe, "%" + suffix + "%")).fetchall()

        total = sum(r["count"] for r in rows)

        if total >= 15:
            bullish = 0
            bearish = 0
            for r in rows:
                if r["closed_bullish"] == 1:
                    bullish = r["count"]
                else:
                    bearish = r["count"]

            pct_hausse = round(bullish / total * 100, 1)
            pct_baisse = round(bearish / total * 100, 1)

            best_result = {
                "prediction": "HAUSSE" if pct_hausse > pct_baisse else "BAISSE",
                "pct_hausse": pct_hausse,
                "pct_baisse": pct_baisse,
                "confidence": round(abs(pct_hausse - 50), 1),
                "total_samples": total,
                "pattern_length": length,
                "pattern_used": suffix,
                "progress": round(progress * 100, 1),
            }
            break

    conn.close()

    if not best_result:
        return {"prediction": None, "message": "Pas assez de donnees"}

    return best_result
