[CmdletBinding(SupportsShouldProcess)]
param([string]$NssmPath = $env:NSSM_PATH)
$ErrorActionPreference = "Stop"
if (-not $NssmPath) { throw "حدد NSSM_PATH أو مرر -NssmPath لمسار nssm.exe" }
if ($PSCmdlet.ShouldProcess("MMFTelegramBotService", "Remove Windows service")) {
  & $NssmPath stop MMFTelegramBotService 2>$null
  & $NssmPath remove MMFTelegramBotService confirm
}
