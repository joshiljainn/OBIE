# OBIE Makefile

# ─────────────────────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────────────────────

DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROD = docker-compose -f docker-compose.prod.yml

# ─────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────

.PHONY: dev-up
dev-up:  ## Start development stack
	$(DOCKER_COMPOSE) up -d

.PHONY: dev-down
dev-down:  ## Stop development stack
	$(DOCKER_COMPOSE) down

.PHONY: dev-logs
dev-logs:  ## View logs
	$(DOCKER_COMPOSE) logs -f

.PHONY: dev-restart
dev-restart:  ## Restart development stack
	$(DOCKER_COMPOSE) restart

# ─────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────

.PHONY: db-migrate
db-migrate:  ## Run database migrations
	cd backend && alembic upgrade head

.PHONY: db-migrate-down
db-migrate-down:  ## Rollback one migration
	cd backend && alembic downgrade -1

.PHONY: db-reset
db-reset:  ## Reset database (WARNING: deletes all data)
	cd backend && alembic downgrade base && alembic upgrade head

.PHONY: db-shell
db-shell:  ## Open database shell
	docker-compose exec db psql -U obie -d obie

# ─────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run tests
	cd backend && pytest

.PHONY: test-cov
test-cov:  ## Run tests with coverage
	cd backend && pytest --cov=app --cov-report=html

.PHONY: test-unit
test-unit:  ## Run unit tests only
	cd backend && pytest tests/unit

.PHONY: test-integration
test-integration:  ## Run integration tests only
	cd backend && pytest tests/integration

# ─────────────────────────────────────────────────────────────
# Code Quality
# ─────────────────────────────────────────────────────────────

.PHONY: lint
lint:  ## Run linter
	cd backend && ruff check .

.PHONY: format
format:  ## Format code
	cd backend && black .

.PHONY: type-check
type-check:  ## Run type checking
	cd backend && mypy app

.PHONY: check
check: lint format type-check  ## Run all checks

# ─────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────

.PHONY: docker-build
docker-build:  ## Build Docker images
	$(DOCKER_COMPOSE) build

.PHONY: docker-build-prod
docker-build-prod:  ## Build production images
	$(DOCKER_COMPOSE_PROD) build

.PHONY: docker-up
docker-up:  ## Start production stack
	$(DOCKER_COMPOSE_PROD) up -d

.PHONY: docker-down
docker-down:  ## Stop production stack
	$(DOCKER_COMPOSE_PROD) down

.PHONY: docker-logs
docker-logs:  ## View production logs
	$(DOCKER_COMPOSE_PROD) logs -f

# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

.PHONY: shell
shell:  ## Open backend shell
	cd backend && python

.PHONY: celery-shell
celery-shell:  ## Open Celery shell
	cd backend && celery -A app.tasks.celery_app shell

.PHONY: clean
clean:  ## Clean up
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/htmlcov
	rm -rf backend/.coverage

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
