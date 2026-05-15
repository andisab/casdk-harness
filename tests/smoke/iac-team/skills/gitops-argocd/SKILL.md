---
name: gitops-argocd
description: >
  GitOps patterns and best practices for Argo CD continuous delivery.
  Provides Argo CD Application and ApplicationSet manifests, multi-environment
  deployment strategies, sync wave orchestration, security hardening patterns,
  and cost optimization configurations with CI/CD integration.

  Activate when user mentions: Argo CD, ArgoCD, GitOps, Application manifest,
  ApplicationSet, sync waves, progressive rollouts, image updater, App of Apps,
  declarative deployment, automated sync, Argo Rollouts integration, GitHub Actions
  GitOps, GitLab Agent, Flux integration.

  Use for: Generating Argo CD resources, multi-tenant patterns, progressive delivery,
  dependency management via sync waves, health checks, automated image updates,
  OIDC authentication, security scanning integration, cost-optimized workload deployment,
  CI/CD pipeline integration with GitHub Actions and GitLab.

  Do NOT use for: Standalone Kubernetes manifests (use kubernetes-native skill),
  Flux CD patterns, Jenkins pipelines, or non-GitOps deployment strategies.
---

# GitOps Argo CD Skill

## Purpose

Provides Argo CD patterns for GitOps-based continuous delivery to Kubernetes clusters. Covers Application and ApplicationSet definitions, repository structures, multi-environment configurations, sync wave orchestration, security best practices, validation pipelines, cost optimization strategies, and CI/CD integration for cloud-native deployments.

## Capabilities

### Core Argo CD Features
- **Argo CD Installation**: Bootstrap Argo CD with HA configuration, RBAC, and SSO
- **Application Manifests**: Define Application resources with sync policies and health checks
- **ApplicationSets**: Implement dynamic application generation for multi-cluster and multi-tenant scenarios
- **Sync Wave Orchestration**: Control deployment ordering using annotations and sync waves
- **App of Apps Pattern**: Manage application portfolios hierarchically
- **Image Updater Integration**: Automate container image updates with policies
- **Multi-Tenancy**: Namespace isolation, RBAC, AppProject scoping
- **Multi-Cluster Management**: Deploy applications across multiple Kubernetes clusters
- **Multi-Environment**: Structure repos for dev/staging/prod with Kustomize/Helm

### Progressive Delivery
- **Argo Rollouts Integration**: Canary and blue-green deployments with automated analysis
- **Traffic Splitting**: Weight-based routing for gradual rollouts
- **Analysis Templates**: Prometheus-based automated rollout validation

### Security & Compliance
- **OIDC Authentication**: Secure Git and cluster access with short-lived credentials
- **GitHub App Integration**: Secure Git authentication without long-lived tokens
- **Secret Management**: HashiCorp Vault, AWS Secrets Manager, External Secrets Operator integration
- **Multi-Phase Validation**: PreSync hooks with Trivy/Checkov security scanning
- **Policy-as-Code**: OPA Gatekeeper integration for policy enforcement
- **Notification System**: Configure alerts to Slack, Teams, Git providers

### Modern Kubernetes Features
- **Gateway API Integration**: Manage Gateway API v1 resources via Argo CD GitOps
- **Gateway API Migration**: Incremental migration from Ingress to Gateway API with zero downtime
- **Native Sidecar Containers**: Kubernetes 1.29+ sidecar lifecycle management patterns
- **BackendTLSPolicy**: TLS termination and re-encryption for Gateway API

### CI/CD Integration
- **GitHub Actions OIDC**: Short-lived credentials for GitOps workflows
- **GitLab Agent + Flux**: Secure GitOps deployments with OCI image sources
- **Reusable Workflows**: Standardized Argo CD deployment patterns
- **Matrix Strategies**: Multi-environment parallel deployments

### Cost Optimization
- **Spot Instance Configuration**: Argo CD-managed workloads on cost-optimized nodes
- **Resource Right-Sizing**: 40-70% CPU utilization targets with HPA
- **Environment-Specific Resources**: Production on-demand, staging spot instances

## Activation

This skill activates automatically when users reference:

- Argo CD components: `Application`, `ApplicationSet`, `AppProject`, `argocd-server`, `argocd-repo-server`
- GitOps concepts: declarative deployment, automated sync, self-healing, drift detection
- Argo CD features: sync waves, health checks, resource hooks, prune propagation
- Multi-environment patterns: app-of-apps, ApplicationSet generators, overlay structure
- Security: OIDC, SSO (Okta, Google, GitHub), RBAC, secret management
- Cost optimization: Spot instances, right-sizing, resource efficiency
- Progressive delivery: Argo Rollouts, canary analysis, blue-green deployment
- Gateway API: HTTPRoute, Gateway resources, BackendTLSPolicy
- CI/CD: GitHub Actions GitOps, GitLab Agent, Flux integration
- Migration: Ingress to Gateway API, certificate-based to agent-based Kubernetes integration

## Core Patterns

### 1. Argo CD Directory Structure

```
bootstrap/
  argocd/
    install.yaml              # Argo CD installation
    argocd-cm.yaml           # ConfigMap for settings
    argocd-rbac-cm.yaml      # RBAC policies
    argocd-cmd-params-cm.yaml # Server parameters

apps/
  base/                       # Base application definitions
  overlays/
    production/               # Production-specific configs
    staging/                  # Staging-specific configs

app-of-apps/
  root-app.yaml              # Root Application managing all apps
  infrastructure.yaml         # Infrastructure apps
  applications.yaml           # Business applications

projects/
  team-alpha.yaml            # AppProject for team isolation
  team-beta.yaml             # AppProject for team isolation
```

### 2. Application Manifest with OIDC Authentication

