param(
  [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
  [string]$TaskName = "MiniMarketAlFaniya"
)
$ErrorActionPreference = "Stop"
$runtime = Join-Path $InstallDir "windows\local_runtime.py"
if (!(Test-Path $runtime)) { throw "لم يتم العثور على windows/local_runtime.py" }
$python = (Get-Command python -ErrorAction Stop).Source
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$runtime`"" -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "تشغيل نظام ميني ماركت الفنية محليًا وخدمات المزامنة" -Force
Write-Host "تم تثبيت التشغيل التلقائي باسم $TaskName"
Write-Host "شغّل الآن: Start-ScheduledTask -TaskName '$TaskName'"
