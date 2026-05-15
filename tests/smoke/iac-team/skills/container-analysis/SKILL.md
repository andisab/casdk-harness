---
name: container-analysis
description: >
  Dockerfile best practices, multi-stage builds, security scanning patterns, CI/CD validation pipelines, and container optimization strategies.

  Activate when user mentions: Dockerfile, container image, multi-stage build, container security,
  image optimization, docker build, container layers, base image, distroless, alpine, scratch image,
  container scanning, vulnerability scanning, dockerfile lint, hadolint, trivy, security pipeline,
  SBOM generation, container validation, CI/CD security gates, image attestation.

  Use for: Dockerfile generation patterns, security hardening, build optimization, layer caching strategies,
  CI/CD security integration, vulnerability management, SBOM generation, policy-as-code validation.

  Do NOT use for: Runtime orchestration (use kubernetes-native skill), CI/CD pipelines (use github-actions-iac skill),
  infrastructure provisioning (use terraform-patterns skill).
---

# Container Analysis Skill

## Purpose

Provides Dockerfile generation patterns, security best practices, CI/CD validation integration, and container optimization strategies for the IaC team plugin. This skill is referenced by the `iac-generator` agent when creating container configurations and by `iac-analyzer` when validating existing containerized applications.

## Core Capabilities

### 1. Multi-Stage Build Patterns

Generate optimized Dockerfiles using multi-stage builds:

- **Build stage**: Install dependencies, compile code, run tests
- **Runtime stage**: Minimal base image with only runtime requirements
- **Security stage**: Run vulnerability scanning, linting, SBOM generation

**Benefits**:
- Reduced image size (50-90% smaller)
- Faster deployment times (less data transfer)
- Smaller attack surface (fewer packages, no build tools)
- Improved layer caching (better CI/CD performance)
- Separation of build-time and runtime dependencies

**Multi-arch support** (2026 best practice):
- Build for AMD64 and ARM64 (AWS Graviton) for cost optimization
- Use `docker buildx` with `--platform linux/amd64,linux/arm64`
- Test both architectures in CI pipeline

### 2. Security Hardening

Apply security best practices for production containers:

#### Core Security Practices

- **Non-root users**: Run containers as unprivileged users (UID > 1000)
- **Minimal base images**: Use distroless, alpine, or scratch when possible
- **No secrets in layers**: Never ADD/COPY secrets (use build args with extreme caution)
- **Pinned versions**: Use specific image tags with SHA256 digests for reproducibility
- **Read-only root filesystem**: Use `--read-only` flag where possible
- **Drop capabilities**: Remove unnecessary Linux capabilities with `--cap-drop`

#### Vulnerability Scanning Integration

**Critical 2026 context**: Trivy has replaced tfsec/checkov for container scanning.

**Recommended scanning tools**:
```bash
# Trivy - All-in-one scanner (vulnerabilities + misconfigurations + secrets + licenses)
trivy image --severity CRITICAL,HIGH myimage:tag

# With SBOM generation for compliance
trivy image --format cyclonedx --output sbom.json myimage:tag

# Ignore unfixed CVEs to avoid blocking on vulnerabilities without patches
trivy image --severity CRITICAL,HIGH --ignore-unfixed myimage:tag

# With policy-based exceptions (.trivyignore file)
trivy image --severity CRITICAL,HIGH --trivyignore .trivyignore myimage:tag

# Grype - Alternative scanner with good accuracy
grype myimage:tag --fail-on high

# Docker Scout - Native Docker scanning
docker scout cves myimage:tag --exit-code --only-severity critical,high
```

**CI/CD Integration Best Practices**:

1. **Update vulnerability database before each scan**:
   ```bash
   trivy image --download-db-only
   trivy image --severity CRITICAL,HIGH myimage:tag
   ```

2. **Cache database between pipeline runs** (reduces scan time by 60-80%):
   ```yaml
   # GitHub Actions example
   - uses: actions/cache@v3
     with:
       path: ~/.cache/trivy
       key: trivy-db-${{ github.run_id }}
       restore-keys: trivy-db-
   ```

