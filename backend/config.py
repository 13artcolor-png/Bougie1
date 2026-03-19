"""Configuration du backend Bougie1"""

import os
from dotenv import load_dotenv

load_dotenv()

# Identifiants MT5
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "")

# Serveur
HOST = "127.0.0.1"
PORT = 8111

# Timeframes supportes (nom -> constante MT5)
TIMEFRAMES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}

# Intervalle de mise a jour WebSocket (secondes)
WS_UPDATE_INTERVAL = 1.0
