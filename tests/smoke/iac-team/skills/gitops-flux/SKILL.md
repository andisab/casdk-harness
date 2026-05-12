---
name: gitops-flux
description: >
  GitOps patterns and best practices for Flux CD continuous delivery.
  Provides Flux manifests, HelmRelease configurations, Kustomization patterns,
  multi-environment deployment strategies, security hardening, and cost optimization.

  Activate when user mentions: Flux, FluxCD, GitOps, HelmRelease, Kustomization,
  image automation, git reconciliation, continuous delivery, helm controller,
  source controller, notification controller, flux bootstrap, Gateway API with Flux.

  Use for: Generating Flux resources, multi-tenant patterns, progressive delivery,
  dependency ordering, health checks, post-build variable substitution, OIDC authentication,
  security scanning integration, cost-optimized workload management.

  Do NOT use for: Standalone Kubernetes manifests (use kubernetes-native skill),
  Argo CD patterns, Jenkins pipelines, or non-GitOps deployment strategies.
---

# GitOps Flux Skill

## Purpose

Provides Flux CD patterns for GitOps-based continuous delivery to Kubernetes clusters. Covers Flux resource definitions, repository structures, multi-environment configurations, security best practices, validation pipelines, and cost optimization strategies for cloud-native deployments.

## Capabilities

- **Flux Bootstrapping**: Initialize Flux in clusters with proper RBAC
- **GitRepository Sources**: Configure Git sources with OIDC/SSH keys, branch tracking, secrets
- **HelmRepository Sources**: Configure Helm chart repositories (public, private, OCI)
- **Kustomization Resources**: Define reconciliation targets with health checks, dependencies
- **HelmRelease Resources**: Deploy Helm charts with values, health checks, rollback policies
- **Image Automation**: Configure image update automation with policies and scanning
- **Multi-Tenancy**: Namespace isolation, RBAC, policy enforcement per tenant
- **Progressive Delivery**: Canary deployments, blue-green strategies using Flagger integration
- **Dependency Ordering**: Use `dependsOn` to sequence deployments correctly
- **Secret Management**: SOPS encryption, sealed secrets, external-secrets integration
- **Notification System**: Configure alerts to Slack, Teams, Git providers
- **Multi-Environment**: Structure repos for dev/staging/prod with overlays
- **OIDC Authentication**: Secure Git provider access without long-lived credentials
- **Security Scanning**: Integrate Trivy/Checkov validation in Flux CI/CD workflows
- **Gateway API Integration**: Manage Gateway API resources via Flux GitOps
- **Cost Optimization**: Spot instance strategies for Flux-managed workloads

## Activation

This skill activates automatically when users reference:

- Flux components: `flux bootstrap`, `fluxctl`, GitRepository, HelmRelease, Kustomization
- GitOps concepts: git reconciliation, continuous delivery, declarative deployment
- Flux features: image automation, notification controller, source controller
- Multi-environment patterns: overlay structure, environment promotion
- Security: OIDC, SOPS, secret management, vulnerability scanning
- Cost optimization: Spot instances, right-sizing, resource efficiency
- Gateway API: HTTPRoute, BackendTLSPolicy, Gateway resources managed by Flux

## Core Patterns

### 1. Flux Directory Structure

```
clusters/
  production/
    flux-system/          # Flux controllers
    infrastructure/       # Core services (Gateway, Ingress, Cert-Manager)
    apps/                 # Application deployments
  staging/
    flux-system/
    infrastructure/
    apps/

infrastructure/
  sources/                # GitRepository, HelmRepository
  controllers/            # External controllers (Nginx, Cert-Manager, Gateway API)
  configs/                # ConfigMaps, Secrets
  policies/               # OPA/Rego policies for validation

apps/
  base/                   # Base Kustomizations
  production/             # Production overlays
  staging/                # Staging overlays
```

### 2. GitRepository Source with OIDC Authentication

**PREFERRED: OIDC (Replaces Long-Lived Credentials)**

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: app-repo
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/org/app-repo
  ref:
    branch: main
  # Use GitHub App or OIDC token (no long-lived credentials)
  # Configure GitHub/GitLab OIDC provider with restrictive trust policy
  secretRef:
    name: git-oidc-credentials  # Contains short-lived OIDC token
  verify:
    mode: strict
  ignore: |
    # Exclude non-deployment files
    .github/
    docs/
    *.md
```

**ALTERNATIVE: SSH Key (Less Secure - Short TTL Recommended)**

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: app-repo
  namespace: flux-system
spec:
  interval: 1m
  url: ssh://git@github.com/org/app-repo
  ref:
    branch: main
  secretRef:
    name: git-ssh-credentials  # SSH key with read-only permissions
  ignore: |
    .github/
    docs/
```

