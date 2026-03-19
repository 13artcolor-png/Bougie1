"""Point d'entree du backend Bougie1"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT
from mt5.connection import connect, disconnect
from ws.candle_stream import candle_websocket
from api.routes import router as api_router
from utils.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie : connexion/deconnexion MT5"""
    logger.info("Demarrage du serveur Bougie1...")
    if connect():
        logger.info("MT5 connecte avec succes")
    else:
        logger.warning("Impossible de se connecter a MT5 au demarrage")
    yield
    disconnect()
    logger.info("Serveur arrete")


app = FastAPI(title="Bougie1", lifespan=lifespan)

# CORS pour le dev frontend (Vite sur port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes API
app.include_router(api_router)

# WebSocket
app.websocket("/ws/candles")(candle_websocket)

# Servir le build frontend en production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Sert l'application React (SPA fallback)"""
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))


if __name__ == "__main__":
    import uvicorn
    # Ecrire le port dans .port pour que le frontend le trouve
    port_file = os.path.join(os.path.dirname(__file__), ".port")
    with open(port_file, "w") as f:
        f.write(str(PORT))
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
