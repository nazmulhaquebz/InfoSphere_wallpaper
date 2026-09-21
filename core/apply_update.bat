@echo off
setlocal enabledelayedexpansion

:: ─────────────────────────────────────────────────────────────────────────────
:: InfoSphere In-App Update Applicator (Detached Execution Worker)
:: %1 = Target Project Root Directory
:: %2 = Source Staging Directory Containing New Files
:: ─────────────────────────────────────────────────────────────────────────────

set "TARGET_DIR=%~1"
set "SOURCE_DIR=%~2"

if "%TARGET_DIR%"=="" set "TARGET_DIR=%~dp0.."
if "%SOURCE_DIR%"=="" exit /b 1

cd /d "%TARGET_DIR%"

:: Allow 2 seconds for browser UI to display restart message
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2" >nul 2>&1

:: ── 1. Stop all active InfoSphere processes cleanly ──────────────────────────
taskkill /F /IM infosphere_wallpaper.exe /T >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TARGET_DIR%\stop_engine.ps1" -Quiet >nul 2>&1
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1

:: ── 2. Copy new files in place (Strictly preserving personal user files) ─────
:: robocopy excludes:
::   /XF user_information.txt .env .env.local (User configs & credentials)
::   /XD "Picture\Original Picture" "Picture\cache" logs output (Personal photos & cache)
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /XF user_information.txt .env .env.local /XD "Original Picture" "cache" logs output /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1

:: In robocopy, exit codes 0 to 7 indicate successful file operations
if %ERRORLEVEL% GTR 7 (
    echo [ERROR] Robocopy encountered an issue during update.
)

:: ── 3. Clean up staging and update cache ─────────────────────────────────────
if exist "%TARGET_DIR%\output\update_staging" (
    rmdir /S /Q "%TARGET_DIR%\output\update_staging" >nul 2>&1
)
if exist "%TARGET_DIR%\output\update_cache" (
    rmdir /S /Q "%TARGET_DIR%\output\update_cache" >nul 2>&1
)

:: ── 4. Relaunch InfoSphere Live Wallpaper Engine ─────────────────────────────
if exist "%TARGET_DIR%\launch_hidden.vbs" (
    wscript.exe "%TARGET_DIR%\launch_hidden.vbs"
) else if exist "%TARGET_DIR%\START_INFOSPHERE.bat" (
    start "" "%TARGET_DIR%\START_INFOSPHERE.bat"
)

exit /b 0
