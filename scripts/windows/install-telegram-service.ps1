[CmdletBinding()]
param(
  [string]$NssmPath = $env:NSSM_PATH,
  [string]$PythonPath = "",
  [string]$EnvFile = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ServiceName = "MMFTelegramBotService"
if (-not $NssmPath) { throw "حدد NSSM_PATH أو مرر -NssmPath لمسار nssm.exe" }
if (-not (Test-Path $NssmPath)) { throw "لم يتم العثور على NSSM: $NssmPath" }
if (-not $PythonPath) {
  $candidate = Join-Path $Root ".venv\Scripts\python.exe"
  $PythonPath = if (Test-Path $candidate) { $candidate } else { (Get-Command python -ErrorAction Stop).Source }
}
if (-not $EnvFile) { $EnvFile = Join-Path $Root "config\telegram-reports.env" }
if (-not (Test-Path $EnvFile)) { throw "أنشئ ملف الأسرار أولًا: $EnvFile" }
$statusDir = Join-Path $env:ProgramData "MMF"
$logDir = Join-Path $statusDir "logs"
New-Item -ItemType Directory -Force $statusDir, $logDir | Out-Null
$runner = Join-Path $Root "scripts\telegram_service_runner.py"
$args = "`"$runner`" --env-file `"$EnvFile`" --project-root `"$Root`" --status-file `"$statusDir\telegram-bot-status.json`""
& $NssmPath install $ServiceName $PythonPath $args
& $NssmPath set $ServiceName AppDirectory $Root
& $NssmPath set $ServiceName DisplayName "Mini Market الفنية Telegram Bot"
& $NssmPath set $ServiceName Description "MMF Telegram reports bot supervisor"
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 10000
& $NssmPath set $ServiceName AppStdout (Join-Path $logDir "service-out.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $logDir "service-error.log")
& $NssmPath set $ServiceName ObjectName LocalSystem
Write-Host "Installed $ServiceName. Start it with scripts\windows\start-telegram-service.ps1"
