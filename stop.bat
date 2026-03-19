@echo off
echo === Bougie1 - Arret ===
taskkill /F /FI "WINDOWTITLE eq Bougie1*" 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8111 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)
echo Bougie1 arrete.
