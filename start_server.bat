@echo off
setlocal EnableDelayedExpansion
title Ayzara Recorder Server (Production)
color 0A

echo ==================================================
echo   STARTING AYZARA DASHBOARD SERVER
echo   Mode: Production (Waitress)
echo ==================================================
echo.

:: ==================================================
:: CHECK NODE.JS & PM2
:: ==================================================
:: ==================================================
:: CHECK NODE.JS & PM2
:: ==================================================
:check_pm2
echo [INFO] Checking for Auto-Start Capability (Node.js)...
node --version >nul 2>&1
if %errorlevel% equ 0 goto :check_pm2_pkg

:: Node.js missing logic
echo [WARNING] Node.js not found. 
echo [INFO] Downloading Node.js 20.11.0 LTS to enable Auto-Restart...

set "NODE_URL=https://nodejs.org/dist/v20.11.0/node-v20.11.0-x64.msi"
set "NODE_FILE=node-v20.11.0-x64.msi"

if not exist "!NODE_FILE!" (
    curl -L "!NODE_URL!" -o "!NODE_FILE!"
)

echo [INFO] Installing Node.js (Silent)...
start /wait msiexec /i "!NODE_FILE!" /quiet /norestart

echo [INFO] Refreshing environment variables...
call refreshenv >nul 2>&1

:: Re-check
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Node.js install requires a PC Restart to take effect.
    echo [INFO] Fallback to manual loop mode for now...
    goto start_app_manual
)

:check_pm2_pkg
echo [INFO] Node.js is present. Checking PM2...
call npm list -g pm2 >nul 2>&1
if %errorlevel% equ 0 goto :run_pm2

:: PM2 install logic
echo [INFO] Installing PM2 and Windows Startup Service...
call npm install pm2 -g
call npm install pm2-windows-startup -g
call pm2-startup install

:run_pm2

:: Disable existing manual instance if any
call pm2 delete ayzara-cam >nul 2>&1

echo.
echo ==================================================
echo   CONFIGURING AUTO-START (PM2)
echo ==================================================
:: Get absolute path to python in venv
set "VENV_PYTHON=%~dp0venv\Scripts\python.exe"
start /min cmd /c "timeout /t 5 >nul && start http://localhost:5000"

:: Start with PM2
echo [INFO] Registering service 'ayzara-cam'...
set "START_SCRIPT=%~dp0start_app.bat"
echo [INFO] Script: "%START_SCRIPT%"
call pm2 start "%START_SCRIPT%" --name "ayzara-cam"

echo [INFO] Saving startup configuration...
call pm2 save

echo.
echo [SUCCESS] Server is running in background!
echo [INFO] It will restart automatically if it crashes or Windows reboots.
echo.
echo Use 'pm2 log' to see details.
echo Use 'pm2 status' to check status.
echo.
pause
exit

:start_app_manual
echo.
echo [INFO] Auto-Start unavailable. Starting in Manual Loop Mode...
echo [INFO] Please leave this window OPEN.
echo.

:manual_loop
:: Auto-open browser
start /min cmd /c "timeout /t 3 >nul && start http://localhost:5000"

python run_prod.py

echo.
echo [WARNING] Server stopped! Restarting in 5 seconds...
timeout /t 5
goto manual_loop