3. **Severity-based failure thresholds** (avoid alert fatigue):
   - CRITICAL/HIGH: Fail pipeline (blocking)
   - MEDIUM: Warn only (log for review)
   - LOW: Informational only

4. **Document exceptions with expiration dates** (.trivyignore):
   ```
   # CVE-2024-1234: Unfixed vulnerability in base image
   # Reviewed: 2026-02-01, Expires: 2026-03-01
   # Approved by: security-team@example.com
   CVE-2024-1234
   ```

5. **Generate SBOM for compliance and incident response**:
   ```bash
   trivy image --format spdx-json --output sbom-spdx.json myimage:tag
   trivy image --format cyclonedx --output sbom-cyclonedx.json myimage:tag
   ```

6. **Continuous monitoring** of deployed images:
   - Rescan production images on schedule (daily/weekly)
   - Alert on newly disclosed vulnerabilities
   - Track vulnerability trends over time

#### AI-Generated Container Security (2026 Context)

When working with AI-generated Dockerfiles, validate against hallucination risks:

- **Base image verification**: Validate image exists in official registries (Docker Hub, ECR Public, GCR)
- **Package validation**: Check package names against official repository indexes
- **Syntax validation**: Use `hadolint` to catch malformed Dockerfile syntax
- **Schema validation**: Ensure all Dockerfile instructions are valid and properly formatted

**Package hallucination attack prevention**:
```bash
# Validate base image exists before building
docker manifest inspect node:20-alpine || echo "Invalid base image"

# Use only official/verified base images
# ✅ GOOD: node:20-alpine (official)
# ❌ BAD: random-user/node:20-custom (unverified)
```

### 3. Layer Optimization

Optimize for build cache efficiency and image size reduction:

#### Caching Strategies

- **Order dependencies first**: Package manager commands before application code
- **Combine RUN commands**: Reduce layer count with `&&` for related operations
- **Clean package caches**: Remove cache in same RUN command (critical!)
- **.dockerignore**: Exclude unnecessary files from build context (node_modules, .git, tests, docs)
- **Copy selectively**: Copy only required files, not entire directories

**Example pattern**:
```dockerfile
# ✅ GOOD: Dependency layer cached separately
COPY package.json package-lock.json ./
RUN npm ci --only=production && npm cache clean --force

# Application code changes don't invalidate dependency layer
COPY src/ ./src/
COPY public/ ./public/
```

```dockerfile
# ❌ BAD: Dependencies reinstalled on every code change
COPY . .
RUN npm install  # Cache invalidated by any file change
```

#### Size Optimization

- **Multi-stage builds**: Only copy runtime artifacts to final image
- **Minimal base images**: alpine (40-120MB), distroless (60-170MB), scratch (2-10MB)
- **Clean up in same layer**: `apt-get install && rm -rf /var/lib/apt/lists/*`
- **Remove build dependencies**: Only install runtime requirements in final stage
- **Compress artifacts**: Use compression for large static assets

**Size comparison** (typical Node.js app):
- Full image (node:20): ~950MB
- Slim image (node:20-slim): ~230MB
- Alpine image (node:20-alpine): ~120MB
- Distroless image: ~170MB (includes only runtime)

### 4. Base Image Selection

Choose appropriate base images for security, size, and compatibility:

| Use Case | Base Image | Size | Security | Compatibility | Use When |
|----------|------------|------|----------|---------------|----------|
| **Node.js** | `node:20-alpine` | ~120MB | Good | Good | Standard apps, dev environments |
| **Node.js** | `gcr.io/distroless/nodejs20-debian12` | ~170MB | Excellent | Excellent | Production services, high security |
| **Python** | `python:3.12-slim` | ~140MB | Good | Excellent | Standard apps, broad compatibility |
| **Python** | `gcr.io/distroless/python3-debian12` | ~60MB | Excellent | Good | Production services (limited C extensions) |
| **Go** | `golang:1.22-alpine` (build) + `scratch` (runtime) | ~2-10MB | Excellent | Good | Compiled binaries, microservices |
| **Go** | `gcr.io/distroless/static-debian12` (runtime) | ~2MB | Excellent | Excellent | Static binaries with CA certs |
| **Static** | `nginx:alpine` | ~40MB | Good | Excellent | Static sites, SPAs, reverse proxies |
| **Static** | `busybox:uclibc` | ~5MB | Good | Good | Minimal static file serving |

