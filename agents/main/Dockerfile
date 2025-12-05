# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12

# =============================================================================
# Stage 1: Base - Common dependencies for all stages
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS base

# Install system dependencies including Node.js for MCP servers
# Includes Playwright browser dependencies for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    nodejs \
    npm \
    openssh-client \
    # Playwright browser dependencies (Chromium)
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Stage 2: Dependencies - Install Python dependencies with caching
# =============================================================================
FROM base AS deps

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies with cache mount (OrbStack optimized)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e .

# =============================================================================
# Stage 3: Development - Full development environment
# =============================================================================
FROM deps AS development

# Install tini for signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Install development dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e ".[dev]"

# Install Claude Code CLI and make it accessible to all users
RUN curl -fsSL https://claude.ai/install.sh | bash && \
    cp /root/.local/bin/claude /usr/local/bin/claude && \
    chmod +x /usr/local/bin/claude

# Install standalone uv/uvx for running Python MCP servers
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx && \
    chmod +x /usr/local/bin/uv /usr/local/bin/uvx

# Install GitHub CLI (gh)
RUN apt-get update && apt-get install -y --no-install-recommends gpg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Install GitLab CLI (glab)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then GLAB_ARCH="arm64"; else GLAB_ARCH="amd64"; fi && \
    curl -fsSL "https://gitlab.com/gitlab-org/cli/-/releases/v1.46.1/downloads/glab_1.46.1_Linux_${GLAB_ARCH}.tar.gz" | tar -xz -C /tmp && \
    mv /tmp/bin/glab /usr/local/bin/glab && \
    chmod +x /usr/local/bin/glab && \
    rm -rf /tmp/bin

# Install Playwright Chromium browser for MCP server
# Must be done before switching to non-root user
RUN --mount=type=cache,target=/root/.cache/npm \
    npx playwright install --with-deps chromium

# Create non-root user for development with home directory
RUN groupadd -r claude && \
    useradd -r -g claude -m -d /home/claude claude && \
    chown -R claude:claude /home/claude

# Copy source code and tests
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/

# Set ownership
RUN chown -R claude:claude /app

# Set unbuffered output (CRITICAL for container streams)
ENV PYTHONUNBUFFERED=1

USER claude

# Signal handling
STOPSIGNAL SIGTERM

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

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

# Set unbuffered output (CRITICAL for container streams)
ENV PYTHONUNBUFFERED=1

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
