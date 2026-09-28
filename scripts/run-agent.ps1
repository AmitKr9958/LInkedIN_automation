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
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

$Start = Get-Date

function Write-AgentLog {
    param([string]$Message)
    $Message | Tee-Object -FilePath $LogFile -Append | Out-Null
}

Write-AgentLog "[$Start] agent cycle start (max-posted-hours=48, HEADLESS=true, DRY_RUN=true)"
Write-AgentLog "[runner] root=$(Get-Location)"
Write-AgentLog "[runner] python=$python"

if (-not (Test-Path $python)) {
    Write-AgentLog "[runner] ERROR: Python executable not found: $python"
    exit 1
}

try {
    # Use native redirection instead of a PowerShell pipeline so stdout/stderr
    # from the Python process are written reliably under Task Scheduler.
    & $python -m app agent --max-posted-hours 48 *>> $LogFile
    $Code = $LASTEXITCODE
    if ($null -eq $Code) { $Code = 1 }
}
catch {
    $Code = 1
    Write-AgentLog "[runner] ERROR: $($_.Exception.Message)"
}

$End = Get-Date
$Duration = [math]::Round(($End - $Start).TotalSeconds, 1)
Write-AgentLog "[$End] agent cycle end exit=$Code duration=${Duration}s"

if ($Code -ne 0) { exit $Code }
