@echo off
title Ayzara Secure Server (HTTPS)
color 0B

==================================================
  STARTING AYZARA SECURE SERVER (HTTPS)
  Certificates: .\ssl\
==================================================

:check_venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating Virtual Environment...
    call venv\Scripts\activate.bat
)

:check_certs
if not exist "ssl\cert.pem" (
    echo [ERROR] ssl\cert.pem not found!
    echo [INFO] Please run 'installer_ssl.bat' first.
    pause
    exit /b
)

:start_app
echo.
[INFO] Starting Application...
[INFO] Browser will open automatically in 3 seconds...
start /min cmd /c "timeout /t 3 >nul && start https://localhost:5000"
python run_dev_secure.py

echo.
echo [WARNING] Server stopped unexpectedly!
echo [INFO] Restarting in 5 seconds...
timeout /t 5
goto start_app
