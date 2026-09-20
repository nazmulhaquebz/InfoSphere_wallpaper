@echo off
setlocal
title InfoSphere Safe Upgrade
cd /d "%~dp0"

echo [1/5] Stopping owned processes...
call stop_engine.bat >nul 2>&1
echo [2/5] Updating Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo [3/5] Updating Jarvis dependencies...
pushd jarvis
call npm install
if errorlevel 1 (popd & exit /b 1)
echo [4/5] Building Jarvis...
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
echo [5/5] Running diagnostics...
python diagnostics.py
if errorlevel 1 exit /b 1
echo [OK] Local upgrade complete. Configuration and data were preserved.
echo Run run_windows.bat when ready to start the updated version.
pause
