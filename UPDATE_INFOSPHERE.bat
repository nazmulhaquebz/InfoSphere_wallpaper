@echo off
setlocal
cd /d "%~dp0"
title InfoSphere 1-Click Auto Updater
color 0B

echo.
echo  ==============================================================
echo     INFOSPHERE 1-CLICK AUTOMATED IN-APP UPDATER
echo  ==============================================================
echo.

python core\updater.py --cli
if errorlevel 1 (
    echo.
    color 0C
    echo  [ERROR] Update failed. Please check your internet connection or GitHub status.
    echo.
    pause
    exit /b 1
)

echo.
color 0A
echo  ==============================================================
echo   [SUCCESS] Engine successfully updated and restarted!
echo  ==============================================================
echo.
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2"
exit /b 0
