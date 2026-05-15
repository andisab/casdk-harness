---
name: helm-charts
description: >
  Helm chart development patterns, template best practices, values schema validation,
  chart testing, OCI registry publishing, library charts, Helmfile orchestration,
  security hardening, and multi-environment deployment strategies.

  Activate when user mentions: Helm, Helm chart, values.yaml, Chart.yaml, helm template,
  helm install, helm upgrade, helm lint, helm test, Helmfile, chart dependencies,
  subchart, umbrella chart, library chart, OCI registry, helm hooks, chart museum,
  values schema, values.schema.json, chart testing, ct lint, helm package, helm push,
  chart signing, provenance, Sigstore, cosign, helm secrets, helm diff.

  Use for: Generating Helm charts, chart templates, values files, schema validation,
  chart testing patterns, multi-environment value overlays, Helmfile orchestration,
  library chart patterns, OCI registry workflows, chart security and signing,
  umbrella chart composition, hook lifecycle management.

  Do NOT use for: Raw Kubernetes manifests (use kubernetes-native skill), Kustomize overlays
  (use kubernetes-native skill), GitOps deployment patterns (use gitops-argocd or gitops-flux skills),
  Terraform Helm provider configuration (use terraform-modules skill).
---

# Helm Charts Skill

## Purpose

Provides Helm 3.x chart development patterns, template best practices, and production-ready chart generation for the iac-generator agent. This skill covers the full chart lifecycle from scaffolding through testing, signing, and publishing to OCI registries, with security-first defaults and multi-environment deployment strategies. Referenced by the `iac-generator` agent when creating Helm-based Kubernetes packaging and by `iac-analyzer` when evaluating existing chart quality.

## Core Capabilities

### 1. Chart Structure and Scaffolding

Generate well-organized Helm charts following the standard directory layout:

