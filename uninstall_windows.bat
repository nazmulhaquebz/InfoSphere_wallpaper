@echo off
setlocal
title InfoSphere Uninstall
cd /d "%~dp0"

echo Stopping owned InfoSphere processes...
call stop_engine.bat >nul 2>&1
schtasks /Delete /TN "InfoSphere_Cyber_Wallpaper" /F >nul 2>&1
schtasks /Delete /TN "InfoSphere_Cyber_Wallpaper_v3" /F >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\InfoSphere_Wallpaper.vbs" >nul 2>&1

echo [OK] InfoSphere startup registrations were removed.
echo [INFO] Project files, config.json, images, logs, and user data were preserved.
echo You may archive or delete this project folder manually after reviewing that data.
pause
