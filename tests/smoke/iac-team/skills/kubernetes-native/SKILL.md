---
name: kubernetes-native
description: >
  Kubernetes native resource patterns, Gateway API v1 implementations, native sidecar containers,
  workload best practices, resource optimization, security hardening, and multi-environment deployment strategies.

  Activate when user mentions: Kubernetes manifests, Deployment, StatefulSet, Service, ConfigMap,
  Secret, Gateway API, HTTPRoute, native sidecars, init containers, Pod lifecycle, resource requests/limits,
  HPA (Horizontal Pod Autoscaler), VPA (Vertical Pod Autoscaler), PDB (Pod Disruption Budget),
  RBAC, ServiceAccount, NetworkPolicy, PodSecurityPolicy, SecurityContext, kubeconform validation,
  Kustomize overlays, spot instance tolerations, node affinity, taints and tolerations.

  Use for: Native Kubernetes resource generation, Gateway API v1 migration, lifecycle management,
  security contexts, resource optimization, cost-effective scheduling, multi-environment configurations.

  Do NOT use for: Helm charts (use helm-charts skill), GitOps patterns (use gitops-flux or gitops-argocd skills),
  container image generation (use container-analysis skill), cloud-specific resources (use aws-eks or gcp-gke skills).
---

# Kubernetes Native Skill

## Purpose

Provides patterns and best practices for native Kubernetes resource definitions using YAML manifests. Covers workload resources (Deployments, StatefulSets, Jobs, CronJobs), networking (Services, Gateway API v1), configuration (ConfigMaps, Secrets), security (RBAC, NetworkPolicy, SecurityContext), and operational concerns (autoscaling, resource management, cost optimization). This skill is referenced by the `iac-generator` agent when creating Kubernetes manifests and by `iac-analyzer` when evaluating existing cluster configurations.

## Core Capabilities

### 1. Gateway API v1 Migration and Implementation

**Context (2026)**: Gateway API reached GA (v1.0) in October 2023 and is now the recommended API for ingress traffic management, replacing the legacy Ingress API. Gateway API v1.4 introduced BackendTLSPolicy v1alpha3 for advanced TLS configurations.

#### Migration Strategy

**Phase 1: Parallel Running**
- Deploy Gateway API resources alongside existing Ingress resources
- Test traffic routing through both systems simultaneously
- Validate Gateway Programmed status condition is True before proceeding
- Incremental migration: move services one at a time rather than bulk deletion

**Phase 2: Validation**
- Use `ingress2gateway` tool for automated conversion from Ingress to HTTPRoute
- Verify all services accessible through new Gateway API routes
- Check conformance reports to select appropriate Gateway implementation (Envoy Gateway, NGINX Gateway Fabric, Istio)
- Validate BackendTLSPolicy configurations if using TLS re-encryption

**Phase 3: Cutover**
- Update DNS entries to point to Gateway service
- Monitor traffic metrics during switchover
- Retain Ingress resources for rollback capability
- Delete legacy Ingress resources only after 7-day stability period

#### Gateway API Resource Pattern

```yaml
# Gateway resource (cluster operator responsibility)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: production-gateway
  namespace: gateway-system
spec:
  gatewayClassName: envoy-gateway  # or nginx-gateway-fabric, istio
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      # Redirect HTTP to HTTPS
      allowedRoutes:
        namespaces:
          from: All
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          # Certificate must be in same namespace (cross-namespace not allowed)
          - name: wildcard-tls-cert
            kind: Secret
      allowedRoutes:
        namespaces:
          from: All
---
# HTTPRoute resource (application developer responsibility)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: production
spec:
  parentRefs:
    - name: production-gateway
      namespace: gateway-system
      # Attach to HTTPS listener
      sectionName: https
  hostnames:
    - "app.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /api
      # Traffic splitting for canary deployment (80/20)
      backendRefs:
        - name: app-service-stable
          port: 8080
          weight: 80
        - name: app-service-canary
          port: 8080
          weight: 20
      # Add custom header before forwarding
      filters:
        - type: RequestHeaderModifier
          requestHeaderModifier:
            add:
              - name: X-Environment
                value: production
```

#### BackendTLSPolicy for TLS Re-Encryption

```yaml
# BackendTLSPolicy v1alpha3 (TLS from Gateway to backend)
apiVersion: gateway.networking.k8s.io/v1alpha3
kind: BackendTLSPolicy
metadata:
  name: app-backend-tls
  namespace: production
spec:
  # Single targetRef (core conformance limitation)
  targetRefs:
    - kind: Service
      name: app-service-stable
      group: ""
  validation:
    # Must set either CACertificateRefs OR WellKnownCACertificates (one required)
    caCertificateRefs:
      - name: backend-ca-cert
        kind: ConfigMap
        group: ""
    hostname: app-backend.production.svc.cluster.local
```