**2026 Recommendations**:
- Prefer distroless for production (no shell, no package manager, minimal CVE surface)
- Use alpine for development (includes shell for debugging)
- Build multi-arch images (AMD64 + ARM64) for AWS Graviton cost savings
- Pin versions with SHA256 digests for reproducibility: `node:20-alpine@sha256:abc123...`

**Multi-arch build example**:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t myimage:latest --push .
```

### 5. Environment-Specific Configuration

Generate Dockerfiles that support multiple environments without hardcoding secrets:

- **Build-time args**: `ARG` for environment selection and non-sensitive config
- **Runtime env vars**: `ENV` for runtime configuration (prefer runtime over build-time)
- **Secrets management**: Never hardcode, reference `.env.example` pattern
- **Health checks**: Include `HEALTHCHECK` for orchestration readiness
- **Metadata labels**: Use `LABEL` for versioning, ownership, CI metadata

**Pattern from SPEC.md constraints**:
```dockerfile
# Use .env.example -> .env.{environment} pattern
# NEVER include actual secrets in image layers

ARG NODE_ENV=production
ENV NODE_ENV=${NODE_ENV}

# Document required environment variables
COPY .env.example .env.example

# At runtime, mount .env.production or provide env vars via orchestration
# Example: docker run --env-file .env.production myimage:latest
# Example: Kubernetes ConfigMap + Secret injection
```

**Health check example**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
```

### 6. Policy-as-Code Validation

Integrate policy enforcement for Dockerfiles using OPA (Open Policy Agent) or Conftest:

**Example OPA policy** (validate Dockerfile compliance):
```rego
# policy/dockerfile.rego
package dockerfile

deny[msg] {
  input[i].Cmd == "from"
  val := input[i].Value
  not contains(val[i], ":")
  msg = "Base image must specify a tag"
}

deny[msg] {
  input[i].Cmd == "user"
  val := input[i].Value
  val[i] == "root"
  msg = "Containers must not run as root"
}
```

**Validation in CI/CD**:
```bash
# Use Conftest to validate Dockerfile against policies
conftest test Dockerfile --policy policy/

# Use Trivy config scanning for Dockerfile misconfigurations
trivy config --severity HIGH,CRITICAL Dockerfile
```

### 7. Resource Optimization and Right-Sizing

Define appropriate resource requests and limits for containers:

**Container resource best practices**:
- Set CPU requests at 40-70% of expected average usage (avoid over-provisioning)
- Set memory requests slightly above average usage (avoid OOM kills)
- Set memory limits 20-30% above requests (allow for spikes)
- Monitor actual usage and adjust quarterly (right-sizing)

**Cost optimization context**:
- ARM-based images (Graviton) offer 20-40% cost savings vs x86
- Right-sized containers reduce cloud spend by up to 32%
- Smaller images reduce storage and transfer costs
- Faster builds reduce CI/CD compute costs

**Example resource definition** (Kubernetes):
```yaml
resources:
  requests:
    cpu: "250m"      # 0.25 CPU cores (40-70% of expected usage)
    memory: "512Mi"  # Slightly above average usage
  limits:
    cpu: "500m"      # 2x requests for bursts
    memory: "768Mi"  # 1.5x requests for spikes
```

## Usage Guidelines

### When to Activate

This skill activates automatically when:

