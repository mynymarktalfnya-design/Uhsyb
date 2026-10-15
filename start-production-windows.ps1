$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'market-backend'
$Frontend = Join-Path $Root 'artifacts\market-frontend'
$Dist = Join-Path $Frontend 'dist\public'
$BackendPort = if ($env:PORT) { [int]$env:PORT } else { 8080 }
$FrontendPort = 5173

if (-not $env:JWT_SECRET_KEY -or $env:JWT_SECRET_KEY.Length -lt 32) {
  throw 'Set JWT_SECRET_KEY (at least 32 characters) in the Windows host environment before starting production.'
}
if (-not $env:NEON_DATABASE_URL -and -not $env:MONGO_URL) {
  throw 'Set NEON_DATABASE_URL or MONGO_URL in the Windows host environment before starting production.'
}
$env:APP_ENV = 'production'
$env:ENVIRONMENT = 'production'
$env:ALLOW_MONGOMOCK = 'false'

Set-Location $Backend
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  py -3 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
$python = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path (Join-Path $Dist 'index.html'))) {
  throw "Production frontend is missing: $Dist\index.html. Build it with pnpm --filter @workspace/market-frontend build."
}

$backendProcess = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','server:app','--host','127.0.0.1','--port',$BackendPort,'--workers','1' -WorkingDirectory $Backend -PassThru
$env:MMF_BACKEND_URL = "http://127.0.0.1:$BackendPort"
$env:MMF_FRONTEND_PORT = "$FrontendPort"
$staticProcess = Start-Process -FilePath $python -ArgumentList (Join-Path $Root 'scripts\local_production_server.py') -WorkingDirectory $Root -PassThru
Write-Host "Open: http://127.0.0.1:$FrontendPort/login"
Write-Host "Backend health: http://127.0.0.1:$BackendPort/api/health"
Write-Host 'Production host serves CSS/JS and proxies /api to FastAPI.'
Write-Host 'Press Ctrl+C to stop both processes.'
try { Wait-Process -Id $backendProcess.Id } finally {
  if ($staticProcess -and -not $staticProcess.HasExited) { Stop-Process -Id $staticProcess.Id -Force }
  if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -Force }
}
