"""Auto-optimisation de la formule de prediction.

Utilise le moteur d'optimisation (formule_extracteur) sur les donnees en base
pour trouver la meilleure formule, la valider, et l'appliquer si meilleure.
"""

import os
import time
from utils.logger import get_logger
from rhythm.optimizer import (
    parser_fichier, rechercher_meilleurs_poids, evaluer_poids,
    generer_formule, analyser_continuation,
    NIVEAUX_AVANCEMENT, MIN_TICKS_BOUGIE
)
from rhythm.custom_formula import save_formula, get_formula

logger = get_logger("rhythm.auto_optimize")


def _export_from_db(symbol: str, timeframe: str) -> str:
    """Exporte les donnees de la base en fichier temporaire pour l'optimiseur."""
    import sqlite3
    from datetime import datetime, timedelta

    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT gs.candle_time, gs.moves, cp.closed_bullish
        FROM grid_sequences gs
        LEFT JOIN close_patterns cp
            ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
        WHERE gs.symbol = ? AND gs.timeframe = ?
        ORDER BY gs.candle_time ASC
    """, (symbol, timeframe)).fetchall()
    conn.close()

    # Ecrire le fichier temporaire
    tmp_path = os.path.join(os.path.dirname(__file__), "..", "data", f"_tmp_optimize_{symbol}.txt")

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("Date | Cloture | Mouvements\n")
        for r in rows:
            dt = datetime.fromtimestamp(r["candle_time"])
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            bullish = r["closed_bullish"]
            cloture = "HAUSSE" if bullish else "BAISSE"
            moves = r["moves"]
            move_list = moves.split(",")

            # Inserer H ou B aux quarts
            enriched = []
            for i, m in enumerate(move_list):
                enriched.append(m)
                position = (i + 1) / len(move_list)
                for q_pct in [0.25, 0.50, 0.75]:
                    prev_pos = i / len(move_list)
                    if prev_pos < q_pct <= position:
                        partial = move_list[:i + 1]
                        partial_u = sum(len(m2) for m2 in partial if m2 and m2[0] == "U")
                        partial_d = sum(len(m2) for m2 in partial if m2 and m2[0] == "D")
                        enriched.append("H" if partial_u >= partial_d else "B")
            enriched.append("H" if bullish else "B")

            f.write(f"{date_str} | {cloture} | {','.join(enriched)}\n")

    return tmp_path


def optimize_formula(symbol: str, timeframe: str = "M15") -> dict:
    """Lance l'optimisation et retourne les resultats.

    Retourne un dict avec :
    - success: bool
    - formule: str (le code Python)
    - precision: float
    - hc_precision: float
    - hc_pct: float
    - validation: dict (train/test)
    - applied: bool (si la formule a ete appliquee)
    """
    logger.info(f"Optimisation demandee pour {symbol} {timeframe}")
    debut = time.time()

    # Etape 1 : Exporter les donnees
    tmp_path = _export_from_db(symbol, timeframe)

    # Etape 2 : Parser le fichier
    bougies, ignorees = parser_fichier(tmp_path)
    logger.info(f"  {len(bougies)} bougies parsees, {ignorees} ignorees")

    if len(bougies) < 50:
        return {"success": False, "error": f"Pas assez de donnees ({len(bougies)} bougies, min 50)"}

    # Etape 3 : Phase 1 - Test des indicateurs individuels
    indicateurs_noms = ['ratio', 'poids', 'max', 'momentum', 'top3', 'nb_runs', 'moy_runs', 'dna_force', 'dna_dir_forte', 'dna_dernier_fort', 'dna_acceleration', 'dna_fin']
    meilleurs_individuels = {}

    for pct in [20, 25, 30]:
        for ind_nom in indicateurs_noms:
            poids_solo = {ind_nom: 1.0}
            r = evaluer_poids(bougies, pct, poids_solo)
            if r:
                if ind_nom not in meilleurs_individuels or r['hc_precision'] > meilleurs_individuels[ind_nom]:
                    meilleurs_individuels[ind_nom] = r['hc_precision']

    indicateurs_utiles = [k for k, v in meilleurs_individuels.items() if v > 55]
    indicateurs_utiles.sort(key=lambda x: meilleurs_individuels[x], reverse=True)

    if len(indicateurs_utiles) > 5:
        indicateurs_utiles = indicateurs_utiles[:5]

    if len(indicateurs_utiles) < 2:
        return {"success": False, "error": "Pas assez d'indicateurs utiles"}

    logger.info(f"  Indicateurs retenus : {indicateurs_utiles}")

    # Etape 4 : Phase 2 - Brute force des poids
    meilleur_global = None

    for pct in NIVEAUX_AVANCEMENT:
        meilleur, nb_combos = rechercher_meilleurs_poids(bougies, pct, indicateurs_utiles)

        if (meilleur_global is None or
            meilleur['hc_precision'] > meilleur_global['hc_precision'] or
            (meilleur['hc_precision'] == meilleur_global['hc_precision'] and
             meilleur['precision'] > meilleur_global['precision'])):
            meilleur_global = dict(meilleur)
            meilleur_global['pct'] = pct

    if not meilleur_global or not meilleur_global.get('poids'):
        return {"success": False, "error": "Aucune combinaison trouvee"}

    # Etape 5 : Phase 3 - Validation
    split = int(len(bougies) * 0.7)
    train = bougies[:split]
    test = bougies[split:]

    poids_final = meilleur_global['poids']
    pct_final = meilleur_global['pct']

    r_train = evaluer_poids(train, pct_final, poids_final)
    r_test = evaluer_poids(test, pct_final, poids_final)

    validation = {}
    if r_train and r_test:
        validation = {
            "train_precision": r_train['precision'],
            "test_precision": r_test['precision'],
            "train_hc": r_train['hc_precision'],
            "test_hc": r_test['hc_precision'],
            "ecart": round(abs(r_train['hc_precision'] - r_test['hc_precision']), 1),
            "status": "SOLIDE" if abs(r_train['hc_precision'] - r_test['hc_precision']) < 5 else
                      "CORRECT" if abs(r_train['hc_precision'] - r_test['hc_precision']) < 10 else
                      "OVERFITTING",
        }

    # Etape 6 : Phase 4 - Generer la formule
    stats = {"nb_bougies": len(bougies)}
    formule = generer_formule(meilleur_global, stats)

    duree = time.time() - debut
    logger.info(f"  Optimisation terminee en {duree:.1f}s")
    logger.info(f"  Precision: {meilleur_global['precision']}% | HC: {meilleur_global['hc_precision']}%")

    # Etape 7 : Appliquer si meilleure (pas d'overfitting)
    applied = False
    if validation.get("status") != "OVERFITTING":
        save_formula(formule)
        applied = True
        logger.info("  Formule appliquee !")
    else:
        logger.warning("  Formule NON appliquee (overfitting detecte)")

    # Nettoyer le fichier temporaire
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    return {
        "success": True,
        "formule": formule,
        "precision": meilleur_global['precision'],
        "hc_precision": meilleur_global['hc_precision'],
        "hc_pct": meilleur_global['hc_pct'],
        "pct_avancement": meilleur_global['pct'],
        "nb_bougies": len(bougies),
        "indicateurs": indicateurs_utiles,
        "poids": {k: v for k, v in meilleur_global['poids'].items() if v > 0},
        "validation": validation,
        "applied": applied,
        "duree": round(duree, 1),
    }