1. User mentions Dockerfile generation or container builds
2. `iac-generator` agent requests container patterns
3. Discussion involves container security, scanning, or validation
4. User asks about base image selection or multi-stage builds
5. CI/CD pipeline integration for container security gates
6. SBOM generation or vulnerability management workflows
7. Dockerfile optimization for size, performance, or cost

### When to Defer

Do NOT activate for:

- **Kubernetes manifests**: Use `kubernetes-native` skill instead
- **CI/CD pipeline configuration**: Use `github-actions-iac` skill for GitHub Actions workflows
- **Runtime orchestration**: Use `kubernetes-native` skill for Deployments, Services, etc.
- **Cloud-specific container services**: Defer to AWS ECS/Fargate or GCP Cloud Run patterns
- **Infrastructure provisioning**: Use `terraform-patterns` skill for Terraform/IaC

### Integration with iac-generator

The `iac-generator` agent references this skill when:

1. Generating Dockerfiles for detected application types
2. Applying security constraints from SPEC.md
3. Optimizing container images for deployment
4. Creating multi-stage builds for efficiency
5. Integrating security scanning in CI/CD workflows
6. Generating policy-as-code validation rules

### Integration with iac-analyzer

The `iac-analyzer` agent references this skill when:

1. Analyzing existing Dockerfiles for optimization opportunities
2. Detecting security vulnerabilities in container configurations
3. Validating Dockerfile compliance with organizational policies
4. Identifying right-sizing opportunities for resource optimization

## Key Patterns

### Pattern 1: Node.js Multi-Stage Build with Security Scanning

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependency definitions first (layer caching)
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy application code
COPY . .

# Build application
RUN npm run build

# Security scanning stage (optional - can also run in CI/CD)
FROM aquasec/trivy:latest AS scanner
COPY --from=builder /app /scan
RUN trivy filesystem --severity CRITICAL,HIGH --exit-code 1 /scan

# Runtime stage (distroless for maximum security)
FROM gcr.io/distroless/nodejs20-debian12
WORKDIR /app

# Copy only production artifacts
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

# Metadata labels for tracking
LABEL org.opencontainers.image.source="https://github.com/myorg/myapp"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.created="2026-02-03T10:00:00Z"

# Run as non-root user (distroless includes nonroot:nonroot)
USER nonroot:nonroot

# Expose port (documentation only in distroless)
EXPOSE 3000

# Health check (requires curl in image or HTTP endpoint check)
# Note: Distroless doesn't include curl, use orchestrator health checks instead

# Start application
CMD ["dist/index.js"]
```

### Pattern 2: Python with Security Scanning and SBOM

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

# Build wheels for faster installation in runtime stage
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Runtime stage
FROM python:3.12-slim
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy wheels and install (no network required)
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Metadata
LABEL org.opencontainers.image.source="https://github.com/myorg/python-app"
LABEL org.opencontainers.image.version="1.0.0"

# Start application
CMD ["python", "app.py"]
```

**CI/CD integration for this image**:
```bash
# Build image
docker build -t myapp:latest .

# Generate SBOM (for compliance and incident response)
trivy image --format cyclonedx --output sbom.json myapp:latest

# Security scan with failure on CRITICAL/HIGH
trivy image --severity CRITICAL,HIGH --exit-code 1 myapp:latest

# Scan for secrets in image layers
trivy image --scanners secret myapp:latest

# Validate Dockerfile against policies
conftest test Dockerfile --policy policy/

# Push to registry only if all checks pass
docker push myapp:latest
```

### Pattern 3: Go Static Binary with Scratch Base

```dockerfile
# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app

# Copy go module definitions first (layer caching)
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build static binary (CGO_ENABLED=0 for fully static linking)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -a \
    -installsuffix cgo \
    -ldflags '-extldflags "-static" -s -w' \
    -o main .

# Runtime stage (scratch = absolutely minimal, ~2MB)
FROM scratch

# Copy CA certificates for HTTPS (required for external API calls)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copy static binary
COPY --from=builder /app/main /main

# Expose port (documentation only)
EXPOSE 8080

# Run as non-root user (UID 65534 = nobody)
USER 65534:65534

# Start application
ENTRYPOINT ["/main"]
```

