param(
    [int]$Port = 7100,
    [string]$TraceDirectory = '',
    [string]$HeadPath = '',
    [ValidateRange(0, 1)][double]$Weight = 1
)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$experimentRoot = Join-Path $appRoot 'artifacts\phoneme_probe_20261106'
if (-not $HeadPath) { $HeadPath = Join-Path $experimentRoot 'train_v1\best.pt' }
$env:LIP_EXPERIMENTAL_PHONEME_HEAD = [IO.Path]::GetFullPath($HeadPath)
$env:LIP_EXPERIMENTAL_VPHON_ROOT = Join-Path $experimentRoot 'deps\vPhon'
$env:LIP_EXPERIMENTAL_PHONEME_WEIGHT = $Weight.ToString([cultureinfo]::InvariantCulture)
if (-not (Test-Path -LiteralPath $env:LIP_EXPERIMENTAL_PHONEME_HEAD)) {
    throw 'Train the phoneme probe first; see experiments/phoneme_probe/README.md.'
}
try {
    & (Join-Path $PSScriptRoot 'run_realtime.ps1') -Device cuda -Port $Port -TraceDirectory $TraceDirectory
} finally {
    Remove-Item Env:LIP_EXPERIMENTAL_PHONEME_HEAD -ErrorAction SilentlyContinue
    Remove-Item Env:LIP_EXPERIMENTAL_VPHON_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:LIP_EXPERIMENTAL_PHONEME_WEIGHT -ErrorAction SilentlyContinue
}
