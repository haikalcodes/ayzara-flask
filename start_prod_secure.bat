@echo off
title Ayzara Production Server (HTTPS/Gevent)
color 0A

==================================================
  STARTING AYZARA PRODUCTION SERVER (HTTPS)
  Engine: Gevent
  Certificates: .\ssl\
==================================================

:check_venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating Virtual Environment...
    call venv\Scripts\activate.bat
)

:start_app
echo.
[INFO] Starting Application...
python run_prod.py

echo.
echo [WARNING] Server stopped unexpectedly!
echo [INFO] Restarting in 5 seconds...
timeout /t 5
goto start_app
