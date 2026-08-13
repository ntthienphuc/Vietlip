param(
    [ValidateSet("api", "cpu", "gpu")]
    [string]$Runtime = "cpu"
)

$ErrorActionPreference = "Stop"
$serverRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $serverRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv $venvRoot
}
& $pythonExe -m pip install --upgrade pip
switch ($Runtime) {
    "api" {
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-api.txt")
    }
    "cpu" {
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-cpu.txt")
    }
    "gpu" {
        & $pythonExe -m pip install -r (Join-Path $serverRoot "requirements-gpu.txt")
    }
}

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
Write-Host "GPU runtime: install official CUDA PyTorch, then requirements-gpu.txt"
