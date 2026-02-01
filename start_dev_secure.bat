@echo off
cd /d "%~dp0"
title Ayzara Secure Server (HTTPS)
color 0B

==================================================
  STARTING AYZARA SECURE SERVER (HTTPS)
  Certificates: .\ssl\
  Engine: Gevent
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
echo [INFO] Starting Application...
echo [INFO] Browser will open automatically in 3 seconds...
start /min cmd /c "timeout /t 3 >nul && start https://localhost:5000"
python run_dev_secure.py

echo.
echo [INFO] Server stopped.
pause
