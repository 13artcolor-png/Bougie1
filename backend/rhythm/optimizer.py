"""
============================================================
EXTRACTEUR DE FORMULE DE PREDICTION - BOUGIES U/D
============================================================
Description : Analyse un fichier .txt de bougies (format U/D),
              teste tous les indicateurs et combinaisons de poids,
              puis genere la meilleure formule prete a copier-coller.

Utilisation : python formule_extracteur.py <fichier.txt>
              ou double-cliquer puis glisser-deposer le fichier

Auteur : Claude pour Pierre (G14)
Dependances : aucune (Python standard uniquement)
============================================================
"""

import sys
import os
import itertools
import time
from datetime import datetime

# ============================================================
# CONSTANTES
# ============================================================

# Pourcentages d'avancement a tester
NIVEAUX_AVANCEMENT = [20, 25, 30, 40, 50]

# Seuil de confiance pour haute confiance
SEUIL_HAUTE_CONFIANCE = 0.2

# Minimum de ticks pour considerer une bougie
MIN_TICKS_BOUGIE = 20

# Minimum de ticks partiels pour prediction
MIN_TICKS_PARTIELS = 3

# Pas pour la recherche de poids - Phase 1 grossiere puis Phase 2 fine
PAS_POIDS_GROSSIER = 0.10
PAS_POIDS_FIN = 0.05

# Tolerance pour la somme des poids (doit faire 1.0)
TOLERANCE_POIDS = 0.02

# Nombre max d'indicateurs pour la brute force
MAX_INDICATEURS = 5


# ============================================================
# PARSER DE FICHIER
# ============================================================

def detecter_format(ligne):
    """
    Detecte le format du fichier automatiquement.
    Format A : "Date | Cloture | Mouvements" (3 colonnes, separateur ' | ')
    Format B : "Date|Open|High|...|Resultat|Mouvements" (14+ colonnes, separateur '|')
    Retourne 'A', 'B' ou None si non reconnu.
    """
    if ' | ' in ligne:
        parties = ligne.split(' | ')
        if len(parties) == 3:
            return 'A'
    if '|' in ligne:
        parties = ligne.split('|')
        if len(parties) >= 10:
            return 'B'
    return None


def extraire_donnees_ligne(ligne, fmt):
    """
    Extrait date, cloture et chaine de mouvements selon le format detecte.
    Retourne (date, cloture, chaine) ou None si la ligne n'est pas valide.
    """
    if fmt == 'A':
        parties = ligne.split(' | ')
        if len(parties) != 3:
            return None
        return parties[0].strip(), parties[1].strip().upper(), parties[2].strip()

    elif fmt == 'B':
        parties = ligne.split('|')
        if len(parties) < 10:
            return None
        # Resultat = avant-derniere colonne, Mouvements = derniere
        cloture = parties[-2].strip().upper()
        chaine = parties[-1].strip()
        date = parties[0].strip()
        return date, cloture, chaine

    return None


def parser_fichier(chemin):
    """
    Lit un fichier .txt de bougies U/D.
    Detecte automatiquement le format (2 formats supportes).
    Retourne une liste de bougies parsees.
    """
    bougies = []
    lignes_ignorees = 0
    fmt = None

    with open(chemin, 'r', encoding='utf-8') as f:
        for numero, ligne in enumerate(f, 1):
            ligne = ligne.strip()

            # Ignorer les lignes vides, commentaires, headers, separateurs
            if not ligne or ligne.startswith('#') or ligne.startswith('Date') or ligne.startswith('---'):
                continue

            # Detecter le format sur la premiere ligne de donnees
            if fmt is None:
                fmt = detecter_format(ligne)
                if fmt is None:
                    lignes_ignorees += 1
                    continue
                print(f"  Format detecte : {'Date | Cloture | Mouvements' if fmt == 'A' else 'Multi-colonnes (auto-detecte)'}")

            resultat = extraire_donnees_ligne(ligne, fmt)
            if resultat is None:
                lignes_ignorees += 1
                continue

            date, cloture, chaine = resultat

            # Valider la cloture
            if cloture not in ('HAUSSE', 'BAISSE'):
                lignes_ignorees += 1
                continue

            # Parser les groupes de mouvements + marqueurs H/B
            groupes = []
            marqueurs_quart = []  # Liste des H/B aux quarts
            position_marqueurs = []  # Position du marqueur dans la sequence

            elements = chaine.split(',')
            idx_mouvement = 0
            for g in elements:
                g = g.strip()
                if g and g[0] in ('U', 'D'):
                    groupes.append((g[0], len(g)))
                    idx_mouvement += 1
                elif g in ('H', 'B'):
                    marqueurs_quart.append(g)
                    position_marqueurs.append(idx_mouvement)

            if not groupes:
                lignes_ignorees += 1
                continue

            total_u = sum(longueur for direction, longueur in groupes if direction == 'U')
            total_d = sum(longueur for direction, longueur in groupes if direction == 'D')

            bougies.append({
                'date': date,
                'cloture': cloture,
                'groupes': groupes,
                'total_u': total_u,
                'total_d': total_d,
                'marqueurs': marqueurs_quart,
                'positions_marqueurs': position_marqueurs,
            })

    return bougies, lignes_ignorees


