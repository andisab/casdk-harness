# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12

# =============================================================================
# Stage 1: Base - Common dependencies for all stages
# =============================================================================
# Pinned by digest for reproducibility. Resolved 2026-05-07; bump deliberately.
FROM python:${PYTHON_VERSION}-slim@sha256:46cb7cc2877e60fbd5e21a9ae6115c30ace7a077b9f8772da879e4590c18c2e3 AS base

# Install system dependencies including Node.js for MCP servers.
# Includes Playwright browser dependencies for Chromium.
# BuildKit cache mounts speed up repeat builds; sharing=locked avoids parallel
# corruption when the same layer is used by multiple stages. The cache mount
# replaces the older `rm -rf /var/lib/apt/lists/*` pattern.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
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
    libxrandr2

# uv from the official Astral image — single source of truth across all stages.
# Avoids a `pip install uv` step in deps + a separate `curl install.sh` in dev.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# uv on Linux containers can't hardlink between the cache mount and target FS.
# Setting copy mode silences the warning and avoids per-install fallback logic.
ENV UV_LINK_MODE=copy

WORKDIR /app

# =============================================================================
# Stage 2: Dependencies - Install Python dependencies with caching
# =============================================================================
FROM base AS deps

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

# Install tini (for signal handling) and the GitHub CLI in a single layer.
# Combining: shared apt-update overhead, single rm at the end via cache mount.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
        tini \
        gpg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh

# Install development dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e ".[dev]"

# Install Claude Code CLI via npm (more reliable than install.sh)
RUN --mount=type=cache,target=/root/.cache/npm \
    npm install -g @anthropic-ai/claude-code

# Install GitLab CLI (glab)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then GLAB_ARCH="arm64"; else GLAB_ARCH="amd64"; fi && \
    curl -fsSL "https://gitlab.com/gitlab-org/cli/-/releases/v1.46.1/downloads/glab_1.46.1_Linux_${GLAB_ARCH}.tar.gz" | tar -xz -C /tmp && \
    mv /tmp/bin/glab /usr/local/bin/glab && \
    chmod +x /usr/local/bin/glab && \
    rm -rf /tmp/bin

# IaC eval tooling (D8): used by Phase A graders for terraform validate,
# helm lint, kubeconform schema checks, tfsec / trivy static analysis.
# All versions pinned for reproducibility; bump deliberately.
# - helm v3.16.3 (Kubernetes package manager + linter)
# - kubeconform v0.6.7 (K8s manifest schema validation)
# - tfsec v1.28.11 (Terraform static security analysis; soon-deprecated in
#   favor of trivy-config, but still the smallest single-binary option)
# - trivy v0.58.1 (filesystem + container + IaC scanning)
ARG HELM_VERSION=3.16.3
ARG KUBECONFORM_VERSION=0.6.7
ARG TFSEC_VERSION=1.28.11
ARG TRIVY_VERSION=0.58.1
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then \
        GO_ARCH="arm64"; TRIVY_ARCH="ARM64"; \
    else \
        GO_ARCH="amd64"; TRIVY_ARCH="64bit"; \
    fi && \
    # helm
    curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${GO_ARCH}.tar.gz" \
        | tar -xz -C /tmp && \
    mv "/tmp/linux-${GO_ARCH}/helm" /usr/local/bin/helm && \
    rm -rf "/tmp/linux-${GO_ARCH}" && \
    # kubeconform
    curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${GO_ARCH}.tar.gz" \
        | tar -xz -C /tmp && \
    mv /tmp/kubeconform /usr/local/bin/kubeconform && \
    # tfsec
    curl -fsSL "https://github.com/aquasecurity/tfsec/releases/download/v${TFSEC_VERSION}/tfsec-linux-${GO_ARCH}" \
        -o /usr/local/bin/tfsec && \
    chmod +x /usr/local/bin/tfsec && \
    # trivy (uses "64bit" / "ARM64" suffix instead of go-style amd64/arm64)
    curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-${TRIVY_ARCH}.tar.gz" \
        | tar -xz -C /tmp trivy && \
    mv /tmp/trivy /usr/local/bin/trivy

# Install Chrome-for-Testing for the @playwright/mcp server.
#
# Why CfT and not chrome / chromium:
# - `chrome` (Google Chrome stable) has no Linux arm64 build — fails on Apple Silicon.
# - `chromium` (the regular Playwright channel) installs into a different cache
#   layout than @playwright/mcp's `--browser=chromium` expects.
# - `chrome-for-testing` is Playwright's cross-platform CfT build (arm64 + amd64)
#   and is what the MCP server actually launches.
#
# Permissions follow Microsoft's official Playwright Docker image pattern:
# `chmod -R 777 ${PLAYWRIGHT_BROWSERS_PATH}` — browser binaries stay root-owned
# (read-only at runtime), but the parent dir is world-writable so the MCP can
# create per-session profile dirs (`mcp-chrome-for-testing-XXX`) at launch.
# Without this, the runtime user gets EACCES on first browser_navigate.
#
# PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright makes browsers user-agnostic so
# install-as-root and run-as-claude resolve the same path.
#
# @playwright/mcp is pinned to a known-good version (lessons learned from the
# `@latest`-resolution drift between 2026-05-06 and 2026-05-07 builds, where
# the default browser channel changed). Bump deliberately on a schedule.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
ARG PLAYWRIGHT_MCP_VERSION=0.0.74
RUN --mount=type=cache,target=/root/.cache/npm \
    npx playwright install-deps chromium \
    && mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
    && npx @playwright/mcp@${PLAYWRIGHT_MCP_VERSION} install-browser chrome-for-testing \
    && chmod -R 777 ${PLAYWRIGHT_BROWSERS_PATH}

