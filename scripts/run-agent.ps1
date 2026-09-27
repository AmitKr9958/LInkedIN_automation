$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$LogDir = Join-Path (Get-Location) "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Simple log rotation: keep the newest 30 agent-*.log files
Get-ChildItem -Path $LogDir -Filter "agent-*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "agent-$Stamp.log"

if (Test-Path ".venv\Scripts\python.exe") {
    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
} else {
    $python = "python"
}

$env:HEADLESS = "true"
$env:DRY_RUN = "true"
$env:LINKEDIN_AGENT_ENABLED = "true"
# Ensure Python stdout/stderr are not fully buffered so partial progress appears
# in the log even if the process is killed by the Task Scheduler timeout.
$env:PYTHONUNBUFFERED = "1"

$Start = Get-Date
"[$Start] agent cycle start (max-posted-hours=48, HEADLESS=true, DRY_RUN=true)" |
    Tee-Object -FilePath $LogFile -Append | Out-Null

& $python -m app agent --max-posted-hours 48 2>&1 |
    Tee-Object -FilePath $LogFile -Append | Out-Null
$Code = $LASTEXITCODE
if ($null -eq $Code) { $Code = 1 }

$End = Get-Date
$Duration = [math]::Round(($End - $Start).TotalSeconds, 1)
"[$End] agent cycle end exit=$Code duration=${Duration}s" |
    Tee-Object -FilePath $LogFile -Append | Out-Null

if ($Code -ne 0) { exit $Code }
