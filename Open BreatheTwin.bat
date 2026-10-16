@echo off
rem Double-click to open the BreatheTwin dashboard in your browser.
rem First run: installs the Python packages it needs (a few minutes, once).
rem The dashboard runs in a small minimised window. Close that window to stop it.
cd /d "%~dp0"
title BreatheTwin setup

rem ---- find Python 3.12 or newer
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY (py -3 --version >nul 2>&1 && set PY=py -3)
if not defined PY (python --version >nul 2>&1 && set PY=python)
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" || goto oldpython

rem ---- already running? just open the browser
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul
if not errorlevel 1 goto openbrowser

rem ---- first run: install packages
%PY% -c "import streamlit, lightgbm, plotly, sklearn, pandas, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Installing the packages BreatheTwin needs. This happens only once and takes a few minutes...
    %PY% -m pip install --disable-pip-version-check -r requirements.txt || goto installfailed
)

start "BreatheTwin (close this window to stop the dashboard)" /min %PY% -m streamlit run app\dashboard.py
echo Starting the dashboard...
timeout /t 8 /nobreak >nul

:openbrowser
start "" http://localhost:8501
exit /b 0

:nopython
echo.
echo Python was not found on this computer.
echo Install Python 3.12 or newer from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during setup), then double-click this file again.
echo.
pause
exit /b 1

:oldpython
echo.
echo BreatheTwin needs Python 3.12 or newer. Please install it from https://www.python.org/downloads/
echo then double-click this file again.
echo.
pause
exit /b 1

:installfailed
echo.
echo The package installation did not finish. Check your internet connection and try again.
echo.
pause
exit /b 1
