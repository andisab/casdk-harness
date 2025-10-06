# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12

# =============================================================================
# Stage 1: Base - Common dependencies for all stages
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Stage 2: Dependencies - Install Python dependencies with caching
# =============================================================================
FROM base AS deps

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy only dependency files for better caching
COPY pyproject.toml ./

# Install dependencies with cache mount (OrbStack optimized)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e .

# =============================================================================
# Stage 3: Development - Full development environment
# =============================================================================
FROM deps AS development

# Install development dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e ".[dev]"

# Install Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

# Create non-root user for development
RUN groupadd -r claude && useradd -r -g claude claude

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Set ownership
RUN chown -R claude:claude /app

USER claude

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Development command (will be overridden by docker-compose)
CMD ["python", "-m", "harness.agent"]

# =============================================================================
# Stage 4: Builder - Build and prepare production assets
# =============================================================================
FROM deps AS builder

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Run any build steps (if needed)
RUN python -m compileall src/

# =============================================================================
# Stage 5: Production - Minimal production image
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS production

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python environment from deps stage
COPY --from=deps /usr/local/lib/python${PYTHON_VERSION}/site-packages /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code from builder
COPY --from=builder /app/src ./src
COPY --from=builder /app/config ./config

# Create non-root user
RUN groupadd -r claude && useradd -r -g claude -d /app -s /bin/bash claude

# Create necessary directories
RUN mkdir -p /workspace /memory /logs && \
    chown -R claude:claude /app /workspace /memory /logs

USER claude

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Signal handling
STOPSIGNAL SIGTERM

# Use tini for proper signal handling
ENTRYPOINT ["tini", "-g", "--"]

# Production command
CMD ["python", "-m", "harness.agent"]
