# =============================================================================
# Claude Agent SDK Harness - Makefile
# =============================================================================
# OrbStack optimized with BuildKit caching and parallel builds

# Shell configuration
SHELL := /bin/bash
.DEFAULT_GOAL := help
.ONESHELL:
.SHELLFLAGS := -ec

# Environment loading
ENV_FILE := .env
-include $(ENV_FILE)
export

# BuildKit mandatory for optimal caching
export DOCKER_BUILDKIT := 1
export BUILDKIT_PROGRESS := plain
export COMPOSE_DOCKER_CLI_BUILD := 1

# Platform detection (OrbStack on macOS uses arm64)
ARCH := $(shell uname -m)
PLATFORM := $(if $(filter arm64,$(ARCH)),linux/arm64,linux/amd64)
PLATFORMS := linux/amd64,linux/arm64

# Project variables
PROJECT_NAME ?= claudeagentsdk-harness
REGISTRY ?= ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*://;s/.git//' 2>/dev/null || echo "andisab/claudeagentsdk-harness")
IMAGE_TAG ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
ENVIRONMENT ?= development

# Compose file resolution
COMPOSE_FILES := -f docker-compose.yml
ifeq ($(ENVIRONMENT),production)
    COMPOSE_FILES += -f docker-compose.prod.yml
else
    COMPOSE_FILES += -f docker-compose.dev.yml
endif

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

# =============================================================================
# Help Target
# =============================================================================
.PHONY: help
help: ## Show available targets
	@echo "$(GREEN)Claude Agent SDK Harness - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# =============================================================================
# Initial Setup
# =============================================================================
.PHONY: init
init: check-env ## Initialize project (first time setup)
	@echo "$(GREEN)Initializing Claude Agent SDK Harness...$(NC)"
	@[ -f $(ENV_FILE) ] || cp .env.example $(ENV_FILE)
	@echo "$(YELLOW)Please edit .env and add your ANTHROPIC_API_KEY$(NC)"
	@mkdir -p workspace memory/checkpoints memory/context logs/{main,reviewer,tester,orchestrator}
	@echo "$(GREEN)Initialization complete!$(NC)"

.PHONY: check-env
check-env: ## Validate environment
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)Docker not installed$(NC)"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "$(RED)Docker Compose v2 required$(NC)"; exit 1; }
	@[ -f $(ENV_FILE) ] || { echo "$(YELLOW)Creating .env from .env.example...$(NC)"; cp .env.example $(ENV_FILE); }

# =============================================================================
# Development
# =============================================================================
.PHONY: dev
dev: check-env ## Start development environment with hot-reload
	@echo "$(GREEN)Starting development environment...$(NC)"
	docker compose $(COMPOSE_FILES) up --build --remove-orphans --watch

.PHONY: dev-detached
dev-detached: check-env ## Start development environment in background
	docker compose $(COMPOSE_FILES) up -d --build --remove-orphans

# =============================================================================
# Build Targets
# =============================================================================
.PHONY: build
build: check-env ## Build all services
	@echo "$(GREEN)Building all services...$(NC)"
	docker compose $(COMPOSE_FILES) build --parallel

.PHONY: build-main
build-main: check-env ## Build main agent only
	docker compose $(COMPOSE_FILES) build main-agent

.PHONY: build-no-cache
build-no-cache: check-env ## Build without cache (clean build)
	docker compose $(COMPOSE_FILES) build --no-cache --parallel

# =============================================================================
# Service Management
# =============================================================================
.PHONY: up
up: check-env ## Start all services
	docker compose $(COMPOSE_FILES) up -d --remove-orphans

.PHONY: up-healthy
up-healthy: check-env ## Start and wait for health checks
	docker compose $(COMPOSE_FILES) up -d --wait --wait-timeout 60

.PHONY: down
down: ## Stop all services
	docker compose $(COMPOSE_FILES) down

.PHONY: restart
restart: ## Restart all services
	docker compose $(COMPOSE_FILES) restart

.PHONY: ps
ps: ## Show running containers
	docker compose $(COMPOSE_FILES) ps

.PHONY: services
services: ## List all services
	@docker compose $(COMPOSE_FILES) ps --services

# =============================================================================
# Logs
# =============================================================================
.PHONY: logs
logs: ## Tail all service logs
	docker compose $(COMPOSE_FILES) logs -f

.PHONY: logs-main
logs-main: ## Tail main agent logs
	docker compose $(COMPOSE_FILES) logs -f main-agent

.PHONY: logs-json
logs-json: ## View logs in JSON format
	docker compose $(COMPOSE_FILES) logs -f --no-log-prefix | jq -R 'fromjson? // .'

# =============================================================================
# Shell Access
# =============================================================================
.PHONY: shell
shell: ## Shell into main agent container
	docker compose $(COMPOSE_FILES) exec main-agent /bin/bash

