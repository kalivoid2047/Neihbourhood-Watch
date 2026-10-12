.DEFAULT_GOAL := help

# ── Python / venv detection ───────────────────────────────────────────────────
# Prefer .venv312 if it exists (project convention), fall back to .venv.
# Override: VENV_PYTHON=/path/to/python make <target>
ifeq ($(wildcard .venv312/Scripts/python.exe),)
  ifeq ($(wildcard .venv312/bin/python),)
    # Windows .venv
    ifeq ($(wildcard .venv/Scripts/python.exe),)
      VENV_PYTHON ?= .venv/bin/python
    else
      VENV_PYTHON ?= .venv/Scripts/python.exe
    endif
  else
    VENV_PYTHON ?= .venv312/bin/python
  endif
else
  VENV_PYTHON ?= .venv312/Scripts/python.exe
endif

MANAGE        = $(VENV_PYTHON) backend/manage.py
SETTINGS_TEST  = --settings=config.settings.test
SETTINGS_LOCAL = --settings=config.settings.local
SETTINGS_PROD  = --settings=config.settings.production

.PHONY: help \
        setup setup-prod \
        dev start stop \
        nginx-conf \
        test lint check deploy-check migrate shell \
        docker-up docker-down docker-build docker-logs \
        frontend-install frontend-dev frontend-build

help:
	@echo ""
	@echo "NHWZ — available make targets"
	@echo "══════════════════════════════════════════════════════"
	@echo ""
	@echo "  Native deployment"
	@echo "  ─────────────────"
	@echo "  setup         First-time dev setup (venv + deps + migrate)"
	@echo "  setup-prod    First-time production setup (Linux/macOS)"
	@echo "  dev           Start all dev services (Django + Celery + Vite)"
	@echo "  start         Start production services (daphne + Celery)"
	@echo "  nginx-conf    Generate infra/nginx/generated/default.conf from .env"
	@echo ""
	@echo "  Development"
	@echo "  ──────────"
	@echo "  test          Run the full Django test suite"
	@echo "  lint          Run flake8 over backend source"
	@echo "  check         Django system check (local settings)"
	@echo "  deploy-check  Django --deploy check (production settings)"
	@echo "  migrate       Apply pending migrations (local)"
	@echo "  shell         Open Django shell (local)"
	@echo ""
	@echo "  Docker (optional — requires Docker Desktop)"
	@echo "  ──────────────────────────────────────────"
	@echo "  docker-up     Start all services via docker compose"
	@echo "  docker-down   Stop all services"
	@echo "  docker-build  Rebuild Docker images"
	@echo "  docker-logs   Tail docker compose logs"
	@echo ""
	@echo "  Frontend"
	@echo "  ────────"
	@echo "  frontend-install  npm ci inside frontend/"
	@echo "  frontend-dev      Start Vite dev server"
	@echo "  frontend-build    Production build"
	@echo ""

# ── Native setup ──────────────────────────────────────────────────────────────

setup:
	bash scripts/setup.sh

setup-prod:
	MODE=prod bash scripts/setup.sh

# ── Native start ──────────────────────────────────────────────────────────────

dev:
	bash scripts/start-dev.sh

start:
	bash scripts/start-prod.sh

nginx-conf:
	bash scripts/generate-nginx-conf.sh

# ── Backend development ───────────────────────────────────────────────────────

test:
	$(MANAGE) test apps $(SETTINGS_TEST) --verbosity=1

lint:
	$(VENV_PYTHON) -m flake8 backend/apps backend/config \
		--max-line-length=120 \
		--exclude=migrations,__pycache__

check:
	$(MANAGE) check $(SETTINGS_LOCAL)

deploy-check:
	DJANGO_SECRET_KEY="ci-placeholder-secret-key-minimum-fifty-chars-abcdefghijklmno" \
	DJANGO_ALLOWED_HOSTS="example.com" \
	DATABASE_URL="postgresql://ci:ci@localhost/ci" \
	$(MANAGE) check --deploy $(SETTINGS_PROD)

migrate:
	$(MANAGE) migrate $(SETTINGS_LOCAL)

shell:
	$(MANAGE) shell $(SETTINGS_LOCAL)

# ── Docker (optional) ─────────────────────────────────────────────────────────

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

# ── Frontend ──────────────────────────────────────────────────────────────────

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
