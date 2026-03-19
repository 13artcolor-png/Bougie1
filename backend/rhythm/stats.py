"""Calcul des statistiques et probabilites de transition entre signatures."""

from rhythm.storage import get_transition_probs, get_stats
from utils.logger import get_logger

logger = get_logger("rhythm.stats")


def get_next_probabilities(symbol: str, timeframe: str, current_signature: str,
                           session: str = "", prev_signature: str = "") -> list:
    """Retourne les probabilites de la prochaine bougie.
    Filtres optionnels : session et signature precedente."""
    probs = get_transition_probs(
        symbol, timeframe, current_signature,
        session=session, prev_signature=prev_signature
    )
    return probs[:10]


def get_global_stats(symbol: str, timeframe: str) -> dict:
    """Retourne les stats globales pour un symbole/timeframe."""
    return get_stats(symbol, timeframe)
