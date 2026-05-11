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
CYAN := \033[0;36m
NC := \033[0m

# =============================================================================
# Help Target
# =============================================================================
.PHONY: help
help: ## Show available targets
	@echo "$(GREEN)Claude Agent SDK Harness - Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Getting Started:$(NC)"
	@echo "  init                 Initialize project (first time setup)"
	@echo "  build                Build all services"
	@echo "  up / up-multi        Start services (background)"
	@echo "  down                 Stop all services"
	@echo "  doctor               Diagnose setup issues"
	@echo ""
	@echo "$(YELLOW)Interactive Mode:$(NC)"
	@echo "  interactive          Start interactive conversation"
	@echo "  interactive-debug    Interactive with DEBUG logs, raw SDK messages, per-turn stats"
	@echo ""
	@echo "$(YELLOW)Autonomous Mode:$(NC)"
	@echo "  autonomous           Start autonomous development"
	@echo "  autonomous-status    Show development progress"
	@echo "  init-spec            Create SPEC.md template"
	@echo ""
	@echo "$(YELLOW)CGF Optimization:$(NC)"
	@echo "  cgf-init             Initialize CGF workspace (NAME=x)"
	@echo "  optimize             Run CGF optimization (discovers SPEC.md)"
	@echo "  optimize-dryrun      Validate optimization setup"
	@echo "  cgf-status           Show optimization run status"
	@echo "  cgf-clean            Remove session state files"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  test                 Run full test suite"
	@echo "  test-unit            Run unit tests only"
	@echo "  test-integration     Run integration tests"
	@echo "  test-multi           Test multi-agent coordination"
	@echo "  coverage             Generate coverage report"
	@echo ""
	@echo "$(YELLOW)Code Quality:$(NC)"
	@echo "  lint / lint-fix      Run linter (with auto-fix)"
	@echo "  format               Format code"
	@echo "  typecheck            Run type checking"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  services             List all services"
	@echo "  logs / logs-main     View service logs"
	@echo "  shell                Shell into main agent"
	@echo "  health               Check service health"
	@echo ""
	@echo "$(YELLOW)Monitoring:$(NC)"
	@echo "  metrics              Open Grafana dashboard"
	@echo "  prometheus           Open Prometheus UI"
	@echo ""
	@echo "$(YELLOW)Maintenance:$(NC)"
	@echo "  clean                Remove containers and volumes"
	@echo "  prune                Prune Docker resources"
	@echo "  reset                Full reset (destructive)"
	@echo ""
	@echo "$(YELLOW)Tip:$(NC) Use MODEL=opus make interactive to change model"
	@echo "For details: cat QUICKSTART.md"
	@echo ""

# =============================================================================
# Getting Started
# =============================================================================
.PHONY: init
init: check-env ## Initialize project (first time setup)
	@echo ""
	@echo "$(GREEN)Welcome to Claude Agent SDK Harness!$(NC)"
	@echo ""
	@if [ -f $(ENV_FILE) ]; then \
		echo "$(GREEN)✓ .env file already exists$(NC)"; \
	else \
		cp .env.example $(ENV_FILE); \
		echo "$(GREEN)✓ Created .env from template$(NC)"; \
	fi
	@mkdir -p workspace memory/checkpoints memory/context logs/{main,reviewer,tester,orchestrator}
	@echo "$(GREEN)✓ Created directories$(NC)"
	@echo ""
	@echo "$(YELLOW)Next Steps:$(NC)"
	@echo "  1. Edit .env and set your ANTHROPIC_API_KEY"
	@echo "  2. Run: make prod"
	@echo "  3. Run: make interactive"
	@echo ""
	@echo "$(GREEN)See QUICKSTART.md for a 5-minute tutorial$(NC)"
	@echo ""

.PHONY: plugins-sync
plugins-sync: ## Clone or update local swe-marketplace plugin source (.plugins/swe-marketplace)
	@MARKETPLACE_DIR=".plugins/swe-marketplace"; \
	MARKETPLACE_URL="https://github.com/andisab/swe-marketplace.git"; \
	mkdir -p .plugins; \
	if [ -d "$$MARKETPLACE_DIR/.git" ]; then \
		echo "$(CYAN)Updating $$MARKETPLACE_DIR$(NC)"; \
		git -C "$$MARKETPLACE_DIR" fetch --quiet origin || { echo "$(RED)fetch failed (network or auth issue?)$(NC)"; exit 1; }; \
		if [ -n "$(SWE_MARKETPLACE_REF)" ]; then \
			git -C "$$MARKETPLACE_DIR" checkout --quiet "$(SWE_MARKETPLACE_REF)" || { echo "$(RED)checkout '$(SWE_MARKETPLACE_REF)' failed (unknown ref?)$(NC)"; exit 1; }; \
		else \
			DEFAULT_BRANCH=$$(git -C "$$MARKETPLACE_DIR" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || echo main); \
			git -C "$$MARKETPLACE_DIR" checkout --quiet "$$DEFAULT_BRANCH" || { echo "$(RED)checkout '$$DEFAULT_BRANCH' failed (detached HEAD with local changes?)$(NC)"; exit 1; }; \
			git -C "$$MARKETPLACE_DIR" pull --ff-only --quiet || { echo "$(RED)fast-forward pull failed (local divergence on '$$DEFAULT_BRANCH'?)$(NC)"; exit 1; }; \
		fi; \
	else \
		echo "$(CYAN)Cloning $$MARKETPLACE_URL → $$MARKETPLACE_DIR$(NC)"; \
		git clone --quiet "$$MARKETPLACE_URL" "$$MARKETPLACE_DIR" || { echo "$(RED)clone failed (network or auth issue?)$(NC)"; exit 1; }; \
		if [ -n "$(SWE_MARKETPLACE_REF)" ]; then \
			git -C "$$MARKETPLACE_DIR" checkout --quiet "$(SWE_MARKETPLACE_REF)" || { echo "$(RED)checkout '$(SWE_MARKETPLACE_REF)' failed (unknown ref?)$(NC)"; exit 1; }; \
		fi; \
	fi; \
	SHA=$$(git -C "$$MARKETPLACE_DIR" rev-parse --short HEAD); \
	echo "$(GREEN)✓ swe-marketplace synced at $$MARKETPLACE_DIR (HEAD=$$SHA)$(NC)"; \
	python3 scripts/synthesize_marketplace_manifests.py "$$MARKETPLACE_DIR" || { echo "$(RED)manifest synthesis failed$(NC)"; exit 1; }

.PHONY: check-env
check-env: ## Validate environment
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)Docker not installed$(NC)"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "$(RED)Docker Compose v2 required$(NC)"; exit 1; }
	@[ -f $(ENV_FILE) ] || { echo "$(YELLOW)Creating .env from .env.example...$(NC)"; cp .env.example $(ENV_FILE); }

# =============================================================================
# Development
# =============================================================================
.PHONY: dev
dev: check-env ## Start development environment with hot-reload (main-agent + monitoring)
	@echo "$(GREEN)Starting development environment...$(NC)"
	docker compose $(COMPOSE_FILES) up --build --remove-orphans --watch

.PHONY: dev-multi
dev-multi: check-env ## Start development with multi-agent (all agents + redis)
	@echo "$(GREEN)Starting multi-agent development environment...$(NC)"
	docker compose $(COMPOSE_FILES) --profile multi-agent up --build --remove-orphans --watch

# =============================================================================
# Build Targets
# =============================================================================
.PHONY: build
build: check-env ## Build all services
	@echo "$(GREEN)Building all services...$(NC)"
	docker compose $(COMPOSE_FILES) build --parallel

.PHONY: build-no-cache
build-no-cache: check-env ## Build without cache (clean build)
	docker compose $(COMPOSE_FILES) build --no-cache --parallel

# =============================================================================
# Service Management
# =============================================================================
.PHONY: up
up: check-env ## Start services (main-agent + monitoring only)
	docker compose $(COMPOSE_FILES) up -d --remove-orphans

.PHONY: up-multi
up-multi: check-env ## Start all services including multi-agent (reviewer, tester, redis)
	docker compose $(COMPOSE_FILES) --profile multi-agent up -d --remove-orphans

.PHONY: down
down: ## Stop all services (including multi-agent if running)
	docker compose $(COMPOSE_FILES) --profile multi-agent down

.PHONY: restart
restart: ## Restart all services
	docker compose $(COMPOSE_FILES) restart

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

.PHONY: shell-agent-two
shell-agent-two: ## Shell into agent-two (evaluator)
	docker compose $(COMPOSE_FILES) exec agent-two /bin/bash

.PHONY: shell-agent-three
shell-agent-three: ## Shell into agent-three (validator)
	docker compose $(COMPOSE_FILES) exec agent-three /bin/bash

# =============================================================================
# Interactive Agent
# =============================================================================
.PHONY: interactive
interactive: ## Start interactive conversation with main agent
	@echo "$(GREEN)Starting interactive session...$(NC)"
	@echo "$(YELLOW)Type 'exit' or 'quit' to end the session$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.interactive

.PHONY: interactive-debug
interactive-debug: ## Start interactive with verbose debug output (DEBUG logs + raw SDK msgs + per-turn stats)
	@echo "$(GREEN)Starting interactive session in debug mode...$(NC)"
	@echo "$(YELLOW)Type 'exit' or 'quit' to end the session$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.interactive --debug

# =============================================================================
# Autonomous Development Mode
# =============================================================================
.PHONY: autonomous
autonomous: ## Start autonomous development mode (quiet by default)
	@echo "$(GREEN)Starting autonomous development mode...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to gracefully stop$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.autonomous --quiet

.PHONY: autonomous-unsafe
autonomous-unsafe: ## Start autonomous with all bash commands allowed (dangerous!)
	@echo "$(RED)WARNING: All bash commands allowed - use with caution!$(NC)"
	docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.autonomous --quiet --allow-all-commands

.PHONY: autonomous-status
autonomous-status: ## Show autonomous development progress (use between sessions or from second terminal)
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)           AUTONOMOUS DEVELOPMENT STATUS$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@# Project Info
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -f /workspace/task_list.json ]; then \
			PROJECT=$$(jq -r ".project_name // \"Unknown\"" /workspace/task_list.json 2>/dev/null); \
			CREATED=$$(jq -r ".created_at // \"Unknown\"" /workspace/task_list.json 2>/dev/null); \
			echo "$(YELLOW)Project:$(NC) $$PROJECT"; \
			echo "$(YELLOW)Created:$(NC) $$CREATED"; \
			echo ""; \
		else \
			echo "$(RED)No task_list.json found - run make autonomous to initialize$(NC)"; \
			exit 0; \
		fi'
	@# Task Stats
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -f /workspace/task_list.json ]; then \
			TOTAL=$$(jq ".tasks | length" /workspace/task_list.json); \
			PASS=$$(jq "[.tasks[] | select(.status == \"PASS\")] | length" /workspace/task_list.json); \
			FAIL=$$(jq "[.tasks[] | select(.status == \"FAIL\")] | length" /workspace/task_list.json); \
			PENDING=$$(jq "[.tasks[] | select(.status == null)] | length" /workspace/task_list.json); \
			if [ $$TOTAL -gt 0 ]; then PCT=$$((PASS * 100 / TOTAL)); else PCT=0; fi; \
			echo "$(YELLOW)Progress:$(NC) $$PASS/$$TOTAL tasks complete ($$PCT%)"; \
			echo "  $(GREEN)✓ PASS:$(NC) $$PASS  $(RED)✗ FAIL:$(NC) $$FAIL  $(YELLOW)○ Pending:$(NC) $$PENDING"; \
			echo ""; \
		fi'
	@# Task List
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -f /workspace/task_list.json ]; then \
			echo "$(YELLOW)Tasks:$(NC)"; \
			jq -r ".tasks[] | \"  \" + (if .status == \"PASS\" then \"$(GREEN)✓$(NC)\" elif .status == \"FAIL\" then \"$(RED)✗$(NC)\" else \"$(YELLOW)○$(NC)\" end) + \" \" + .id + \": \" + .title" /workspace/task_list.json; \
			echo ""; \
		fi'
	@# Session Info
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -d /workspace/sessions ]; then \
			SESSION_COUNT=$$(ls /workspace/sessions/session_*.json 2>/dev/null | wc -l | tr -d " "); \
			if [ "$$SESSION_COUNT" -gt 0 ]; then \
				LATEST=$$(ls -t /workspace/sessions/session_*.json 2>/dev/null | head -1); \
				LATEST_NAME=$$(basename $$LATEST 2>/dev/null); \
				echo "$(YELLOW)Sessions:$(NC) $$SESSION_COUNT total (latest: $$LATEST_NAME)"; \
			else \
				echo "$(YELLOW)Sessions:$(NC) None yet"; \
			fi; \
		fi'
	@# Recent Commits
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -d /workspace/.git ]; then \
			echo ""; \
			echo "$(YELLOW)Recent Commits:$(NC)"; \
			cd /workspace && git log --oneline -3 2>/dev/null | sed "s/^/  /"; \
		fi'
	@# Next Steps
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		if [ -f /workspace/context/next-steps.md ]; then \
			echo ""; \
			echo "$(YELLOW)Next Steps:$(NC)"; \
			head -5 /workspace/context/next-steps.md | sed "s/^/  /"; \
		fi'
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(YELLOW)Tip:$(NC) Run 'make autonomous' to resume development"
	@echo ""

