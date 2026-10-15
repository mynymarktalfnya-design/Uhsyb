[CmdletBinding()]
param(
  [string]$InstallRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$PythonPath = 'python',
  [string]$NssmPath = $env:NSSM_PATH
)
$ErrorActionPreference = 'Stop'
$Data = Join-Path $env:ProgramData 'MMF'
New-Item -ItemType Directory -Force -Path (Join-Path $Data 'offline'), (Join-Path $Data 'config'), (Join-Path $Data 'logs') | Out-Null
$envFile = Join-Path $Data 'config\production.env'
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $InstallRoot 'runtime\production.env.example') $envFile }

# The local queue service remains the source-controlled pywin32 service.
$local = Join-Path $InstallRoot 'local-service\mmf_windows_service.py'
if (Test-Path $local) {
  & $PythonPath -m pip install --disable-pip-version-check pywin32
  & $PythonPath $local install
  sc.exe config MMFLocalQueueService start=auto | Out-Null
  sc.exe failure MMFLocalQueueService reset=86400 actions=restart/5000/restart/15000/restart/60000 | Out-Null
  & $PythonPath $local start
}

# Telegram remains independent and is installed only when NSSM and real env are supplied.
$telegram = Join-Path $InstallRoot 'scripts\windows\install-telegram-service.ps1'
if ((Test-Path $telegram) -and $NssmPath) {
  & $telegram -NssmPath $NssmPath -PythonPath $PythonPath -EnvFile $envFile
}
Write-Host 'MMF services installed. Secrets are stored outside the application directory.'
