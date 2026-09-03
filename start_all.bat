@echo off
title MJONAI Master Launcher
echo =======================================================
echo     STARTING MJONAI MISSION CONTROL + TRADING ENGINE
echo =======================================================
echo.
start "MJONAI Mission Control" cmd /k "d:\MJONAI\start_cockpit.bat"
timeout /t 3 /nobreak >nul
start "MJONAI Trading Engine" cmd /k "d:\MJONAI\start_engine.bat"
echo Done! Both processes running in separate windows.
