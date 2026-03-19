"""Backfill des patterns de cloture."""
import MetaTrader5 as mt5
from rhythm.close_predictor import init_close_table, save_close_pattern
from rhythm.grid_moves import compute_grid_moves

print("Initialisation...")
init_close_table()

mt5.initialize()
mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")

print("Recuperation des bougies M15...")
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 1, 10000)

print("Recuperation des M1...")
all_m1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 99999)

m1_by_candle = {}
for m1 in all_m1:
    t = int(m1[0])
    cs = t - (t % 900)
    if cs not in m1_by_candle:
        m1_by_candle[cs] = []
    m1_by_candle[cs].append({
        "time": t, "open": float(m1[1]), "high": float(m1[2]),
        "low": float(m1[3]), "close": float(m1[4]),
    })

saved = 0
for i, candle in enumerate(rates):
    cs = int(candle[0])
    o = float(candle[1])
    h = float(candle[2])
    l = float(candle[3])
    c = float(candle[4])

    micros = m1_by_candle.get(cs, [])
    if len(micros) < 5:
        continue

    micros.sort(key=lambda x: x["time"])
    moves = compute_grid_moves(micros, h, l)

    if len(moves) >= 2:
        bullish = c > o
        save_close_pattern("XAUUSD", "M15", cs, moves, bullish)
        saved += 1

    if (i + 1) % 2000 == 0:
        print(f"  {i + 1}/{len(rates)} ({saved})")

mt5.shutdown()
print(f"\nResultat: {saved} patterns sauvegardes")

# Test
import sqlite3
conn = sqlite3.connect("data/signatures.db")
total = conn.execute("SELECT COUNT(*) FROM close_patterns WHERE symbol='XAUUSD'").fetchone()[0]
bull = conn.execute("SELECT COUNT(*) FROM close_patterns WHERE symbol='XAUUSD' AND closed_bullish=1").fetchone()[0]
print(f"Total: {total}, Hausse: {bull} ({bull*100/total:.1f}%), Baisse: {total-bull} ({(total-bull)*100/total:.1f}%)")

# Test prediction
from rhythm.close_predictor import predict_close
tests = [
    ["DDD", "UUUUUUUUU"],
    ["UUUUU", "DDDDDDDDDD"],
    ["DDDDDDDDDD", "UUUUU", "DDDDD"],
    ["UUU", "DD", "UUUUUUUU"],
]
print("\n=== Tests ===")
for t in tests:
    result = predict_close("XAUUSD", "M15", t, 0.5)
    if result.get("prediction"):
        print(f"  {t} -> {result['prediction']} (hausse {result['pct_hausse']}% / baisse {result['pct_baisse']}%) sur {result['total_samples']} echantillons")
    else:
        print(f"  {t} -> {result.get('message')}")

conn.close()
