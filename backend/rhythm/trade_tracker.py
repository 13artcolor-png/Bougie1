"""Suivi des trades declenches par les signaux.

- Entree : premier signal de la bougie (1 lot)
- Sortie normale : close de la bougie (1 lot)
- Sortie retournement : si signal s'inverse, cloture a 0.5 lot
- Note 1-10 basee sur le gain et la confiance du signal
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.trade_tracker")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_trade_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            confidence REAL NOT NULL,
            lot_size REAL NOT NULL DEFAULT 1.0,
            points REAL NOT NULL DEFAULT 0,
            exit_type TEXT NOT NULL DEFAULT 'close',
            note INTEGER NOT NULL DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.commit()
    conn.close()


init_trade_table()


def calculate_note(points: float, confidence: float, avg_range: float) -> int:
    """Calcule une note de 1 a 10.

    Combine le gain en points (normalise par le range moyen) et la confiance.
    """
    if avg_range <= 0:
        avg_range = 1

    # Normaliser le gain par le range moyen (-1 a +1)
    gain_ratio = points / avg_range
    gain_ratio = max(-1, min(1, gain_ratio))

    # Score : gain normalise (70%) + confiance (30%)
    conf_score = (confidence - 50) / 50  # 0 a 1
    combined = gain_ratio * 0.7 + conf_score * 0.3

    # Convertir en note 1-10
    note = int(round((combined + 1) * 4.5 + 1))
    return max(1, min(10, note))


def save_trade(symbol: str, timeframe: str, candle_time: int,
               direction: str, entry_price: float, exit_price: float,
               confidence: float, lot_size: float, exit_type: str,
               avg_range: float = 0):
    """Sauvegarde un trade termine."""
    if direction == "LONG":
        points = (exit_price - entry_price) * lot_size
    else:
        points = (entry_price - exit_price) * lot_size

    note = calculate_note(points / lot_size, confidence, avg_range)

    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO trades
        (symbol, timeframe, candle_time, direction, entry_price, exit_price,
         confidence, lot_size, points, exit_type, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, timeframe, candle_time, direction, entry_price, exit_price,
          confidence, lot_size, round(points, 2), exit_type, note))
    conn.commit()
    conn.close()

    status = "WIN" if points > 0 else "LOSS"
    logger.info(f"Trade {direction} {status}: entry={entry_price:.2f} exit={exit_price:.2f} points={points:.2f} note={note}/10 ({exit_type})")


def get_trade_stats(symbol: str, timeframe: str, limit: int = 50) -> dict:
    """Stats des trades."""
    conn = _get_conn()

    rows = conn.execute("""
        SELECT * FROM trades
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC
        LIMIT ?
    """, (symbol, timeframe, limit)).fetchall()

    conn.close()

    if not rows:
        return {"total": 0, "wins": 0, "losses": 0, "wr": 0,
                "total_points": 0, "avg_note": 0, "history": []}

    trades = [dict(r) for r in rows]
    total = len(trades)
    wins = sum(1 for t in trades if t["points"] > 0)
    losses = total - wins
    total_points = sum(t["points"] for t in trades)
    avg_note = round(sum(t["note"] for t in trades) / total, 1) if total > 0 else 0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "wr": round(wins / total * 100, 1) if total > 0 else 0,
        "total_points": round(total_points, 2),
        "avg_note": avg_note,
        "history": trades,
    }