- **Chart.yaml**: Metadata, versioning, dependencies, maintainers, and annotations
- **values.yaml**: Sensible defaults with security-first configuration
- **values.schema.json**: JSON Schema validation for values input
- **templates/**: Kubernetes resource templates with helper functions
- **charts/**: Subcharts and dependencies
- **crds/**: Custom Resource Definitions (installed before templates)
- **tests/**: Helm test pods for post-deployment validation

**Standard Chart Layout**:
```
mychart/
├── Chart.yaml                # Chart metadata and dependencies
├── Chart.lock                # Locked dependency versions
├── values.yaml               # Default values (security-first)
├── values.schema.json        # JSON Schema for values validation
├── .helmignore               # Files to exclude from packaging
├── README.md                 # Chart documentation
├── LICENSE                   # License file
├── templates/
│   ├── _helpers.tpl          # Named template definitions
│   ├── deployment.yaml       # Deployment resource
│   ├── service.yaml          # Service resource
│   ├── serviceaccount.yaml   # ServiceAccount with annotations
│   ├── configmap.yaml        # ConfigMap for non-sensitive config
│   ├── secret.yaml           # Secret references (never hardcoded)
│   ├── hpa.yaml              # HorizontalPodAutoscaler
│   ├── pdb.yaml              # PodDisruptionBudget
│   ├── networkpolicy.yaml    # NetworkPolicy for segmentation
│   ├── ingress.yaml          # Gateway API HTTPRoute (preferred) or Ingress
│   ├── NOTES.txt             # Post-install usage instructions
│   └── tests/
│       └── test-connection.yaml  # Helm test pod
├── charts/                   # Subchart dependencies
└── ci/
    ├── ct.yaml               # chart-testing configuration
    ├── lint-values.yaml      # Values for linting
    └── test-values.yaml      # Values for testing
```

### 2. Chart.yaml Best Practices

Define chart metadata with proper versioning and dependency management:

- **SemVer Versioning**: Strict semantic versioning for `version` and `appVersion`
- **Dependency Pinning**: Pin subchart versions with `~` or exact versions
- **Annotations**: Document chart capabilities, category, and minimum Kubernetes version
- **Maintainers**: Include team contact information for ownership tracking

### 3. Template Functions and Pipelines

Generate templates using Helm's template engine effectively:

- **Named Templates**: Reusable `define`/`include` blocks in `_helpers.tpl`
- **Pipeline Chaining**: Combine functions with `|` for transformations
- **Required Values**: Use `required` to fail fast on missing critical values
- **Default Values**: Use `default` for optional fields with fallbacks
- **tpl Function**: Render user-supplied strings as templates
- **Lookup Function**: Query cluster state during rendering (use cautiously)
- **Flow Control**: `if/else`, `range`, `with` for conditional rendering

### 4. Values Schema Validation

Enforce input validation with `values.schema.json`:

- **Type Enforcement**: Prevent string/int/bool type mismatches
- **Required Fields**: Mark mandatory values to catch missing configuration early
- **Enum Constraints**: Restrict values to valid options
- **Pattern Matching**: Validate formats (DNS names, image references, resource quantities)
- **Composition**: Use `$ref` for reusable schema definitions

### 5. Chart Testing

Validate charts across the development lifecycle:

- **helm lint --strict**: Syntax and best practice validation
- **helm template**: Render templates locally for inspection
- **helm test**: Post-deployment validation with test pods
- **chart-testing (ct)**: CI-focused chart validation and upgrade testing
- **kubeconform**: Schema validation of rendered templates
- **Trivy config**: Security scanning of chart templates

### 6. OCI Registry and Distribution

Publish and consume charts via OCI-compliant registries:

- **helm push/pull**: Native OCI artifact support (Helm 3.8+)
- **Registry Authentication**: OIDC-based auth for CI/CD workflows
- **Chart Signing**: Sigstore cosign for provenance verification
- **Multi-Registry**: Push to ECR, GAR, GHCR, Docker Hub
- **Immutable Tags**: Never overwrite published chart versions

## Chart.yaml Patterns

### Application Chart

```yaml
apiVersion: v2
name: myapp
description: A production-ready microservice chart
type: application
version: 1.2.0
appVersion: "3.4.5"

# Kubernetes version constraint
kubeVersion: ">=1.28.0-0"

# Maintainers for ownership tracking
maintainers:
  - name: Platform Team
    email: platform@example.com
    url: https://github.com/orgs/example/teams/platform

# Chart annotations for discovery and documentation
annotations:
  category: application
  artifacthub.io/license: MIT
  artifacthub.io/prerelease: "false"
  artifacthub.io/signKey: |
    fingerprint: ABC123DEF456...
    url: https://example.com/pgp-key.asc

# Home and source URLs
home: https://github.com/example/myapp
sources:
  - https://github.com/example/myapp
icon: https://example.com/icons/myapp.png

keywords:
  - microservice
  - api
  - backend

# Dependencies with version constraints
dependencies:
  - name: postgresql
    version: "~15.5.0"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    condition: postgresql.enabled
    alias: db

  - name: redis
    version: "~19.0.0"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    condition: redis.enabled

  - name: common
    version: "~2.0.0"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    tags:
      - bitnami-common
```

### Library Chart

```yaml
apiVersion: v2
name: common-lib
description: Shared template library for standardized resource generation
type: library
version: 1.0.0

# Library charts have no appVersion (they produce no resources directly)
# They are consumed by other charts via dependencies

maintainers:
  - name: Platform Team
    email: platform@example.com
```

## Values.yaml Patterns

### Security-First Defaults

```yaml
# values.yaml - Production-ready defaults with security hardening

# -- Number of replicas (overridden by HPA when enabled)
replicaCount: 2

image:
  # -- Container image repository
  repository: registry.example.com/myapp
  # -- Image pull policy
  pullPolicy: IfNotPresent
  # -- Image tag (defaults to Chart appVersion)
  tag: ""

# -- Image pull secrets for private registries
imagePullSecrets: []

# -- Override chart name
nameOverride: ""
# -- Override full release name
fullnameOverride: ""

serviceAccount:
  # -- Create a ServiceAccount
  create: true
  # -- ServiceAccount annotations (e.g., IRSA, Workload Identity)
  annotations: {}
    # eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/myapp
    # iam.gke.io/gcp-service-account: myapp@project.iam.gserviceaccount.com
  # -- ServiceAccount name (generated if not set)
  name: ""
  # -- Automount API credentials
  automountServiceAccountToken: false

# Security context at Pod level
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

# Security context at container level
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop:
      - ALL

service:
  # -- Service type
  type: ClusterIP
  # -- Service port
  port: 80
  # -- Container target port
  targetPort: 8080

ingress:
  # -- Enable ingress (Gateway API HTTPRoute preferred for new deployments)
  enabled: false
  # -- Ingress class name
  className: ""
  annotations: {}
  hosts:
    - host: chart-example.local
      paths:
        - path: /
          pathType: Prefix
  tls: []

# Gateway API (preferred over Ingress for Kubernetes 1.28+)
gatewayApi:
  # -- Enable Gateway API HTTPRoute
  enabled: false
  # -- Parent Gateway reference
  parentRefs:
    - name: production-gateway
      namespace: gateway-system
      sectionName: https
  # -- Hostnames for the HTTPRoute
  hostnames: []
  # -- HTTPRoute rules
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs: []

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  # -- Enable Horizontal Pod Autoscaler
  enabled: true
  # -- Minimum replicas
  minReplicas: 2
  # -- Maximum replicas
  maxReplicas: 10
  # -- Target CPU utilization (40-70% optimal)
  targetCPUUtilizationPercentage: 60
  # -- Target memory utilization
  targetMemoryUtilizationPercentage: 70

podDisruptionBudget:
  # -- Enable PDB for availability during disruptions
  enabled: true
  # -- Minimum available pods
  minAvailable: 1
  # maxUnavailable: 1  # Alternative to minAvailable

networkPolicy:
  # -- Enable NetworkPolicy for network segmentation
  enabled: true
  # -- Ingress rules (default: allow from same namespace)
  ingress: []
  # -- Egress rules (default: allow DNS + same namespace)
  egress: []

# Health check configuration
probes:
  startup:
    enabled: true
    httpGet:
      path: /healthz
      port: http
    initialDelaySeconds: 10
    periodSeconds: 5
    failureThreshold: 30
  liveness:
    enabled: true
    httpGet:
      path: /healthz
      port: http
    periodSeconds: 10
    failureThreshold: 3
  readiness:
    enabled: true
    httpGet:
      path: /ready
      port: http
    periodSeconds: 5
    failureThreshold: 3

# Environment variables from ConfigMap and Secret references
env: []
  # - name: DATABASE_URL
  #   valueFrom:
  #     secretKeyRef:
  #       name: db-credentials
  #       key: url

# Extra environment variables from ConfigMaps or Secrets
envFrom: []
  # - configMapRef:
  #     name: app-config
  # - secretRef:
  #     name: app-secrets

# -- Extra volume mounts
extraVolumeMounts:
  - name: tmp
    mountPath: /tmp
  - name: cache
    mountPath: /app/cache

# -- Extra volumes
extraVolumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}

# -- Node selector
nodeSelector: {}

# -- Tolerations (e.g., for Spot instances)
tolerations: []
  # - key: "spot"
  #   operator: "Equal"
  #   value: "true"
  #   effect: "NoSchedule"

# -- Pod anti-affinity and topology spread
affinity: {}

# -- Topology spread constraints for high availability
topologySpreadConstraints: []
  # - maxSkew: 1
  #   topologyKey: topology.kubernetes.io/zone
  #   whenUnsatisfiable: DoNotSchedule

# -- Pod annotations (e.g., Prometheus scraping)
podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9090"
  prometheus.io/path: "/metrics"

# Subchart toggles
postgresql:
  enabled: false

redis:
  enabled: false
```

## Values Schema Validation

### values.schema.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["image", "service"],
  "properties": {
    "replicaCount": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100,
      "description": "Number of pod replicas"
    },
    "image": {
      "type": "object",
      "required": ["repository"],
      "properties": {
        "repository": {
          "type": "string",
          "pattern": "^[a-z0-9][a-z0-9._/-]*$",
          "description": "Container image repository"
        },
        "pullPolicy": {
          "type": "string",
          "enum": ["Always", "IfNotPresent", "Never"],
          "default": "IfNotPresent"
        },
        "tag": {
          "type": "string",
          "description": "Image tag (defaults to appVersion)"
        }
      }
    },
    "service": {
      "type": "object",
      "required": ["port"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
          "default": "ClusterIP"
        },
        "port": {
          "type": "integer",
          "minimum": 1,
          "maximum": 65535
        },
        "targetPort": {
          "type": "integer",
          "minimum": 1,
          "maximum": 65535
        }
      }
    },
    "resources": {
      "$ref": "#/$defs/resources"
    },
    "autoscaling": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "minReplicas": {
          "type": "integer",
          "minimum": 1
        },
        "maxReplicas": {
          "type": "integer",
          "minimum": 1
        },
        "targetCPUUtilizationPercentage": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100
        }
      }
    },
    "securityContext": {
      "type": "object",
      "properties": {
        "runAsNonRoot": {
          "type": "boolean",
          "const": true,
          "description": "Must run as non-root (enforced)"
        },
        "allowPrivilegeEscalation": {
          "type": "boolean",
          "const": false,
          "description": "Privilege escalation must be disabled (enforced)"
        }
      }
    }
  },
  "$defs": {
    "resources": {
      "type": "object",
      "properties": {
        "requests": {
          "type": "object",
          "properties": {
            "cpu": { "type": "string", "pattern": "^[0-9]+m?$" },
            "memory": { "type": "string", "pattern": "^[0-9]+(Mi|Gi)$" }
          }
        },
        "limits": {
          "type": "object",
          "properties": {
            "cpu": { "type": "string", "pattern": "^[0-9]+m?$" },
            "memory": { "type": "string", "pattern": "^[0-9]+(Mi|Gi)$" }
          }
        }
      }
    }
  }
}
```

**Schema validation runs automatically** during `helm install`, `helm upgrade`, and `helm lint`. Any values that violate the schema produce a clear error message before rendering templates.

## Template Patterns

### _helpers.tpl (Named Templates)

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "mychart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars because some Kubernetes name fields are limited to this.
*/}}
{{- define "mychart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "mychart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "mychart.labels" -}}
helm.sh/chart: {{ include "mychart.chart" . }}
{{ include "mychart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Chart.Name }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "mychart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mychart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "mychart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "mychart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the image reference with tag defaulting to appVersion
*/}}
{{- define "mychart.image" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end }}

