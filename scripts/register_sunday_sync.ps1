param(
    [string]$TaskName = "feb-sunday-sync",
    [ValidateSet("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")]
    [string]$DayOfWeek = "Sunday",
    [string]$Time = "23:30",
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$ExtraArguments = "--all-targets --publish"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $PythonExe = "python"
    }
}

$syncScript = (Resolve-Path (Join-Path $scriptDir "sync_and_publish.py")).Path
$triggerTime = [datetime]::ParseExact($Time, "HH:mm", $null)
$arguments = "`"$syncScript`" $ExtraArguments"

$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $triggerTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Sync FEB data on Sunday night and optionally publish to GitHub." `
    -Force | Out-Null

$xml = Export-ScheduledTask -TaskName $TaskName
$xml = [regex]::Replace(
    $xml,
    '(<StartBoundary>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:[+-]\d{2}:\d{2})?(</StartBoundary>)',
    '$1$2'
)
Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force | Out-Null

Write-Host "Task registered successfully."
Write-Host "TaskName: $TaskName"
Write-Host "Schedule: $DayOfWeek at $Time"
Write-Host "Python:   $PythonExe"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Command:  $PythonExe $arguments"
