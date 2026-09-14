$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Data = Join-Path $env:ProgramData 'MMF\offline'
New-Item -ItemType Directory -Force -Path $Data | Out-Null
$env:MMF_LOCAL_DB = Join-Path $Data 'offline-queue.sqlite3'
[Environment]::SetEnvironmentVariable('MMF_LOCAL_DB', $env:MMF_LOCAL_DB, 'Machine')
python -m pip install --upgrade pywin32
python "$Root\mmf_windows_service.py" install
sc.exe config MMFLocalQueueService start=auto
sc.exe failure MMFLocalQueueService reset=86400 actions=restart/5000/restart/15000/restart/60000
python "$Root\mmf_windows_service.py" start
Write-Host 'MMFLocalQueueService installed and started.'
Write-Host "Persistent database: $env:MMF_LOCAL_DB"