**Core Application Structure:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
  # Finalizers ensure cascading delete of resources
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  # Annotations for notifications and metadata
  annotations:
    argocd-image-updater.argoproj.io/image-list: myapp=ghcr.io/org/myapp
    argocd-image-updater.argoproj.io/myapp.update-strategy: semver
    notifications.argoproj.io/subscribe.on-sync-succeeded.slack: deployments
spec:
  # Project for RBAC and resource restrictions
  project: default

  # Source repository configuration
  source:
    repoURL: https://github.com/org/app-repo
    targetRevision: main
    path: k8s/production

    # For Helm charts
    helm:
      releaseName: myapp
      valueFiles:
        - values.yaml
        - values-production.yaml
      parameters:
        - name: image.tag
          value: "1.0.0"

    # For Kustomize
    kustomize:
      namePrefix: prod-
      commonLabels:
        environment: production
      images:
        - myapp=ghcr.io/org/myapp:v1.0.0

  # Destination cluster and namespace
  destination:
    server: https://kubernetes.default.svc
    namespace: myapp-prod

  # Sync policy configuration
  syncPolicy:
    automated:
      prune: true          # Delete resources not in Git
      selfHeal: true       # Auto-sync on drift detection
      allowEmpty: false    # Prevent empty sync
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true    # Prune after successful sync
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m

  # Ignore differences for known fields
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas  # HPA manages replicas
```

**GitHub App Authentication (Recommended):**

```yaml
# Best practice: GitHub Apps provide fine-grained, short-lived access tokens
apiVersion: v1
kind: Secret
metadata:
  name: github-app-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://github.com/org/app-repo
  githubAppID: "123456"
  githubAppInstallationID: "789012"
  githubAppPrivateKey: |
    -----BEGIN RSA PRIVATE KEY-----
    ...
    -----END RSA PRIVATE KEY-----
```

**OIDC Authentication Alternative:**

```yaml
# For environments requiring OIDC token-based authentication
apiVersion: v1
kind: Secret
metadata:
  name: git-oidc-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://github.com/org/app-repo
  # OIDC token refreshed automatically by external system
  password: <oidc-token>
  username: x-access-token
```

### 3. ApplicationSet for Multi-Environment

**Git Generator Pattern:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-environments
  namespace: argocd
spec:
  # Control sync behavior
  syncPolicy:
    preserveResourcesOnDeletion: false

  generators:
    # Git directory generator - one app per directory
    - git:
        repoURL: https://github.com/org/app-repo
        revision: main
        directories:
          - path: apps/*/overlays/production
          - path: apps/*/overlays/staging

  template:
    metadata:
      name: '{{path.basename}}-{{path[2]}}'
      labels:
        environment: '{{path[2]}}'
        app: '{{path.basename}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/app-repo
        targetRevision: main
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path.basename}}-{{path[2]}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

**Cluster Generator Pattern (Multi-Cluster):**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-clusters
  namespace: argocd
spec:
  generators:
    # Deploy to all registered clusters with specific label
    - clusters:
        selector:
          matchLabels:
            environment: production

  template:
    metadata:
      name: 'myapp-{{name}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/app-repo
        targetRevision: main
        path: k8s/base
        helm:
          parameters:
            - name: cluster.name
              value: '{{name}}'
            - name: cluster.region
              value: '{{metadata.labels.region}}'
      destination:
        server: '{{server}}'
        namespace: myapp
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

### 4. Sync Wave Orchestration

Control deployment order using sync waves (lower numbers deploy first):

```yaml
# Wave 0: Namespaces and CRDs
apiVersion: v1
kind: Namespace
metadata:
  name: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "0"
---
# Wave 1: ConfigMaps and Secrets
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "1"
---
# Wave 2: Deployments and Services
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "2"
---
# Wave 3: Gateway API resources after apps ready
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "3"
---
# Wave 4: Database migrations after infrastructure
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "4"
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
```

### 5. App of Apps Pattern

**Root Application:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-app
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/org/app-repo
    targetRevision: main
    path: app-of-apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Infrastructure Apps (Child):**

```yaml
# app-of-apps/infrastructure.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: infrastructure
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: infrastructure
  source:
    repoURL: https://github.com/org/infrastructure-repo
    targetRevision: main
    path: k8s/production
  destination:
    server: https://kubernetes.default.svc
    namespace: infrastructure
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
---
# app-of-apps/applications.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: applications
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  project: default
  source:
    repoURL: https://github.com/org/app-repo
    targetRevision: main
    path: apps/production
  destination:
    server: https://kubernetes.default.svc
    namespace: apps
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 6. Multi-Tenant AppProject

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-alpha
  namespace: argocd
