"""Backfill automatique au demarrage.

Recupere les 99999 bougies M15 d'un actif avec toutes leurs M1
par tranches de 99999, calcule les mouvements de grille et stocke en base.
Ne recalcule pas les bougies deja en base.
"""

import MetaTrader5 as mt5
from rhythm.grid_moves import compute_grid_moves, _get_conn as get_grid_conn
from rhythm.close_predictor import save_close_pattern
from rhythm.grid_moves import save_grid_sequence
from utils.logger import get_logger

logger = get_logger("rhythm.auto_backfill")


def auto_backfill(symbol: str, timeframe: str = "M15"):
    """Backfill automatique. Ne recalcule pas ce qui est deja en base."""

    tf_map = {"M15": mt5.TIMEFRAME_M15, "M5": mt5.TIMEFRAME_M5, "M1": mt5.TIMEFRAME_M1}
    tf_seconds = {"M15": 900, "M5": 300, "M1": 60}
    tf_mt5 = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
    dur = tf_seconds.get(timeframe, 900)

    # Verifier combien de bougies sont deja en base
    conn = get_grid_conn()
    existing = conn.execute(
        "SELECT COUNT(*) FROM grid_sequences WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe)
    ).fetchone()[0]
    conn.close()

    logger.info(f"Auto-backfill {symbol} {timeframe}: {existing} bougies deja en base")

    # Recuperer les bougies M15
    logger.info(f"Recuperation des bougies {timeframe}...")
    all_candles = mt5.copy_rates_from_pos(symbol, tf_mt5, 1, 99999)
    if all_candles is None or len(all_candles) == 0:
        logger.error(f"Pas de donnees {timeframe} pour {symbol}")
        return

    total_candles = len(all_candles)
    logger.info(f"{total_candles} bougies {timeframe} recuperees")

    # Verifier quelles bougies manquent
    conn = get_grid_conn()
    existing_times = set()
    rows = conn.execute(
        "SELECT candle_time FROM grid_sequences WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe)
    ).fetchall()
    for r in rows:
        existing_times.add(r[0])
    conn.close()

    missing = [c for c in all_candles if int(c[0]) not in existing_times]
    logger.info(f"{len(missing)} bougies a traiter ({len(existing_times)} deja en base)")

    if len(missing) == 0:
        logger.info("Tout est deja en base, rien a faire")
        return

    # Recuperer les M1 par tranches de 90000
    logger.info("Recuperation des M1 par tranches...")
    m1_by_candle = {}
    tranche = 0

    while True:
        tranche += 1
        offset = (tranche - 1) * 90000
        m1_batch = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, offset, 90000)

        if m1_batch is None or len(m1_batch) == 0:
            logger.info(f"  Tranche {tranche}: pas de donnees, arret")
            break

        batch_count = len(m1_batch)
        logger.info(f"  Tranche {tranche}: {batch_count} M1")

        for m1 in m1_batch:
            t = int(m1[0])
            cs = t - (t % dur)
            if cs not in m1_by_candle:
                m1_by_candle[cs] = []
            m1_by_candle[cs].append({
                "time": t, "open": float(m1[1]), "high": float(m1[2]),
                "low": float(m1[3]), "close": float(m1[4]),
            })

        if batch_count < 1000:
            logger.info("  Fin des donnees M1")
            break

        # Limiter a 15 tranches max (~1.35M M1)
        if tranche >= 15:
            logger.info("  Limite de 15 tranches atteinte")
            break

    logger.info(f"Total: {len(m1_by_candle)} groupes M1")

    # Traiter les bougies manquantes
    saved = 0
    skipped = 0

    for candle in missing:
        cs = int(candle[0])
        o = float(candle[1])
        h = float(candle[2])
        l = float(candle[3])
        c = float(candle[4])

        micros = m1_by_candle.get(cs, [])
        if len(micros) < 5:
            skipped += 1
            continue

        micros.sort(key=lambda x: x["time"])
        moves = compute_grid_moves(micros, h, l)

        if len(moves) < 2:
            skipped += 1
            continue

        # Sauvegarder les mouvements de grille
        save_grid_sequence(symbol, timeframe, cs, moves)

        # Sauvegarder le pattern de cloture
        bullish = c > o
        save_close_pattern(symbol, timeframe, cs, moves, bullish)

        saved += 1
        if saved % 1000 == 0:
            logger.info(f"  {saved} bougies sauvegardees...")

    logger.info(f"Auto-backfill termine: {saved} nouvelles, {skipped} ignorees")
