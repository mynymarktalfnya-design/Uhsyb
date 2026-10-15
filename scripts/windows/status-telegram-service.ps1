$ErrorActionPreference = "Stop"
Get-Service -Name "MMFTelegramBotService"
$status = Join-Path $env:ProgramData "MMF\telegram-bot-status.json"
if (Test-Path $status) { Get-Content $status -Raw }
