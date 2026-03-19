"""Dictionnaire de patterns - memoire binaire U/D.

Stocke chaque combinaison de mouvements U/D observee avec :
- Ce qui a suivi (prochain mouvement U ou D)
- Comment la bougie a cloture (HAUSSE ou BAISSE)

Plus il y a de donnees, plus les predictions sont precises.
Le systeme ne calcule pas, il se souvient.
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.pattern_memory")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_pattern_tables():
    """Cree les tables du dictionnaire de patterns."""
    conn = _get_conn()

    # Table principale : chaque pattern et ce qui a suivi
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            pattern TEXT NOT NULL,
            pattern_length INTEGER NOT NULL,
            next_direction TEXT NOT NULL,
            close_result TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(symbol, timeframe, pattern, next_direction, close_result)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern_lookup
        ON pattern_memory(symbol, timeframe, pattern)
    """)

    conn.commit()
    conn.close()


# Initialiser au chargement
init_pattern_tables()


def _normalize_move(move: str) -> str:
    """Normalise un mouvement en direction + taille.
    DDDDD -> D5, UUU -> U3, DD -> D2
    """
    if not move or move[0] not in ("U", "D"):
        return move
    return f"{move[0]}{len(move)}"


def _build_patterns(moves: list, max_length: int = 5) -> list:
    """Construit tous les sous-patterns d'une sequence de mouvements.

    Pour chaque position, genere des patterns de taille 2 a max_length.
    Chaque mouvement est normalise (DDD -> D3).

    Retourne [(pattern_str, next_move_direction, position)]
    """
    normalized = [_normalize_move(m) for m in moves if m and m[0] in ("U", "D")]

    if len(normalized) < 3:
        return []

    patterns = []
    for size in range(2, min(max_length + 1, len(normalized))):
        for i in range(len(normalized) - size):
            pattern = ",".join(normalized[i:i + size])
            next_move = normalized[i + size]
            next_dir = next_move[0]  # U ou D
            patterns.append((pattern, next_dir, size))

    return patterns


def learn_from_candle(symbol: str, timeframe: str, moves: list, close_result: str):
    """Apprend tous les patterns d'une bougie cloturee.

    moves: liste des mouvements (ex: ["DDD", "UU", "DDDDD", ...])
    close_result: "HAUSSE" ou "BAISSE"
    """
    if len(moves) < 3:
        return

    patterns = _build_patterns(moves)
    if not patterns:
        return

    conn = _get_conn()

    for pattern, next_dir, size in patterns:
        conn.execute("""
            INSERT INTO pattern_memory
            (symbol, timeframe, pattern, pattern_length, next_direction, close_result, count)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(symbol, timeframe, pattern, next_direction, close_result)
            DO UPDATE SET count = count + 1
        """, (symbol, timeframe, pattern, size, next_dir, close_result))

    conn.commit()
    conn.close()


def predict_next_move(symbol: str, timeframe: str, current_moves: list) -> dict:
    """Predit le prochain mouvement (U ou D) base sur le dictionnaire.

    Teste les patterns du plus long au plus court.
    Retourne le premier qui a assez de donnees.
    """
    if len(current_moves) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    normalized = [_normalize_move(m) for m in current_moves if m and m[0] in ("U", "D")]

    if len(normalized) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    # Tester du pattern le plus long au plus court
    for size in range(min(5, len(normalized)), 1, -1):
        pattern = ",".join(normalized[-size:])

        rows = conn.execute("""
            SELECT next_direction, SUM(count) as total
            FROM pattern_memory
            WHERE symbol = ? AND timeframe = ? AND pattern = ?
            GROUP BY next_direction
            ORDER BY total DESC
        """, (symbol, timeframe, pattern)).fetchall()

        total = sum(r["total"] for r in rows)

        if total >= 20:  # Assez de donnees
            conn.close()

            details = {}
            for r in rows:
                details[r["next_direction"]] = {
                    "count": r["total"],
                    "pct": round(r["total"] / total * 100, 1),
                }

            best = max(details.items(), key=lambda x: x[1]["pct"])

            return {
                "prediction": best[0],
                "confidence": best[1]["pct"],
                "pattern": pattern,
                "pattern_size": size,
                "total_samples": total,
                "details": details,
            }

    conn.close()
    return {"prediction": None, "message": "Pattern inconnu"}


