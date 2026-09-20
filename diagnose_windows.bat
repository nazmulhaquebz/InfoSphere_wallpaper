@echo off
setlocal
cd /d "%~dp0"
python diagnostics.py
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
