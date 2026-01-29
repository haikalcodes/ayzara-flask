@echo off
cd /d "%~dp0"
echo =================================== > startup_debug.log
echo Date: %DATE% %TIME% >> startup_debug.log
echo Starting AYZARA Dashboard... >> startup_debug.log

:: Use explicit venv python
set "V_PYTHON=%~dp0venv\Scripts\python.exe"
echo V_PYTHON path: "%V_PYTHON%" >> startup_debug.log

if exist "%V_PYTHON%" (
    echo Using VirtualEnv Python >> startup_debug.log
    "%V_PYTHON%" run_prod.py >> startup_debug.log 2>&1
) else (
    echo [ERROR] Venv specific python not found at %V_PYTHON% >> startup_debug.log
    echo Fallback to global python >> startup_debug.log
    python run_prod.py >> startup_debug.log 2>&1
)

echo Script finished with errorlevel %errorlevel% >> startup_debug.log

