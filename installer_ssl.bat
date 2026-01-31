@echo off
setlocal
title Ayzara SSL Installer (Organized)

echo ========================================================
echo   AYZARA SSL AUTOMATION SETUP (Refactored)
echo   Target Folder: .\ssl\
echo ========================================================
echo.

:: 0. CLEANUP OLD FILES (Root)
echo [0/6] Cleaning up old root files...
if exist "mkcert.exe" del "mkcert.exe"
if exist "cert.pem" del "cert.pem"
if exist "key.pem" del "key.pem"
if exist "rootCA.pem" del "rootCA.pem"
:: We do NOT delete run_dev_secure.py as it is now a static file
if exist "start_dev_secure.bat" del "start_dev_secure.bat"
echo    [OK] Cleanup complete.

:: 1. Create SSL Directory
echo.
echo [1/6] Creating 'ssl' directory...
if not exist "ssl" mkdir ssl
echo    [OK] Directory ready.

:: 2. Check/Install mkcert (Inside ssl folder)
if not exist "ssl\mkcert.exe" (
    echo.
    echo [2/6] Downloading mkcert.exe to ssl folder...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe' -OutFile 'ssl\mkcert.exe'"
    if not exist "ssl\mkcert.exe" (
        echo [ERROR] Failed to download mkcert. Please download manually to ssl folder.
        pause
        exit /b 1
    )
    echo [INFO] mkcert.exe downloaded successfully.
) else (
    echo [2/6] mkcert.exe found in ssl folder.
)

:: 3. Install Root CA
echo.
echo [3/6] Installing Local Root CA...
cd ssl
mkcert.exe -install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Root CA.
    cd ..
    pause
    exit /b 1
)
cd ..

:: 4. Detect IP & Generate Certs
echo.
echo [4/6] Detecting IP And Generating Certificates...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4 Address"') do set IP=%%a
set IP=%IP: =%
echo    Detected IP: %IP%

cd ssl
mkcert.exe -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 %IP%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to generate certificates.
    cd ..
    pause
    exit /b 1
)
:: Copy RootCA here for easy access
for /f "delims=" %%i in ('mkcert.exe -CAROOT') do set CAROOT=%%i
copy "%CAROOT%\rootCA.pem" "rootCA.pem" >nul
cd ..
echo    [OK] Certificates generated in .\ssl\

:: 5. Python Runner (Skipped - Static File)
echo.
echo [5/6] Python Runner verified.

:: 6. Create Batch Starter
echo.
echo [6/6] Creating start_dev_secure.bat...
(
echo @echo off
echo title Ayzara Secure Server (HTTPS^)
echo color 0B
echo.
echo ==================================================
echo   STARTING AYZARA SECURE SERVER (HTTPS^)
echo   Certificates: .\ssl\
echo   Engine: Gevent
echo ==================================================
echo.
echo :check_venv
echo if exist "venv\Scripts\activate.bat" (
echo     echo [INFO] Activating Virtual Environment...
echo     call venv\Scripts\activate.bat
echo ^)
echo.
echo :check_certs
echo if not exist "ssl\cert.pem" (
echo     echo [ERROR] ssl\cert.pem not found!
echo     echo [INFO] Please run 'installer_ssl.bat' first.
echo     pause
echo     exit /b
echo ^)
echo.
echo :start_app
echo echo.
echo [INFO] Starting Application...
echo [INFO] Browser will open automatically in 3 seconds...
echo start /min cmd /c "timeout /t 3 >nul && start https://localhost:5000"
echo python run_dev_secure.py
echo.
echo echo.
echo echo [INFO] Server stopped.
echo pause
) > start_dev_secure.bat

echo.
echo ========================================================
echo   SETUP COMPLETE!
echo ========================================================
echo.
echo [IMPORTANT] FILES ARRANGED:
echo 1. SSL Files are now in the 'ssl' folder:
echo    - ssl\cert.pem
echo    - ssl\key.pem
echo    - ssl\rootCA.pem (Send THIS to your phone!)
echo    - ssl\mkcert.exe
echo.
echo 2. Old root files have been cleaned up.
echo.
echo Now run 'start_dev_secure.bat' to start!
echo.
pause
