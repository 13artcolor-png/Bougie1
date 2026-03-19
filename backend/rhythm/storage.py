"""Stockage SQLite des signatures rythmiques."""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.storage")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    """Ouvre une connexion SQLite et cree la table si necessaire."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            signature TEXT NOT NULL,
            category TEXT NOT NULL,
            timing TEXT NOT NULL,
            detail TEXT NOT NULL,
            session TEXT NOT NULL DEFAULT '',
            prev_signature TEXT NOT NULL DEFAULT '',
            open_row INTEGER NOT NULL,
            high_col TEXT NOT NULL,
            low_col TEXT NOT NULL,
            close_row INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            candle_open REAL,
            candle_high REAL,
            candle_low REAL,
            candle_close REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sig_lookup
        ON signatures(symbol, timeframe, signature)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sig_session
        ON signatures(symbol, timeframe, session)
    """)
    conn.commit()
    return conn


def save_signature(sig: dict) -> bool:
    """Sauvegarde une signature en base."""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT OR IGNORE INTO signatures
            (symbol, timeframe, candle_time, signature, category, timing, detail,
             session, prev_signature,
             open_row, high_col, low_col, close_row, order_type,
             candle_open, candle_high, candle_low, candle_close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sig["symbol"], sig["timeframe"], sig["candle_time"],
            sig["signature"], sig["category"], sig["timing"], sig["detail"],
            sig.get("session", ""), sig.get("prev_signature", ""),
            sig["open_row"], sig["high_col"],
            sig["low_col"], sig["close_row"], sig["order_type"],
            sig["candle_open"], sig["candle_high"],
            sig["candle_low"], sig["candle_close"],
        ))
        inserted = conn.total_changes > 0
        conn.commit()
        conn.close()
        if inserted:
            logger.info(f"Signature sauvegardee: {sig['signature']}")
        return inserted
    except Exception as e:
        logger.error(f"Erreur sauvegarde signature: {e}")
        return False


def get_last_signatures(symbol: str, timeframe: str, limit: int = 50) -> list:
    """Recupere les N dernieres signatures."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM signatures
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC
        LIMIT ?
    """, (symbol, timeframe, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transition_probs(symbol: str, timeframe: str, after_signature: str,
                         session: str = "", lookback: int = 0,
                         prev_signature: str = "") -> list:
    """Calcule les probabilites de transition apres une signature.

    Args:
        after_signature: signature actuelle
        session: filtrer par session (ASIE, EUROPE, US, NUIT) ou vide pour toutes
        lookback: nombre max de bougies a considerer (0 = toutes)
        prev_signature: signature precedente (contexte 2 bougies) ou vide
    """
    conn = _get_conn()

    # Construire la requete avec filtres optionnels
    conditions_s1 = ["s1.symbol = ?", "s1.timeframe = ?", "s1.signature = ?"]
    params: list = [symbol, timeframe, after_signature]

    if session:
        conditions_s1.append("s1.session = ?")
        params.append(session)

    if prev_signature:
        conditions_s1.append("s1.prev_signature = ?")
        params.append(prev_signature)

    where_s1 = " AND ".join(conditions_s1)

    # Sous-requete pour le lookback (limiter aux N plus recentes)
    if lookback > 0:
        subquery = f"""
            SELECT s1.candle_time FROM signatures s1
            WHERE {where_s1}
            ORDER BY s1.candle_time DESC LIMIT ?
        """
        lookback_params = params + [lookback]

        rows = conn.execute(f"""
            SELECT s2.signature, COUNT(*) as count
            FROM signatures s1
            JOIN signatures s2
                ON s2.symbol = s1.symbol
                AND s2.timeframe = s1.timeframe
                AND s2.candle_time > s1.candle_time
            WHERE {where_s1}
                AND s1.candle_time IN ({subquery})
                AND NOT EXISTS (
                    SELECT 1 FROM signatures s3
                    WHERE s3.symbol = s1.symbol
                    AND s3.timeframe = s1.timeframe
                    AND s3.candle_time > s1.candle_time
                    AND s3.candle_time < s2.candle_time
                )
            GROUP BY s2.signature
            ORDER BY count DESC
        """, params + lookback_params).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT s2.signature, COUNT(*) as count
            FROM signatures s1
            JOIN signatures s2
                ON s2.symbol = s1.symbol
                AND s2.timeframe = s1.timeframe
                AND s2.candle_time > s1.candle_time
            WHERE {where_s1}
                AND NOT EXISTS (
                    SELECT 1 FROM signatures s3
                    WHERE s3.symbol = s1.symbol
                    AND s3.timeframe = s1.timeframe
                    AND s3.candle_time > s1.candle_time
                    AND s3.candle_time < s2.candle_time
                )
            GROUP BY s2.signature
            ORDER BY count DESC
        """, params).fetchall()

    conn.close()

    total = sum(r["count"] for r in rows)
    if total == 0:
        return []

    return [
        {
            "signature": r["signature"],
            "count": r["count"],
            "probability": round(r["count"] / total, 3),
        }
        for r in rows
    ]


def get_stats(symbol: str, timeframe: str) -> dict:
    """Statistiques globales."""
    conn = _get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM signatures WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe)
    ).fetchone()[0]

    top = conn.execute("""
        SELECT signature, COUNT(*) as count
        FROM signatures WHERE symbol = ? AND timeframe = ?
        GROUP BY signature ORDER BY count DESC LIMIT 10
    """, (symbol, timeframe)).fetchall()

    conn.close()

    return {
        "total": total,
        "top_signatures": [
            {"signature": r["signature"], "count": r["count"],
             "probability": round(r["count"] / total, 3) if total > 0 else 0}
            for r in top
        ],
    }
