@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
%PY% reset_donchi.py
if errorlevel 1 (
  echo Reset was cancelled or unsuccessful.
) else (
  echo Clean setup complete. Start with START_WINDOWS.bat.
)
pause