.PHONY: init-spec
init-spec: ## Copy SPEC.example.md template to workspace/SPEC.md
	@if [ -f workspace/SPEC.md ]; then \
		echo "$(YELLOW)workspace/SPEC.md already exists$(NC)"; \
		echo "Remove it first or edit directly: rm workspace/SPEC.md"; \
	else \
		cp docs/examples/SPEC.example.md workspace/SPEC.md; \
		echo "$(GREEN)Created workspace/SPEC.md from docs/examples/SPEC.example.md$(NC)"; \
		echo "Edit workspace/SPEC.md to describe your project, then run: make autonomous"; \
	fi

# =============================================================================
# CGF Optimization
# =============================================================================

.PHONY: cgf-init
cgf-init: ## Initialize CGF workspace (usage: make cgf-init NAME=my-agent)
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Usage: make cgf-init NAME=<workspace-name>$(NC)"; \
		echo ""; \
		echo "Example:"; \
		echo "  make cgf-init NAME=python-expert"; \
		echo ""; \
		echo "This creates workspace/python-expert/ with:"; \
		echo "  - SPEC.md (CGF optimization template)"; \
		exit 1; \
	fi
	@if [ -d "workspace/$(NAME)" ]; then \
		echo "$(YELLOW)workspace/$(NAME)/ already exists$(NC)"; \
		if [ -f "workspace/$(NAME)/SPEC.md" ]; then \
			echo "SPEC.md exists. Edit it or remove to start fresh."; \
		else \
			cp docs/examples/CGF_SPEC.example.md workspace/$(NAME)/SPEC.md; \
			echo "$(GREEN)Created workspace/$(NAME)/SPEC.md$(NC)"; \
		fi; \
	else \
		mkdir -p workspace/$(NAME); \
		cp docs/examples/CGF_SPEC.example.md workspace/$(NAME)/SPEC.md; \
		echo "$(GREEN)Created workspace/$(NAME)/$(NC)"; \
		echo "$(GREEN)Created workspace/$(NAME)/SPEC.md$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Copy your resource file to workspace/$(NAME)/"
	@echo "  2. Edit workspace/$(NAME)/SPEC.md with your optimization goals"
	@echo "  3. Run: make optimize"
