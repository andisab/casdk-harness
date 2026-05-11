---
name: crossplane
description: >
  Crossplane composition patterns for cloud-native infrastructure provisioning.
  Provides XRD (CompositeResourceDefinition), Composition, and Claim patterns
  for AWS, Azure, GCP resources with security best practices, validation pipelines,
  and hallucination detection for AI-generated compositions.

  Activate when user mentions: crossplane, XRD, composite resource, composition,
  claim, provider config, managed resources, crossplane composition, infrastructure
  composition, declarative infrastructure, control plane.

  Use for: Generating Crossplane compositions, XRDs, Claims, ProviderConfigs,
  and managed resource patterns following cloud-native best practices with
  multi-phase validation and cost optimization.

  Do NOT use for: Direct Terraform/Pulumi code, CloudFormation templates,
  Kubernetes operators (unless Crossplane-specific), raw cloud provider APIs.
---

# Crossplane Composition Skill

Expert knowledge for generating production-ready Crossplane compositions that follow infrastructure-as-code best practices with strong security defaults, multi-phase validation, and hallucination prevention.

## Core Capabilities

### 1. XRD (CompositeResourceDefinition) Generation
Create composite resource definitions with proper versioning, validation, and schema design:

- **API Design**: Group/version/kind naming conventions following Kubernetes API standards
- **Schema Validation**: OpenAPI v3 schemas with constraints, enums, and pattern validation
- **Defaulting**: Sensible defaults for optional fields with security-first values
- **Status Fields**: Connection secrets and condition reporting with proper status subresource
- **Versioning**: Support for v1alpha1, v1beta1, v1 progressions with conversion webhooks
- **Schema Validation**: Validate all generated resource types against official Crossplane provider schemas (hallucination detection)

### 2. Composition Patterns
Generate compositions that implement XRDs with managed resources:

- **Resource Selection**: Use `matchLabels` for dynamic composition selection
- **Patch Strategies**: FromCompositeFieldPath, ToCompositeFieldPath, CombineFromComposite, CombineToComposite
- **Connection Secrets**: Properly expose credentials to claims with secret propagation
- **Dependencies**: Use `readinessChecks` for resource ordering and dependency management
- **Multi-Cloud**: Abstract provider differences in compositions for portability
- **Transform Functions**: Use string, math, and map transforms for computed values
- **Composition Functions**: Leverage function pipelines for complex logic (Patch & Transform, Go templating)

### 3. Claim Templates
Generate namespace-scoped claims for developer self-service:

- **Simple Interface**: Hide complexity from application teams with minimal parameters
- **Connection Secrets**: Reference secrets in same namespace for application consumption
- **Composition Selection**: Use labels or explicit compositionRef for environment-specific routing
- **Parameters**: Expose only necessary configuration knobs following least-privilege principle
- **Resource Quotas**: Consider namespace resource limits in claim designs

### 4. ProviderConfig Security
Configure provider authentication following security best practices:

- **OIDC/IRSA**: Prefer IAM Roles for Service Accounts (no long-lived keys)
- **Workload Identity**: Use GCP Workload Identity or Azure Managed Identity
- **Least Privilege**: Scope permissions to required resources with policy validation
- **Secret Management**: Use Kubernetes secrets with proper RBAC when OIDC unavailable
- **Multi-Account**: Support separate dev/staging/prod configs with namespace isolation
- **Credential Rotation**: Document rotation procedures and expiration policies

## Multi-Phase Validation Pipeline

**CRITICAL**: All AI-generated Crossplane compositions MUST pass two-phase validation before deployment:

### Phase 1: Technical Validation (Syntax & Structure)
```bash
# Step 1: Schema validation against Crossplane CRDs
kubectl apply --dry-run=server -f composition.yaml

# Step 2: Validate against provider schemas (hallucination detection)
# Ensures all resource types and attributes exist in provider documentation
crossplane beta validate composition.yaml

# Step 3: Check composition readiness
kubectl get composition -o jsonpath='{.status.conditions[?(@.type=="Synced")].status}'

# Target: >95% syntax validation success
```

