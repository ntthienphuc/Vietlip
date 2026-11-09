param(
    [switch]$SkipPythonBuild,
    [switch]$SkipInstaller,
    [string]$CheckpointPath = "D:\Project\Lip_App\Lip_Final\06_CHECKPOINT\epoch=13-step=55986-002.ckpt",
    [string]$AutoAvsrRoot = "D:\Project\Lip_App\Lip_Final\02_PROJECT_MAIN\main_code_results_phase\baselines\auto_avsr",
    [string]$VocabularyRoot = "D:\Project\Lip_App\Lip_Final\02_PROJECT_MAIN\main_code_results_phase\benchmark_v1\vocabulary",
    [string]$InnoCompilerPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    [string]$ReleaseOutputDir = ""
)

$ErrorActionPreference = "Stop"

function Get-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    try {
        $sha256 = [Security.Cryptography.SHA256]::Create()
        try {
            return (
                [BitConverter]::ToString($sha256.ComputeHash($stream))
            ).Replace("-", "")
        } finally {
            $sha256.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$serverRoot = Join-Path $repoRoot "server"
$buildRoot = Join-Path $repoRoot "build\windows_server"
$distDir = Join-Path $buildRoot "pyinstaller-dist"
$workDir = Join-Path $buildRoot "pyinstaller-work"
$specDir = Join-Path $buildRoot "spec"
$stageDir = Join-Path $buildRoot "stage\server"
$runtimePython = Join-Path $serverRoot ".venv\Scripts\python.exe"
$sitePackages = Join-Path $serverRoot ".venv\Lib\site-packages"
$lightningAbout = Join-Path $sitePackages "pytorch_lightning\__about__.py"
$lightningVersion = Join-Path $sitePackages "pytorch_lightning\__version__.py"
$lightningVersionInfo = Join-Path $sitePackages "pytorch_lightning\version.info"
$fabricVersionInfo = Join-Path $sitePackages "lightning_fabric\version.info"
$releaseDir = if ($ReleaseOutputDir) {
    [IO.Path]::GetFullPath($ReleaseOutputDir)
} else {
    Join-Path $repoRoot "output\LipReader_v1.1.0_2026-07-28"
}

$normalizedBuildRoot = [IO.Path]::GetFullPath($buildRoot).TrimEnd("\") + "\"
$normalizedStageDir = [IO.Path]::GetFullPath($stageDir)
if (-not $normalizedStageDir.StartsWith(
    $normalizedBuildRoot,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Unsafe stage directory: $normalizedStageDir"
}

foreach ($required in @(
    $runtimePython,
    $CheckpointPath,
    $AutoAvsrRoot,
    (Join-Path $VocabularyRoot "vi_unigram_2000.model"),
    (Join-Path $VocabularyRoot "vi_unigram_2000.auto_avsr_units.txt"),
    (Join-Path $serverRoot "assets\20words_mean_face.npy"),
    (Join-Path $serverRoot "assets\MEAN_FACE_LICENSE.txt"),
    $lightningAbout,
    $lightningVersion,
    $lightningVersionInfo,
    $fabricVersionInfo
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required packaging input is missing: $required"
    }
}

$expectedCheckpointHash = "6A41D0A3ACF15075A0E2F75EAD2215B5B8FCC38697885DE8EE851EB3FF576C00"
$actualCheckpointHash = Get-Sha256 $CheckpointPath
if ($actualCheckpointHash -ne $expectedCheckpointHash) {
    throw "Checkpoint checksum mismatch."
}
$meanFacePath = Join-Path $serverRoot "assets\20words_mean_face.npy"
$expectedMeanFaceHash = "DBF68B2044171E1160716DF7C53E8BBFAA0EE8C61FB41171D04CB6092BB81422"
$actualMeanFaceHash = Get-Sha256 $meanFacePath
if ($actualMeanFaceHash -ne $expectedMeanFaceHash) {
    throw "Mean-face checksum mismatch."
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
$env:PIP_CACHE_DIR = "D:\AI_CACHE\pip"
$env:TEMP = "D:\AI_CACHE\temp"
$env:TMP = "D:\AI_CACHE\temp"

if (-not $SkipPythonBuild) {
    Write-Host "[1/5] Installing the packaging tool in the D-drive runtime venv..."
    & $runtimePython -m pip install "pyinstaller==6.16.0"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller installation failed."
    }

    Write-Host "[2/5] Building standalone LipReaderServer..."
    & $runtimePython -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name LipReaderServer `
        --distpath $distDir `
        --workpath $workDir `
        --specpath $specDir `
        --paths $serverRoot `
        --paths $AutoAvsrRoot `
        --add-data "$meanFacePath;assets" `
        --add-data "$lightningAbout;pytorch_lightning" `
        --add-data "$lightningVersion;pytorch_lightning" `
        --add-data "$lightningVersionInfo;pytorch_lightning" `
        --add-data "$fabricVersionInfo;lightning_fabric" `
        --collect-submodules app `
        --collect-all mediapipe `
        --collect-all cv2 `
        --collect-all torch `
        --collect-all torchaudio `
        --collect-all sentencepiece `
        --collect-submodules skimage `
        --hidden-import lightning `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan.on `
        --exclude-module jax `
        --exclude-module jaxlib `
        --exclude-module tensorflow `
        --exclude-module pandas `
        (Join-Path $serverRoot "desktop_launcher.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Standalone server build failed."
    }
}

Write-Host "[3/5] Assembling the immutable server stage..."
if (Test-Path -LiteralPath $stageDir) {
    $resolvedStage = (Resolve-Path -LiteralPath $stageDir).Path
    if (-not $resolvedStage.StartsWith(
        $normalizedBuildRoot,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to delete unsafe stage: $resolvedStage"
    }
    Remove-Item -LiteralPath $resolvedStage -Recurse -Force
}
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

$builtServer = Join-Path $distDir "LipReaderServer"
if (-not (Test-Path -LiteralPath (Join-Path $builtServer "LipReaderServer.exe"))) {
    throw "Packaged server was not found: $builtServer"
}
# The frozen runtime contains thousands of small files. Robocopy's bounded
# multi-threaded copy is materially faster and avoids timing out packaging
# shells; the target was already validated and recreated above.
& robocopy.exe `
    $builtServer `
    $stageDir `
    /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /MT:16 /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {
    throw "Copying the frozen server stage failed with robocopy exit code $LASTEXITCODE."
}

# PyInstaller's broad Torch collection includes C/C++ development artifacts.
# They are not loaded by the frozen eager-inference runtime and add ~850 MB.
$stagedTorchRoot = Join-Path $stageDir "_internal\torch"
$stagedTorchInclude = Join-Path $stagedTorchRoot "include"
$stagedTorchLib = Join-Path $stagedTorchRoot "lib"
if (Test-Path -LiteralPath $stagedTorchInclude) {
    Remove-Item -LiteralPath $stagedTorchInclude -Recurse -Force
}
if (Test-Path -LiteralPath $stagedTorchLib) {
    Get-ChildItem -LiteralPath $stagedTorchLib -File -Filter "*.lib" |
        Remove-Item -Force
}

$resourcesDir = Join-Path $stageDir "resources"
$modelDir = Join-Path $resourcesDir "models"
$vocabDir = Join-Path $resourcesDir "vocabulary"
$toolsDir = Join-Path $stageDir "tools"
New-Item -ItemType Directory -Path $modelDir,$vocabDir,$toolsDir -Force | Out-Null

$stagedCheckpoint = Join-Path $modelDir (Split-Path -Leaf $CheckpointPath)
New-Item -ItemType HardLink -Path $stagedCheckpoint -Target $CheckpointPath | Out-Null
Copy-Item -LiteralPath $AutoAvsrRoot -Destination (Join-Path $resourcesDir "auto_avsr") -Recurse
Copy-Item `
    -LiteralPath (Join-Path $VocabularyRoot "vi_unigram_2000.model") `
    -Destination $vocabDir
Copy-Item `
    -LiteralPath (Join-Path $VocabularyRoot "vi_unigram_2000.auto_avsr_units.txt") `
    -Destination $vocabDir
Copy-Item `
    -LiteralPath (Join-Path $scriptDir "config.visual_only.env") `
    -Destination (Join-Path $stageDir "config.env")
Copy-Item `
    -LiteralPath (Join-Path $scriptDir "install_optional_llm.ps1") `
    -Destination $toolsDir
Copy-Item `
    -LiteralPath (Join-Path $scriptDir "README_INSTALL.txt") `
    -Destination $stageDir
Copy-Item `
    -LiteralPath (Join-Path $AutoAvsrRoot "LICENSE") `
    -Destination (Join-Path $stageDir "AUTO_AVSR_LICENSE.txt")
Copy-Item `
    -LiteralPath (Join-Path $serverRoot "assets\MEAN_FACE_LICENSE.txt") `
    -Destination (Join-Path $stageDir "MEAN_FACE_LICENSE.txt")

$stageCheckpointHash = Get-Sha256 $stagedCheckpoint
if ($stageCheckpointHash -ne $expectedCheckpointHash) {
    throw "Staged checkpoint checksum mismatch."
}

Write-Host "[4/5] Smoke-checking stage inventory..."
$stageFiles = Get-ChildItem -LiteralPath $stageDir -Recurse -File
$stageBytes = ($stageFiles | Measure-Object Length -Sum).Sum
Write-Host ("Stage: {0:N2} GB across {1} files" -f ($stageBytes / 1GB), $stageFiles.Count)

if (-not $SkipInstaller) {
    Write-Host "[5/5] Compiling the Windows installer..."
    if (-not (Test-Path -LiteralPath $InnoCompilerPath)) {
        throw "Inno Setup compiler not found: $InnoCompilerPath"
    }
    & $InnoCompilerPath `
        "/DStageDir=$stageDir" `
        "/DOutputDir=$releaseDir" `
        (Join-Path $scriptDir "LipReaderServer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed."
    }
}

$installer = Join-Path $releaseDir "LipReader-Server-Setup-v1.1.0.exe"
if (-not $SkipInstaller -and -not (Test-Path -LiteralPath $installer)) {
    throw "Installer output was not found: $installer"
}
Write-Host "Packaging complete: $releaseDir"
