$ErrorActionPreference = "Stop"
$serverRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $serverRoot ".env"

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )
    if (-not (Test-Path -LiteralPath $envFile)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -eq 2 -and $parts[0].Trim() -eq $Name) {
            return $parts[1].Trim()
        }
    }
    return $null
}

$provider = Get-DotEnvValue -Name "LIP_LLM_PROVIDER"
if ($provider -eq "ollama") {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        throw "Ollama is required but was not found in PATH."
    }
    $baseUrl = Get-DotEnvValue -Name "LIP_LLM_BASE_URL"
    $model = Get-DotEnvValue -Name "LIP_LLM_MODEL"
    if (-not $baseUrl -or -not $model) {
        throw "LIP_LLM_BASE_URL and LIP_LLM_MODEL are required for Ollama."
    }
    try {
        $tags = Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 3
    } catch {
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
        $tags = $null
        foreach ($attempt in 1..20) {
            Start-Sleep -Milliseconds 500
            try {
                $tags = Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 2
                break
            } catch {
                if ($attempt -eq 20) {
                    throw "Ollama did not become ready at $baseUrl."
                }
            }
        }
    }
    $availableModels = @($tags.models | ForEach-Object { $_.name })
    if ($model -notin $availableModels) {
        throw "Ollama model '$model' is missing. Run: ollama pull $model"
    }
    Write-Output "Ollama ready: $model"
}

& (Join-Path $serverRoot "run_server.ps1")
