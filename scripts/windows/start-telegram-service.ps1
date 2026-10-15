$ErrorActionPreference = "Stop"
Start-Service -Name "MMFTelegramBotService"
Get-Service -Name "MMFTelegramBotService"