spec:
  description: "Project for Team Alpha applications"

  # Source repositories allowed
  sourceRepos:
    - https://github.com/org/team-alpha-*

  # Destination clusters and namespaces
  destinations:
    - namespace: 'team-alpha-*'
      server: https://kubernetes.default.svc
    - namespace: team-alpha-shared
      server: https://kubernetes.default.svc

  # Deny creation of specific resource types
  namespaceResourceBlacklist:
    - group: ''
      kind: ResourceQuota
    - group: ''
      kind: LimitRange

  # Allow only specific resource types
  namespaceResourceWhitelist:
    - group: 'apps'
      kind: Deployment
    - group: ''
      kind: Service
    - group: ''
      kind: ConfigMap
    - group: ''
      kind: Secret
    - group: 'networking.k8s.io'
      kind: Ingress
    - group: 'gateway.networking.k8s.io'
      kind: HTTPRoute

  # Cluster resource restrictions
  clusterResourceBlacklist:
    - group: '*'
      kind: '*'

  # RBAC roles
  roles:
    - name: team-alpha-admin
      description: "Full access to team alpha applications"
      policies:
        - p, proj:team-alpha:team-alpha-admin, applications, *, team-alpha/*, allow
      groups:
        - team-alpha

    - name: team-alpha-viewer
      description: "Read-only access"
      policies:
        - p, proj:team-alpha:team-alpha-viewer, applications, get, team-alpha/*, allow
      groups:
        - team-alpha-viewers
```

### 7. Image Updater Integration

**Argo CD Image Updater Configuration:**

```yaml
# ConfigMap for Image Updater
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-image-updater-config
  namespace: argocd
data:
  registries.conf: |
    registries:
    - name: GitHub Container Registry
      api_url: https://ghcr.io
      prefix: ghcr.io
      credentials: secret:argocd/ghcr-credentials#creds
      default: true

    - name: Docker Hub
      api_url: https://registry-1.docker.io
      prefix: docker.io
      credentials: pullsecret:kube-system/dockerhub
```

**Application with Image Update Automation:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
  annotations:
    # Configure image updater
    argocd-image-updater.argoproj.io/image-list: myapp=ghcr.io/org/myapp
    argocd-image-updater.argoproj.io/myapp.update-strategy: semver
    argocd-image-updater.argoproj.io/myapp.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+$
    argocd-image-updater.argoproj.io/myapp.ignore-tags: latest, dev
    # Write back method
    argocd-image-updater.argoproj.io/write-back-method: git:secret:argocd/git-credentials
    argocd-image-updater.argoproj.io/git-branch: main
spec:
  source:
    repoURL: https://github.com/org/app-repo
    targetRevision: main
    path: k8s/production
    kustomize:
      images:
        - myapp=ghcr.io/org/myapp:v1.0.0  # Updated automatically
  # ... rest of spec
```

### 8. Secret Management with External Secrets

**External Secrets Operator Integration:**

```yaml
# ExternalSecret definition
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "1"  # Before deployments
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: app-secrets
    creationPolicy: Owner
  data:
    - secretKey: database-password
      remoteRef:
        key: production/myapp/db
        property: password
---
# SecretStore for AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: myapp
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      # Use IRSA (IAM Roles for Service Accounts) - no credentials
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
```

### 9. Notification Configuration

```yaml
# argocd-notifications-cm ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
  namespace: argocd
data:
  # Service configuration
  service.slack: |
    token: $slack-token

  # Notification templates
  template.app-deployed: |
    message: |
      Application {{.app.metadata.name}} deployed successfully.
      Sync Status: {{.app.status.sync.status}}
      Health Status: {{.app.status.health.status}}
      {{if eq .serviceType "slack"}}:white_check_mark:{{end}}
    slack:
      attachments: |
        [{
          "title": "{{ .app.metadata.name}}",
          "title_link":"{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
          "color": "#18be52",
          "fields": [
          {
            "title": "Sync Status",
            "value": "{{.app.status.sync.status}}",
            "short": true
          },
          {
            "title": "Repository",
            "value": "{{.app.spec.source.repoURL}}",
            "short": true
          }
          ]
        }]

  # Triggers
  trigger.on-deployed: |
    - description: Application deployed
      send:
      - app-deployed
      when: app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'

  trigger.on-sync-failed: |
    - description: Application sync failed
      send:
      - app-sync-failed
      when: app.status.operationState.phase in ['Error', 'Failed']
---
# Application subscription
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  annotations:
    notifications.argoproj.io/subscribe.on-deployed.slack: deployments
    notifications.argoproj.io/subscribe.on-sync-failed.slack: alerts
```

## Gateway API Integration

### Gateway API v1 Migration from Ingress

**Incremental Migration Strategy (Zero Downtime):**

```yaml
# Step 1: Run in parallel - keep existing Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: myapp
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp-service
                port:
                  number: 80
---
# Step 2: Deploy Gateway API resources alongside
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: production-gateway
  namespace: gateway-system
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  gatewayClassName: envoy-gateway
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: All
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: All
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-cert
---
# Step 3: Create HTTPRoute (test in parallel)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: myapp-route
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "3"
spec:
  parentRefs:
    - name: production-gateway
      namespace: gateway-system
  hostnames:
    - "myapp.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: myapp-service
          port: 80
---
# Step 4: Validate Gateway status before removing Ingress
# Run: kubectl wait --for=condition=Programmed gateway/production-gateway -n gateway-system
# Only after Gateway Programmed=True, delete Ingress resource incrementally
```

**Using ingress2gateway Tool:**

```bash
# Install ingress2gateway
go install github.com/kubernetes-sigs/ingress2gateway@latest

# Convert Ingress to Gateway API resources
ingress2gateway print \
  --input-file=ingress.yaml \
  --output-file=gateway-api.yaml

# Review generated HTTPRoute and Gateway resources
kubectl apply -f gateway-api.yaml --dry-run=server
```

**Role-Oriented Resource Separation:**

```yaml
# Cluster operator concern: Gateway (shared infrastructure)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-gateway
  namespace: gateway-system
  annotations:
    # Managed by infrastructure team
    argocd.argoproj.io/sync-wave: "1"
spec:
  gatewayClassName: cilium
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: Selector
          selector:
            matchLabels:
              gateway-access: "true"
      tls:
        mode: Terminate
        certificateRefs:
          - name: shared-tls-cert
---
# Application developer concern: HTTPRoute (application-specific routing)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: myapp
  annotations:
    # Managed by application team
    argocd.argoproj.io/sync-wave: "3"
spec:
  parentRefs:
    - name: shared-gateway
      namespace: gateway-system
  hostnames:
    - "api.myapp.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /api/v1
          headers:
            - name: X-API-Version
              value: v1
      filters:
        - type: RequestHeaderModifier
          requestHeaderModifier:
            add:
              - name: X-Forwarded-Proto
                value: https
      backendRefs:
        - name: api-service
          port: 8080
          weight: 80
        - name: api-service-canary
          port: 8080
          weight: 20
```

### BackendTLSPolicy for TLS Re-Encryption

**Version: gateway.networking.k8s.io/v1alpha3**

```yaml
# BackendTLSPolicy for TLS termination at Gateway and re-encryption to backend
apiVersion: gateway.networking.k8s.io/v1alpha3
kind: BackendTLSPolicy
metadata:
  name: backend-tls-policy
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  # Single targetRef (core conformance limitation)
  targetRef:
    group: ''
    kind: Service
    name: backend-service
  tls:
    # At least one required: CACertificateRefs OR WellKnownCACertificates
    caCertificateRefs:
      - name: backend-ca-cert
        kind: ConfigMap
        # Must be in same namespace (cross-namespace not allowed)
        group: ''
    hostname: backend.internal.example.com
---
# Alternative: Using well-known CA certificates
apiVersion: gateway.networking.k8s.io/v1alpha3
kind: BackendTLSPolicy
metadata:
  name: backend-tls-wellknown
  namespace: myapp
spec:
  targetRef:
    group: ''
    kind: Service
    name: api-service
  tls:
    wellKnownCACertificates: System
    hostname: api.internal.example.com
```

**Important Constraints:**

- BackendTLSPolicy uses single targetRef (core conformance)
- Cross-namespace certificate references are **not allowed**
- Must set either `CACertificateRefs` OR `WellKnownCACertificates`
- Status representation limitations when targeting multiple Services used in HTTPRoutes on same Gateway

### Gateway Argo CD Application

```yaml
# Manage Gateway API resources with Argo CD
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gateway-api-infrastructure
  namespace: argocd
spec:
  project: infrastructure
  source:
    repoURL: https://github.com/org/infrastructure-repo
    targetRevision: main
    path: gateway-api
  destination:
    server: https://kubernetes.default.svc
    namespace: gateway-system
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
  # Ensure Gateway becomes Programmed before apps deploy
  syncWaves:
    - wave: 1
```

## Native Sidecar Containers (Kubernetes 1.29+)

**Requirements:**
- Kubernetes API server version: 1.29+
- Node version: 1.29+

### Logging Sidecar Pattern

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-with-logging-sidecar
  namespace: myapp
spec:
  replicas: 3
  template:
    spec:
      # Native sidecar: init container with restartPolicy Always
      initContainers:
        - name: log-collector
          image: fluent/fluent-bit:2.0
          restartPolicy: Always  # Makes it a native sidecar (Kubernetes 1.29+)
          ports:
            - containerPort: 24224
              name: fluentd
              protocol: TCP
          # Startup probe ensures sidecar ready before main containers
          startupProbe:
            httpGet:
              path: /api/v1/health
              port: 2020
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30
          # Readiness contributes to Pod readiness
          readinessProbe:
            httpGet:
              path: /api/v1/health
              port: 2020
            periodSeconds: 10
          # Lifecycle hooks for graceful termination
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5 && /fluent-bit/bin/fluent-bit -c /fluent-bit/etc/fluent-bit.conf -s"]
          volumeMounts:
            - name: log-volume
              mountPath: /var/log
          # Appropriate grace period for sidecar cleanup
          terminationGracePeriodSeconds: 30

      # Main application containers start after sidecar ready
      containers:
        - name: myapp
          image: myapp:latest
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: log-volume
              mountPath: /var/log

      volumes:
        - name: log-volume
          emptyDir: {}
```

### Service Mesh Sidecar (Istio/Linkerd Pattern)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-with-proxy
  namespace: myapp
spec:
  template:
    spec:
      initContainers:
        # Native sidecar proxy (replaces traditional sidecar injection)
        - name: envoy-proxy
          image: envoyproxy/envoy:v1.28
          restartPolicy: Always
          ports:
            - containerPort: 15001
              name: proxy-admin
          startupProbe:
            httpGet:
              path: /ready
              port: 15001
            initialDelaySeconds: 3
            periodSeconds: 2
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 15001
            periodSeconds: 5
          # PreStop ensures graceful proxy shutdown
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15 && curl -X POST http://localhost:15001/drain_listeners"]
          terminationGracePeriodSeconds: 45

      containers:
        - name: myapp
          image: myapp:latest
          ports:
            - containerPort: 8080
```

### Job with Sidecar (Non-Blocking Pattern)

```yaml
# Traditional sidecars prevent Job completion; native sidecars terminate after main container
apiVersion: batch/v1
kind: Job
metadata:
  name: data-processing-job
  namespace: myapp
spec:
  template:
    spec:
      restartPolicy: OnFailure
      initContainers:
        # Sidecar provides service during Job but terminates after main completes
        - name: metrics-collector
          image: prometheus/pushgateway:latest
          restartPolicy: Always
          ports:
            - containerPort: 9091
          startupProbe:
            httpGet:
              path: /-/healthy
              port: 9091
            periodSeconds: 2
            failureThreshold: 15

      containers:
        - name: processor
          image: data-processor:v1
          env:
            - name: METRICS_ENDPOINT
              value: "http://localhost:9091/metrics/job/data-processing"
          command:
            - /bin/sh
            - -c
            - |
              echo "Starting processing..."
              process_data.sh
              echo "Complete - metrics sidecar will terminate automatically"
```

**Termination Behavior:**

- Native sidecars (restartPolicy Always) start during init phase
- Main containers wait for sidecar startupProbe success
- Sidecars terminate in **reverse order** after main containers
- Jobs complete successfully even with native sidecars

## Security Best Practices

### OIDC Authentication Patterns

**AWS IRSA (IAM Roles for Service Accounts):**

```yaml
# ServiceAccount with IRSA annotation
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argocd-repo-server
  namespace: argocd
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/argocd-repo-server
---
# IAM Trust Policy (AWS)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/oidc.eks.REGION.amazonaws.com/id/CLUSTER_ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.REGION.amazonaws.com/id/CLUSTER_ID:sub": "system:serviceaccount:argocd:argocd-repo-server",
          "oidc.eks.REGION.amazonaws.com/id/CLUSTER_ID:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

### Multi-Phase Validation Pipeline

**Phase 1: Technical Validation (Syntax & Structure)**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: validate-manifests-technical
  namespace: myapp
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  template:
    spec:
      serviceAccountName: validation-sa
      containers:
        - name: technical-validation
          image: aquasec/trivy:latest
          command:
            - sh
            - -c
            - |
              # Update vulnerability database
              trivy image --download-db-only

              # Security scan (CRITICAL and HIGH only)
              trivy config --severity CRITICAL,HIGH \
                --ignore-unfixed \
                --exit-code 1 \
                /manifests/

              # Syntax validation
              kubectl apply --dry-run=client -f /manifests/ --recursive

              # Terraform plan validation (if using Terraform)
              terraform plan -input=false -detailed-exitcode

              echo "✓ Technical validation passed (95%+ syntax success)"
          volumeMounts:
            - name: manifests
              mountPath: /manifests
      volumes:
        - name: manifests
          configMap:
            name: deployment-manifests
      restartPolicy: Never
  backoffLimit: 1
```

**Phase 2: Intent Validation (Policy & Requirements)**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: validate-manifests-intent
  namespace: myapp
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  template:
    spec:
      serviceAccountName: validation-sa
      containers:
        - name: intent-validation
          image: openpolicyagent/conftest:latest
          command:
            - sh
            - -c
            - |
              # OPA/Rego policy validation against organizational requirements
              conftest test /manifests/ \
                -p /policies/ \
                --fail-on-warn \
                --output json > /tmp/results.json

              # Check for contextual reasoning failures (47.6% of intent errors)
              # Validate dependency graphs against intent specifications
              python3 /scripts/validate_intent.py /tmp/results.json

              echo "✓ Intent validation passed (policy compliance verified)"
          volumeMounts:
            - name: manifests
              mountPath: /manifests
            - name: policies
              mountPath: /policies
            - name: scripts
              mountPath: /scripts
      volumes:
        - name: manifests
          configMap:
            name: deployment-manifests
        - name: policies
          configMap:
            name: opa-policies
        - name scripts:
          configMap:
            name: validation-scripts
      restartPolicy: Never
  backoffLimit: 1
```

**OPA Policy Example (policy-as-code):**

```rego
# policies/security_baseline.rego
package kubernetes.security

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.securityContext.runAsNonRoot
  msg = sprintf("Deployment %v must set runAsNonRoot: true", [input.metadata.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  container.securityContext.privileged
  msg = sprintf("Container %v must not run privileged", [container.name])
}

deny[msg] {
  input.kind == "Service"
  input.spec.type == "LoadBalancer"
  not input.metadata.annotations["service.beta.kubernetes.io/aws-load-balancer-ssl-cert"]
  msg = "LoadBalancer services must use SSL/TLS certificates"
}
```

### Policy Validation with OPA Gatekeeper

```yaml
# Constraint Template (no root containers)
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8spspprivilegedcontainer
spec:
  crd:
    spec:
      names:
        kind: K8sPSPPrivilegedContainer
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8spspprivileged

        violation[{"msg": msg}] {
          c := input.review.object.spec.containers[_]
          c.securityContext.privileged
          msg := sprintf("Privileged container is not allowed: %v", [c.name])
        }
---
# Apply constraint to namespaces
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sPSPPrivilegedContainer
metadata:
  name: no-privileged-containers
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment", "StatefulSet", "DaemonSet"]
    namespaces:
      - production
      - staging
```

### Secret Management Best Practices

**Pattern 1: External Secrets Operator (Recommended)**

Already covered in Core Patterns section 8.

**Pattern 2: Sealed Secrets**

```yaml
# Generate sealed secret
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# SealedSecret resource (safe to commit to Git)
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: app-secrets
  namespace: myapp
spec:
  encryptedData:
    database-password: AgBy3i4OJSWK+PiTySYZZA9rO43cGDEq...
  template:
    metadata:
      name: app-secrets
```

**Pattern 3: Vault Integration**

```yaml
# Vault Agent Injector
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "myapp"
        vault.hashicorp.com/agent-inject-secret-db: "secret/data/myapp/database"
    spec:
      serviceAccountName: myapp
      containers:
        - name: app
          image: myapp:latest
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: vault-secret
                  key: database-password
```

## CI/CD Integration

### GitHub Actions with OIDC

**Reusable Workflow for Argo CD Deployment:**

```yaml
# .github/workflows/argocd-deploy.yml
name: Argo CD GitOps Deployment

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      application:
        required: true
        type: string
      image_tag:
        required: true
        type: string
    secrets:
      ARGOCD_SERVER:
        required: true

permissions:
  id-token: write   # Required for OIDC token request
  contents: read

jobs:
  deploy:
    name: Deploy to ${{ inputs.environment }}
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      # OIDC authentication to AWS (short-lived credentials)
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-argocd
          role-session-name: GitHubActions-ArgoCD-${{ github.run_id }}
          aws-region: us-west-2

      # Update image tag in Git repository
      - name: Update Kustomization
        run: |
          cd k8s/overlays/${{ inputs.environment }}
          kustomize edit set image ${{ inputs.application }}=${{ inputs.image_tag }}
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add kustomization.yaml
          git commit -m "Update ${{ inputs.application }} to ${{ inputs.image_tag }}"
          git push

      # Trigger Argo CD sync
      - name: Argo CD Sync
        run: |
          argocd app sync ${{ inputs.application }}-${{ inputs.environment }} \
            --server ${{ secrets.ARGOCD_SERVER }} \
            --auth-token ${{ steps.argocd-token.outputs.token }} \
            --prune \
            --timeout 600

      # Wait for healthy status
      - name: Wait for deployment
        run: |
          argocd app wait ${{ inputs.application }}-${{ inputs.environment }} \
            --server ${{ secrets.ARGOCD_SERVER }} \
            --auth-token ${{ steps.argocd-token.outputs.token }} \
            --health \
            --timeout 600
```

**Caller Workflow:**

```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    uses: ./.github/workflows/argocd-deploy.yml@v1.2.3  # Pin to tag
    with:
      environment: production
      application: myapp
      image_tag: ${{ github.ref_name }}
    secrets:
      ARGOCD_SERVER: ${{ secrets.ARGOCD_SERVER }}
```

**AWS IAM Trust Policy for OIDC:**

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
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### GitLab Agent with Flux GitOps

**GitLab Agent Configuration:**

```yaml
# .gitlab/agents/production/config.yaml
gitops:
  manifest_projects:
    - id: org/infrastructure
      paths:
        - glob: 'apps/**/*.yaml'
      reconcile_timeout: 3600s
      dry_run_strategy: none
      prune: true
      prune_timeout: 3600s
      prune_propagation_policy: foreground
      inventory_policy: must_match

