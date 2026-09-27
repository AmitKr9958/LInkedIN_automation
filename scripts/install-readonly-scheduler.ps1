$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run-agent.ps1"
$HiddenRunner = Join-Path $PSScriptRoot "run-agent-hidden.vbs"
$TaskName = "LinkedIn Agent - Read Only Discovery"

if (-not (Test-Path $Runner)) {
    throw "Agent runner not found: $Runner"
}
if (-not (Test-Path $HiddenRunner)) {
    throw "Hidden launcher not found: $HiddenRunner"
}

# Use wscript.exe as the scheduled-task entry point. The VBScript launcher
# starts PowerShell with window style 0 (hidden), avoiding a visible console
# even when Task Scheduler runs the task in the interactive user session.
$Action = New-ScheduledTaskAction `
    -Execute "$env:SystemRoot\System32\wscript.exe" `
    -Argument "//B //NoLogo `"$HiddenRunner`""

$Trigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -Hidden `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Read-only LinkedIn discovery; no account-changing action is executed." `
    -Force | Out-Null

Write-Host "Installed: $TaskName"
Write-Host "Launcher: wscript.exe -> run-agent-hidden.vbs"
