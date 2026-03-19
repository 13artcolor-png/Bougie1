"""Formule pour predire le prochain quart.

Predit si le prix va monter ou descendre entre le quart actuel et le suivant.
Formule separee de la prediction de cloture car le mouvement court terme
n'obeit pas aux memes regles.

Variables disponibles :
  - moves: list[str] - mouvements de grille jusqu'a maintenant
  - current_quarter: int - quart actuel (1, 2 ou 3)
  - price_at_open: float - prix a l'ouverture
  - price_now: float - prix actuel
  - price_high: float - high actuel
  - price_low: float - low actuel
"""

import os
from utils.logger import get_logger

logger = get_logger("rhythm.next_quarter")

FORMULA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "next_quarter_formula.py")

DEFAULT_FORMULA = '''# Formule de prediction du prochain quart
# Predit si le prix va monter ou descendre entre maintenant et le prochain quart
#
# Variables :
#   moves: list[str] - mouvements de grille
#   current_quarter: int - quart actuel (1, 2 ou 3)
#   price_at_open, price_now, price_high, price_low: float
#
# Retourner : result = {"prediction": "HAUSSE"|"BAISSE", "pct": float}

total_up = sum(len(m) for m in moves if m[0] == "U")
total_down = sum(len(m) for m in moves if m[0] == "D")
total = total_up + total_down

if total < 2:
    result = {"prediction": "HAUSSE", "pct": 50.0}
else:
    # Le dernier mouvement indique souvent la direction du prochain
    last_move = moves[-1] if moves else "U"
    last_dir = last_move[0]
    last_len = len(last_move)

    # Apres un long mouvement, tendance a continuer
    # Apres un court mouvement, tendance a inverser
    if last_len >= 5:
        # Long mouvement : continuation probable
        if last_dir == "U":
            pct = 50 + min(25, last_len * 2)
            result = {"prediction": "HAUSSE", "pct": round(pct, 1)}
        else:
            pct = 50 + min(25, last_len * 2)
            result = {"prediction": "BAISSE", "pct": round(pct, 1)}
    else:
        # Court mouvement : regarder la tendance globale
        ratio = total_up / total
        if ratio > 0.55:
            result = {"prediction": "HAUSSE", "pct": round(50 + (ratio - 0.5) * 40, 1)}
        elif ratio < 0.45:
            result = {"prediction": "BAISSE", "pct": round(50 + (0.5 - ratio) * 40, 1)}
        else:
            # Position actuelle vs open
            if price_now > price_at_open:
                result = {"prediction": "HAUSSE", "pct": 52.0}
            else:
                result = {"prediction": "BAISSE", "pct": 52.0}
'''


def get_next_quarter_formula() -> str:
    if os.path.exists(FORMULA_PATH):
        with open(FORMULA_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return DEFAULT_FORMULA


def save_next_quarter_formula(code: str) -> bool:
    try:
        os.makedirs(os.path.dirname(FORMULA_PATH), exist_ok=True)
        with open(FORMULA_PATH, "w", encoding="utf-8") as f:
            f.write(code)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde: {e}")
        return False


def predict_next_quarter(moves: list, current_quarter: int,
                          price_at_open: float, price_now: float,
                          price_high: float, price_low: float) -> dict:
    """Execute la formule de prediction du prochain quart."""
    code = get_next_quarter_formula()

    local_vars = {
        "moves": moves,
        "current_quarter": current_quarter,
        "price_at_open": price_at_open,
        "price_now": price_now,
        "price_high": price_high,
        "price_low": price_low,
        "result": {"prediction": "HAUSSE", "pct": 50.0},
    }

    try:
        exec(code, {"__builtins__": __builtins__}, local_vars)
        result = local_vars.get("result", {"prediction": "HAUSSE", "pct": 50.0})
        return {
            "prediction": result.get("prediction", "HAUSSE"),
            "pct": round(float(result.get("pct", 50)), 1),
        }
    except Exception as e:
        logger.error(f"Erreur formule next quarter: {e}")
        return {"prediction": "HAUSSE", "pct": 50.0, "error": str(e)}