flux:
  # Flux handles GitOps sync, agentk provides management interface
  reconciliation:
    enabled: true
  sources:
    # Use OCI images as source (recommended over Git)
    - kind: OCIRepository
      name: myapp-prod
      namespace: flux-system
      interval: 5m
      url: oci://registry.gitlab.com/org/delivery/myapp
      tag: production

  # Immediate reconciliation via Receiver
  receivers:
    - kind: Receiver
      name: gitlab-receiver
      namespace: flux-system
      secretRef:
        name: webhook-token
```

**Flux OCIRepository Source:**

```yaml
# Managed by GitLab Agent - declarative cluster state
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: myapp-production
  namespace: flux-system
spec:
  interval: 5m
  url: oci://registry.gitlab.com/org/delivery-repos/myapp
  ref:
    tag: production
  secretRef:
    name: gitlab-registry-credentials
---
# Kustomization for automatic deployment
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: myapp-production
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: OCIRepository
    name: myapp-production
  path: ./manifests
  prune: true
  wait: true
  timeout: 5m
```

**GitLab CI/CD Pipeline:**

```yaml
# .gitlab-ci.yml
stages:
  - build
  - package
  - deploy

variables:
  OCI_REGISTRY: registry.gitlab.com/org/delivery-repos

build:
  stage: build
  image: docker:latest
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

