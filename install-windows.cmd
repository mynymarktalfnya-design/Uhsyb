@echo off
setlocal
cd /d "%~dp0"

:: Request Administrator privileges automatically.
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Requesting Administrator permission...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

echo Installing MMFLocalQueueService...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local-service\install-windows.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. Review the message above.
  pause
  exit /b 1
)

echo.
echo Installation completed successfully.
echo Service: MMFLocalQueueService
pause
endlocal
