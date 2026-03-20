"""Backtest du dictionnaire ADN sur les 6600+ bougies en base.

Pour chaque bougie, on simule la prediction ADN a chaque quart
et on compare avec le resultat reel.
"""
import sqlite3
import os
from rhythm.pattern_dna import moves_to_dna, dna_to_string, init_dna_tables

DB_PATH = os.path.join("data", "signatures.db")

print("=== Backtest Dictionnaire ADN ===")

# Recuperer toutes les bougies
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT gs.candle_time, gs.moves, cp.closed_bullish
    FROM grid_sequences gs
    LEFT JOIN close_patterns cp
        ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
    WHERE gs.symbol = 'XAUUSD' AND gs.timeframe = 'M15'
    ORDER BY gs.candle_time ASC
""").fetchall()

conn.close()

print(f"{len(rows)} bougies recuperees")

# Phase 1 : Construire le dictionnaire progressivement
# On utilise les N premieres bougies pour apprendre, puis on teste sur les suivantes
# Split : 70% apprentissage, 30% test

split = int(len(rows) * 0.7)
train = rows[:split]
test = rows[split:]

print(f"Train : {len(train)} bougies")
print(f"Test  : {len(test)} bougies")

# Construire le dictionnaire depuis le train
print("\nConstruction du dictionnaire depuis le train...")
dna_dict = {}  # pattern -> {"HAUSSE": count, "BAISSE": count}

for r in train:
    moves = r["moves"].split(",")
    close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
    dna = moves_to_dna(moves)

    if len(dna) < 2:
        continue

    # Stocker les sous-patterns de taille 2 a 8
    for size in range(2, min(9, len(dna) + 1)):
        for i in range(len(dna) - size + 1):
            sub = dna_to_string(dna[i:i + size])
            if sub not in dna_dict:
                dna_dict[sub] = {"HAUSSE": 0, "BAISSE": 0}
            dna_dict[sub][close_result] += 1

print(f"Dictionnaire : {len(dna_dict)} patterns uniques")

# Phase 2 : Tester sur les 30% restantes
print("\nBacktest sur le test set...")

results = {"Q1": {"ok": 0, "total": 0}, "Q2": {"ok": 0, "total": 0},
           "Q3": {"ok": 0, "total": 0}, "Q4": {"ok": 0, "total": 0}}

for r in test:
    moves = r["moves"].split(",")
    close_result = "HAUSSE" if r["closed_bullish"] else "BAISSE"
    dna = moves_to_dna(moves)

    if len(dna) < 4:
        continue

    # Tester a chaque quart
    for q, q_name in [(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]:
        cut = max(2, int(len(dna) * q / 4))
        partial_dna = dna[:cut]

        # Chercher le pattern le plus long qui matche (fin de sequence)
        total_hausse = 0
        total_baisse = 0

        for size in range(min(8, len(partial_dna)), 1, -1):
            sub = dna_to_string(partial_dna[-size:])

            if sub in dna_dict:
                counts = dna_dict[sub]
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

# Afficher les resultats
print("\n=== RESULTATS BACKTEST ADN ===")
print(f"{'Quart':<10} {'WR':>10} {'OK/Total':>15}")
print("-" * 40)

for q_name in ["Q1", "Q2", "Q3", "Q4"]:
    ok = results[q_name]["ok"]
    total = results[q_name]["total"]
    wr = round(ok / total * 100, 1) if total > 0 else 0
    print(f"{q_name:<10} {wr:>8.1f}% {ok:>6}/{total}")

# Comparaison avec la formule actuelle
print("\n=== COMPARAISON ===")
print(f"Formule actuelle (live) : Q1:~66% Q2:~50% Q3:~73% Q4:~82%")
print(f"Dictionnaire ADN        : Q1:{round(results['Q1']['ok']/results['Q1']['total']*100,1) if results['Q1']['total'] else 0}% Q2:{round(results['Q2']['ok']/results['Q2']['total']*100,1) if results['Q2']['total'] else 0}% Q3:{round(results['Q3']['ok']/results['Q3']['total']*100,1) if results['Q3']['total'] else 0}% Q4:{round(results['Q4']['ok']/results['Q4']['total']*100,1) if results['Q4']['total'] else 0}%")

# Test avec differentes categories d'amplitude
print("\n=== TEST SENSIBILITE AUX SEUILS ===")
for seuils in [(2, 5, 10), (3, 8, 15), (4, 10, 20), (2, 6, 12)]:
    # Recalculer avec des seuils differents
    p, m, g = seuils
    def alt_cat(length):
        if length <= p: return "P"
        elif length <= m: return "M"
        elif length <= g: return "G"
        else: return "T"

    # Reconstruire le dictionnaire
    alt_dict = {}
    for r in train:
        moves_list = r["moves"].split(",")
        close_r = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        alt_dna = []
        for mv in moves_list:
            mv = mv.strip()
            if mv and mv[0] in ("U", "D"):
                alt_dna.append(f"{mv[0]}{alt_cat(len(mv))}")
        if len(alt_dna) < 2:
            continue
        for size in range(2, min(7, len(alt_dna) + 1)):
            for i in range(len(alt_dna) - size + 1):
                sub = ",".join(alt_dna[i:i + size])
                if sub not in alt_dict:
                    alt_dict[sub] = {"HAUSSE": 0, "BAISSE": 0}
                alt_dict[sub][close_r] += 1

    # Tester Q4 seulement pour la comparaison rapide
    q4_ok = 0
    q4_total = 0
    for r in test:
        moves_list = r["moves"].split(",")
        close_r = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        alt_dna = []
        for mv in moves_list:
            mv = mv.strip()
            if mv and mv[0] in ("U", "D"):
                alt_dna.append(f"{mv[0]}{alt_cat(len(mv))}")
        if len(alt_dna) < 4:
            continue
        th = 0
        tb = 0
        for size in range(min(6, len(alt_dna)), 1, -1):
            sub = ",".join(alt_dna[-size:])
            if sub in alt_dict:
                c = alt_dict[sub]
                t = c["HAUSSE"] + c["BAISSE"]
                if t >= 10:
                    w = 2 ** size
                    th += c["HAUSSE"] * w
                    tb += c["BAISSE"] * w
        if th + tb > 0:
            pred = "HAUSSE" if th > tb else "BAISSE"
            q4_total += 1
            if pred == close_r:
                q4_ok += 1

    wr = round(q4_ok / q4_total * 100, 1) if q4_total > 0 else 0
    print(f"  Seuils P<={p} M<={m} G<={g} T>{g} : Q4 WR = {wr}% ({q4_ok}/{q4_total}) | {len(alt_dict)} patterns")
