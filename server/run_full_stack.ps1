# Compatibility entry point: one visual recognition server.
& (Join-Path $PSScriptRoot "run_realtime.ps1") @args
exit $LASTEXITCODE
