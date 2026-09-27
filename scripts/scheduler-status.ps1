$ErrorActionPreference = "Continue"
$TaskName = "LinkedIn Agent - Read Only Discovery"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "STATUS: NOT_INSTALLED"
    exit 1
}
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
$Action = ($Task.Actions | Select-Object -First 1)
$Trigger = ($Task.Triggers | Select-Object -First 1)
$Settings = $Task.Settings

Write-Host "STATUS: $($Task.State)"
Write-Host "Enabled: $($Task.Settings.Enabled)"
Write-Host "LastRunTime: $($Info.LastRunTime)"
Write-Host "LastTaskResult: $($Info.LastTaskResult)"
Write-Host "NextRunTime: $($Info.NextRunTime)"
Write-Host "NumberOfMissedRuns: $($Info.NumberOfMissedRuns)"
Write-Host "Execute: $($Action.Execute)"
Write-Host "Arguments: $($Action.Arguments)"
Write-Host "WorkingDirectory: $($Action.WorkingDirectory)"
Write-Host "ExecutionTimeLimit: $($Settings.ExecutionTimeLimit)"
Write-Host "MultipleInstances: $($Settings.MultipleInstances)"
Write-Host "StartWhenAvailable: $($Settings.StartWhenAvailable)"
Write-Host "Hidden: $($Settings.Hidden)"
if ($Trigger) {
    Write-Host "TriggerRepetitionInterval: $($Trigger.Repetition.Interval)"
    Write-Host "TriggerRepetitionDuration: $($Trigger.Repetition.Duration)"
}
