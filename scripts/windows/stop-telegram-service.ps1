$ErrorActionPreference = "Stop"
Stop-Service -Name "MMFTelegramBotService"
Get-Service -Name "MMFTelegramBotService"
