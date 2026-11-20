param(
    [Parameter(Mandatory=$true)][string]$StageDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$SkipStage,
    [switch]$IncludeSavedGeminiKey,
    [string]$InnoCompiler = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath (Join-Path $output 'VietLip-Server-Setup-1.10.5.exe')) {
    throw 'Use a new output folder; the existing final installer is preserved.'
}
$python = Join-Path $repo 'server\.venv\Scripts\python.exe'
if (-not $SkipStage) {
    if (-not (Test-Path -LiteralPath $python)) {
        $python = Join-Path $env:LOCALAPPDATA 'Programs\VietLip Server\runtime\python.exe'
    }
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Install VietLip Server or prepare the developer Python 3.11 environment before staging.'
    }
    $stageArgs = @((Join-Path $PSScriptRoot 'stage_bundle.py'), '--output', $StageDirectory)
    if (-not (Test-Path -LiteralPath (Join-Path $repo 'server\models\SO_seed17.pt'))) {
        $checkpoint = Join-Path $env:LOCALAPPDATA 'Programs\VietLip Server\server\models\SO_seed17.pt'
        $stageArgs += @('--checkpoint', $checkpoint)
    }
    & $python @stageArgs
    if ($LASTEXITCODE -ne 0) { throw 'Runtime staging failed.' }
}
$stage = (Resolve-Path -LiteralPath $StageDirectory).Path
if (-not (Test-Path -LiteralPath $InnoCompiler)) { throw 'Inno Setup 6 is required.' }
$runtime = Join-Path $stage 'runtime\python.exe'
& $runtime (Join-Path $stage 'verify_bundle.py')
if ($LASTEXITCODE -ne 0) { throw 'Payload checksum verification failed.' }
& $runtime (Join-Path $stage 'server\check_runtime.py')
if ($LASTEXITCODE -ne 0) { throw 'Relocatable runtime check failed.' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
$internal = Join-Path (Split-Path -Parent $stage) ('inno-payload-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $internal | Out-Null
& $InnoCompiler "/DStageDir=$stage" "/DOutputDir=$internal" (Join-Path $PSScriptRoot 'VietLipServer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
$packageArgs = @((Join-Path $PSScriptRoot 'package_installer.py'), '--payload', $internal,
    '--output', (Join-Path $output 'VietLip-Server-Setup-1.10.5.exe'),
    '--receipt', (Join-Path (Split-Path -Parent $stage) 'INSTALLER_PACKAGE.json'))
if ($IncludeSavedGeminiKey) { $packageArgs += '--with-saved-gemini-key' }
& $runtime @packageArgs
if ($LASTEXITCODE -ne 0) { throw 'Self-contained EXE packaging failed.' }
Write-Host "Self-contained installer created in $output. No external .bin files are required."
