# Basic Flux Setup Example

This example demonstrates a minimal Flux CD setup for a single application.

## Directory Structure

```
flux-repo/
├── clusters/
│   └── production/
│       ├── flux-system/
│       │   ├── gotk-components.yaml
│       │   ├── gotk-sync.yaml
│       │   └── kustomization.yaml
│       └── apps.yaml
├── infrastructure/
│   └── sources/
│       ├── app-repo.yaml
│       └── kustomization.yaml
└── apps/
    └── my-app/
        ├── helmrelease.yaml
        ├── namespace.yaml
        └── kustomization.yaml
```

## Step 1: Bootstrap Flux

```bash
# Install Flux CLI
curl -s https://fluxcd.io/install.sh | sudo bash

# Bootstrap Flux to cluster
flux bootstrap github \
  --owner=my-org \
  --repository=flux-repo \
  --branch=main \
  --path=clusters/production \
  --personal
```

## Step 2: Create GitRepository Source

**File**: `infrastructure/sources/app-repo.yaml`

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: my-app-repo
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/my-org/my-app
  ref:
    branch: main
  secretRef:
    name: github-token
```

**File**: `infrastructure/sources/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - app-repo.yaml
```

## Step 3: Create Application Namespace

**File**: `apps/my-app/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
  labels:
    app: my-app
```

## Step 4: Create HelmRelease

**File**: `apps/my-app/helmrelease.yaml`

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: my-app
  namespace: my-app
spec:
  interval: 30m
  chart:
    spec:
      chart: ./charts/my-app
      sourceRef:
        kind: GitRepository
        name: my-app-repo
        namespace: flux-system
      interval: 5m
  values:
    replicaCount: 2
    image:
      repository: ghcr.io/my-org/my-app
      tag: v1.0.0
    service:
      type: ClusterIP
      port: 80
    ingress:
      enabled: true
      className: nginx
      hosts:
        - host: my-app.example.com
          paths:
            - path: /
              pathType: Prefix
  install:
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
```

**File**: `apps/my-app/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - helmrelease.yaml
```

## Step 5: Create Cluster Kustomization

**File**: `clusters/production/apps.yaml`

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps
  prune: true
  wait: true
  timeout: 5m
```

## Step 6: Commit and Push

```bash
git add .
git commit -m "Add my-app Flux configuration"
git push origin main
```

## Step 7: Verify Deployment

```bash
# Check Flux reconciliation
flux get all

# Check HelmRelease status
flux get helmrelease -n my-app

# Check application pods
kubectl get pods -n my-app

# View Flux logs
flux logs --level=info --all-namespaces
```

## Expected Output

```
NAME            READY   MESSAGE
my-app          True    Release reconciliation succeeded

NAME                          READY   STATUS    RESTARTS   AGE
my-app-7d8f4b5c9d-abcde      1/1     Running   0          2m
my-app-7d8f4b5c9d-fghij      1/1     Running   0          2m
```

## Next Steps

1. Add more applications to `apps/` directory
2. Configure image automation for automatic updates
3. Add notifications for deployment status
4. Set up multi-environment overlays (staging, production)
5. Implement SOPS for secret management
