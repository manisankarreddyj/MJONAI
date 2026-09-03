@echo off
title MJONAI Mission Control Terminal
cd /d d:\MJONAI\mjonai-build
echo =======================================================
echo       STARTING MJONAI MISSION CONTROL TERMINAL
echo =======================================================
echo.
echo Opening http://localhost:8787/terminal in your browser...
timeout /t 2 /nobreak >nul
start http://localhost:8787/terminal
echo.
d:\MJONAI\.venv\Scripts\python.exe run_app.py
pause
