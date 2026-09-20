@echo off
title InfoSphere - One Click Setup

SET "PROJECT=%~dp0"
IF "%PROJECT:~-1%"=="\" SET "PROJECT=%PROJECT:~0,-1%"

SET "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
SET "VBS_LAUNCH=%PROJECT%\launch_hidden.vbs"
SET "VBS_STARTUP=%STARTUP%\InfoSphere_Wallpaper.vbs"

:: ── Step 1: Stop only processes owned by this InfoSphere install ──────────
call "%PROJECT%\stop_engine.bat" >nul 2>&1

:: ── Step 2: Install and verify declared dependencies ───────────────────────
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python was not found. Install Python 3.8+ and add it to PATH.
    pause & exit /b 1
)

python -m pip install -r "%PROJECT%\requirements.txt" --quiet
IF ERRORLEVEL 1 (
    echo [ERROR] Python dependency installation failed.
    echo         Retry: python -m pip install -r "%PROJECT%\requirements.txt"
    pause & exit /b 1
)

python -c "import PIL, psutil, speedtest" >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python dependencies were installed but cannot be imported.
    pause & exit /b 1
)

where npm >nul 2>&1
IF NOT ERRORLEVEL 1 (
    IF EXIST "%PROJECT%\jarvis\package.json" (
        echo [INFO] Installing optional Jarvis dashboard dependencies...
        cd /d "%PROJECT%\jarvis" && call npm install --quiet >nul 2>&1
        cd /d "%PROJECT%"
    )
) ELSE (
    echo [INFO] Node.js/npm not found. Skipping optional Jarvis dashboard (wallpaper runs independently).
)

:: ── Locate node.exe ────────────────────────────────────────────────────────
SET "NODE_EXE="
FOR /F "tokens=*" %%i IN ('where node 2^>nul') DO (
    IF NOT DEFINED NODE_EXE SET "NODE_EXE=%%i"
)
IF NOT DEFINED NODE_EXE (
    IF EXIST "C:\Program Files\nodejs\node.exe" (
        SET "NODE_EXE=C:\Program Files\nodejs\node.exe"
    ) ELSE (
        SET "NODE_EXE=node"
    )
)

:: ── Step 3: Register in HKCU Run and clean up legacy Startup folder ───────
del /f /q "%VBS_STARTUP%" >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "InfoSphere_Cyber_Wallpaper" /t REG_SZ /d "wscript.exe \"%VBS_LAUNCH%\"" /f >nul 2>&1

:: ── Step 5: Launch it right now ───────────────────────────────────────────
wscript.exe "%VBS_LAUNCH%"

echo.
echo  ================================================
echo   InfoSphere Setup Complete!
echo  ================================================
echo   Engine is RUNNING now in the background.
echo   It will AUTO-START at every Windows login.
echo  ================================================
timeout /t 4 /nobreak >nul
