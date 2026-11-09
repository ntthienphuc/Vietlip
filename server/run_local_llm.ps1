param([int]$Port = 7110)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'tools\llama\llama-server.exe'
$model = Join-Path $PSScriptRoot 'models\llm\Qwen3-1.7B-Q4_K_M.gguf'
if (-not (Test-Path -LiteralPath $runtime) -or -not (Test-Path -LiteralPath $model)) {
    throw 'Local optional LLM files are missing; see docs/OPTIMIZATION_2026-11-06.md.'
}
# Explicit opt-in. Benchmark found no gain from this model; live defaults stay off.
& $runtime -m $model --alias qwen3-1.7b --host 127.0.0.1 --port $Port `
    -c 2048 -t 4 -tb 4 -ngl 0 --parallel 1 --reasoning off
exit $LASTEXITCODE
