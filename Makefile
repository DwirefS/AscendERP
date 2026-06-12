# ANTS developer Makefile
.DEFAULT_GOAL := help

ENCRYPTION_MASTER_KEY ?= dev-only-key

.PHONY: help install dev dev-down test test-unit smoke lint serve

help: ## Show this help
	@echo "ANTS - available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in editable mode with dev extras
	pip install -e ".[dev]"

dev: ## Start dev dependencies (postgres + redis) in the background
	docker compose -f docker-compose.dev.yml up -d

dev-down: ## Stop dev dependencies
	docker compose -f docker-compose.dev.yml down

test: ## Run the full test suite
	ENCRYPTION_MASTER_KEY=$(ENCRYPTION_MASTER_KEY) python -m pytest -q

test-unit: ## Run unit tests only
	ENCRYPTION_MASTER_KEY=$(ENCRYPTION_MASTER_KEY) python -m pytest tests/unit -q

smoke: ## Run the boot-path smoke tests
	ENCRYPTION_MASTER_KEY=$(ENCRYPTION_MASTER_KEY) python -m pytest tests/smoke -q

lint: ## Run ruff (advisory only, never fails)
	ruff check src services ants_platform ants_mcp --exit-zero

serve: ## Run the API gateway locally with auto-reload
	uvicorn services.api_gateway.main:app --reload
