"""Reference des 16 patterns possibles.

Chaque pattern est une sequence de 4 directions U/D (une par case A/B/C/D).
U = le prix monte dans cette case
D = le prix descend dans cette case
"""

PATTERNS = {
    "UUUU": {
        "nom": "Montee continue",
        "description": "Le prix monte du debut a la fin sans interruption",
        "direction": "HAUSSIER",
    },
    "UUUD": {
        "nom": "Montee puis chute finale",
        "description": "Monte pendant 3/4 de la bougie puis redescend en fin",
        "direction": "HAUSSIER",
    },
    "UUDU": {
        "nom": "Montee, correction, reprise",
        "description": "Monte, corrige en C puis remonte en D",
        "direction": "HAUSSIER",
    },
    "UUDD": {
        "nom": "V inverse (monte puis descend)",
        "description": "Monte en premiere moitie puis redescend en deuxieme",
        "direction": "BAISSIER",
    },
    "UDUU": {
        "nom": "Montee, creux B, reprise",
        "description": "Monte en A, creux en B, puis remonte en C et D",
        "direction": "HAUSSIER",
    },
    "UDDU": {
        "nom": "Zigzag montant",
        "description": "Monte, descend, descend, remonte - finit en hausse",
        "direction": "HAUSSIER",
    },
    "UDDD": {
        "nom": "Pic initial puis chute",
        "description": "Monte en A puis descend tout le reste de la bougie",
        "direction": "BAISSIER",
    },
    "UDUD": {
        "nom": "Zigzag neutre",
        "description": "Alterne monte/descend - mouvement indecis",
        "direction": "NEUTRE",
    },
    "DUUU": {
        "nom": "Creux initial puis montee",
        "description": "Descend en A puis monte tout le reste de la bougie",
        "direction": "HAUSSIER",
    },
    "DUUD": {
        "nom": "V classique (descend puis remonte puis rechute)",
        "description": "Descend en A, remonte en B et C, rechute en D",
        "direction": "NEUTRE",
    },
    "DUDU": {
        "nom": "Zigzag neutre",
        "description": "Alterne descend/monte - mouvement indecis",
        "direction": "NEUTRE",
    },
    "DUDD": {
        "nom": "Descente avec rebond A",
        "description": "Descend, rebond en B, puis continue de descendre",
        "direction": "BAISSIER",
    },
    "DDUU": {
        "nom": "V haussier (descend puis remonte)",
        "description": "Descend en premiere moitie puis remonte en deuxieme",
        "direction": "HAUSSIER",
    },
    "DDUD": {
        "nom": "Descente, rebond C, rechute",
        "description": "Descend, continue, rebond en C puis rechute en D",
        "direction": "BAISSIER",
    },
    "DDDU": {
        "nom": "Chute puis remontee finale",
        "description": "Descend pendant 3/4 de la bougie puis remonte en fin",
        "direction": "BAISSIER",
    },
    "DDDD": {
        "nom": "Chute continue",
        "description": "Le prix descend du debut a la fin sans interruption",
        "direction": "BAISSIER",
    },
}


def get_pattern(signature: str) -> dict:
    """Retourne les infos d'un pattern par son code."""
    return PATTERNS.get(signature, {
        "nom": signature,
        "description": "Pattern inconnu",
        "direction": "?",
    })


def get_all_patterns() -> list:
    """Retourne tous les patterns."""
    return [{"code": k, **v} for k, v in PATTERNS.items()]