### 3. HelmRepository Source

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: bitnami
  namespace: flux-system
spec:
  interval: 10m
  url: https://charts.bitnami.com/bitnami
  timeout: 60s
---
# Private Helm repository with authentication
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: private-charts
  namespace: flux-system
spec:
  interval: 10m
  url: https://charts.example.com
  secretRef:
    name: helm-repo-credentials
```

### 4. Kustomization Resource with Validation

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./infrastructure/production
  prune: true
  wait: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx-ingress-controller
      namespace: ingress-nginx
  postBuild:
    substitute:
      CLUSTER_NAME: "production"
      REGION: "us-west-2"
    substituteFrom:
      - kind: ConfigMap
        name: cluster-vars
  # Validate manifests before applying
  validation: server
```

### 5. HelmRelease Resource with Cost Optimization

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: nginx-ingress
  namespace: infrastructure
spec:
  interval: 30m
  timeout: 10m
  chart:
    spec:
      chart: nginx-ingress-controller
      version: '9.x'
      sourceRef:
        kind: HelmRepository
        name: bitnami
        namespace: flux-system
      interval: 12h
  values:
    replicaCount: 3
    service:
      type: LoadBalancer
    resources:
      limits:
        cpu: 200m
        memory: 256Mi
      requests:
        cpu: 100m
        memory: 128Mi
    # Cost optimization: Use Spot instances for non-critical workloads
    nodeSelector:
      workload-type: spot-optimized
    tolerations:
      - key: "spot"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
  install:
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
      remediateLastFailure: true
    cleanupOnFail: true
  rollback:
    timeout: 10m
    cleanupOnFail: true
  test:
    enable: true
```

### 6. Dependency Ordering

```yaml
# Deploy infrastructure first
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./infrastructure/production
  prune: true
  wait: true
---
# Then deploy applications (depends on infrastructure)
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  dependsOn:
    - name: infrastructure
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/production
  prune: true
  wait: true
```

### 7. Image Automation

```yaml
# Image repository scanning
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImageRepository
metadata:
  name: app-image
  namespace: flux-system
spec:
  image: ghcr.io/org/app
  interval: 5m
  secretRef:
    name: ghcr-credentials
---
# Image update policy with semantic versioning
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImagePolicy
metadata:
  name: app-policy
  namespace: flux-system
spec:
  imageRepositoryRef:
    name: app-image
  policy:
    semver:
      range: '>=1.0.0 <2.0.0'
---
# Image update automation
apiVersion: image.toolkit.fluxcd.io/v1beta1
kind: ImageUpdateAutomation
metadata:
  name: app-update
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  git:
    checkout:
      ref:
        branch: main
    commit:
      author:
        email: fluxcdbot@example.com
        name: FluxCD Bot
      messageTemplate: 'chore: update {{range .Updated.Images}}{{println .}}{{end}}'
    push:
      branch: main
  update:
    path: ./apps/production
    strategy: Setters
```

### 8. Multi-Tenant Pattern

```yaml
# Tenant namespace
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-alpha
  labels:
    toolkit.fluxcd.io/tenant: alpha
---
# Tenant service account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: flux-tenant-alpha
  namespace: tenant-alpha
---
# Tenant RBAC (namespace-scoped)
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: flux-tenant-alpha
  namespace: tenant-alpha
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: flux-tenant-alpha
    namespace: tenant-alpha
---
# Tenant Kustomization
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tenant-alpha
  namespace: tenant-alpha
spec:
  serviceAccountName: flux-tenant-alpha
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: tenant-alpha-repo
    namespace: tenant-alpha
  path: ./deploy
  prune: true
  wait: true
```

### 9. Secret Management with SOPS

```yaml
# Create encrypted secret file (run manually)
# sops --encrypt --age <public-key> secret.yaml > secret.enc.yaml

# Kustomization with decryption
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/production
  prune: true
  decryption:
    provider: sops
    secretRef:
      name: sops-age  # Age private key
```

### 10. Notification Configuration

```yaml
# Notification provider (Slack)
apiVersion: notification.toolkit.fluxcd.io/v1beta2
kind: Provider
metadata:
  name: slack
  namespace: flux-system
spec:
  type: slack
  channel: deployments
  secretRef:
    name: slack-webhook
---
# Alert for failures
apiVersion: notification.toolkit.fluxcd.io/v1beta2
kind: Alert
metadata:
  name: infrastructure-alert
  namespace: flux-system