**Important Gateway API Notes**:
- **Role separation**: Gateway (cluster operator) vs HTTPRoute (app developer) with RBAC enforcement
- **Cross-namespace certificates**: NOT allowed; cert must be in same namespace as Gateway
- **BackendTLSPolicy status**: Limited representation when targeting multiple Services in HTTPRoutes on same Gateway
- **Conformance reports**: Check implementation-specific features before relying on advanced capabilities
- **Migration tool**: Use `kubectl ingress2gateway` for automated Ingress → HTTPRoute conversion

### 2. Native Sidecar Containers (Kubernetes 1.29+)

**Context (2026)**: Kubernetes 1.29 introduced native sidecar support using `restartPolicy: Always` on init containers, replacing the traditional sidecar pattern that used regular containers.

#### Native Sidecar Pattern

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-sidecar
  namespace: production
spec:
  # Init containers with restartPolicy: Always become native sidecars
  initContainers:
    # Sidecar 1: Logging agent (must be ready before app starts)
    - name: log-forwarder
      image: fluent/fluent-bit:3.0
      restartPolicy: Always  # This makes it a native sidecar
      ports:
        - containerPort: 24224
          protocol: TCP
      # StartupProbe signals when sidecar is operational
      startupProbe:
        httpGet:
          path: /api/v1/health
          port: 2020
        initialDelaySeconds: 5
        periodSeconds: 5
        failureThreshold: 30  # 150s total startup time allowed
      # Readiness probe contributes to Pod readiness
      readinessProbe:
        httpGet:
          path: /api/v1/health
          port: 2020
        periodSeconds: 10
      # Lifecycle hooks for initialization and cleanup
      lifecycle:
        postStart:
          exec:
            command: ["/bin/sh", "-c", "echo 'Sidecar initialized' >> /var/log/sidecar.log"]
        preStop:
          exec:
            command: ["/bin/sh", "-c", "sleep 5 && /fluent-bit/bin/fluent-bit -s"]
      resources:
        requests:
          cpu: 50m
          memory: 64Mi
        limits:
          cpu: 100m
          memory: 128Mi
      volumeMounts:
        - name: logs
          mountPath: /var/log/app

    # Traditional init container (blocks progression)
    - name: init-database-migration
      image: app-migrator:1.0
      # No restartPolicy = traditional init container (default: Never)
      command: ["/app/run-migrations.sh"]

  # Main application containers start after init containers (including sidecars with startupProbe success)
  containers:
    - name: app
      image: app:1.2.3
      ports:
        - containerPort: 8080
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
      resources:
        requests:
          cpu: 250m
          memory: 512Mi
        limits:
          cpu: 500m
          memory: 1Gi

  volumes:
    - name: logs
      emptyDir: {}

  # Termination: Sidecars terminate AFTER main containers in reverse startup order
  terminationGracePeriodSeconds: 60
```

**Native Sidecar Behavior**:
- **Startup**: Sidecars start in init container sequence but DON'T block subsequent containers (once startupProbe succeeds)
- **Readiness**: Sidecar readiness probes contribute to overall Pod readiness
- **Termination**: Sidecars terminate AFTER main containers in REVERSE startup order
- **Job compatibility**: Native sidecars don't prevent Job completion (traditional sidecars would)
- **Version requirement**: Kubernetes 1.29+ (both API server and nodes)

**Use Cases**:
- Logging/metrics agents (Fluent Bit, Datadog, Prometheus exporter)
- Service mesh proxies (Istio, Linkerd)
- Secret rotation agents (external-secrets, vault-agent)
- Configuration sync (consul-template, confd)

### 3. Workload Resource Patterns

#### Deployment (Stateless Applications)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: production
  labels:
    app: frontend
    tier: web
    version: v1.2.3
spec:
  replicas: 3
  revisionHistoryLimit: 10
  # Deployment strategy: RollingUpdate (default) or Recreate
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Allow 1 extra pod during updates
      maxUnavailable: 0  # Maintain full capacity during rollout
  selector:
    matchLabels:
      app: frontend
      tier: web
  template:
    metadata:
      labels:
        app: frontend
        tier: web
        version: v1.2.3
      annotations:
        # Prometheus scraping
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      # SecurityContext at Pod level
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault

      # Service account for RBAC
      serviceAccountName: frontend-sa

      # Topology spread for high availability
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: frontend

      # Cost optimization: Prefer Spot instances (80%), fallback to On-Demand (20%)
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

      # Tolerate Spot instance interruptions
      tolerations:
        - key: "spot"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"

      # Handle Spot interruptions gracefully (2-minute AWS warning)
      terminationGracePeriodSeconds: 120

      containers:
        - name: frontend
          image: frontend:1.2.3
          imagePullPolicy: IfNotPresent

          # SecurityContext at container level
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL

          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
            - name: metrics
              containerPort: 9090
              protocol: TCP

          # Environment variables from ConfigMap and Secret
          env:
            - name: APP_ENV
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: environment
            - name: DATABASE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace

          # Probes for health checking
          startupProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 30  # 150s total startup time

          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 10
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /ready
              port: http
            periodSeconds: 5
            successThreshold: 1
            failureThreshold: 3

          # Lifecycle hooks for graceful shutdown
          lifecycle:
            preStop:
              exec:
                # Delay termination to allow deregistration from load balancer
                command: ["/bin/sh", "-c", "sleep 15 && /app/graceful-shutdown.sh"]

          # Resource requests and limits (right-sized for 40-70% utilization)
          resources:
            requests:
              cpu: 250m      # 0.25 CPU cores (40-70% target)
              memory: 512Mi  # Slightly above average usage
            limits:
              cpu: 500m      # 2x requests for bursts
              memory: 768Mi  # 1.5x requests for spikes

          # Volume mounts (read-only where possible)
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /app/cache
            - name: config
              mountPath: /app/config
              readOnly: true

      # Volumes
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir: {}
        - name: config
          configMap:
            name: app-config
            defaultMode: 0444  # Read-only
```

