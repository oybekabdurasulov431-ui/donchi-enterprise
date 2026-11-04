@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% --version
if errorlevel 1 (
    echo ERROR: Python 3.10+ not found. Install from python.org.
    pause
    exit /b 1
)
echo.
echo Installing / checking Python requirements...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Packages could not be installed. Check internet and Python version.
    pause
    exit /b 1
)
echo.
echo Checking platform owner (first launch only)...
%PY% setup_admin.py
if errorlevel 1 (
    echo ERROR: Admin setup not completed. The server will not start.
    pause
    exit /b 1
)
echo.
echo =============================================================
echo DONCHI CLEAN START 1.1 - LOCAL SERVER

echo SUPER ADMIN: http://127.0.0.1:8787/platform/
echo STORE ADMIN: http://127.0.0.1:8787/app/
echo DONCHI SITE: http://127.0.0.1:8787/site/
echo Keep this window open. Press Ctrl+C to stop.
echo =============================================================
echo.
%PY% -m uvicorn server:app --host 127.0.0.1 --port 8787
pause