.PHONY: cgf-status
cgf-status: ## Show status of CGF optimization runs
	@echo "$(GREEN)CGF Optimization Run Status$(NC)"
	@echo ""
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		found=0; \
		for state in workspace/*/sessions/task_list.json workspace/*/task_list.json workspace/*/sessions/optimization-state.json; do \
			if [ -f "$$state" ]; then \
				found=1; \
				WORKSPACE=$$(dirname "$$state"); \
				if [ "$$(basename $$WORKSPACE)" = "sessions" ]; then \
					WORKSPACE=$$(dirname "$$WORKSPACE"); \
				fi; \
				RESOURCE=$$(basename "$$WORKSPACE"); \
				STATE_FILE=$$(basename "$$state"); \
				if [ "$$STATE_FILE" = "optimization-state.json" ]; then \
					echo "$(CYAN)$$RESOURCE (Multi-Resource)$(NC)"; \
					SPEC_TYPE=$$(jq -r ".spec_type // \"unknown\"" "$$state" 2>/dev/null); \
					PHASE=$$(jq -r ".current_phase // \"UNKNOWN\"" "$$state" 2>/dev/null); \
					CREATED=$$(jq -r ".created_at // \"N/A\"" "$$state" 2>/dev/null); \
					TOTAL=$$(jq -r ".resources | length" "$$state" 2>/dev/null); \
					COMPLETED=$$(jq -r "[.resources | to_entries[] | select(.value.status == \"optimized\")] | length" "$$state" 2>/dev/null); \
					echo "  Type: $$SPEC_TYPE"; \
					echo "  Phase: $$PHASE"; \
					echo "  Resources: $$COMPLETED/$$TOTAL optimized"; \
					echo "  Created: $$CREATED"; \
					jq -r ".resources | to_entries[] | \"    - \" + .key + \": \" + .value.status + (if .value.quality.overall then \" (\" + (.value.quality.overall | tostring) + \")\" else \"\" end)" "$$state" 2>/dev/null; \
				else \
					PHASE=$$(jq -r ".current_phase // \"UNKNOWN\"" "$$state" 2>/dev/null); \
					CREATED=$$(jq -r ".created_at // \"N/A\"" "$$state" 2>/dev/null); \
					ITERATION=$$(jq -r ".iteration // 0" "$$state" 2>/dev/null); \
					echo "$(YELLOW)$$RESOURCE$(NC)"; \
					echo "  Phase: $$PHASE (iteration $$ITERATION)"; \
					echo "  Created: $$CREATED"; \
				fi; \
				if [ -f "$$WORKSPACE/SPEC.md" ]; then \
					if grep -q "## Capabilities" "$$WORKSPACE/SPEC.md" 2>/dev/null; then \
						echo "  Spec: SPEC.md $(CYAN)(multi-resource)$(NC) $(GREEN)✓$(NC)"; \
					else \
						echo "  Spec: SPEC.md $(GREEN)✓$(NC)"; \
					fi; \
				elif [ -f "$$WORKSPACE/cgf_spec.yaml" ]; then \
					echo "  Spec: cgf_spec.yaml $(GREEN)✓$(NC)"; \
				fi; \
				echo ""; \
			fi; \
		done; \
		if [ $$found -eq 0 ]; then \
			echo "No active CGF optimization runs"; \
			echo ""; \
			echo "Start one with:"; \
			echo "  make cgf-init NAME=my-project     # Create workspace with SPEC.md"; \
			echo "  make optimize                     # Run optimization"; \
		fi'

.PHONY: cgf-clean
cgf-clean: ## Remove CGF run state files (keeps artifacts)
	@echo "$(YELLOW)Removing CGF run state files (sessions/ directories)...$(NC)"
	@docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
		rm -rf workspace/*/sessions 2>/dev/null; \
		rm -f workspace/*/task_list.json workspace/*/qa_session.json 2>/dev/null; \
		echo "$(GREEN)CGF session states cleared$(NC)"; \
		echo "Research and optimized files preserved."'

