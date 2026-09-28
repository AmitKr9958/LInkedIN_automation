@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo LinkedIn Automation virtual environment was not found.
  echo Expected: %CD%\.venv\Scripts\python.exe
  pause
  exit /b 1
)
echo Starting LinkedIn Automation Control Center...
start "LinkedIn Agent Dashboard" "%CD%\.venv\Scripts\python.exe" -m app dashboard
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8765"
echo.
echo Dashboard: http://127.0.0.1:8765
echo The dashboard server is running in the separate window.
echo Close that window when you want to stop the dashboard.