# ============================================================
# EXTRACTION DE DONNEES PARTIELLES
# ============================================================

def extraire_partiels(groupes, total_ticks, pct):
    """
    Simule ce qu'on verrait a pct% d'avancement de la bougie.
    Retourne les indicateurs calcules sur la portion visible.
    """
    seuil = int(total_ticks * pct / 100)
    if seuil < MIN_TICKS_PARTIELS:
        return None

    u = 0
    d = 0
    ticks = 0
    runs_u = []
    runs_d = []
    groupes_vus = []

    for direction, longueur in groupes:
        restant = seuil - ticks
        if restant <= 0:
            break
        contribution = min(longueur, restant)

        if direction == 'U':
            u += contribution
            runs_u.append(contribution)
        else:
            d += contribution
            runs_d.append(contribution)

        ticks += contribution
        groupes_vus.append((direction, contribution))

    if ticks < MIN_TICKS_PARTIELS:
        return None

    return {
        'u': u, 'd': d, 'ticks': ticks,
        'runs_u': runs_u, 'runs_d': runs_d,
        'groupes_vus': groupes_vus,
    }


# ============================================================
# CALCUL DES INDICATEURS
# ============================================================

def calculer_indicateurs(p, marqueurs=None):
    """
    Calcule les indicateurs a partir des donnees partielles.
    Retourne un dict avec chaque indicateur entre 0 et 1.
    marqueurs = liste des H/B aux quarts (optionnel)
    """
    # 1. Ratio simple U/total
    ratio = p['u'] / p['ticks']

    # 2. Poids des runs (expose 1.5 = les gros runs comptent plus)
    poids_u = sum(l ** 1.5 for l in p['runs_u'])
    poids_d = sum(l ** 1.5 for l in p['runs_d'])
    tp = poids_u + poids_d
    ratio_poids = poids_u / tp if tp > 0 else 0.5

    # 3. Run maximum
    max_u = max(p['runs_u']) if p['runs_u'] else 0
    max_d = max(p['runs_d']) if p['runs_d'] else 0
    tm = max_u + max_d
    ratio_max = max_u / tm if tm > 0 else 0.5

    # 4. Momentum recent (derniers 40% des groupes)
    groupes = p['groupes_vus']
    n = len(groupes)
    if n >= 3:
        debut = max(0, int(n * 0.6))
        recents = groupes[debut:]
        u_rec = sum(l for d, l in recents if d == 'U')
        t_rec = sum(l for _, l in recents)
        momentum = u_rec / t_rec if t_rec > 0 else 0.5
    else:
        momentum = ratio  # Pas assez de groupes, utiliser le ratio simple

    # 5. Top 3 runs de chaque cote
    top3_u = sorted(p['runs_u'], reverse=True)[:3]
    top3_d = sorted(p['runs_d'], reverse=True)[:3]
    st = sum(top3_u) + sum(top3_d)
    ratio_top3 = sum(top3_u) / st if st > 0 else 0.5

    # 6. Nombre de runs U vs D
    nu = len(p['runs_u'])
    nd = len(p['runs_d'])
    tn = nu + nd
    ratio_nb_runs = nu / tn if tn > 0 else 0.5

    # 7. Run moyen U vs D
    if p['runs_u'] and p['runs_d']:
        moy_u = sum(p['runs_u']) / len(p['runs_u'])
        moy_d = sum(p['runs_d']) / len(p['runs_d'])
        t_moy = moy_u + moy_d
        ratio_moy = moy_u / t_moy if t_moy > 0 else 0.5
    else:
        ratio_moy = ratio

    result = {
        'ratio': ratio,
        'poids': ratio_poids,
        'max': ratio_max,
        'momentum': momentum,
        'top3': ratio_top3,
        'nb_runs': ratio_nb_runs,
        'moy_runs': ratio_moy,
    }

    # 8. Score des marqueurs H/B (si disponibles)
    # Compte le nombre de H vs B dans les marqueurs visibles
    if marqueurs:
        nb_h = sum(1 for m in marqueurs if m == 'H')
        nb_b = sum(1 for m in marqueurs if m == 'B')
        total_m = nb_h + nb_b
        result['marqueurs'] = nb_h / total_m if total_m > 0 else 0.5

        # 9. Tendance des marqueurs : les derniers marqueurs comptent plus
        if total_m >= 2:
            poids_m = 0
            total_poids_m = 0
            for i, m in enumerate(marqueurs):
                w = i + 1  # Poids croissant
                total_poids_m += w
                if m == 'H':
                    poids_m += w
            result['tendance_marqueurs'] = poids_m / total_poids_m if total_poids_m > 0 else 0.5
        else:
            result['tendance_marqueurs'] = result['marqueurs']

        # 10. Coherence marqueurs/mouvements : les marqueurs confirment-ils le ratio U/D ?
        accord = abs(result['marqueurs'] - ratio)
        result['coherence'] = 1.0 - accord  # 1.0 = parfaitement coherent, 0.0 = completement oppose
    else:
        result['marqueurs'] = 0.5
        result['tendance_marqueurs'] = 0.5
        result['coherence'] = 0.5

    return result