.PHONY: cgf-reset
cgf-reset: ## Remove all CGF workspaces (destructive)
	@read -p "$(RED)This will delete all CGF workspace directories. Are you sure? [y/N] $(NC)" -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose $(COMPOSE_FILES) exec -T main-agent bash -c '\
			rm -rf workspace/*/sessions workspace/*/research workspace/*/reviews 2>/dev/null; \
			rm -f workspace/*/task_list.json workspace/*/qa_session.json workspace/*/cgf_spec.yaml 2>/dev/null; \
			rm -f workspace/*/*-v*.md workspace/*/*-orig.md 2>/dev/null; \
			echo "$(GREEN)CGF workspaces reset$(NC)"'; \
	fi

# =============================================================================
# CGF Optimization CLI
# =============================================================================
# Usage:
#   make optimize                       # Discover SPEC.md automatically
#
# SPEC.md auto-discovery:
#   - Exactly one SPEC.md must exist in workspace/
#   - If multiple found, an error is thrown (user must delete extras)
#   - If none found, user is prompted to create one
#
# Two-phase optimization session (runs in Docker like autonomous mode):
#   1. Q&A Phase: cgf-initializer gathers requirements interactively
#   2. Optimization Phase: cgf-orchestrator runs autonomous optimization
#
# Workspace Structure (SPEC.md location = workspace root):
#   {workspace}/
#   ├── SPEC.md                      # Optimization spec (defines workspace root)
#   ├── {resource}.md                # Original resource (never modified)
#   ├── {resource}-v1.md             # First optimization
#   ├── research/                    # Research artifacts
#   └── sessions/                    # Runtime state (delete to reset)
#
# Environment variables (set in .env or override):
#   CGF_OPTIMIZER_MODE   - agentic | python | both (default: agentic)
#   CGF_ITERATIONS       - max iterations per section (default: 10)
#   CGF_ITERATION_REVIEW - pause for review after each (default: false)
#   CGF_EVAL_MODEL       - sonnet | haiku | opus (default: sonnet)
#   CGF_VERBOSE          - show progress (default: true)
#
# Multi-Resource Optimization:
#   CGF_QUALITY_THRESHOLD - quality target per resource (default: 0.85)
#   CGF_MAX_ITERATIONS    - max iterations per resource (default: 5)
#   CGF_PARALLEL_GEN      - generate resources in parallel (default: true)

