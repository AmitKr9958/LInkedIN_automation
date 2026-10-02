$ErrorActionPreference = "Continue"
$TaskName = "LinkedIn Profile Optimizer - Weekly"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) { Write-Host "STATUS: NOT_INSTALLED"; exit 1 }
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
$Trigger = ($Task.Triggers | Select-Object -First 1)
Write-Host "STATUS: $($Task.State)"
Write-Host "Enabled: $($Task.Settings.Enabled)"
Write-Host "LastRunTime: $($Info.LastRunTime)"
Write-Host "LastTaskResult: $($Info.LastTaskResult)"
Write-Host "NextRunTime: $($Info.NextRunTime)"
Write-Host "NumberOfMissedRuns: $($Info.NumberOfMissedRuns)"
Write-Host "ExecutionTimeLimit: $($Task.Settings.ExecutionTimeLimit)"
Write-Host "MultipleInstances: $($Task.Settings.MultipleInstances)"
if ($Trigger) {
    Write-Host "DaysOfWeek: $($Trigger.DaysOfWeek)"
    Write-Host "StartBoundary: $($Trigger.StartBoundary)"
}
