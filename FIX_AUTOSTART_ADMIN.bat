@echo off
:: ============================================================
::  InfoSphere - Fix Autostart (Run as Administrator ONCE)
::  This removes the duplicate Task Scheduler entry that was
::  causing "terminal opens and closes" on Windows login.
:: ============================================================
echo.
echo  [Fix] Removing duplicate Task Scheduler entry...
schtasks /delete /tn "InfoSphere_Cyber_Wallpaper_v3" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Task "InfoSphere_Cyber_Wallpaper_v3" deleted successfully.
) else (
    echo  [WARN] Could not delete task (may need admin or already gone).
)

:: Clean registry Run key - ensure it points to launch_hidden.vbs
echo  [Fix] Verifying HKCU Registry autostart...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "InfoSphere_Cyber_Wallpaper" /t REG_SZ /d "wscript.exe \"%~dp0launch_hidden.vbs\"" /f >nul 2>&1
echo  [OK] Registry autostart verified.

echo.
echo  ============================================================
echo   Fix complete! Restart Windows to verify the fix.
echo   The wallpaper engine will start silently with ZERO terminals.
echo  ============================================================
echo.
pause
