# Windows shim for `make` (SPEC requires make dev/test/seed/sim). All Python via `uv`.
# Usage: .\make.ps1 dev | test | seed | sim | install | build
param([string]$Target = "dev")
$Backend = Join-Path $PSScriptRoot "backend"
switch ($Target) {
  "install" { uv pip install -r "$Backend\requirements.txt" --system }
  "test" { Push-Location $Backend; uv run pytest tests -x -q; Pop-Location }
  "seed" { Push-Location $Backend; uv run python -m app.seed; Pop-Location }
  "sim" { uv run --directory $Backend python -m app.sim_cli }
  "build" { Push-Location (Join-Path $PSScriptRoot "frontend"); npm run build; Pop-Location }
  default {
    Write-Host "backend :8000 (frontend lands in Phase 7)"
    uv run --directory $Backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  }
}
