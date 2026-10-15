# Windows shim for `make` (SPEC requires make dev/test/seed/sim). All Python via `uv`.
# Usage: .\make.ps1 dev [port] | test | seed | sim | install | build
#   e.g. .\make.ps1 dev 8001   (when :8000 is busy)
param([string]$Target = "dev", [int]$Port = 8000)
$Backend = Join-Path $PSScriptRoot "backend"
switch ($Target) {
  "install" { uv pip install -r "$Backend\requirements.txt" --system }
  "test" { Push-Location $Backend; uv run pytest tests -x -q; Pop-Location }
  "seed" { Push-Location $Backend; uv run python -m app.seed; Pop-Location }
  "sim" { uv run --directory $Backend python -m app.sim_cli }
  "build" { Push-Location (Join-Path $PSScriptRoot "frontend"); npm run build; Pop-Location }
  default {
    # Backend in background job, frontend in foreground (Ctrl+C stops both).
    Write-Host "backend :$Port + frontend :5173 (VITE_API_BASE -> :$Port)"
    $job = Start-Job -ScriptBlock {
      param($p, $root) Set-Location $root
      uv run --directory (Join-Path $root "backend") uvicorn app.main:app --host 0.0.0.0 --port $p
    } -ArgumentList $Port, $PSScriptRoot
    try {
      $env:VITE_API_BASE = "http://127.0.0.1:$Port/api"
      Push-Location (Join-Path $PSScriptRoot "frontend")
      npm run dev -- --host --port 5173
    } finally {
      Pop-Location
      Stop-Job $job; Remove-Job $job -Force
      Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue
    }
  }
}
