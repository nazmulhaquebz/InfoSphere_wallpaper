@echo off
setlocal
cd /d "%~dp0"

color 0C
echo.
echo    ========================================================================
echo       ____        __       _____       __                  
echo      /  _/__  ___/ /____  / ___/___   / /  ___  _______ _  
echo     _/ // _ \/ _  // __/ / /__ / _ \ / _ \/ _ \/ __/ _ `/  
echo    /___/_//_/\_,_//_/    \___// .__//_//_/\___/_/  \_,_/   
echo                              /_/                           
echo.
echo      TACTICAL CYBER LIVE WALLPAPER ENGINE v2.6.6 - SHUTDOWN
echo      Author Name: Mohammad Nazmul Haque
echo      Address: Tulshipur, Madhabpur, Habiganj, Bangladesh
echo      Last Updated: 2026-09-23 - Ultra-Lightweight Architecture, Zero-CPU Cooling & <50MB RAM
echo    ========================================================================
echo.
echo    Initiating secure shutdown...
echo.

:: ─── [1/3] Stop Go wallpaper engine (infosphere_wallpaper.exe + WebView2) ──
echo    [1/3] Stopping Go wallpaper engine...
taskkill /F /IM infosphere_wallpaper.exe /T >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Process -Name msedgewebview2 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1
echo           Done.

:: ─── [2/3] Stop Python telemetry & updater processes ───────────────────────
echo    [2/3] Stopping Python engines & updater workers...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_engine.ps1" -Quiet >nul 2>&1
:: Fallback: force-kill any remaining pythonw/python running main.py or updater.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -match 'python') -and (($_.CommandLine -match 'main\.py') -or ($_.CommandLine -match 'updater\.py')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo           Done.

:: ─── [3/3] Clean up port 8090 if anything is still bound ────────────────────
echo    [3/3] Releasing port 8090...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo           Done.

echo.
color 0A
echo    ========================================================================
echo      [SHUTDOWN COMPLETE] InfoSphere fully stopped.
echo.
echo      - Go wallpaper engine (infosphere_wallpaper.exe): stopped
echo      - Python telemetry engine (main.py):              stopped
echo      - WebView2 processes:                             stopped
echo      - HTTP port 8090:                                 released
echo    ========================================================================
echo.
pause
