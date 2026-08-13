[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = "Stop"
$serverRoot = [IO.Path]::GetFullPath(
    (Split-Path -Parent $MyInvocation.MyCommand.Path)
)
$venvRoot = [IO.Path]::GetFullPath((Join-Path $serverRoot ".venv"))
$processes = @(Get-CimInstance Win32_Process)
$targetIds = [Collections.Generic.HashSet[int]]::new()

foreach ($process in $processes) {
    $commandLine = [string]$process.CommandLine
    $executablePath = [string]$process.ExecutablePath
    if (
        ($commandLine.Contains($serverRoot) -and
            $commandLine -match "run_(full_stack|server)\.ps1") -or
        ($executablePath.StartsWith(
            $venvRoot,
            [StringComparison]::OrdinalIgnoreCase
        ) -and $commandLine -match "uvicorn app\.main:app")
    ) {
        [void]$targetIds.Add([int]$process.ProcessId)
    }
}

$foundDescendant = $true
while ($foundDescendant) {
    $foundDescendant = $false
    foreach ($process in $processes) {
        if (
            $targetIds.Contains([int]$process.ParentProcessId) -and
            -not $targetIds.Contains([int]$process.ProcessId)
        ) {
            [void]$targetIds.Add([int]$process.ProcessId)
            $foundDescendant = $true
        }
    }
}

if ($targetIds.Count -eq 0) {
    Write-Output "Lip Reader API is not running."
    exit 0
}

foreach ($processId in @($targetIds) | Sort-Object -Descending) {
    if ($PSCmdlet.ShouldProcess("process $processId", "Stop Lip Reader API")) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Output "Stopped Lip Reader process $processId"
    }
}
