# Drake AI Trading — Makefile
# Reproducible build, test, and QA commands.
# All commands are idempotent. Use from the repository root.

.PHONY: help test test-smoke test-all docker-build docker-up docker-down docker-logs lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: ## Run smoke tests (fast — no DB/Redis dependencies)
	cd backend && python -m pytest tests/test_smoke.py tests/test_health_full.py -x -v

test-all: ## Run full test suite (requires PostgreSQL + Redis at configured hosts)
	cd backend && python -m pytest -x -v

test-unit: ## Run unit tests only (no integration dependencies)
	cd backend && python -m pytest tests/test_smoke.py tests/test_health_full.py \
		tests/test_sprint1a.py tests/test_sprint2_market_data.py \
		tests/test_sprint3_backtesting.py tests/test_sprint4_paper_trading.py \
		tests/test_sprint5_live_trading.py tests/test_settings_persistence.py \
		tests/test_market_data_import_validation.py -x -v

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start all services in detached mode
	docker compose up -d

docker-down: ## Stop and remove all services
	docker compose down -v

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-health: ## Check health of running services
	@echo "=== API Health ==="
	@curl -s http://localhost:8000/health 2>/dev/null || echo "API not reachable"
	@echo ""
	@echo "=== Full Health ==="
	@curl -s http://localhost:8000/api/v1/health/full 2>/dev/null || echo "Full health not reachable"
	@echo ""
	@echo "=== Readiness ==="
	@curl -s http://localhost:8000/api/v1/infrastructure/deployment/readiness 2>/dev/null || echo "Readiness not reachable"

lint: ## Run linting (ruff)
	cd backend && python -m ruff check app/ tests/

clean: ## Remove Python cache and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
