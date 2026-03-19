"""Connexion persistante a MetaTrader 5"""

import MetaTrader5 as mt5
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH
from utils.logger import get_logger

logger = get_logger("mt5.connection")

# Etat de la connexion
_connected = False


def connect() -> bool:
    """Initialise la connexion a MT5. Retourne True si connecte."""
    global _connected

    if _connected and mt5.terminal_info() is not None:
        return True

    # Initialiser MT5
    if not mt5.initialize(path=MT5_PATH):
        logger.error(f"Echec initialisation MT5: {mt5.last_error()}")
        _connected = False
        return False

    # Se connecter au compte
    if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        logger.error(f"Echec login MT5: {mt5.last_error()}")
        mt5.shutdown()
        _connected = False
        return False

    info = mt5.account_info()
    logger.info(f"Connecte a MT5 - Compte: {info.login}, Serveur: {info.server}")
    _connected = True
    return True


def disconnect():
    """Ferme la connexion MT5"""
    global _connected
    mt5.shutdown()
    _connected = False
    logger.info("Deconnecte de MT5")


def is_connected() -> bool:
    """Verifie si la connexion MT5 est active"""
    global _connected
    if _connected:
        try:
            info = mt5.terminal_info()
            if info is None:
                _connected = False
        except Exception:
            _connected = False
    return _connected
