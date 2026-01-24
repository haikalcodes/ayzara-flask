@echo off
title IINSTALLING AYZARA RECORDER DEPENDENCIES
color 0B

echo ==================================================
echo   AYZARA RECORDER - ONE CLICK INSTALLER
echo ==================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and check "Add to PATH".
    pause
    exit /b
)

:: 2. Check FFmpeg (Critical for Video Processing)
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg is NOT found in PATH.
    echo [INFO] Attempting to install via Winget...
    winget install "FFmpeg (Essentials Build)" --accept-source-agreements --accept-package-agreements
    
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

:: 3. Create VENV if missing
if not exist "venv" (
    echo [INFO] Creating Virtual Environment - venv...
    python -m venv venv
    echo [OK] venv created.
) else (
    echo [INFO] venv folder already exists.
)

:: 4. Activate and Install
echo [INFO] Installing dependencies from requirements.txt...
echo This may take a few minutes (downloading libraries)...
echo.

call venv\Scripts\activate.bat
pip install -r requirements.txt

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