# Create non-root user for development with home directory
RUN groupadd -r claude && \
    useradd -r -g claude -m -d /home/claude claude

# Copy source code and tests with claude ownership baked in (skips a chown layer).
COPY --chown=claude:claude src/ ./src/
COPY --chown=claude:claude config/ ./config/
COPY --chown=claude:claude tests/ ./tests/
COPY --chown=claude:claude .claude/ ./.claude/

# Clone swe-marketplace plugin source. Pin via SWE_MARKETPLACE_REF (build arg)
# for reproducibility; empty = HEAD of default branch.
ARG SWE_MARKETPLACE_REF=
COPY scripts/synthesize_marketplace_manifests.py /tmp/synthesize_marketplace_manifests.py
RUN git clone https://github.com/andisab/swe-marketplace.git /opt/plugins/swe-marketplace \
    && if [ -n "$SWE_MARKETPLACE_REF" ]; then \
         git -C /opt/plugins/swe-marketplace checkout "$SWE_MARKETPLACE_REF"; \
       fi \
    && python3 /tmp/synthesize_marketplace_manifests.py /opt/plugins/swe-marketplace \
    && rm -rf /opt/plugins/swe-marketplace/.git /tmp/synthesize_marketplace_manifests.py \
    && chown -R claude:claude /app /opt/plugins
# /opt/ms-playwright stays root:root — browsers are read-only at runtime
# (mode 0755 lets claude execute them) and chowning it here would duplicate
# the entire ~956 MB browser tree into this layer.

# Set unbuffered output (CRITICAL for container streams)
ENV PYTHONUNBUFFERED=1

# OpenTelemetry defaults (overridable via docker-compose / env). When the
# bundled otel-collector service is unreachable (e.g., direct `docker run`),
# the SDK silently no-ops; flip CLAUDE_CODE_ENABLE_TELEMETRY=0 to fully disable.
ENV CLAUDE_CODE_ENABLE_TELEMETRY=1
ENV OTEL_METRICS_EXPORTER=otlp
ENV OTEL_LOGS_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ENV OTEL_METRIC_EXPORT_INTERVAL=10000
ENV OTEL_METRICS_INCLUDE_SESSION_ID=false
ENV OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false
ENV OTEL_SERVICE_NAME=casdk-harness

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
COPY .claude/ ./.claude/

# Clone swe-marketplace plugin source for production image. Pin via
# SWE_MARKETPLACE_REF (build arg); empty = HEAD of default branch.
ARG SWE_MARKETPLACE_REF=
COPY scripts/synthesize_marketplace_manifests.py /tmp/synthesize_marketplace_manifests.py
RUN git clone https://github.com/andisab/swe-marketplace.git /opt/plugins/swe-marketplace \
    && if [ -n "$SWE_MARKETPLACE_REF" ]; then \
         git -C /opt/plugins/swe-marketplace checkout "$SWE_MARKETPLACE_REF"; \
       fi \
    && python3 /tmp/synthesize_marketplace_manifests.py /opt/plugins/swe-marketplace \
    && rm -rf /opt/plugins/swe-marketplace/.git /tmp/synthesize_marketplace_manifests.py

# Run any build steps (if needed)
RUN python -m compileall src/

# =============================================================================
# Stage 5: Production - Minimal production image
# =============================================================================
FROM python:${PYTHON_VERSION}-slim@sha256:46cb7cc2877e60fbd5e21a9ae6115c30ace7a077b9f8772da879e4590c18c2e3 AS production

# Install only runtime dependencies (cached apt lists; no manual rm).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tini

WORKDIR /app

# Copy Python environment from deps stage
COPY --from=deps /usr/local/lib/python${PYTHON_VERSION}/site-packages /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Create non-root user
RUN groupadd -r claude && useradd -r -g claude -d /app -s /bin/bash claude

# Copy application code from builder, owned by claude.
COPY --from=builder --chown=claude:claude /app/src ./src
COPY --from=builder --chown=claude:claude /app/config ./config
COPY --from=builder --chown=claude:claude /app/.claude ./.claude

# Copy swe-marketplace plugin source from builder, owned by claude.
COPY --from=builder --chown=claude:claude /opt/plugins/swe-marketplace /opt/plugins/swe-marketplace

# Create necessary writable directories
RUN mkdir -p /workspace /memory /logs && \
    chown -R claude:claude /workspace /memory /logs

# Set unbuffered output (CRITICAL for container streams)
ENV PYTHONUNBUFFERED=1

# OpenTelemetry defaults (overridable via docker-compose / env). See
# development stage above for behavior notes.
ENV CLAUDE_CODE_ENABLE_TELEMETRY=1
ENV OTEL_METRICS_EXPORTER=otlp
ENV OTEL_LOGS_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ENV OTEL_METRIC_EXPORT_INTERVAL=10000
ENV OTEL_METRICS_INCLUDE_SESSION_ID=false
ENV OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false
ENV OTEL_SERVICE_NAME=casdk-harness

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
