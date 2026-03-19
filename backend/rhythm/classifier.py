"""Classification des rythmes de bougies v2.

Systeme base sur le parcours reel du prix a travers la grille 4x4.

PATTERN PRINCIPAL (16 possibles) :
  Sequence de 4 directions U/D (une par case A/B/C/D).
  Ex: "DUUD" = descend en A, monte en B, monte en C, descend en D.

INTENSITE (sous-information) :
  Position du prix (ligne 1-4) a la fin de chaque case.
  1 = fort haut, 2 = haut modere, 3 = bas modere, 4 = fort bas.
  Ex: "4-2-1-3" = fin case A en ligne 4, fin B en ligne 2, etc.

Lignes 2 et 3 = zone range (mouvement modere)
Lignes 1 et 4 = biais prononce (mouvement fort)
"""

from utils.logger import get_logger

logger = get_logger("rhythm.classifier")

# Duree des timeframes en secondes
TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}


def _price_to_row(price: float, low: float, high: float) -> int:
    """Convertit un prix en ligne (1-4). 1 = haut, 4 = bas."""
    if high == low:
        return 2
    ratio = (price - low) / (high - low)
    if ratio >= 0.75:
        return 1
    elif ratio >= 0.50:
        return 2
    elif ratio >= 0.25:
        return 3
    else:
        return 4


def _time_to_col(tick_time: int, candle_start: int, duration: int) -> str:
    """Convertit un timestamp en colonne (A-D)."""
    if duration == 0:
        return "A"
    elapsed = tick_time - candle_start
    ratio = elapsed / duration
    if ratio < 0.25:
        return "A"
    elif ratio < 0.50:
        return "B"
    elif ratio < 0.75:
        return "C"
    else:
        return "D"


def _interpolate_prices(candle: dict, micro_candles: list, timeframe: str) -> list:
    """Calcule le prix approximatif a la fin de chaque case (A, B, C, D).

    Utilise les micro-bougies pour interpoler.
    Retourne [prix_fin_A, prix_fin_B, prix_fin_C, prix_fin_D].
    """
    candle_start = candle["time"]
    duration = TF_SECONDS.get(timeframe, 900)

    if not micro_candles:
        return [candle["close"]] * 4

    # Grouper les micro-bougies par case
    case_prices = {0: [], 1: [], 2: [], 3: []}  # 0=A, 1=B, 2=C, 3=D

    for mc in micro_candles:
        elapsed = mc["time"] - candle_start
        if duration > 0:
            ratio = elapsed / duration
        else:
            ratio = 0
        col_idx = min(3, int(ratio * 4))
        case_prices[col_idx].append(mc)

    # Prix a la fin de chaque case = close de la derniere micro-bougie de la case
    prices = []
    last_known_price = candle["open"]
    for i in range(4):
        if case_prices[i]:
            # Derniere micro-bougie de cette case
            last_mc = max(case_prices[i], key=lambda mc: mc["time"])
            last_known_price = last_mc["close"]
        prices.append(last_known_price)

    # La derniere case utilise le close de la bougie
    prices[3] = candle["close"]

    return prices


def classify_candle(candle: dict, micro_candles: list, timeframe: str) -> dict | None:
    """Classifie une bougie cloturee.

    Retourne un dict avec :
    - signature : ex "DUUD" (16 patterns)
    - intensity : ex "4-2-1-3" (position par case)
    - detail : signature complete "DUUD|4-2-1-3"
    + donnees pour le stockage
    """
    if not candle or not micro_candles or len(micro_candles) < 2:
        return None

    candle_open = candle["open"]
    candle_high = candle["high"]
    candle_low = candle["low"]
    candle_close = candle["close"]
    candle_start = candle["time"]
    duration = TF_SECONDS.get(timeframe, 900)

    if candle_high == candle_low:
        return None

    # Prix a la fin de chaque case
    case_prices = _interpolate_prices(candle, micro_candles, timeframe)

    # Sequence de directions (U/D par case)
    prev_price = candle_open
    directions = ""
    for price in case_prices:
        directions += "U" if price >= prev_price else "D"
        prev_price = price

    # Intensite (ligne 1-4 a la fin de chaque case)
    rows = []
    for price in case_prices:
        rows.append(_price_to_row(price, candle_low, candle_high))
    intensity = "-".join(str(r) for r in rows)

    # Signature = pattern principal
    signature = directions

    # Detail complet
    detail = f"{signature}|{intensity}"

    # Paires pour stockage
    pair_ab = directions[:2]
    pair_cd = directions[2:]

    # --- Anciens champs pour compatibilite ---
    # Trouver quand le high et le low se produisent
    high_time = candle_start
    low_time = candle_start
    best_high = -1e9
    best_low = 1e9
    for mc in micro_candles:
        if mc["high"] > best_high:
            best_high = mc["high"]
            high_time = mc["time"]
        if mc["low"] < best_low:
            best_low = mc["low"]
            low_time = mc["time"]

    high_col = _time_to_col(high_time, candle_start, duration)
    low_col = _time_to_col(low_time, candle_start, duration)
    order = "HL" if high_time <= low_time else "LH"
    open_row = _price_to_row(candle_open, candle_low, candle_high)
    close_row = _price_to_row(candle_close, candle_low, candle_high)

    # Categorie simplifiee (pour l'ancien systeme de compatibilite)
    category = directions
    timing = pair_ab

    # --- Session horaire ---
    # Le timestamp est en broker time. FusionMarkets = UTC+3 en hiver, UTC+3 en ete.
    # On centralise l'offset dans config pour pouvoir le changer facilement.
    from config import BROKER_UTC_OFFSET
    broker_hour = (candle_start // 3600) % 24
    utc_hour = (broker_hour - BROKER_UTC_OFFSET) % 24

    if 0 <= utc_hour < 8:
        session = "ASIE"
    elif 8 <= utc_hour < 13:
        session = "EUROPE"
    elif 13 <= utc_hour < 21:
        session = "US"
    else:
        session = "NUIT"

    result = {
        "signature": signature,
        "category": category,
        "timing": timing,
        "detail": detail,
        "intensity": intensity,
        "pair_ab": pair_ab,
        "pair_cd": pair_cd,
        "session": session,
        "open_row": open_row,
        "high_col": high_col,
        "low_col": low_col,
        "close_row": close_row,
        "order_type": order,
        "symbol": candle.get("symbol", ""),
        "timeframe": timeframe,
        "candle_time": candle_start,
        "candle_open": candle_open,
        "candle_high": candle_high,
        "candle_low": candle_low,
        "candle_close": candle_close,
    }

    logger.info(f"{signature} [{session}] ({detail}) pour {timeframe} a {candle_start}")
    return result
