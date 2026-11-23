param([string]$Python = '')

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Python) {
    $Python = Join-Path $projectRoot 'server\.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Prepare server/.venv with the native and development requirements, or pass -Python with an existing executable.'
}

function Invoke-Check {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Check failed: {0} {1}' -f $Executable, ($Arguments -join ' '))
    }
}

Push-Location $projectRoot
try {
    $pythonSources = @('server/app', 'server/tests', 'server/desktop_launcher.py',
        'server/desktop_runtime.py')
    Invoke-Check $Python (@('-m', 'ruff', 'check') + $pythonSources)
    Invoke-Check $Python (@('-m', 'ruff', 'format', '--check') + $pythonSources)
    Invoke-Check 'dart' @('format', '--output=none', '--set-exit-if-changed', 'lib', 'test')
    Invoke-Check 'flutter' @('analyze', '--no-pub')
    Invoke-Check 'flutter' @('test', '--no-pub')
    Push-Location 'server'
    try {
        Invoke-Check $Python @('-m', 'pytest', 'tests', '../packaging/windows_server/tests', '-q')
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