### Phase 2: Intent Validation (Policy & Security)
```bash
# Step 1: Policy-as-code validation with OPA/Rego
opa eval --data policies/ --input composition.yaml "data.crossplane.violations"

# Step 2: Security scanning with Trivy
trivy config composition.yaml \
  --severity CRITICAL,HIGH \
  --format json \
  --output trivy-report.json

# Step 3: Validate security requirements
# - No long-lived credentials (source: Secret)
# - IRSA/Workload Identity configured
# - Least-privilege IAM policies
# - Connection secrets use proper RBAC

# Target: 0 policy violations, 0 CRITICAL/HIGH security findings
```

### Hallucination Detection Checklist
- [ ] All resource `apiVersion` values match installed provider versions
- [ ] All `kind` values exist in provider CRDs (`kubectl get crds`)
- [ ] All `spec.forProvider` fields match provider resource schemas
- [ ] No fabricated patch field paths (validate against XRD schema)
- [ ] Connection secret keys match actual provider outputs
- [ ] Provider exists and version is compatible

**Target metrics**: >99% hallucination detection rate, >95% validation success rate

## Security Patterns

### Credential Management
**REQUIRED**: All provider configurations MUST use OIDC/IRSA or similar short-lived credentials:

```yaml
# ✅ GOOD: AWS IRSA (IAM Roles for Service Accounts)
apiVersion: aws.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: aws-provider-config
spec:
  credentials:
    source: InjectedIdentity  # Uses IRSA pod identity
  # Optional: Assume role for cross-account access
  assumeRoleChain:
    - roleARN: arn:aws:iam::123456789012:role/crossplane-prod
```

```yaml
# ✅ GOOD: GCP Workload Identity
apiVersion: gcp.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: gcp-provider-config
spec:
  credentials:
    source: InjectedIdentity
  projectID: my-gcp-project-id
```

```yaml
# ⚠️ ACCEPTABLE: Azure Managed Identity
apiVersion: azure.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: azure-provider-config
spec:
  credentials:
    source: InjectedIdentity
  # Uses Azure AD Workload Identity
```

```yaml
# ❌ BAD: Long-lived credentials
apiVersion: aws.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: aws-provider-config
spec:
  credentials:
    source: Secret  # Avoid unless absolutely necessary
    secretRef:
      name: aws-credentials  # Long-lived keys = security risk
      namespace: crossplane-system
      key: credentials
```

### Secret References
Never hardcode secrets in compositions or XRDs. Use `.env` pattern:

- Provide `.env.example` with placeholder values
- Document required secrets in README with rotation procedures
- Reference secrets from ProviderConfig or connection secrets
- Use Kubernetes RBAC to restrict secret access
- Scan for hardcoded credentials using Trivy `--scanners secret`

### RBAC Boundaries
Limit claim creation to specific namespaces with proper role separation:

```yaml
# ClusterRole for XRD access (cluster-scoped, for infrastructure team)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: crossplane-xrd-admin
rules:
  - apiGroups: ["apiextensions.crossplane.io"]
    resources: ["compositeresourcedefinitions", "compositions"]
    verbs: ["*"]

---
# Role for Claim access (namespace-scoped, for application developers)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: crossplane-claim-user
  namespace: dev-team-namespace
rules:
  - apiGroups: ["database.example.com"]
    resources: ["postgresqlclaims"]
    verbs: ["create", "get", "list", "watch", "delete"]
```

### Security Scanning Integration

**Trivy Configuration** (scan Crossplane YAML manifests):
```bash
# Update database before scanning (minimize false positives)
trivy image --download-db-only

# Scan composition with severity thresholds
trivy config crossplane/compositions/ \
  --severity CRITICAL,HIGH \
  --ignore-unfixed \
  --format json \
  --exit-code 1

# Generate SBOM for supply chain security
trivy config crossplane/ \
  --format cyclonedx \
  --output crossplane-sbom.json
```

