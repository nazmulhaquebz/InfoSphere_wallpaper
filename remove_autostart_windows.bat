@echo off
setlocal
title InfoSphere — Remove Autostart
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo Removing InfoSphere autostart registrations...
schtasks /Delete /TN "InfoSphere_Cyber_Wallpaper" /F >nul 2>&1
schtasks /Delete /TN "InfoSphere_Cyber_Wallpaper_v3" /F >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\InfoSphere_Wallpaper.vbs" >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "InfoSphere_Cyber_Wallpaper" /f >nul 2>&1
call "%PROJECT_DIR%\stop_engine.bat" >nul 2>&1
echo [OK] Autostart removed. Project files and user data were preserved.
pause
