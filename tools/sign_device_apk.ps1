param(
    [Parameter(Mandatory=$true)][string]$InputApk,
    [Parameter(Mandatory=$true)][string]$OutputApk,
    [Parameter(Mandatory=$true)][string]$PreviousDeviceApk
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$signingRoot = Join-Path $projectRoot 'android\signing'
$sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk\build-tools'
$signer = Get-ChildItem -LiteralPath $sdk -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
    Sort-Object { [version]$_.Name } -Descending |
    ForEach-Object { Join-Path $_.FullName 'apksigner.bat' } |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $signer) { throw 'Android apksigner not found.' }
$inputPath = (Resolve-Path -LiteralPath $InputApk).Path
$previousPath = (Resolve-Path -LiteralPath $PreviousDeviceApk).Path
$outputPath = [IO.Path]::GetFullPath($OutputApk)
if (Test-Path -LiteralPath $outputPath) { throw 'Use a new output path; prior APKs are preserved.' }
$oldCertificate = & $signer verify --print-certs $previousPath
if ($LASTEXITCODE -ne 0) { throw 'Previous device APK signature is invalid.' }
$credential = Import-Clixml -LiteralPath (Join-Path $signingRoot 'release-signing.clixml')
$env:LIP_DEVICE_SIGN_PASS = $credential.GetNetworkCredential().Password
try {
    & $signer sign --ks (Join-Path $signingRoot 'lip-reader-test-release.jks') `
        --ks-key-alias lip-reader-test-release --ks-pass env:LIP_DEVICE_SIGN_PASS `
        --key-pass env:LIP_DEVICE_SIGN_PASS --out $outputPath $inputPath
    if ($LASTEXITCODE -ne 0) { throw 'APK signing failed.' }
} finally {
    Remove-Item Env:\LIP_DEVICE_SIGN_PASS
}
$newCertificate = & $signer verify --print-certs $outputPath
if ($LASTEXITCODE -ne 0) { throw 'New APK signature is invalid.' }
$oldDigest = ($oldCertificate | Select-String 'certificate SHA-256 digest').Line
$newDigest = ($newCertificate | Select-String 'certificate SHA-256 digest').Line
if (-not $oldDigest -or $oldDigest -ne $newDigest) {
    throw 'Certificate mismatch; do not install this APK over the existing app.'
}
Write-Output $newDigest
Write-Output "Signed device APK: $outputPath"
