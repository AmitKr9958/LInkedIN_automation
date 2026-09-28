$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path ".venv\Scripts\python.exe") {
    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
} else {
    $python = "python"
}

Write-Host "Starting LinkedIn Agent Control Center on http://127.0.0.1:8765"
Write-Host "Keep this window open while using the dashboard."
Write-Host "Stop with Ctrl+C."
& $python -m app dashboard --host 127.0.0.1 --port 8765