.PHONY: optimize
optimize: ## Run CGF optimization (auto-discovers SPEC.md)
	@echo "$(GREEN)Discovering SPEC.md in workspace...$(NC)"
	@SPEC_COUNT=$$(find workspace -name "SPEC.md" -type f 2>/dev/null | wc -l | tr -d ' '); \
	if [ "$$SPEC_COUNT" -eq 0 ]; then \
		echo "$(RED)Error: No SPEC.md found in workspace/$(NC)"; \
		echo ""; \
		echo "Create one to start optimization:"; \
		echo "  make cgf-init NAME=my-project"; \
		exit 1; \
	elif [ "$$SPEC_COUNT" -gt 1 ]; then \
		echo "$(RED)Error: Multiple SPEC.md files found:$(NC)"; \
		find workspace -name "SPEC.md" -type f 2>/dev/null | sed 's/^/  - /'; \
		echo ""; \
		echo "Please keep only one SPEC.md file in workspace/"; \
		exit 1; \
	else \
		SPEC_PATH=$$(find workspace -name "SPEC.md" -type f 2>/dev/null); \
		SPEC_DIR=$$(dirname "$$SPEC_PATH"); \
		echo "$(GREEN)Found: $$SPEC_PATH$(NC)"; \
		if grep -q "## Capabilities" "$$SPEC_PATH" 2>/dev/null; then \
			echo "$(CYAN)Detected: Multi-resource SPEC.md$(NC)"; \
			docker compose $(COMPOSE_FILES) exec -it main-agent python -c "\
from harness.optimization.multi_resource_orchestrator import run_multi_resource_optimization; \
import asyncio; \
result = asyncio.run(run_multi_resource_optimization('/$$SPEC_DIR', verbose=True)); \
print('Success!' if result.success else f'Failed: {result.error}')" 2>/dev/null || \
			docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.cgf_session --path "/$$SPEC_DIR"; \
		else \
			docker compose $(COMPOSE_FILES) exec -it main-agent python -m harness.cgf_session --path "/$$SPEC_DIR"; \
		fi; \
	fi