**Multi-arch build for Go (AMD64 + ARM64)**:
```bash
# Build for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myapp:latest \
  --push \
  .
```

### Pattern 4: Security-Compliant with OIDC Support

```dockerfile
# Example: Container that supports OIDC auth (no long-lived credentials)
FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

COPY . .
RUN npm run build

# Runtime stage
FROM gcr.io/distroless/nodejs20-debian12
WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

# NO hardcoded secrets - expects runtime environment variables
# .env.example documents required vars for reference:
# - OIDC_PROVIDER_URL (e.g., https://accounts.google.com)
# - OIDC_CLIENT_ID (provided at runtime via orchestration)
# - OIDC_AUDIENCE (application identifier)
# - OIDC_REDIRECT_URI (callback URL)

COPY .env.example .env.example

USER nonroot:nonroot
EXPOSE 3000

CMD ["dist/index.js"]
```

**Runtime configuration** (Kubernetes example):
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: oidc-app
spec:
  containers:
  - name: app
    image: myapp:latest
    env:
    - name: OIDC_PROVIDER_URL
      value: "https://accounts.google.com"
    - name: OIDC_CLIENT_ID
      valueFrom:
        secretKeyRef:
          name: oidc-credentials
          key: client-id
    - name: OIDC_AUDIENCE
      value: "my-app-audience"
```

## Security Compliance

All generated Dockerfiles must comply with SPEC.md constraints and industry best practices:

### ✅ Required Security Practices

- **No hardcoded secrets**: Use `.env.example` pattern, mount secrets at runtime via orchestration
- **Non-root user**: Always run as unprivileged user (UID > 1000 or nonroot)
- **Pinned versions**: Use specific tags with SHA256 digests for reproducibility
- **Vulnerability scanning**: Integrate Trivy/Grype in CI/CD with severity-based thresholds
- **SBOM generation**: Generate CycloneDX or SPDX SBOM for compliance and incident response
- **Policy validation**: Use Conftest/OPA to enforce organizational policies
- **OIDC preferred**: Reference OIDC setup in documentation, avoid long-lived credentials
- **Minimal base images**: Use distroless/alpine/scratch to reduce attack surface
- **Read-only filesystem**: Use `--read-only` flag where possible

### ✅ Validation Commands

```bash
# Lint Dockerfile for best practices and common mistakes
hadolint Dockerfile

# Security scan (must pass with no CRITICAL/HIGH findings)
trivy image --severity CRITICAL,HIGH --exit-code 1 <image>

# Scan for hardcoded secrets in image layers
trivy image --scanners secret <image>

# Verify non-root user
docker inspect <image> | jq '.[0].Config.User'

# Validate Dockerfile against custom policies
conftest test Dockerfile --policy policy/

# Check image size (should be < 500MB for most apps)
docker images <image> --format "{{.Size}}"

# Generate SBOM for compliance
trivy image --format cyclonedx --output sbom.json <image>

# Test multi-arch build works correctly
docker buildx imagetools inspect <image>
```

### ✅ CI/CD Integration Example

```yaml
# GitHub Actions example
name: Container Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Lint Dockerfile
      - name: Hadolint
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile

      # Build image
      - name: Build
        run: docker build -t myapp:${{ github.sha }} .

      # Update Trivy DB (critical for accurate results)
      - name: Update Trivy DB
        run: |
          docker run --rm aquasec/trivy:latest image --download-db-only

      # Security scan with severity threshold
      - name: Trivy Scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          severity: 'CRITICAL,HIGH'
          exit-code: 1  # Fail pipeline on findings
          ignore-unfixed: true  # Don't block on unfixed CVEs

      # Generate SBOM
      - name: Generate SBOM
        run: |
          docker run --rm aquasec/trivy:latest image \
            --format cyclonedx \
            --output sbom.json \
            myapp:${{ github.sha }}

      # Policy validation
      - name: Conftest
        run: |
          conftest test Dockerfile --policy policy/

      # Only push if all checks pass
      - name: Push
        if: success()
        run: docker push myapp:${{ github.sha }}
