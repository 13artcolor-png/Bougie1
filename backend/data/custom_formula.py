# Formule de prediction de cloture
# Variables disponibles :
#   moves: list[str] - mouvements de grille (ex: ["DDD", "UU", "DDDDD"])
#   progress: float - progression (0.0 a 1.0)
#   candle_open, candle_high, candle_low, candle_close: float
#   prev_close: float - close bougie precedente
#
# Doit retourner : {"pct_hausse": float, "pct_baisse": float}

total_up = sum(len(m) for m in moves if m[0] == "U")
total_down = sum(len(m) for m in moves if m[0] == "D")
total = total_up + total_down

if total < 3:
    result = {"pct_hausse": 50.0, "pct_baisse": 50.0}
else:
    # --- Indicateur 1 : Ratio simple U/total ---
    ratio = total_up / total

    # --- Indicateur 2 : Poids des runs (gros runs = plus decisifs) ---
    poids_u = sum(len(m) ** 1.5 for m in moves if m[0] == "U")
    poids_d = sum(len(m) ** 1.5 for m in moves if m[0] == "D")
    total_poids = poids_u + poids_d
    ratio_poids = poids_u / total_poids if total_poids > 0 else 0.5

    # --- Indicateur 3 : Run maximum (le plus long mouvement) ---
    max_u = max((len(m) for m in moves if m[0] == "U"), default=0)
    max_d = max((len(m) for m in moves if m[0] == "D"), default=0)
    total_max = max_u + max_d
    ratio_max = max_u / total_max if total_max > 0 else 0.5

    # --- Score composite (teste sur 6674 bougies) ---
    score = 0.40 * ratio + 0.35 * ratio_poids + 0.25 * ratio_max

    # --- Confiance augmente avec la progression ---
    confiance = abs(score - 0.5) * 2
    amplitude = 30 + progress * 20

    pct_hausse = 50.0 + (score - 0.5) * 2 * amplitude
    pct_hausse = max(15, min(85, pct_hausse))
    pct_hausse = round(pct_hausse, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    result = {"pct_hausse": pct_hausse, "pct_baisse": pct_baisse}
