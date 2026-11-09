param([Parameter(Mandatory=$true)][string]$SourcePath)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelRoot = Join-Path $projectRoot 'server\models'
$manifest = Get-Content -LiteralPath (Join-Path $modelRoot 'MODEL_MANIFEST.json') -Raw | ConvertFrom-Json
$selected = $manifest.files | Where-Object { $_.file -eq $manifest.selected }
if (-not $selected) { throw 'Selected model is missing from the manifest.' }
$source = (Resolve-Path -LiteralPath $SourcePath).Path
$target = Join-Path $modelRoot $manifest.selected
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $selected.sha256) {
    throw 'Source checkpoint does not match the tested model hash.'
}
if (Test-Path -LiteralPath $target) {
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $selected.sha256) {
        throw 'Existing checkpoint differs; preserve it and use another checkout.'
    }
    Write-Output 'Verified existing application model.'
    exit 0
}
Copy-Item -LiteralPath $source -Destination $target
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $selected.sha256) {
    throw 'Copied checkpoint failed verification.'
}
Write-Output "Verified application model: $target"
