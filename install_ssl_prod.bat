@echo off
setlocal
title Ayzara SSL Installer PROD

echo ========================================================
echo   AYZARA SSL AUTOMATION SETUP (PRODUCTION)
echo   Target Folder: .\ssl\
echo ========================================================
echo.

:: 1. Create SSL Directory
if not exist "ssl" mkdir ssl

:: 2. Check/Install mkcert
if not exist "ssl\mkcert.exe" (
    echo [INFO] Please copy mkcert.exe to ssl folder or run installer_ssl.bat first to download it.
    pause
    exit /b 1
)

:: 3. Generate Certs if missing
if not exist "ssl\cert.pem" (
    echo [INFO] Certificates missing. Generating...
    
    :: Detect IP
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4 Address"') do set IP=%%a
    set IP=%IP: =%
    echo    Detected IP: %IP%

    cd ssl
    mkcert.exe -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 %IP%
    cd ..
) else (
    echo [INFO] Certificates already exist.
)

:: 4. Create Production Batch Starter
echo.
echo [INFO] Creating start_prod_secure.bat...
(
echo @echo off
echo setlocal
echo cd /d "%%~dp0"
echo title Ayzara Production Server ^(HTTPS/Gevent^)
echo color 0A
echo.
echo :: Initialize Crash Counter
echo set RETRY_COUNT=0
echo set MAX_RETRIES=3
echo.
echo :check_venv
echo if exist "venv\Scripts\activate.bat" ^(
echo     echo [INFO] Activating Virtual Environment...
echo     call venv\Scripts\activate.bat
echo ^)
echo.
echo :start_server
echo echo.
echo echo ==================================================
echo echo   AYZARA PRODUCTION SERVER ^(HTTPS^)
echo echo   Attempt: %%RETRY_COUNT%% / %%MAX_RETRIES%%
echo echo ==================================================
echo.
echo :: Open Browser logic: ONLY if this is the first run ^(RETRY_COUNT is 0^)
echo if %%RETRY_COUNT%% EQU 0 ^(
echo     echo [INFO] Browser will open automatically in 5 seconds...
echo     REM Launches a separate mini-window that waits 5s then opens the URL
echo     start /min cmd /c "timeout /t 5 >nul && start https://localhost:5000"
echo ^)
echo.
echo :: Run the Server ^(Blocking^)
echo python run_prod.py
echo.
echo :: Check output
echo if %%ERRORLEVEL%% EQU 0 ^(
echo     echo.
echo     echo [INFO] Server stopped manually ^(Clean Exit^).
echo     goto end
echo ^)
echo.
echo :: Crash Handling
echo echo.
echo echo [WARNING] Server crashed with Code: %%ERRORLEVEL%%
echo set /a RETRY_COUNT+=1
echo.
echo if %%RETRY_COUNT%% GEQ %%MAX_RETRIES%% ^(
echo     echo.
echo     echo ==================================================
echo     echo [CRITICAL] TOO MANY CRASHES ^(%%RETRY_COUNT%% in a row^^).
echo     echo [SYSTEM] Auto-restart stopped to protect the system.
echo     echo ==================================================
echo     color 0C
echo     echo.
echo     echo Please check the error logs above.
echo     pause
echo     goto end
echo ^)
echo.
echo echo [INFO] Restarting in 5 seconds...
echo echo.
echo pause
echo goto start_server
echo.
echo :end
echo echo.
echo echo [INFO] Session ended.
echo pause
) > start_prod_secure.bat

echo.
echo ========================================================
echo   SETUP COMPLETE!
echo ========================================================
echo Run 'start_prod_secure.bat' to start the production server.
echo.
pause