# ============================================================
# EVALUATION D'UNE COMBINAISON DE POIDS
# ============================================================

def evaluer_poids(bougies, pct, poids_dict):
    """
    Evalue une combinaison de poids sur toutes les bougies a un % d'avancement.
    Retourne precision globale et haute confiance.
    """
    correct = 0
    total = 0
    hc_ok = 0
    hc_total = 0

    for b in bougies:
        tt = b['total_u'] + b['total_d']
        if tt < MIN_TICKS_BOUGIE:
            continue

        p = extraire_partiels(b['groupes'], tt, pct)
        if not p:
            continue

        # Extraire les marqueurs visibles a ce % d'avancement
        marqueurs_visibles = []
        if b.get('marqueurs') and b.get('positions_marqueurs'):
            nb_groupes_visibles = len(p['groupes_vus'])
            for m_val, m_pos in zip(b['marqueurs'], b['positions_marqueurs']):
                if m_pos <= nb_groupes_visibles:
                    marqueurs_visibles.append(m_val)

        ind = calculer_indicateurs(p, marqueurs_visibles if marqueurs_visibles else None)

        # Score composite (ignorer les cles absentes de ind)
        score = sum(poids_dict[k] * ind.get(k, 0.5) for k in poids_dict)

        prediction = 'HAUSSE' if score > 0.5 else 'BAISSE'
        confiance = abs(score - 0.5) * 2
        total += 1

        if prediction == b['cloture']:
            correct += 1

        if confiance > SEUIL_HAUTE_CONFIANCE:
            hc_total += 1
            if prediction == b['cloture']:
                hc_ok += 1

    if total == 0:
        return None

    return {
        'precision': round(correct / total * 100, 1),
        'hc_precision': round(hc_ok / hc_total * 100, 1) if hc_total > 0 else 0,
        'hc_pct': round(hc_total / total * 100, 1) if total > 0 else 0,
        'total': total,
    }


# ============================================================
# RECHERCHE DES POIDS OPTIMAUX
# ============================================================

def _frange(start, stop, step):
    """Range pour float"""
    vals = []
    val = start
    while val <= stop:
        vals.append(round(val, 2))
        val += step
    return vals


def _generer_combos(indicateurs, pas, tolerance):
    """Genere les combinaisons de poids qui font ~1.0"""
    n = len(indicateurs)
    valeurs = _frange(0.0, 1.0, pas)

    for combo in itertools.product(valeurs, repeat=n):
        if abs(sum(combo) - 1.0) <= tolerance:
            nb_nz = sum(1 for v in combo if v > 0)
            if nb_nz >= 2:
                yield dict(zip(indicateurs, combo))


def _evaluer_meilleur(bougies, pct, combos_gen):
    """Evalue un generateur de combinaisons et retourne le meilleur"""
    meilleur = {
        'precision': 0, 'hc_precision': 0, 'hc_pct': 0,
        'poids': {}, 'total': 0,
    }
    nb_combos = 0

    for poids_dict in combos_gen:
        nb_combos += 1
        r = evaluer_poids(bougies, pct, poids_dict)
        if r is None:
            continue

        if (r['hc_precision'] > meilleur['hc_precision'] or
            (r['hc_precision'] == meilleur['hc_precision'] and
             r['precision'] > meilleur['precision'])):
            meilleur = {
                'precision': r['precision'],
                'hc_precision': r['hc_precision'],
                'hc_pct': r['hc_pct'],
                'poids': dict(poids_dict),
                'total': r['total'],
            }

    return meilleur, nb_combos


