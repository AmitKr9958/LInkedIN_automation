@echo off
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found at "%ROOT%\.venv\Scripts\python.exe"
  echo Create the environment and install the project dependencies first.
  popd
  pause
  exit /b 1
)

echo Starting LinkedIn Automation Control Center...
start "LinkedIn Agent Dashboard" "%ROOT%\.venv\Scripts\python.exe" -m app dashboard --host 127.0.0.1 --port 8765

echo Waiting for dashboard health endpoint...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline=(Get-Date).AddSeconds(20); do { try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo ERROR: Dashboard did not become healthy within 20 seconds.
  echo Check the separate dashboard window for startup errors.
  popd
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8765"
echo Dashboard is healthy: http://127.0.0.1:8765
popd
endlocal
