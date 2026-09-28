param(
    [string]$TaskName = "LinkedIn Skill Center"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "Python environment not found: $pythonw"
}

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m app dashboard" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Skill Center started."
Write-Host "Open: http://127.0.0.1:8765"
Write-Host "It will start automatically when you sign in to Windows."
