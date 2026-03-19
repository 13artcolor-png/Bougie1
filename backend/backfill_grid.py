"""Backfill des mouvements de grille (v2 - mouvements regroupes)."""
import sqlite3
import MetaTrader5 as mt5
from rhythm.grid_moves import init_grid_tables, compute_grid_moves, save_grid_sequence

# Vider les anciennes donnees
print("Nettoyage des anciennes donnees...")
conn = sqlite3.connect("data/signatures.db")
conn.execute("DELETE FROM grid_sequences")
conn.execute("DELETE FROM grid_ngrams")
conn.commit()
conn.close()

print("Initialisation des tables...")
init_grid_tables()

print("Connexion MT5...")
mt5.initialize()
mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")

print("Recuperation des bougies M15...")
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 1, 10000)
if rates is None:
    print("Erreur")
    mt5.shutdown()
    exit()

print(f"{len(rates)} bougies")

print("Recuperation des micro-bougies M1...")
all_m1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 99999)
if all_m1 is None:
    print("Erreur M1")
    mt5.shutdown()
    exit()

print(f"{len(all_m1)} M1")

m1_by_candle = {}
for m1 in all_m1:
    t = int(m1[0])
    candle_start = t - (t % 900)
    if candle_start not in m1_by_candle:
        m1_by_candle[candle_start] = []
    m1_by_candle[candle_start].append({
        "time": t, "open": float(m1[1]), "high": float(m1[2]),
        "low": float(m1[3]), "close": float(m1[4]),
    })

saved = 0
total_moves = 0

for i, candle in enumerate(rates):
    candle_start = int(candle[0])
    h = float(candle[2])
    l = float(candle[3])

    micros = m1_by_candle.get(candle_start, [])
    if len(micros) < 5:
        continue

    micros.sort(key=lambda x: x["time"])
    moves = compute_grid_moves(micros, h, l)

    if len(moves) >= 3:
        save_grid_sequence("XAUUSD", "M15", candle_start, moves)
        saved += 1
        total_moves += len(moves)

    if (i + 1) % 2000 == 0:
        print(f"  {i + 1}/{len(rates)} ({saved} sauvegardees)")

mt5.shutdown()

avg = total_moves / saved if saved > 0 else 0
print(f"\nResultat: {saved} sequences, {avg:.1f} mouvements/bougie en moyenne")

# Stats et tests
conn = sqlite3.connect("data/signatures.db")

# Exemples de sequences
print("\nExemples de sequences:")
rows = conn.execute("SELECT moves, move_count FROM grid_sequences LIMIT 5").fetchall()
for r in rows:
    print(f"  [{r[0]}] ({r[1]} mouvements)")

r = conn.execute("SELECT COUNT(DISTINCT ngram) FROM grid_ngrams WHERE symbol='XAUUSD'").fetchone()
print(f"\nN-grams uniques: {r[0]}")

# Tests de prediction
print("\n=== Tests de prediction ===")
tests = ["D,DD", "DD,U", "DDD,U", "U,DD", "UU,D", "UUU,D", "D,UU", "DD,UU"]
for seq in tests:
    rows = conn.execute("""
        SELECT next_move, count FROM grid_ngrams
        WHERE symbol='XAUUSD' AND ngram=?
        ORDER BY count DESC
    """, (seq,)).fetchall()
    total = sum(r[1] for r in rows)
    if total >= 5:
        print(f"\n  Apres [{seq}] ({total} echantillons):")
        for r in rows[:4]:
            pct = r[1] * 100 / total
            print(f"    -> {r[0]:5s} {pct:5.1f}% ({r[1]}x)")

conn.close()