**Checkov Configuration** (compliance frameworks):
```bash
# Scan with CIS Kubernetes Benchmark
checkov -d crossplane/compositions/ \
  --framework kubernetes \
  --compact \
  --quiet

# Custom policy for Crossplane-specific checks
checkov -d crossplane/ \
  --external-checks-dir ./policies/ \
  --check CKV_CROSSPLANE_1  # No long-lived credentials
```

**.trivyignore Example** (document exceptions with expiration):
```
# CVE-2024-1234: False positive - not applicable to Crossplane compositions
# Reviewed: 2026-02-03, Expires: 2026-05-03, Approved: security-team@example.com
CVE-2024-1234

# MEDIUM severity findings accepted for dev environment
# Review quarterly for production promotions
CKV_K8S_20
```

## Composition Structure

### Standard Composition Layout

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: {resource-type}-{cloud-provider}-{variant}
  labels:
    crossplane.io/xrd: x{resourcetype}s.{group}
    provider: {aws|azure|gcp}
    environment: {dev|staging|prod}
    cost-optimized: "true"  # Indicates use of spot instances/savings plans
spec:
  writeConnectionSecretsToNamespace: crossplane-system
  compositeTypeRef:
    apiVersion: {group}/{version}
    kind: X{ResourceType}

  # Composition functions for complex logic (Crossplane 1.14+)
  mode: Pipeline  # Use function pipelines for advanced transformations
  pipeline:
    - step: patch-and-transform
      functionRef:
        name: function-patch-and-transform
      input:
        apiVersion: pt.fn.crossplane.io/v1beta1
        kind: Resources
        resources: []  # Define resources in pipeline

  resources:
    - name: {logical-name}
      base:
        apiVersion: {provider-api}
        kind: {ManagedResource}
        spec:
          forProvider:
            # Provider-specific configuration
            # VALIDATE: All fields must exist in provider schema
          providerConfigRef:
            name: {provider-config-name}
          # Deletion policy for data safety
          deletionPolicy: Orphan  # Or Delete (default)

      patches:
        - type: FromCompositeFieldPath
          fromFieldPath: spec.parameters.{field}
          toFieldPath: spec.forProvider.{field}
          transforms:
            - type: string
              string:
                fmt: "prefix-%s-suffix"

        - type: ToCompositeFieldPath
          fromFieldPath: status.atProvider.{field}
          toFieldPath: status.{field}

        - type: CombineFromComposite
          combine:
            variables:
              - fromFieldPath: spec.parameters.name
              - fromFieldPath: spec.parameters.environment
            strategy: string
            string:
              fmt: "%s-%s-resource"
          toFieldPath: spec.forProvider.resourceName

      # Readiness checks for dependency ordering
      readinessChecks:
        - type: MatchString
          fieldPath: status.atProvider.state
          matchString: "ACTIVE"

      connectionDetails:
        - type: FromConnectionSecretKey
          name: {output-key}
          fromConnectionSecretKey: {provider-key}
```

## Cost Optimization Patterns

### Spot Instance Integration for Compute Resources

**EKS Node Groups with Spot Instances** (66-90% savings):
```yaml
apiVersion: eks.aws.crossplane.io/v1alpha1
kind: NodeGroup
metadata:
  name: spot-nodegroup
spec:
  forProvider:
    capacityType: SPOT  # Use Spot instances
    instanceTypes:
      - t3a.medium
      - t3.medium
      - t2.medium
      - t3a.large  # Diversify across 4+ types
    scalingConfig:
      desiredSize: 3
      maxSize: 10
      minSize: 1
    # Spot best practices
    updateConfig:
      maxUnavailable: 1  # Graceful replacement
```

**GKE Node Pool with Spot VMs**:
```yaml
apiVersion: container.gcp.crossplane.io/v1beta2
kind: NodePool
metadata:
  name: spot-nodepool
spec:
  forProvider:
    # Use Spot VMs (preemptible in GCP)
    nodeConfig:
      spot: true
      machineType: e2-standard-4
      diskSizeGb: 100
    autoscaling:
      enabled: true
      minNodeCount: 1
      maxNodeCount: 10
    management:
      autoRepair: true
      autoUpgrade: true
