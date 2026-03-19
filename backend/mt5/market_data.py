"""Recuperation des donnees de marche depuis MT5"""

import MetaTrader5 as mt5
from typing import Optional
from datetime import datetime, timezone, timedelta
from utils.logger import get_logger
from config import TIMEFRAMES

logger = get_logger("mt5.market_data")

# Mapping nom timeframe -> constante MT5
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

# Nombre de micro-bougies M1 par timeframe
MICRO_COUNT = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


def get_candles(symbol: str, timeframe: str, count: int = 25) -> Optional[list]:
    """Recupere les N dernieres bougies pour un symbole et timeframe donnes.
    Retourne une liste de dicts ou None en cas d'erreur."""
    tf = TF_MAP.get(timeframe)
    if tf is None:
        logger.error(f"Timeframe inconnu: {timeframe}")
        return None

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        logger.error(f"Pas de donnees pour {symbol} {timeframe}: {mt5.last_error()}")
        return None

    return [
        {
            "time": int(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": int(r[5]),
        }
        for r in rates
    ]


def get_micro_candles(symbol: str, timeframe: str, micro_tf: str = "M1",
                      candle_start_time: int = 0) -> Optional[list]:
    """Recupere les micro-bougies de la bougie en cours uniquement.
    candle_start_time = timestamp de debut de la bougie principale en cours.
    Pour M1/M5/etc : recupere les bougies MT5 puis filtre par candle_start_time.
    Pour S30/S15 : agrege les ticks depuis candle_start_time."""
    tf_seconds = {
        "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
        "H1": 3600, "H4": 14400, "D1": 86400,
    }
    main_seconds = tf_seconds.get(timeframe, 900)

    # Si le micro_tf est un timeframe MT5 standard (M1, M5, M15, etc.)
    if micro_tf in TF_MAP:
        micro_seconds = tf_seconds.get(micro_tf, 60)
        # Recuperer un peu plus que necessaire pour etre sur d'avoir toutes les donnees
        count = max(1, (main_seconds // micro_seconds) + 5)
        all_candles = get_candles(symbol, micro_tf, count)
        if all_candles is None:
            return None
        # Filtrer : ne garder que celles dans la duree de la bougie
        if candle_start_time > 0:
            candle_end_time = candle_start_time + main_seconds
            return [c for c in all_candles
                    if c["time"] >= candle_start_time and c["time"] < candle_end_time]
        return all_candles

    # S30 ou S15 : agreger les ticks
    # SOLUTION : utiliser copy_ticks_from avec le timestamp de la bougie converti en UTC.
    # copy_ticks_from(symbol, datetime_utc, count) retourne les ticks a partir de ce moment.
    # Les timestamps retournes sont en broker time (comme les bougies).
    interval_seconds = 30 if micro_tf == "S30" else 15

    if candle_start_time <= 0:
        return None

    # Convertir le timestamp broker en datetime UTC pour copy_ticks_from
    from_dt = datetime.fromtimestamp(candle_start_time, tz=timezone.utc)
    # Recuperer assez de ticks pour couvrir toute la bougie (60 ticks/seconde max)
    max_ticks = main_seconds * 20
    ticks = mt5.copy_ticks_from(symbol, from_dt, max_ticks, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        logger.error(f"Pas de ticks pour {symbol}: {mt5.last_error()}")
        return None

    # Agreger les ticks en bougies de interval_seconds
    candles = []
    current_bucket = None

    for tick in ticks:
        tick_time = int(tick[0])
        tick_bid = float(tick[1])
        bucket = tick_time - (tick_time % interval_seconds)

        if bucket != current_bucket:
            current_bucket = bucket
            candles.append({
                "time": bucket,
                "open": tick_bid,
                "high": tick_bid,
                "low": tick_bid,
                "close": tick_bid,
                "volume": 1,
            })
        else:
            c = candles[-1]
            if tick_bid > c["high"]:
                c["high"] = tick_bid
            if tick_bid < c["low"]:
                c["low"] = tick_bid
            c["close"] = tick_bid
            c["volume"] += 1

    return candles


def get_candles_from_time(symbol: str, timeframe: str, from_time: int, count: int = 20) -> Optional[list]:
    """Recupere des bougies a partir d'un timestamp specifique (pour l'historique).
    from_time = timestamp broker time.
    Utilise copy_rates_range pour recuperer les bougies dans une plage de temps."""
    tf = TF_MAP.get(timeframe)
    if tf is None:
        return None
    tf_seconds = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800,
                  "H1": 3600, "H4": 14400, "D1": 86400}
    micro_dur = tf_seconds.get(timeframe, 60)
    # Plage : du debut de la bougie jusqu'a la fin + marge
    dt_from = datetime.fromtimestamp(from_time, tz=timezone.utc)
    dt_to = datetime.fromtimestamp(from_time + count * micro_dur + 60, tz=timezone.utc)
    rates = mt5.copy_rates_range(symbol, tf, dt_from, dt_to)
    if rates is None or len(rates) == 0:
        return None
    return [
        {
            "time": int(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": int(r[5]),
        }
        for r in rates
    ]


def get_current_tick(symbol: str) -> Optional[dict]:
    """Recupere le tick courant pour un symbole"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Pas de tick pour {symbol}: {mt5.last_error()}")
        return None

    return {
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "last": float(tick.last),
        "time": int(tick.time),
    }


def get_symbols() -> list:
    """Recupere la liste des symboles disponibles sur le broker"""
    symbols = mt5.symbols_get()
    if symbols is None:
        logger.error(f"Impossible de recuperer les symboles: {mt5.last_error()}")
        return []

    # Filtrer les symboles visibles et tries par nom
    result = []
    for s in symbols:
        if s.visible:
            result.append({
                "name": s.name,
                "description": s.description,
                "digits": s.digits,
            })
    result.sort(key=lambda x: x["name"])
    return result
