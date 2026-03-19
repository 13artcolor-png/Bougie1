"""Chargement historique : classifie les anciennes bougies MT5 et remplit la base.
Usage : python -m rhythm.backfill XAUUSD M15 10000
"""

import sys
from mt5.connection import connect, disconnect
from mt5.market_data import get_candles, get_candles_from_time
from rhythm.classifier import classify_candle, TF_SECONDS
from rhythm.storage import save_signature
from utils.logger import get_logger

logger = get_logger("rhythm.backfill")


def backfill(symbol: str, timeframe: str, count: int = 1000):
    """Classifie les N dernieres bougies cloturees avec session et contexte."""
    connect()

    duration = TF_SECONDS.get(timeframe, 900)

    candles = get_candles(symbol, timeframe, count + 1)
    if candles is None:
        logger.error("Impossible de recuperer les bougies")
        disconnect()
        return

    closed = candles[:-1]
    logger.info(f"Backfill : {len(closed)} bougies {timeframe} pour {symbol}")

    saved = 0
    skipped = 0
    prev_sig = ""  # Signature de la bougie precedente (contexte)

    for i, candle in enumerate(closed):
        candle["symbol"] = symbol

        # Recuperer les micro-bougies M1 a partir du timestamp de cette bougie
        micro = get_candles_from_time(symbol, "M1", candle["time"], 20)

        if not micro or len(micro) < 2:
            prev_sig = ""
            skipped += 1
            continue

        # Filtrer : ne garder que les M1 dans la duree de la bougie
        candle_end = candle["time"] + duration
        micro_filtered = [m for m in micro
                          if m["time"] >= candle["time"] and m["time"] < candle_end]

        if len(micro_filtered) < 2:
            prev_sig = ""
            skipped += 1
            continue

        sig = classify_candle(candle, micro_filtered, timeframe)
        if sig is None:
            prev_sig = ""
            skipped += 1
            continue

        # Ajouter le contexte : signature precedente
        sig["prev_signature"] = prev_sig

        if save_signature(sig):
            saved += 1

        # Garder la signature actuelle pour la prochaine iteration
        prev_sig = sig["signature"]

        if (i + 1) % 500 == 0:
            logger.info(f"  Progression : {i + 1}/{len(closed)} ({saved} sauvegardees)")

    disconnect()
    logger.info(f"Backfill termine : {saved} sauvegardees, {skipped} ignorees")
    print(f"\nResultat : {saved} signatures sauvegardees sur {len(closed)} bougies")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    tf = sys.argv[2] if len(sys.argv) > 2 else "M15"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
    backfill(sym, tf, n)
