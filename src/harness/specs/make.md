>[toc]

# Makefile Specification for Docker Projects

## Key Principles

1. **Always use BuildKit**: `DOCKER_BUILDKIT=1`
2. **Cache aggressively**: Registry cache, cache mounts, inline cache
3. **Multi-stage builds**: Separate dev/build/prod stages
4. **Platform awareness**: Build for both amd64 and arm64
5. **Health checks**: Liveness and readiness probes
6. **Graceful shutdown**: Handle SIGTERM properly
7. **Volume optimization**: Exclude node_modules, build artifacts
8. **Environment separation**: Use compose overrides
9. **Security first**: Non-root users, secrets management
10. **OrbStack on macOS**: 2x performance improvement
11. **.dockerignore always**: Minimize context, exclude .git, .env, logs
12. **COPY late, COPY specific**: Dependencies first, source code last
13. **Parallel builds**: `docker compose build --parallel` when possible
14. **Dev = bind mounts**: Production = COPY for immutability
15. **Single command startup**: `make dev` should be all you need
16. **Fail fast**: Set `-e` in shell scripts, validate early
17. **Buildx by default**: `docker buildx install` for native builder
18. **Layer reuse**: Order Dockerfile commands by change frequency
19. **Named targets**: Use descriptive stage names for clarity
20. **Compose watch**: Use `develop.watch` for auto-rebuild in v2.22+

