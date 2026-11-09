param(
    [ValidateSet("api", "cpu", "gpu")]
    [string]$Runtime = "cpu",
    [string]$Python = ''
)

$ErrorActionPreference = "Stop"
$serverRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $serverRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    if ($Python) { & $Python -m venv $venvRoot }
    else { py -3.11 -m venv $venvRoot }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required. Pass -Python with its executable path.' }
}
& $pythonExe -m pip install --upgrade pip
switch ($Runtime) {
    "api" {
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-api.txt")
    }
    "cpu" {
        & $pythonExe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
        if ($LASTEXITCODE -ne 0) { throw 'PyTorch CPU installation failed.' }
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-native.txt")
    }
    "gpu" {
        & $pythonExe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu126
        if ($LASTEXITCODE -ne 0) { throw 'PyTorch CUDA installation failed.' }
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-native.txt")
    }
}
if ($LASTEXITCODE -ne 0) { throw 'Server dependency installation failed.' }

$assetDirectory = Join-Path $serverRoot "assets"
$meanFacePath = Join-Path $assetDirectory "20words_mean_face.npy"
if (-not (Test-Path -LiteralPath $meanFacePath)) {
    New-Item -ItemType Directory -Path $assetDirectory -Force | Out-Null
    Invoke-WebRequest `
        -Uri "https://raw.githubusercontent.com/mpc001/Lipreading_using_Temporal_Convolutional_Networks/master/preprocessing/20words_mean_face.npy" `
        -OutFile $meanFacePath
    Write-Host "Downloaded upstream lip-alignment asset."
}
$expectedMeanFaceHash = "DBF68B2044171E1160716DF7C53E8BBFAA0EE8C61FB41171D04CB6092BB81422"
$actualMeanFaceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $meanFacePath).Hash
if ($actualMeanFaceHash -ne $expectedMeanFaceHash) {
    throw "20words_mean_face.npy checksum mismatch. Refusing to run an unverified asset."
}

Write-Host "$Runtime environment ready."
Write-Host "CPU model runtime (default): .\\setup_server.ps1 -Runtime cpu"
Write-Host "GPU runtime: .\setup_server.ps1 -Runtime gpu"
Write-Host "Start the application server: .\run_realtime.ps1"
