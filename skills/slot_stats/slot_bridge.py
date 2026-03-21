"""Bridge entre slot_stats et Bougie1.

Analyse les bougies par creneau horaire en utilisant les outils de Bougie1.
Genere des alertes LONG/SHORT et les envoie a B1 via l'API.

Usage :
  python slot_bridge.py BTCUSD M15
  ou
  from skills.slot_stats.slot_bridge import run_slot_analysis
"""

import sys
import os
import time
import requests
from datetime import datetime

# Permet d'importer les modules backend
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../backend"))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

B1_URL = "http://127.0.0.1:8111"


def analyze_slots(symbol: str, timeframe: str = "M15", lookback: int = 2000) -> dict:
    """Analyse les bougies par creneau horaire.

    Pour chaque heure du jour, calcule :
    - % de bougies vertes (green_pct)
    - Continuation : si la bougie precedente est verte, % que celle-ci aussi
    - Retournement : si la bougie precedente est verte, % que celle-ci soit rouge
    """
    import MetaTrader5 as mt5

    mt5.initialize()
    mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")

    tf_map = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
    rates = mt5.copy_rates_from_pos(symbol, tf_map.get(timeframe, mt5.TIMEFRAME_M15), 0, lookback)
    mt5.shutdown()

    if rates is None or len(rates) < 100:
        return {"error": "Pas assez de donnees", "slots": []}

    # Analyser par creneau horaire (broker time)
    slots = {}
    for i in range(1, len(rates)):
        candle = rates[i]
        prev = rates[i - 1]

        hour = (int(candle[0]) // 3600) % 24
        is_green = candle[4] > candle[1]  # close > open
        prev_green = prev[4] > prev[1]

        if hour not in slots:
            slots[hour] = {
                "total": 0, "green": 0,
                "cont_gg": 0, "cont_gr": 0, "cont_rr": 0, "cont_rg": 0,
                "after_green": 0, "after_red": 0,
            }

        s = slots[hour]
        s["total"] += 1
        if is_green:
            s["green"] += 1

        if prev_green:
            s["after_green"] += 1
            if is_green:
                s["cont_gg"] += 1  # Continuation verte
            else:
                s["cont_gr"] += 1  # Retournement vert->rouge
        else:
            s["after_red"] += 1
            if not is_green:
                s["cont_rr"] += 1  # Continuation rouge
            else:
                s["cont_rg"] += 1  # Retournement rouge->vert

    # Formater les resultats
    result_slots = []
    for hour in range(24):
        s = slots.get(hour, {"total": 0, "green": 0, "after_green": 0, "after_red": 0,
                              "cont_gg": 0, "cont_gr": 0, "cont_rr": 0, "cont_rg": 0})
        if s["total"] < 10:
            continue

        green_pct = round(s["green"] / s["total"] * 100, 1)
        cont_pct = 0
        rev_pct = 0
        if s["after_green"] > 0:
            cont_pct = round(s["cont_gg"] / s["after_green"] * 100, 1)
        if s["after_red"] > 0:
            rev_pct = round(s["cont_rg"] / s["after_red"] * 100, 1)

        # Biais directionnel : si green_pct > 55 -> biais haussier
        bias = "NEUTRE"
        if green_pct > 58:
            bias = "LONG"
        elif green_pct < 42:
            bias = "SHORT"

        result_slots.append({
            "hour": hour,
            "time_str": f"{hour:02d}:00",
            "green_pct": green_pct,
            "cont_pct": cont_pct,
            "rev_pct": rev_pct,
            "samples": s["total"],
            "bias": bias,
        })

    # Trouver le meilleur creneau
    best_cont = max(result_slots, key=lambda x: x["cont_pct"]) if result_slots else None
    best_rev = max(result_slots, key=lambda x: x["rev_pct"]) if result_slots else None

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "lookback": lookback,
        "slots": result_slots,
        "best_cont": best_cont,
        "best_rev": best_rev,
    }


def get_current_signal(symbol: str, timeframe: str = "M15", lookback: int = 2000) -> dict:
    """Analyse le creneau actuel et genere un signal si pertinent."""
    stats = analyze_slots(symbol, timeframe, lookback)
    if stats.get("error"):
        return stats

    # Heure actuelle (broker time = UTC+3)
    import MetaTrader5 as mt5
    mt5.initialize()
    mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")
    tick = mt5.symbol_info_tick(symbol)
    mt5.shutdown()

    if not tick:
        return {"error": "Pas de tick", "signal": None}

    broker_hour = (int(tick.time) // 3600) % 24

    # Trouver le slot actuel
    current_slot = None
    for s in stats["slots"]:
        if s["hour"] == broker_hour:
            current_slot = s
            break

    if not current_slot:
        return {"signal": None, "raison": f"Pas de donnees pour l'heure {broker_hour}"}

    # Generer le signal
    signal = None
    confidence = 0
    raison = ""

    if current_slot["bias"] == "LONG" and current_slot["green_pct"] > 55:
        signal = "LONG"
        confidence = current_slot["green_pct"]
        raison = f"Biais haussier a {broker_hour}h ({current_slot['green_pct']}% vertes)"
    elif current_slot["bias"] == "SHORT" and current_slot["green_pct"] < 45:
        signal = "SHORT"
        confidence = 100 - current_slot["green_pct"]
        raison = f"Biais baissier a {broker_hour}h ({current_slot['green_pct']}% vertes)"
    elif current_slot["cont_pct"] > 65:
        # Forte continuation : regarder la bougie precedente
        signal = "CONT"  # Signal de continuation (direction de la precedente)
        confidence = current_slot["cont_pct"]
        raison = f"Forte continuation a {broker_hour}h ({current_slot['cont_pct']}%)"

    return {
        "signal": signal,
        "confidence": confidence,
        "raison": raison,
        "current_slot": current_slot,
        "broker_hour": broker_hour,
    }


def send_alert_to_b1(symbol: str, direction: str):
    """Envoie une alerte a Bougie1 via l'API."""
    try:
        r = requests.post(f"{B1_URL}/api/alert/{symbol}", json={"direction": direction})
        result = r.json()
        print(f"  B1 repond: {result.get('signal', 'N/A')} - {result.get('raison', '')}")
        return result
    except Exception as e:
        print(f"  Erreur connexion B1: {e}")
        return None


def run_slot_analysis(symbol: str = "BTCUSD", timeframe: str = "M15"):
    """Lance l'analyse et envoie le signal a B1."""
    print(f"\n=== Slot Analysis : {symbol} {timeframe} ===")
    print(f"Heure : {datetime.now().strftime('%H:%M')}")

    signal = get_current_signal(symbol, timeframe)

    if signal.get("error"):
        print(f"Erreur : {signal['error']}")
        return

    if signal.get("signal"):
        direction = signal["signal"]
        if direction == "CONT":
            print(f"Signal CONTINUATION ({signal['confidence']}%) - {signal['raison']}")
            print("  -> La direction depend de la bougie precedente")
        else:
            print(f"Signal {direction} ({signal['confidence']}%) - {signal['raison']}")
            print(f"  -> Envoi a B1...")
            send_alert_to_b1(symbol, direction)
    else:
        print(f"Pas de signal pour ce creneau")
        if signal.get("current_slot"):
            s = signal["current_slot"]
            print(f"  Heure broker: {signal['broker_hour']}h")
            print(f"  Vertes: {s['green_pct']}% | Cont: {s['cont_pct']}% | Rev: {s['rev_pct']}%")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    tf = sys.argv[2] if len(sys.argv) > 2 else "M15"
    run_slot_analysis(sym, tf)
