---
title: Deployment Operations
description: CI/CD pipelines, containerization, zero-downtime deployments, and infrastructure automation
tags: [skill, deployment, devops, ci-cd, docker, kubernetes, automation]
type: skill
version: "1.0.0"
category: operations
---

# Deployment Operations

## Overview

This skill provides comprehensive deployment and operations practices including CI/CD pipeline setup, containerization with Docker, zero-downtime deployments, monitoring, and rollback strategies. Use this skill to automate deployments, ensure reliability, and minimize downtime.

**When to use this skill:**
- Setting up CI/CD pipelines
- Containerizing applications with Docker
- Implementing zero-downtime deployments
- Configuring monitoring and alerting
- Planning rollback strategies
- Managing infrastructure as code

## Key Concepts

### CI/CD Pipeline Stages

```
┌─────────┐   ┌──────┐   ┌──────┐   ┌────────┐   ┌────────┐   ┌──────────┐
│ Commit  │ → │ Build│ → │ Test │ → │ Deploy │ → │Monitor │ → │Rollback? │
│  Code   │   │      │   │      │   │Staging │   │        │   │          │
└─────────┘   └──────┘   └──────┘   └────────┘   └────────┘   └──────────┘
                                          ↓
                                     ┌────────┐
                                     │ Deploy │
                                     │  Prod  │
                                     └────────┘
```

**Pipeline Steps:**
1. **Build**: Compile code, create artifacts
2. **Test**: Run unit, integration, E2E tests
3. **Security Scan**: Check for vulnerabilities
4. **Deploy to Staging**: Test in production-like environment
5. **Deploy to Production**: Release to users
6. **Monitor**: Track metrics and errors
7. **Rollback**: Revert if issues detected

### Deployment Strategies

**1. Blue-Green Deployment:**
```
Blue (old version)     Green (new version)
     ↓                      ↓
[Load Balancer] ────→ [Blue Environment]
                      [Green Environment]

After testing Green:
[Load Balancer] ────→ [Green Environment]
                      [Blue Environment] (kept as rollback)
```

**2. Canary Deployment:**
```
              5% traffic → [Canary (v2.0)]
[Load Balancer]
              95% traffic → [Stable (v1.0)]

If canary successful:
              100% traffic → [v2.0]
```

**3. Rolling Deployment:**
```
Server 1: v1.0 → v2.0
Server 2: v1.0 → v2.0
Server 3: v1.0 → v2.0
(one at a time)
```

## Implementation

### GitHub Actions CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ========================================
  # BUILD & TEST
  # ========================================
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run linter
        run: npm run lint

      - name: Run type check
        run: npm run typecheck

      - name: Run unit tests
        run: npm run test:unit

      - name: Run integration tests
        run: npm run test:integration

      - name: Generate coverage report
        run: npm run test:coverage

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json

  # ========================================
  # SECURITY SCAN
  # ========================================
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: auto

      - name: Dependency security audit
        run: npm audit --audit-level=moderate

      - name: Check for secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: main

  # ========================================
  # BUILD DOCKER IMAGE
  # ========================================
  build-image:
    needs: [build-and-test, security-scan]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=sha

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache,mode=max

  # ========================================
  # DEPLOY TO STAGING
  # ========================================
  deploy-staging:
    needs: build-image
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.example.com

    steps:
      - name: Deploy to staging
        run: |
          echo "Deploying to staging..."
          # kubectl apply -f k8s/staging/
          # or helm upgrade --install app ./helm-chart

      - name: Run smoke tests
        run: |
          curl -f https://staging.example.com/health || exit 1

  # ========================================
  # DEPLOY TO PRODUCTION
  # ========================================
  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://example.com

    steps:
      - name: Deploy to production
        run: |
          echo "Deploying to production..."
          # Blue-green deployment or canary

      - name: Health check
        run: |
          curl -f https://example.com/health || exit 1

      - name: Notify Slack
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Deployment to production completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Docker Configuration

```dockerfile
# Dockerfile - Multi-stage build for optimization
# ========================================
# Stage 1: Build
# ========================================
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && \
    npm cache clean --force

# Copy source code
COPY . .

# Build application
RUN npm run build

# ========================================
# Stage 2: Production
# ========================================
FROM node:18-alpine AS production

# Security: Run as non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

WORKDIR /app

# Copy built artifacts from builder
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package*.json ./

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD node healthcheck.js

# Start application
CMD ["node", "dist/index.js"]
```

```yaml
# docker-compose.yml - Local development and staging
version: '3.8'

services:
  # Application
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  labels:
    app: myapp
    version: v1.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Zero-downtime deployment
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
        version: v1.0.0
    spec:
      containers:
      - name: app
        image: ghcr.io/myorg/myapp:v1.0.0
        ports:
        - containerPort: 3000
          name: http
        env:
        - name: NODE_ENV
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: myapp-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  type: LoadBalancer
  selector:
    app: myapp
  ports:
  - protocol: TCP
    port: 80
    targetPort: 3000
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Zero-Downtime Deployment Script

```bash
#!/bin/bash
# deploy.sh - Zero-downtime deployment script

