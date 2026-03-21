# Formule de prediction de cloture - XAUUSD
# Generee le 20/03/2026 20:01
# Basee sur 6857 bougies
# Precision globale : 74.6%
# Haute confiance : 94.6% (sur 15.0% des cas)
# Validation K-Fold (5 plis) : 74.6% +/- 0.5%
# K-Fold HC : 94.6% +/- 1.4%
# Meilleur a 50% d'avancement
# Exposant optimise : 1.2
# Seuil HC : 0.3
#
# Variables disponibles :
#   moves: list[str] - mouvements de grille (ex: ["DDD", "UU", "DDDDD"])
#   progress: float - progression (0.0 a 1.0)
#   candle_open, candle_high, candle_low, candle_close: float
#   prev_close, prev_high, prev_low: float - bougie precedente
#
# Doit retourner : {"pct_hausse": float, "pct_baisse": float}

total_up = sum(len(m) for m in moves if m[0] == "U")
total_down = sum(len(m) for m in moves if m[0] == "D")
total = total_up + total_down

if total < 3:
    result = {"pct_hausse": 50.0, "pct_baisse": 50.0}
else:
    # Ratio simple U/total (poids 0.1)
    ratio = total_up / total

    # Run moyen U vs D (poids 0.1)
    lens_u = [len(m) for m in moves if m[0] == "U"]
    lens_d = [len(m) for m in moves if m[0] == "D"]
    if lens_u and lens_d:
        moy_u = sum(lens_u) / len(lens_u)
        moy_d = sum(lens_d) / len(lens_d)
        ratio_moy = moy_u / (moy_u + moy_d)
    else:
        ratio_moy = total_up / total

    # Entropie directionnelle (regularite) (poids 0.8)
    import math
    tous_lens = [len(m) for m in moves]
    if len(tous_lens) >= 3:
        moy_g = sum(tous_lens) / len(tous_lens)
        if moy_g > 0:
            var_g = sum((r - moy_g) ** 2 for r in tous_lens) / len(tous_lens)
            cv = math.sqrt(var_g) / moy_g
            reg = max(0, 1 - cv)
            entropie = 0.5 + (total_up / total - 0.5) * (1 + reg * 0.5)
            entropie = max(0.05, min(0.95, entropie))
        else:
            entropie = 0.5
    else:
        entropie = total_up / total

    # Indicateur : Recherche de meche (biais bougie precedente)
    prev_range = prev_high - prev_low
    if prev_range > 0 and progress < 0.5:
        prev_pos = (prev_close - prev_low) / prev_range
        wick_bias = 1.0 - prev_pos
        wick_weight = 0.15 * (1.0 - progress * 2)
    else:
        wick_bias = 0.5
        wick_weight = 0.0

    # Score composite (poids optimises + biais meche)
    base_score = 0.8 * entropie + 0.1 * ratio + 0.1 * ratio_moy
    score = base_score * (1.0 - wick_weight) + wick_bias * wick_weight

    # Conversion en pourcentage avec amplitude selon progression
    amplitude = 30 + progress * 20
    pct_hausse = 50.0 + (score - 0.5) * 2 * amplitude
    pct_hausse = max(15, min(85, pct_hausse))
    pct_hausse = round(pct_hausse, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    result = {"pct_hausse": pct_hausse, "pct_baisse": pct_baisse}
