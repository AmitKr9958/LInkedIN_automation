$ErrorActionPreference = "Stop"
$TaskName = "LinkedIn Agent - Read Only Discovery"
Start-ScheduledTask -TaskName $TaskName
Write-Host "Started: $TaskName"
