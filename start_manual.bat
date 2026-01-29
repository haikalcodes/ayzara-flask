@echo off
setlocal EnableDelayedExpansion
title Ayzara Recorder - MANUAL MODE
color 0A
cd /d "%~dp0"

echo ==================================================
echo   AYZARA DASHBOARD - MANUAL START
echo ==================================================
echo.

:check_venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating Virtual Environment...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] venv not found! Using global python...
)

:start_loop
echo.
echo [INFO] Starting Server...
echo [INFO] Browser will open automatically...

:: Open browser in background
start "" "http://localhost:5000"

:: Run App
python run_prod.py

echo.
echo [WARNING] App crashed or stopped!
echo [INFO] Restarting in 5 seconds...
timeout /t 5
goto start_loop
