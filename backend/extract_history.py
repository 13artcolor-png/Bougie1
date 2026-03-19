"""Extraction de l'historique complet d'un actif en fichier texte.

Recupere les M1 par tranches, calcule les mouvements de grille,
simule la formule a chaque quart, et exporte en .txt.
"""
import MetaTrader5 as mt5
import sys
import os
from datetime import datetime, timezone, timedelta
from rhythm.grid_moves import compute_grid_moves
from rhythm.custom_formula import execute_formula

def extract_history(symbol: str, timeframe: str = "M15", output_file: str = None):
    """Extrait l'historique complet d'un actif."""

    if output_file is None:
        output_file = f"data/{symbol}_M15_history.txt"

    tf_seconds = 900  # M15

    print(f"=== Extraction {symbol} M15 ===")
    print("Connexion MT5...")
    mt5.initialize()
    mt5.login(288110, password="@Sodomie123", server="FusionMarkets-Demo")

    # Recuperer toutes les bougies M15 disponibles
    print("Recuperation des bougies M15...")
    all_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, 99999)
    if all_m15 is None or len(all_m15) == 0:
        print(f"Erreur: pas de donnees M15 pour {symbol}")
        mt5.shutdown()
        return

    print(f"{len(all_m15)} bougies M15 recuperees")

    # Recuperer les M1 par tranches
    print("Recuperation des M1 par tranches...")
    all_m1_dict = {}  # candle_start -> [micros]

    # Determiner la plage de temps
    first_m15_time = int(all_m15[0][0])
    last_m15_time = int(all_m15[-1][0])

    # Recuperer par tranches de 99999 M1
    current_end = last_m15_time + tf_seconds
    tranche = 0
    total_m1 = 0

    while True:
        tranche += 1
        # Utiliser copy_rates_from_pos par decalage au lieu de copy_rates_range
        # Calculer le nombre de M1 a sauter depuis la position 0
        # On recupere par tranches de 99999 M1
        offset = (tranche - 1) * 90000  # decalage en nombre de bougies M1
        m1_batch = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, offset, 90000)

        if m1_batch is None or len(m1_batch) == 0:
            print(f"  Tranche {tranche}: pas de donnees, arret")
            break

        batch_first = int(m1_batch[0][0])
        batch_last = int(m1_batch[-1][0])
        print(f"  Tranche {tranche}: {len(m1_batch)} M1 ({datetime.fromtimestamp(batch_first).strftime('%Y-%m-%d')} -> {datetime.fromtimestamp(batch_last).strftime('%Y-%m-%d')})")

        # Indexer par bougie M15
        for m1 in m1_batch:
            t = int(m1[0])
            cs = t - (t % tf_seconds)
            if cs not in all_m1_dict:
                all_m1_dict[cs] = []
            all_m1_dict[cs].append({
                "time": t, "open": float(m1[1]), "high": float(m1[2]),
                "low": float(m1[3]), "close": float(m1[4]),
            })

        total_m1 += len(m1_batch)

        # Verifier si on a depasse la plage
        if batch_first < first_m15_time:
            break

        if len(m1_batch) < 1000:
            print(f"  Fin des donnees M1")
            break

    print(f"Total: {total_m1} M1 indexees dans {len(all_m1_dict)} groupes")

    # Traiter chaque bougie M15
    print("Calcul des mouvements et predictions...")
    results = []
    processed = 0
    skipped = 0

    for candle in all_m15:
        cs = int(candle[0])
        o = float(candle[1])
        h = float(candle[2])
        l = float(candle[3])
        c = float(candle[4])

        micros = all_m1_dict.get(cs, [])
        if len(micros) < 5:
            skipped += 1
            continue

        micros.sort(key=lambda x: x["time"])
        moves = compute_grid_moves(micros, h, l)

        if len(moves) < 3:
            skipped += 1
            continue

        # Resultat reel
        actual = "HAUSSE" if c > o else "BAISSE"

        # Simuler la formule a chaque quart
        quarters = {}
        for q in [1, 2, 3, 4]:
            # Prendre les mouvements jusqu'a ce quart
            cut = max(1, int(len(moves) * q / 4))
            partial_moves = moves[:cut]
            progress = q / 4

            # Calculer le close approximatif a ce quart
            # Utiliser la micro-bougie la plus proche du quart
            micro_idx = max(0, min(len(micros) - 1, int(len(micros) * q / 4) - 1))
            approx_close = micros[micro_idx]["close"]
            approx_high = max(m["high"] for m in micros[:micro_idx + 1])
            approx_low = min(m["low"] for m in micros[:micro_idx + 1])

            result = execute_formula(
                partial_moves, progress,
                o, approx_high, approx_low, approx_close, o
            )

            if result and result.get("prediction"):
                pct = result["pct_hausse"] if result["prediction"] == "HAUSSE" else result["pct_baisse"]
                quarters[q] = {
                    "prediction": result["prediction"],
                    "pct": round(pct, 1),
                }
            else:
                quarters[q] = {"prediction": "", "pct": 0}

        # Formater la date
        dt = datetime.fromtimestamp(cs)
        date_str = dt.strftime("%Y-%m-%d %H:%M")

        results.append({
            "date": date_str,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "actual": actual,
            "moves": ",".join(moves),
            "q1": quarters.get(1, {}),
            "q2": quarters.get(2, {}),
            "q3": quarters.get(3, {}),
            "q4": quarters.get(4, {}),
        })

        processed += 1
        if processed % 1000 == 0:
            print(f"  {processed} bougies traitees...")

    mt5.shutdown()

    print(f"\n{processed} bougies traitees, {skipped} ignorees")

    if processed == 0:
        print("ERREUR: aucune bougie traitee")
        return

    # Ecrire le fichier au format unifie (avec H/B aux quarts)
    print(f"Ecriture dans {output_file}...")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        total = len(results)
        f.write(f"# Historique {symbol} M15 - {total} bougies\n")
        f.write(f"# Genere le {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Source : MT5 historique (H/B simules)\n")
        f.write(f"# Format unifie : mouvements U/D avec marqueurs H/B aux quarts\n")
        f.write(f"# H = prix au-dessus de l'open, B = en-dessous\n")
        f.write(f"#\n")
        f.write(f"Date | Cloture | Mouvements\n")

        for r in results:
            moves_list = r["moves"].split(",")

            # Inserer H ou B aux quarts
            enriched = []
            for i, m in enumerate(moves_list):
                enriched.append(m)
                position = (i + 1) / len(moves_list)
                for q_pct in [0.25, 0.50, 0.75]:
                    prev_pos = i / len(moves_list)
                    if prev_pos < q_pct <= position:
                        partial = moves_list[:i + 1]
                        partial_u = sum(len(m2) for m2 in partial if m2 and m2[0] == "U")
                        partial_d = sum(len(m2) for m2 in partial if m2 and m2[0] == "D")
                        enriched.append("H" if partial_u >= partial_d else "B")

            # Marqueur final
            enriched.append("H" if r["actual"] == "HAUSSE" else "B")

            f.write(f"{r['date']} | {r['actual']} | {','.join(enriched)}\n")

    print(f"\nFichier sauvegarde: {output_file}")
    print(f"{total} bougies au format unifie avec H/B")


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    extract_history(symbol)
