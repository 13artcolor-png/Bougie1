# Formule de prediction de cloture
# Generee le 20/03/2026 13:19
# Basee sur 6836 bougies
# Precision globale : 74.5%
# Haute confiance : 90.7% (sur 31.6% des cas)
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
    # Indicateur : Ratio simple U/total (poids 0.89)
    ratio = total_up / total

    # Indicateur : Poids des runs (exposant 1.5) (poids 0.11)
    poids_u = sum(len(m) ** 1.5 for m in moves if m[0] == "U")
    poids_d = sum(len(m) ** 1.5 for m in moves if m[0] == "D")
    tp = poids_u + poids_d
    ratio_poids = poids_u / tp if tp > 0 else 0.5

    # Score composite (poids optimises par brute force)
    score = 0.89 * ratio + 0.11 * ratio_poids

    # Conversion en pourcentage avec amplitude selon progression
    amplitude = 30 + progress * 20
    pct_hausse = 50.0 + (score - 0.5) * 2 * amplitude
    pct_hausse = max(15, min(85, pct_hausse))
    pct_hausse = round(pct_hausse, 1)
    pct_baisse = round(100 - pct_hausse, 1)

    result = {"pct_hausse": pct_hausse, "pct_baisse": pct_baisse}