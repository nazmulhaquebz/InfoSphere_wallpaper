@echo off
setlocal
title InfoSphere Engine Shutdown
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_engine.ps1"
timeout /t 2 /nobreak >nul
