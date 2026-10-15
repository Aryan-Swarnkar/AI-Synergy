# KhadSetu v2 Makefile (SPEC §2). Canonical on Linux/Mac/Git-Bash; see make.ps1 on Windows.
# All Python runs via `uv` (never bare pip/python).
BACKEND_DIR := backend
FRONTEND_DIR := frontend

.PHONY: dev test seed sim install build

install:
	uv pip install -r $(BACKEND_DIR)/requirements.txt --system
	cd $(FRONTEND_DIR) && npm install || echo "(frontend not yet scaffolded, skipping)"

dev:
	@echo "backend :8000 + frontend :5173 (MOCK externals)"
	uv run --directory $(BACKEND_DIR) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload & \
	cd $(FRONTEND_DIR) && npm run dev -- --host --port 5173 || uv run --directory $(BACKEND_DIR) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run --directory $(BACKEND_DIR) pytest tests -x -q

seed:
	uv run --directory $(BACKEND_DIR) python -m app.seed

sim:
	uv run --directory $(BACKEND_DIR) python -m app.sim_cli

build:
	cd $(FRONTEND_DIR) && npm run build || echo "(frontend not yet scaffolded)"
