@echo off
setlocal
title InfoSphere Auto-Build Pipeline v2.2.0
cd /d "%~dp0"

echo.
echo  ==============================================================
echo     InfoSphere Auto-Build Pipeline
echo  ==============================================================
echo.

SET "PYTHON_CLI=C:\Users\nazmu\AppData\Local\Programs\Python\Python314\python.exe"
SET "PYTHON_DAEMON=C:\Users\nazmu\AppData\Local\Programs\Python\Python314\pythonw.exe"

IF NOT EXIST "%PYTHON_CLI%" (
    SET "PYTHON_CLI=python"
)
IF NOT EXIST "%PYTHON_DAEMON%" (
    SET "PYTHON_DAEMON=%PYTHON_CLI%"
)

echo [1/5] Stopping old engine instances...
call stop_engine.bat >nul 2>&1

echo [2/5] Verifying and installing dependencies...
"%PYTHON_CLI%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)

echo [3/5] Running diagnostics and regression tests...
"%PYTHON_CLI%" -m unittest discover -s tests -t .
if errorlevel 1 (
    echo [ERROR] Regression tests failed. Aborting build.
    exit /b 1
)

echo [4/5] Touch and sync all active project scripts...
powershell -Command "$now = Get-Date; Get-Item 'main.py', 'install_autostart_windows.bat', 'run_windows.bat', 'launch_hidden.vbs', 'config.json', 'auto_build.bat', 'build_windows.bat' | ForEach-Object { $_.LastWriteTime = $now }"

echo [5/5] Recompiling and launching live wallpaper engine...
pushd core\wallpaper
go build -ldflags="-s -w" -buildvcs=false -o ..\..\infosphere_wallpaper.exe . >nul 2>&1
popd
wscript.exe "%~dp0launch_hidden.vbs"

echo.
echo  ==============================================================
echo   [SUCCESS] Automatic Build and Deploy Complete!
echo   Live engine running in background and actively updating desktop!
echo  ==============================================================
echo.
