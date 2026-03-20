"""Backtest du dictionnaire intelligent (smart_memory) sur les bougies en base."""
import sqlite3
from rhythm.smart_memory import moves_to_dna

DB_PATH = "data/signatures.db"

print("=== Backtest Smart Memory ===")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT gs.moves, cp.closed_bullish
    FROM grid_sequences gs
    LEFT JOIN close_patterns cp
        ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
    WHERE gs.symbol = 'XAUUSD' AND gs.timeframe = 'M15'
    ORDER BY gs.candle_time ASC
""").fetchall()
conn.close()

print(f"{len(rows)} bougies")

split = int(len(rows) * 0.7)
train = rows[:split]
test = rows[split:]
print(f"Train: {len(train)} | Test: {len(test)}")

# Construire le dictionnaire par quart
print("\nConstruction du dictionnaire...")
memory = {}  # "Q:pattern" -> {"HAUSSE": count, "BAISSE": count}

for r in train:
    moves = r["moves"].split(",")
    close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
    dna = moves_to_dna(moves)
    if len(dna) < 4:
        continue

    for q in range(1, 5):
        cut = max(2, int(len(dna) * q / 4))
        partial = dna[:cut]

        for size in range(2, min(7, len(partial) + 1)):
            sub = ",".join(partial[-size:])
            key = f"Q{q}:{sub}"
            if key not in memory:
                memory[key] = {"HAUSSE": 0, "BAISSE": 0}
            memory[key][close_result] += 1

print(f"Dictionnaire : {len(memory)} patterns")

# Tester
print("\nBacktest...")
results = {}
for q_name in ["Q1", "Q2", "Q3", "Q4"]:
    results[q_name] = {"ok": 0, "total": 0}

for r in test:
    moves = r["moves"].split(",")
    close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
    dna = moves_to_dna(moves)
    if len(dna) < 4:
        continue

    for q in range(1, 5):
        q_name = f"Q{q}"
        cut = max(2, int(len(dna) * q / 4))
        partial = dna[:cut]

        total_hausse = 0
        total_baisse = 0

        for size in range(min(6, len(partial)), 1, -1):
            sub = ",".join(partial[-size:])
            key = f"Q{q}:{sub}"

            if key in memory:
                counts = memory[key]
                total = counts["HAUSSE"] + counts["BAISSE"]
                if total >= 10:
                    weight = 2 ** size
                    total_hausse += counts["HAUSSE"] * weight
                    total_baisse += counts["BAISSE"] * weight

        grand_total = total_hausse + total_baisse
        if grand_total > 0:
            prediction = "HAUSSE" if total_hausse > total_baisse else "BAISSE"
            results[q_name]["total"] += 1
            if prediction == close_result:
                results[q_name]["ok"] += 1

# Resultats
print("\n=== RESULTATS ===")
print(f"{'Quart':<10} {'WR':>10} {'OK/Total':>15}")
print("-" * 40)
for q_name in ["Q1", "Q2", "Q3", "Q4"]:
    ok = results[q_name]["ok"]
    total = results[q_name]["total"]
    wr = round(ok / total * 100, 1) if total > 0 else 0
    print(f"{q_name:<10} {wr:>8.1f}% {ok:>6}/{total}")

print(f"\nComparaison :")
print(f"  Formule actuelle : Q1:~66% Q2:~50% Q3:~73% Q4:~82%")
print(f"  ADN sans position: Q1:56% Q2:58% Q3:57% Q4:58%")
print(f"  Smart memory     : voir ci-dessus")
