# Multi-Environment Flux Setup

This example demonstrates how to manage multiple environments (staging, production) with Flux CD using overlays.

## Repository Structure

```
flux-repo/
├── clusters/
│   ├── staging/
│   │   ├── flux-system/
│   │   ├── infrastructure.yaml
│   │   └── apps.yaml
│   └── production/
│       ├── flux-system/
│       ├── infrastructure.yaml
│       └── apps.yaml
├── infrastructure/
│   ├── base/
│   │   ├── nginx-ingress/
│   │   └── cert-manager/
│   ├── staging/
│   │   └── kustomization.yaml
│   └── production/
│       └── kustomization.yaml
└── apps/
    ├── base/
    │   └── web-app/
    │       ├── deployment.yaml
    │       ├── service.yaml
    │       ├── ingress.yaml
    │       └── kustomization.yaml
    ├── staging/
    │   └── web-app/
    │       ├── kustomization.yaml
    │       └── patches.yaml
    └── production/
        └── web-app/
            ├── kustomization.yaml
            └── patches.yaml
```

## Base Application

**File**: `apps/base/web-app/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: web-app
spec:
  replicas: 1  # Override in environments
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
      - name: web-app
        image: ghcr.io/org/web-app:latest  # Override in environments
        ports:
        - containerPort: 8080
        env:
        - name: ENVIRONMENT
          value: "base"  # Override in environments
        - name: LOG_LEVEL
          value: "info"  # Override in environments
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
```

**File**: `apps/base/web-app/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: web-app
resources:
  - deployment.yaml
  - service.yaml
  - ingress.yaml
```

## Staging Overlay

**File**: `apps/staging/web-app/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: web-app
resources:
  - ../../base/web-app
patches:
  - path: patches.yaml
images:
  - name: ghcr.io/org/web-app
    newTag: staging-latest
```

**File**: `apps/staging/web-app/patches.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: web-app
        env:
        - name: ENVIRONMENT
          value: "staging"
        - name: LOG_LEVEL
          value: "debug"
        - name: API_URL
          value: "https://api.staging.example.com"
```

## Production Overlay

**File**: `apps/production/web-app/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: web-app
resources:
  - ../../base/web-app
patches:
  - path: patches.yaml
images:
  - name: ghcr.io/org/web-app
    newTag: v1.2.3  # Pinned version for production
replicas:
  - name: web-app
    count: 5
```

**File**: `apps/production/web-app/patches.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  template:
    spec:
      containers:
      - name: web-app
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: LOG_LEVEL
          value: "warn"
        - name: API_URL
          value: "https://api.example.com"
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-app
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-app
            port:
              number: 80
  tls:
  - hosts:
    - app.example.com
    secretName: web-app-tls
```

## Staging Cluster Configuration

**File**: `clusters/staging/apps.yaml`

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 5m
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/staging
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTER_NAME: "staging"
      DOMAIN: "staging.example.com"
```

## Production Cluster Configuration

**File**: `clusters/production/apps.yaml`

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  dependsOn:
    - name: infrastructure
  interval: 10m
  retryInterval: 2m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/production
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTER_NAME: "production"
      DOMAIN: "example.com"
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: web-app
      namespace: web-app
```

## Promotion Workflow

### 1. Deploy to Staging

```bash
# Update staging image tag
cd apps/staging/web-app
kustomize edit set image ghcr.io/org/web-app:staging-abc123

git add kustomization.yaml
git commit -m "Deploy staging-abc123 to staging"
git push
```

### 2. Verify Staging

```bash
# Check deployment status
flux get kustomization apps --context=staging-cluster

# Run tests against staging
curl https://app.staging.example.com/health

# Monitor for issues
flux logs --context=staging-cluster --follow
```

### 3. Promote to Production

```bash
# Update production with tested version
cd apps/production/web-app
kustomize edit set image ghcr.io/org/web-app:v1.2.3

git add kustomization.yaml
git commit -m "Promote v1.2.3 to production"
git push
```

### 4. Monitor Production

```bash
# Watch deployment progress
flux get kustomization apps --context=production-cluster --watch

# Verify health checks pass
kubectl get deployment web-app -n web-app --context=production-cluster

# Check application metrics
curl https://app.example.com/health
```

## Environment-Specific Variables

Use ConfigMaps for environment-specific configuration:

**File**: `clusters/staging/config.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-config
  namespace: flux-system
data:
  CLUSTER_NAME: "staging"
  ENVIRONMENT: "staging"
  REPLICAS: "2"
  LOG_LEVEL: "debug"
  DOMAIN: "staging.example.com"
```

Reference in Kustomization:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  postBuild:
    substituteFrom:
      - kind: ConfigMap
        name: cluster-config
```

## Best Practices

1. **Pin versions in production**: Use specific tags, not `latest`
2. **Test in staging first**: Always deploy to staging before production
3. **Use health checks**: Ensure deployments succeed before marking complete
4. **Implement dependencies**: Deploy infrastructure before applications
5. **Monitor reconciliation**: Set up alerts for failed deployments
6. **Use Git tags**: Tag production releases in Git for rollback capability
7. **Separate repos or branches**: Consider separate repos per environment for larger teams