#### StatefulSet (Stateful Applications)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: database
  namespace: production
spec:
  serviceName: database-headless  # Required for stable network identity
  replicas: 3
  revisionHistoryLimit: 10

  # Pod Management Policy: OrderedReady (default) or Parallel
  podManagementPolicy: OrderedReady

  # Update Strategy: RollingUpdate or OnDelete
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 0  # Update pods with ordinal >= partition

  selector:
    matchLabels:
      app: database

  template:
    metadata:
      labels:
        app: database
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999

      # Anti-affinity for high availability (spread across zones)
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchExpressions:
                  - key: app
                    operator: In
                    values:
                      - database
              topologyKey: topology.kubernetes.io/zone

      containers:
        - name: postgres
          image: postgres:16-alpine

          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL

          ports:
            - name: postgres
              containerPort: 5432

          env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials
                  key: password
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata

          livenessProbe:
            exec:
              command:
                - pg_isready
                - -U
                - postgres
            periodSeconds: 10
            failureThreshold: 3

          readinessProbe:
            exec:
              command:
                - pg_isready
                - -U
                - postgres
            periodSeconds: 5
            failureThreshold: 3

          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi

          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: tmp
              mountPath: /tmp
            - name: run
              mountPath: /var/run/postgresql

      volumes:
        - name: tmp
          emptyDir: {}
        - name: run
          emptyDir: {}

  # VolumeClaimTemplates for persistent storage
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: fast-ssd  # Use SSD for database performance
        resources:
          requests:
            storage: 100Gi
---
# Headless Service for StatefulSet (stable DNS names)
apiVersion: v1
kind: Service
metadata:
  name: database-headless
  namespace: production
spec:
  clusterIP: None  # Headless service
  selector:
    app: database
  ports:
    - name: postgres
      port: 5432
      targetPort: postgres
```

#### Job and CronJob

```yaml
# Job: One-time task execution
apiVersion: batch/v1
kind: Job
metadata:
  name: database-migration
  namespace: production
spec:
  # Parallelism and completions for distributed work
  parallelism: 1
  completions: 1

  # Retry policy
  backoffLimit: 3

  # Time limits
  activeDeadlineSeconds: 600  # 10 minutes max
  ttlSecondsAfterFinished: 86400  # Clean up after 24 hours

  template:
    metadata:
      labels:
        job: database-migration
    spec:
      restartPolicy: OnFailure  # Required for Jobs

      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      # Native sidecar example in Job (doesn't prevent completion)
      initContainers:
        - name: log-sidecar
          image: fluent/fluent-bit:3.0
          restartPolicy: Always  # Native sidecar
          # This sidecar will terminate after main container completes

      containers:
        - name: migrator
          image: app-migrator:1.0

          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL

          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: url

          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi

          volumeMounts:
            - name: tmp
              mountPath: /tmp

      volumes:
        - name: tmp
          emptyDir: {}
---
# CronJob: Scheduled task execution
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
  namespace: production
