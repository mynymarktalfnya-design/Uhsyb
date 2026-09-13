@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run install_windows.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
set "ALLOW_MONGOMOCK=true"
set "OFFLINE_MODE=true"
set "NEON_DATABASE_URL="
set "MONGO_URL="
set "LOCAL_DB_FILE=%LOCALAPPDATA%\MiniMarket\data\local_db.json.gz"
set "BACKUP_DIR=%LOCALAPPDATA%\MiniMarket\backups"
set "JWT_SECRET_KEY=mini-market-local-windows-secret-change-me"
set "PORT=3000"

if not exist "%LOCALAPPDATA%\MiniMarket\data" mkdir "%LOCALAPPDATA%\MiniMarket\data"
if not exist "%LOCALAPPDATA%\MiniMarket\backups" mkdir "%LOCALAPPDATA%\MiniMarket\backups"

start "Mini Market" http://127.0.0.1:%PORT%
python -m uvicorn deploy_server:app --host 127.0.0.1 --port %PORT%
