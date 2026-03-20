"""Formule personnalisable pour le calcul du pourcentage de cloture.

L'utilisateur peut modifier le code Python qui calcule le % de hausse/baisse.
Le code a acces aux variables suivantes :
  - moves: list[str] - la liste des mouvements de grille (ex: ["DDD", "UU", "DDDDD"])
  - progress: float - progression de la bougie (0.0 a 1.0)
  - candle_open: float - prix d'ouverture
  - candle_high: float - prix le plus haut
  - candle_low: float - prix le plus bas
  - candle_close: float - prix actuel (close en cours)
  - prev_close: float - close de la bougie precedente

Le code doit retourner un dict : {"pct_hausse": float, "pct_baisse": float}
"""

import os
import json
from utils.logger import get_logger

logger = get_logger("rhythm.custom_formula")

FORMULA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "custom_formula.py")

# Formule par defaut (fallback si data/custom_formula.py n'existe pas)
# La vraie formule est dans data/custom_formula.py (modifiable via l'editeur)
DEFAULT_FORMULA = '''# Formule de prediction de cloture - DEFAUT
# Variables disponibles :
#   moves: list[str] - mouvements de grille (ex: ["DDD", "UU", "DDDDD"])
#   progress: float - progression (0.0 a 1.0)
#   candle_open, candle_high, candle_low, candle_close: float
#   prev_close: float - close bougie precedente
#
# Doit retourner : {"pct_hausse": float, "pct_baisse": float}

# Compter les cases haussières et baissières
total_up = sum(len(m) for m in moves if m[0] == "U")
total_down = sum(len(m) for m in moves if m[0] == "D")
total = total_up + total_down

if total == 0:
    result = {"pct_hausse": 50.0, "pct_baisse": 50.0}
else:
    # Position actuelle vs open
    if candle_close > candle_open:
        # Le prix est au-dessus de l'open
        bias = 55 + (total_up - total_down) / total * 20
    else:
        # Le prix est en-dessous de l'open
        bias = 45 - (total_down - total_up) / total * 20

    # Limiter entre 20 et 80
    bias = max(20, min(80, bias))

    # Plus la bougie avance, plus la position actuelle compte
    if progress > 0.5:
        if candle_close > candle_open:
            bias = bias * 0.5 + (50 + progress * 30) * 0.5
        else:
            bias = bias * 0.5 + (50 - progress * 30) * 0.5

    pct_hausse = round(bias, 1)
    pct_baisse = round(100 - bias, 1)
    result = {"pct_hausse": pct_hausse, "pct_baisse": pct_baisse}
'''


def get_formula() -> str:
    """Retourne le code de la formule actuelle."""
    if os.path.exists(FORMULA_PATH):
        with open(FORMULA_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return DEFAULT_FORMULA


def save_formula(code: str) -> bool:
    """Sauvegarde le code de la formule."""
    try:
        os.makedirs(os.path.dirname(FORMULA_PATH), exist_ok=True)
        with open(FORMULA_PATH, "w", encoding="utf-8") as f:
            f.write(code)
        logger.info("Formule sauvegardee")
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde formule: {e}")
        return False


def execute_formula(moves: list, progress: float,
                     candle_open: float, candle_high: float,
                     candle_low: float, candle_close: float,
                     prev_close: float) -> dict:
    """Execute la formule personnalisee et retourne le resultat."""
    code = get_formula()

    # Variables accessibles dans la formule
    local_vars = {
        "moves": moves,
        "progress": progress,
        "candle_open": candle_open,
        "candle_high": candle_high,
        "candle_low": candle_low,
        "candle_close": candle_close,
        "prev_close": prev_close,
        "result": {"pct_hausse": 50.0, "pct_baisse": 50.0},
    }

    try:
        exec(code, {"__builtins__": __builtins__}, local_vars)
        result = local_vars.get("result", {"pct_hausse": 50.0, "pct_baisse": 50.0})

        pct_h = float(result.get("pct_hausse", 50))
        pct_b = float(result.get("pct_baisse", 50))

        prediction = "HAUSSE" if pct_h > pct_b else "BAISSE"

        return {
            "prediction": prediction,
            "pct_hausse": round(pct_h, 1),
            "pct_baisse": round(pct_b, 1),
            "confidence": round(abs(pct_h - 50), 1),
        }
    except Exception as e:
        logger.error(f"Erreur execution formule: {e}")
        return {
            "prediction": None,
            "error": str(e),
            "pct_hausse": 50.0,
            "pct_baisse": 50.0,
            "confidence": 0,
        }
