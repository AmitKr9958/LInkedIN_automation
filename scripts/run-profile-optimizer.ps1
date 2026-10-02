$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$LogDir = Join-Path (Get-Location) "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Get-ChildItem -Path $LogDir -Filter "profile-optimizer-*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -Skip 12 | Remove-Item -Force -ErrorAction SilentlyContinue
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "profile-optimizer-$Stamp.log"
$python = if (Test-Path ".venv\Scripts\python.exe") { (Resolve-Path ".venv\Scripts\python.exe").Path } else { "python" }
$env:HEADLESS = "true"
$env:DRY_RUN = "true"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
"[$(Get-Date)] profile optimization cycle start" | Tee-Object -FilePath $LogFile -Append | Out-Null
$StdoutFile = Join-Path $LogDir "profile-optimizer-$Stamp.stdout.tmp"
$StderrFile = Join-Path $LogDir "profile-optimizer-$Stamp.stderr.tmp"
try {
    $proc = Start-Process -FilePath $python -ArgumentList @("-m","app","profile-optimize","--queue-review","--notify-telegram") -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput $StdoutFile -RedirectStandardError $StderrFile -PassThru
    $proc.WaitForExit()
    $Code = $proc.ExitCode
    if (Test-Path $StdoutFile) { Get-Content $StdoutFile -ErrorAction SilentlyContinue | Add-Content -Path $LogFile }
    if (Test-Path $StderrFile) { Get-Content $StderrFile -ErrorAction SilentlyContinue | Add-Content -Path $LogFile }
} catch {
    $Code = 1
    "[runner] ERROR: $($_.Exception.Message)" | Add-Content -Path $LogFile
}
Remove-Item $StdoutFile, $StderrFile -Force -ErrorAction SilentlyContinue
"[$(Get-Date)] profile optimization cycle end exit=$Code" | Add-Content -Path $LogFile
exit $Code
