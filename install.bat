@echo off
setlocal EnableDelayedExpansion
title IINSTALLING AYZARA RECORDER DEPENDENCIES
color 0B

echo ==================================================
echo   AYZARA RECORDER - ONE CLICK INSTALLER
echo ==================================================
echo.

:: 0. Detect Architecture & Install System Level Dependencies
echo [INFO] Checking System Architecture...
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto :x64
if "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto :x64
goto :x86

:x64
echo [INFO] Detected 64-bit System (x64)
set "ARCH=x64"
set "VC_URL=https://download.microsoft.com/download/2/E/6/2E61CFA4-993B-4DD4-91DA-3737CD5CD6E3/vcredist_x64.exe"
set "VC_FILE=vcredist_2013_x64.exe"
:: Assuming Python 3.14.2 URL pattern for 2026
set "PY_URL=https://www.python.org/ftp/python/3.14.2/python-3.14.2-amd64.exe"
set "PY_FILE=python-3.14.2-amd64.exe"
goto :install_deps

:x86
echo [INFO] Detected 32-bit System (x86)
set "ARCH=x86"
set "VC_URL=https://download.microsoft.com/download/2/E/6/2E61CFA4-993B-4DD4-91DA-3737CD5CD6E3/vcredist_x86.exe"
set "VC_FILE=vcredist_2013_x86.exe"
set "PY_URL=https://www.python.org/ftp/python/3.14.2/python-3.14.2.exe"
set "PY_FILE=python-3.14.2.exe"
goto :install_deps

:install_deps
echo.
echo [INFO] Installing Visual C++ 2013 Redistributable (%ARCH%)...
if exist "%VC_FILE%" goto :run_vc_install
echo Downloading %VC_FILE%...
curl -L "%VC_URL%" -o "%VC_FILE%"

:run_vc_install
echo Installing %VC_FILE%...
start /wait "" "%VC_FILE%" /install /quiet /norestart
echo [OK] Visual C++ 2013 installation step completed.

:: 1. Check Python and Install if Missing
python --version >nul 2>&1
if %errorlevel% equ 0 goto :python_installed

echo.
echo [INFO] Python is NOT installed.
echo [INFO] Downloading Python 3.14.2 (%ARCH%)...
if exist "%PY_FILE%" goto :run_py_install
curl -L "%PY_URL%" -o "%PY_FILE%"

:run_py_install
echo [INFO] Installing Python 3.14.2...
echo.
set "py_target_dir="
echo [QUESTION] Install Python to Default Location (C:\Program Files\Python)?
echo [Y] Yes (Recommended)
echo [N] No, I want to specific a custom drive/folder
set /p "want_custom=Your Choice (Y/N) [Y]: "

if /i "!want_custom!"=="N" (
    echo.
    set /p "py_target_dir=Enter full path (e.g. D:\Apps\Python): "
    echo [INFO] Target set to: !py_target_dir!
)

echo Please wait, this may take a few minutes...
if defined py_target_dir (
    start /wait "" "%PY_FILE%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir="!py_target_dir!"
) else (
    start /wait "" "%PY_FILE%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
)

echo.
echo [WARNING] Python installed. You may need to RESTART this script or your PC
echo to ensure Python is detected in the PATH.
echo.
echo Trying to refresh local environment...
:: Attempt to continue by checking strictly
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python still not detected after install.
    echo Please restart your terminal/computer and run install.bat again.
    pause
    exit /b
)

:python_installed
echo [OK] Python is present.

:: 2. Check FFmpeg (Critical for Video Processing)
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg is NOT found in PATH.
    echo [INFO] Attempting to install via Winget...
    
    set "ff_args="
    echo.
    echo [QUESTION] Install FFmpeg to Default Location?
    set /p "want_custom_ff=Your Choice (Y/N) [Y]: "
    if /i "!want_custom_ff!"=="N" (
         set /p "ff_target=Enter full path (e.g. D:\Apps\FFmpeg): "
         set "ff_args=--location "!ff_target!""
    )
    
    winget install "FFmpeg (Essentials Build)" --accept-source-agreements --accept-package-agreements !ff_args!
    
    :: Re-check
    ffmpeg -version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] FFmpeg install failed or not found!
        echo You MUST install FFmpeg manually and add it to System PATH.
        echo Download: https://www.gyan.dev/ffmpeg/builds/
        echo.
        pause
    ) else (
        echo [OK] FFmpeg installed successfully.
    )
) else (
    echo [OK] FFmpeg found.
)

:: 3. Setup Virtual Environment
echo [INFO] Checking Virtual Environment...
if not exist "venv\Scripts\python.exe" goto :create_venv

:: Check if venv works
"venv\Scripts\python.exe" --version >nul 2>&1
if %errorlevel% equ 0 goto :venv_ok

echo [WARNING] Existing venv is broken/moved. Recreating...
rmdir /s /q "venv"

:create_venv
echo [INFO] Creating new Virtual Environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b
)
echo [OK] venv created.

:venv_ok
echo [INFO] Venv is ready.

:: 4. Activate and Install
echo [INFO] Installing dependencies from requirements.txt...
echo This may take a few minutes (downloading libraries)...
echo.

call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.


echo.
echo ==================================================
echo   INSTALLATION COMPLETE!
echo.
echo   [IMPORTANT] 
echo   If you see "DLL Load Failed" with OpenCV:
echo   Please install "Visual C++ Redistributable 2015-2022"
echo ==================================================
echo.
pause
