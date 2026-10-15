$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Data = Join-Path $env:ProgramData 'MMF\offline'
New-Item -ItemType Directory -Force -Path $Data | Out-Null
$TokenFile = Join-Path $Data 'local-service.token'
if (-not (Test-Path $TokenFile)) {
    [guid]::NewGuid().ToString('N') | Set-Content -Path $TokenFile -NoNewline -Encoding ascii
}
$env:MMF_LOCAL_DB = Join-Path $Data 'offline-queue.sqlite3'
[Environment]::SetEnvironmentVariable('MMF_LOCAL_DB', $env:MMF_LOCAL_DB, 'Machine')
[Environment]::SetEnvironmentVariable('MMF_LOCAL_TOKEN_FILE', $TokenFile, 'Machine')
icacls.exe $Data /inheritance:r /grant:r "$env:USERNAME:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
icacls.exe $TokenFile /inheritance:r /grant:r "$env:USERNAME:F" "SYSTEM:F" "Administrators:F" | Out-Null
python -m pip install --upgrade pywin32
python "$Root\mmf_windows_service.py" install
sc.exe config MMFLocalQueueService start=auto
sc.exe failure MMFLocalQueueService reset=86400 actions=restart/5000/restart/15000/restart/60000
python "$Root\mmf_windows_service.py" start
Write-Host 'MMFLocalQueueService installed and started.'
Write-Host "Persistent database: $env:MMF_LOCAL_DB"
