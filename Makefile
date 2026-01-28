.PHONY: install dev test lint format clean db-migrate db-upgrade db-downgrade run docker-build docker-up docker-down setup

# Python interpreter
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
BLACK := $(PYTHON) -m black
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy

# Project settings
PROJECT_NAME := behavioral-optimization
VENV := .venv
PYTHON_VERSION := 3.11

## Development Setup
install:
	$(PIP) install -r requirements.txt

dev:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

setup: install dev
	cp .env.example .env
	alembic upgrade head
	@echo "✓ Setup complete. Update .env with your settings."

## Testing
test:
	$(PYTEST) tests/ -v --cov=app --cov-report=html --cov-report=term-missing

test-fast:
	$(PYTEST) tests/ -v --tb=short

## Code Quality
lint:
	$(RUFF) check app/
	$(MYPY) app/

format:
	$(BLACK) app/ tests/
	$(RUFF) check --fix app/ tests/

## Database
db-migrate:
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-reset:
	alembic downgrade base
	alembic upgrade head

## Running
run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

## Cleaning
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/

## Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

## Help
help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make dev            - Install development dependencies"
	@echo "  make setup          - Setup project"
	@echo "  make test           - Run tests with coverage"
	@echo "  make test-fast      - Run tests without coverage"
	@echo "  make lint           - Lint code"
	@echo "  make format         - Format code"
	@echo "  make clean          - Clean cache and build files"
	@echo "  make run            - Run development server"
	@echo "  make run-prod       - Run production server"
	@echo "  make db-migrate     - Create new migration"
	@echo "  make db-upgrade     - Apply migrations"
	@echo "  make db-downgrade   - Rollback migration"
	@echo "  make db-reset       - Reset database"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