spec:
  # Schedule: Every day at 2 AM UTC
  schedule: "0 2 * * *"

  # Timezone (Kubernetes 1.27+)
  timeZone: "America/New_York"

  # Concurrency policy: Allow, Forbid, or Replace
  concurrencyPolicy: Forbid

  # History limits
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1

  # Job execution deadline (skip if missed)
  startingDeadlineSeconds: 300

  jobTemplate:
    spec:
      backoffLimit: 2
      ttlSecondsAfterFinished: 86400
      template:
        spec:
          restartPolicy: OnFailure

          securityContext:
            runAsNonRoot: true
            runAsUser: 1000

          containers:
            - name: backup
              image: backup-tool:1.0

              securityContext:
                allowPrivilegeEscalation: false
                capabilities:
                  drop:
                    - ALL

              env:
                - name: AWS_ACCESS_KEY_ID
                  valueFrom:
                    secretKeyRef:
                      name: s3-credentials
                      key: access_key_id
                - name: AWS_SECRET_ACCESS_KEY
                  valueFrom:
                    secretKeyRef:
                      name: s3-credentials
                      key: secret_access_key

              resources:
                requests:
                  cpu: 100m
                  memory: 128Mi
                limits:
                  cpu: 200m
                  memory: 256Mi
```

### 4. Service Networking

```yaml
# ClusterIP Service (internal only)
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: production
  labels:
    app: backend
spec:
  type: ClusterIP  # Default type
  selector:
    app: backend
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 8080
  # Session affinity for stateful connections
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800  # 3 hours
---
# LoadBalancer Service (external access)
apiVersion: v1
kind: Service
metadata:
  name: frontend-lb
  namespace: production
  annotations:
    # AWS-specific annotations
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    # GCP-specific annotations
    cloud.google.com/load-balancer-type: "External"
spec:
  type: LoadBalancer
  selector:
    app: frontend
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 8080
    - name: https
      protocol: TCP
      port: 443
      targetPort: 8443
  # Preserve client source IP
  externalTrafficPolicy: Local
```

### 5. Configuration and Secrets

```yaml
# ConfigMap for non-sensitive configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: production
data:
  # Simple key-value pairs
  environment: "production"
  log_level: "info"
  feature_flags: "feature-a,feature-b"

  # File-like data
  app.yaml: |
    server:
      port: 8080
      timeout: 30s
    database:
      max_connections: 100
      connection_timeout: 5s
---
# Secret for sensitive data (base64 encoded)
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
data:
  # Base64 encoded values (never commit actual secrets!)
  # This is a placeholder - use external-secrets or sealed-secrets in practice
  password: cGxhY2Vob2xkZXI=  # "placeholder"
  url: cG9zdGdyZXNxbDovL3VzZXI6cGFzc0BkYjo1NDMyL2RibmFtZQ==
---
# Secret for Docker registry authentication
apiVersion: v1
kind: Secret
metadata:
  name: docker-registry-secret
  namespace: production
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: eyJhdXRocyI6eyJyZWdpc3RyeS5leGFtcGxlLmNvbSI6eyJ1c2VybmFtZSI6InVzZXIiLCJwYXNzd29yZCI6InBhc3MiLCJhdXRoIjoiZFhObGNqcHdZWE56In19fQ==
```

**Secret Management Best Practices**:
- **NEVER commit actual secrets to Git** - use `.env.example` pattern for documentation
- Use external secret management:
  - **external-secrets-operator**: Sync from AWS Secrets Manager, GCP Secret Manager, Vault
  - **sealed-secrets**: Encrypt secrets for GitOps workflows
  - **SOPS**: Encrypt secrets with Age or AWS KMS
- Use short-lived credentials via IRSA (AWS) or Workload Identity (GCP)
- Rotate secrets regularly using automated tools

### 6. Security Context and RBAC

```yaml
# ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: frontend-sa
  namespace: production
  annotations:
    # AWS IRSA (IAM Roles for Service Accounts)
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/frontend-role
    # GCP Workload Identity
    iam.gke.io/gcp-service-account: frontend@project-id.iam.gserviceaccount.com
---
# Role (namespace-scoped permissions)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: config-reader
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
    # Resource names for fine-grained control
    resourceNames: ["app-config", "db-credentials"]
---
# RoleBinding (grants Role to ServiceAccount)
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: frontend-config-reader
  namespace: production
subjects:
  - kind: ServiceAccount
    name: frontend-sa
    namespace: production
roleRef:
  kind: Role
  name: config-reader
  apiGroup: rbac.authorization.k8s.io
---
# ClusterRole (cluster-wide permissions)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
---
# NetworkPolicy (network segmentation)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-netpol
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow traffic from Gateway
    - from:
        - namespaceSelector:
            matchLabels:
              name: gateway-system
        - podSelector:
            matchLabels:
              app: gateway
      ports:
        - protocol: TCP
          port: 8080
  egress:
    # Allow traffic to backend
    - to:
        - podSelector:
            matchLabels:
              app: backend
      ports:
        - protocol: TCP
          port: 80
    # Allow DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
        - podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

