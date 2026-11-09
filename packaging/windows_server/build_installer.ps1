param(
    [Parameter(Mandatory=$true)][string]$StageDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$SkipStage,
    [string]$InnoCompiler = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repo 'server\.venv\Scripts\python.exe'
if (-not $SkipStage) {
    & $python (Join-Path $PSScriptRoot 'stage_bundle.py') --output $StageDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Runtime staging failed.' }
}
$stage = (Resolve-Path -LiteralPath $StageDirectory).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $InnoCompiler)) { throw 'Inno Setup 6 is required.' }
$runtime = Join-Path $stage 'runtime\python.exe'
& $runtime (Join-Path $stage 'verify_bundle.py')
if ($LASTEXITCODE -ne 0) { throw 'Payload checksum verification failed.' }
& $runtime (Join-Path $stage 'server\check_runtime.py')
if ($LASTEXITCODE -ne 0) { throw 'Relocatable runtime check failed.' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
& $InnoCompiler "/DStageDir=$stage" "/DOutputDir=$output" (Join-Path $PSScriptRoot 'VietLipServer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Write-Host "Installer created in $output. Keep all .bin files next to the .exe."
