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
echo title Ayzara Production Server (HTTPS/Gevent^)
echo color 0A
echo.
echo ==================================================
echo   STARTING AYZARA PRODUCTION SERVER (HTTPS^)
echo   Engine: Gevent
echo   Certificates: .\ssl\
echo ==================================================
echo.
echo :check_venv
echo if exist "venv\Scripts\activate.bat" (
echo     echo [INFO] Activating Virtual Environment...
echo     call venv\Scripts\activate.bat
echo ^)
echo.
echo :start_app
echo echo.
echo [INFO] Starting Application...
echo python run_prod.py
echo.
echo echo.
echo echo [WARNING] Server stopped unexpectedly!
echo echo [INFO] Restarting in 5 seconds...
echo timeout /t 5
echo goto start_app
) > start_prod_secure.bat

echo.
echo ========================================================
echo   SETUP COMPLETE!
echo ========================================================
echo Run 'start_prod_secure.bat' to start the production server.
echo.
pause
