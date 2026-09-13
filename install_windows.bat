@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Mini Market - Windows offline setup
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.windows.txt
if errorlevel 1 (
  echo Dependency installation failed. Internet is required only for this first setup.
  pause
  exit /b 1
)

echo Setup complete. The app will run offline after this step.
pause
