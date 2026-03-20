"""Dictionnaire de patterns ADN - reconnaissance par categories d'amplitude.

Chaque mouvement est categorise :
  Direction (U/D) + Amplitude (P/M/G/T)
  P = petit (1-3 cases)
  M = moyen (4-8 cases)
  G = grand (9-15 cases)
  T = tres grand (16+ cases)

Exemple :
  DDDDDDDDDDDDUUUUUDDDDDDDDDDDDDUUUUUUU
  = D12, U5, D13, U7
  = DG, UM, DG, UM

Le dictionnaire stocke ces sequences categorisees et ce qui a suivi.
La reconnaissance partielle progressive affine la prediction au fur et a mesure.
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.pattern_dna")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _amplitude_category(length: int) -> str:
    """Convertit une amplitude en categorie P/M/G/T."""
    if length <= 3:
        return "P"
    elif length <= 8:
        return "M"
    elif length <= 15:
        return "G"
    else:
        return "T"


def moves_to_dna(moves: list) -> list:
    """Convertit une liste de mouvements en sequence ADN.

    ["DDDDDDDDDDDDD", "UUUUU", "DDDDDDDDDDDDD", "UUUUUUU"]
    -> ["DG", "UM", "DG", "UM"]
    """
    dna = []
    for m in moves:
        if not m or m[0] not in ("U", "D"):
            continue
        direction = m[0]
        amplitude = len(m)
        cat = _amplitude_category(amplitude)
        dna.append(f"{direction}{cat}")
    return dna


def dna_to_string(dna: list) -> str:
    """Convertit une sequence ADN en string."""
    return ",".join(dna)


def init_dna_tables():
    """Cree les tables pour le dictionnaire ADN."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_dna (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            dna_pattern TEXT NOT NULL,
            close_result TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(symbol, timeframe, dna_pattern, close_result)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dna_lookup
        ON pattern_dna(symbol, timeframe, dna_pattern)
    """)
    conn.commit()
    conn.close()


# Initialiser au chargement
init_dna_tables()


def learn_candle(symbol: str, timeframe: str, moves: list, close_result: str):
    """Apprend une bougie dans le dictionnaire ADN.

    Stocke tous les sous-patterns de taille 2 a 8 avec le resultat de cloture.
    """
    dna = moves_to_dna(moves)
    if len(dna) < 2:
        return

    conn = _get_conn()

    # Stocker des sous-patterns de taille 2 a 8
    for size in range(2, min(9, len(dna) + 1)):
        for i in range(len(dna) - size + 1):
            sub = dna_to_string(dna[i:i + size])
            conn.execute("""
                INSERT INTO pattern_dna
                (symbol, timeframe, dna_pattern, close_result, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(symbol, timeframe, dna_pattern, close_result)
                DO UPDATE SET count = count + 1
            """, (symbol, timeframe, sub, close_result))

    # Stocker aussi le pattern complet (debut -> fin) comme "sequence complete"
    full = dna_to_string(dna)
    conn.execute("""
        INSERT INTO pattern_dna
        (symbol, timeframe, dna_pattern, close_result, count)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(symbol, timeframe, dna_pattern, close_result)
        DO UPDATE SET count = count + 1
    """, (symbol, timeframe, f"FULL:{full}", close_result))

    conn.commit()
    conn.close()


def predict_close(symbol: str, timeframe: str, current_moves: list) -> dict:
    """Predit la cloture par reconnaissance progressive.

    Teste les patterns du plus long au plus court.
    Combine les resultats avec poids exponentiel (patterns longs = plus de poids).
    """
    dna = moves_to_dna(current_moves)
    if len(dna) < 2:
        return {"prediction": None, "message": "Pas assez de mouvements"}

    conn = _get_conn()

    total_hausse = 0
    total_baisse = 0
    best_pattern = ""
    best_size = 0
    total_samples = 0

    # Tester les patterns du plus long au plus court (fin de sequence = plus recent)
    for size in range(min(8, len(dna)), 1, -1):
        # Prendre les DERNIERS elements de la sequence
        sub = dna_to_string(dna[-size:])

        rows = conn.execute("""
            SELECT close_result, SUM(count) as total
            FROM pattern_dna
            WHERE symbol = ? AND timeframe = ? AND dna_pattern = ?
            GROUP BY close_result
        """, (symbol, timeframe, sub)).fetchall()

        total = sum(r["total"] for r in rows)

        if total >= 10:
            weight = 2 ** size  # Poids exponentiel

            for r in rows:
                if r["close_result"] == "HAUSSE":
                    total_hausse += r["total"] * weight
                else:
                    total_baisse += r["total"] * weight

            if not best_pattern:
                best_pattern = sub
                best_size = size
                total_samples = total

    conn.close()

    grand_total = total_hausse + total_baisse
    if grand_total == 0:
        return {"prediction": None, "message": "Pattern ADN inconnu"}

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
        "dna": dna_to_string(dna),
        "source": "dictionnaire_adn",
    }


def backfill_dna(symbol: str, timeframe: str):
    """Remplit le dictionnaire ADN depuis les grid_sequences en base."""
    conn = _get_conn()

    existing = conn.execute("""
        SELECT COUNT(*) FROM pattern_dna WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]

    if existing > 0:
        logger.info(f"Dictionnaire ADN deja rempli ({existing} entrees)")
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

    logger.info(f"Backfill dictionnaire ADN : {len(rows)} bougies")

    for i, r in enumerate(rows):
        moves = r["moves"].split(",")
        close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        learn_candle(symbol, timeframe, moves, close_result)

        if (i + 1) % 1000 == 0:
            logger.info(f"  {i + 1}/{len(rows)} bougies")

    # Nettoyage des patterns rares
    conn2 = _get_conn()
    deleted = conn2.execute("""
        DELETE FROM pattern_dna WHERE symbol = ? AND timeframe = ? AND count < 3
    """, (symbol, timeframe)).rowcount
    conn2.commit()

    total = conn2.execute("""
        SELECT COUNT(DISTINCT dna_pattern) FROM pattern_dna WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]
    conn2.close()

    logger.info(f"Dictionnaire ADN : {total} patterns uniques ({deleted} rares supprimes)")


def get_dna_stats(symbol: str, timeframe: str) -> dict:
    """Stats du dictionnaire ADN."""
    conn = _get_conn()
    total = conn.execute("""
        SELECT COUNT(DISTINCT dna_pattern) FROM pattern_dna WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0]
    entries = conn.execute("""
        SELECT SUM(count) FROM pattern_dna WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe)).fetchone()[0] or 0
    conn.close()
    return {"total_patterns": total, "total_entries": entries}