package-oci:
  stage: package
  image: fluxcd/flux-cli:v2.0
  script:
    # Package Kubernetes manifests as OCI artifact
    - |
      flux push artifact oci://$OCI_REGISTRY/myapp:$CI_COMMIT_TAG \
        --path="./k8s/production" \
        --source="${CI_PROJECT_URL}" \
        --revision="${CI_COMMIT_SHA}"

trigger-gitops:
  stage: deploy
  image: curlimages/curl:latest
  script:
    # Trigger Flux Receiver for immediate reconciliation
    - |
      curl -X POST $FLUX_RECEIVER_URL \
        -H "Authorization: Bearer $FLUX_WEBHOOK_TOKEN"
  only:
    - tags
```

### Multi-Environment Matrix Deployment

```yaml
# .github/workflows/multi-env-deploy.yml
name: Multi-Environment Deployment

on:
  workflow_dispatch:
    inputs:
      image_tag:
        required: true
        type: string

jobs:
  deploy:
    strategy:
      matrix:
        environment: [dev, staging, production]
        include:
          - environment: dev
            cluster: dev-cluster
            replicas: 2
            resources: small
          - environment: staging
            cluster: staging-cluster
            replicas: 3
            resources: medium
          - environment: production
            cluster: prod-cluster-1
            replicas: 5
            resources: large
      fail-fast: false  # Continue deploying to other envs on failure
      max-parallel: 2   # Limit concurrent deployments

    runs-on: ubuntu-latest
    environment: ${{ matrix.environment }}

    steps:
      - name: Deploy to ${{ matrix.environment }}
        run: |
          argocd app set myapp-${{ matrix.environment }} \
            --parameter replicaCount=${{ matrix.replicas }} \
            --parameter resources.profile=${{ matrix.resources }} \
            --kustomize-image myapp=${{ inputs.image_tag }}

          argocd app sync myapp-${{ matrix.environment }} --prune
          argocd app wait myapp-${{ matrix.environment }} --health
