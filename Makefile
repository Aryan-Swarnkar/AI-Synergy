# KhadSetu v2 Makefile (SPEC §2). Canonical on Linux/Mac/Git-Bash; see make.ps1 on Windows.
BACKEND_DIR := backend
FRONTEND_DIR := frontend

.PHONY: dev test seed sim install build

install:
	cd $(BACKEND_DIR) && pip install -r requirements.txt
	cd $(FRONTEND_DIR) && npm install || echo "(frontend not yet scaffolded, skipping)"

dev:
	@echo "backend :8000 + frontend :5173 (MOCK externals)"
	uvicorn app.main:app --app-dir $(BACKEND_DIR) --host 0.0.0.0 --port 8000 --reload & \
	cd $(FRONTEND_DIR) && npm run dev -- --host --port 5173 || uvicorn app.main:app --app-dir $(BACKEND_DIR) --host 0.0.0.0 --port 8000 --reload

test:
	cd $(BACKEND_DIR) && python -m pytest -x -q

seed:
	cd $(BACKEND_DIR) && python -m app.seed

sim:
	cd $(BACKEND_DIR) && python -c "print('simulator lands in Phase 6; try: make seed')"

build:
	cd $(FRONTEND_DIR) && npm run build || echo "(frontend not yet scaffolded)"
