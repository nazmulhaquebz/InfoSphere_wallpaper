@echo off
setlocal
cd /d "%~dp0"
title InfoSphere Version Control Manager

IF "%~1"=="" (
    echo.
    echo  ==============================================================
    echo     InfoSphere Version Control Manager
    echo  ==============================================================
    python bump_version.py --show
    echo.
    set /p "NEW_VER=Enter new version number (e.g. 2.3.1): "
    if not defined NEW_VER exit /b 0
    set /p "NOTES=Enter release summary or notes: "
    python bump_version.py %NEW_VER% "%NOTES%"
    pause
    exit /b 0
)

python bump_version.py %*