def predict_close(symbol: str, timeframe: str, current_moves: list, progress: float = 0.5) -> dict:
    """Predit la cloture (HAUSSE ou BAISSE) base sur le dictionnaire.

    Cherche dans le dictionnaire les patterns qui correspondent
    et regarde comment les bougies avec ces patterns ont cloture.
    """
    if len(current_moves) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    normalized = [_normalize_move(m) for m in current_moves if m and m[0] in ("U", "D")]

    if len(normalized) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    # Combiner les resultats de plusieurs tailles de pattern
    total_hausse = 0
    total_baisse = 0
    best_pattern = ""
    best_size = 0
    total_samples = 0

    for size in range(min(5, len(normalized)), 1, -1):
        pattern = ",".join(normalized[-size:])

        rows = conn.execute("""
            SELECT close_result, SUM(count) as total
            FROM pattern_memory
            WHERE symbol = ? AND timeframe = ? AND pattern = ?
            GROUP BY close_result
            ORDER BY total DESC
        """, (symbol, timeframe, pattern)).fetchall()

        total = sum(r["total"] for r in rows)

        if total >= 15:
            # Les patterns plus longs pesent exponentiellement plus
            weight = 2 ** size  # Poids exponentiel : taille 2=4, 3=8, 4=16, 5=32

            for r in rows:
                if r["close_result"] == "HAUSSE":
                    total_hausse += r["total"] * weight
                else:
                    total_baisse += r["total"] * weight

            if not best_pattern:
                best_pattern = pattern
                best_size = size
                total_samples = total

    conn.close()

    grand_total = total_hausse + total_baisse
    if grand_total == 0:
        return {"prediction": None, "message": "Pattern inconnu"}

    pct_hausse = round(total_hausse / grand_total * 100, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    return {
        "prediction": "HAUSSE" if pct_hausse > pct_baisse else "BAISSE",
        "pct_hausse": pct_hausse,
        "pct_baisse": pct_baisse,
        "confidence": round(abs(pct_hausse - 50), 1),
        "best_pattern": best_pattern,
        "best_pattern_size": best_size,
        "total_samples": total_samples,
    }


def get_memory_stats(symbol: str, timeframe: str) -> dict:
    """Retourne les stats du dictionnaire de patterns."""
    conn = _get_conn()

    total_patterns = conn.execute("""
        SELECT COUNT(DISTINCT pattern) FROM pattern_memory
        WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]

    total_entries = conn.execute("""
        SELECT SUM(count) FROM pattern_memory
        WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0] or 0

    conn.close()

    return {
        "total_patterns": total_patterns,
        "total_entries": total_entries,
    }


def backfill_patterns(symbol: str, timeframe: str):
    """Remplit le dictionnaire depuis les grid_sequences en base."""
    conn = _get_conn()

    # Verifier si deja fait
    existing = conn.execute("""
        SELECT COUNT(*) FROM pattern_memory WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]

    if existing > 0:
        logger.info(f"Dictionnaire deja rempli ({existing} entrees)")
        conn.close()
        return

    # Recuperer toutes les bougies
    rows = conn.execute("""
        SELECT gs.moves, cp.closed_bullish
        FROM grid_sequences gs
        LEFT JOIN close_patterns cp
            ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
        WHERE gs.symbol = ? AND gs.timeframe = ?
    """, (symbol, timeframe)).fetchall()

    conn.close()

    logger.info(f"Backfill dictionnaire : {len(rows)} bougies")

    for i, r in enumerate(rows):
        moves = r["moves"].split(",")
        close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        learn_from_candle(symbol, timeframe, moves, close_result)

        if (i + 1) % 1000 == 0:
            logger.info(f"  {i + 1}/{len(rows)} bougies traitees")

    # Nettoyage : supprimer les patterns vus moins de 3 fois
    cleanup_rare_patterns(symbol, timeframe, min_count=3)

    stats = get_memory_stats(symbol, timeframe)
    logger.info(f"Dictionnaire rempli : {stats['total_patterns']} patterns, {stats['total_entries']} entrees")


def cleanup_rare_patterns(symbol: str, timeframe: str, min_count: int = 3):
    """Supprime les patterns vus moins de min_count fois."""
    conn = _get_conn()
    deleted = conn.execute("""
        DELETE FROM pattern_memory
        WHERE symbol = ? AND timeframe = ? AND count < ?
    """, (symbol, timeframe, min_count)).rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        logger.info(f"Nettoyage : {deleted} patterns rares supprimes (< {min_count} occurrences)")