{{/*
Render a value that may contain template expressions.
Usage: {{ include "mychart.tplValue" (dict "value" .Values.someField "context" $) }}
*/}}
{{- define "mychart.tplValue" -}}
{{- if typeIs "string" .value }}
{{- tpl .value .context }}
{{- else }}
{{- tpl (.value | toYaml) .context }}
{{- end }}
{{- end }}
```

### Deployment Template

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
  {{- with .Values.deploymentAnnotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  revisionHistoryLimit: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      {{- include "mychart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        # Force rollout on ConfigMap changes
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        {{- with .Values.podAnnotations }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
      labels:
        {{- include "mychart.labels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "mychart.serviceAccountName" . }}
      automountServiceAccountToken: {{ .Values.serviceAccount.automountServiceAccountToken | default false }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      {{- with .Values.topologySpreadConstraints }}
      topologySpreadConstraints:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: {{ include "mychart.image" . | quote }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.targetPort | default 8080 }}
              protocol: TCP
            {{- if (index .Values.podAnnotations "prometheus.io/scrape") }}
            - name: metrics
              containerPort: {{ index .Values.podAnnotations "prometheus.io/port" | default "9090" | int }}
              protocol: TCP
            {{- end }}
          {{- with .Values.env }}
          env:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with .Values.envFrom }}
          envFrom:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- if .Values.probes.startup.enabled }}
          startupProbe:
            {{- omit .Values.probes.startup "enabled" | toYaml | nindent 12 }}
          {{- end }}
          {{- if .Values.probes.liveness.enabled }}
          livenessProbe:
            {{- omit .Values.probes.liveness "enabled" | toYaml | nindent 12 }}
          {{- end }}
          {{- if .Values.probes.readiness.enabled }}
          readinessProbe:
            {{- omit .Values.probes.readiness "enabled" | toYaml | nindent 12 }}
          {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- with .Values.extraVolumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
      {{- with .Values.extraVolumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      terminationGracePeriodSeconds: 60
```

### Service Template

```yaml
# templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
  {{- with .Values.service.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "mychart.selectorLabels" . | nindent 4 }}
```

### NetworkPolicy Template

```yaml
# templates/networkpolicy.yaml
{{- if .Values.networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "mychart.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow traffic from same namespace by default
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: {{ .Values.service.targetPort | default 8080 }}
    {{- with .Values.networkPolicy.ingress }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
  egress:
    # Allow DNS resolution
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    # Allow traffic within same namespace
    - to:
        - podSelector: {}
    {{- with .Values.networkPolicy.egress }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
{{- end }}
```

