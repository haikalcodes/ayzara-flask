@echo off
title Ayzara Recorder Server (Production)
color 0A

echo ==================================================
echo   STARTING AYZARA DASHBOARD SERVER
echo   Mode: Production (Waitress)
echo ==================================================
echo.

:check_venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Virtual Environment found. Activating...
    call venv\Scripts\activate.bat
    goto start_app
) else (
    echo [WARNING] venv folder not found!
    echo [INFO] Trying global python...
)

:start_app
echo.
echo [INFO] Starting Application...
echo [INFO] Please leave this window OPEN to keep server running.
echo.

:: Run the production script
python run_prod.py

:: If app crashes or closes, pause before restart
echo.
echo [WARNING] Server stopped unexpectedly!
echo [INFO] Restarting in 5 seconds...
timeout /t 5
goto start_app
