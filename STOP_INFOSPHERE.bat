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
echo      Author: Mohammad Nazmul Haque, Habiganj, Bangladesh
echo      Build: Ultra-Lightweight - under 50MB RAM, Low CPU
echo    ========================================================================
echo.
echo    Initiating secure shutdown...
echo.

:: ─── [1/3] Stop Go wallpaper engine only (InfoSphere-owned WebView2 only) ───
echo    [1/3] Stopping Go wallpaper engine...
taskkill /F /IM infosphere_wallpaper.exe /T >nul 2>&1
:: Only kill WebView2 processes owned by InfoSphere (by CommandLine match)
:: This does NOT kill WhatsApp, Chrome or other WebView2 processes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'msedgewebview2.exe' -and $_.CommandLine -like '*InfoSphere*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo           Done.

:: ─── [2/3] Stop Python telemetry processes ───────────────────────────────────
echo    [2/3] Stopping Python engines...
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
echo      - InfoSphere WebView2 processes:                  stopped
echo      - HTTP port 8090:                                 released
echo      Note: WhatsApp, Chrome WebView2 are NOT affected.
echo    ========================================================================
echo.
pause
