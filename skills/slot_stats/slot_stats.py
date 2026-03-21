"""
Skill autonome : statistiques brutes par créneau horaire TSB.

Point d'entrée : get_slot_stats(symbol, timeframe, lookback, gmt_offset)

Retourne les stats brutes de scan_offsets() pour chaque slot du jour :
  cont_perc, rev_perc, green_pct, avg_body, avg_range, samples, market_open

Aucune décision BUY/SELL — données pures pour un système externe.
"""
import sys
import os

# Permet d'importer les modules backend quand le skill est utilisé en standalone
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../backend"))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from mt5.connection import connect_mt5, disconnect_mt5
from mt5.market_data import get_candles
from engine.scanner import scan_offsets
from utils.json_helper import load_json
from utils.logger import log
from config import TRADING_CONFIG_FILE


def get_slot_stats(symbol: str, timeframe: str = "H1",
                   lookback: int = None, gmt_offset: int = None,
                   min_samples: int = 5) -> dict:
    """
    Calcule les statistiques brutes par créneau horaire pour un symbole.

    Gère la connexion MT5 en interne (acquiert et libère le lock).

    Args:
        symbol:      Symbole broker (ex: "EURUSD", "XAUUSD")
        timeframe:   "M15", "M30" ou "H1"
        lookback:    Nombre de bougies à analyser (None = valeur du trading_config)
        gmt_offset:  Fuseau horaire utilisateur (None = valeur du trading_config)
        min_samples: Nombre minimum d'échantillons par créneau

    Returns:
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "lookback": 2000,
            "gmt_offset": 1,
            "slots": [
                {
                    "session": 0,
                    "time_str": "00:00",
                    "cont_perc": 72.5,   # % continuation (plus élevé = forte tendance)
                    "cont_off": 3,        # offset optimal pour continuation
                    "rev_perc": 65.0,    # % retournement (100 - best_rev_raw)
                    "rev_off": 7,         # offset optimal pour retournement
                    "avg_body": 0.00045,  # taille corps moyen en price units
                    "avg_range": 0.00080, # range moyen (high-low) en price units
                    "green_pct": 54.2,    # % de bougies vertes sur ce créneau
                    "samples": 187,       # nombre d'échantillons disponibles
                    "market_open": True,  # marché ouvert sur ce créneau
                },
                ...
            ],
            "best_cont_session": 14,   # index du slot avec la meilleure continuation
            "best_rev_session": 9,     # index du slot avec le meilleur retournement
            "error": None              # message d'erreur si échec, sinon None
        }
    """
    # Charger les paramètres depuis le config si non fournis
    if lookback is None or gmt_offset is None:
        cfg = load_json(TRADING_CONFIG_FILE, {})
        if lookback is None:
            lookback = cfg.get("lookback", 2000)
        if gmt_offset is None:
            gmt_offset = cfg.get("gmt_offset", 0)

    result_base = {
        "symbol": symbol,
        "timeframe": timeframe,
        "lookback": lookback,
        "gmt_offset": gmt_offset,
    }

    # Connexion MT5
    account = connect_mt5()
    if not account:
        log.error(f"[SlotStats] MT5 non connecté pour {symbol} {timeframe}")
        return {**result_base, "slots": [], "best_cont_session": -1,
                "best_rev_session": -1, "error": "MT5 non connecté"}

    try:
        candles = get_candles(symbol, timeframe, lookback + 10)
    finally:
        disconnect_mt5()

    if not candles:
        log.warning(f"[SlotStats] Aucune bougie pour {symbol} {timeframe}")
        return {**result_base, "slots": [], "best_cont_session": -1,
                "best_rev_session": -1, "error": "Aucune bougie disponible"}

    # Calcul des stats (fonction pure, pas de MT5)
    scan_result = scan_offsets(
        candles=candles,
        timeframe=timeframe,
        lookback=lookback,
        min_samples=min_samples,
        gmt_offset=gmt_offset,
        symbol=symbol,
    )

    log.info(f"[SlotStats] {symbol} {timeframe}: {len(scan_result['slots'])} slots "
             f"| best_cont={scan_result['best_cont_session']} "
             f"| best_rev={scan_result['best_rev_session']}")

    return {
        **result_base,
        "slots": scan_result["slots"],
        "best_cont_session": scan_result["best_cont_session"],
        "best_rev_session": scan_result["best_rev_session"],
        "error": None,
    }
