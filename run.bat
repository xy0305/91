@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

%PY% -c "import PySide6, Crypto" 2>nul
if errorlevel 1 (
  echo Installing dependencies...
  %PY% -m pip install -r requirements.txt
)

echo.
echo Optional: install mpv for HEVC-FLV  https://mpv.io/installation/
echo HEVC codec pack: Microsoft Store - HEVC Video Extensions
echo.
%PY% -m camwin
if errorlevel 1 pause