.PHONY: optimize-dryrun
optimize-dryrun: ## Validate optimization setup
	@echo "$(GREEN)CGF Optimization Setup Check$(NC)"
	@echo ""
	@echo "  Discovering SPEC.md files in workspace/..."
	@SPEC_COUNT=$$(find workspace -name "SPEC.md" -type f 2>/dev/null | wc -l | tr -d ' '); \
	if [ "$$SPEC_COUNT" -eq 0 ]; then \
		echo "  $(RED)No SPEC.md found in workspace/$(NC)"; \
		echo ""; \
		echo "  Create one to start optimization:"; \
		echo "    make cgf-init NAME=my-project"; \
		exit 1; \
	elif [ "$$SPEC_COUNT" -eq 1 ]; then \
		SPEC_PATH=$$(find workspace -name "SPEC.md" -type f 2>/dev/null); \
		SPEC_DIR=$$(dirname "$$SPEC_PATH"); \
		echo "  SPEC.md:      $$SPEC_PATH $(GREEN)✓$(NC)"; \
		echo "  Workspace:    $$SPEC_DIR/"; \
		if grep -q "## Capabilities" "$$SPEC_PATH" 2>/dev/null; then \
			echo "  Type:         $(CYAN)Multi-resource SPEC$(NC)"; \
		else \
			echo "  Type:         Single-resource SPEC"; \
		fi; \
	else \
		echo "  $(RED)Multiple SPEC.md files found ($$SPEC_COUNT):$(NC)"; \
		find workspace -name "SPEC.md" -type f 2>/dev/null | sed 's/^/    - /'; \
		echo ""; \
		echo "  Please keep only one SPEC.md file in workspace/"; \
		exit 1; \
	fi
	@echo ""
	@echo "$(GREEN)Environment Settings:$(NC)"
	@echo "  CGF_OPTIMIZER_MODE:     $${CGF_OPTIMIZER_MODE:-agentic}"
	@echo "  CGF_ITERATIONS:         $${CGF_ITERATIONS:-10}"
	@echo "  CGF_ITERATION_REVIEW:   $${CGF_ITERATION_REVIEW:-false}"
	@echo "  CGF_EVAL_MODEL:         $${CGF_EVAL_MODEL:-sonnet}"
	@echo "  CGF_VERBOSE:            $${CGF_VERBOSE:-true}"
	@echo "  CGF_QUALITY_THRESHOLD:  $${CGF_QUALITY_THRESHOLD:-0.85}"
	@echo "  CGF_MAX_ITERATIONS:     $${CGF_MAX_ITERATIONS:-5}"
	@echo ""
	@echo "$(GREEN)Ready to optimize. Run:$(NC)"
	@echo "  make optimize"

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