```

**Interruption Handling** (include in composition documentation):
```yaml
# Composition should document required add-ons:
# - AWS: aws-node-termination-handler DaemonSet
# - GCP: GKE automatic preemption handling
# - Azure: Azure Spot Virtual Machines with eviction policies

# EventBridge rule for Spot interruptions (AWS)
# Composition can create this alongside NodeGroup
apiVersion: cloudwatchevents.aws.crossplane.io/v1alpha1
kind: Rule
metadata:
  name: spot-interruption-handler
spec:
  forProvider:
    eventPattern: |
      {
        "source": ["aws.ec2"],
        "detail-type": ["EC2 Spot Instance Interruption Warning"]
      }
    targets:
      - arn: arn:aws:lambda:region:account:function:drain-node
        id: spot-drain-lambda
```

### Right-Sizing and Auto-Scaling

**Auto-Scaling Policies** (target 40-70% utilization):
```yaml
apiVersion: autoscaling.aws.crossplane.io/v1alpha1
kind: AutoScalingGroup
metadata:
  name: app-asg
spec:
  forProvider:
    minSize: 2
    maxSize: 20
    desiredCapacity: 5
    # Target tracking scaling (asymmetric policies)
    targetTrackingConfiguration:
      predefinedMetricSpecification:
        predefinedMetricType: ASGAverageCPUUtilization
      targetValue: 60.0  # Scale at 60% CPU
    # Scale up fast (1 min), scale down slow (5 min cooldown)
    healthCheckGracePeriod: 300
    cooldown: 300
```

**Scheduled Scaling** (70% savings for non-production):
```yaml
# Composition can include scheduled actions for dev/test
apiVersion: autoscaling.aws.crossplane.io/v1alpha1
kind: ScheduledAction
metadata:
  name: scale-down-after-hours
spec:
  forProvider:
    autoScalingGroupName: dev-asg
    schedule: "0 18 * * MON-FRI"  # 6 PM weekdays
    minSize: 0
    maxSize: 0
    desiredCapacity: 0
---
apiVersion: autoscaling.aws.crossplane.io/v1alpha1
kind: ScheduledAction
metadata:
  name: scale-up-business-hours
spec:
  forProvider:
    autoScalingGroupName: dev-asg
    schedule: "0 8 * * MON-FRI"  # 8 AM weekdays
    minSize: 2
    maxSize: 10
    desiredCapacity: 3
```

### Reserved Capacity and Savings Plans

**Composition Annotations** (document cost strategy):
```yaml
metadata:
  annotations:
    cost.strategy: "mixed-spot-ondemand"
    cost.spot-percentage: "70"
    cost.savings-plan: "compute-savings-plan-1yr"
    cost.estimated-monthly: "$1200"
    cost.vs-ondemand-savings: "68%"
```

## Modern Kubernetes Patterns

### Gateway API Integration (v1 GA)

When generating Kubernetes manifests in compositions, use Gateway API instead of Ingress:

```yaml
# HTTPRoute resource (application developer concern)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
spec:
  parentRefs:
    - name: shared-gateway
      namespace: gateway-system
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /api
      backendRefs:
        - name: backend-service
          port: 8080
          weight: 80  # Traffic splitting for canary
        - name: backend-service-canary
          port: 8080
          weight: 20
```

**BackendTLSPolicy for mTLS**:
```yaml
apiVersion: gateway.networking.k8s.io/v1alpha3
kind: BackendTLSPolicy
metadata:
  name: backend-tls
spec:
  targetRef:
    group: ''
    kind: Service
    name: backend-service
  tls:
    caCertificateRefs:
      - name: backend-ca-cert
        group: ''
        kind: ConfigMap
    hostname: backend.example.com