### 7. Autoscaling and Resource Management

```yaml
# Horizontal Pod Autoscaler (HPA v2)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 3
  maxReplicas: 20

  # Scaling metrics
  metrics:
    # CPU-based scaling
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60  # Target 40-70% optimal range

    # Memory-based scaling
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70

    # Custom metrics (requires metrics server)
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"

  # Scaling behavior (fine-grained control)
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
        - type: Percent
          value: 50  # Scale down max 50% at a time
          periodSeconds: 60
        - type: Pods
          value: 2  # Scale down max 2 pods at a time
          periodSeconds: 60
      selectPolicy: Min  # Use most conservative policy
    scaleUp:
      stabilizationWindowSeconds: 0  # Immediate scale up
      policies:
        - type: Percent
          value: 100  # Double capacity if needed
          periodSeconds: 30
        - type: Pods
          value: 4  # Add max 4 pods at a time
          periodSeconds: 30
      selectPolicy: Max  # Use most aggressive policy
---
# Vertical Pod Autoscaler (VPA)
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: backend-vpa
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend

  # Update policy: Off, Initial, Recreate, or Auto
  updatePolicy:
    updateMode: "Auto"

  # Resource policy
  resourcePolicy:
    containerPolicies:
      - containerName: backend
        minAllowed:
          cpu: 100m
          memory: 128Mi
        maxAllowed:
          cpu: 2000m
          memory: 4Gi
        controlledResources: ["cpu", "memory"]
---
# Pod Disruption Budget (PDB)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: frontend-pdb
  namespace: production
spec:
  minAvailable: 2  # OR use maxUnavailable: 1
  selector:
    matchLabels:
      app: frontend
```

### 8. Multi-Environment Configuration with Kustomize

```
# Directory structure
base/
  deployment.yaml
  service.yaml
  configmap.yaml
  kustomization.yaml

overlays/
  staging/
    kustomization.yaml
    patch-deployment.yaml
    configmap.yaml
  production/
    kustomization.yaml
    patch-deployment.yaml
    configmap.yaml
```

**base/kustomization.yaml**:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml

commonLabels:
  app: myapp
  managed-by: kustomize
```

**overlays/staging/kustomization.yaml**:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: staging

bases:
  - ../../base

# Patches for staging environment
patchesStrategicMerge:
  - patch-deployment.yaml

# Replace base ConfigMap with staging-specific version
configMapGenerator:
  - name: app-config
    behavior: replace
    literals:
      - environment=staging
      - log_level=debug
      - replicas=1

# Images
images:
  - name: app
    newName: registry.example.com/app
    newTag: staging-latest

# Common annotations
commonAnnotations:
  environment: staging
```

**overlays/staging/patch-deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 1
  template:
    spec:
      # Staging uses Spot instances for cost savings (70% cheaper)
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: workload-type
                    operator: In
                    values:
                      - spot-optimized

      tolerations:
        - key: "spot"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"

      containers:
        - name: app
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 200m
              memory: 512Mi
```

**overlays/production/kustomization.yaml**:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: production

bases:
  - ../../base

patchesStrategicMerge:
  - patch-deployment.yaml

configMapGenerator:
  - name: app-config
    behavior: replace
    literals:
      - environment=production
      - log_level=warn
      - replicas=5

images:
  - name: app
    newName: registry.example.com/app
    newTag: v1.2.3  # Pinned version for production

commonAnnotations:
  environment: production
```

**overlays/production/patch-deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 5
  template:
    spec:
      # Production uses mix of Spot (80%) and On-Demand (20%)
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

      # Topology spread for high availability
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: myapp

      containers:
        - name: app
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 500m
              memory: 768Mi
```

### 9. Cost Optimization Strategies

#### Spot Instance Configuration

```yaml
# Node pool configuration (infrastructure level)
# This is typically done via cloud provider (EKS, GKE) or Terraform
# Shown here for context of workload configuration

# Workload configuration for Spot instances
apiVersion: apps/v1
kind: Deployment
metadata:
  name: batch-processor
  namespace: production
