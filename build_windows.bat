@echo off
setlocal
title InfoSphere Windows Build Pipeline v2.2.0
cd /d "%~dp0"

echo.
echo  ==============================================================
echo     InfoSphere Complete Production Build & Packaging
echo  ==============================================================
echo.

SET "PYTHON_EXE="
IF EXIST "C:\Users\nazmu\AppData\Local\Programs\Python\Python314\python.exe" (
    SET "PYTHON_EXE=C:\Users\nazmu\AppData\Local\Programs\Python\Python314\python.exe"
)
IF NOT DEFINED PYTHON_EXE (
    IF EXIST "%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
        SET "PYTHON_EXE=%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    )
)
IF NOT DEFINED PYTHON_EXE (
    SET "PYTHON_EXE=python"
)

echo [1/6] Stopping existing engine instances...
call stop_engine.bat >nul 2>&1

echo [2/6] Verifying core requirements...
"%PYTHON_EXE%" -m pip install -r requirements.txt --quiet
if errorlevel 1 exit /b 1

echo [3/6] Running full test suite...
"%PYTHON_EXE%" -m unittest discover -s tests -t .
if errorlevel 1 exit /b 1

echo [4/6] Building Jarvis frontend...
pushd jarvis
if exist package.json (
    call npm install --quiet
    call npm run build
)
popd

echo [5/6] Synchronizing timestamps and launcher configs...
powershell -Command "$now = Get-Date; Get-Item 'main.py', 'START_INFOSPHERE.bat', 'STOP_INFOSPHERE.bat', 'UPDATE_INFOSPHERE.bat', 'install_autostart_windows.bat', 'run_windows.bat', 'launch_hidden.vbs', 'config.json' | ForEach-Object { $_.LastWriteTime = $now }"

echo [6/6] Recompiling Go live wallpaper and restarting live engine...
pushd core\wallpaper
go build -ldflags="-s -w" -buildvcs=false -o ..\..\infosphere_wallpaper.exe . >nul 2>&1
popd
wscript.exe "%~dp0launch_hidden.vbs"

echo.
echo  ==============================================================
echo   [OK] Build complete. Engine updated and running in background.
echo  ==============================================================
echo.
pause
