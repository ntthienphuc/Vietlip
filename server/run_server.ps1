$ErrorActionPreference = "Stop"
$serverRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $serverRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Missing server\.venv. Run setup_server.ps1 first."
}
$envFile = Join-Path $serverRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            throw "Invalid .env line: $trimmed"
        }
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}
if (-not $env:LIP_MODEL_LOAD_ON_STARTUP) {
    # Keep the first mobile request warm in the standard run path.
    $env:LIP_MODEL_LOAD_ON_STARTUP = "true"
}
Set-Location -LiteralPath $serverRoot
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 7100