spec:
  providerRef:
    name: slack
  eventSeverity: error
  eventSources:
    - kind: Kustomization
      name: infrastructure
    - kind: HelmRelease
      name: '*'
      namespace: infrastructure
  suspend: false
```

### 11. Gateway API Integration

```yaml
# Flux manages Gateway API resources
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: gateway-api
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./infrastructure/gateway-api
  prune: true
  wait: true
  healthChecks:
    - apiVersion: gateway.networking.k8s.io/v1
      kind: Gateway
      name: production-gateway
      namespace: gateway-system
---
# Gateway resource managed by Flux
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: production-gateway
  namespace: gateway-system
spec:
  gatewayClassName: envoy-gateway
  listeners:
    - name: http
      protocol: HTTP
      port: 80
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-cert
---
# HTTPRoute managed by Flux
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: apps
spec:
  parentRefs:
    - name: production-gateway
      namespace: gateway-system
  hostnames:
    - "app.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: app-service
          port: 80
```

## Security Best Practices

### OIDC Authentication (Preferred)

Use OIDC for Git provider authentication instead of long-lived SSH keys or tokens:

**GitHub Actions OIDC Integration:**

```yaml
# GitHub Actions workflow using OIDC
name: Update Flux Repository
on:
  push:
    branches: [main]

permissions:
  id-token: write  # Required for OIDC token request
  contents: read

jobs:
  flux-update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure Git with OIDC
        run: |
          # Use GitHub OIDC token for Git operations
          # Configure trust policy on GitRepository resource
          echo "OIDC token configured"

      - name: Trigger Flux Reconciliation
        run: |
          # Flux detects Git changes via webhook or polling
          flux reconcile source git app-repo
```

**AWS IAM OIDC Trust Policy for GitRepository:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:sub": "repo:org/app-repo:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### Multi-Phase Validation Pipeline

Implement rigorous validation before deploying Flux resources:

**Phase 1: Technical Validation (Syntax & Structure)**

```bash
# Validate Kubernetes manifests syntax
kubectl apply --dry-run=client -f resource.yaml

# Validate Kustomizations
kubectl kustomize ./path/to/kustomization --enable-helm

# Validate HelmReleases
flux diff helmrelease <name> --path ./path/to/release.yaml

# Check Flux compatibility
flux check

# Validate YAML structure
yamllint -c .yamllint.yml manifests/
```

**Phase 2: Intent Validation (Policy & Security)**

```bash
# Validate with OPA/Rego policies (organizational requirements)
conftest test manifests/ -p policies/

# Security scanning with Trivy (IaC misconfigurations)
trivy config --severity CRITICAL,HIGH manifests/

# Security scanning with Checkov (compliance frameworks)
checkov --directory manifests/ --framework kubernetes --check CIS_KUBERNETES

