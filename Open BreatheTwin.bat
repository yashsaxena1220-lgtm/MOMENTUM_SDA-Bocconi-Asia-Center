@echo off
rem Double-click to open the BreatheTwin dashboard in your browser.
rem Starts the app in a small minimised window if it is not already running. Close that window to stop it.
cd /d "%~dp0"
set PY=python
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

netstat -ano | findstr ":8501" | findstr "LISTENING" >nul
if errorlevel 1 (
    start "BreatheTwin (close this window to stop the dashboard)" /min %PY% -m streamlit run app\dashboard.py
    timeout /t 8 /nobreak >nul
)
start "" http://localhost:8501
