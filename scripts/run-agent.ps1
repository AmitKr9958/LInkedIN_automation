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

Write-AgentLog "[$Start] agent cycle start (max-posted-hours=6, HEADLESS=true, DRY_RUN=true)"
Write-AgentLog "[runner] root=$(Get-Location)"
Write-AgentLog "[runner] python=$python"

if (-not (Test-Path $python)) {
    Write-AgentLog "[runner] ERROR: Python executable not found: $python"
    exit 1
}

$StdoutFile = Join-Path $LogDir "agent-$Stamp.stdout.tmp"
$StderrFile = Join-Path $LogDir "agent-$Stamp.stderr.tmp"

try {
    # Start-Process avoids Windows PowerShell treating native stderr as a
    # terminating NativeCommandError. This is important under Task Scheduler:
    # the agent's stderr must be captured without converting normal diagnostics
    # into a runner exception.
    $proc = Start-Process -FilePath $python -ArgumentList @("-m", "app", "agent", "--max-posted-hours", "6") -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput $StdoutFile -RedirectStandardError $StderrFile -PassThru

    $proc.WaitForExit()
    $Code = $proc.ExitCode

    if (Test-Path $StdoutFile) {
        Get-Content $StdoutFile -ErrorAction SilentlyContinue | Add-Content -Path $LogFile
    }
    if (Test-Path $StderrFile) {
        Get-Content $StderrFile -ErrorAction SilentlyContinue | Add-Content -Path $LogFile
    }
}
catch {
    $Code = 1
    Write-AgentLog "[runner] ERROR: $($_.Exception.Message)"
}

Remove-Item $StdoutFile, $StderrFile -Force -ErrorAction SilentlyContinue

$End = Get-Date
$Duration = [math]::Round(($End - $Start).TotalSeconds, 1)
Write-AgentLog "[$End] agent cycle end exit=$Code duration=${Duration}s"

if ($Code -ne 0) { exit $Code }
