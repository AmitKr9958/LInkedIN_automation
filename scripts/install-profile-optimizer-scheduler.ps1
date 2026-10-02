param(
    [switch]$Enable,
    [string]$At = "10:00"
)
$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run-profile-optimizer.ps1"
$HiddenRunner = Join-Path $PSScriptRoot "run-profile-optimizer-hidden.vbs"
$TaskName = "LinkedIn Profile Optimizer - Weekly"
if (-not (Test-Path $Runner)) { throw "Runner not found: $Runner" }
if (-not (Test-Path $HiddenRunner)) { throw "Hidden launcher not found: $HiddenRunner" }
$Argument = '//B //NoLogo "' + $HiddenRunner + '"'
$Action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wscript.exe" -Argument $Argument
$Trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Sunday -At ([datetime]::Parse($At))
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Weekly read-only LinkedIn profile audit and human-review draft." -Force | Out-Null
Disable-ScheduledTask -TaskName $TaskName | Out-Null
if ($Enable) {
    Enable-ScheduledTask -TaskName $TaskName | Out-Null
    Write-Host "Installed and ENABLED: $TaskName"
} else {
    Write-Host "Installed and DISABLED: $TaskName"
}
Write-Host "Schedule: Sunday at $At (Windows local time)"