spec:
  replicas: 10
  template:
    spec:
      # Prefer Spot instances (70% cost savings)
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: workload-type
                    operator: In
                    values:
                      - spot-optimized

      # Tolerate Spot instance taints
      tolerations:
        - key: "spot"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"

      # Handle 2-minute Spot interruption notice
      terminationGracePeriodSeconds: 120

      containers:
        - name: processor
          image: batch-processor:1.0

          # Graceful shutdown on interruption
          lifecycle:
            preStop:
              exec:
                command:
                  - /bin/sh
                  - -c
                  - |
                    # Deregister from load balancer
                    sleep 15
                    # Drain in-flight requests
                    /app/graceful-shutdown.sh
                    # Final cleanup
                    exit 0

          # Right-sized resources (40-70% utilization target)
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi
```

#### Right-Sizing Best Practices

**Resource Request Sizing**:
- **CPU requests**: Set at 40-70% of expected average usage (avoid over-provisioning)
- **Memory requests**: Set slightly above average usage (avoid OOM kills)
- **CPU limits**: Set 1.5-2x requests (allow for bursts)
- **Memory limits**: Set 1.2-1.5x requests (allow for spikes)

**Monitoring and Adjustment**:
```yaml
# Use VPA in "recommend" mode to analyze resource usage
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: app-vpa-recommender
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  updatePolicy:
    updateMode: "Off"  # Recommendation only, don't auto-update
```

#### Non-Production Environment Scheduling

```yaml
# CronJob to scale down staging environment during off-hours
apiVersion: batch/v1
kind: CronJob
metadata:
  name: staging-scaledown
  namespace: kube-system
spec:
  schedule: "0 19 * * 1-5"  # 7 PM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: environment-manager
          restartPolicy: OnFailure
          containers:
            - name: scaledown
              image: bitnami/kubectl:latest
              command:
                - /bin/sh
                - -c
                - |
                  # Scale down all Deployments in staging namespace
                  kubectl scale deployment --all --replicas=0 -n staging
                  # Scale down StatefulSets
                  kubectl scale statefulset --all --replicas=0 -n staging
---
# CronJob to scale up staging environment during business hours
apiVersion: batch/v1
kind: CronJob
metadata:
  name: staging-scaleup
  namespace: kube-system
spec:
  schedule: "0 8 * * 1-5"  # 8 AM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: environment-manager
          restartPolicy: OnFailure
          containers:
            - name: scaleup
              image: bitnami/kubectl:latest
              command:
                - /bin/sh
                - -c
                - |
                  # Restore Deployments to desired state (stored in annotations)
                  kubectl get deployment -n staging -o json | \
                    jq -r '.items[] | "\(.metadata.name) \(.metadata.annotations["original-replicas"] // "1")"' | \
                    while read name replicas; do
                      kubectl scale deployment $name --replicas=$replicas -n staging
                    done
```

### 10. Validation and Security Scanning

#### Technical Validation

```bash
# Validate Kubernetes manifest syntax (client-side dry-run)
kubectl apply --dry-run=client -f deployment.yaml

# Validate against cluster API (server-side dry-run)
kubectl apply --dry-run=server -f deployment.yaml

# Validate Kustomization
kubectl kustomize overlays/production

# Schema validation with kubeconform
kubeconform -summary -output json deployment.yaml

# YAML linting
yamllint -c .yamllint.yml manifests/
```

#### Intent Validation (Policy-as-Code)

```bash
# Security scanning with Trivy (IaC misconfigurations)
trivy config --severity CRITICAL,HIGH manifests/

# Multi-platform scanning with Checkov
checkov --directory manifests/ --framework kubernetes --check CIS_KUBERNETES

# Policy validation with OPA/Conftest
conftest test manifests/ -p policies/

# Kubernetes-specific policy with Kyverno
kyverno apply policies/ --resource manifests/
```

**Example OPA Policy** (require resource limits):
```rego
# policy/resource-limits.rego
package kubernetes.admission

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.limits
  msg = sprintf("Container '%s' must define resource limits", [container.name])
}
```

#### AI Hallucination Detection

When working with AI-generated Kubernetes manifests:

1. **Resource Type Validation**: Ensure all `apiVersion` and `kind` combinations are valid
   ```bash
   kubectl api-resources | grep <resource-type>
   ```

2. **Schema Validation**: Verify field names and types using `kubectl explain`
   ```bash
   kubectl explain Deployment.spec.template.spec.containers
   kubectl explain Gateway.spec.listeners.tls
   ```

3. **Dependency Validation**: Check referenced resources exist
   ```bash
   kubectl get configmap app-config -n production
   kubectl get secret db-credentials -n production
   kubectl get serviceaccount frontend-sa -n production
   ```

4. **Test in Non-Production**: Always apply generated manifests to staging before production

5. **Human Review Required**: Never auto-deploy AI-generated configurations without approval gate

## Security Best Practices

### ✅ Required Security Practices

- **Non-root containers**: Always set `runAsNonRoot: true` and `runAsUser: 1000+`
- **Read-only root filesystem**: Set `readOnlyRootFilesystem: true` where possible
- **Drop capabilities**: Remove all Linux capabilities with `capabilities.drop: [ALL]`
- **No privilege escalation**: Set `allowPrivilegeEscalation: false`
- **Seccomp profile**: Use `seccompProfile.type: RuntimeDefault`
- **Resource limits**: Always define requests and limits for CPU and memory
- **Network policies**: Implement network segmentation with NetworkPolicy
- **RBAC**: Use ServiceAccounts with minimal permissions via Role/RoleBinding
- **Secret management**: Use external-secrets, sealed-secrets, or SOPS (never commit secrets)
- **OIDC authentication**: Use IRSA (AWS) or Workload Identity (GCP) instead of long-lived credentials

### ✅ Validation Commands

```bash
# Validate security context
kubectl get pod <pod-name> -o json | jq '.spec.securityContext'

