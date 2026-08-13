param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir,
    [string]$Model = "qwen2.5:7b",
    [switch]$SkipInstall,
    [switch]$SkipModelPull
)

$ErrorActionPreference = "Stop"
$appPath = [IO.Path]::GetFullPath($AppDir)
$logDir = Join-Path $env:LOCALAPPDATA "Lip Reader Server"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logPath = Join-Path $logDir "llm-install.log"
Start-Transcript -LiteralPath $logPath -Append | Out-Null

function Find-Ollama {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $appPath "Ollama\ollama.exe"),
        (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Wait-Ollama {
    param([string]$Executable)
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
        return
    } catch {
        Start-Process -FilePath $Executable -ArgumentList "serve" -WindowStyle Hidden
    }
    foreach ($attempt in 1..60) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
            return
        } catch {
            if ($attempt -eq 60) {
                throw "Ollama did not become ready on port 11434."
            }
        }
    }
}

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidate = Get-ChildItem `
            -Path (Join-Path $kitsRoot "*\x64\signtool.exe") `
            -File `
            -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    return $null
}

function Test-TrustedSignature {
    param([string]$Path)

    $signTool = Find-SignTool
    if ($signTool) {
        & $signTool verify /pa /q $Path
        return $LASTEXITCODE -eq 0
    }
    try {
        $signature = Get-AuthenticodeSignature -LiteralPath $Path
        return $signature.Status -eq "Valid"
    } catch {
        throw "Windows could not verify the Ollama installer signature: $($_.Exception.Message)"
    }
}

function Invoke-InstallerAndWait {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    # Start-Process -Wait can wait for the entire descendant process tree. The
    # Ollama installer launches its tray app, which is intentionally long-lived;
    # wait only for the setup PID so component installation can continue.
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = ($Arguments -join " ")
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Could not start the Ollama installer."
    }
    try {
        $process.WaitForExit()
        return $process.ExitCode
    } finally {
        $process.Dispose()
    }
}

function Download-OllamaInstaller {
    param([string]$Destination)

    $uri = "https://ollama.com/download/OllamaSetup.exe"
    if ((Test-Path -LiteralPath $Destination) -and
        (Test-TrustedSignature -Path $Destination)) {
        Write-Host "Using the previously downloaded signed Ollama installer."
        return
    }
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) {
        throw "curl.exe is required to download Ollama with resume support."
    }

    # Ollama's Windows package is large. Resume an interrupted transfer and
    # retry transient CDN/network failures instead of leaving the LLM disabled.
    Write-Host "Downloading the official Ollama Windows installer (resume enabled)..."
    & $curl.Source `
        --location `
        --fail `
        --retry 12 `
        --retry-all-errors `
        --retry-delay 5 `
        --connect-timeout 30 `
        --continue-at - `
        --output $Destination `
        $uri
    if ($LASTEXITCODE -ne 0) {
        throw "Ollama download failed after retries (curl exit $LASTEXITCODE)."
    }
    if (-not (Test-Path -LiteralPath $Destination)) {
        throw "Ollama installer was not downloaded."
    }
    $downloaded = (Get-Item -LiteralPath $Destination).Length
    if ($downloaded -lt 100MB) {
        throw "Ollama installer is unexpectedly small: $downloaded bytes."
    }
}

function Set-ConfigValue {
    param(
        [string[]]$Lines,
        [string]$Name,
        [string]$Value
    )
    $replacement = "$Name=$Value"
    $matched = $false
    $updated = foreach ($line in $Lines) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=") {
            $matched = $true
            $replacement
        } else {
            $line
        }
    }
    if (-not $matched) {
        $updated += $replacement
    }
    return @($updated)
}

try {
    Write-Host "Preparing optional local LLM for Lip Reader..."
    $ollamaExe = Find-Ollama
    $ollamaWasAlreadyInstalled = [bool]$ollamaExe
    if (-not $ollamaExe -and -not $SkipInstall) {
        $modelDir = Join-Path $appPath "ollama-models"
        New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
        [Environment]::SetEnvironmentVariable(
            "OLLAMA_MODELS",
            $modelDir,
            "User"
        )
        $env:OLLAMA_MODELS = $modelDir
        $downloadDir = Join-Path $env:TEMP "LipReaderOllamaSetup"
        New-Item -ItemType Directory -Path $downloadDir -Force | Out-Null
        $installer = Join-Path $downloadDir "OllamaSetup.exe"
        Download-OllamaInstaller -Destination $installer
        if (-not (Test-TrustedSignature -Path $installer)) {
            throw "Ollama installer signature is not valid."
        }
        $ollamaInstallDir = Join-Path $appPath "Ollama"
        $arguments = @(
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/DIR=`"$ollamaInstallDir`""
        )
        $installerExitCode = Invoke-InstallerAndWait `
            -Executable $installer `
            -Arguments $arguments
        if ($installerExitCode -ne 0) {
            throw "Ollama installer returned exit code $installerExitCode."
        }
        $ollamaExe = Find-Ollama
    }
    if (-not $ollamaExe) {
        throw "Ollama is not installed. Visual-only remains available."
    }

    $existingModelDir = [Environment]::GetEnvironmentVariable(
        "OLLAMA_MODELS",
        "User"
    )
    if ($existingModelDir) {
        $modelDir = $existingModelDir
        Write-Host "Keeping existing OLLAMA_MODELS=$modelDir"
        $env:OLLAMA_MODELS = $modelDir
    } elseif (-not $ollamaWasAlreadyInstalled) {
        $modelDir = Join-Path $appPath "ollama-models"
        New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
        [Environment]::SetEnvironmentVariable(
            "OLLAMA_MODELS",
            $modelDir,
            "User"
        )
        Write-Host "OLLAMA_MODELS=$modelDir"
        $env:OLLAMA_MODELS = $modelDir
    } else {
        Write-Host "Keeping the existing Ollama default model storage."
    }

    Wait-Ollama -Executable $ollamaExe
    if (-not $SkipModelPull) {
        Write-Host "Downloading $Model. This is approximately 4.7 GB..."
        & $ollamaExe pull $Model
        if ($LASTEXITCODE -ne 0) {
            throw "ollama pull $Model failed."
        }
    }

    $tags = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -TimeoutSec 10
    $available = @($tags.models | ForEach-Object { $_.name })
    if (-not $SkipModelPull -and $Model -notin $available) {
        throw "The model was not listed by Ollama after download: $Model"
    }

    $configPath = Join-Path $appPath "config.env"
    $lines = if (Test-Path -LiteralPath $configPath) {
        @(Get-Content -LiteralPath $configPath)
    } else {
        @()
    }
    $lines = Set-ConfigValue $lines "LIP_LLM_PROVIDER" "ollama"
    $lines = Set-ConfigValue $lines "LIP_LLM_BASE_URL" "http://127.0.0.1:11434"
    $lines = Set-ConfigValue $lines "LIP_LLM_MODEL" $Model
    Set-Content -LiteralPath $configPath -Value $lines -Encoding UTF8
    Write-Host "Local LLM is ready: $Model"
} finally {
    Stop-Transcript | Out-Null
}
