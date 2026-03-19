"""Controle des predictions : compare la prediction avec le resultat reel.
A chaque bougie cloturee, on verifie si la prediction etait correcte :
- Direction de depart (HAUT/BAS/NEUTRE)
- Categorie (V, Vi, IMP+, IMP-, RNG)
- Sous-categorie complete (V-debut, Vi-fin, etc.)
"""

import sqlite3
import os
from utils.logger import get_logger

logger = get_logger("rhythm.predictions")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            candle_time INTEGER NOT NULL,
            predicted_signature TEXT NOT NULL,
            predicted_category TEXT NOT NULL,
            predicted_direction TEXT NOT NULL,
            actual_signature TEXT,
            actual_category TEXT,
            actual_direction TEXT,
            direction_correct INTEGER DEFAULT 0,
            category_correct INTEGER DEFAULT 0,
            signature_correct INTEGER DEFAULT 0,
            session TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, candle_time)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_lookup
        ON predictions(symbol, timeframe, candle_time)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_stats
        ON predictions(symbol, timeframe, actual_signature)
    """)
    conn.commit()
    return conn


def _sig_to_direction(signature: str) -> str:
    """Deduit la direction de depart a partir de la signature.
    Supporte les 2 formats :
    - Ancien : Vi-debut, IMP+, V-fin, RNG
    - Nouveau : DUUD, UDDU, UUDD (sequence de 4 directions)
    """
    # Nouveau format (4 caracteres U/D)
    if len(signature) == 4 and all(c in "UD" for c in signature):
        if signature[0] == "U":
            return "HAUT"
        else:
            return "BAS"
    # Ancien format
    if signature.startswith("Vi") or signature.startswith("IMP+"):
        return "HAUT"
    elif signature.startswith("V-") or signature.startswith("IMP-"):
        return "BAS"
    return "NEUTRE"


def _sig_to_category(signature: str) -> str:
    """Extrait la categorie de la signature.
    Supporte les 2 formats :
    - Ancien : V-debut -> V
    - Nouveau : DUUD -> premiere moitie (DU)
    """
    if len(signature) == 4 and all(c in "UD" for c in signature):
        return signature[:2]  # Premiere moitie comme categorie
    return signature.split("-")[0] if "-" in signature else signature


def save_prediction(symbol: str, timeframe: str, candle_time: int,
                    predicted_signature: str, session: str = "") -> bool:
    """Sauvegarde la prediction pour la prochaine bougie (avant cloture)."""
    try:
        conn = _get_conn()
        pred_dir = _sig_to_direction(predicted_signature)
        pred_cat = _sig_to_category(predicted_signature)
        conn.execute("""
            INSERT OR IGNORE INTO predictions
            (symbol, timeframe, candle_time, predicted_signature,
             predicted_category, predicted_direction, session)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, timeframe, candle_time, predicted_signature,
              pred_cat, pred_dir, session))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde prediction: {e}")
        return False


def verify_prediction(symbol: str, timeframe: str, candle_time: int,
                      actual_signature: str) -> dict | None:
    """Verifie une prediction apres cloture de la bougie.
    Met a jour la ligne en base et retourne le resultat."""
    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT * FROM predictions
            WHERE symbol = ? AND timeframe = ? AND candle_time = ?
        """, (symbol, timeframe, candle_time)).fetchone()

        if row is None:
            conn.close()
            return None

        actual_dir = _sig_to_direction(actual_signature)
        actual_cat = _sig_to_category(actual_signature)
        pred_sig = row["predicted_signature"]
        pred_cat = row["predicted_category"]
        pred_dir = row["predicted_direction"]

        dir_ok = 1 if pred_dir == actual_dir else 0
        cat_ok = 1 if pred_cat == actual_cat else 0
        sig_ok = 1 if pred_sig == actual_signature else 0

        # Si prediction NEUTRE et resultat non-NEUTRE, direction incorrecte
        # Si resultat NEUTRE, on ne compte pas la direction
        if actual_dir == "NEUTRE" or pred_dir == "NEUTRE":
            dir_ok = -1  # -1 = non applicable

        conn.execute("""
            UPDATE predictions SET
                actual_signature = ?, actual_category = ?, actual_direction = ?,
                direction_correct = ?, category_correct = ?, signature_correct = ?
            WHERE symbol = ? AND timeframe = ? AND candle_time = ?
        """, (actual_signature, actual_cat, actual_dir,
              dir_ok, cat_ok, sig_ok,
              symbol, timeframe, candle_time))
        conn.commit()
        conn.close()

        result = {
            "predicted": pred_sig,
            "actual": actual_signature,
            "predicted_direction": pred_dir,
            "actual_direction": actual_dir,
            "direction_correct": dir_ok == 1,
            "category_correct": cat_ok == 1,
            "signature_correct": sig_ok == 1,
            "direction_na": dir_ok == -1,
        }
        logger.info(f"Prediction: {pred_sig} -> Reel: {actual_signature} | "
                     f"Dir: {'OK' if dir_ok == 1 else 'KO' if dir_ok == 0 else 'N/A'} | "
                     f"Cat: {'OK' if cat_ok else 'KO'} | Sig: {'OK' if sig_ok else 'KO'}")
        return result

    except Exception as e:
        logger.error(f"Erreur verification prediction: {e}")
        return None


def get_prediction_stats(symbol: str, timeframe: str, limit: int = 100) -> dict:
    """Statistiques de reussite des predictions."""
    conn = _get_conn()

    # Dernieres predictions verifiees
    rows = conn.execute("""
        SELECT * FROM predictions
        WHERE symbol = ? AND timeframe = ? AND actual_signature IS NOT NULL
        ORDER BY candle_time DESC LIMIT ?
    """, (symbol, timeframe, limit)).fetchall()

    conn.close()

    if not rows:
        return {"total": 0, "direction_pct": 0, "category_pct": 0,
                "signature_pct": 0, "history": []}

    total = len(rows)
    # Direction : ignorer les N/A (-1)
    dir_applicable = [r for r in rows if r["direction_correct"] >= 0]
    dir_correct = sum(1 for r in dir_applicable if r["direction_correct"] == 1)
    cat_correct = sum(1 for r in rows if r["category_correct"] == 1)
    sig_correct = sum(1 for r in rows if r["signature_correct"] == 1)

    history = [
        {
            "candle_time": r["candle_time"],
            "predicted": r["predicted_signature"],
            "actual": r["actual_signature"],
            "direction_correct": r["direction_correct"] == 1,
            "category_correct": r["category_correct"] == 1,
            "signature_correct": r["signature_correct"] == 1,
            "direction_na": r["direction_correct"] == -1,
            "session": r["session"],
        }
        for r in rows[:20]  # 20 dernieres pour l'affichage
    ]

    return {
        "total": total,
        "direction_pct": round(dir_correct / len(dir_applicable) * 100, 1) if dir_applicable else 0,
        "category_pct": round(cat_correct / total * 100, 1),
        "signature_pct": round(sig_correct / total * 100, 1),
        "direction_total": len(dir_applicable),
        "history": history,
    }