def rechercher_meilleurs_poids(bougies, pct, indicateurs_actifs):
    """
    Recherche en 2 phases :
    Phase 1 : Scan grossier (pas de 0.10) pour trouver la zone
    Phase 2 : Affinage (pas de 0.05) autour du meilleur
    """
    # Phase 1 : scan grossier
    combos1 = _generer_combos(indicateurs_actifs, PAS_POIDS_GROSSIER, TOLERANCE_POIDS)
    meilleur, nb1 = _evaluer_meilleur(bougies, pct, combos1)

    if not meilleur['poids']:
        return meilleur, nb1

    # Phase 2 : affinage autour du meilleur (+/- 0.10)
    def _combos_affinage():
        ranges = {}
        for k in indicateurs_actifs:
            centre = meilleur['poids'].get(k, 0)
            bas = max(0.0, centre - 0.10)
            haut = min(1.0, centre + 0.10)
            ranges[k] = _frange(bas, haut, PAS_POIDS_FIN)

        for combo in itertools.product(*[ranges[k] for k in indicateurs_actifs]):
            if abs(sum(combo) - 1.0) <= TOLERANCE_POIDS:
                nb_nz = sum(1 for v in combo if v > 0)
                if nb_nz >= 2:
                    yield dict(zip(indicateurs_actifs, combo))

    meilleur2, nb2 = _evaluer_meilleur(bougies, pct, _combos_affinage())
    nb_total = nb1 + nb2

    # Garder le meilleur des deux phases
    if meilleur2['hc_precision'] > meilleur['hc_precision']:
        return meilleur2, nb_total
    elif (meilleur2['hc_precision'] == meilleur['hc_precision'] and
          meilleur2['precision'] > meilleur['precision']):
        return meilleur2, nb_total

    return meilleur, nb_total


# ============================================================
# ANALYSE DE CONTINUATION
# ============================================================

def analyser_continuation(bougies):
    """Verifie si la bougie precedente predit la suivante"""
    continuation = 0
    total = 0

    for i in range(1, len(bougies)):
        total += 1
        if bougies[i]['cloture'] == bougies[i-1]['cloture']:
            continuation += 1

    if total == 0:
        return 50.0

    return round(continuation / total * 100, 1)


# ============================================================
# GENERATION DE LA FORMULE
# ============================================================

