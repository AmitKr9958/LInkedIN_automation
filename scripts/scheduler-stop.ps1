$ErrorActionPreference = "Stop"
$TaskName = "LinkedIn Agent - Read Only Discovery"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Write-Host "Stopped: $TaskName"
