.PHONY: help setup test lint format docker-up docker-down docker-test seed demo deploy-staging deploy-prod clean

# Default Python interpreter
PYTHON := python3
POETRY := poetry

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup: ## Set up local development environment
	@chmod +x scripts/setup_local.sh
	@./scripts/setup_local.sh

install: ## Install Python dependencies
	$(POETRY) install --with dev --no-interaction

pre-commit: ## Install pre-commit hooks
	$(POETRY) run pre-commit install

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run all tests
	$(POETRY) run pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	$(POETRY) run pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	$(POETRY) run pytest tests/integration/ -v --tb=short

test-e2e: ## Run end-to-end tests only
	$(POETRY) run pytest tests/e2e/ -v --tb=short

test-cov: ## Run tests with coverage report
	$(POETRY) run pytest tests/ -v --tb=short --cov=src --cov-report=term-missing --cov-report=html

test-watch: ## Run tests in watch mode
	$(POETRY) run pytest-watch -- tests/ -v --tb=short

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------

lint: ## Run linters (ruff check + mypy)
	$(POETRY) run ruff check src/ tests/
	$(POETRY) run mypy src/ --ignore-missing-imports

format: ## Auto-format code with ruff
	$(POETRY) run ruff format src/ tests/
	$(POETRY) run ruff check --fix src/ tests/

format-check: ## Check formatting without making changes
	$(POETRY) run ruff format --check src/ tests/
	$(POETRY) run ruff check src/ tests/

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-build: ## Build all Docker images
	docker compose build

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-test: ## Run tests in Docker
	docker compose -f docker-compose.test.yaml up --build --abort-on-container-exit

docker-clean: ## Remove all containers, volumes, and images
	docker compose down -v --rmi local

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

seed: ## Seed sample data (CSV, SQLite, benchmarks)
	$(POETRY) run $(PYTHON) scripts/seed_data.py

seed-kb: ## Seed the Qdrant knowledge base
	$(POETRY) run $(PYTHON) scripts/seed_knowledge_base.py

seed-all: seed seed-kb ## Seed all data sources

# ---------------------------------------------------------------------------
# Demo & Development
# ---------------------------------------------------------------------------

demo: ## Run the interactive demo
	$(POETRY) run $(PYTHON) scripts/run_demo.py --local

demo-api: ## Run the demo against the API server
	$(POETRY) run $(PYTHON) scripts/run_demo.py

api: ## Start the API server locally
	$(POETRY) run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

dashboard: ## Start the Streamlit dashboard locally
	$(POETRY) run streamlit run src/dashboard/app.py --server.port=8501

# ---------------------------------------------------------------------------
# Load Testing
# ---------------------------------------------------------------------------

load-test: ## Run Locust load tests (opens web UI at http://localhost:8089)
	$(POETRY) run locust -f scripts/load_test.py --host=http://localhost:8000

load-test-headless: ## Run Locust headless (10 users, 60s)
	$(POETRY) run locust -f scripts/load_test.py \
		--host=http://localhost:8000 \
		--headless --users 10 --spawn-rate 2 --run-time 60s

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

deploy-staging: ## Deploy to staging (requires Azure CLI login)
	@echo "Triggering staging deployment via GitHub Actions..."
	@echo "Push to 'develop' branch to trigger CD-staging workflow."

deploy-prod: ## Deploy to production (requires release tag)
	@echo "To deploy to production:"
	@echo "  1. Create a git tag: git tag v1.x.x"
	@echo "  2. Push the tag: git push origin v1.x.x"
	@echo "  3. Create a GitHub release from the tag"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
	rm -rf reports/
	rm -f data/sample_sales.db