```

### Native Sidecar Containers (Kubernetes 1.29+)

When compositions include Pod specs, use native sidecars:

```yaml
# In composition that creates Pods/Deployments
spec:
  template:
    spec:
      initContainers:
        # Native sidecar using restartPolicy: Always
        - name: log-forwarder
          image: fluent/fluent-bit:2.1
          restartPolicy: Always  # Makes this a native sidecar
          # Startup probe signals sidecar readiness
          startupProbe:
            httpGet:
              path: /api/v1/health
              port: 2020
            failureThreshold: 30
            periodSeconds: 10
          # Lifecycle hooks for initialization
          lifecycle:
            postStart:
              exec:
                command: ["/bin/sh", "-c", "echo Sidecar started"]
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]  # Graceful shutdown
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
      containers:
        - name: main-app
          image: app:v1.0
          # Main container starts after sidecar is ready
```

**Benefits**:
- Sidecars start before main containers and terminate after
- Jobs complete properly even with sidecars present
- Better resource management and termination ordering

## Error Pattern Recognition

Common LLM-generated Crossplane errors (from research findings):

### Factual Incorrectness (65% of technical errors)
**Error**: Invalid `apiVersion` or `kind` not matching provider CRDs
```yaml
# ❌ WRONG: Hallucinated API version
apiVersion: aws.crossplane.io/v1beta5  # v1beta5 doesn't exist
kind: RDSInstance  # Wrong kind name
```
**Fix**: Validate against installed CRDs
```bash
kubectl get crds | grep rds
# Use: rdsinstances.database.aws.crossplane.io
```

### Contextual Reasoning Failure (47.6% of intent errors)
**Error**: Missing required dependencies or improper readiness checks
```yaml
# ❌ WRONG: No dependency between subnet and instance
resources:
  - name: subnet
    base:
      kind: Subnet
  - name: instance
    base:
      kind: Instance
      spec:
        forProvider:
          subnetId: # Missing patch from subnet status
```
**Fix**: Use patches and readiness checks
```yaml
resources:
  - name: subnet
    base:
      kind: Subnet
    readinessChecks:
      - type: MatchString
        fieldPath: status.atProvider.state
        matchString: "available"
  - name: instance
    base:
      kind: Instance
    patches:
      - type: FromCompositeFieldPath
        fromFieldPath: status.subnet.id  # Proper dependency
        toFieldPath: spec.forProvider.subnetId
```

### Incomplete Specifications
**Error**: Missing required connection details or status fields
```yaml
# ❌ WRONG: No connection details exposed
resources:
  - name: database
    base:
      kind: RDSInstance
    # Missing connectionDetails section
```
**Fix**: Expose necessary connection secrets
```yaml
resources:
  - name: database
    connectionDetails:
      - type: FromConnectionSecretKey
        name: endpoint
        fromConnectionSecretKey: endpoint
      - type: FromConnectionSecretKey
        name: password
        fromConnectionSecretKey: password
      - type: FromFieldPath
        name: username
        fromFieldPath: spec.forProvider.masterUsername
```

## Validation Requirements

All generated Crossplane resources must:

1. **Pass Schema Validation**: `kubectl apply --dry-run=server -f composition.yaml`
2. **Include Required Labels**: crossplane.io/xrd, provider, environment, cost-optimized
3. **Connection Secrets**: Use proper secret propagation with RBAC
4. **Status Conditions**: Report readiness and errors with proper condition types
5. **Security Scan**: 0 CRITICAL/HIGH findings in Trivy/Checkov
6. **Hallucination Check**: All resource types/attributes validated against provider schemas
7. **Policy Validation**: Pass OPA/Rego policy checks for organizational requirements
8. **Cost Annotations**: Document cost strategy and estimated expenses

## Common Patterns

### Multi-Resource Composition
For resources requiring multiple managed resources (e.g., VPC with subnets, security groups):

- Use `resources[*].name` as logical identifiers
- Patch between managed resources using `FromCompositeFieldPath` + `ToCompositeFieldPath`
- Define `readinessChecks` to ensure creation order
- Use `dependsOn` in function pipelines for explicit dependencies

### Environment-Specific Compositions
Create separate compositions for dev/staging/prod with cost optimization:

```yaml
# composition-dev.yaml (cost-optimized with Spot)
metadata:
  name: postgres-aws-dev
  labels:
    environment: dev
    cost-optimized: "true"
  annotations:
    cost.strategy: "spot-instances-70-percent"

