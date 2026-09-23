@echo off
setlocal
cd /d "%~dp0"

color 0B
echo.
echo    ========================================================================
echo       ____        __       _____       __                  
echo      /  _/__  ___/ /____  / ___/___   / /  ___  _______ _  
echo     _/ // _ \/ _  // __/ / /__ / _ \ / _ \/ _ \/ __/ _ `/  
echo    /___/_//_/\_,_//_/    \___// .__//_//_/\___/_/  \\_,_/   
echo                              /_/                           
echo.
echo      TACTICAL CYBER LIVE WALLPAPER ENGINE v2.6.6 (Go-Native)
echo      Author Name: Mohammad Nazmul Haque
echo      Address: Tulshipur, Madhabpur, Habiganj, Bangladesh
echo      Last Updated: 2026-09-23 - Ultra-Lightweight Architecture, Zero-CPU Cooling, Low RAM (under 50MB)
echo    ========================================================================
echo.

:: ─── [1/3] Kill any running instances cleanly ───────────────────────────────
echo    [1/3] Stopping any previous instances...
taskkill /F /IM infosphere_wallpaper.exe /T >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_engine.ps1" -Quiet >nul 2>&1
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 1"
echo           Done.

:: ─── [2/3] Launch Python telemetry engine + Go wallpaper engine (silent) ────
echo    [2/3] Launching InfoSphere Live Wallpaper Engine...
wscript.exe "%~dp0launch_hidden.vbs"
echo           Done.

:: ─── [3/3] Confirm running ──────────────────────────────────────────────────
echo    [3/3] Verifying engine started...
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 4"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Get-Process -Name infosphere_wallpaper -ErrorAction SilentlyContinue) { Write-Host '          Engine running  [OK]' } else { Write-Host '          WARNING: engine not detected - try running as Administrator' }"

echo.
color 0A
echo    ========================================================================
echo      [SUCCESS] InfoSphere is running as a live Windows Wallpaper!
echo.
echo      Single Go binary: infosphere_wallpaper.exe
echo        - HTTP server + SSE hub  : port 8090
echo        - Live wallpaper layer   : Embedded in WorkerW behind desktop icons
echo        - Desktop icons          : 100%% visible and interactive on top
echo        - Mouse and Desktop clicks : Native Windows desktop behavior
echo        - Taskbar                : hidden (real wallpaper behavior)
echo        - Python telemetry       : background (main.py via pythonw)
echo        - Automated Updates      : 1-Click In-App Updater and GitHub Release Sync
echo      Zero console windows - runs silently in background.
echo    ========================================================================
echo.
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2"
exit /b 0