.PHONY: test-multi
test-multi: ## Test multi-agent coordination via Redis
	docker compose $(COMPOSE_FILES) exec main-agent pytest tests/integration/test_multi_agent.py -v

.PHONY: coverage
coverage: ## Generate test coverage report
	docker compose $(COMPOSE_FILES) exec main-agent pytest --cov=src/harness --cov-report=html --cov-report=term

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

.PHONY: reset-workspace
reset-workspace: ## Reset workspace and sessions (clears all project files)
	@read -p "$(YELLOW)This will delete workspace contents and session logs. Are you sure? [y/N] $(NC)" -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf workspace/SPEC.md workspace/task_list.json workspace/context/* workspace/sessions/* 2>/dev/null || true; \
		echo "$(GREEN)Workspace reset complete$(NC)"; \
	fi

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
prod: ## Build and start production environment
	@ENVIRONMENT=production $(MAKE) build
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
doctor: ## Diagnose setup issues
	@echo ""
	@echo "$(GREEN)Claude Agent SDK Harness - Setup Diagnostics$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Docker Check$(NC)"
	@command -v docker >/dev/null 2>&1 && echo "  $(GREEN)✓ Docker installed$(NC)" || echo "  $(RED)✗ Docker not installed$(NC)"
	@docker info >/dev/null 2>&1 && echo "  $(GREEN)✓ Docker daemon running$(NC)" || echo "  $(RED)✗ Docker daemon not running - start Docker Desktop$(NC)"
	@docker compose version >/dev/null 2>&1 && echo "  $(GREEN)✓ Docker Compose v2 available$(NC)" || echo "  $(RED)✗ Docker Compose v2 required$(NC)"
	@echo ""
	@echo "$(YELLOW)2. Environment Check$(NC)"
	@[ -f .env ] && echo "  $(GREEN)✓ .env file exists$(NC)" || echo "  $(RED)✗ .env file missing - run 'make init'$(NC)"
	@if [ -f .env ]; then \
		if grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then \
			echo "  $(GREEN)✓ ANTHROPIC_API_KEY appears configured$(NC)"; \
		elif grep -q "^ANTHROPIC_API_KEY=" .env 2>/dev/null; then \
			echo "  $(YELLOW)⚠ ANTHROPIC_API_KEY set but may be placeholder$(NC)"; \
		else \
			echo "  $(RED)✗ ANTHROPIC_API_KEY not set in .env$(NC)"; \
		fi \
	fi
	@echo ""
	@echo "$(YELLOW)3. Port Availability$(NC)"
	@lsof -i :8080 >/dev/null 2>&1 && echo "  $(YELLOW)⚠ Port 8080 in use (main agent)$(NC)" || echo "  $(GREEN)✓ Port 8080 available$(NC)"
	@lsof -i :3000 >/dev/null 2>&1 && echo "  $(YELLOW)⚠ Port 3000 in use (grafana)$(NC)" || echo "  $(GREEN)✓ Port 3000 available$(NC)"
	@lsof -i :9090 >/dev/null 2>&1 && echo "  $(YELLOW)⚠ Port 9090 in use (prometheus)$(NC)" || echo "  $(GREEN)✓ Port 9090 available$(NC)"
	@echo ""
	@echo "$(YELLOW)4. Container Status$(NC)"
	@if docker compose $(COMPOSE_FILES) ps --quiet 2>/dev/null | grep -q .; then \
		echo "  $(GREEN)✓ Containers running$(NC)"; \
		docker compose $(COMPOSE_FILES) ps --format "table {{.Service}}\t{{.Status}}" 2>/dev/null | head -5; \
	else \
		echo "  $(YELLOW)⚠ No containers running - run 'make dev' or 'make prod'$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)5. Platform Info$(NC)"
	@echo "  Platform: $(PLATFORM)"
	@echo "  Docker context: $$(docker context show 2>/dev/null || echo 'default')"
	@echo ""
	@echo "$(GREEN)If all checks pass, run: make dev && make interactive$(NC)"
	@echo ""

# =============================================================================
# SSH Setup (for private repositories)
# =============================================================================
.PHONY: ssh-init
ssh-init: ## Initialize SSH directory structure
	@mkdir -p .ssh
	@chmod 700 .ssh
	@[ -f .ssh/config ] || cp .ssh/config.example .ssh/config 2>/dev/null || touch .ssh/config
	@chmod 600 .ssh/config
	@echo "$(GREEN)SSH directory initialized.$(NC)"
	@echo "$(YELLOW)Run 'make ssh-keygen-github' and 'make ssh-keygen-gitlab' to generate keys.$(NC)"

.PHONY: ssh-known-hosts
ssh-known-hosts: ## Pre-populate known_hosts with GitHub/GitLab host keys (required for containers)
	@echo "$(GREEN)Fetching host keys for GitHub and GitLab...$(NC)"
	@ssh-keyscan -t ed25519,rsa github.com >> .ssh/known_hosts 2>/dev/null
	@ssh-keyscan -t ed25519,rsa gitlab.com >> .ssh/known_hosts 2>/dev/null
	@sort -u .ssh/known_hosts -o .ssh/known_hosts
	@chmod 644 .ssh/known_hosts
	@echo "$(GREEN)known_hosts updated. Host keys added for:$(NC)"
	@grep -c "github.com" .ssh/known_hosts | xargs -I{} echo "  - github.com ({} keys)"
	@grep -c "gitlab.com" .ssh/known_hosts | xargs -I{} echo "  - gitlab.com ({} keys)"

.PHONY: ssh-keygen-github
ssh-keygen-github: ## Generate dedicated GitHub SSH key
	@ssh-keygen -t ed25519 -C "harness-github" -f .ssh/id_ed25519_github -N ""
	@chmod 600 .ssh/id_ed25519_github
	@echo "$(GREEN)GitHub key generated. Add this public key to GitHub:$(NC)"
	@cat .ssh/id_ed25519_github.pub

.PHONY: ssh-keygen-gitlab
ssh-keygen-gitlab: ## Generate dedicated GitLab SSH key
	@ssh-keygen -t ed25519 -C "harness-gitlab" -f .ssh/id_ed25519_gitlab -N ""
	@chmod 600 .ssh/id_ed25519_gitlab
	@echo "$(GREEN)GitLab key generated. Add this public key to GitLab:$(NC)"
	@cat .ssh/id_ed25519_gitlab.pub

.PHONY: ssh-test
ssh-test: ssh-known-hosts ## Test SSH connections to GitHub and GitLab (also updates known_hosts)
	@echo "$(GREEN)Testing GitHub SSH...$(NC)"
	@ssh -i .ssh/id_ed25519_github -T git@github.com 2>&1 || true
	@echo ""
	@echo "$(GREEN)Testing GitLab SSH...$(NC)"
	@ssh -i .ssh/id_ed25519_gitlab -T git@gitlab.com 2>&1 || true