# composition-prod.yaml (reliability-focused)
metadata:
  name: postgres-aws-prod
  labels:
    environment: prod
    cost-optimized: "false"
  annotations:
    cost.strategy: "reserved-instances-savings-plan"
```

### Provider Abstraction
Create provider-agnostic XRDs that can be implemented by multiple clouds:

```yaml
# XRD: Database (provider-agnostic)
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xdatabases.example.com
spec:
  group: example.com
  names:
    kind: XDatabase
    plural: xdatabases
  versions:
    - name: v1alpha1
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                parameters:
                  type: object
                  properties:
                    size:
                      type: string
                      enum: ["small", "medium", "large"]
                    costOptimized:
                      type: boolean
                      default: false
                  required: ["size"]

# Compositions:
# - database-aws (RDS with Spot read replicas for costOptimized=true)
# - database-azure (Azure SQL with reserved capacity)
# - database-gcp (Cloud SQL with committed use discounts)
```

## File Organization

When generating Crossplane resources, organize as:

```
crossplane/
├── definitions/
│   └── x{resource}.yaml         # XRDs
├── compositions/
│   ├── {resource}-{provider}-{variant}.yaml
│   ├── {resource}-{provider}-cost-optimized.yaml  # Spot/savings variants
│   └── ...
├── claims/
│   └── {resource}-claim.yaml    # Example claims
├── provider-configs/
│   ├── aws-config.yaml          # IRSA configuration
│   ├── azure-config.yaml        # Managed Identity configuration
│   └── gcp-config.yaml          # Workload Identity configuration
├── policies/
│   ├── opa/                     # OPA/Rego policies for intent validation
│   └── .trivyignore             # Documented security exceptions
├── tests/
│   └── composition-tests.yaml   # Validation test cases
└── .env.example                 # Required secrets documentation
```

## Progressive Disclosure

**Core instructions above** (~2000 tokens) cover 90% of use cases with modern patterns.

**For detailed examples and advanced patterns**, reference:
- `examples/database-composition.yaml` - Full PostgreSQL RDS composition with cost optimization
- `examples/network-composition.yaml` - Multi-resource VPC setup with Gateway API
- `examples/xrd-with-validation.yaml` - Complex OpenAPI validation schemas
- `examples/cost-optimized-eks.yaml` - EKS cluster with Spot node groups and interruption handling
- `templates/composition-template.yaml` - Starter template with validation pipeline
- `templates/xrd-template.yaml` - XRD boilerplate with security annotations

## Usage Instructions

### When Invoked
1. **Identify resource type**: Database, network, compute, storage, etc.
2. **Determine cloud provider**: AWS, Azure, GCP, or multi-cloud
3. **Assess cost requirements**: Production (reliability) vs dev/test (cost-optimized)
4. **Select composition pattern**: Single-resource, multi-resource, or abstraction
5. **Generate XRD first** (if new resource type) with proper schema validation
6. **Generate Composition(s)** implementing the XRD with validation pipeline
7. **Generate example Claim** for testing
8. **Include ProviderConfig** with OIDC/IRSA/Workload Identity configuration
9. **Run multi-phase validation**:
   - Technical: `kubectl apply --dry-run=server`
   - Intent: `opa eval` + `trivy config`
   - Hallucination check: Validate against provider schemas
10. **Document cost strategy** in annotations

### Generated Output Structure
For each resource request, generate:
- XRD (if new composite resource) with hallucination-resistant schemas
- Composition (1+ variants: standard + cost-optimized)
- Example claim for dev and production environments
- ProviderConfig with OIDC/IRSA/Workload Identity (no long-lived keys)
- OPA policies for intent validation
- .trivyignore with documented exceptions (if needed)
- .env.example documenting required secrets
- README section explaining usage, validation, and cost strategy

### Quality Checks
Before completing generation:
- [ ] All YAML is valid and properly indented
- [ ] No hardcoded secrets (check spec.forProvider fields with Trivy)
- [ ] ProviderConfig uses OIDC/IRSA/Workload Identity (not long-lived keys)
- [ ] Connection secrets properly propagated with RBAC
- [ ] Labels include crossplane.io/xrd, provider, environment, cost-optimized
- [ ] OpenAPI schemas include validation constraints (enums, patterns, min/max)
- [ ] Status conditions defined in XRD with proper types
- [ ] All resource types validated against provider CRDs (hallucination check)
- [ ] Multi-phase validation pipeline passes (technical + intent)
- [ ] Security scan shows 0 CRITICAL/HIGH findings
- [ ] Cost strategy documented in annotations
- [ ] Readiness checks configured for resource dependencies
- [ ] Modern K8s patterns used (Gateway API v1, native sidecars for K8s 1.29+)

**Target metrics**:
- >95% syntax validation success
- >99% hallucination detection
- 0 CRITICAL/HIGH security findings
- 0 policy violations

## Boundaries

### Use This Skill For:
- Generating Crossplane XRDs, Compositions, Claims
- Crossplane provider configurations with OIDC/IRSA/Workload Identity
- Multi-cloud infrastructure abstractions
- Connection secret patterns with security controls
- Crossplane RBAC configurations
- Cost-optimized composition variants (Spot instances, savings plans)
- Validation pipelines (technical + intent + security)
- Modern Kubernetes patterns (Gateway API v1, native sidecars)

### Do NOT Use For:
- Raw Kubernetes manifests (unless Crossplane CRDs)
- Terraform/Pulumi/CloudFormation code (use terraform-modules or other skills)
- Helm charts (unless packaging Crossplane resources)
- Cloud provider SDKs or APIs directly
- Infrastructure not managed by Crossplane
- Ingress resources (use Gateway API v1 instead)

## Integration with iac-generator

This skill is invoked by the `iac-generator` agent when:
- User requests Crossplane-based infrastructure
- Repository analysis identifies Crossplane as the IaC tool
- Composition pattern is needed for multi-cloud abstraction
- Cost optimization requirements specified

The iac-generator agent will:
1. Call this skill for composition patterns with cost requirements
2. Integrate generated resources into repository structure
3. Run multi-phase validation:
   - Technical: `kubectl apply --dry-run=server`
   - Intent: OPA policy validation
   - Security: Trivy/Checkov scanning
   - Hallucination: Provider schema validation
4. Ensure security constraints are met (OIDC/IRSA, no hardcoded secrets)
5. Document cost strategy and estimated savings
6. Apply modern K8s patterns (Gateway API v1, native sidecars)

## Examples

See `examples/` directory for:
- `database-rds-composition.yaml` - Complete PostgreSQL RDS setup with cost optimization
- `vpc-network-composition.yaml` - Multi-resource networking with Gateway API v1
- `kubernetes-cluster-xrd.yaml` - Complex XRD with validation and hallucination prevention
- `multi-cloud-database.yaml` - Provider-agnostic abstraction with cost annotations
- `providerconfig-oidc.yaml` - Secure authentication patterns (AWS IRSA, GCP Workload Identity)
- `cost-optimized-eks.yaml` - EKS cluster with Spot node groups (70% cost savings)
- `native-sidecar-deployment.yaml` - Pod spec with K8s 1.29+ native sidecars
- `validation-pipeline.yaml` - Complete validation workflow (technical + intent)

## References

For comprehensive Crossplane documentation:
- Crossplane Docs: https://docs.crossplane.io
- Provider Reference: https://marketplace.upbound.io
- Composition Functions: https://docs.crossplane.io/latest/concepts/composition-functions
- Gateway API v1: https://gateway-api.sigs.k8s.io
- Native Sidecars: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers
- Security Best Practices: Use OIDC/IRSA, Trivy scanning, OPA policies
- Cost Optimization: AWS Spot instances, GCP Spot VMs, right-sizing, scheduled scaling
