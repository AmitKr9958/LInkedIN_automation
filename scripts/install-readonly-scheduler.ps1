$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run-agent.ps1"
$TaskName = "LinkedIn Agent - Read Only Discovery"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Read-only LinkedIn discovery; no account-changing action is executed." -Force | Out-Null
Write-Host "Installed: $TaskName"
