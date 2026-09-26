$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path ".venv\Scripts\python.exe") { $python = ".venv\Scripts\python.exe" } else { $python = "python" }
$env:HEADLESS = "true"
$env:DRY_RUN = "true"
& $python -m app agent --max-posted-hours 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
