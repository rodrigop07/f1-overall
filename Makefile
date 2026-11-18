.PHONY: setup bootstrap compute sync dev-backend dev-frontend dev test build audit

PYTHON := backend/.venv/bin/python
PYTEST := backend/.venv/bin/pytest
UVICORN := backend/.venv/bin/uvicorn

setup:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install --upgrade pip
	backend/.venv/bin/pip install -e "./backend[dev]"
	cd frontend && npm install

bootstrap:
	cd backend && .venv/bin/python -m app.cli bootstrap

sync:
	cd backend && .venv/bin/python -m app.cli sync

compute:
	cd backend && .venv/bin/python -m app.cli recompute

audit:
	cd backend && .venv/bin/python -m app.cli audit

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

dev:
	@echo "Start backend & frontend in parallel..."
	$(MAKE) -j2 dev-backend dev-frontend

test:
	cd backend && .venv/bin/pytest tests/ -v
	cd frontend && npm run build

build:
	cd frontend && npm run build
