@echo off
cd /d "%~dp0"
echo Installing optional libraries (theme, tray icon, Windows notifications)...
python -m pip install -r requirements.txt
echo.
echo Done. Start the app with run.bat
pause