def generer_formule(meilleur_global, stats):
    """
    Genere le code Python de la formule pret a copier-coller.
    """
    poids = meilleur_global['poids']
    pct = meilleur_global['pct']

    # Noms lisibles des indicateurs
    noms = {
        'ratio': 'Ratio simple U/total',
        'poids': 'Poids des runs (exposant 1.5)',
        'max': 'Run maximum U vs D',
        'momentum': 'Momentum recent (derniers 40%)',
        'top3': 'Top 3 runs de chaque cote',
        'nb_runs': 'Nombre de runs U vs D',
        'moy_runs': 'Run moyen U vs D',
        'marqueurs': 'Score marqueurs H/B aux quarts',
        'tendance_marqueurs': 'Tendance marqueurs (poids croissant)',
        'coherence': 'Coherence marqueurs/mouvements',
    }

    # Filtrer les poids > 0
    poids_actifs = {k: v for k, v in poids.items() if v > 0}

    # Construire le code
    lignes = []
    lignes.append("# Formule de prediction de cloture")
    lignes.append(f"# Generee le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lignes.append(f"# Basee sur {stats['nb_bougies']} bougies")
    lignes.append(f"# Precision globale : {meilleur_global['precision']}%")
    lignes.append(f"# Haute confiance : {meilleur_global['hc_precision']}% (sur {meilleur_global['hc_pct']}% des cas)")
    lignes.append(f"# Meilleur a {pct}% d'avancement")
    lignes.append("#")
    lignes.append("# Variables disponibles :")
    lignes.append("#   moves: list[str] - mouvements de grille (ex: [\"DDD\", \"UU\", \"DDDDD\"])")
    lignes.append("#   progress: float - progression (0.0 a 1.0)")
    lignes.append("#   candle_open, candle_high, candle_low, candle_close: float")
    lignes.append("#   prev_close: float - close bougie precedente")
    lignes.append("#")
    lignes.append("# Doit retourner : {\"pct_hausse\": float, \"pct_baisse\": float}")
    lignes.append("")

    lignes.append("total_up = sum(len(m) for m in moves if m[0] == \"U\")")
    lignes.append("total_down = sum(len(m) for m in moves if m[0] == \"D\")")
    lignes.append("total = total_up + total_down")
    lignes.append("")
    lignes.append("if total < 3:")
    lignes.append("    result = {\"pct_hausse\": 50.0, \"pct_baisse\": 50.0}")
    lignes.append("else:")

    # Indicateur 1 : Ratio (toujours present)
    if 'ratio' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['ratio']} (poids {poids_actifs['ratio']})")
        lignes.append("    ratio = total_up / total")
        lignes.append("")

    # Indicateur 2 : Poids des runs
    if 'poids' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['poids']} (poids {poids_actifs['poids']})")
        lignes.append("    poids_u = sum(len(m) ** 1.5 for m in moves if m[0] == \"U\")")
        lignes.append("    poids_d = sum(len(m) ** 1.5 for m in moves if m[0] == \"D\")")
        lignes.append("    tp = poids_u + poids_d")
        lignes.append("    ratio_poids = poids_u / tp if tp > 0 else 0.5")
        lignes.append("")

    # Indicateur 3 : Max run
    if 'max' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['max']} (poids {poids_actifs['max']})")
        lignes.append("    max_u = max((len(m) for m in moves if m[0] == \"U\"), default=0)")
        lignes.append("    max_d = max((len(m) for m in moves if m[0] == \"D\"), default=0)")
        lignes.append("    tm = max_u + max_d")
        lignes.append("    ratio_max = max_u / tm if tm > 0 else 0.5")
        lignes.append("")

    # Indicateur 4 : Momentum
    if 'momentum' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['momentum']} (poids {poids_actifs['momentum']})")
        lignes.append("    n = len(moves)")
        lignes.append("    debut = max(0, int(n * 0.6))")
        lignes.append("    recents = moves[debut:]")
        lignes.append("    u_rec = sum(len(m) for m in recents if m[0] == \"U\")")
        lignes.append("    t_rec = sum(len(m) for m in recents)")
        lignes.append("    momentum = u_rec / t_rec if t_rec > 0 else 0.5")
        lignes.append("")

    # Indicateur 5 : Top 3
    if 'top3' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['top3']} (poids {poids_actifs['top3']})")
        lignes.append("    runs_u = sorted([len(m) for m in moves if m[0] == \"U\"], reverse=True)[:3]")
        lignes.append("    runs_d = sorted([len(m) for m in moves if m[0] == \"D\"], reverse=True)[:3]")
        lignes.append("    st = sum(runs_u) + sum(runs_d)")
        lignes.append("    ratio_top3 = sum(runs_u) / st if st > 0 else 0.5")
        lignes.append("")

    # Indicateur 6 : Nombre de runs
    if 'nb_runs' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['nb_runs']} (poids {poids_actifs['nb_runs']})")
        lignes.append("    nu = sum(1 for m in moves if m[0] == \"U\")")
        lignes.append("    nd = sum(1 for m in moves if m[0] == \"D\")")
        lignes.append("    tn = nu + nd")
        lignes.append("    ratio_nb_runs = nu / tn if tn > 0 else 0.5")
        lignes.append("")

    # Indicateur 7 : Run moyen
    if 'moy_runs' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['moy_runs']} (poids {poids_actifs['moy_runs']})")
        lignes.append("    lens_u = [len(m) for m in moves if m[0] == \"U\"]")
        lignes.append("    lens_d = [len(m) for m in moves if m[0] == \"D\"]")
        lignes.append("    if lens_u and lens_d:")
        lignes.append("        moy_u = sum(lens_u) / len(lens_u)")
        lignes.append("        moy_d = sum(lens_d) / len(lens_d)")
        lignes.append("        ratio_moy = moy_u / (moy_u + moy_d)")
        lignes.append("    else:")
        lignes.append("        ratio_moy = total_up / total")
        lignes.append("")

    # Indicateur 8 : Score marqueurs H/B
    if 'marqueurs' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['marqueurs']} (poids {poids_actifs['marqueurs']})")
        lignes.append("    # Note: les marqueurs H/B ne sont pas dans moves en live")
        lignes.append("    # On utilise le ratio U/D comme proxy")
        lignes.append("    score_marqueurs = total_up / total")
        lignes.append("")

    # Indicateur 9 : Tendance marqueurs
    if 'tendance_marqueurs' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['tendance_marqueurs']} (poids {poids_actifs['tendance_marqueurs']})")
        lignes.append("    # Tendance recente ponderee")
        lignes.append("    n_moves = len(moves)")
        lignes.append("    if n_moves >= 2:")
        lignes.append("        pw = sum((i+1) * len(m) for i, m in enumerate(moves) if m[0] == \"U\")")
        lignes.append("        tw = sum((i+1) * len(m) for i, m in enumerate(moves))")
        lignes.append("        tendance_m = pw / tw if tw > 0 else 0.5")
        lignes.append("    else:")
        lignes.append("        tendance_m = total_up / total")
        lignes.append("")

    # Indicateur 10 : Coherence
    if 'coherence' in poids_actifs:
        lignes.append(f"    # Indicateur : {noms['coherence']} (poids {poids_actifs['coherence']})")
        lignes.append("    coherence_val = 1.0 - abs(total_up / total - 0.5) * 2")
        lignes.append("    coherence_val = max(0, min(1, coherence_val))")
        lignes.append("")

    # Score composite
    lignes.append("    # Score composite (poids optimises par brute force)")
    termes = []
    var_names = {
        'ratio': 'ratio',
        'poids': 'ratio_poids',
        'max': 'ratio_max',
        'momentum': 'momentum',
        'top3': 'ratio_top3',
        'nb_runs': 'ratio_nb_runs',
        'moy_runs': 'ratio_moy',
        'marqueurs': 'score_marqueurs',
        'tendance_marqueurs': 'tendance_m',
        'coherence': 'coherence_val',
    }

    for k, v in sorted(poids_actifs.items(), key=lambda x: -x[1]):
        termes.append(f"{v} * {var_names[k]}")

    # Formater la ligne de score sur plusieurs lignes si necessaire
    if len(termes) <= 3:
        lignes.append(f"    score = {' + '.join(termes)}")
    else:
        lignes.append(f"    score = ({termes[0]}")
        for t in termes[1:-1]:
            lignes.append(f"             + {t}")
        lignes.append(f"             + {termes[-1]})")

    lignes.append("")
    lignes.append("    # Conversion en pourcentage avec amplitude selon progression")
    lignes.append("    amplitude = 30 + progress * 20")
    lignes.append("    pct_hausse = 50.0 + (score - 0.5) * 2 * amplitude")
    lignes.append("    pct_hausse = max(15, min(85, pct_hausse))")
    lignes.append("    pct_hausse = round(pct_hausse, 1)")
    lignes.append("    pct_baisse = round(100 - pct_hausse, 1)")
    lignes.append("")
    lignes.append("    result = {\"pct_hausse\": pct_hausse, \"pct_baisse\": pct_baisse}")

    return "\n".join(lignes)


