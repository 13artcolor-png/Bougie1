"""Suivi des predictions de cloture (hausse/baisse).

A chaque bougie cloturee, on compare la prediction avec le resultat reel.
On stocke l'historique pour calculer le WR (Win Rate).
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.close_tracker")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tracker_table():
    """Cree les tables de suivi des predictions."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS close_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            predicted TEXT NOT NULL,
            pct_predicted REAL NOT NULL,
            actual TEXT NOT NULL,
            correct INTEGER NOT NULL,
            samples INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS close_tracker_quarters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            predicted TEXT NOT NULL,
            pct_predicted REAL NOT NULL,
            actual TEXT NOT NULL,
            correct INTEGER NOT NULL,
            price_at_quarter REAL DEFAULT 0,
            moves_count_up INTEGER DEFAULT 0,
            moves_count_down INTEGER DEFAULT 0,
            next_q_predicted TEXT DEFAULT '',
            next_q_pct REAL DEFAULT 0,
            next_q_actual TEXT DEFAULT '',
            next_q_correct INTEGER DEFAULT 0,
            UNIQUE(symbol, timeframe, candle_time, quarter)
        )
    """)
    conn.commit()
    conn.close()


# Initialiser la table au chargement du module
init_tracker_table()


def save_close_result(symbol: str, timeframe: str, candle_time: int,
                       predicted: str, pct_predicted: float,
                       actual_bullish: bool, samples: int):
    """Sauvegarde le resultat d'une prediction de cloture."""
    actual = "HAUSSE" if actual_bullish else "BAISSE"
    correct = 1 if predicted == actual else 0

    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO close_tracker
        (symbol, timeframe, candle_time, predicted, pct_predicted, actual, correct, samples)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, timeframe, candle_time, predicted, pct_predicted, actual, correct, samples))
    conn.commit()
    conn.close()

    status = "OK" if correct else "KO"
    logger.info(f"Close prediction: {predicted} ({pct_predicted}%) -> {actual} = {status}")


def save_quarter_prediction(symbol: str, timeframe: str, candle_time: int,
                             quarter: int, predicted: str, pct_predicted: float,
                             price_at_quarter: float = 0,
                             moves_up: int = 0, moves_down: int = 0,
                             next_q_predicted: str = "", next_q_pct: float = 0):
    """Sauvegarde la prediction a un quart donne avec donnees enrichies."""
    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO close_tracker_quarters
        (symbol, timeframe, candle_time, quarter, predicted, pct_predicted,
         actual, correct, price_at_quarter, moves_count_up, moves_count_down,
         next_q_predicted, next_q_pct, next_q_actual, next_q_correct)
        VALUES (?, ?, ?, ?, ?, ?, '', 0, ?, ?, ?, ?, ?, '', 0)
    """, (symbol, timeframe, candle_time, quarter, predicted, pct_predicted,
          price_at_quarter, moves_up, moves_down, next_q_predicted, next_q_pct))
    conn.commit()
    conn.close()


def finalize_quarter_predictions(symbol: str, timeframe: str, candle_time: int,
                                   actual_bullish: bool, quarter_prices: dict = None):
    """Met a jour les predictions par quart avec le resultat final."""
    actual = "HAUSSE" if actual_bullish else "BAISSE"
    conn = _get_conn()

    # Mettre a jour le resultat de cloture
    conn.execute("""
        UPDATE close_tracker_quarters
        SET actual = ?, correct = CASE WHEN predicted = ? THEN 1 ELSE 0 END
        WHERE symbol = ? AND timeframe = ? AND candle_time = ?
    """, (actual, actual, symbol, timeframe, candle_time))

    # Verifier les predictions next_q (quart a quart)
    if quarter_prices:
        for q in [1, 2, 3]:
            price_q = quarter_prices.get(q, 0)
            price_next = quarter_prices.get(q + 1, 0)
            if price_q > 0 and price_next > 0:
                next_actual = "HAUSSE" if price_next > price_q else "BAISSE"
                conn.execute("""
                    UPDATE close_tracker_quarters
                    SET next_q_actual = ?,
                        next_q_correct = CASE WHEN next_q_predicted = ? THEN 1 ELSE 0 END
                    WHERE symbol = ? AND timeframe = ? AND candle_time = ? AND quarter = ?
                """, (next_actual, next_actual, symbol, timeframe, candle_time, q))

    conn.commit()
    conn.close()


def get_close_stats(symbol: str, timeframe: str, limit: int = 50) -> dict:
    """Retourne les statistiques de predictions de cloture."""
    conn = _get_conn()

    # Total et WR
    rows = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(correct) as wins
        FROM close_tracker
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC
        LIMIT ?
    """, (symbol, timeframe, limit)).fetchone()

    total = rows["total"] or 0
    wins = rows["wins"] or 0
    wr = round(wins / total * 100, 1) if total > 0 else 0

    # Historique des dernieres predictions
    history = conn.execute("""
        SELECT candle_time, predicted, pct_predicted, actual, correct, samples
        FROM close_tracker
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC
        LIMIT ?
    """, (symbol, timeframe, limit)).fetchall()

    # WR par quart
    quarter_stats = {}
    for q in [1, 2, 3, 4]:
        qr = conn.execute("""
            SELECT COUNT(*) as total, SUM(correct) as wins
            FROM close_tracker_quarters
            WHERE symbol = ? AND timeframe = ? AND quarter = ? AND actual != ''
        """, (symbol, timeframe, q)).fetchone()
        qt = qr["total"] or 0
        qw = qr["wins"] or 0
        quarter_stats[str(q)] = {
            "total": qt,
            "wins": qw,
            "wr": round(qw / qt * 100, 1) if qt > 0 else 0,
        }

    conn.close()

    return {
        "total": total,
        "wins": wins,
        "losses": total - wins,
        "wr": wr,
        "quarters": quarter_stats,
        "history": [dict(r) for r in history],
    }