# Validate against custom policies
kyverno apply policies/ --resource manifests/
```

**CI/CD Integration Example:**

```yaml
# .github/workflows/flux-validation.yml
name: Flux Validation Pipeline
on: [pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Update Vulnerability Database
        run: trivy image --download-db-only

      - name: Technical Validation
        run: |
          kubectl apply --dry-run=client -f clusters/production/
          kubectl kustomize clusters/production/apps --enable-helm

      - name: Security Scanning
        run: |
          trivy config --severity CRITICAL,HIGH \
            --ignore-unfixed \
            --exit-code 1 \
            clusters/production/

      - name: Policy Validation
        run: |
          conftest test clusters/production/ \
            -p policies/ \
            --fail-on-warn
```

### Secret Encryption Requirements

- **Never commit plaintext secrets** to Git repositories
- Use SOPS with Age or AWS KMS for encryption at rest
- Alternative: Use External Secrets Operator to fetch from vault
- Pattern: `.env.example` → `.env.local` (gitignored) → encrypted `.env.production`

**SOPS Encryption Workflow:**

```bash
# Generate Age key pair
age-keygen -o age.key

# Extract public key
PUBLIC_KEY=$(age-keygen -y age.key)

# Encrypt secret
sops --encrypt --age $PUBLIC_KEY secret.yaml > secret.enc.yaml

# Store Age private key in Kubernetes Secret
kubectl create secret generic sops-age \
  --from-file=age.agekey=age.key \
  --namespace=flux-system

# Flux will decrypt automatically using Kustomization decryption config
```

### Hallucination Detection for Generated Manifests

When using AI to generate Flux resources:

1. **Validate Resource Types**: Ensure all `apiVersion` and `kind` combinations exist in cluster
2. **Schema Validation**: Use `kubectl explain` to verify field names and types
3. **Verify Dependencies**: Check that referenced resources (ConfigMaps, Secrets, ServiceAccounts) exist
4. **Test in Non-Prod**: Always apply generated manifests to staging before production
5. **Human Review Required**: Never auto-deploy AI-generated configurations without approval gate

```bash
# Validate generated Flux resource against cluster API
kubectl explain GitRepository.spec
kubectl explain HelmRelease.spec.chart.spec

# Verify referenced resources exist
kubectl get secret git-credentials -n flux-system
kubectl get configmap cluster-vars -n flux-system

# Dry-run to detect invalid configurations
flux diff kustomization apps --path ./generated/apps.yaml
```

## Multi-Environment Strategy

### Overlay Pattern

```
apps/
  base/
    app/
      deployment.yaml
      service.yaml
      kustomization.yaml
  staging/
    app/
      kustomization.yaml       # Overlays base
      patches.yaml             # Staging-specific patches
  production/
    app/
      kustomization.yaml       # Overlays base
      patches.yaml             # Production-specific patches
```

### Environment-Specific Kustomizations

```yaml
# clusters/production/apps.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/production
  prune: true
  postBuild:
    substitute:
      ENVIRONMENT: "production"
      REPLICAS: "3"
      LOG_LEVEL: "warn"
      NODE_SELECTOR: "workload-type=on-demand"  # Production uses On-Demand
---
# clusters/staging/apps.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/staging
  prune: true
  postBuild:
    substitute:
      ENVIRONMENT: "staging"
      REPLICAS: "1"
      LOG_LEVEL: "debug"
      NODE_SELECTOR: "workload-type=spot-optimized"  # Staging uses Spot (70% cost savings)
```

## Cost Optimization Patterns

### Spot Instance Configuration for Flux-Managed Workloads

```yaml
# apps/production/app-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: apps
spec:
  replicas: 5
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      # Mix Spot (80%) and On-Demand (20%) for cost + reliability
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 80
              preference:
                matchExpressions:
                  - key: workload-type
                    operator: In
                    values:
                      - spot-optimized
            - weight: 20
              preference:
                matchExpressions:
                  - key: workload-type
                    operator: In
                    values:
                      - on-demand
      tolerations:
        - key: "spot"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"
      # Handle Spot interruptions gracefully
      terminationGracePeriodSeconds: 120  # Allow 2-min shutdown
      containers:
        - name: app
          image: myapp:latest
          resources:
            requests:
              cpu: 100m     # Right-sized (40-70% utilization target)
              memory: 256Mi
            limits:
              cpu: 200m
              memory: 512Mi
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15 && /app/graceful-shutdown.sh"]
```

### Right-Sizing with HPA and VPA

```yaml
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
  namespace: apps
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60  # Target 40-70% optimal range
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # Slow scale-down to prevent thrashing
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0  # Fast scale-up for traffic spikes
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
```

### Non-Production Environment Scheduling

```yaml
# CronJob to shut down staging environments during off-hours
apiVersion: batch/v1
kind: CronJob
metadata:
  name: staging-shutdown
  namespace: flux-system
spec:
  schedule: "0 19 * * 1-5"  # 7 PM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: flux-automation
          containers:
            - name: shutdown
              image: bitnami/kubectl:latest
              command:
                - /bin/sh
                - -c
                - |
                  kubectl scale deployment --all --replicas=0 -n staging-apps
          restartPolicy: OnFailure
---
# CronJob to start up staging environments
apiVersion: batch/v1
kind: CronJob
metadata:
  name: staging-startup
  namespace: flux-system
spec:
  schedule: "0 8 * * 1-5"  # 8 AM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: flux-automation
          containers:
            - name: startup
              image: bitnami/kubectl:latest
              command:
                - /bin/sh
                - -c
                - |
                  # Trigger Flux reconciliation to restore desired state
                  flux reconcile kustomization staging-apps --with-source
          restartPolicy: OnFailure
```

## Health Checks and Validation

### Deployment Health Checks

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
    name: app-repo
  path: ./apps/production
  prune: true
  wait: true
  timeout: 5m
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: frontend
      namespace: apps
    - apiVersion: apps/v1
      kind: StatefulSet
      name: database
      namespace: data
    - apiVersion: batch/v1
      kind: Job
      name: migration
      namespace: apps
    - apiVersion: gateway.networking.k8s.io/v1
      kind: Gateway
      name: production-gateway
      namespace: gateway-system
```

### HelmRelease Testing

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: app
  namespace: apps
spec:
  chart:
    spec:
      chart: app
      sourceRef:
        kind: HelmRepository
        name: private-charts
  test:
    enable: true
    timeout: 5m
  valuesFrom:
    - kind: ConfigMap
      name: app-config
      valuesKey: values.yaml
```

## Troubleshooting Commands

```bash
# Check Flux system status
flux check

# List all Flux resources
flux get all

# Reconcile immediately (force sync)
flux reconcile source git app-repo
flux reconcile kustomization apps
flux reconcile helmrelease nginx-ingress

# Suspend/resume reconciliation
flux suspend kustomization apps
flux resume kustomization apps

# View logs with filtering
flux logs --level=error --all-namespaces
flux logs --kind=Kustomization --name=apps

# Debug specific resource
kubectl describe kustomization apps -n flux-system
kubectl describe helmrelease app -n apps
kubectl describe gateway production-gateway -n gateway-system

# Export current state
flux export source git app-repo
flux export kustomization apps

# Validate Flux resources before committing
flux diff kustomization apps --path ./clusters/production/apps.yaml

# Check for drift between Git and cluster
flux diff kustomization infrastructure --path ./infrastructure/production
```

## Usage Guidelines

### When to Use This Skill

- User requests Flux resource generation
- GitOps deployment patterns needed
- Multi-environment Kubernetes deployments
- Helm chart deployments via GitOps
- Image update automation required
- Multi-tenant cluster configurations
- Progressive delivery strategies
- Gateway API resources managed via GitOps
- Cost optimization for Kubernetes workloads
- Security hardening for GitOps pipelines

### When NOT to Use This Skill

- Standalone Kubernetes manifests (use kubernetes-native skill)
- Argo CD or other GitOps tools (different API/patterns)
- Non-Kubernetes deployments
- Direct `kubectl apply` workflows
- CI/CD pipelines not using GitOps
- Terraform or cloud provider resource management

## Integration with iac-team Agents

### With iac-generator Agent

When the `iac-generator` agent needs Flux patterns:

1. **Reference this skill** for Flux resource structures
2. **Apply security constraints**: OIDC auth, encrypted secrets, validation pipelines
3. **Use dependency ordering**: Infrastructure before apps
4. **Include health checks**: Wait for readiness before marking complete
5. **Validate before writing**: Use `kubectl --dry-run` or `flux diff`
6. **Add cost optimization**: Spot instance tolerations, right-sized resource requests
7. **Security scanning**: Integrate Trivy/Checkov validation in CI/CD

### With iac-analyzer Agent

When the `iac-analyzer` agent reviews Flux configurations:

1. **Check for OIDC usage** instead of long-lived credentials
2. **Verify secret encryption** with SOPS or External Secrets
3. **Validate dependency ordering** in Kustomizations
4. **Check health checks** are configured for critical resources
5. **Review resource requests/limits** for right-sizing (40-70% CPU utilization)
6. **Verify Spot instance configuration** for non-critical workloads
7. **Ensure validation pipeline** exists (technical + policy checks)

## Advanced Patterns

### Flux with OCI Artifact Repositories

```yaml
# Use OCI repository as source instead of Git
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: app-manifests
  namespace: flux-system
spec:
  interval: 5m
  url: oci://ghcr.io/org/app-manifests
  ref:
    tag: latest
  secretRef:
    name: ghcr-credentials
---
# Kustomization using OCI source
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: OCIRepository
    name: app-manifests
  path: ./production
  prune: true
```

### Flux with Terraform Integration

```yaml
# Flux manages Terraform-created Kubernetes resources
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: terraform-managed-apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: terraform-output-repo
  path: ./k8s-manifests  # Generated by Terraform
  prune: true
  wait: true
  # Depends on Terraform having run successfully
  dependsOn:
    - name: infrastructure
```

## Constraints Compliance

This skill enforces:
- ✅ No hardcoded secrets (use SOPS, external-secrets)
- ✅ OIDC preferred over long-lived credentials
- ✅ Kubernetes manifests pass `kubectl --dry-run` validation
- ✅ Helm charts pass `helm lint --strict`
- ✅ Security scanning integration points (Trivy, Checkov)
- ✅ Multi-phase validation (technical + intent/policy)
- ✅ Cost optimization patterns (Spot instances, right-sizing, scheduling)
- ✅ Gateway API v1 compatibility (when using Gateway resources)
- ✅ Resource limits and requests for all workloads

---

**Version**: 2.0.0
**Last Updated**: 2026-02-03
**Compatible With**: Flux v2.x (toolkit.fluxcd.io/v1), Gateway API v1.x, Kubernetes 1.29+
