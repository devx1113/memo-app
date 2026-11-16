@echo off
rem Builds a single-file Windows exe: dist\MemoReminder.exe
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller -r requirements.txt || goto :err
python -m PyInstaller --noconfirm --clean MemoReminder.spec || goto :err
echo.
echo Done: dist\MemoReminder.exe
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
