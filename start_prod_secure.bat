@echo off
setlocal
title Ayzara Production Server (HTTPS/Gevent)
color 0A

:: Initialize Crash Counter
set RETRY_COUNT=0
set MAX_RETRIES=3

:check_venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating Virtual Environment...
    call venv\Scripts\activate.bat
)

:start_server
echo.
echo ==================================================
echo   AYZARA PRODUCTION SERVER (HTTPS)
echo   Attempt: %RETRY_COUNT% / %MAX_RETRIES%
echo ==================================================

:: Open Browser logic: ONLY if this is the first run (RETRY_COUNT is 0)
if %RETRY_COUNT% EQU 0 (
    echo [INFO] Browser will open automatically in 5 seconds...
    :: Launches a separate mini-window that waits 5s then opens the URL
    start /min cmd /c "timeout /t 5 >nul && start https://localhost:5000"
)

:: Run the Server (Blocking)
python run_prod.py

:: Check output
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [INFO] Server stopped manually (Clean Exit).
    goto end
)

:: Crash Handling
echo.
echo [WARNING] Server crashed with Code: %ERRORLEVEL%
set /a RETRY_COUNT+=1

if %RETRY_COUNT% GEQ %MAX_RETRIES% (
    echo.
    echo ==================================================
    echo [CRITICAL] TOO MANY CRASHES (%RETRY_COUNT% in a row).
    echo [SYSTEM] Auto-restart stopped to protect the system.
    echo ==================================================
    color 0C
    echo.
    echo Please check the error logs above.
    pause
    goto end
)

echo [INFO] Restarting in 5 seconds...
echo.
timeout /t 5
goto start_server

:end
echo.
echo [INFO] Session ended.
pause
