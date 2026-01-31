@echo off
title AYZARA SERVER (Auto-Restart Watchdog)
cls

set /a RETRY_COUNT=0
set MAX_RETRIES=3

:START
echo [WATCHDOG] Starting Ayzara Server...
echo [WATCHDOG] Logs are being written to logs/server_auto.log
echo [WATCHDOG] Crash Count: %RETRY_COUNT% / %MAX_RETRIES%

:: Create logs directory if not exists
if not exist logs mkdir logs

:: Append start event to log
echo. >> logs/server_auto.log
echo =================================================== >> logs/server_auto.log
echo [WATCHDOG] Server Started at %date% %time% (Retry: %RETRY_COUNT%) >> logs/server_auto.log
echo =================================================== >> logs/server_auto.log

echo Running server... (Check logs/server_auto.log for history)
python run_prod.py >> logs/server_auto.log 2>&1

:: Check exit code
if %ERRORLEVEL% EQU 0 (
    echo [WATCHDOG] Server stopped normally (Clean Exit).
    echo [WATCHDOG] Server stopped normally at %date% %time% >> logs/server_auto.log
    goto END
)

:: Handle Crash
echo.
echo ===================================================
echo [WATCHDOG] CRITICAL: Server Crashed! (Code: %ERRORLEVEL%)
echo [WATCHDOG] CRASH DETECTED at %date% %time% - Code %ERRORLEVEL% >> logs/server_auto.log

set /a RETRY_COUNT+=1
if %RETRY_COUNT% GEQ %MAX_RETRIES% (
    goto TOO_MANY_CRASHES
)

echo [WATCHDOG] Restarting in 5 seconds... (Attempt %RETRY_COUNT% of %MAX_RETRIES%)
echo ===================================================
timeout /t 5 >nul
goto START

:TOO_MANY_CRASHES
echo.
echo ===================================================
echo [WATCHDOG] ERROR: Too many consecutive crashes (%RETRY_COUNT% times).
echo [WATCHDOG] Stops auto-restart to protect system.
echo [WATCHDOG] GIVING UP at %date% %time% >> logs/server_auto.log
echo ===================================================
echo.
echo [ACTION REQUIRED] Please check logs/server_auto.log for errors.
echo Press any key to close...
pause
goto END

:END
echo [WATCHDOG] Session Ended.
pause