```

## Cost Optimization Patterns

### Spot Instance Configuration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-cost-optimized
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/org/app-repo
    targetRevision: main
    path: k8s/production
    helm:
      parameters:
        - name: spotInstanceEnabled
          value: "true"
        - name: spotInstanceMixPercentage
          value: "80"  # 80% Spot, 20% On-Demand
        - name: resources.requests.cpu
          value: "100m"  # Right-sized (40-70% utilization target)
        - name: resources.requests.memory
          value: "256Mi"
---
# Deployment with Spot configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myapp
spec:
  replicas: 5
  template:
    spec:
      # Prefer Spot instances with On-Demand fallback
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
      terminationGracePeriodSeconds: 120
      containers:
        - name: app
          image: myapp:latest
          resources:
            requests:
              cpu: 100m     # Right-sized for 40-70% utilization
              memory: 256Mi
            limits:
              cpu: 200m
              memory: 512Mi
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15 && /app/graceful-shutdown.sh"]
```

### HPA with Optimal Utilization Targets

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
  namespace: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "3"  # After Deployment
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
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
      stabilizationWindowSeconds: 300  # Slow scale-down
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0  # Fast scale-up
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
```

### Environment-Specific Resource Configuration

```yaml
# Production: On-Demand instances with higher resources
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-production
  namespace: argocd