- [Official Documentation](https://www.gnu.org/software/make/manual/make.html)
- [Make Tutorial by Example](https://makefiletutorial.com/)
- [Awesome Make Resources](https://github.com/adelarsq/awesome-make)

## Core Configuration

```makefile
# Shell configuration
SHELL := /bin/bash
.DEFAULT_GOAL := help
.ONESHELL:
.SHELLFLAGS := -ec

# Environment loading
ENV_FILE := .env
-include $(ENV_FILE)
export

# BuildKit mandatory
export DOCKER_BUILDKIT := 1
export BUILDKIT_PROGRESS := plain
export COMPOSE_DOCKER_CLI_BUILD := 1

# Platform detection
ARCH := $(shell uname -m)
PLATFORM := $(if $(filter arm64,$(ARCH)),linux/arm64,linux/amd64)
PLATFORMS := linux/amd64,linux/arm64

# Project variables
PROJECT_NAME ?= $(shell basename $(PWD))
REGISTRY ?= ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*://;s/.git//')
IMAGE_TAG ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
ENVIRONMENT ?= development

# Compose file resolution
COMPOSE_FILES := -f docker-compose.yml
ifeq ($(ENVIRONMENT),production)
    COMPOSE_FILES += -f docker-compose.prod.yml
else ifneq (,$(wildcard docker-compose.override.yml))
    COMPOSE_FILES += -f docker-compose.override.yml
endif
```

## Build Targets

```makefile
# Development build with hot reload and watch mode
dev: check-env
	docker compose $(COMPOSE_FILES) up --build --remove-orphans --watch

# Production build with cache optimization
build:
	docker buildx build \
		--platform $(PLATFORM) \
		--target production \
		--cache-from type=registry,ref=$(REGISTRY)/$(PROJECT_NAME):cache \
		--cache-to type=inline \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--tag $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG) \
		--load .

# Multi-platform build with secrets
build-multi:
	docker buildx build \
		--platform $(PLATFORMS) \
		--target production \
		--secret id=npmrc,src=$$HOME/.npmrc \
		--secret id=github_token \
		--ssh default \
		--cache-from type=registry,ref=$(REGISTRY)/$(PROJECT_NAME):cache \
		--cache-to type=registry,ref=$(REGISTRY)/$(PROJECT_NAME):cache,mode=max,compression=zstd \
		--tag $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG) \
		--tag $(REGISTRY)/$(PROJECT_NAME):latest \
		--push .

# Build with SBOM and provenance
build-secure:
	docker buildx build \
		--platform $(PLATFORMS) \
		--sbom=true \
		--provenance=true \
		--tag $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG) \
		--push .
```

## Dockerfile Patterns

### Multi-stage with advanced BuildKit features
```dockerfile
# syntax=docker/dockerfile:1
ARG BUILDPLATFORM
ARG TARGETPLATFORM

# Dependencies stage with cache mounts
FROM --platform=$BUILDPLATFORM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --only=production

# Development stage with debugging
FROM node:20-alpine AS development
RUN apk add --no-cache git openssh-client
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=development
ENV WATCHPACK_POLLING=true
CMD ["npm", "run", "dev"]

# Builder stage with secrets and SSH
FROM --platform=$BUILDPLATFORM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Mount secrets for private npm registry
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    --mount=type=ssh \
    --mount=type=cache,target=/root/.npm \
    npm ci && npm run build

# Production stage with init system
FROM node:20-alpine AS production
RUN apk add --no-cache dumb-init tini
WORKDIR /app
USER node
COPY --chown=node:node --from=deps /app/node_modules ./node_modules
COPY --chown=node:node --from=builder /app/dist ./dist
EXPOSE 3000
# Enhanced health check with dependencies
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node healthcheck.js || exit 1
# Handle signals properly
STOPSIGNAL SIGTERM
ENTRYPOINT ["tini", "-g", "--"]
CMD ["node", "dist/index.js"]
```

### Python FastAPI with advanced patterns
```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim AS production
WORKDIR /app
# Install with bind mount for requirements
RUN --mount=type=bind,from=builder,source=/app/wheels,target=/wheels \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels /wheels/*
# Heredoc for complex scripts
RUN <<EOF
set -ex
apt-get update
apt-get install -y --no-install-recommends \
    curl \
    ca-certificates
rm -rf /var/lib/apt/lists/*
groupadd -r app && useradd -r -g app app
EOF
COPY --chown=app:app . .
USER app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose Patterns

### Base compose file with watch mode (v2.22+)
```yaml
services:
  app:
    build:
      context: .
      target: ${BUILD_TARGET:-development}
      cache_from:
        - type=registry,ref=${REGISTRY}/${PROJECT_NAME}:cache
    environment:
      - NODE_ENV=${NODE_ENV:-development}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: package.json
        - action: sync+restart
          path: ./config
          target: /app/config
```

### Development override with enhanced debugging
```yaml
services:
  app:
    build:
      target: development
    volumes:
      - .:/app:cached
      - /app/node_modules
      - /app/.next
    environment:
      - WATCHPACK_POLLING=true
      - NODE_OPTIONS=--inspect=0.0.0.0:9229
    command: npm run dev
    ports:
      - "9229:9229"  # Node.js debugger
```

### Production override with orchestration
```yaml
services:
  app:
    build:
      target: production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
    secrets:
      - db_password
      - jwt_secret

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

## Essential Make Patterns

### Help system
```makefile
.PHONY: help
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
```

### Environment validation
```makefile
check-env:
	@[ -f $(ENV_FILE) ] || cp .env.example $(ENV_FILE)
	@command -v docker >/dev/null 2>&1 || { echo "Docker not installed"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 required"; exit 1; }
```

### Service management and orchestration
```makefile
up: check-env ## Start services
	docker compose $(COMPOSE_FILES) up -d --remove-orphans

up-deps: ## Start only dependencies
	docker compose $(COMPOSE_FILES) up -d db redis rabbitmq

down: ## Stop services
	docker compose $(COMPOSE_FILES) down

logs: ## Tail logs
	docker compose $(COMPOSE_FILES) logs -f

shell: ## Container shell
	docker compose $(COMPOSE_FILES) exec app sh

restart: ## Restart services
	docker compose $(COMPOSE_FILES) restart

# Parallel service operations
build-parallel: ## Build all services in parallel
	docker compose $(COMPOSE_FILES) build --parallel

# Health-based startup
up-healthy: ## Start with health checks
	docker compose $(COMPOSE_FILES) up -d --wait --wait-timeout 60

# Service discovery
services: ## List all services
	@docker compose $(COMPOSE_FILES) ps --services

# Scale services
scale: ## Scale app service
	docker compose $(COMPOSE_FILES) up -d --scale app=3
```

### Database operations
```makefile
db-migrate: ## Run migrations
	docker compose $(COMPOSE_FILES) exec app npm run migrate

db-backup: ## Backup database
	docker compose $(COMPOSE_FILES) exec -T db pg_dump -U postgres $(DB_NAME) | gzip > backup_$(shell date +%Y%m%d_%H%M%S).sql.gz

db-restore: ## Restore from backup
	@read -p "Backup file: " file; \
	gunzip -c $$file | docker compose $(COMPOSE_FILES) exec -T db psql -U postgres $(DB_NAME)
```

### Testing
```makefile
test: ## Run tests
	docker compose $(COMPOSE_FILES) exec app npm test

test-ci: ## CI test runner
	docker compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from test
```

### Cleanup
```makefile
clean: ## Remove containers/volumes
	docker compose $(COMPOSE_FILES) down -v --remove-orphans

prune: ## Prune Docker resources
	docker system prune -af --volumes --filter "label!=keep"
```

## OrbStack Optimization

```makefile
# Detect OrbStack
DOCKER_CONTEXT := $(shell docker context show 2>/dev/null)
ifeq ($(DOCKER_CONTEXT),orbstack)
    export DOCKER_DEFAULT_PLATFORM := linux/arm64
    COMPOSE_FILES += -f docker-compose.orbstack.yml
endif

orbstack-migrate: ## Migrate to OrbStack
	orb migrate docker && docker context use orbstack
```

## Advanced Cache & Registry Optimization

### Multi-layer cache strategies
```makefile
# Registry cache with compression
BUILDX_CACHE_REGISTRY := --cache-from type=registry,ref=$(REGISTRY)/cache:latest \
                         --cache-to type=registry,ref=$(REGISTRY)/cache:latest,mode=max,compression=zstd,compression-level=3

# GitHub Actions cache
BUILDX_CACHE_GHA := --cache-from type=gha,scope=$(GITHUB_REF_NAME) \
                    --cache-to type=gha,scope=$(GITHUB_REF_NAME),mode=max

# S3 cache with expiration
BUILDX_CACHE_S3 := --cache-from type=s3,region=$(AWS_REGION),bucket=$(CACHE_BUCKET),name=$(PROJECT_NAME) \
                   --cache-to type=s3,region=$(AWS_REGION),bucket=$(CACHE_BUCKET),name=$(PROJECT_NAME),mode=max

# Azure Blob cache
BUILDX_CACHE_AZURE := --cache-from type=azblob,account_url=$(AZURE_URL),name=$(PROJECT_NAME) \
                      --cache-to type=azblob,account_url=$(AZURE_URL),name=$(PROJECT_NAME),mode=max

# Inline cache for backward compatibility
BUILDX_CACHE_INLINE := --cache-to type=inline \
                       --build-arg BUILDKIT_INLINE_CACHE=1
```

### Volume mount optimization
```makefile
# Platform-specific optimizations
VOLUME_OPTS := cached
ifeq ($(shell uname),Darwin)
    VOLUME_OPTS := delegated
endif

DEV_VOLUMES := -v $(PWD):/app:$(VOLUME_OPTS) \
               -v /app/node_modules \
               -v /app/.next \
               -v /app/__pycache__
```

## Security & Debugging Patterns

### Security scanning and compliance
```makefile
# Security scanning with multiple tools
scan: ## Run security scans
	@echo "Running Trivy scan..."
	@trivy image --severity HIGH,CRITICAL $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG)
	@echo "Running Snyk scan..."
	@snyk container test $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG) || true
	@echo "Generating SBOM..."
	@syft $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG) -o spdx-json > sbom.json

# Image signing with cosign
sign: ## Sign container image
	cosign sign --key cosign.key $(REGISTRY)/$(PROJECT_NAME):$(IMAGE_TAG)

# Secret generation with rotation
secrets: ## Generate secrets
	@mkdir -p secrets
	@openssl rand -base64 32 > secrets/jwt_secret.txt
	@openssl rand -base64 32 > secrets/db_password.txt
	@chmod 600 secrets/*.txt
	@echo "Secrets generated at $$(date)" >> secrets/.rotation.log
```

### Debug and troubleshooting targets
```makefile
# Debug container with tools
debug: ## Run debug container
	docker compose $(COMPOSE_FILES) run --rm \
		-e DEBUG=true \
		--entrypoint /bin/sh \
		app -c "apk add --no-cache curl jq htop && exec /bin/sh"

# Root shell for debugging
shell-root: ## Root shell access
	docker compose $(COMPOSE_FILES) exec -u root app sh

# Structured log following
logs-tail: ## Follow logs with filters
	docker compose $(COMPOSE_FILES) logs -f --tail=100 app | jq -R 'fromjson? // .'

# Container inspection
inspect: ## Inspect running containers
	@docker compose $(COMPOSE_FILES) ps --format json | jq '.'
	@docker inspect $$(docker compose $(COMPOSE_FILES) ps -q app) | jq '.[0].State'

# Docker events monitoring
events: ## Monitor Docker events
	docker events --filter container=$$(docker compose $(COMPOSE_FILES) ps -q app) \
		--format 'table {{.Time}}\t{{.Action}}\t{{.Type}}'
```

## CI/CD Integration

```makefile
# GitHub Actions
ci-build:
	docker buildx build \
		--platform $(PLATFORMS) \
		--cache-from type=gha \
		--cache-to type=gha,mode=max \
		--tag $(REGISTRY)/$(PROJECT_NAME):$(GITHUB_SHA) \
		--push .

# GitLab CI
ci-gitlab:
	docker buildx build \
		--platform $(PLATFORMS) \
		--cache-from type=registry,ref=$(CI_REGISTRY_IMAGE):cache \
		--cache-to type=registry,ref=$(CI_REGISTRY_IMAGE):cache,mode=max \
		--tag $(CI_REGISTRY_IMAGE):$(CI_COMMIT_SHA) \
		--push .
```

## Template Usage

```bash
# Initialize project
make check-env
make dev

# Production deployment
make build-multi
make prod

# Maintenance
make db-backup
make clean
make prune
```