set -e

APP_NAME="myapp"
NEW_VERSION=$1
HEALTHCHECK_URL="https://example.com/health"
ROLLBACK_VERSION=$(kubectl get deployment $APP_NAME -o jsonpath='{.spec.template.spec.containers[0].image}')

echo "🚀 Starting deployment of ${APP_NAME}:${NEW_VERSION}"
echo "📦 Current version: ${ROLLBACK_VERSION}"

# Step 1: Update deployment
echo "📝 Updating deployment..."
kubectl set image deployment/$APP_NAME \
  app=ghcr.io/myorg/$APP_NAME:$NEW_VERSION \
  --record

# Step 2: Wait for rollout
echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/$APP_NAME --timeout=5m

# Step 3: Health check
echo "🏥 Running health checks..."
for i in {1..10}; do
  if curl -f -s $HEALTHCHECK_URL > /dev/null; then
    echo "✅ Health check passed"
    break
  fi

  if [ $i -eq 10 ]; then
    echo "❌ Health check failed after 10 attempts"
    echo "🔄 Rolling back to previous version..."
    kubectl rollout undo deployment/$APP_NAME
    exit 1
  fi

  echo "⏳ Attempt $i/10 failed, retrying in 5s..."
  sleep 5
done

# Step 4: Monitor metrics
echo "📊 Monitoring error rates..."
sleep 30  # Wait for metrics to accumulate

ERROR_RATE=$(curl -s "https://monitoring.example.com/api/error-rate")
if [ $(echo "$ERROR_RATE > 5.0" | bc) -eq 1 ]; then
  echo "❌ Error rate too high: ${ERROR_RATE}%"
  echo "🔄 Rolling back..."
  kubectl rollout undo deployment/$APP_NAME
  exit 1
fi

echo "✅ Deployment successful!"
echo "🎉 ${APP_NAME}:${NEW_VERSION} is now live"

# Step 5: Clean up old resources
echo "🧹 Cleaning up old replicasets..."
kubectl delete replicaset -l app=$APP_NAME --field-selector=status.replicas=0
```

### Health Checks

```python
# FastAPI health check endpoints
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import psycopg2

app = FastAPI()

@app.get("/health")
async def health_check():
    """Liveness probe - is service running?"""
    return {"status": "healthy"}

@app.get("/ready")
async def readiness_check():
    """Readiness probe - can service handle requests?"""
    checks = {
        "database": check_database(),
        "redis": check_redis(),
        "dependencies": check_external_services()
    }

    all_healthy = all(checks.values())

    return JSONResponse(
        content={"status": "ready" if all_healthy else "not ready", "checks": checks},
        status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

def check_database() -> bool:
    """Check database connectivity."""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        conn.close()
        return True
    except:
        return False

def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        return redis_client.ping()
    except:
        return False
```

## Best Practices

### CI/CD Pipeline

**Do:**
- ✅ Run tests before deployment
- ✅ Use caching to speed up builds
- ✅ Implement security scanning
- ✅ Version all Docker images with git SHA
- ✅ Use separate environments (dev, staging, prod)
- ✅ Require manual approval for production
- ✅ Send deployment notifications
- ✅ Tag releases in git

**Don't:**
- ❌ Deploy without tests passing
- ❌ Use `latest` tag for production
- ❌ Store secrets in code (use secret management)
- ❌ Deploy directly to production
- ❌ Skip staging environment

### Container Best Practices

**Do:**
- ✅ Use multi-stage builds
- ✅ Run as non-root user
- ✅ Minimize image size
- ✅ Use specific base image versions
- ✅ Implement health checks
- ✅ Scan images for vulnerabilities
- ✅ Use .dockerignore

**Don't:**
- ❌ Include unnecessary files in image
- ❌ Run as root user
- ❌ Use `latest` tag
- ❌ Store secrets in images
- ❌ Ignore security scans

### Rollback Strategy

**Preparation:**
1. Keep previous version deployed (blue-green)
2. Tag all releases in git
3. Version Docker images
4. Test rollback procedure regularly
5. Document rollback steps

**When to Rollback:**
- High error rates (>5%)
- Performance degradation (>20% slower)
- Critical bugs discovered
- Failed health checks
- User-reported issues spike

## Monitoring and Alerting

```yaml
# prometheus/alerts.yml
groups:
  - name: application
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # High response time
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile response time > 1s"

      # Low availability
      - alert: ServiceDown
        expr: up{job="myapp"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
```

## Related Skills & Conventions

- [Docker Compose Stack Template](../templates/docker-compose-stack.md) - Docker configuration
- [GitHub Actions CI Template](../templates/github-actions-ci.md) - CI/CD setup
- [Testing Strategies](./testing-strategies.md) - Automated testing in CI/CD
- [Performance Optimization](./performance-optimization.md) - Production performance

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