.PHONY: shell-root
shell-root: ## Root shell into main agent
	docker compose $(COMPOSE_FILES) exec -u root main-agent /bin/bash

.PHONY: shell-reviewer
shell-reviewer: ## Shell into reviewer agent
	docker compose $(COMPOSE_FILES) exec reviewer-agent /bin/bash

.PHONY: shell-tester
shell-tester: ## Shell into tester agent
	docker compose $(COMPOSE_FILES) exec tester-agent /bin/bash

# =============================================================================
# Interactive Agent
# =============================================================================
.PHONY: interactive
interactive: ## Start interactive conversation with main agent
	@echo "$(GREEN)Starting interactive session...$(NC)"
	@echo "$(YELLOW)Type 'exit' or 'quit' to end the session$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.interactive

.PHONY: chat
chat: interactive ## Alias for interactive mode

.PHONY: interactive-model
interactive-model: ## Start interactive with specific model (usage: make interactive-model MODEL=opus)
	@echo "$(GREEN)Starting interactive session with $(MODEL) model...$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.interactive --model $(MODEL)

.PHONY: interactive-quiet
interactive-quiet: ## Start interactive in quiet mode (no system logs)
	@echo "$(GREEN)Starting interactive session in quiet mode...$(NC)"
	@echo "$(YELLOW)Type 'exit' or 'quit' to end the session$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.interactive --quiet

# =============================================================================
# Testing
# =============================================================================
.PHONY: test
test: ## Run full test suite
	docker compose $(COMPOSE_FILES) exec main-agent pytest

.PHONY: test-unit
test-unit: ## Run unit tests only
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/unit/ -v

.PHONY: test-integration
test-integration: ## Run integration tests
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/ -v -m integration

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/e2e/ -v -m e2e

.PHONY: test-smoke
test-smoke: ## Run smoke tests
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/smoke/ -v -m smoke

.PHONY: coverage
coverage: ## Generate test coverage report
	docker compose $(COMPOSE_FILES) exec main-agent pytest --cov=src/harness --cov-report=html --cov-report=term

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	docker compose $(COMPOSE_FILES) exec main-agent pytest-watch

.PHONY: test-buffering
test-buffering: ## Test container stream buffering
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/test_container_buffering.py -v

.PHONY: test-signals
test-signals: ## Test signal handling and graceful shutdown
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/test_signal_handling.py -v

.PHONY: test-multi-agent
test-multi-agent: ## Test multi-agent coordination via Redis
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/test_multi_agent.py -v

.PHONY: test-all-multiagent
test-all-multiagent: ## Run all multi-agent implementation tests
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/test_container_buffering.py tests/integration/test_signal_handling.py tests/integration/test_multi_agent.py -v

# =============================================================================
# Code Quality
# =============================================================================
.PHONY: lint
lint: ## Run linter
	docker compose $(COMPOSE_FILES) exec main-agent ruff check src/ tests/

.PHONY: lint-fix
lint-fix: ## Run linter with auto-fix
	docker compose $(COMPOSE_FILES) exec main-agent ruff check --fix src/ tests/

.PHONY: format
format: ## Format code
	docker compose $(COMPOSE_FILES) exec main-agent ruff format src/ tests/

.PHONY: typecheck
typecheck: ## Run type checking
	docker compose $(COMPOSE_FILES) exec main-agent mypy src/

# =============================================================================
# Database Operations
# =============================================================================
.PHONY: db-shell
db-shell: ## PostgreSQL shell
	docker compose $(COMPOSE_FILES) exec postgres psql -U ${POSTGRES_USER:-claude} -d ${POSTGRES_DB:-claude_harness}

.PHONY: db-backup
db-backup: ## Backup database
	@mkdir -p backups
	docker compose $(COMPOSE_FILES) exec -T postgres pg_dump -U ${POSTGRES_USER:-claude} ${POSTGRES_DB:-claude_harness} | gzip > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(GREEN)Database backed up to backups/$(NC)"

.PHONY: db-restore
db-restore: ## Restore database from backup
	@read -p "Backup file: " file; \
	gunzip -c $$file | docker compose $(COMPOSE_FILES) exec -T postgres psql -U ${POSTGRES_USER:-claude} ${POSTGRES_DB:-claude_harness}

# =============================================================================
# Monitoring
# =============================================================================
.PHONY: metrics
metrics: ## Open Grafana dashboard
	@echo "$(GREEN)Opening Grafana at http://localhost:${GRAFANA_PORT:-3000}$(NC)"
	@echo "Default credentials: admin / ${GRAFANA_PASSWORD:-changeme123}"
	@open http://localhost:${GRAFANA_PORT:-3000} 2>/dev/null || xdg-open http://localhost:${GRAFANA_PORT:-3000} 2>/dev/null || echo "Open http://localhost:${GRAFANA_PORT:-3000}"

