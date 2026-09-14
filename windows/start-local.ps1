param([string]$InstallDir = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"
$runtime = Join-Path $InstallDir "windows\local_runtime.py"
$python = (Get-Command python -ErrorAction Stop).Source
& $python $runtime