# Check running containers are non-root
kubectl exec <pod-name> -- id

# Verify resource limits are set
kubectl describe pod <pod-name> | grep -A 5 "Limits:"

# Check RBAC permissions
kubectl auth can-i --list --as=system:serviceaccount:production:frontend-sa

# Validate NetworkPolicy
kubectl describe networkpolicy frontend-netpol -n production

# Test Gateway API resource
kubectl get gateway production-gateway -n gateway-system -o yaml
kubectl get httproute app-route -n production -o yaml
```

## Anti-Patterns to Avoid

### ❌ Common Mistakes

1. **Running as root**:
   ```yaml
   # WRONG: No securityContext, runs as root by default
   spec:
     containers:
       - name: app
         image: app:latest
   ```

   **FIX**: Always specify non-root user:
   ```yaml
   spec:
     securityContext:
       runAsNonRoot: true
       runAsUser: 1000
       fsGroup: 1000
     containers:
       - name: app
         image: app:latest
   ```

2. **No resource limits**:
   ```yaml
   # WRONG: No resource requests or limits
   containers:
     - name: app
       image: app:latest
   ```

   **FIX**: Always define resources:
   ```yaml
   containers:
     - name: app
       image: app:latest
       resources:
         requests:
           cpu: 250m
           memory: 512Mi
         limits:
           cpu: 500m
           memory: 768Mi
   ```

3. **Using latest tag**:
   ```yaml
   # WRONG: Non-deterministic deployments
   image: app:latest
   ```

   **FIX**: Pin specific versions:
   ```yaml
   image: app:1.2.3  # or app@sha256:abc123...
   ```

4. **Hardcoded secrets**:
   ```yaml
   # WRONG: Secrets in plain text
   env:
     - name: DATABASE_PASSWORD
       value: "mysecretpassword"
   ```

   **FIX**: Use Secret references:
   ```yaml
   env:
     - name: DATABASE_PASSWORD
       valueFrom:
         secretKeyRef:
           name: db-credentials
           key: password
   ```

5. **No health checks**:
   ```yaml
   # WRONG: No probes defined
   containers:
     - name: app
       image: app:latest
   ```

   **FIX**: Add startup, liveness, and readiness probes:
   ```yaml
   containers:
     - name: app
       image: app:latest
       startupProbe:
         httpGet:
           path: /healthz
           port: 8080
         initialDelaySeconds: 10
         periodSeconds: 5
         failureThreshold: 30
       livenessProbe:
         httpGet:
           path: /healthz
           port: 8080
         periodSeconds: 10
       readinessProbe:
         httpGet:
           path: /ready
           port: 8080
         periodSeconds: 5
   ```

6. **Ingress instead of Gateway API** (2026 context):
   ```yaml
   # OUTDATED: Legacy Ingress API
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   ```

   **FIX**: Migrate to Gateway API v1:
   ```yaml
   apiVersion: gateway.networking.k8s.io/v1
   kind: Gateway
   # ... + HTTPRoute
   ```

7. **Traditional sidecars in Kubernetes 1.29+**:
   ```yaml
   # OUTDATED: Regular container as sidecar
   containers:
     - name: app
       image: app:latest
     - name: sidecar
       image: sidecar:latest
   ```

   **FIX**: Use native sidecar pattern:
   ```yaml
   initContainers:
     - name: sidecar
       image: sidecar:latest
       restartPolicy: Always  # Native sidecar
   containers:
     - name: app
       image: app:latest
   ```

8. **No graceful shutdown**:
   ```yaml
   # WRONG: No lifecycle hooks, abrupt termination
   containers:
     - name: app
       image: app:latest
   ```

   **FIX**: Add preStop hook:
   ```yaml
   containers:
     - name: app
       image: app:latest
       lifecycle:
         preStop:
           exec:
             command: ["/bin/sh", "-c", "sleep 15 && /app/graceful-shutdown.sh"]
   ```

9. **Cross-namespace certificate references in Gateway API**:
   ```yaml
   # WRONG: Certificate in different namespace
   apiVersion: gateway.networking.k8s.io/v1
   kind: Gateway
   spec:
     listeners:
       - tls:
           certificateRefs:
             - name: cert
               namespace: cert-manager  # NOT ALLOWED
   ```

   **FIX**: Certificate in same namespace as Gateway:
   ```yaml
   spec:
     listeners:
       - tls:
           certificateRefs:
             - name: cert  # Must be in same namespace
   ```

10. **No Pod Disruption Budget for critical workloads**:
    ```yaml
    # WRONG: No PDB, all pods can be evicted during maintenance
    ```

    **FIX**: Define PDB to maintain availability:
    ```yaml
    apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: app-pdb
    spec:
      minAvailable: 2
      selector:
        matchLabels:
          app: myapp
    ```

## Integration with iac-team Agents

### With iac-generator Agent

When the `iac-generator` agent invokes this skill:

1. **Context**: Provide application type (stateless/stateful), scale requirements, environment
2. **Security**: Apply SPEC.md constraints (non-root, resource limits, RBAC)
3. **Optimization**: Include cost optimization patterns (Spot instances, right-sizing)
4. **Gateway API**: Use v1 Gateway API for ingress (not legacy Ingress)
5. **Native sidecars**: Use Kubernetes 1.29+ pattern with `restartPolicy: Always`
6. **Validation**: Ensure manifests pass `kubectl --dry-run` and security scanning

### With iac-analyzer Agent

When `iac-analyzer` detects Kubernetes resources:

1. Identify resource types and relationships (Deployment → Service → Gateway)
2. Analyze security posture (SecurityContext, RBAC, NetworkPolicy)
3. Detect optimization opportunities (missing HPA, over-provisioned resources)
4. Flag outdated patterns (Ingress API, traditional sidecars)
5. Recommend right-sizing based on resource usage
6. Validate against Gateway API v1 compatibility

## Best Practices Summary

1. **Always use Gateway API v1** for ingress (not legacy Ingress)
2. **Implement native sidecars** with `restartPolicy: Always` on init containers (Kubernetes 1.29+)
3. **Run as non-root** with read-only root filesystem and dropped capabilities
4. **Define resource requests and limits** targeting 40-70% CPU utilization
5. **Use HPA for horizontal scaling** and VPA for right-sizing recommendations
6. **Implement PDB** for critical workloads to maintain availability during disruptions
7. **Add health checks** (startup, liveness, readiness) for all containers
8. **Use external secret management** (external-secrets, sealed-secrets, SOPS)
9. **Apply NetworkPolicy** for network segmentation and zero-trust networking
10. **Leverage Spot instances** for cost optimization (70% savings) with proper interruption handling
11. **Validate with multi-phase pipeline** (technical + intent validation)
12. **Test in non-production first** before deploying AI-generated manifests
13. **Use Kustomize overlays** for multi-environment configuration management
14. **Implement graceful shutdown** with preStop hooks and terminationGracePeriodSeconds
15. **Monitor and adjust** resource allocations quarterly using VPA recommendations

## References

For comprehensive patterns and advanced techniques, see:

- **Gateway API**: https://gateway-api.sigs.k8s.io/
- **Gateway API v1 GA**: https://kubernetes.io/blog/2023/10/31/gateway-api-ga/
- **Gateway API v1.4**: https://kubernetes.io/blog/2025/11/06/gateway-api-v1-4/
- **Native Sidecar Containers**: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/
- **Sidecar KEP**: https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/753-sidecar-containers/README.md
- **Kubernetes Best Practices**: https://kubernetes.io/docs/concepts/configuration/overview/
- **Pod Security Standards**: https://kubernetes.io/docs/concepts/security/pod-security-standards/
- **Autoscaling**: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- **Kustomize**: https://kustomize.io/
- **kubeconform**: https://github.com/yannh/kubeconform
- **Trivy**: https://trivy.dev/
- **Checkov**: https://www.checkov.io/
- **OPA/Conftest**: https://www.conftest.dev/

---

**Version**: 1.0.0
**Last Updated**: 2026-02-03
**Compatible With**: Kubernetes 1.29+, Gateway API v1.x

*This skill is part of the iac-team plugin. For related capabilities, see: container-analysis (Dockerfiles), gitops-flux (GitOps patterns), helm-charts (Helm templates), terraform-modules (infrastructure provisioning), aws-eks (AWS specifics), gcp-gke (GCP specifics).*
