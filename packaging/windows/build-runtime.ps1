$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '../..')
$Runtime = Join-Path $Root 'runtime'
if (Test-Path $Runtime) { Remove-Item $Runtime -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

# Run this script on a Windows build machine with Python and PyInstaller installed.
$PyInstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $PyInstaller) { throw 'PyInstaller is required on the Windows build machine: python -m pip install pyinstaller' }

function Build-OneFile($name, $script, $paths) {
  $args = @('--noconfirm','--clean','--onefile','--name',$name,'--distpath',$Runtime,'--workpath',(Join-Path $Root 'build/pyinstaller'), '--specpath',(Join-Path $Root 'build/pyinstaller'))
  foreach ($path in $paths) { $args += @('--paths',(Join-Path $Root $path)) }
  $args += (Join-Path $Root $script)
  & $PyInstaller.Source @args
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $name" }
}

Build-OneFile 'mmf-backend' 'market-backend/server.py' @('market-backend')
Build-OneFile 'mmf-local-service' 'local-service/mmf_local_service.py' @('local-service')
Build-OneFile 'mmf-production-host' 'scripts/local_production_server.py' @('market-backend','scripts')
# Telegram is installed as a separate Windows service and is intentionally not started by the UI.
if (Test-Path (Join-Path $Root 'config/production.env.example')) { Copy-Item (Join-Path $Root 'config/production.env.example') (Join-Path $Runtime 'production.env.example') }
Write-Host 'Windows runtime binaries prepared in runtime/'
