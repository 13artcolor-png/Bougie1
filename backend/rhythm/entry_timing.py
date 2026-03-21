"""Timing d'entree - decide quand entrer sur un signal externe.

Recoit une direction (LONG/SHORT) d'un agent externe.
Analyse la bougie en cours pour determiner :
- ENTRE MAINTENANT : le timing est bon
- ATTENDS : le timing est mauvais, attendre un meilleur prix
- N'ENTRE PAS : la bougie contredit la direction

Fournit aussi :
- Le niveau de prix d'entree optimal
- Le stop loss suggere (low/high de la bougie precedente)
"""

from utils.logger import get_logger

logger = get_logger("rhythm.entry_timing")


def analyze_entry(direction: str, current_candle: dict, last_closed: dict,
                   grid_moves: list, progress: float) -> dict:
    """Analyse le timing d'entree pour une direction donnee.

    Args:
        direction: "LONG" ou "SHORT"
        current_candle: bougie en cours (open, high, low, close)
        last_closed: bougie precedente (open, high, low, close)
        grid_moves: mouvements de grille de la bougie en cours
        progress: progression de la bougie (0.0 a 1.0)

    Returns:
        dict avec signal, entry_price, stop_loss, raison
    """
    if not current_candle or not last_closed:
        return {"signal": "ATTENDS", "raison": "Pas de donnees"}

    price_now = current_candle["close"]
    candle_open = current_candle["open"]
    candle_high = current_candle["high"]
    candle_low = current_candle["low"]
    prev_high = last_closed["high"]
    prev_low = last_closed["low"]
    prev_close = last_closed["close"]

    # Analyser les mouvements recents
    if not grid_moves or len(grid_moves) < 2:
        return {
            "signal": "ATTENDS",
            "raison": "Pas assez de mouvements",
            "entry_price": price_now,
            "stop_loss": prev_low if direction == "LONG" else prev_high,
        }

    # Dernier mouvement et sa direction
    last_move = grid_moves[-1]
    last_dir = last_move[0]  # U ou D
    last_amp = len(last_move)  # Amplitude

    # Avant-dernier mouvement
    prev_move = grid_moves[-2] if len(grid_moves) >= 2 else ""
    prev_dir = prev_move[0] if prev_move else ""

    # Ratio U/D global
    total_u = sum(len(m) for m in grid_moves if m[0] == "U")
    total_d = sum(len(m) for m in grid_moves if m[0] == "D")
    total = total_u + total_d
    ratio = total_u / total if total > 0 else 0.5

    # Position du prix vs open
    is_above_open = price_now > candle_open

    # --- LOGIQUE DE TIMING ---

    if direction == "LONG":
        stop_loss = min(prev_low, candle_low)

        # Cas 1 : le prix vient de faire un pullback (D) apres une montee -> BON TIMING
        if last_dir == "D" and prev_dir == "U" and last_amp <= 5:
            return {
                "signal": "ENTRE",
                "raison": "Pullback apres montee - bon point d'entree",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 75,
            }

        # Cas 2 : le prix est en train de monter (U) -> timing OK mais pas optimal
        if last_dir == "U":
            if last_amp <= 3:
                return {
                    "signal": "ENTRE",
                    "raison": "Debut de montee - entree acceptable",
                    "entry_price": price_now,
                    "stop_loss": stop_loss,
                    "confidence": 65,
                }
            else:
                return {
                    "signal": "ATTENDS",
                    "raison": "Montee deja avancee - attendre un pullback",
                    "entry_price": price_now,
                    "stop_loss": stop_loss,
                    "confidence": 50,
                }

        # Cas 3 : le prix descend fortement -> attendre
        if last_dir == "D" and last_amp > 5:
            return {
                "signal": "ATTENDS",
                "raison": "Forte descente en cours - attendre la fin",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 40,
            }

        # Cas 4 : la bougie contredit la direction (ratio D dominant)
        if ratio < 0.35 and progress > 0.3:
            return {
                "signal": "N_ENTRE_PAS",
                "raison": "La bougie est clairement baissiere",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 20,
            }

        # Cas par defaut
        return {
            "signal": "ATTENDS",
            "raison": "Situation neutre - pas de signal clair",
            "entry_price": price_now,
            "stop_loss": stop_loss,
            "confidence": 50,
        }

    elif direction == "SHORT":
        stop_loss = max(prev_high, candle_high)

        # Cas 1 : le prix vient de faire un rebond (U) apres une descente -> BON TIMING
        if last_dir == "U" and prev_dir == "D" and last_amp <= 5:
            return {
                "signal": "ENTRE",
                "raison": "Rebond apres descente - bon point d'entree",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 75,
            }

        # Cas 2 : le prix descend (D) -> timing OK
        if last_dir == "D":
            if last_amp <= 3:
                return {
                    "signal": "ENTRE",
                    "raison": "Debut de descente - entree acceptable",
                    "entry_price": price_now,
                    "stop_loss": stop_loss,
                    "confidence": 65,
                }
            else:
                return {
                    "signal": "ATTENDS",
                    "raison": "Descente deja avancee - attendre un rebond",
                    "entry_price": price_now,
                    "stop_loss": stop_loss,
                    "confidence": 50,
                }

        # Cas 3 : le prix monte fortement -> attendre
        if last_dir == "U" and last_amp > 5:
            return {
                "signal": "ATTENDS",
                "raison": "Forte montee en cours - attendre la fin",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 40,
            }

        # Cas 4 : la bougie contredit la direction
        if ratio > 0.65 and progress > 0.3:
            return {
                "signal": "N_ENTRE_PAS",
                "raison": "La bougie est clairement haussiere",
                "entry_price": price_now,
                "stop_loss": stop_loss,
                "confidence": 20,
            }

        return {
            "signal": "ATTENDS",
            "raison": "Situation neutre - pas de signal clair",
            "entry_price": price_now,
            "stop_loss": stop_loss,
            "confidence": 50,
        }

    return {"signal": "ATTENDS", "raison": "Direction inconnue"}