# ============================================================
# AFFICHAGE
# ============================================================

def afficher_barre(pct, largeur=40):
    """Affiche une barre de progression"""
    rempli = int(largeur * pct / 100)
    barre = '#' * rempli + '-' * (largeur - rempli)
    sys.stdout.write(f"\r  [{barre}] {pct:.0f}%")
    sys.stdout.flush()


def afficher_titre(texte):
    """Affiche un titre encadre"""
    largeur = 70
    print(f"\n{'=' * largeur}")
    print(f"  {texte}")
    print(f"{'=' * largeur}")


def afficher_sous_titre(texte):
    print(f"\n  --- {texte} ---")


# ============================================================
# MAIN
# ============================================================

def main():
    afficher_titre("EXTRACTEUR DE FORMULE DE PREDICTION")
    print("  Analyse de chaines U/D pour predire la cloture de bougie")

    # Recuperer les fichiers (un ou plusieurs)
    chemins = []

    if len(sys.argv) > 1:
        # Fichiers passes en argument (lancer.bat fichier1.txt fichier2.txt ...)
        chemins = sys.argv[1:]
    else:
        print("\n  Entrez le(s) chemin(s) des fichiers .txt :")
        print("  (un par ligne, ligne vide pour terminer)")
        print("  (glissez-deposez les fichiers ici)")
        while True:
            ligne = input("\n  > ").strip().strip('"').strip("'")
            if not ligne:
                break
            chemins.append(ligne)

    if not chemins:
        print("\n  ERREUR : Aucun fichier specifie.")
        try:
            input("\n  Appuyez sur Entree pour quitter...")
        except EOFError:
            pass
        return

    # Verifier que tous les fichiers existent
    for c in chemins:
        if not os.path.exists(c):
            print(f"\n  ERREUR : Fichier introuvable : {c}")
            try:
                input("\n  Appuyez sur Entree pour quitter...")
            except EOFError:
                pass
            return

    # Parser tous les fichiers et fusionner
    afficher_sous_titre("LECTURE DES FICHIERS")
    debut = time.time()
    bougies = []
    total_ignorees = 0

    for c in chemins:
        b, ign = parser_fichier(c)
        print(f"  {os.path.basename(c)} : {len(b)} bougies")
        bougies.extend(b)
        total_ignorees += ign

    duree = time.time() - debut
    chemin = chemins[0]  # Pour le nom du fichier de sortie

    if len(chemins) > 1:
        print(f"\n  TOTAL FUSIONNE : {len(bougies)} bougies ({len(chemins)} fichiers)")
    if total_ignorees > 0:
        print(f"  Lignes ignorees : {total_ignorees}")
    print(f"  Temps : {duree:.1f}s")

    if len(bougies) < 50:
        print(f"\n  ERREUR : Pas assez de bougies ({len(bougies)}). Minimum 50.")
        try:
            input("\n  Appuyez sur Entree pour quitter...")
        except EOFError:
            pass
        return

    # Stats de base
    nb_hausse = sum(1 for b in bougies if b['cloture'] == 'HAUSSE')
    nb_baisse = len(bougies) - nb_hausse
    taux_continuation = analyser_continuation(bougies)

    afficher_sous_titre("STATISTIQUES DU FICHIER")
    print(f"  Bougies HAUSSE : {nb_hausse} ({round(nb_hausse/len(bougies)*100, 1)}%)")
    print(f"  Bougies BAISSE : {nb_baisse} ({round(nb_baisse/len(bougies)*100, 1)}%)")
    print(f"  Taux de continuation : {taux_continuation}%")

    ticks_moy = round(sum(b['total_u'] + b['total_d'] for b in bougies) / len(bougies))
    print(f"  Ticks moyen par bougie : {ticks_moy}")

    # ============================================================
    # PHASE 1 : Test des indicateurs individuels
    # ============================================================
    afficher_titre("PHASE 1 : TEST DES INDICATEURS INDIVIDUELS")

    indicateurs_noms = ['ratio', 'poids', 'max', 'momentum', 'top3', 'nb_runs', 'moy_runs', 'marqueurs', 'tendance_marqueurs', 'coherence']
    noms_lisibles = {
        'ratio': 'Ratio U/total',
        'poids': 'Poids runs (exp 1.5)',
        'max': 'Run maximum',
        'momentum': 'Momentum recent',
        'top3': 'Top 3 runs',
        'nb_runs': 'Nb runs U vs D',
        'moy_runs': 'Run moyen U vs D',
        'marqueurs': 'Score marqueurs H/B aux quarts',
        'tendance_marqueurs': 'Tendance marqueurs (poids croissant)',
        'coherence': 'Coherence marqueurs/mouvements',
    }

    meilleurs_individuels = {}

    for pct in [20, 25, 30]:
        afficher_sous_titre(f"A {pct}% d'avancement")
        print(f"  {'Indicateur':<25} {'Precision':>10} {'HC':>10}")
        print(f"  {'-'*50}")

        resultats = []
        for ind_nom in indicateurs_noms:
            # Tester chaque indicateur seul (poids 1.0)
            poids_solo = {ind_nom: 1.0}
            r = evaluer_poids(bougies, pct, poids_solo)
            if r:
                resultats.append((ind_nom, r['precision'], r['hc_precision']))

        resultats.sort(key=lambda x: x[2], reverse=True)

        for nom, prec, hc in resultats:
            print(f"  {noms_lisibles[nom]:<25} {prec:>8.1f}% {hc:>8.1f}%")
            if nom not in meilleurs_individuels or hc > meilleurs_individuels[nom]:
                meilleurs_individuels[nom] = hc

    # Selectionner les TOP indicateurs (ceux qui font mieux que le hasard)
    indicateurs_utiles = [k for k, v in meilleurs_individuels.items() if v > 55]
    indicateurs_utiles.sort(key=lambda x: meilleurs_individuels[x], reverse=True)

    # Garder max indicateurs pour la brute force (sinon trop de combinaisons)
    if len(indicateurs_utiles) > MAX_INDICATEURS:
        indicateurs_utiles = indicateurs_utiles[:MAX_INDICATEURS]

    print(f"\n  Indicateurs retenus pour optimisation : {len(indicateurs_utiles)}")
    for ind in indicateurs_utiles:
        print(f"    - {noms_lisibles[ind]} (HC max: {meilleurs_individuels[ind]}%)")

    # ============================================================
    # PHASE 2 : Brute force des poids
    # ============================================================
    afficher_titre("PHASE 2 : RECHERCHE DES POIDS OPTIMAUX")
    print(f"  Indicateurs : {len(indicateurs_utiles)}")
    print(f"  Pas de recherche : {PAS_POIDS_GROSSIER} puis affinage {PAS_POIDS_FIN}")

    meilleur_global = None
    debut_brute = time.time()

    for i, pct in enumerate(NIVEAUX_AVANCEMENT):
        print(f"\n  Test a {pct}% d'avancement...")

        meilleur, nb_combos = rechercher_meilleurs_poids(bougies, pct, indicateurs_utiles)

        print(f"    Combinaisons testees : {nb_combos}")
        print(f"    Precision globale : {meilleur['precision']}%")
        print(f"    Haute confiance : {meilleur['hc_precision']}% (sur {meilleur['hc_pct']}% des cas)")

        poids_str = " | ".join(f"{k}={v}" for k, v in meilleur['poids'].items() if v > 0)
        print(f"    Poids : {poids_str}")

        if (meilleur_global is None or
            meilleur['hc_precision'] > meilleur_global['hc_precision'] or
            (meilleur['hc_precision'] == meilleur_global['hc_precision'] and
             meilleur['precision'] > meilleur_global['precision'])):
            meilleur_global = dict(meilleur)
            meilleur_global['pct'] = pct

    duree_brute = time.time() - debut_brute
    print(f"\n  Temps total brute force : {duree_brute:.1f}s")

    # ============================================================
    # PHASE 3 : Validation croisee (train/test split)
    # ============================================================
    afficher_titre("PHASE 3 : VALIDATION (TRAIN 70% / TEST 30%)")

    split = int(len(bougies) * 0.7)
    train = bougies[:split]
    test = bougies[split:]

    print(f"  Train : {len(train)} bougies")
    print(f"  Test  : {len(test)} bougies")

    # Evaluer la meilleure config sur train et test separement
    poids_final = meilleur_global['poids']
    pct_final = meilleur_global['pct']

    r_train = evaluer_poids(train, pct_final, poids_final)
    r_test = evaluer_poids(test, pct_final, poids_final)

    if r_train and r_test:
        print(f"\n  {'Metrique':<25} {'Train':>10} {'Test':>10} {'Ecart':>10}")
        print(f"  {'-'*55}")
        print(f"  {'Precision globale':<25} {r_train['precision']:>8.1f}% {r_test['precision']:>8.1f}% {abs(r_train['precision']-r_test['precision']):>8.1f}%")
        print(f"  {'Haute confiance':<25} {r_train['hc_precision']:>8.1f}% {r_test['hc_precision']:>8.1f}% {abs(r_train['hc_precision']-r_test['hc_precision']):>8.1f}%")

        ecart_hc = abs(r_train['hc_precision'] - r_test['hc_precision'])
        if ecart_hc < 5:
            print(f"\n  RESULTAT : Formule SOLIDE (ecart train/test < 5%)")
        elif ecart_hc < 10:
            print(f"\n  RESULTAT : Formule CORRECTE (ecart train/test < 10%)")
            print(f"  Conseil : fournir plus de donnees pour ameliorer la robustesse")
        else:
            print(f"\n  ATTENTION : Risque d'overfitting (ecart > 10%)")
            print(f"  Conseil : fournir au moins 3 jours de donnees supplementaires")
    else:
        print(f"\n  Pas assez de donnees pour valider (split trop petit)")

    # ============================================================
    # PHASE 4 : Generation de la formule
    # ============================================================
    afficher_titre("PHASE 4 : FORMULE GENEREE")

    stats = {
        'nb_bougies': len(bougies),
    }

    formule = generer_formule(meilleur_global, stats)

    print(f"\n{formule}")

    # Sauvegarder la formule dans un fichier
    if len(chemins) == 1:
        nom_base = os.path.splitext(os.path.basename(chemin))[0]
    else:
        nom_base = f"multi_{len(chemins)}fichiers_{len(bougies)}bougies"
    fichier_sortie = os.path.join(os.path.dirname(chemin), f"formule_{nom_base}.txt")

    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        f.write(formule)

    print(f"\n  Formule sauvegardee dans : {fichier_sortie}")

    # Resume final
    afficher_titre("RESUME")
    print(f"  Fichiers utilises  : {len(chemins)}")
    print(f"  Bougies analysees  : {len(bougies)}")
    print(f"  Meilleur avancement: {meilleur_global['pct']}%")
    print(f"  Precision globale  : {meilleur_global['precision']}%")
    print(f"  Haute confiance    : {meilleur_global['hc_precision']}% (sur {meilleur_global['hc_pct']}% des cas)")
    print(f"  Indicateurs utilises: {sum(1 for v in meilleur_global['poids'].values() if v > 0)}")

    poids_str = " + ".join(f"{noms_lisibles[k]} ({v})" for k, v in meilleur_global['poids'].items() if v > 0)
    print(f"  Composition : {poids_str}")

    print(f"\n  La formule est prete a etre copiee dans ton outil.")

    try:
        input("\n  Appuyez sur Entree pour quitter...")
    except EOFError:
        pass


if __name__ == '__main__':
    main()
