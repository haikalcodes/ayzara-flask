@echo off
title AYZARA Dashboard - Flask
cd /d "%~dp0"

echo ============================================
echo   AYZARA DASHBOARD - Flask v2.0
echo   Buka browser: http://localhost:5000
echo   Tekan Ctrl+C untuk keluar
echo ============================================
echo.

REM Check if venv exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Install dependencies if needed
pip show flask >nul 2>&1 || pip install -r requirements.txt

REM Run Flask
python app.py

pause
