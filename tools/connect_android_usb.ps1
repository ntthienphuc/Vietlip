param([string]$Serial = '', [int]$Port = 7100)
$ErrorActionPreference = 'Stop'
$adbPath = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adbPath)) { throw "ADB not found: $adbPath" }
if (-not $Serial) {
    $physical = @(& $adbPath devices | Where-Object { $_ -match '^([^\s]+)\s+device$' } |
        ForEach-Object { ($_ -split '\s+')[0] } | Where-Object { $_ -notlike 'emulator-*' })
    if ($physical.Count -ne 1) { throw 'Connect one authorized phone or pass -Serial explicitly.' }
    $Serial = $physical[0]
}
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/healthz" -TimeoutSec 5
if (-not $health.realtime_available -or $health.model_state -ne 'ready') {
    throw 'Start server/run_realtime.ps1 and wait for the model to become ready.'
}
& $adbPath -s $Serial reverse "tcp:$Port" "tcp:$Port"
if ($LASTEXITCODE -ne 0) { throw 'Could not establish USB forwarding.' }
Write-Output "USB connected: $Serial; model=$($health.model_id); device=$($health.device)"
Write-Output "App settings URL: http://127.0.0.1:$Port (keep USB connected)."
