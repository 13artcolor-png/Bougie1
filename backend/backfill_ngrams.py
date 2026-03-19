"""Backfill des micro-sequences et n-grams depuis l'historique MT5."""
import MetaTrader5 as mt5
from rhythm.micro_predict import init_tables, compute_sequence, save_sequence_and_ngrams

print("Initialisation des tables...")
init_tables()

print("Connexion MT5...")
mt5.initialize()
mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")

# Recuperer 10000 bougies M15 cloturees
print("Recuperation des bougies M15...")
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 1, 10000)
if rates is None:
    print("Erreur: pas de donnees")
    mt5.shutdown()
    exit()

print(f"{len(rates)} bougies recuperees")

# Pour chaque bougie, recuperer ses micro-bougies M1 et calculer la sequence
saved = 0
skipped = 0

# Recuperer TOUTES les M1 d'un coup (plus efficace)
print("Recuperation des micro-bougies M1...")
all_m1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 99999)
if all_m1 is None:
    print("Erreur: pas de M1")
    mt5.shutdown()
    exit()

print(f"{len(all_m1)} micro-bougies M1 recuperees")

# Indexer les M1 par tranche de 15 minutes
m1_by_candle = {}
for m1 in all_m1:
    t = int(m1[0])
    # Trouver la bougie M15 a laquelle cette M1 appartient
    candle_start = t - (t % 900)
    if candle_start not in m1_by_candle:
        m1_by_candle[candle_start] = []
    m1_by_candle[candle_start].append({
        "time": t,
        "open": float(m1[1]),
        "high": float(m1[2]),
        "low": float(m1[3]),
        "close": float(m1[4]),
    })

print(f"{len(m1_by_candle)} groupes M1 indexes")

# Traiter chaque bougie M15
for i, candle in enumerate(rates):
    candle_start = int(candle[0])
    h = float(candle[2])
    l = float(candle[3])

    micros = m1_by_candle.get(candle_start, [])
    if len(micros) < 5:
        skipped += 1
        continue

    # Trier par temps
    micros.sort(key=lambda x: x["time"])

    # Calculer la sequence
    seq = compute_sequence(micros, h, l)
    if len(seq) < 4:
        skipped += 1
        continue

    threshold = (h - l) * 0.05

    save_sequence_and_ngrams("XAUUSD", "M15", candle_start, seq, threshold)
    saved += 1

    if (i + 1) % 1000 == 0:
        print(f"  Progression: {i + 1}/{len(rates)} ({saved} sauvegardees)")

mt5.shutdown()
print(f"\nResultat: {saved} sequences sauvegardees, {skipped} ignorees")

# Stats sur les n-grams
import sqlite3
conn = sqlite3.connect("data/signatures.db")
r = conn.execute("SELECT COUNT(*) FROM micro_sequences").fetchone()
print(f"Sequences en base: {r[0]}")
r = conn.execute("SELECT COUNT(*) FROM ngrams WHERE symbol='XAUUSD'").fetchone()
print(f"N-grams en base: {r[0]}")
r = conn.execute("SELECT COUNT(DISTINCT ngram) FROM ngrams WHERE symbol='XAUUSD'").fetchone()
print(f"N-grams uniques: {r[0]}")

# Top 10 n-grams les plus frequents
print("\nTop 10 n-grams:")
rows = conn.execute("""
    SELECT ngram, next_move, count FROM ngrams
    WHERE symbol='XAUUSD'
    ORDER BY count DESC LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r[0]} -> {r[1]}  ({r[2]}x)")

conn.close()