```

## Anti-Patterns to Avoid

### ❌ Common Mistakes

1. **Secrets in layers**:
   ```dockerfile
   # WRONG: Secret visible in layer history (even if deleted later)
   COPY .env .env
   RUN some-command && rm .env  # Secret still in previous layer!
   ```

   **FIX**: Never copy secrets. Use build-time secrets (BuildKit) or runtime env vars:
   ```dockerfile
   # BuildKit secret mount (not persisted in layers)
   RUN --mount=type=secret,id=api_key \
       some-command --key=$(cat /run/secrets/api_key)
   ```

2. **Latest tags**:
   ```dockerfile
   # WRONG: Non-reproducible builds, potential breaking changes
   FROM node:latest
   ```

   **FIX**: Pin specific versions with SHA256 digest:
   ```dockerfile
   FROM node:20-alpine@sha256:abc123def456...
   ```

3. **Running as root**:
   ```dockerfile
   # WRONG: Security risk, violates least privilege principle
   # (no USER specified = runs as root by default)
   FROM node:20-alpine
   COPY . .
   CMD ["node", "app.js"]
   ```

   **FIX**: Always specify non-root user:
   ```dockerfile
   FROM node:20-alpine
   RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser
   USER appuser
   COPY --chown=appuser:appuser . .
   CMD ["node", "app.js"]
   ```

4. **Large image sizes**:
   ```dockerfile
   # WRONG: Full Ubuntu image with unnecessary packages
   FROM ubuntu:22.04
   RUN apt-get update && apt-get install -y python3 python3-pip nodejs npm
   COPY . .
   RUN pip install -r requirements.txt
   ```

   **FIX**: Use minimal base image and multi-stage builds:
   ```dockerfile
   FROM python:3.12-slim AS builder
   RUN pip wheel --wheel-dir /wheels -r requirements.txt

   FROM python:3.12-slim
   COPY --from=builder /wheels /wheels
   RUN pip install --no-cache-dir /wheels/*.whl
   ```

5. **No cache optimization**:
   ```dockerfile
   # WRONG: Code copied before dependencies, invalidates cache on every change
   COPY . .
   RUN npm install  # Runs every time any file changes
   ```

   **FIX**: Copy dependencies first, then code:
   ```dockerfile
   COPY package*.json ./
   RUN npm ci --only=production && npm cache clean --force
   COPY . .  # Code changes don't invalidate dependency layer
   ```

6. **Package cache not cleaned in same layer**:
   ```dockerfile
   # WRONG: Package cache persisted in layer, increases image size
   RUN apt-get update && apt-get install -y curl
   RUN rm -rf /var/lib/apt/lists/*  # Cleanup in separate layer = no size benefit
   ```

   **FIX**: Clean cache in same RUN command:
   ```dockerfile
   RUN apt-get update && \
       apt-get install -y --no-install-recommends curl && \
       rm -rf /var/lib/apt/lists/*
   ```

7. **Ignoring .dockerignore**:
   ```
   # WRONG: No .dockerignore file, copying unnecessary files
   # Result: Slow builds, large build context, potential secret leaks
   ```

   **FIX**: Create .dockerignore to exclude unnecessary files:
   ```
   # .dockerignore
   node_modules
   npm-debug.log
   .git
   .gitignore
   .env
   .env.local
   *.md
   tests/
   .vscode/
   .idea/
   ```

8. **No health checks**:
   ```dockerfile
   # WRONG: No health check, orchestrator can't detect unhealthy containers
   FROM node:20-alpine
   COPY . .
   CMD ["node", "app.js"]
   ```

   **FIX**: Add HEALTHCHECK instruction:
   ```dockerfile
   FROM node:20-alpine
   RUN apk add --no-cache curl
   COPY . .
   HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
     CMD curl -f http://localhost:3000/health || exit 1
   CMD ["node", "app.js"]
   ```

9. **Outdated scanning tools** (2026 context):
   ```bash
   # WRONG: Using deprecated tfsec for container scanning
   tfsec Dockerfile
   ```

   **FIX**: Use Trivy (tfsec replacement) for comprehensive scanning:
   ```bash
   trivy config --severity CRITICAL,HIGH Dockerfile
   trivy image --severity CRITICAL,HIGH myimage:tag
   ```

10. **No SBOM generation**:
    ```bash
    # WRONG: No software bill of materials, hard to track vulnerabilities
    docker build -t myimage .
    docker push myimage
    ```

    **FIX**: Generate SBOM for compliance and incident response:
    ```bash
    docker build -t myimage .
    trivy image --format cyclonedx --output sbom.json myimage
    trivy image --severity CRITICAL,HIGH --exit-code 1 myimage
    docker push myimage
    ```

## Integration Notes

### For iac-generator Agent

When the `iac-generator` agent invokes this skill:

1. **Context**: Provide detected language/framework (Node.js, Python, Go, etc.)
2. **Constraints**: Reference SPEC.md security requirements (no hardcoded secrets, OIDC preferred)
3. **Environment**: Specify target environment (dev/staging/production)
4. **Optimization**: Request size vs. security vs. speed priority
5. **Architecture**: Specify target platforms (AMD64, ARM64, or both for multi-arch)
6. **CI/CD**: Indicate if CI/CD security integration is required

### For iac-analyzer Agent

When `iac-analyzer` detects containers:

1. Pass application type detection to inform Dockerfile generation
2. Identify existing Dockerfiles for optimization analysis
3. Map dependencies for multi-stage build planning
4. Detect security vulnerabilities and recommend fixes
5. Identify right-sizing opportunities based on resource usage patterns

## Best Practices Summary

1. **Always use multi-stage builds** for compiled languages and large dependency trees
2. **Choose minimal base images** appropriate for your runtime needs (distroless > alpine > slim)
3. **Pin versions with SHA256 digests** for production images (reproducibility)
4. **Optimize layer caching** by ordering commands from least to most frequently changing
5. **Run as non-root user** for security (UID > 1000 or nonroot)
6. **Include health checks** for orchestration compatibility
7. **Integrate security scanning** in CI/CD with severity-based thresholds (fail on CRITICAL/HIGH)
8. **Generate SBOM** for compliance and incident response (CycloneDX or SPDX)
9. **Never hardcode secrets** - use runtime environment variables with `.env` pattern
10. **Validate with linting** using hadolint before committing
11. **Update vulnerability databases** before each scan to minimize false positives
12. **Document exceptions** in .trivyignore with expiration dates and approval info
13. **Use policy-as-code** (Conftest/OPA) to enforce organizational standards
14. **Build multi-arch images** (AMD64 + ARM64) for cost optimization on AWS Graviton
15. **Right-size resource requests** based on actual usage (40-70% CPU utilization target)

## References

For comprehensive patterns and advanced techniques, see:

- **Official Docker best practices**: https://docs.docker.com/develop/dev-best-practices/
- **Distroless images**: https://github.com/GoogleContainerTools/distroless
- **Hadolint (Dockerfile linter)**: https://github.com/hadolint/hadolint
- **Trivy (security scanner)**: https://trivy.dev/
- **Grype (alternative scanner)**: https://github.com/anchore/grype
- **Conftest (policy-as-code)**: https://www.conftest.dev/
- **SBOM standards**: https://cyclonedx.org/ and https://spdx.dev/
- **Multi-arch builds**: https://docs.docker.com/build/building/multi-platform/
- **BuildKit secrets**: https://docs.docker.com/build/building/secrets/

---

*This skill is part of the iac-team plugin. For related capabilities, see: kubernetes-native (orchestration), github-actions-iac (CI/CD), terraform-patterns (infrastructure provisioning), security-scanning (vulnerability management).*
