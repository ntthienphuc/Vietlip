# Download the selected VietLip model into the current checkout.
$ErrorActionPreference = 'Stop'
$repo = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
$modelDir = Join-Path $repo 'server\models'
$target = Join-Path $modelDir 'SO_seed17.pt'
$manifest = Get-Content -LiteralPath (Join-Path $modelDir 'MODEL_MANIFEST.json') -Raw | ConvertFrom-Json
$expected = @($manifest.files | Where-Object { $_.file -eq 'SO_seed17.pt' })
if ($manifest.selected -ne 'SO_seed17.pt' -or $expected.Count -ne 1 -or $expected[0].sha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'Invalid SO17 model manifest.'
}
$digest = $expected[0].sha256
if (Test-Path -LiteralPath $target) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash -ne $digest) {
        throw "Existing file has an unexpected checksum. Move it elsewhere before retrying: $target"
    }
    Write-Output "SO17 already verified: $target"
    return
}
$url = 'https://github.com/ntthienphuc/liplens-app/releases/download/vietlip-1.10.5-so17/SO_seed17.pt'
$temp = Join-Path $modelDir ("SO_seed17." + [guid]::NewGuid().ToString('N') + '.partial')
try {
    & curl.exe --fail --location --retry 3 --silent --show-error --output $temp $url
    if ($LASTEXITCODE -ne 0) { throw "Checkpoint download failed (curl $LASTEXITCODE)." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $temp).Hash -ne $digest) {
        throw 'Downloaded checkpoint has an unexpected SHA-256.'
    }
    [IO.File]::Move($temp, $target)
    Write-Output "SO17 downloaded and verified: $target"
} finally {
    if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
}