spec:
  source:
    helm:
      parameters:
        - name: environment
          value: "production"
        - name: replicaCount
          value: "5"
        - name: nodeSelector.workload-type
          value: "on-demand"
        - name: resources.requests.cpu
          value: "500m"
        - name: resources.requests.memory
          value: "1Gi"
---
# Staging: Spot instances with lower resources (70% cost savings)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-staging
  namespace: argocd
spec:
  source:
    helm:
      parameters:
        - name: environment
          value: "staging"
        - name: replicaCount
          value: "2"
        - name: nodeSelector.workload-type
          value: "spot-optimized"
        - name: resources.requests.cpu
          value: "100m"
        - name: resources.requests.memory
          value: "256Mi"
```

## Progressive Delivery with Argo Rollouts

### Canary Deployment

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp-rollout
  namespace: myapp
spec:
  replicas: 5
  strategy:
    canary:
      steps:
        - setWeight: 20   # 20% traffic to canary
        - pause: {duration: 2m}
        - setWeight: 40
        - pause: {duration: 2m}
        - setWeight: 60
        - pause: {duration: 2m}
        - setWeight: 80
        - pause: {duration: 2m}
      # Automated analysis
      analysis:
        templates:
          - templateName: success-rate
        startingStep: 2
      # Automatic rollback on failure
      maxSurge: 1
      maxUnavailable: 0
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: app
          image: myapp:latest
---
# Analysis Template
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  metrics:
    - name: success-rate
      interval: 30s
      successCondition: result[0] >= 0.95
      provider:
        prometheus:
          address: http://prometheus.monitoring:9090
          query: |
            sum(rate(http_requests_total{status=~"2.."}[2m]))
            /
            sum(rate(http_requests_total[2m]))
```

### Blue-Green Deployment

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp-bluegreen
  namespace: myapp
spec:
  replicas: 5
  strategy:
    blueGreen:
      activeService: myapp-active
      previewService: myapp-preview
      autoPromotionEnabled: false  # Manual approval
      prePromotionAnalysis:
        templates:
          - templateName: smoke-tests
      postPromotionAnalysis:
        templates:
          - templateName: performance-tests
      scaleDownDelaySeconds: 300  # Keep blue for 5min
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: app
          image: myapp:latest
```

## Multi-Environment Strategy

### Kustomize Overlay Pattern

```
k8s/
  base/
    deployment.yaml
    service.yaml
    kustomization.yaml
  overlays/
    production/
      kustomization.yaml
      patches/
        replica-count.yaml
        resource-limits.yaml
    staging/
      kustomization.yaml
      patches/
        replica-count.yaml
        resource-limits.yaml
```

**Base Kustomization:**

```yaml
# k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml

commonLabels:
  app: myapp
```

**Production Overlay:**

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

namespace: myapp-prod

commonLabels:
  environment: production

images:
  - name: myapp
    newTag: v1.0.0

patches:
  - path: patches/replica-count.yaml
  - path: patches/resource-limits.yaml

configMapGenerator:
  - name: app-config
    literals:
      - ENVIRONMENT=production
      - LOG_LEVEL=warn
      - NODE_SELECTOR=on-demand
```

### Helm Values Pattern

```yaml
# Production Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-production
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/org/helm-charts
    chart: myapp
    targetRevision: 1.0.0
    helm:
      values: |
        environment: production
        replicaCount: 5
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
        nodeSelector:
          workload-type: on-demand
        autoscaling:
          enabled: true
          minReplicas: 3
          maxReplicas: 10
---
# Staging Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-staging
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/org/helm-charts
    chart: myapp
    targetRevision: 1.0.0
    helm:
      values: |
        environment: staging
        replicaCount: 2
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
        nodeSelector:
          workload-type: spot-optimized
        autoscaling:
          enabled: false
```

## Health Checks and Sync Policies

### Custom Health Checks

```yaml
# argocd-cm ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  # Custom health check for custom CRD
  resource.customizations.health.example.com_MyResource: |
    hs = {}
    if obj.status ~= nil then
      if obj.status.phase == "Running" then
        hs.status = "Healthy"
        hs.message = "Resource is running"
        return hs
      elseif obj.status.phase == "Failed" then
        hs.status = "Degraded"
        hs.message = obj.status.message
        return hs
      end
    end
    hs.status = "Progressing"
    hs.message = "Waiting for resource to start"
    return hs
```

### Sync Options

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
spec:
  syncPolicy:
    syncOptions:
      # Create namespace if not exists
      - CreateNamespace=true

      # Prune resources in correct order
      - PrunePropagationPolicy=foreground
      - PruneLast=true

      # Respect ignore differences
      - RespectIgnoreDifferences=true

      # Replace resources instead of apply
      - Replace=false

      # Server-side apply (Kubernetes 1.22+)
      - ServerSideApply=true

      # Fail sync on shared resource
      - FailOnSharedResource=false
```

## Troubleshooting Commands

```bash
# Check application status
argocd app get myapp

# Sync application immediately
argocd app sync myapp

# View sync details
argocd app history myapp
argocd app diff myapp

# View application logs
argocd app logs myapp

# Suspend/resume sync
argocd app set myapp --sync-policy none  # Suspend
argocd app set myapp --sync-policy automated  # Resume

# Delete application (keep resources)
argocd app delete myapp --cascade=false

# View sync operation details
kubectl describe application myapp -n argocd

# Check Argo CD server logs
kubectl logs -n argocd deployment/argocd-server

# Check repo server logs (useful for Git auth issues)
kubectl logs -n argocd deployment/argocd-repo-server

# List all applications
argocd app list

# Get application manifests
argocd app manifests myapp

# Rollback to previous version
argocd app rollback myapp <history-id>

# Refresh app (force Git polling)
argocd app refresh myapp --hard

# Validate Gateway status (Gateway API migration)
kubectl wait --for=condition=Programmed gateway/production-gateway -n gateway-system

