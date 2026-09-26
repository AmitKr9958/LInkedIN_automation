$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName "LinkedIn Agent - Read Only Discovery" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed: LinkedIn Agent - Read Only Discovery"
