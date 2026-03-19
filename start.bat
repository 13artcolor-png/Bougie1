@echo off
echo === Bougie1 - Demarrage ===

REM Build du frontend
echo [1/2] Build du frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo ERREUR: Build frontend echoue
    pause
    exit /b 1
)
cd ..

REM Lancer le backend
echo [2/2] Lancement du backend...
cd backend
python main.py
cd ..