### HPA Template

```yaml
# templates/hpa.yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "mychart.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
      selectPolicy: Min
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
      selectPolicy: Max
{{- end }}
```

### ServiceAccount Template with OIDC Annotations

```yaml
# templates/serviceaccount.yaml
{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "mychart.serviceAccountName" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
automountServiceAccountToken: {{ .Values.serviceAccount.automountServiceAccountToken | default false }}
{{- end }}
```

### Helm Test Pod

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "mychart.fullname" . }}-test-connection"
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
    - name: wget
      image: busybox:1.36
      command: ['wget']
      args: ['{{ include "mychart.fullname" . }}:{{ .Values.service.port }}/healthz', '-q', '-O', '-', '--timeout=5']
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      resources:
        limits:
          cpu: 50m
          memory: 32Mi
  restartPolicy: Never
```

### NOTES.txt Post-Install Instructions

```yaml
# templates/NOTES.txt
1. Get the application URL by running:
{{- if .Values.ingress.enabled }}
{{- range $host := .Values.ingress.hosts }}
  http{{ if $.Values.ingress.tls }}s{{ end }}://{{ $host.host }}{{ (first $host.paths).path }}
{{- end }}
{{- else if .Values.gatewayApi.enabled }}
  Your application is exposed via Gateway API HTTPRoute.
  Check route status: kubectl get httproute {{ include "mychart.fullname" . }} -n {{ .Release.Namespace }}
{{- else if contains "NodePort" .Values.service.type }}
  export NODE_PORT=$(kubectl get --namespace {{ .Release.Namespace }} -o jsonpath="{.spec.ports[0].nodePort}" services {{ include "mychart.fullname" . }})
  export NODE_IP=$(kubectl get nodes --namespace {{ .Release.Namespace }} -o jsonpath="{.items[0].status.addresses[0].address}")
  echo http://$NODE_IP:$NODE_PORT
{{- else if contains "LoadBalancer" .Values.service.type }}
  NOTE: It may take a few minutes for the LoadBalancer IP to be available.
  kubectl get --namespace {{ .Release.Namespace }} svc {{ include "mychart.fullname" . }} -w
{{- else if contains "ClusterIP" .Values.service.type }}
  kubectl port-forward --namespace {{ .Release.Namespace }} svc/{{ include "mychart.fullname" . }} 8080:{{ .Values.service.port }}
  echo "Visit http://127.0.0.1:8080"
{{- end }}

2. Run helm tests:
  helm test {{ .Release.Name }} -n {{ .Release.Namespace }}
```

## Helm Hooks

### Hook Lifecycle Management

```yaml
# templates/hooks/pre-install-migration.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "mychart.fullname" . }}-migration
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  backoffLimit: 3
  activeDeadlineSeconds: 300
  ttlSecondsAfterFinished: 600
  template:
    metadata:
      labels:
        {{- include "mychart.selectorLabels" . | nindent 8 }}
    spec:
      restartPolicy: OnFailure
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: migration
          image: {{ include "mychart.image" . | quote }}
          command: ["/app/migrate.sh"]
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "mychart.fullname" . }}-db
                  key: url
          resources:
            limits:
              cpu: 200m
              memory: 256Mi
```

**Hook Types and Ordering**:

| Hook | Timing | Use Case |
|------|--------|----------|
| `pre-install` | Before resources created | DB migration, secret seeding |
| `post-install` | After resources created | Notification, smoke test |
| `pre-upgrade` | Before upgrade | Schema migration, backup |
| `post-upgrade` | After upgrade | Cache warmup, notification |
| `pre-delete` | Before uninstall | Data backup, deregistration |
| `post-delete` | After uninstall | Cleanup external resources |
| `pre-rollback` | Before rollback | Backup current state |
| `post-rollback` | After rollback | Notification |
| `test` | On `helm test` | Post-deploy validation |

**Hook Weight**: Lower values execute first. Use `-10` to `10` for ordering.

**Delete Policies**:
- `before-hook-creation`: Delete previous hook before creating new one
- `hook-succeeded`: Delete after successful execution
- `hook-failed`: Delete after failed execution

## Chart Dependencies and Subcharts

### Managing Dependencies

```bash
# Add dependency repositories and update lockfile
helm dependency update ./mychart

# Verify dependencies are resolved
helm dependency list ./mychart
```

### Subchart Value Overrides

```yaml
# Parent chart values.yaml overrides subchart values
postgresql:
  enabled: true
  auth:
    postgresPassword: "" # Set via --set or secret reference at deploy time
    database: myapp
  primary:
    persistence:
      enabled: true
      size: 20Gi
      storageClass: "gp3"
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 500m
        memory: 1Gi

redis:
  enabled: true
  auth:
    enabled: true
    password: "" # Set via --set or secret reference at deploy time
  master:
    persistence:
      enabled: false
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
```

### Conditional Subchart Rendering

```yaml
# In parent values.yaml
postgresql:
  enabled: true  # Toggle subchart on/off

