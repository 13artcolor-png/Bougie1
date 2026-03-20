"""Dictionnaire intelligent - memoire par sequence + position.

Stocke les patterns ADN (DG, UM, DP...) avec leur position dans la bougie (Q1-Q4).
Le meme pattern a des significations differentes selon qu'il arrive tot ou tard.

Format : "Q2:DG,UM,DG" → HAUSSE 65% (120 occurrences)

Prediction :
1. Convertir les mouvements actuels en ADN
2. Determiner le quart en cours
3. Chercher "Qx:derniers_mouvements" dans le dictionnaire
4. Retourner les probabilites
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.smart_memory")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _amp_cat(length: int) -> str:
    """P=petit(1-3), M=moyen(4-8), G=grand(9-15), T=tres_grand(16+)"""
    if length <= 3: return "P"
    elif length <= 8: return "M"
    elif length <= 15: return "G"
    else: return "T"


def moves_to_dna(moves: list) -> list:
    """Convertit les mouvements bruts en ADN categorise."""
    dna = []
    for m in moves:
        m = m.strip()
        if m and m[0] in ("U", "D"):
            dna.append(f"{m[0]}{_amp_cat(len(m))}")
    return dna


def init_smart_tables():
    """Cree les tables du dictionnaire intelligent."""
    conn = _get_conn()

    # Table principale : pattern + position → resultat
    conn.execute("""
        CREATE TABLE IF NOT EXISTS smart_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            quarter INTEGER NOT NULL,
            pattern TEXT NOT NULL,
            pattern_size INTEGER NOT NULL,
            close_result TEXT NOT NULL,
            next_move TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(symbol, timeframe, quarter, pattern, close_result, next_move)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_smart_lookup
        ON smart_memory(symbol, timeframe, quarter, pattern)
    """)
    conn.commit()
    conn.close()


init_smart_tables()


def learn_candle(symbol: str, timeframe: str, moves: list, close_result: str):
    """Apprend une bougie complete dans le dictionnaire intelligent.

    Pour chaque position dans la bougie (Q1-Q4), stocke les sous-patterns
    et ce qui a suivi (prochain mouvement + cloture).
    """
    dna = moves_to_dna(moves)
    if len(dna) < 4:
        return

    conn = _get_conn()

    # Pour chaque quart
    for q in range(1, 5):
        # Couper la sequence au quart
        cut = max(2, int(len(dna) * q / 4))
        partial = dna[:cut]

        # Le prochain mouvement apres ce quart (si disponible)
        next_move = dna[cut] if cut < len(dna) else ""

        # Stocker les sous-patterns de taille 2 a 6 (fin de sequence = plus pertinent)
        for size in range(2, min(7, len(partial) + 1)):
            sub = ",".join(partial[-size:])

            conn.execute("""
                INSERT INTO smart_memory
                (symbol, timeframe, quarter, pattern, pattern_size, close_result, next_move, count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(symbol, timeframe, quarter, pattern, close_result, next_move)
                DO UPDATE SET count = count + 1
            """, (symbol, timeframe, q, sub, size, close_result, next_move))

    conn.commit()
    conn.close()


def predict(symbol: str, timeframe: str, current_moves: list, progress: float) -> dict:
    """Prediction intelligente par sequence + position.

    Retourne la prediction de cloture ET du prochain mouvement.
    """
    dna = moves_to_dna(current_moves)
    if len(dna) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    # Determiner le quart en cours
    quarter = min(4, int(progress * 4) + 1)

    conn = _get_conn()

    # --- Prediction de cloture ---
    total_hausse = 0
    total_baisse = 0
    best_pattern = ""
    best_size = 0
    total_samples = 0

    for size in range(min(6, len(dna)), 1, -1):
        sub = ",".join(dna[-size:])

        rows = conn.execute("""
            SELECT close_result, SUM(count) as total
            FROM smart_memory
            WHERE symbol = ? AND timeframe = ? AND quarter = ? AND pattern = ?
            GROUP BY close_result
        """, (symbol, timeframe, quarter, sub)).fetchall()

        total = sum(r["total"] for r in rows)

        if total >= 10:
            weight = 2 ** size

            for r in rows:
                if r["close_result"] == "HAUSSE":
                    total_hausse += r["total"] * weight
                else:
                    total_baisse += r["total"] * weight

            if not best_pattern:
                best_pattern = sub
                best_size = size
                total_samples = total

    # --- Prediction du prochain mouvement ---
    next_move_counts = {}
    for size in range(min(6, len(dna)), 1, -1):
        sub = ",".join(dna[-size:])

        rows = conn.execute("""
            SELECT next_move, SUM(count) as total
            FROM smart_memory
            WHERE symbol = ? AND timeframe = ? AND quarter = ? AND pattern = ?
                AND next_move != ''
            GROUP BY next_move
            ORDER BY total DESC
        """, (symbol, timeframe, quarter, sub)).fetchall()

        total = sum(r["total"] for r in rows)
        if total >= 10:
            weight = 2 ** size
            for r in rows:
                nm = r["next_move"]
                if nm not in next_move_counts:
                    next_move_counts[nm] = 0
                next_move_counts[nm] += r["total"] * weight
            break  # Le plus long pattern suffit pour le prochain mouvement

    conn.close()

    # Resultat cloture
    grand_total = total_hausse + total_baisse
    if grand_total == 0:
        return {"prediction": None, "message": "Pattern inconnu pour ce quart"}

    pct_hausse = round(total_hausse / grand_total * 100, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    result = {
        "prediction": "HAUSSE" if pct_hausse > pct_baisse else "BAISSE",
        "pct_hausse": pct_hausse,
        "pct_baisse": pct_baisse,
        "confidence": round(abs(pct_hausse - 50), 1),
        "best_pattern": best_pattern,
        "best_pattern_size": best_size,
        "total_samples": total_samples,
        "quarter": quarter,
        "dna": ",".join(dna),
        "source": "smart_memory",
    }

    # Prochain mouvement
    if next_move_counts:
        nm_total = sum(next_move_counts.values())
        next_moves = sorted(next_move_counts.items(), key=lambda x: -x[1])
        best_nm = next_moves[0]
        result["next_move"] = best_nm[0]
        result["next_move_pct"] = round(best_nm[1] / nm_total * 100, 1)
        result["next_move_details"] = {
            k: round(v / nm_total * 100, 1) for k, v in next_moves[:3]
        }

    return result


def backfill_smart(symbol: str, timeframe: str):
    """Remplit le dictionnaire intelligent depuis les donnees en base."""
    conn = _get_conn()

    existing = conn.execute("""
        SELECT COUNT(*) FROM smart_memory WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]

    if existing > 0:
        logger.info(f"Smart memory deja remplie ({existing} entrees)")
        conn.close()
        return

    rows = conn.execute("""
        SELECT gs.moves, cp.closed_bullish
        FROM grid_sequences gs
        LEFT JOIN close_patterns cp
            ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
        WHERE gs.symbol = ? AND gs.timeframe = ?
    """, (symbol, timeframe)).fetchall()

    conn.close()

    logger.info(f"Backfill smart memory : {len(rows)} bougies")

    for i, r in enumerate(rows):
        moves = r["moves"].split(",")
        close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        learn_candle(symbol, timeframe, moves, close_result)

        if (i + 1) % 1000 == 0:
            logger.info(f"  {i + 1}/{len(rows)}")

    # Nettoyage
    conn2 = _get_conn()
    deleted = conn2.execute("""
        DELETE FROM smart_memory WHERE symbol = ? AND timeframe = ? AND count < 3
    """, (symbol, timeframe)).rowcount
    total = conn2.execute("""
        SELECT COUNT(DISTINCT pattern) FROM smart_memory WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]
    conn2.commit()
    conn2.close()

    logger.info(f"Smart memory : {total} patterns uniques ({deleted} rares supprimes)")