.PHONY: prometheus
prometheus: ## Open Prometheus UI
	@echo "$(GREEN)Opening Prometheus at http://localhost:${PROMETHEUS_PORT:-9090}$(NC)"
	@open http://localhost:${PROMETHEUS_PORT:-9090} 2>/dev/null || xdg-open http://localhost:${PROMETHEUS_PORT:-9090} 2>/dev/null || echo "Open http://localhost:${PROMETHEUS_PORT:-9090}"

.PHONY: health
health: ## Check service health
	@echo "$(GREEN)Checking service health...$(NC)"
	@docker compose $(COMPOSE_FILES) ps --format json | jq -r '.[] | "\(.Service): \(.Health)"'

# =============================================================================
# Maintenance & Cleanup
# =============================================================================
.PHONY: clean
clean: ## Remove containers and volumes
	docker compose $(COMPOSE_FILES) down -v --remove-orphans
	@echo "$(GREEN)Cleaned up containers and volumes$(NC)"

.PHONY: prune
prune: ## Prune unused Docker resources
	docker system prune -af --volumes --filter "label!=keep"
	@echo "$(GREEN)Docker resources pruned$(NC)"

.PHONY: reset
reset: clean ## Full reset (destructive!)
	@read -p "$(RED)This will delete ALL data. Are you sure? [y/N] $(NC)" -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf workspace/* memory/checkpoints/* memory/context/* logs/**/*; \
		echo "$(GREEN)Full reset complete$(NC)"; \
	fi

.PHONY: backup
backup: ## Backup workspace and checkpoints
	@mkdir -p backups
	@tar -czf backups/workspace_$(shell date +%Y%m%d_%H%M%S).tar.gz workspace/
	@tar -czf backups/memory_$(shell date +%Y%m%d_%H%M%S).tar.gz memory/
	@echo "$(GREEN)Backup complete in backups/$(NC)"

.PHONY: restore
restore: ## Restore from latest backup
	@echo "Available backups:"
	@ls -lh backups/ | grep -E 'workspace|memory'
	@read -p "Enter backup date (YYYYMMDD_HHMMSS): " date; \
	tar -xzf backups/workspace_$$date.tar.gz; \
	tar -xzf backups/memory_$$date.tar.gz; \
	echo "$(GREEN)Restore complete$(NC)"

# =============================================================================
# Production Deployment
# =============================================================================
.PHONY: prod
prod: ## Start production environment
	@ENVIRONMENT=production $(MAKE) up

.PHONY: prod-build
prod-build: ## Build for production
	@ENVIRONMENT=production $(MAKE) build

.PHONY: prod-deploy
prod-deploy: prod-build ## Build and deploy to production
	@ENVIRONMENT=production docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait

# =============================================================================
# CI/CD
# =============================================================================
.PHONY: ci-test
ci-test: ## Run tests in CI environment
	docker compose -f docker-compose.yml run --rm main-agent pytest --cov=src/ --cov-report=xml

.PHONY: ci-build
ci-build: ## Build for CI
	docker buildx build \
		--platform $(PLATFORM) \
		--target production \
		--cache-from type=registry,ref=$(REGISTRY)/main:cache \
		--cache-to type=inline \
		--tag $(REGISTRY)/main:$(IMAGE_TAG) \
		--load \
		-f agents/main/Dockerfile .

# =============================================================================
# Utility
# =============================================================================
.PHONY: version
version: ## Show version information
	@echo "Project: $(PROJECT_NAME)"
	@echo "Tag: $(IMAGE_TAG)"
	@echo "Platform: $(PLATFORM)"
	@echo "Registry: $(REGISTRY)"
	@echo "Environment: $(ENVIRONMENT)"

.PHONY: doctor
doctor: check-env ## Diagnose setup issues
	@echo "$(GREEN)Running diagnostics...$(NC)"
	@echo "Docker version:"
	@docker version
	@echo ""
	@echo "Docker Compose version:"
	@docker compose version
	@echo ""
	@echo "Python version:"
	@python3 --version
	@echo ""
	@echo "Platform: $(PLATFORM)"
	@echo ""
	@[ -f .env ] && echo "$(GREEN)✓ .env file exists$(NC)" || echo "$(RED)✗ .env file missing$(NC)"
	@[ -n "$$ANTHROPIC_API_KEY" ] && echo "$(GREEN)✓ ANTHROPIC_API_KEY set$(NC)" || echo "$(YELLOW)⚠ ANTHROPIC_API_KEY not set$(NC)"

.PHONY: install-deps
install-deps: ## Install Python dependencies locally
	pip install uv
	uv pip install --system -e ".[dev]"

# =============================================================================
# OrbStack Specific
# =============================================================================
.PHONY: orbstack-info
orbstack-info: ## Show OrbStack information
	@echo "Docker context: $(shell docker context show 2>/dev/null)"
	@echo "Platform: $(PLATFORM)"
	@docker info | grep "Operating System"

# =============================================================================
# Phony Targets
# =============================================================================
.PHONY: all
all: check-env build up ## Build and start everything