# In templates, reference subchart outputs
{{- if .Values.postgresql.enabled }}
env:
  - name: DATABASE_HOST
    value: {{ printf "%s-postgresql" (include "mychart.fullname" .) }}
  - name: DATABASE_PORT
    value: "5432"
{{- end }}
```

## Library Charts

### Creating a Library Chart

Library charts contain only named templates (no rendered resources). They provide standardized helpers across multiple application charts.

```yaml
# common-lib/templates/_labels.tpl
{{- define "common.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "common.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

```yaml
# common-lib/templates/_security.tpl
{{- define "common.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "common.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
runAsUser: 1000
capabilities:
  drop:
    - ALL
{{- end }}
```

### Consuming a Library Chart

```yaml
# Application Chart.yaml
dependencies:
  - name: common-lib
    version: "1.0.0"
    repository: "oci://registry.example.com/charts"

# In application templates
spec:
  template:
    spec:
      securityContext:
        {{- include "common.podSecurityContext" . | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- include "common.containerSecurityContext" . | nindent 12 }}
```

## Umbrella Charts and Monorepo Patterns

### Umbrella Chart Structure

```
platform/
├── Chart.yaml              # type: application
├── values.yaml             # Global overrides
├── values-dev.yaml         # Dev environment
├── values-staging.yaml     # Staging environment
├── values-prod.yaml        # Production environment
├── charts/
│   ├── frontend/           # Local subchart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   ├── backend/            # Local subchart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   └── worker/             # Local subchart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
└── templates/
    └── _helpers.tpl        # Shared helpers across subcharts
```

### Umbrella Chart.yaml

```yaml
apiVersion: v2
name: platform
description: Umbrella chart for the full application platform
type: application
version: 2.0.0

dependencies:
  - name: frontend
    version: "1.x.x"
    repository: "file://./charts/frontend"
    condition: frontend.enabled

  - name: backend
    version: "1.x.x"
    repository: "file://./charts/backend"
    condition: backend.enabled

  - name: worker
    version: "1.x.x"
    repository: "file://./charts/worker"
    condition: worker.enabled

  # External dependency from OCI registry
  - name: postgresql
    version: "~15.5.0"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    condition: postgresql.enabled
```

### Global Values Pattern

```yaml
# Umbrella chart values.yaml
global:
  # Shared values accessible by all subcharts via .Values.global
  imageRegistry: registry.example.com
  imagePullSecrets:
    - name: registry-credentials
  storageClass: gp3

frontend:
  enabled: true
  replicaCount: 3
  image:
    repository: "{{ .Values.global.imageRegistry }}/frontend"
    tag: "1.5.0"

backend:
  enabled: true
  replicaCount: 2
  image:
    repository: "{{ .Values.global.imageRegistry }}/backend"
    tag: "2.1.0"

worker:
  enabled: true
  replicaCount: 1
```

## Security Best Practices

### No Hardcoded Secrets

**REQUIRED**: Charts must never contain hardcoded secrets in `values.yaml` or templates.

```yaml
# values.yaml - CORRECT: Empty defaults with documentation
postgresql:
  auth:
    postgresPassword: ""  # REQUIRED: Set via --set or external secret
    # Use: helm install myapp ./mychart --set postgresql.auth.postgresPassword=$DB_PASS
    # Or: Use external-secrets-operator to sync from AWS Secrets Manager / GCP Secret Manager
```

```yaml
# templates/secret.yaml - CORRECT: Reference external values only
{{- if .Values.existingSecret }}
# Use existing Secret (created by external-secrets-operator or sealed-secrets)
{{- else }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
type: Opaque
data:
  {{- range $key, $val := .Values.secrets }}
  {{ $key }}: {{ $val | b64enc | quote }}
  {{- end }}
{{- end }}
```

```yaml
# BAD: Hardcoded secrets in values.yaml
# postgresql:
#   auth:
#     postgresPassword: "my-secret-password"  # NEVER DO THIS
```

### OIDC for CI/CD Authentication

```bash
# GitHub Actions: Authenticate to OCI registry with OIDC
- name: Login to ECR
  uses: aws-actions/amazon-ecr-login@v2

- name: Push Helm chart to ECR
  run: |
    helm push mychart-1.0.0.tgz oci://${{ env.ECR_REGISTRY }}/charts

# GCP: Authenticate with Workload Identity
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/123/locations/global/workloadIdentityPools/github/providers/github
    service_account: helm-publisher@project.iam.gserviceaccount.com

- name: Push to Artifact Registry
  run: |
    helm push mychart-1.0.0.tgz oci://us-docker.pkg.dev/project/charts
```

### Chart Signing with Sigstore/Cosign

```bash
# Sign chart OCI artifact after pushing
cosign sign --yes \
  oci://registry.example.com/charts/mychart:1.0.0

# Verify chart signature before installation
cosign verify \
  --certificate-identity-regexp=".*@example.com" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  oci://registry.example.com/charts/mychart:1.0.0

# Helm provenance file (legacy GPG signing)
helm package --sign --key "Platform Team" --keyring ~/.gnupg/secring.gpg mychart/
helm verify mychart-1.0.0.tgz
```

### Security Scanning of Charts

```bash
# Scan rendered templates for misconfigurations
helm template myrelease ./mychart -f values-prod.yaml | trivy config --severity CRITICAL,HIGH -

# Scan chart directory directly
trivy config ./mychart --severity CRITICAL,HIGH

# Validate no secrets in chart source
trivy fs ./mychart --scanners secret --severity CRITICAL,HIGH
```

## Multi-Environment Strategy

### Value Overlay Pattern

```
mychart/
├── values.yaml              # Base defaults (security-first)
├── values-dev.yaml          # Dev overrides
├── values-staging.yaml      # Staging overrides
└── values-prod.yaml         # Production overrides
```

**values-dev.yaml**:
```yaml
replicaCount: 1

resources:
  requests:
    cpu: 50m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi

autoscaling:
  enabled: false

# Use Spot instances for cost savings (70% cheaper)
tolerations:
  - key: "spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"

nodeSelector:
  workload-type: spot-optimized

# Reduced health check thresholds for faster iteration
probes:
  startup:
    enabled: true
    httpGet:
      path: /healthz
      port: http
    initialDelaySeconds: 5
    periodSeconds: 3
    failureThreshold: 10
```

**values-staging.yaml**:
```yaml
replicaCount: 2

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 60

# Mix of Spot and On-Demand
tolerations:
  - key: "spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

**values-prod.yaml**:
```yaml
replicaCount: 3

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 60

podDisruptionBudget:
  enabled: true
  minAvailable: 2

topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: myapp

# Production: mix Spot (80%) and On-Demand (20%)
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
```

**Deployment commands**:
```bash
# Deploy to each environment with overlay
helm upgrade --install myapp ./mychart -f values-dev.yaml -n dev
helm upgrade --install myapp ./mychart -f values-staging.yaml -n staging
helm upgrade --install myapp ./mychart -f values-prod.yaml -n production
```

## Helmfile Orchestration

### Helmfile for Multi-Chart Deployments

```yaml
# helmfile.yaml
repositories:
  - name: bitnami
    url: registry-1.docker.io/bitnamicharts
    oci: true

  - name: ingress-nginx
    url: https://kubernetes.github.io/ingress-nginx

environments:
  dev:
    values:
      - environments/dev/values.yaml
    kubeContext: dev-cluster
  staging:
    values:
      - environments/staging/values.yaml
    kubeContext: staging-cluster
  production:
    values:
      - environments/production/values.yaml
    kubeContext: production-cluster

---

helmDefaults:
  wait: true
  timeout: 300
  createNamespace: true
  cleanupOnFail: true

releases:
  # Infrastructure components first
  - name: cert-manager
    namespace: cert-manager
    chart: jetstack/cert-manager
    version: "1.14.x"
    values:
      - installCRDs: true

  # Application stack
  - name: backend
    namespace: {{ .Environment.Name }}
    chart: ./charts/backend
    values:
      - ./charts/backend/values.yaml
      - ./charts/backend/values-{{ .Environment.Name }}.yaml
    needs:
      - cert-manager/cert-manager
    set:
      - name: image.tag
        value: {{ requiredEnv "BACKEND_TAG" }}

  - name: frontend
    namespace: {{ .Environment.Name }}
    chart: ./charts/frontend
    values:
      - ./charts/frontend/values.yaml
      - ./charts/frontend/values-{{ .Environment.Name }}.yaml
    needs:
      - {{ .Environment.Name }}/backend
    set:
      - name: image.tag
        value: {{ requiredEnv "FRONTEND_TAG" }}
```

**Helmfile Commands**:
```bash
# Diff before applying (requires helm-diff plugin)
helmfile -e production diff

# Apply to specific environment
helmfile -e production apply

# Sync all releases
helmfile -e staging sync

# Destroy all releases
helmfile -e dev destroy

# Apply only specific releases
helmfile -e production -l name=backend apply
```

## Cost Optimization

### Resource Right-Sizing

```yaml
# Target 40-70% CPU utilization
# Use VPA in recommendation mode to find optimal values
resources:
  requests:
    cpu: 100m      # Set at 40-70% of expected average
    memory: 256Mi  # Set slightly above average usage
  limits:
    cpu: 500m      # 2-5x requests for burst
    memory: 512Mi  # 1.5-2x requests for spikes

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 60  # Within 40-70% optimal range
```

### Spot Instance Tolerations

```yaml
# Dev/staging: All workloads on Spot (70% savings)
tolerations:
  - key: "spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"

# Production: Prefer Spot with On-Demand fallback
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
            - key: workload-type
              operator: In
              values: ["spot-optimized"]

# Handle 2-minute Spot interruption notice
terminationGracePeriodSeconds: 120
```

## Health Checks and Validation

### Pre-Deployment Validation

```bash
# Step 1: Lint chart with strict mode (REQUIRED by SPEC.md)
helm lint --strict ./mychart
helm lint --strict ./mychart -f values-prod.yaml

# Step 2: Render templates locally and validate
helm template myrelease ./mychart -f values-prod.yaml > rendered.yaml
kubeconform -summary -strict rendered.yaml

# Step 3: Security scan rendered output
helm template myrelease ./mychart -f values-prod.yaml | \
  trivy config --severity CRITICAL,HIGH -

# Step 4: Dry-run against cluster
helm upgrade --install myrelease ./mychart \
  -f values-prod.yaml \
  --dry-run --debug \
  -n production

# Step 5: Diff against running state (requires helm-diff plugin)
helm diff upgrade myrelease ./mychart -f values-prod.yaml -n production
```

### Chart Testing with chart-testing (ct)

```yaml
# ci/ct.yaml
remote: origin
target-branch: main
chart-dirs:
  - charts
chart-repos:
  - bitnami=https://charts.bitnami.com/bitnami
helm-extra-args: --timeout 300s
validate-maintainers: true
check-version-increment: true
```

```bash
# Lint all changed charts
ct lint --config ci/ct.yaml

# Install and test changed charts (requires Kind cluster)
ct install --config ci/ct.yaml

# Lint and install with upgrade testing
ct lint-and-install --config ci/ct.yaml --upgrade
```

### CI/CD Integration Example

```yaml
# .github/workflows/helm-ci.yml
name: Helm Chart CI

on:
  pull_request:
    paths:
      - 'charts/**'

permissions:
  id-token: write
  contents: read

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Helm
        uses: azure/setup-helm@v4
        with:
          version: v3.15.0

      - name: Set up chart-testing
        uses: helm/chart-testing-action@v2

      - name: Lint charts (strict mode)
        run: ct lint --config ci/ct.yaml

      - name: Render and validate schemas
        run: |
          for chart in charts/*/; do
            echo "Validating $chart"
            helm template test "$chart" -f "$chart/ci/test-values.yaml" > /tmp/rendered.yaml
            kubeconform -summary -strict /tmp/rendered.yaml
          done

      - name: Security scan
        run: |
          for chart in charts/*/; do
            helm template test "$chart" | trivy config --severity CRITICAL,HIGH --exit-code 1 -
          done

      - name: Create Kind cluster
        uses: helm/kind-action@v1

      - name: Install and test charts
        run: ct install --config ci/ct.yaml --upgrade

  publish:
    needs: lint-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Helm
        uses: azure/setup-helm@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/helm-publisher
          aws-region: us-east-1

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Package and push charts
        run: |
          for chart in charts/*/; do
            helm package "$chart"
            chart_name=$(basename "$chart")
            helm push ${chart_name}-*.tgz oci://${ECR_REGISTRY}/charts
          done

      - name: Sign chart artifacts
        run: |
          for chart in charts/*/; do
            chart_name=$(basename "$chart")
            version=$(helm show chart "$chart" | grep '^version:' | awk '{print $2}')
            cosign sign --yes oci://${ECR_REGISTRY}/charts/${chart_name}:${version}
          done
```

## Troubleshooting Commands

```bash
# Debug template rendering
helm template myrelease ./mychart --debug 2>&1 | head -100

# Show computed values (merged defaults + overrides)
helm get values myrelease -n production -a

# Show rendered manifests from deployed release
helm get manifest myrelease -n production

# Check release history and rollback
helm history myrelease -n production
helm rollback myrelease 3 -n production

# Test release health
helm test myrelease -n production --logs

# Diff before upgrade (requires helm-diff plugin)
helm diff upgrade myrelease ./mychart -f values-prod.yaml -n production

# Validate chart schema without deploying
helm lint --strict ./mychart -f values-prod.yaml

# List all releases across namespaces
helm list --all-namespaces

# Show chart dependencies tree
helm dependency list ./mychart

# Debug OCI registry connectivity
helm registry login registry.example.com
helm pull oci://registry.example.com/charts/mychart --version 1.0.0

# Export rendered templates for manual review
helm template myrelease ./mychart -f values-prod.yaml --output-dir ./rendered/
```

## Anti-Patterns and Common Gotchas

### 1. Hardcoded Secrets in values.yaml

```yaml
# BAD: Secrets committed to version control
database:
  password: "my-super-secret-password"
```

**FIX**: Use empty defaults with deployment-time injection:
```yaml
# GOOD: Empty defaults, set at deploy time
database:
  password: ""
  existingSecret: ""  # Name of pre-existing Secret

# Deploy with:
# helm install myapp ./mychart --set database.password=$DB_PASS
# Or use external-secrets-operator to sync from vault
```

### 2. Missing values.schema.json

```
# BAD: No schema validation
mychart/
├── Chart.yaml
├── values.yaml
└── templates/
```

**FIX**: Always include a schema file. At minimum, validate required fields and types:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["image"],
  "properties": {
    "image": {
      "type": "object",
      "required": ["repository"]
    }
  }
}
```

### 3. Using `latest` Image Tags

```yaml
# BAD: Non-deterministic deployments
image:
  tag: latest
```

**FIX**: Default to Chart.appVersion and pin specific tags:
```yaml
image:
  tag: ""  # Defaults to .Chart.AppVersion in template
```

### 4. No Resource Limits

```yaml
# BAD: Unbounded resource consumption
resources: {}
```

**FIX**: Always define requests and limits:
```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### 5. Ignoring helm lint --strict

```bash
# BAD: Only running basic lint
helm lint ./mychart
```

**FIX**: Always use strict mode to catch warnings as errors:
```bash
# GOOD: Strict mode catches common issues
helm lint --strict ./mychart
helm lint --strict ./mychart -f values-prod.yaml
```

### 6. Mutable OCI Chart Tags

```bash
# BAD: Overwriting existing chart version in registry
helm push mychart-1.0.0.tgz oci://registry.example.com/charts  # Overwrites 1.0.0!
```

**FIX**: Enforce immutable versions. Increment `version` in Chart.yaml for every change. Configure registry to reject duplicate tags.

### 7. No ConfigMap Checksum Annotation

```yaml
# BAD: ConfigMap changes don't trigger pod rollout
spec:
  template:
    spec:
      containers:
        - name: app
```

**FIX**: Add checksum annotation to force rollout on config changes:
```yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

### 8. Missing .helmignore

```
# BAD: Chart package includes unnecessary files (.git, tests, CI config)
```

**FIX**: Create `.helmignore`:
```
# .helmignore
.git
.gitignore
.github/
ci/
*.md
!README.md
LICENSE
.helmignore
*.orig
*.bak
.idea/
.vscode/
__pycache__/
*.pyc
```

### 9. Incorrect Template Indentation

```yaml
# BAD: nindent value doesn't match context
spec:
  template:
    metadata:
      labels:
        {{- include "mychart.labels" . | nindent 6 }}  # Wrong: should be 8
```

**FIX**: Always verify indentation matches YAML context. Use `helm template --debug` to catch issues.

### 10. No PodDisruptionBudget for Production

```yaml
# BAD: All pods can be evicted during node drain
podDisruptionBudget:
  enabled: false
```

**FIX**: Enable PDB for production workloads:
```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1  # Or use maxUnavailable
```

## Chart Versioning and Release Strategy

### Versioning Conventions

- **`version`**: Chart version (SemVer). Increment on every chart change.
- **`appVersion`**: Application version. Updated when the packaged application changes.
- Both fields must follow SemVer (`MAJOR.MINOR.PATCH`).

**Version Bump Strategy**:
| Change Type | Version Field | Example |
|-------------|--------------|---------|
| Template fix / docs | PATCH | 1.2.3 -> 1.2.4 |
| New value / feature | MINOR | 1.2.3 -> 1.3.0 |
| Breaking change | MAJOR | 1.2.3 -> 2.0.0 |
| App image update only | appVersion only | appVersion: 3.4.5 -> 3.5.0 |

### Release Workflow

```bash
# 1. Develop and lint locally
helm lint --strict ./mychart
helm template test ./mychart | kubeconform -strict

# 2. Package chart
helm package ./mychart

# 3. Push to OCI registry
helm push mychart-1.2.0.tgz oci://registry.example.com/charts

# 4. Sign artifact
cosign sign --yes oci://registry.example.com/charts/mychart:1.2.0

# 5. Install from registry
helm install myrelease oci://registry.example.com/charts/mychart --version 1.2.0

# 6. Verify signature before install (production policy)
cosign verify \
  --certificate-identity-regexp=".*@example.com" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  oci://registry.example.com/charts/mychart:1.2.0
```

## Usage Guidelines

### When to Activate

This skill activates automatically when:

1. User requests Helm chart generation or modification
2. `iac-generator` agent needs Kubernetes packaging via Helm
3. Discussion involves chart templating, values design, or chart dependencies
4. User asks about Helmfile orchestration or multi-chart deployments
5. Chart testing, linting, or CI/CD pipeline integration is needed
6. OCI registry publishing or chart signing is discussed
7. Multi-environment value overlay design is needed

### When to Defer

Do NOT activate for:

- **Raw Kubernetes manifests**: Use `kubernetes-native` skill for plain YAML
- **Kustomize overlays**: Use `kubernetes-native` skill for Kustomize patterns
- **GitOps deployment**: Use `gitops-argocd` or `gitops-flux` for deployment patterns
- **Terraform Helm provider**: Use `terraform-modules` skill for `helm_release` resource
- **Container image building**: Use `container-analysis` skill for Dockerfiles
- **Cloud-specific K8s services**: Use `aws-eks` or `gcp-gke` for platform-specific setup

## Integration with iac-team Agents

### With iac-generator Agent

When the `iac-generator` agent invokes this skill:

1. **Context**: Provide application type, language, framework, and deployment requirements
2. **Security**: Apply SPEC.md constraints (no hardcoded secrets, OIDC preferred, `helm lint --strict` must pass)
3. **Schema**: Generate `values.schema.json` to validate all required inputs
4. **Testing**: Include `helm test` pods and `ct` configuration for CI
5. **Environment**: Generate value overlay files for dev/staging/production
6. **Registry**: Configure OCI push workflow with Sigstore signing
7. **Validation**: Ensure rendered templates pass `kubeconform` and Trivy scanning

### With iac-analyzer Agent

When `iac-analyzer` detects existing Helm charts:

1. Evaluate chart structure against best practices (missing schema, tests, .helmignore)
2. Identify security issues (hardcoded secrets, missing securityContext, no NetworkPolicy)
3. Check for outdated patterns (legacy Ingress instead of Gateway API, missing PDB)
4. Validate Chart.yaml versioning and dependency management
5. Assess template quality (proper use of helpers, indentation, conditional rendering)

### With iac-validator Agent

When `iac-validator` validates chart output:

1. Run `helm lint --strict` on all generated charts
2. Render templates and validate with `kubeconform`
3. Scan rendered output with Trivy for misconfigurations
4. Verify no secrets in chart source files
5. Check schema validation passes with environment-specific values

## Constraints Compliance

All generated Helm charts must satisfy these SPEC.md requirements:

- [ ] `helm lint --strict` passes with zero warnings
- [ ] No hardcoded secrets in `values.yaml` or templates
- [ ] OIDC preferred for CI/CD registry authentication
- [ ] `values.schema.json` included with type and required field validation
- [ ] Security context defaults: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`
- [ ] Resource requests and limits defined for all containers
- [ ] Rendered templates pass `kubeconform` schema validation
- [ ] Trivy config scan shows 0 CRITICAL/HIGH findings
- [ ] Chart tests included for post-deployment validation
- [ ] `.helmignore` excludes unnecessary files from packaging
- [ ] SemVer versioning for `version` and `appVersion`
- [ ] PodDisruptionBudget template included (enabled by default for production)
- [ ] NetworkPolicy template included for network segmentation
- [ ] ConfigMap checksum annotation triggers rollout on config changes

## References

For comprehensive Helm documentation and tooling:

- **Helm Documentation**: https://helm.sh/docs/
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Chart Template Guide**: https://helm.sh/docs/chart_template_guide/
- **values.schema.json**: https://helm.sh/docs/topics/charts/#schema-files
- **OCI Support**: https://helm.sh/docs/topics/registries/
- **Helm Test**: https://helm.sh/docs/helm/helm_test/
- **chart-testing (ct)**: https://github.com/helm/chart-testing
- **Helmfile**: https://helmfile.readthedocs.io/
- **Sigstore/cosign**: https://docs.sigstore.dev/
- **kubeconform**: https://github.com/yannh/kubeconform
- **Trivy**: https://trivy.dev/
- **Artifact Hub**: https://artifacthub.io/
- **Gateway API**: https://gateway-api.sigs.k8s.io/

---

**Version**: 1.0.0
**Last Updated**: 2026-02-03
**Compatible With**: Helm 3.12+, Kubernetes 1.28+

*This skill is part of the iac-team plugin. For related capabilities, see: kubernetes-native (raw manifests), gitops-argocd (ArgoCD deployment), gitops-flux (Flux deployment), container-analysis (Dockerfiles), terraform-modules (infrastructure provisioning), security-validation (scanning).*
