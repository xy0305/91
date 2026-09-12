@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller --noconfirm --clean CamWin.spec
echo.
echo Output: dist\CamWin\CamWin.exe
pause
