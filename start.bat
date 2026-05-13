@echo off
chcp 65001 >nul
cd /d "%~dp0"
 
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
python app.py
pause
