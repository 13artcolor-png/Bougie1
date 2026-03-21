# Formule de prediction de cloture
# Generee le 21/03/2026 11:05
# Basee sur 6742 bougies
# Precision globale : 74.0%
# Haute confiance : 91.1% (sur 24.9% des cas)
# Meilleur a 50% d'avancement
#
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
    # Indicateur : Ratio simple U/total (poids 0.5)
    ratio = total_up / total

    # Indicateur : Run maximum U vs D (poids 0.1)
    max_u = max((len(m) for m in moves if m[0] == "U"), default=0)
    max_d = max((len(m) for m in moves if m[0] == "D"), default=0)
    tm = max_u + max_d
    ratio_max = max_u / tm if tm > 0 else 0.5

    # Indicateur : Top 3 runs de chaque cote (poids 0.07)
    runs_u = sorted([len(m) for m in moves if m[0] == "U"], reverse=True)[:3]
    runs_d = sorted([len(m) for m in moves if m[0] == "D"], reverse=True)[:3]
    st = sum(runs_u) + sum(runs_d)
    ratio_top3 = sum(runs_u) / st if st > 0 else 0.5

    # Indicateur : Run moyen U vs D (poids 0.32)
    lens_u = [len(m) for m in moves if m[0] == "U"]
    lens_d = [len(m) for m in moves if m[0] == "D"]
    if lens_u and lens_d:
        moy_u = sum(lens_u) / len(lens_u)
        moy_d = sum(lens_d) / len(lens_d)
        ratio_moy = moy_u / (moy_u + moy_d)
    else:
        ratio_moy = total_up / total

    # Score composite (poids optimises par brute force)
    score = (0.5 * ratio
             + 0.32 * ratio_moy
             + 0.1 * ratio_max
             + 0.07 * ratio_top3)

    # Conversion en pourcentage avec amplitude selon progression
    amplitude = 30 + progress * 20
    pct_hausse = 50.0 + (score - 0.5) * 2 * amplitude
    pct_hausse = max(15, min(85, pct_hausse))
    pct_hausse = round(pct_hausse, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    result = {"pct_hausse": pct_hausse, "pct_baisse": pct_baisse}