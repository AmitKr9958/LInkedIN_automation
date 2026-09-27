$ErrorActionPreference = "Continue"
$TaskName = "LinkedIn Agent - Read Only Discovery"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "STATUS: NOT_INSTALLED"
    exit 1
}
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "STATUS: $($Task.State)"
Write-Host "LastRunTime: $($Info.LastRunTime)"
Write-Host "LastTaskResult: $($Info.LastTaskResult)"
Write-Host "NextRunTime: $($Info.NextRunTime)"
Write-Host "NumberOfMissedRuns: $($Info.NumberOfMissedRuns)"