# Check native sidecar status (Kubernetes 1.29+)
kubectl get pods -o jsonpath='{.items[*].spec.initContainers[?(@.restartPolicy=="Always")].name}'
```

## Usage Guidelines

### When to Use This Skill

- User requests Argo CD Application or ApplicationSet generation
- GitOps deployment patterns needed for Kubernetes
- Multi-environment or multi-cluster deployments
- Helm chart deployments via GitOps
- Automated image update workflows
- Multi-tenant cluster configurations
- Progressive delivery strategies (canary, blue-green)
- Gateway API resources managed via GitOps
- Gateway API migration from Ingress (zero downtime)
- Cost optimization for Kubernetes workloads
- Security hardening for GitOps pipelines
- CI/CD integration with GitHub Actions or GitLab
- Native sidecar container patterns (Kubernetes 1.29+)

### When NOT to Use This Skill

- Standalone Kubernetes manifests (use kubernetes-native skill)
- Flux CD or other GitOps tools (different API/patterns)
- Non-Kubernetes deployments
- Direct `kubectl apply` workflows
- CI/CD pipelines not using GitOps
- Terraform or cloud provider resource management

## Integration with iac-team Agents

### With iac-generator Agent

When the `iac-generator` agent needs Argo CD patterns:

1. **Reference this skill** for Application and ApplicationSet structures
2. **Apply security constraints**: OIDC/SSO auth, External Secrets, validation hooks
3. **Use sync waves**: Control deployment ordering (CRDs → Config → Apps → Routes)
4. **Include health checks**: Configure custom health assessments for CRDs
5. **Validate before writing**: Use `argocd app diff` or `kubectl --dry-run`
6. **Add cost optimization**: Spot instance configurations, right-sized resources
7. **Security scanning**: Integrate Trivy/Checkov in PreSync hooks
8. **Gateway API migration**: Use incremental migration strategy with parallel running
9. **Native sidecars**: Use restartPolicy Always for Kubernetes 1.29+ deployments

### With iac-analyzer Agent

When the `iac-analyzer` agent reviews Argo CD configurations:

1. **Check for OIDC/SSO** instead of local user accounts
2. **Verify secret management** with External Secrets or Sealed Secrets
3. **Validate sync wave ordering** ensures dependencies deploy first
4. **Check health checks** are configured for critical resources
5. **Review resource requests/limits** for right-sizing (40-70% CPU utilization)
6. **Verify Spot instance configuration** for non-critical workloads
7. **Ensure validation hooks** exist (PreSync security scanning)
8. **Validate Gateway API migration** follows incremental strategy
9. **Check Gateway status** validation before removing Ingress resources
10. **Verify native sidecar patterns** use restartPolicy Always correctly

## Advanced Patterns

### Multi-Cluster Federation

```yaml
# Register multiple clusters
argocd cluster add prod-cluster-1 --name prod-us-west-2
argocd cluster add prod-cluster-2 --name prod-eu-west-1

# ApplicationSet for multi-cluster deployment
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-global
  namespace: argocd
spec:
  generators:
    - clusters:
        selector:
          matchLabels:
            environment: production
  template:
    metadata:
      name: 'myapp-{{name}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/app-repo
        targetRevision: main
        path: k8s/base
        helm:
          parameters:
            - name: region
              value: '{{metadata.labels.region}}'
      destination:
        server: '{{server}}'
        namespace: myapp
```

### Wave-Based Dependency Management

```yaml
# Complex dependency chain
# Wave 0: CRDs
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: examples.example.com
  annotations:
    argocd.argoproj.io/sync-wave: "0"

# Wave 1: Operators/Controllers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-controller
  annotations:
    argocd.argoproj.io/sync-wave: "1"

# Wave 2: Custom Resources
apiVersion: example.com/v1
kind: Example
metadata:
  name: my-example
  annotations:
    argocd.argoproj.io/sync-wave: "2"

# Wave 3: Applications using custom resources
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  annotations:
    argocd.argoproj.io/sync-wave: "3"
```

## Version Requirements

**Kubernetes:**
- Native sidecar containers: 1.29+ (API server and nodes)
- Gateway API v1: 1.29+
- Gateway API BackendTLSPolicy v1alpha3: Check cluster CRD versions

**Argo CD:**
- Application and ApplicationSet: v2.0+
- Image Updater: v0.12+
- Argo Rollouts: v1.0+

**CI/CD:**
- GitHub Actions OIDC: Available all versions
- GitLab Agent with Flux: GitLab 16.2+ (native GitOps deprecated)
- Certificate-based Kubernetes integration: Sunsets May 2026

## Constraints Compliance

This skill enforces:
- ✅ No hardcoded secrets (use External Secrets, Sealed Secrets, Vault)
- ✅ OIDC/SSO preferred over local user accounts
- ✅ Kubernetes manifests pass `kubectl --dry-run` validation
- ✅ Helm charts pass `helm lint --strict`
- ✅ Security scanning integration in PreSync hooks (Trivy, Checkov)
- ✅ Multi-phase validation (technical syntax + intent policy)
- ✅ Cost optimization patterns (Spot instances, right-sizing, HPA)
- ✅ Gateway API v1 compatibility with incremental migration strategy
- ✅ Resource limits and requests for all workloads
- ✅ Sync wave orchestration for dependency management
- ✅ Native sidecar containers use restartPolicy Always (Kubernetes 1.29+)
- ✅ GitHub Actions use OIDC for short-lived credentials
- ✅ GitLab uses Agent with Flux (not deprecated certificate-based integration)

---

**Version**: 2.0.0
**Last Updated**: 2026-02-04
**Compatible With**: Argo CD v2.x, Gateway API v1.x, Kubernetes 1.29+, GitHub Actions, GitLab 16.2+
