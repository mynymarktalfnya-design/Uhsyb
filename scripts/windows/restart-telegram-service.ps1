$ErrorActionPreference = "Stop"
Restart-Service -Name "MMFTelegramBotService"
Get-Service -Name "MMFTelegramBotService"
