param(
    [ValidateSet('auto','cpu','cuda')][string]$Device = 'auto',
    [ValidateSet('beam','greedy')][string]$Decoder = 'beam',
    [double]$WindowSeconds = 6,
    [double]$UpdateSeconds = 1.5,
    [int]$BeamSize = 3,
    [double]$CtcWeight = 0.1,
    [string]$Checkpoint = '',
    [int]$Port = 7100,
    [string]$TraceDirectory = '',
    [switch]$SkipWarmup
)
$ErrorActionPreference = 'Stop'
$serverRoot = $PSScriptRoot
$pythonExe = Join-Path $serverRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run setup_server.ps1 first.' }
if (-not $Checkpoint) { $Checkpoint = Join-Path $serverRoot 'models\SO_seed17.pt' }
if (-not (Test-Path -LiteralPath $Checkpoint)) { throw "Missing model: $Checkpoint" }
$env:LIP_MODEL_BACKEND = 'native_avsr'
$env:LIP_MODEL_ID = 'auto-avsr-vi-' + [IO.Path]::GetFileNameWithoutExtension($Checkpoint).ToLowerInvariant()
$env:AUTO_AVSR_CHECKPOINT = (Resolve-Path -LiteralPath $Checkpoint).Path
$env:AUTO_AVSR_ROOT = Join-Path $serverRoot 'vendor\auto_avsr'
$env:VSR_SPM_MODEL = Join-Path $serverRoot 'assets\tokenizers\vi.model'
$env:VSR_SPM_UNITS = Join-Path $serverRoot 'assets\tokenizers\vi_units.txt'
$env:LIP_MODEL_LOAD_ON_STARTUP = 'true'
$env:LIP_STARTUP_WARMUP = if ($SkipWarmup) { '0' } else { '1' }
$env:LIP_DEVICE = $Device
$env:LIP_PRECISION = 'auto'
$env:LIP_REALTIME_DECODER = $Decoder
$env:LIP_REALTIME_SAMPLE_FPS = '25'
$env:LIP_REALTIME_WINDOW_SECONDS = $WindowSeconds.ToString([cultureinfo]::InvariantCulture)
$env:LIP_REALTIME_BEAM_SIZE = $BeamSize.ToString()
$env:LIP_CTC_WEIGHT = $CtcWeight.ToString([cultureinfo]::InvariantCulture)
$env:LIP_CPU_THREADS = '4'
$env:LIP_REALTIME_OVERLAP_SECONDS = '1'
$env:LIP_REALTIME_DECODE_INTERVAL_SECONDS = $UpdateSeconds.ToString([cultureinfo]::InvariantCulture)
if ($TraceDirectory) {
    $env:LIP_REALTIME_TRACE_DIR = [IO.Path]::GetFullPath($TraceDirectory)
}
Set-Location -LiteralPath $serverRoot
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port $Port --ws-max-size 1100000 --ws-max-queue 8
exit $LASTEXITCODE
