@echo off
:: ============================================================
::  InfoSphere Cyber Live Wallpaper Engine v2.2.0
::  install_autostart_windows.bat
::
::  Installs a Task Scheduler entry so the engine starts
::  automatically at EVERY Windows login - silently, in
::  background, no terminal window, no user interaction.
:: ============================================================
SET "APP_VERSION=unknown"
for /f "usebackq delims=" %%v in ("%~dp0VERSION") do SET "APP_VERSION=%%v"
title InfoSphere - Install Autostart v%APP_VERSION%

SET "PROJECT_DIR=%~dp0"
IF "%PROJECT_DIR:~-1%"=="\" SET "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo.
echo  ==============================================================
echo     InfoSphere - Autostart Installer  v%APP_VERSION%
echo     Engine will start silently at every Windows login
echo  ==============================================================
echo.

:: Multi-tier Python Locator (finds working Python environment)
SET "PYTHONW="
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    SET "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
)
IF NOT DEFINED PYTHONW (
    IF EXIST "%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
        SET "PYTHONW=%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    )
)
IF NOT DEFINED PYTHONW (
    FOR /F "tokens=*" %%i IN ('where python 2^>nul') DO (
        echo %%i | findstr /I "WindowsApps" >nul
        IF ERRORLEVEL 1 (
            IF NOT DEFINED PYTHONW SET "PYTHONW=%%i"
        )
    )
)
IF NOT EXIST "%PYTHONW%" (
    echo  [ERROR] python.exe not found. Make sure Python is installed and in PATH.
    pause & exit /b 1
)

echo  [OK] Using Python: %PYTHONW%
echo  [OK] Project Root: %PROJECT_DIR%
echo.

SET "NODE_EXE="
FOR /F "tokens=*" %%i IN ('where node 2^>nul') DO (
    IF NOT DEFINED NODE_EXE SET "NODE_EXE=%%i"
)
IF NOT DEFINED NODE_EXE (
    IF EXIST "C:\Program Files\nodejs\node.exe" (
        SET "NODE_EXE=C:\Program Files\nodejs\node.exe"
    )
)

:: ── Clean Autostart Registration (HKCU Run) ──
:: Remove any legacy duplicate in Startup folder to prevent race conditions on login
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\InfoSphere_Wallpaper.vbs" >nul 2>&1

:: Register in HKCU Run registry key (Standard & rock-solid)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "InfoSphere_Cyber_Wallpaper" /t REG_SZ /d "wscript.exe \"%PROJECT_DIR%\launch_hidden.vbs\"" /f >nul 2>&1

echo  ==============================================================
echo   SUCCESS! Autostart configured via Windows HKCU Run Registry.
echo   Engine starts automatically at every Windows login.
echo   Runs silently with zero terminal popup.
echo  ==============================================================
echo.
echo  Starting engine in background now...
wscript.exe "%PROJECT_DIR%\launch_hidden.vbs"
echo  [OK] Launched successfully.
echo.
pause
