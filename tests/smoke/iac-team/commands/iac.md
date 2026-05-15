---
description: Infrastructure-as-Code automation - analyze, generate, validate, and deploy resources with AI-assisted workflows
argument-hint: <operation> [--repo <path>] [--target <platform>] [--gitops <tool>] [--validate] [--dry-run]
allowed-tools: Task, Read, Grep, Glob, Bash(git:*), Bash(kubectl:*), Bash(helm:*), Bash(terraform:*), Bash(docker:*)
model: sonnet
---

# Infrastructure-as-Code Automation Command

Execute IaC operations using specialized agents for analysis, generation, and validation with modern best practices.

## Operation: ${1:-help}

${1}

---

## Parameter Validation

**Before executing any operation, validate required parameters:**

```bash
# Extract operation (required)
OPERATION="${1:-help}"

# Extract parameters from ARGUMENTS
REPO_PATH=$(echo "$ARGUMENTS" | grep -oP '(?<=--repo )[^ ]+' || echo ".")
TARGET_PLATFORM=$(echo "$ARGUMENTS" | grep -oP '(?<=--target )[^ ]+')
GITOPS_TOOL=$(echo "$ARGUMENTS" | grep -oP '(?<=--gitops )[^ ]+')
CI_PLATFORM=$(echo "$ARGUMENTS" | grep -oP '(?<=--ci )[^ ]+')
VALIDATE_PATH=$(echo "$ARGUMENTS" | grep -oP '(?<=--path )[^ ]+' || echo ".")

# Extract flags
DRY_RUN=$(echo "$ARGUMENTS" | grep -q '\--dry-run' && echo "true" || echo "false")
HELM_MODE=$(echo "$ARGUMENTS" | grep -q '\--helm' && echo "true" || echo "false")
STRICT_MODE=$(echo "$ARGUMENTS" | grep -q '\--strict' && echo "true" || echo "false")
SKIP_VALIDATION=$(echo "$ARGUMENTS" | grep -q '\--no-validate' && echo "true" || echo "false")
VALIDATE_ALL=$(echo "$ARGUMENTS" | grep -q '\--all' && echo "true" || echo "false")
BROWNFIELD=$(echo "$ARGUMENTS" | grep -q '\--brownfield' && echo "true" || echo "false")
GATEWAY_API=$(echo "$ARGUMENTS" | grep -q '\--gateway-api' && echo "true" || echo "false")
REQUIRE_APPROVAL=$(echo "$ARGUMENTS" | grep -q '\--require-approval' && echo "true" || echo "false")

# Validation checks
case "$OPERATION" in
  generate|deploy)
    if [ -z "$TARGET_PLATFORM" ]; then
      echo "❌ ERROR: --target parameter is required for $OPERATION operation"
      echo "Valid targets: aws-eks, aws-ecs, gcp-gke, gcp-run, kubernetes, terraform"
      echo ""
      echo "Usage: /iac $OPERATION --target <platform> [other options]"
      exit 1
    fi

    # Validate target platform
    VALID_TARGETS="aws-eks|aws-ecs|gcp-gke|gcp-run|kubernetes|terraform"
    if ! echo "$TARGET_PLATFORM" | grep -qE "^($VALID_TARGETS)$"; then
      echo "❌ ERROR: Invalid target '$TARGET_PLATFORM'"
      echo "Valid targets: aws-eks, aws-ecs, gcp-gke, gcp-run, kubernetes, terraform"
      exit 1
    fi
    ;;

  analyze)
    if [ ! -d "$REPO_PATH" ]; then
      echo "❌ ERROR: Repository path '$REPO_PATH' does not exist"
      echo "Usage: /iac analyze --repo <path>"
      exit 1
    fi
    ;;

  validate)
    if [ "$VALIDATE_ALL" = "false" ] && [ ! -d "$VALIDATE_PATH" ]; then
      echo "❌ ERROR: Validation path '$VALIDATE_PATH' does not exist"
      echo "Usage: /iac validate --path <path> OR /iac validate --all"
      exit 1
    fi
    ;;
esac
```

---

## Available Operations

### 1. analyze - Repository Analysis
**Purpose**: Scan codebase to identify services, dependencies, and deployment patterns with brownfield context awareness.

**Usage**:
```bash
/iac analyze --repo <path>
/iac analyze --repo . --brownfield  # Reads existing state files
/iac analyze --repo . --output analysis.json
```

**What it does**:
- Detects application frameworks and languages
- Identifies database and service dependencies
- Maps network topology and service mesh patterns
- **Brownfield mode**: Reads Terraform state and existing K8s resources
- Generates architecture diagram and recommendations
- Creates `iac-analysis.json` with context for AI generation

**Brownfield analysis** (when `--brownfield` flag set):
- Reads `terraform.tfstate` for existing infrastructure context
- Queries Kubernetes API for deployed resources: `kubectl get all -A -o json`
- Detects existing resource dependencies to avoid conflicts
- Injects context into generation prompts preventing hallucinated assumptions

**Invokes**: `iac-analyzer` agent with repo-analysis skill

**Exit codes**:
- `0`: Analysis completed successfully
- `1`: Repository path invalid or not accessible
- `2`: Analysis failed (unsupported project structure)

---

### 2. generate - Resource Generation
**Purpose**: Create production-ready IaC resources with AI-assisted validation, hallucination detection, and modern K8s/Terraform patterns.

**Usage**:
```bash
/iac generate --target aws-eks
/iac generate --target gcp-gke --gitops argocd --gateway-api
/iac generate --target kubernetes --helm --require-approval
/iac generate --repo . --target aws-eks --gitops flux --brownfield
```

**Parameters**:
- `--target`: Platform (**required**: `aws-eks`, `aws-ecs`, `gcp-gke`, `gcp-run`, `kubernetes`, `terraform`)
- `--gitops`: GitOps tool (`argocd`, `flux`, `none`)
- `--helm`: Generate Helm charts instead of raw manifests
- `--ci`: CI/CD platform (`github-actions`, `gitlab-ci`)
- `--repo`: Repository path (defaults to current directory)
- `--brownfield`: Read existing state for context injection (prevents AI hallucinations)
- `--gateway-api`: Use Gateway API v1 instead of Ingress (K8s 1.31+)
- `--require-approval`: Enable human-in-the-loop governance for critical resources

**What it generates**:
- **Containerization**: Multi-stage Dockerfiles with security hardening
- **Kubernetes**: Deployments with native sidecars (K8s 1.29+), resource limits, health checks
- **Gateway API** (if `--gateway-api`): HTTPRoute and Gateway resources instead of Ingress
- **Helm**: Production-ready charts with values.yaml variants
- **Terraform**: Cloud infrastructure with 1.7+ features (import blocks with for_each, .tftest.hcl tests)
- **CI/CD**: Pipelines with OIDC authentication, reusable workflows, matrix optimization
- **GitOps**: ArgoCD Applications or Flux Kustomizations with immediate reconciliation

**AI-Assisted Generation Features**:

1. **Hallucination Detection**:
   - Validates all resource types against official provider schemas
   - Checks module sources against verified registries (Terraform Registry, Helm Hub)
   - Flags unverifiable dependencies for human review
   - Implements dual-validation for AI-generated configurations

2. **Context Injection** (brownfield mode):
   - Reads existing `terraform.tfstate` before generation
   - Queries current Kubernetes resources: `kubectl get all -A`
   - Injects state context into AI prompts avoiding resource conflicts
   - Aligns generated resources with existing infrastructure

3. **Human-in-the-Loop Governance** (when `--require-approval`):
   - Flags high-risk resources for review: IAM policies, security groups, encryption configs
   - Generates approval checkpoints in CI/CD pipelines
   - Creates audit trail: `generation-audit.json` with AI decisions and human approvals

**Modern Features**:

**Kubernetes 1.31+ patterns**:
- Native sidecar containers using `restartPolicy: Always` on init containers
- Gateway API v1 with HTTPRoute for traffic routing (replaces Ingress)
- BackendTLSPolicy for TLS termination and re-encryption
- Proper startup ordering and termination sequences for sidecars

**Terraform 1.7+ patterns**:
- Import blocks with `for_each` for multi-resource imports
- Native test framework with `.tftest.hcl` files
- Mock providers for unit testing without cloud API calls
- Automatic test resource cleanup

**CI/CD patterns**:
- OIDC authentication with restrictive trust policies (no long-lived credentials)
- Reusable workflows pinned to commit SHAs or semantic version tags
- Matrix strategies with fail-fast and type=gha cache for Docker builds
- GitLab DAG pipelines with `needs` keyword for parallel execution

**Security enforcements** (pre-flight checks):
- ✅ Verify no `.env` files exist in repo (use `.env.example` instead)
- ✅ Check no AWS/GCP credentials in repository
- ✅ Validate required tools available (kubectl, helm, terraform)
- ✅ Verify Kubernetes version 1.29+ for native sidecars
- ✅ Check Terraform version 1.7+ for import for_each and testing

**Invokes**: `iac-generator` agent with platform-specific skills

**Exit codes**:
- `0`: Generation completed successfully
- `1`: Warnings present (resources generated but may need review)
- `2`: Generation failed (security violations, hallucination detected, or validation errors)

---

### 3. validate - Multi-Phase Security and Policy Validation
**Purpose**: Two-phase validation (technical + intent) with severity-based thresholds and comprehensive scanning.

**Usage**:
```bash
/iac validate --path ./kubernetes
/iac validate --path ./terraform --strict
/iac validate --all
```

**Validation Architecture** (two-phase approach):

**Phase 1: Technical Validation** (syntax and security):
- **Container Security**: Trivy with updated databases, `--ignore-unfixed` flag
- **Infrastructure Security**: Checkov (replaces tfsec), Trivy-IaC
- **Kubernetes**: `kubectl --dry-run=server` validation
- **Helm**: `helm lint --strict` checking
- **Terraform**: `terraform plan` dry-run + `terraform test` execution
- **Secrets**: Detection with `.trivyignore` for documented exceptions

**Phase 2: Intent Validation** (semantic and policy):
- **OPA/Rego Policies**: Validate infrastructure intent against organizational requirements
- **Dependency Graphs**: Verify resource relationships match specifications
- **Compliance Frameworks**: CIS, PCI-DSS, GDPR checks via Checkov
- **Gateway API Conformance**: Validate HTTPRoute and Gateway configurations

**Trivy Configuration** (best practices 2026):
```bash
# Update database before scanning
trivy image --download-db-only

# Scan with severity-based thresholds
trivy config ${VALIDATE_PATH} \
  --severity HIGH,CRITICAL \
  --exit-code 1 \
  --ignore-unfixed \
  --ignorefile .trivyignore

# Generate SBOM for compliance
trivy image --format cyclonedx --output sbom.json myimage:tag
```

**Checkov Configuration** (Trivy-IaC alternative):
```bash
# Multi-framework scanning
checkov -d ${VALIDATE_PATH} \
  --framework terraform,kubernetes,dockerfile \
  --quiet \
  --compact \
  --skip-check CKV_AWS_123  # Documented exceptions in policy file

# Compliance framework validation
checkov -d ${VALIDATE_PATH} --check CIS_AWS --output json
```

**Severity-Based Exit Codes**:
- `0`: All validations passed
- `1`: MEDIUM/LOW findings (deployable with warnings)
- `2`: CRITICAL/HIGH findings (deployment **blocked**)

**Validation Outputs**:
- `validation-report.json` - Machine-readable results
- `validation-summary.md` - Human-readable summary with remediation guidance
- `sbom.json` - Software Bill of Materials for incident response

**Invokes**: `iac-validator` agent with security-validation skill

---

### 4. deploy - Full Pipeline with Approval Gates
**Purpose**: Execute complete analysis → generation → validation → approval → deployment workflow.

**Usage**:
```bash
/iac deploy --repo . --target aws-eks --gitops argocd
/iac deploy --repo . --target gcp-gke --ci github-actions --dry-run
/iac deploy --repo . --target aws-eks --brownfield --require-approval
```

**Workflow**:
1. **Analyze** repository structure and dependencies (with brownfield context if flag set)
2. **Generate** IaC resources with AI-assisted validation and hallucination detection
3. **Validate** using two-phase validation (technical + intent)
4. **Human Approval** (if `--require-approval` or high-risk changes detected)
5. **Deploy** via GitOps or manual instructions (or show plan if --dry-run)

**Parameters**:
- `--repo`: Repository path (defaults to current directory)
- `--target`: Platform (**required**: `aws-eks`, `gcp-gke`, etc.)
- `--gitops`: GitOps tool (`argocd`, `flux`)
- `--ci`: Generate CI/CD pipeline
- `--dry-run`: Show plan without executing
- `--no-validate`: Skip validation stage (not recommended for production)
- `--brownfield`: Context injection from existing infrastructure
- `--gateway-api`: Use Gateway API v1 instead of Ingress
- `--require-approval`: Enforce human oversight for critical resources

**Human-in-the-Loop Governance**:

When `--require-approval` flag set or high-risk changes detected:

1. **Approval Required For**:
   - IAM role policies and permissions
   - Security group rules and network access
   - Encryption configuration changes
   - Database schema modifications
   - Production namespace deployments

2. **Approval Workflow**:
   - Generate change summary with risk assessment
   - Create approval checkpoint in CI/CD pipeline
   - Record approval in audit trail: `deployment-audit.json`
   - Proceed only after explicit human approval

3. **Audit Trail Format**:
```json
{
  "timestamp": "2026-02-03T23:00:00Z",
  "operation": "deploy",
  "target": "aws-eks",
  "ai_recommendations": [
    {
      "resource": "IAM Role Policy",
      "action": "Create",
      "risk_level": "HIGH",
      "reasoning": "Grants eks:DescribeCluster permission"
    }
  ],
  "human_review": {
    "reviewer": "ops-team",
    "approved": true,
    "timestamp": "2026-02-03T23:05:00Z",
    "notes": "Reviewed permissions - least privilege verified"
  }
}
```

**Invokes**: Orchestrates all three agents in sequence with approval gates

**Exit codes**:
- `0`: Pipeline completed successfully
- `1`: Completed with warnings
- `2`: Pipeline failed, blocked by validation, or approval denied

---

## Execution Logic

### Case: analyze

```markdown
**🔍 Analyzing repository**: ${REPO_PATH}

**Mode**: ${BROWNFIELD:+BROWNFIELD (context-aware)}${BROWNFIELD:-GREENFIELD (clean environment)}

**Pre-flight checks**:
- ✅ Repository exists and is accessible
- ✅ Read permissions verified
${BROWNFIELD:+- ✅ Terraform state file detected: \`terraform.tfstate\`}
${BROWNFIELD:+- ✅ Kubernetes context available for resource query}

---

**Invoking iac-analyzer agent...**

Use the Task tool to invoke the specialized agent:

<Task>
  subagent_type: general-purpose
  description: Analyze repository structure
  prompt: |
    You are the iac-analyzer agent. Analyze the repository at ${REPO_PATH}.

    **Analysis mode**: ${BROWNFIELD:+BROWNFIELD - Context injection enabled}${BROWNFIELD:-GREENFIELD - Assume clean environment}

    **Your objectives**:
    1. Detect application frameworks and programming languages
    2. Identify database dependencies (PostgreSQL, MySQL, MongoDB, Redis, etc.)
    3. Map service dependencies and network topology
    4. Identify deployment patterns and requirements
    5. Generate architecture recommendations

    ${BROWNFIELD:+**Brownfield context injection** (CRITICAL for avoiding AI hallucinations):}
    ${BROWNFIELD:+}
    ${BROWNFIELD:+1. **Read existing Terraform state**:}
    ${BROWNFIELD:+   \`\`\`bash}
    ${BROWNFIELD:+   # Extract deployed infrastructure context}
    ${BROWNFIELD:+   if [ -f "${REPO_PATH}/terraform.tfstate" ]; then}
    ${BROWNFIELD:+     terraform state list > existing-resources.txt}
    ${BROWNFIELD:+     terraform output -json > existing-outputs.json}
    ${BROWNFIELD:+   fi}
    ${BROWNFIELD:+   \`\`\`}
    ${BROWNFIELD:+}
    ${BROWNFIELD:+2. **Query existing Kubernetes resources**:}
    ${BROWNFIELD:+   \`\`\`bash}
    ${BROWNFIELD:+   # Get all deployed resources in cluster}
    ${BROWNFIELD:+   kubectl get all -A -o json > existing-k8s-resources.json}
    ${BROWNFIELD:+   kubectl get ingress,gateway,httproute -A -o json > existing-networking.json}
    ${BROWNFIELD:+   \`\`\`}
    ${BROWNFIELD:+}
    ${BROWNFIELD:+3. **Inject context into analysis**:}
    ${BROWNFIELD:+   - Note existing VPC IDs, subnet CIDRs, security group IDs}
    ${BROWNFIELD:+   - Record deployed service names and namespaces}
    ${BROWNFIELD:+   - Document existing Gateway API or Ingress configurations}
    ${BROWNFIELD:+   - Flag potential resource naming conflicts}

    **Output requirements**:
    - Create `iac-analysis.json` in repository root with:
      - detected_languages: List of languages and frameworks
      - services: Array of service definitions with dependencies
      - databases: Database configurations and connection patterns
      - network_topology: Service mesh and network requirements
      - recommendations: Platform-specific deployment recommendations
      ${BROWNFIELD:+- existing_infrastructure: Context from state files and K8s resources}
      ${BROWNFIELD:+- conflict_warnings: Potential naming or resource conflicts}

    **Analysis structure**:
    ```json
    {
      "analysis_version": "1.1",
      "analysis_mode": "${BROWNFIELD:+brownfield}${BROWNFIELD:-greenfield}",
      "repository": "${REPO_PATH}",
      "timestamp": "<ISO8601>",
      "detected_languages": [...],
      "services": [...],
      "databases": [...],
      "network_topology": {...},
      "recommendations": {...}
      ${BROWNFIELD:+,"existing_infrastructure": {}
      ${BROWNFIELD:+,"conflict_warnings": []}
    }
    ```

    After analysis, provide a summary of findings and next steps.
</Task>

---

**✅ Analysis complete!**

**Output files**:
- `${REPO_PATH}/iac-analysis.json` - Structured analysis data
- `${REPO_PATH}/architecture-diagram.md` - Visual architecture
${BROWNFIELD:+- \`${REPO_PATH}/existing-resources.txt\` - Current infrastructure inventory}
${BROWNFIELD:+- \`${REPO_PATH}/existing-k8s-resources.json\` - Deployed Kubernetes resources}

**Next steps**:
```bash
# Generate IaC resources from analysis
/iac generate --target aws-eks --gitops argocd ${BROWNFIELD:+--brownfield}

# Or view the analysis
cat ${REPO_PATH}/iac-analysis.json
```
```

---

### Case: generate

```markdown
**⚙️ Generating IaC resources for**: ${TARGET_PLATFORM}

**Configuration**:
- Repository: ${REPO_PATH}
- Platform: ${TARGET_PLATFORM}
- GitOps: ${GITOPS_TOOL:-none}
- CI/CD: ${CI_PLATFORM:-none}
- Helm mode: ${HELM_MODE}
- Brownfield mode: ${BROWNFIELD}
- Gateway API: ${GATEWAY_API}
- Require approval: ${REQUIRE_APPROVAL}

---

**Pre-flight security checks**:
```bash
# Check for sensitive files
if [ -f "${REPO_PATH}/.env" ]; then
  echo "⚠️  WARNING: .env file detected. Move secrets to .env.local (gitignored)"
  echo "   Create .env.example with placeholder values instead"
fi

# Check for hardcoded credentials (basic check)
if grep -rE "(password|api[_-]?key|secret|token)[\"']?\s*[:=]\s*[\"'][^\"']+[\"']" ${REPO_PATH} --include="*.yaml" --include="*.yml" 2>/dev/null | grep -v ".env.example" | head -1; then
  echo "❌ ERROR: Potential hardcoded credentials detected in YAML files"
  echo "   Use .env.example pattern or Kubernetes Secrets instead"
  exit 2
fi

# Verify Kubernetes version for native sidecars
if command -v kubectl >/dev/null 2>&1; then
  K8S_VERSION=$(kubectl version --short 2>/dev/null | grep "Server Version" | grep -oP 'v\K[0-9]+\.[0-9]+' || echo "0.0")
  K8S_MAJOR=$(echo $K8S_VERSION | cut -d. -f1)
  K8S_MINOR=$(echo $K8S_VERSION | cut -d. -f2)

  if [ "$K8S_MAJOR" -eq 1 ] && [ "$K8S_MINOR" -lt 29 ]; then
    echo "⚠️  WARNING: Kubernetes version $K8S_VERSION detected"
    echo "   Native sidecar containers require v1.29+. Will use traditional pattern."
  fi
fi

# Verify Terraform version for 1.7+ features
if command -v terraform >/dev/null 2>&1; then
  TF_VERSION=$(terraform version -json 2>/dev/null | grep -oP '"terraform_version":\s*"\K[0-9]+\.[0-9]+' || echo "0.0")
  TF_MAJOR=$(echo $TF_VERSION | cut -d. -f1)
  TF_MINOR=$(echo $TF_VERSION | cut -d. -f2)

  if [ "$TF_MAJOR" -eq 1 ] && [ "$TF_MINOR" -lt 7 ]; then
    echo "⚠️  WARNING: Terraform version $TF_VERSION detected"
    echo "   Import for_each and native testing require v1.7+. Features disabled."
  fi
fi

# Verify required tools
case ${TARGET_PLATFORM} in
  aws-eks|gcp-gke|kubernetes)
    command -v kubectl >/dev/null 2>&1 || echo "⚠️  WARNING: kubectl not found - install for validation"
    [ "${HELM_MODE}" = "true" ] && command -v helm >/dev/null 2>&1 || echo "⚠️  WARNING: helm not found - install for chart generation"
    [ "${GATEWAY_API}" = "true" ] && echo "ℹ️  INFO: Gateway API mode enabled - will use HTTPRoute instead of Ingress"
    ;;
  terraform)
    command -v terraform >/dev/null 2>&1 || echo "⚠️  WARNING: terraform not found - install for generation"
    ;;
esac

echo "✅ Security checks passed"
```

---

**Invoking iac-generator agent...**

<Task>
  subagent_type: general-purpose
  description: Generate IaC resources
  prompt: |
    You are the iac-generator agent. Generate production-ready IaC resources for ${TARGET_PLATFORM} with AI-assisted validation.

    **Context**:
    - Repository: ${REPO_PATH}
    - Target platform: ${TARGET_PLATFORM}
    - GitOps tool: ${GITOPS_TOOL:-none}
    - CI/CD platform: ${CI_PLATFORM:-none}
    - Helm mode: ${HELM_MODE}
    - Brownfield mode: ${BROWNFIELD}
    - Gateway API mode: ${GATEWAY_API}
    - Require approval: ${REQUIRE_APPROVAL}

    **Read analysis** (if exists):
    - File: ${REPO_PATH}/iac-analysis.json
    - Use detected services, languages, dependencies
    ${BROWNFIELD:+- CRITICAL: Read existing_infrastructure section to avoid conflicts}

    **AI-Assisted Generation (2026 best practices)**:

    1. **Hallucination Detection and Prevention**:
       - Validate ALL Terraform resource types against official provider schemas before acceptance
       - Check module sources against verified registries: https://registry.terraform.io
       - For Kubernetes resources, validate against API server: \`kubectl explain <resource>\`
       - Flag any unverifiable dependencies for human review
       - Never generate resource types or attributes not in official documentation

    2. **Context Injection** (when brownfield mode enabled):
       ${BROWNFIELD:+- Read \`${REPO_PATH}/iac-analysis.json\` existing_infrastructure section}
       ${BROWNFIELD:+- Use actual VPC IDs, subnet IDs, security group IDs from state}
       ${BROWNFIELD:+- Avoid naming conflicts with existing resources}
       ${BROWNFIELD:+- Align with deployed Kubernetes resources (namespaces, services)}
       ${BROWNFIELD:+- Generate Terraform \`import\` blocks for existing resources using for_each}

    3. **Human-in-the-Loop Governance** (when require-approval enabled):
       ${REQUIRE_APPROVAL:+- Flag high-risk resources for review: IAM policies, security groups, encryption}
       ${REQUIRE_APPROVAL:+- Generate approval checkpoints in CI/CD pipelines}
       ${REQUIRE_APPROVAL:+- Create audit trail in \`generation-audit.json\` with reasoning}
       ${REQUIRE_APPROVAL:+- Add comments in generated code explaining AI decisions}

    **Generation requirements**:

    1. **Containerization** (`./docker/`):
       - Multi-stage Dockerfile for each service
       - Security hardening (non-root user, minimal base image)
       - .dockerignore with security exclusions
       - Trivy-compatible security contexts

    2. **Kubernetes/Helm** (`./kubernetes/`):

       **Standard resources**:
       - Deployments with resource limits (requests and limits)
       - Health checks: startupProbe, livenessProbe, readinessProbe
       - Security contexts: runAsNonRoot, readOnlyRootFilesystem, seccompProfile
       - Services with appropriate types (ClusterIP, LoadBalancer)
       - ConfigMaps for configuration
       - Secret manifests (encrypted, no hardcoded values)

       **Native Sidecar Containers** (Kubernetes 1.29+):
       \`\`\`yaml
       # Use restartPolicy: Always on init containers for sidecars
       initContainers:
         - name: logging-sidecar
           image: fluent/fluent-bit:latest
           restartPolicy: Always  # Makes it a native sidecar
           startupProbe:  # Signal sidecar is ready
             httpGet:
               path: /api/v1/health
               port: 2020
             failureThreshold: 30
             periodSeconds: 10
       \`\`\`

       **Gateway API v1** (if ${GATEWAY_API} enabled, K8s 1.31+):
       \`\`\`yaml
       # Replace Ingress with Gateway + HTTPRoute
       apiVersion: gateway.networking.k8s.io/v1
       kind: Gateway
       metadata:
         name: production-gateway
       spec:
         gatewayClassName: nginx  # Or envoy, istio, etc.
         listeners:
           - name: https
             protocol: HTTPS
             port: 443
             tls:
               mode: Terminate
               certificateRefs:
                 - name: tls-cert  # Same namespace only
       ---
       apiVersion: gateway.networking.k8s.io/v1
       kind: HTTPRoute
       metadata:
         name: app-route
       spec:
         parentRefs:
           - name: production-gateway
         rules:
           - matches:
               - path:
                   type: PathPrefix
                   value: /api
             backendRefs:
               - name: api-service
                 port: 8080
       \`\`\`

       **BackendTLSPolicy** (TLS to backend):
       \`\`\`yaml
       apiVersion: gateway.networking.k8s.io/v1alpha3
       kind: BackendTLSPolicy
       metadata:
         name: backend-tls
       spec:
         targetRefs:
           - name: api-service  # Single targetRef for clear status
             kind: Service
         validation:
           caCertificateRefs:
             - name: backend-ca-cert
               kind: ConfigMap
           hostname: api.internal.example.com
       \`\`\`

       ${HELM_MODE:+**Helm Chart Structure**:}
       ${HELM_MODE:+\`\`\`}
       ${HELM_MODE:+kubernetes/myapp-chart/}
       ${HELM_MODE:+├── Chart.yaml}
       ${HELM_MODE:+├── values.yaml          # Default values}
       ${HELM_MODE:+├── values-dev.yaml      # Environment-specific}
       ${HELM_MODE:+├── values-staging.yaml}
       ${HELM_MODE:+├── values-prod.yaml}
       ${HELM_MODE:+└── templates/}
       ${HELM_MODE:+    ├── deployment.yaml}
       ${HELM_MODE:+    ├── service.yaml}
       ${HELM_MODE:+    ├── ${GATEWAY_API:+httproute.yaml}${GATEWAY_API:-ingress.yaml}}
       ${HELM_MODE:+    └── tests/}
       ${HELM_MODE:+\`\`\`}

    3. **Terraform** (`./terraform/`) - if ${TARGET_PLATFORM} includes aws/gcp:

       **Modern Terraform 1.7+ Features**:

       **Import blocks with for_each** (multi-resource imports):
       \`\`\`hcl
       # Import existing Kubernetes namespaces
       variable "existing_namespaces" {
         type = map(object({
           name = string
         }))
         default = {
           "prod"    = { name = "production" }
           "staging" = { name = "staging" }
           "dev"     = { name = "development" }
         }
       }

       import {
         for_each = var.existing_namespaces
         to       = kubernetes_namespace.environments[each.key]
         id       = each.value.name
       }

       resource "kubernetes_namespace" "environments" {
         for_each = var.existing_namespaces
         metadata {
           name = each.value.name
         }
       }
       \`\`\`

       **Native test framework** (tests/main.tftest.hcl):
       \`\`\`hcl
       # Unit tests with mock providers
       mock_provider "aws" {
         override_resource {
           target = aws_instance.example
           values = {
             ami           = "ami-12345678"  # Meaningful mock values
             instance_type = "t3.micro"
             tags = {
               Name = "test-instance"
             }
           }
         }
       }

       run "unit_test_instance_config" {
         command = plan  # No API calls

         assert {
           condition     = aws_instance.example.instance_type == "t3.micro"
           error_message = "Instance type must be t3.micro"
         }
       }

       # Integration tests with real infrastructure
       run "integration_test_deployment" {
         command = apply  # Actually provisions resources

         assert {
           condition     = aws_instance.example.state == "running"
           error_message = "Instance must be in running state"
         }
       }
       # Resources automatically cleaned up after test
       \`\`\`

       **Standard Infrastructure Modules**:
       - VPC/network modules with cost-optimized CIDR allocation
       - EKS/GKE cluster with Spot instance support:
         \`\`\`hcl
         # AWS EKS with Spot instances (66-90% cost savings)
         eks_managed_node_groups = {
           spot = {
             capacity_type  = "SPOT"
             instance_types = ["t3.medium", "t3a.medium", "t3.large", "t3a.large"]  # Diversification

             min_size     = 2
             max_size     = 10
             desired_size = 3

             # Spot allocation strategy
             use_mixed_instances_policy = true
             mixed_instances_policy = {
               instances_distribution = {
                 on_demand_base_capacity                  = 1  # 20-40% On-Demand for reliability
                 on_demand_percentage_above_base_capacity = 20
                 spot_allocation_strategy                 = "price-capacity-optimized"
               }
             }

             # Handle interruptions
             tags = {
               "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/lifecycle" = "spot"
             }
           }
         }
         \`\`\`
       - RDS/CloudSQL with encryption and right-sizing
       - IAM roles with IRSA/Workload Identity (OIDC)
       - Security groups with least privilege

    4. **CI/CD** (`./github/workflows/` or `.gitlab-ci.yml`) - if ${CI_PLATFORM} set:

       **OIDC Authentication** (NO long-lived credentials):
       \`\`\`yaml
       # GitHub Actions with OIDC
       jobs:
         deploy:
           runs-on: ubuntu-latest
           permissions:
             id-token: write  # Required for OIDC token request
             contents: read
           steps:
             - uses: aws-actions/configure-aws-credentials@v4
               with:
                 role-to-assume: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
                 aws-region: us-east-1
                 role-session-name: GitHubActions-\${{ github.run_id }}
       \`\`\`

       **IAM Trust Policy** (restrictive):
       \`\`\`json
       {
         "Version": "2012-10-17",
         "Statement": [{
           "Effect": "Allow",
           "Principal": {"Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"},
           "Action": "sts:AssumeRoleWithWebIdentity",
           "Condition": {
             "StringEquals": {
               "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
               "token.actions.githubusercontent.com:sub": "repo:ORG/REPO:ref:refs/heads/main"
             }
           }
         }]
       }
       \`\`\`

       **Reusable Workflows** (centralized patterns):
       \`\`\`yaml
       # .github/workflows/deploy-reusable.yml
       name: Reusable Deployment Workflow
       on:
         workflow_call:
           inputs:
             environment:
               required: true
               type: string
           secrets:
             CLUSTER_NAME:
               required: true

       jobs:
         deploy:
           runs-on: ubuntu-latest
           steps:
             - name: Deploy to \${{ inputs.environment }}
               run: kubectl apply -f k8s/

       # Caller workflow - pin to SHA or tag
       jobs:
         production:
           uses: org/workflows/.github/workflows/deploy-reusable.yml@v1.2.3  # Pinned version
           with:
             environment: production
           secrets:
             CLUSTER_NAME: \${{ secrets.PROD_CLUSTER }}
       \`\`\`

       **Matrix Optimization** (parallel testing):
       \`\`\`yaml
       strategy:
         fail-fast: true  # Cancel remaining on first failure
         matrix:
           include:
             - os: ubuntu-latest
               k8s-version: "1.31"
             - os: ubuntu-latest
               k8s-version: "1.30"
           # Use exclude for invalid combinations
       \`\`\`

       **Security Scanning**:
       \`\`\`yaml
       - name: Security Scan
         run: |
           # Update Trivy database
           trivy image --download-db-only

           # Scan with severity thresholds
           trivy config . \\
             --severity HIGH,CRITICAL \\
             --exit-code 1 \\
             --ignore-unfixed \\
             --ignorefile .trivyignore

           # Generate SBOM
           trivy image --format cyclonedx --output sbom.json myimage:tag
       \`\`\`

       ${REQUIRE_APPROVAL:+**Approval Gate** (human-in-the-loop):}
       ${REQUIRE_APPROVAL:+\`\`\`yaml}
       ${REQUIRE_APPROVAL:+- name: Request Approval}
       ${REQUIRE_APPROVAL:+  uses: trstringer/manual-approval@v1}
       ${REQUIRE_APPROVAL:+  with:}
       ${REQUIRE_APPROVAL:+    approvers: ops-team,security-team}
       ${REQUIRE_APPROVAL:+    minimum-approvals: 1}
       ${REQUIRE_APPROVAL:+    issue-title: "Deploy to Production"}
       ${REQUIRE_APPROVAL:+\`\`\`}

    5. **GitOps** (`./gitops/`) - if ${GITOPS_TOOL} set:

       **ArgoCD Application**:
       \`\`\`yaml
       apiVersion: argoproj.io/v1alpha1
       kind: Application
       metadata:
         name: myapp
         namespace: argocd
       spec:
         project: default
         source:
           repoURL: https://github.com/org/repo
           targetRevision: HEAD
           path: kubernetes/
         destination:
           server: https://kubernetes.default.svc
           namespace: production
         syncPolicy:
           automated:
             prune: true
             selfHeal: true
           syncOptions:
             - CreateNamespace=true
       \`\`\`

       **Flux Kustomization** (with OCI image source):
       \`\`\`yaml
       apiVersion: source.toolkit.fluxcd.io/v1
       kind: OCIRepository
       metadata:
         name: myapp
         namespace: flux-system
       spec:
         interval: 5m
         url: oci://ghcr.io/org/myapp-manifests
         ref:
           tag: latest
       ---
       apiVersion: kustomize.toolkit.fluxcd.io/v1
       kind: Kustomization
       metadata:
         name: myapp
         namespace: flux-system
       spec:
         interval: 10m
         sourceRef:
           kind: OCIRepository
           name: myapp
         path: ./
         prune: true
         wait: true
         timeout: 5m
       \`\`\`

    **Security constraints** (MUST enforce):
    - ❌ NO hardcoded secrets (use .env.example → .env.local pattern)
    - ✅ OIDC for CI/CD (no AWS_ACCESS_KEY_ID or long-lived tokens)
    - ✅ Kubernetes manifests MUST pass: \`kubectl apply --dry-run=server\`
    - ✅ Helm charts MUST pass: \`helm lint --strict\`
    - ✅ All images use specific tags (no :latest)
    - ✅ Container security contexts (runAsNonRoot, readOnlyRootFilesystem)
    - ✅ Validate ALL resource types against provider schemas (hallucination prevention)
    - ✅ Trivy scanning with .trivyignore for documented exceptions
    - ✅ Severity-based failure thresholds (fail on CRITICAL/HIGH only)

    **Cost Optimization** (embedded in generated resources):
    - Spot instances with price-capacity-optimized allocation (66-90% savings)
    - Resource right-sizing with CPU limits at 40-70% target utilization
    - Auto-scaling policies for variable workloads
    - Scheduled shutdown for non-production (70% savings)
    - ${BROWNFIELD:+Reserved Instance/Savings Plan recommendations based on existing usage}

    **After generation**:
    - Validate all manifests locally before outputting
    - Create README.md in each directory explaining usage
    - Generate .trivyignore template for security exceptions
    - ${REQUIRE_APPROVAL:+Create generation-audit.json with AI decisions and risk assessments}
    - Log summary of generated files and any hallucination warnings
</Task>

---

**✅ Generation complete!**

**Generated structure**:
```
${REPO_PATH}/
├── docker/
│   ├── Dockerfile
│   └── .dockerignore
├── kubernetes/
│   ├── deployment.yaml  # Native sidecars if K8s 1.29+
│   ├── service.yaml
│   ├── ${GATEWAY_API:+httproute.yaml}${GATEWAY_API:-ingress.yaml}  # Gateway API or Ingress
${GATEWAY_API:+│   ├── gateway.yaml}
${GATEWAY_API:+│   └── backendtlspolicy.yaml}
│   ├── configmap.yaml
│   └── secret.yaml (template - populate from .env)
${HELM_MODE:+│   └── helm-chart/}
${HELM_MODE:+│       ├── Chart.yaml}
${HELM_MODE:+│       ├── values.yaml}
${HELM_MODE:+│       ├── values-dev.yaml}
${HELM_MODE:+│       ├── values-staging.yaml}
${HELM_MODE:+│       ├── values-prod.yaml}
${HELM_MODE:+│       └── templates/}
├── terraform/
│   ├── main.tf  # Spot instances, right-sizing, cost optimization
│   ├── variables.tf
│   ├── outputs.tf
│   ├── import.tf  # Import blocks with for_each (TF 1.7+)
│   ├── modules/
│   └── tests/
│       └── main.tftest.hcl  # Native test framework
├── .trivyignore  # Template for security exceptions
${CI_PLATFORM:+├── .github/workflows/  (or .gitlab-ci.yml)}
${CI_PLATFORM:+│   ├── deploy.yaml  # OIDC auth, reusable workflows}
${CI_PLATFORM:+│   └── security-scan.yaml  # Trivy with severity thresholds}
${GITOPS_TOOL:+└── gitops/}
${GITOPS_TOOL:+    ├── application.yaml  # ArgoCD or Flux}
${GITOPS_TOOL:+    └── kustomization.yaml}
${REQUIRE_APPROVAL:+└── generation-audit.json  # AI decisions and risk assessments}
```

**Next steps**:
```bash
# Validate generated resources (two-phase: technical + intent)
/iac validate --all

# Review modern features
${GATEWAY_API:+cat ${REPO_PATH}/kubernetes/httproute.yaml  # Gateway API v1}
cat ${REPO_PATH}/terraform/import.tf  # Import blocks with for_each
cat ${REPO_PATH}/terraform/tests/main.tftest.hcl  # Native tests

# Review cost optimization
grep -A 10 "capacity_type.*SPOT" ${REPO_PATH}/terraform/main.tf

${REQUIRE_APPROVAL:+# Review AI decisions and risk assessments}
${REQUIRE_APPROVAL:+cat ${REPO_PATH}/generation-audit.json}
```
```

---

### Case: validate

```markdown
**🔒 Multi-Phase Validation**: ${VALIDATE_PATH}

**Validation architecture**: Two-phase (technical + intent)
**Mode**: ${STRICT_MODE:+STRICT (fail on HIGH+)}${STRICT_MODE:-STANDARD (fail on CRITICAL only)}

---

**Pre-validation checks**:
```bash
# Update Trivy database (prevent false positives)
echo "Updating vulnerability databases..."
trivy image --download-db-only

# Verify tools available
VALIDATORS_AVAILABLE=0
command -v trivy >/dev/null 2>&1 && VALIDATORS_AVAILABLE=$((VALIDATORS_AVAILABLE + 1)) || echo "⚠️  trivy not found - container scanning disabled"
command -v checkov >/dev/null 2>&1 && VALIDATORS_AVAILABLE=$((VALIDATORS_AVAILABLE + 1)) || echo "⚠️  checkov not found - IaC scanning disabled"
command -v kubectl >/dev/null 2>&1 && VALIDATORS_AVAILABLE=$((VALIDATORS_AVAILABLE + 1)) || echo "⚠️  kubectl not found - K8s validation disabled"
command -v conftest >/dev/null 2>&1 && echo "✅ OPA conftest available - policy validation enabled" || echo "ℹ️  conftest not found - OPA validation skipped"

if [ $VALIDATORS_AVAILABLE -eq 0 ]; then
  echo "❌ ERROR: No security validators available"
  echo "   Install at least one: trivy, checkov, kubectl"
  exit 2
fi

echo "✅ Found $VALIDATORS_AVAILABLE validator(s)"
```

---

**Invoking iac-validator agent...**

<Task>
  subagent_type: general-purpose
  description: Multi-phase IaC validation
  prompt: |
    You are the iac-validator agent. Perform comprehensive two-phase validation (technical + intent).

    **Validation scope**: ${VALIDATE_ALL:+All generated resources}${VALIDATE_ALL:-${VALIDATE_PATH}}
    **Strict mode**: ${STRICT_MODE} (${STRICT_MODE:+Fail on HIGH+}${STRICT_MODE:-Fail on CRITICAL only})

    **PHASE 1: Technical Validation** (syntax, security, configuration)

    1. **Container Security** (Trivy - 2026 best practices):
       \`\`\`bash
       # Database already updated in pre-validation

       # Scan Dockerfiles with severity-based thresholds
       trivy config ${VALIDATE_PATH}/docker/ \\
         --severity ${STRICT_MODE:+HIGH,CRITICAL}${STRICT_MODE:-CRITICAL} \\
         --exit-code 1 \\
         --ignore-unfixed \\
         --ignorefile ${VALIDATE_PATH}/.trivyignore

       # Scan container images if built
       if docker images | grep -q "myapp"; then
         trivy image \\
           --severity ${STRICT_MODE:+HIGH,CRITICAL}${STRICT_MODE:-CRITICAL} \\
           --exit-code 1 \\
           --ignore-unfixed \\
           myapp:latest

         # Generate SBOM for compliance
         trivy image --format cyclonedx --output ${VALIDATE_PATH}/sbom.json myapp:latest
       fi
       \`\`\`

    2. **Infrastructure Security** (Checkov - replaces tfsec):
       \`\`\`bash
       # Multi-framework scanning
       checkov -d ${VALIDATE_PATH} \\
         --framework terraform,kubernetes,dockerfile \\
         --quiet \\
         --compact \\
         ${STRICT_MODE:+--hard-fail-on HIGH,CRITICAL}${STRICT_MODE:---hard-fail-on CRITICAL} \\
         --output json --output-file ${VALIDATE_PATH}/checkov-report.json

       # Compliance framework validation
       checkov -d ${VALIDATE_PATH}/terraform/ \\
         --framework terraform \\
         --check CIS_AWS \\
         --output cli
       \`\`\`

    3. **Kubernetes Validation**:
       \`\`\`bash
       # Syntax validation with API server
       kubectl apply --dry-run=server -f ${VALIDATE_PATH}/kubernetes/ 2>&1

       # Gateway API validation (if present)
       if [ -f "${VALIDATE_PATH}/kubernetes/gateway.yaml" ]; then
         # Check Gateway status conditions
         kubectl explain Gateway.status.conditions

         # Validate HTTPRoute backend references
         kubectl apply --dry-run=server -f ${VALIDATE_PATH}/kubernetes/httproute.yaml

         # Verify BackendTLSPolicy configuration
         if [ -f "${VALIDATE_PATH}/kubernetes/backendtlspolicy.yaml" ]; then
           # Ensure either CACertificateRefs OR WellKnownCACertificates is set
           grep -q "caCertificateRefs\\|wellKnownCACertificates" ${VALIDATE_PATH}/kubernetes/backendtlspolicy.yaml || echo "❌ ERROR: BackendTLSPolicy missing CA configuration"
         fi
       fi

       # Native sidecar validation (K8s 1.29+)
       if grep -q "restartPolicy: Always" ${VALIDATE_PATH}/kubernetes/deployment.yaml; then
         K8S_VERSION=$(kubectl version --short 2>/dev/null | grep "Server Version" | grep -oP 'v\K[0-9]+\.[0-9]+' || echo "0.0")
         if [[ "$K8S_VERSION" < "1.29" ]]; then
           echo "❌ ERROR: Native sidecars require Kubernetes 1.29+, detected $K8S_VERSION"
           exit 2
         fi
       fi

       # Security context validation
       checkov -f ${VALIDATE_PATH}/kubernetes/deployment.yaml \\
         --framework kubernetes \\
         --check CKV_K8S_40,CKV_K8S_43  # runAsNonRoot, readOnlyRootFilesystem
       \`\`\`

    4. **Helm Chart Validation** (if present):
       \`\`\`bash
       if [ -d "${VALIDATE_PATH}/kubernetes/"*"-chart" ]; then
         # Strict linting
         helm lint ${VALIDATE_PATH}/kubernetes/*/  --strict

         # Template rendering validation
         helm template test ${VALIDATE_PATH}/kubernetes/*/ | kubectl apply --dry-run=server -f - 2>&1
       fi
       \`\`\`

    5. **Terraform Validation**:
       \`\`\`bash
       if [ -d "${VALIDATE_PATH}/terraform/" ]; then
         cd ${VALIDATE_PATH}/terraform/

         # Initialize without backend
         terraform init -backend=false

         # Syntax validation
         terraform validate

         # Run native tests (Terraform 1.7+)
         if [ -d "tests/" ]; then
           terraform test
         fi

         # Planning (dry-run)
         terraform plan -out=plan.tfplan 2>&1

         # Verify version constraints
         if grep -q "for_each" import.tf 2>/dev/null; then
           TF_VERSION=$(terraform version -json | grep -oP '"terraform_version":\s*"\K[0-9]+\.[0-9]+')
           if [[ "$TF_VERSION" < "1.7" ]]; then
             echo "❌ ERROR: Import for_each requires Terraform 1.7+, detected $TF_VERSION"
             exit 2
           fi
         fi
       fi
       \`\`\`

    6. **Secret Detection**:
       \`\`\`bash
       # Pattern-based detection
       SECRETS_FOUND=$(grep -rE "(password|api[_-]?key|secret|token)[\"']?\s*[:=]\s*[\"'][^\"']+[\"']" ${VALIDATE_PATH} \\
         --include="*.yaml" --include="*.yml" --include="*.tf" \\
         --exclude="*.example*" --exclude="*template*" \\
         --exclude=".trivyignore" 2>/dev/null | wc -l)

       if [ $SECRETS_FOUND -gt 0 ]; then
         echo "❌ CRITICAL: $SECRETS_FOUND potential hardcoded secrets detected"
         exit 2
       fi

       # Trivy secret scanning
       trivy fs ${VALIDATE_PATH} \\
         --scanners secret \\
         --exit-code 2
       \`\`\`

    **PHASE 2: Intent Validation** (semantic, policy, compliance)

    1. **OPA/Rego Policy Validation** (if conftest available):
       \`\`\`bash
       # Validate against organizational policies
       if command -v conftest >/dev/null 2>&1; then
         conftest test ${VALIDATE_PATH}/kubernetes/ \\
           --policy /path/to/policies/ \\
           --all-namespaces

         conftest test ${VALIDATE_PATH}/terraform/ \\
           --policy /path/to/policies/
       fi
       \`\`\`

    2. **Dependency Graph Validation**:
       - Verify Terraform resource dependencies match intended architecture
       - Check Kubernetes Service → Deployment → Pod relationships
       - Validate Gateway API HTTPRoute → Service backend references
       - Ensure IAM role trust relationships align with security requirements

    3. **Compliance Framework Checks**:
       \`\`\`bash
       # CIS Benchmark validation
       checkov -d ${VALIDATE_PATH} --check CIS_AWS --output cli

       # PCI-DSS compliance (if applicable)
       checkov -d ${VALIDATE_PATH} --framework terraform --check PCI_DSS

       # GDPR data protection checks (if applicable)
       checkov -d ${VALIDATE_PATH} --framework kubernetes --check GDPR
       \`\`\`

    4. **Cost Optimization Validation**:
       - Verify Spot instance allocation strategies are diversified (4+ types, 4+ AZs)
       - Check CPU resource limits target 40-70% utilization
       - Validate auto-scaling policies are configured
       - Ensure non-production resources have scheduling/right-sizing

    **Severity Classification**:
    - **CRITICAL**: Hardcoded secrets, public admin access, no encryption, hallucinated resources
    - **HIGH**: Missing security contexts, overly permissive IAM, no TLS, unverified modules
    - **MEDIUM**: Missing resource limits, no health checks, suboptimal cost settings
    - **LOW**: Style violations, non-critical warnings

    **Blocking Conditions** (exit code 2):
    - Any CRITICAL findings
    - ${STRICT_MODE:+Any HIGH findings}
    - Hardcoded secrets detected
    - Kubernetes validation failures (kubectl --dry-run=server)
    - Terraform plan errors
    - Helm lint failures (with --strict)
    - Gateway API configuration errors (missing CA certs, invalid routes)
    - Version incompatibilities (K8s < 1.29 with native sidecars, TF < 1.7 with for_each imports)
    - Hallucinated resource types or modules not in official registries

    **Output Format**:
    ```
    ═══════════════════════════════════════════════════════════
    PHASE 1: TECHNICAL VALIDATION
    ═══════════════════════════════════════════════════════════

    Container Security (Trivy):
    ✅ PASSED: No critical vulnerabilities in Dockerfiles
    ℹ️  INFO: SBOM generated at ${VALIDATE_PATH}/sbom.json

    Infrastructure Security (Checkov):
    ✅ PASSED: 47/50 checks passed
    ⚠️  WARNING: 3 MEDIUM findings (resource limits, health checks)

    Kubernetes Validation:
    ✅ PASSED: All manifests valid (kubectl --dry-run=server)
    ✅ PASSED: Gateway API configuration valid
    ✅ PASSED: Native sidecar containers compatible with K8s 1.31

    Terraform Validation:
    ✅ PASSED: Syntax valid (terraform validate)
    ✅ PASSED: All tests passed (terraform test)
    ✅ PASSED: Plan generated successfully

    Secret Detection:
    ✅ PASSED: No hardcoded credentials detected

    ═══════════════════════════════════════════════════════════
    PHASE 2: INTENT VALIDATION
    ═══════════════════════════════════════════════════════════

    Policy Compliance (OPA):
    ✅ PASSED: All organizational policies satisfied

    Dependency Graph:
    ✅ PASSED: Resource relationships match architecture

    Compliance Frameworks:
    ✅ PASSED: CIS AWS Foundations Benchmark
    ⚠️  INFO: PCI-DSS checks skipped (not applicable)

    Cost Optimization:
    ✅ PASSED: Spot instances properly diversified (4 types, 3 AZs)
    ✅ PASSED: Resource limits target 50-70% utilization
    ⚠️  WARNING: Auto-scaling not configured for production workload

    ═══════════════════════════════════════════════════════════
    VALIDATION SUMMARY
    ═══════════════════════════════════════════════════════════

    ✅ PASSED: 28 checks
    ⚠️  WARNINGS: 4 findings (severity: MEDIUM/LOW)
    ❌ FAILURES: 0 findings

    MEDIUM FINDINGS:
    1. Deployment 'api-deployment' missing resource limits (CPU/memory)
    2. Service 'frontend-service' missing health check annotations
    3. Auto-scaling policy not configured for 'backend-deployment'

    RECOMMENDATIONS:
    1. Add resource requests/limits to all Deployments
    2. Configure HorizontalPodAutoscaler for production workloads
    3. Add startupProbe/livenessProbe/readinessProbe to all containers

    EXIT CODE: 1 (Warnings present - review before production deployment)
    ```

    Generate detailed validation report in both JSON (machine-readable) and Markdown (human-readable) formats.
</Task>

---

**Validation results displayed above**

**Exit Code Interpretation**:
- `0` = ✅ All validations passed - safe to deploy
- `1` = ⚠️  Warnings present - review before deploying
- `2` = ❌ Critical issues found - **DO NOT DEPLOY**

**Generated Reports**:
- `${VALIDATE_PATH}/validation-report.json` - Machine-readable results
- `${VALIDATE_PATH}/validation-summary.md` - Human-readable summary
- `${VALIDATE_PATH}/sbom.json` - Software Bill of Materials
- `${VALIDATE_PATH}/checkov-report.json` - Detailed Checkov findings

**If validation fails**:
```bash
# Review detailed findings
cat ${VALIDATE_PATH}/validation-summary.md

# Fix critical issues
# - Remove hardcoded secrets
# - Add missing security contexts
# - Fix Gateway API configurations

# Re-validate with strict mode
/iac validate --path ${VALIDATE_PATH} --strict

# Or regenerate with corrections
/iac generate --target ${TARGET_PLATFORM} --repo .
```
```

---

### Case: deploy

```markdown
**🚀 Full IaC Pipeline with Governance**

**Configuration**:
- Repository: ${REPO_PATH}
- Target: ${TARGET_PLATFORM}
- GitOps: ${GITOPS_TOOL:-manual}
- CI/CD: ${CI_PLATFORM:-manual}
- Dry run: ${DRY_RUN}
- Validation: ${SKIP_VALIDATION:+DISABLED}${SKIP_VALIDATION:-ENABLED}
- Brownfield mode: ${BROWNFIELD}
- Gateway API: ${GATEWAY_API}
- Require approval: ${REQUIRE_APPROVAL}

---

## Pipeline Execution

### Stage 1/5: Analysis

**Status**: 🔍 Analyzing repository structure...

<Task>
  subagent_type: general-purpose
  description: Analyze repository with context
  prompt: |
    You are the iac-analyzer agent. Analyze ${REPO_PATH} with ${BROWNFIELD:+brownfield context awareness}${BROWNFIELD:-greenfield assumptions}.

    Follow the analysis protocol from the 'analyze' operation.

    ${BROWNFIELD:+**CRITICAL**: Read terraform.tfstate and query Kubernetes resources for context injection.}

    **Output**: iac-analysis.json with detected services, languages, dependencies${BROWNFIELD:+, and existing infrastructure context}.
</Task>

**✅ Stage 1 complete** - Analysis saved to `iac-analysis.json`

---

### Stage 2/5: Generation

**Status**: ⚙️ Generating IaC resources for ${TARGET_PLATFORM}...

<Task>
  subagent_type: general-purpose
  description: Generate IaC with AI validation
  prompt: |
    You are the iac-generator agent. Generate production-ready resources for ${TARGET_PLATFORM} with AI-assisted validation.

    **Context**:
    - Analysis file: ${REPO_PATH}/iac-analysis.json (read this first)
    - Target: ${TARGET_PLATFORM}
    - GitOps: ${GITOPS_TOOL}
    - CI/CD: ${CI_PLATFORM}
    - Helm: ${HELM_MODE}
    - Brownfield: ${BROWNFIELD}
    - Gateway API: ${GATEWAY_API}
    - Require approval: ${REQUIRE_APPROVAL}

    Follow the generation protocol from the 'generate' operation.

    **CRITICAL**:
    - Validate ALL resource types against provider schemas (hallucination prevention)
    - ${BROWNFIELD:+Inject context from existing_infrastructure section in analysis}
    - ${REQUIRE_APPROVAL:+Flag high-risk resources and create approval gates}
    - Use modern K8s 1.31+ and Terraform 1.7+ features
    - Implement OIDC authentication for CI/CD
    - Configure Spot instances with proper diversification
    - ${GATEWAY_API:+Use Gateway API v1 instead of Ingress}

    **Output**: IaC resources in docker/, kubernetes/, terraform/, gitops/ directories${REQUIRE_APPROVAL:+ plus generation-audit.json}.
</Task>

**✅ Stage 2 complete** - Resources generated in respective directories

---

### Stage 3/5: Validation

${SKIP_VALIDATION:+**Status**: ⏭️  SKIPPED (--no-validate flag set)}
${SKIP_VALIDATION:+}
${SKIP_VALIDATION:+⚠️  **WARNING**: Skipping validation is not recommended for production deployments.}
${SKIP_VALIDATION:+Security issues, hallucinated resources, or configuration errors may exist.}

${SKIP_VALIDATION:-**Status**: 🔒 Multi-phase validation (technical + intent)...}
${SKIP_VALIDATION:-}
${SKIP_VALIDATION:-<Task>}
${SKIP_VALIDATION:-  subagent_type: general-purpose}
${SKIP_VALIDATION:-  description: Two-phase IaC validation}
${SKIP_VALIDATION:-  prompt: |}
${SKIP_VALIDATION:-    You are the iac-validator agent. Perform two-phase validation (technical + intent).}
${SKIP_VALIDATION:-    }
${SKIP_VALIDATION:-    Follow the validation protocol from the 'validate' operation.}
${SKIP_VALIDATION:-    }
${SKIP_VALIDATION:-    **Phase 1**: Technical validation (syntax, security, configuration)}
${SKIP_VALIDATION:-    **Phase 2**: Intent validation (semantic, policy, compliance)}
${SKIP_VALIDATION:-    }
${SKIP_VALIDATION:-    **CRITICAL**: Block deployment if CRITICAL or ${STRICT_MODE:+HIGH} findings detected.}
${SKIP_VALIDATION:-    }
${SKIP_VALIDATION:-    Generate validation-report.json and validation-summary.md.}
${SKIP_VALIDATION:-    Exit code 2 will abort the pipeline.}
${SKIP_VALIDATION:-</Task>}
${SKIP_VALIDATION:-}
${SKIP_VALIDATION:-**✅ Stage 3 complete** - Validation passed, proceeding to approval stage}

---

### Stage 4/5: Human Approval

${REQUIRE_APPROVAL:+**Status**: 👥 Human oversight required for deployment...}
${REQUIRE_APPROVAL:+}
${REQUIRE_APPROVAL:+**High-risk changes detected**:}
${REQUIRE_APPROVAL:+- IAM role policies modifying permissions}
${REQUIRE_APPROVAL:+- Security group rules affecting network access}
${REQUIRE_APPROVAL:+- Production namespace deployments}
${REQUIRE_APPROVAL:+}
${REQUIRE_APPROVAL:+**Review audit trail**:}
${REQUIRE_APPROVAL:+\`\`\`bash}
${REQUIRE_APPROVAL:+cat ${REPO_PATH}/generation-audit.json}
${REQUIRE_APPROVAL:+\`\`\`}
${REQUIRE_APPROVAL:+}
${REQUIRE_APPROVAL:+**Approval checkpoint**: Waiting for ops-team or security-team approval...}
${REQUIRE_APPROVAL:+}
${REQUIRE_APPROVAL:+*If using GitHub Actions, approval gate will be created as manual workflow_dispatch.*}
${REQUIRE_APPROVAL:+*If using GitLab CI, manual job approval required before proceeding.*}
${REQUIRE_APPROVAL:+}
${REQUIRE_APPROVAL:+**✅ Stage 4 complete** - Approval granted, proceeding to deployment}

${REQUIRE_APPROVAL:-**Status**: ⏭️  No high-risk changes detected, skipping approval gate}

---

### Stage 5/5: Deployment

${DRY_RUN:+**Status**: 📋 DRY RUN MODE - Showing deployment plan without execution}
${DRY_RUN:-**Status**: 🚀 DEPLOYING to ${TARGET_PLATFORM}}

**Deployment method**: ${GITOPS_TOOL:-manual}

${GITOPS_TOOL:+**GitOps Deployment** (${GITOPS_TOOL}):}
${GITOPS_TOOL:+}
${GITOPS_TOOL:+<Task>}
${GITOPS_TOOL:+  subagent_type: general-purpose}
${GITOPS_TOOL:+  description: Deploy via GitOps}
${GITOPS_TOOL:+  prompt: |}
${GITOPS_TOOL:+    Configure ${GITOPS_TOOL} deployment:}
${GITOPS_TOOL:+    }
${GITOPS_TOOL:+    1. **Commit resources to Git**:}
${GITOPS_TOOL:+       \`\`\`bash}
${GITOPS_TOOL:+       cd ${REPO_PATH}}
${GITOPS_TOOL:+       git add docker/ kubernetes/ terraform/ gitops/}
${GITOPS_TOOL:+       git commit -m "feat: add IaC resources for ${TARGET_PLATFORM}}
${GITOPS_TOOL:+       }
${GITOPS_TOOL:+       Generated with modern best practices:}
${GITOPS_TOOL:+       - ${GATEWAY_API:+Gateway API v1 (HTTPRoute)}${GATEWAY_API:-Ingress}${GATEWAY_API:+ for traffic routing}}
${GITOPS_TOOL:+       - Native sidecar containers (K8s 1.29+)}
${GITOPS_TOOL:+       - Terraform 1.7+ with import blocks and testing}
${GITOPS_TOOL:+       - OIDC authentication for CI/CD}
${GITOPS_TOOL:+       - Spot instances with cost optimization}
${GITOPS_TOOL:+       - ${GITOPS_TOOL} GitOps configuration}
${GITOPS_TOOL:+       "}
${GITOPS_TOOL:+       git push origin main}
${GITOPS_TOOL:+       \`\`\`}
${GITOPS_TOOL:+    }
${GITOPS_TOOL:+    2. **Apply ${GITOPS_TOOL} configuration**:}
${GITOPS_TOOL:+       \`\`\`bash}
${GITOPS_TOOL:+       kubectl apply -f ${REPO_PATH}/gitops/}
${GITOPS_TOOL:+       \`\`\`}
${GITOPS_TOOL:+    }
${GITOPS_TOOL:+    3. **Monitor sync status**:}
${GITOPS_TOOL:+       - ArgoCD: \`kubectl get applications -n argocd -w\`}
${GITOPS_TOOL:+       - Flux: \`kubectl get kustomizations -n flux-system -w\`}
${GITOPS_TOOL:+    }
${GITOPS_TOOL:+    Provide sync status, deployment health, and next steps.}
${GITOPS_TOOL:+</Task>}
${GITOPS_TOOL:+}
${GITOPS_TOOL:+**✅ GitOps deployment initiated**}
${GITOPS_TOOL:+}
${GITOPS_TOOL:+**Monitor deployment**:}
${GITOPS_TOOL:+\`\`\`bash}
${GITOPS_TOOL:+# Watch sync progress}
${GITOPS_TOOL:+${GITOPS_TOOL:+kubectl get applications -n argocd -w  # ArgoCD}
${GITOPS_TOOL:+${GITOPS_TOOL:+# OR}
${GITOPS_TOOL:+${GITOPS_TOOL:+kubectl get kustomizations -n flux-system -w  # Flux}
${GITOPS_TOOL:+}
${GITOPS_TOOL:+# Check application health}
${GITOPS_TOOL:+kubectl get pods -n <namespace> -w}
${GITOPS_TOOL:+}
${GITOPS_TOOL:+# View Gateway API status (if enabled)}
${GITOPS_TOOL:+${GATEWAY_API:+kubectl get gateway,httproute -n <namespace>}
${GITOPS_TOOL:+\`\`\`}

${GITOPS_TOOL:-**Manual Deployment Instructions**:}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-${DRY_RUN:+**DRY RUN** - Execute these commands to deploy:}${DRY_RUN:-Executing manual deployment...}}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-**Step 1: Build and push container images**}
${GITOPS_TOOL:-\`\`\`bash}
${GITOPS_TOOL:-cd ${REPO_PATH}}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Build with security scanning}
${GITOPS_TOOL:-docker build -t myapp:v1.0.0 -f docker/Dockerfile .}
${GITOPS_TOOL:-trivy image myapp:v1.0.0 --severity HIGH,CRITICAL}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Tag and push}
${GITOPS_TOOL:-docker tag myapp:v1.0.0 <registry>/myapp:v1.0.0}
${GITOPS_TOOL:-docker push <registry>/myapp:v1.0.0}
${GITOPS_TOOL:-\`\`\`}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-**Step 2: Deploy infrastructure (Terraform)**}
${GITOPS_TOOL:-\`\`\`bash}
${GITOPS_TOOL:-cd ${REPO_PATH}/terraform/}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Initialize and validate}
${GITOPS_TOOL:-terraform init}
${GITOPS_TOOL:-terraform validate}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Run tests (Terraform 1.7+)}
${GITOPS_TOOL:-terraform test}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Plan and apply}
${GITOPS_TOOL:-terraform plan -out=plan.tfplan}
${GITOPS_TOOL:-terraform apply plan.tfplan}
${GITOPS_TOOL:-\`\`\`}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-**Step 3: Deploy Kubernetes resources**}
${GITOPS_TOOL:-\`\`\`bash}
${GITOPS_TOOL:-# Update kubeconfig}
${GITOPS_TOOL:-${TARGET_PLATFORM:+aws eks update-kubeconfig --name <cluster-name>  # AWS EKS}
${GITOPS_TOOL:-${TARGET_PLATFORM:+gcloud container clusters get-credentials <cluster-name>  # GCP GKE}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Verify cluster version for modern features}
${GITOPS_TOOL:-kubectl version --short}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-${GATEWAY_API:+# Install Gateway API CRDs if needed (K8s 1.31+)}
${GITOPS_TOOL:-${GATEWAY_API:+kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Deploy resources}
${GITOPS_TOOL:-${HELM_MODE:+helm install myapp ${REPO_PATH}/kubernetes/myapp-chart/ --values ${REPO_PATH}/kubernetes/myapp-chart/values-prod.yaml}${HELM_MODE:-kubectl apply -f ${REPO_PATH}/kubernetes/}}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Verify deployment}
${GITOPS_TOOL:-kubectl get pods,svc${GATEWAY_API:+,gateway,httproute} -n <namespace> -w}
${GITOPS_TOOL:-\`\`\`}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-**Step 4: Verify deployment health**}
${GITOPS_TOOL:-\`\`\`bash}
${GITOPS_TOOL:-# Check pod status}
${GITOPS_TOOL:-kubectl get pods -n <namespace>}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-${GATEWAY_API:+# Verify Gateway API resources}
${GITOPS_TOOL:-${GATEWAY_API:+kubectl describe gateway production-gateway -n <namespace>}
${GITOPS_TOOL:-${GATEWAY_API:+kubectl describe httproute app-route -n <namespace>}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Check service endpoints}
${GITOPS_TOOL:-kubectl get svc,${GATEWAY_API:+httproute}${GATEWAY_API:-ingress} -n <namespace>}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# View logs}
${GITOPS_TOOL:-kubectl logs -l app=myapp -n <namespace> --tail=50 -f}
${GITOPS_TOOL:-}
${GITOPS_TOOL:-# Monitor cost optimization (Spot instances)}
${GITOPS_TOOL:-kubectl get nodes -l node.kubernetes.io/lifecycle=spot}
${GITOPS_TOOL:-\`\`\`}

---

## Pipeline Summary

**✅ Pipeline complete!**

**Execution time**: <calculated from start>

**Generated artifacts**:
- Analysis: `${REPO_PATH}/iac-analysis.json`${BROWNFIELD:+ (with brownfield context)}
- Docker: `${REPO_PATH}/docker/`
- Kubernetes: `${REPO_PATH}/kubernetes/` (${GATEWAY_API:+Gateway API v1}${GATEWAY_API:-Ingress})
- Terraform: `${REPO_PATH}/terraform/` (with Terraform 1.7+ features)
${CI_PLATFORM:+- CI/CD: \`${REPO_PATH}/.github/workflows/\` or \`${REPO_PATH}/.gitlab-ci.yml\` (OIDC auth)}
${GITOPS_TOOL:+- GitOps: \`${REPO_PATH}/gitops/\`}
${REQUIRE_APPROVAL:+- Audit: \`${REPO_PATH}/generation-audit.json\` (AI decisions and approvals)}
- Validation: `${REPO_PATH}/validation-report.json`, `${REPO_PATH}/sbom.json`

**Modern features implemented**:
✅ Gateway API v1 (HTTPRoute) instead of Ingress (${GATEWAY_API:+enabled}${GATEWAY_API:-disabled})
✅ Native sidecar containers with restartPolicy: Always (K8s 1.29+)
✅ Terraform 1.7+ import blocks with for_each
✅ Native Terraform test framework (.tftest.hcl)
✅ OIDC authentication for CI/CD (no long-lived credentials)
✅ Spot instances with price-capacity-optimized allocation (66-90% savings)
✅ Multi-phase validation (technical + intent with OPA)
✅ Hallucination detection for AI-generated configs
${BROWNFIELD:+✅ Context injection from existing infrastructure}
${REQUIRE_APPROVAL:+✅ Human-in-the-loop governance with audit trail}

**Cost optimization**:
- Spot instances: 66-90% savings vs On-Demand
- Right-sizing: CPU limits target 40-70% utilization
- Auto-scaling: Configured for variable workloads
${BROWNFIELD:+- Reserved Instance recommendations based on existing usage patterns}

**Next steps**:
1. Monitor deployment health: `kubectl get pods -A -w`
2. Check application logs: `kubectl logs -l app=<app-name> -f`
3. ${GATEWAY_API:+Verify Gateway API routing: \`kubectl get httproute -A\`}${GATEWAY_API:-Access application: Check Service/Ingress endpoints}
4. Review CI/CD pipelines: Verify OIDC authentication working
5. Monitor cost savings: Check Spot instance allocation and utilization

**Troubleshooting**:
- Pods pending: Check resource quotas and node capacity
- Validation failed: Review `validation-summary.md` for remediation guidance
- Gateway API issues: Verify K8s 1.31+ and CRDs installed
- Spot interruptions: Check EventBridge rules and interruption handling
- Deployment stuck: `kubectl describe pod <pod-name>` for events
```

---

### Case: help (default)

```markdown
# Infrastructure-as-Code Automation (2026 Edition)

**Usage**: `/iac <operation> [flags]`

Execute modern IaC operations with AI-assisted validation, multi-phase security scanning, and cost optimization.

## Operations

| Operation | Description | Example |
|-----------|-------------|---------|
| `analyze` | Scan repository and generate architecture analysis with brownfield context | `/iac analyze --repo . --brownfield` |
| `generate` | Create IaC resources with AI validation and modern K8s/Terraform patterns | `/iac generate --target aws-eks --gateway-api` |
| `validate` | Two-phase validation (technical + intent) with severity-based thresholds | `/iac validate --all --strict` |
| `deploy` | Full pipeline with approval gates and governance | `/iac deploy --repo . --target gcp-gke --require-approval` |

## Common Flags

| Flag | Description | Required | Example |
|------|-------------|----------|---------|
| `--repo <path>` | Repository to analyze (default: `.`) | No | `--repo /path/to/app` |
| `--target <platform>` | Target platform for generation | Yes (generate/deploy) | `--target aws-eks` |
| `--gitops <tool>` | GitOps tool (`argocd`, `flux`) | No | `--gitops argocd` |
| `--ci <platform>` | CI/CD platform (`github-actions`, `gitlab-ci`) | No | `--ci github-actions` |
| `--path <path>` | Path for validation | No | `--path ./terraform` |
| `--helm` | Generate Helm charts | No | `--helm` |
| `--dry-run` | Show plan without executing | No | `--dry-run` |
| `--strict` | Strict validation mode (fail on HIGH+) | No | `--strict` |
| `--no-validate` | Skip validation stage | No | `--no-validate` |
| `--all` | Validate all generated resources | No | `--all` |
| `--brownfield` | **NEW**: Context injection from existing infrastructure | No | `--brownfield` |
| `--gateway-api` | **NEW**: Use Gateway API v1 instead of Ingress | No | `--gateway-api` |
| `--require-approval` | **NEW**: Human-in-the-loop governance for critical resources | No | `--require-approval` |

## Target Platforms

| Platform | Description | Cloud Provider | Cost Optimization |
|----------|-------------|----------------|-------------------|
| `aws-eks` | Amazon EKS with IRSA and Spot instances | AWS | 66-90% savings |
| `aws-ecs` | Amazon ECS Fargate with Spot | AWS | 70% savings |
| `gcp-gke` | Google GKE with Workload Identity and Spot | GCP | 66-91% savings |
| `gcp-run` | Google Cloud Run | GCP | Pay-per-use |
| `kubernetes` | Generic Kubernetes with modern features | Cloud-agnostic | Configurable |
| `terraform` | Terraform modules with 1.7+ features | Multi-cloud | IaC-level optimization |

## Modern Features (2026)

### Kubernetes 1.31+ Features
- **Gateway API v1**: HTTPRoute and Gateway resources (replaces Ingress)
- **Native Sidecar Containers**: restartPolicy: Always on init containers
- **BackendTLSPolicy**: TLS termination and re-encryption patterns

### Terraform 1.7+ Features
- **Import blocks with for_each**: Multi-resource imports
- **Native test framework**: .tftest.hcl files with mocking
- **Mock providers**: Unit testing without cloud API calls

### CI/CD Patterns
- **OIDC Authentication**: Short-lived tokens (no AWS_ACCESS_KEY_ID)
- **Reusable Workflows**: Pinned to commit SHAs or semantic versions
- **Matrix Optimization**: fail-fast with type=gha cache

### AI-Assisted Generation
- **Hallucination Detection**: Validates resource types against provider schemas
- **Context Injection**: Reads existing state to prevent conflicts
- **Human-in-the-Loop**: Approval gates for high-risk changes

### Security & Cost
- **Two-Phase Validation**: Technical (Trivy/Checkov) + Intent (OPA)
- **Severity-Based Thresholds**: Fail on CRITICAL/HIGH only
- **Spot Instance Optimization**: 66-90% cost savings with diversification
- **Right-Sizing**: CPU limits target 40-70% utilization

## Examples

### Quick Start (Full Pipeline - Modern Stack)
```bash
# Analyze, generate with modern features, validate, and deploy
/iac deploy \\
  --repo . \\
  --target aws-eks \\
  --gitops argocd \\
  --gateway-api \\
  --brownfield \\
  --require-approval
```

### Step-by-Step Workflow

**1. Analyze existing application (brownfield mode)**:
```bash
/iac analyze --repo . --brownfield
# Reads terraform.tfstate and existing K8s resources
# Prevents AI hallucinations and resource conflicts
# Output: iac-analysis.json with context
```

**2. Generate with Gateway API and modern patterns**:
```bash
/iac generate \\
  --target aws-eks \\
  --gateway-api \\
  --gitops argocd \\
  --ci github-actions \\
  --helm
# Generates:
# - Gateway API v1 (HTTPRoute) instead of Ingress
# - Native sidecar containers (K8s 1.29+)
# - Terraform with import blocks and testing (1.7+)
# - CI/CD with OIDC authentication
# - Spot instances with cost optimization
```

**3. Validate with two-phase approach**:
```bash
/iac validate --all --strict
# Phase 1: Technical (Trivy, Checkov, kubectl --dry-run)
# Phase 2: Intent (OPA policies, dependency graphs)
# Exit code 0 = safe, 2 = blocked
```

**4. Deploy with approval gate**:
```bash
/iac deploy \\
  --repo . \\
  --target aws-eks \\
  --gitops argocd \\
  --require-approval
# Human approval required for IAM policies, security groups
# Audit trail saved to generation-audit.json
```

### Platform-Specific Examples

**AWS EKS with Gateway API and Spot instances**:
```bash
/iac deploy \\
  --repo . \\
  --target aws-eks \\
  --gateway-api \\
  --gitops flux \\
  --ci github-actions \\
  --brownfield
# - Gateway API v1 for traffic routing
# - Spot instances: 66-90% cost savings
# - OIDC authentication for GitHub Actions
# - Context injection from existing infrastructure
```

**GCP GKE with Helm and strict validation**:
```bash
/iac generate --target gcp-gke --helm
/iac validate --all --strict
helm install myapp ./kubernetes/myapp-chart/ \\
  --values ./kubernetes/myapp-chart/values-prod.yaml
```

**Brownfield Terraform with import blocks**:
```bash
/iac generate --target terraform --brownfield
# Generates import blocks with for_each for existing resources
# Terraform 1.7+ feature for multi-resource imports
cd terraform && terraform apply
```

### Validation Examples

**Two-phase validation with strict mode**:
```bash
/iac validate --all --strict
# Phase 1: Trivy, Checkov, kubectl --dry-run, Terraform test
# Phase 2: OPA policies, dependency graphs, compliance frameworks
# Fails on CRITICAL/HIGH findings
```

**Generate SBOM for compliance**:
```bash
/iac validate --all
# Output: sbom.json (CycloneDX format)
# For incident response and supply chain security
```

## Security Features

The IaC Team plugin enforces 2026 security best practices:

✅ **Multi-Phase Validation**: Technical (syntax/security) + Intent (semantic/policy)
✅ **Hallucination Detection**: Validates AI-generated resources against provider schemas
✅ **No Hardcoded Secrets**: .env.example → .env.local pattern with secret detection
✅ **OIDC Authentication**: Short-lived tokens with restrictive trust policies
✅ **Container Security**: Trivy with --ignore-unfixed and .trivyignore
✅ **Infrastructure Security**: Checkov (replaces tfsec) with compliance frameworks
✅ **Kubernetes Validation**: kubectl --dry-run=server and Gateway API checks
✅ **Helm Linting**: helm lint --strict for chart quality
✅ **Terraform Testing**: Native test framework with mocking (1.7+)
✅ **OPA Policy Compliance**: Intent validation with Rego policies
✅ **SBOM Generation**: CycloneDX/SPDX for supply chain security

**Severity-based exit codes**:
- `0` - All security checks passed (PASSED)
- `1` - MEDIUM/LOW findings (WARNINGS - review recommended)
- `2` - CRITICAL/HIGH findings (**BLOCKED** - do not deploy)

## Cost Optimization Features

**Spot Instance Configuration** (66-90% savings):
- price-capacity-optimized allocation strategy
- Diversification: 4+ instance types, 4+ availability zones
- Interruption handling: EventBridge + PreStop hooks
- Mixed capacity: 60-80% Spot, 20-40% On-Demand for reliability

**Right-Sizing and Auto-Scaling**:
- CPU resource limits target 40-70% utilization
- Auto-scaling policies for variable workloads
- Scheduled shutdown for non-production (70% savings)
- AWS Compute Optimizer / GCP Recommender integration

**Cost Commitment Strategies**:
- Reserved Instances / Savings Plans for baseline (60-70% coverage)
- 1-year No Upfront commitments for flexibility
- Quarterly review and adjustment process

**Network Cost Optimization**:
- Keep compute and data in same region/AZ
- VPC endpoints for AWS service access
- Cross-region transfer cost awareness

## Agents Used

This command orchestrates three specialized agents with modern capabilities:

| Agent | Purpose | Operations | Modern Features |
|-------|---------|------------|-----------------|
| `iac-analyzer` | Repository analysis and brownfield context | analyze, deploy | State file reading, K8s resource querying, conflict detection |
| `iac-generator` | IaC generation with AI validation | generate, deploy | Hallucination detection, context injection, Gateway API, native sidecars, Terraform 1.7+ |
| `iac-validator` | Two-phase security validation | validate, deploy | Trivy/Checkov, OPA policies, Gateway API checks, Terraform testing |

## Output Structure

After running operations, expect this directory structure:

```
<repository>/
├── iac-analysis.json              # Architecture analysis
├── architecture-diagram.md        # Visual diagram
├── existing-resources.txt         # Brownfield: Current infrastructure (if --brownfield)
├── existing-k8s-resources.json    # Brownfield: Deployed resources (if --brownfield)
├── docker/
│   ├── Dockerfile                 # Multi-stage, security-hardened
│   └── .dockerignore
├── kubernetes/
│   ├── deployment.yaml            # Native sidecars (K8s 1.29+)
│   ├── service.yaml
│   ├── httproute.yaml             # Gateway API v1 (if --gateway-api)
│   ├── gateway.yaml               # Gateway API v1 (if --gateway-api)
│   ├── backendtlspolicy.yaml      # TLS to backend (if --gateway-api)
│   ├── ingress.yaml               # Traditional (if not --gateway-api)
│   ├── configmap.yaml
│   ├── secret.yaml                # Template only (populate from .env)
│   └── <app>-chart/               # Helm chart (if --helm)
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       └── templates/
├── terraform/
│   ├── main.tf                    # Spot instances, cost optimization
│   ├── variables.tf
│   ├── outputs.tf
│   ├── import.tf                  # Import blocks with for_each (TF 1.7+)
│   ├── modules/                   # VPC, EKS/GKE, RDS/CloudSQL
│   └── tests/
│       └── main.tftest.hcl        # Native test framework (TF 1.7+)
├── .trivyignore                   # Security exceptions with expiry dates
├── .github/workflows/             # GitHub Actions (if --ci github-actions)
│   ├── deploy.yaml                # OIDC auth, reusable workflows
│   └── security-scan.yaml         # Trivy with severity thresholds
├── .gitlab-ci.yml                 # GitLab CI (if --ci gitlab-ci)
├── gitops/                        # GitOps configs (if --gitops set)
│   ├── application.yaml           # ArgoCD Application
│   └── kustomization.yaml         # Flux Kustomization (OCI source)
├── generation-audit.json          # AI decisions and approvals (if --require-approval)
├── validation-report.json         # Machine-readable validation results
├── validation-summary.md          # Human-readable validation summary
└── sbom.json                      # Software Bill of Materials
```

## Troubleshooting

### Common Errors

**Error: `Gateway API CRDs not installed`**
```bash
# Solution: Install Gateway API CRDs for K8s 1.31+
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
```

**Error: `Kubernetes version too old for native sidecars`**
```bash
# Solution: Upgrade cluster to 1.29+ or disable native sidecar feature
kubectl version --short
# Upgrade cluster or remove --gateway-api flag
```

**Error: `Terraform version incompatible with import for_each`**
```bash
# Solution: Upgrade to Terraform 1.7+
terraform version
# Upgrade: https://www.terraform.io/downloads
```

**Exit code 2: Hallucinated resource detected**
```bash
# Solution: Review validation-summary.md for details
cat validation-summary.md
# Fix: Verify resource types against provider schemas
# Regenerate with corrected configuration
```

**Exit code 2: Critical security findings**
```bash
# Solution: Review findings and apply fixes
/iac validate --all --strict  # See detailed findings
# Common issues:
# - Remove hardcoded secrets (use .env.example pattern)
# - Add security contexts (runAsNonRoot, readOnlyRootFilesystem)
# - Fix overly permissive IAM policies
# - Add missing health checks and resource limits
/iac generate --target aws-eks  # Regenerate after fixes
```

**Gateway API HTTPRoute not working**
```bash
# Solution: Verify Gateway status and route configuration
kubectl describe gateway production-gateway -n <namespace>
# Check Gateway status.conditions[type=Programmed] == True
kubectl describe httproute app-route -n <namespace>
# Verify backendRefs point to existing services
```

**Spot instance frequent interruptions**
```bash
# Solution: Increase diversification and check allocation strategy
# Edit terraform/main.tf:
# - Use 4+ instance types across 4+ AZs
# - Set spot_allocation_strategy = "price-capacity-optimized"
# - Increase On-Demand base capacity (20-40%)
terraform apply
```

### Version Compatibility

**Kubernetes Features**:
- Native sidecars: Requires 1.29+
- Gateway API v1: Requires 1.31+ (GA)
- BackendTLSPolicy v1alpha3: Requires Gateway API CRDs

**Terraform Features**:
- Import for_each: Requires 1.7+
- Native testing: Requires 1.6+
- Mock providers: Requires 1.7+

**Check versions**:
```bash
kubectl version --short
terraform version
```

### Validation Bypass (Not Recommended)

Only for development/testing - **NEVER in production**:
```bash
/iac deploy --repo . --target aws-eks --no-validate
```

### Debug Mode

Enable verbose output for troubleshooting:
```bash
# Set verbose logging
export CLAUDE_LOG_LEVEL=debug

# Run operation with detailed output
/iac deploy --repo . --target aws-eks

# Review validation reports
cat validation-summary.md
cat validation-report.json
cat generation-audit.json  # If --require-approval used
```

## Integration with Claude Agent SDK

This command integrates with the multi-agent plugin system using modern orchestration patterns:

**Agent Communication Flow**:
```
iac-analyzer
  ↓ (outputs)
  iac-analysis.json (with brownfield context)
  ↓ (consumed by)
iac-generator (with AI validation)
  ↓ (outputs)
  IaC resources + generation-audit.json
  ↓ (validated by)
iac-validator (two-phase)
  ↓ (outputs)
  validation-report.json + SBOM
  ↓ (if exit code 0 or 1)
  ↓ (human approval if required)
Deployment stage
```

**Tool Permissions**:
- Bash commands restricted to: git, kubectl, helm, terraform, docker, trivy, checkov
- Task tool for agent-to-agent coordination
- Read/Write/Grep for file operations

## Quick Reference

**Most common workflows**:

```bash
# Modern full pipeline (recommended - 2026 stack)
/iac deploy \\
  --repo . \\
  --target aws-eks \\
  --gateway-api \\
  --gitops argocd \\
  --brownfield \\
  --require-approval

# Generate with modern features (manual deployment)
/iac generate \\
  --target kubernetes \\
  --gateway-api \\
  --helm \\
  --brownfield
helm install myapp ./kubernetes/myapp-chart/ --values values-prod.yaml

# Strict validation before production deployment
/iac validate --all --strict

# Brownfield Terraform with import and testing
/iac generate --target terraform --brownfield
cd terraform
terraform test  # Run native tests (TF 1.7+)
terraform apply
```

## What's New in 2026

**Kubernetes**:
- ✨ Gateway API v1 replaces Ingress (HTTPRoute, Gateway, BackendTLSPolicy)
- ✨ Native sidecar containers with restartPolicy: Always
- ✨ Improved startup ordering and termination sequences

**Terraform**:
- ✨ Import blocks with for_each for multi-resource imports
- ✨ Native test framework with .tftest.hcl files
- ✨ Mock providers for unit testing without cloud API calls

**CI/CD**:
- ✨ OIDC authentication standard (GitHub Actions, GitLab CI)
- ✨ Reusable workflows with semantic versioning
- ✨ Matrix optimization with fail-fast and caching
- ✨ GitLab Agent for K8s with Flux integration

**Security**:
- ✨ Two-phase validation (technical + intent with OPA)
- ✨ Trivy replaces tfsec (all-in-one scanning)
- ✨ Severity-based thresholds (--ignore-unfixed)
- ✨ SBOM generation (CycloneDX/SPDX)

**AI-Assisted**:
- ✨ Hallucination detection against provider schemas
- ✨ Brownfield context injection from state files
- ✨ Human-in-the-loop governance with audit trails

**Cost Optimization**:
- ✨ Spot instances with price-capacity-optimized (66-90% savings)
- ✨ Right-sizing with 40-70% CPU target utilization
- ✨ Automated Reserved Instance/Savings Plan recommendations

---

*Part of the IaC Team plugin for Infrastructure-as-Code automation with 2026 best practices*
```

---

## Additional Notes

### Modern Feature Compatibility Matrix

| Feature | Kubernetes Version | Terraform Version | Notes |
|---------|-------------------|-------------------|-------|
| Native Sidecars | 1.29+ | N/A | Use restartPolicy: Always on init containers |
| Gateway API v1 | 1.31+ (GA) | N/A | Requires Gateway API CRDs installation |
| BackendTLSPolicy | 1.31+ | N/A | API version: gateway.networking.k8s.io/v1alpha3 |
| Import for_each | N/A | 1.7+ | Multi-resource imports in single block |
| Native Testing | N/A | 1.6+ | .tftest.hcl files with run blocks |
| Mock Providers | N/A | 1.7+ | Unit testing without cloud API calls |

### AI-Assisted Generation Best Practices

**Hallucination Prevention**:
1. Validate ALL resource types against official schemas
2. Check module sources against verified registries
3. Use kubectl explain for Kubernetes resources
4. Flag unverifiable dependencies for human review

**Context Injection (Brownfield)**:
1. Read terraform.tfstate before generation
2. Query Kubernetes API: `kubectl get all -A -o json`
3. Inject VPC IDs, subnet IDs, security groups into prompts
4. Generate import blocks for existing resources

**Human-in-the-Loop Governance**:
1. Flag high-risk resources: IAM, security groups, encryption
2. Generate approval checkpoints in CI/CD pipelines
3. Create audit trail with AI decisions and human approvals
4. Add comments explaining AI reasoning in generated code

### Security Scanning Configuration

**Trivy Best Practices** (2026):
```bash
# Update database before scanning
trivy image --download-db-only

# Severity-based thresholds
trivy config . \\
  --severity HIGH,CRITICAL \\
  --exit-code 1 \\
  --ignore-unfixed \\
  --ignorefile .trivyignore

# SBOM generation
trivy image --format cyclonedx --output sbom.json myimage:tag

# Continuous monitoring
# Schedule daily rescans of production images
```

**.trivyignore Format**:
```
# Example security exception with expiry date
CVE-2024-12345  # Reviewed by security-team on 2026-02-01
                 # No fix available, compensating controls in place
                 # Expires: 2026-03-01
                 # Approval: JIRA-SEC-123
```

**Checkov Configuration** (replaces tfsec):
```bash
# Multi-framework scanning
checkov -d . \\
  --framework terraform,kubernetes,dockerfile \\
  --hard-fail-on CRITICAL,HIGH \\
  --compact \\
  --output json

# Compliance frameworks
checkov -d ./terraform --check CIS_AWS --output cli
checkov -d ./kubernetes --check CIS_Kubernetes_1.23 --output cli
```

### Cost Optimization Details

**Spot Instance Configuration**:
```hcl
# AWS EKS Node Group with Spot (66-90% savings)
eks_managed_node_groups = {
  spot = {
    capacity_type  = "SPOT"

    # Diversification across instance types (4+)
    instance_types = [
      "t3.medium", "t3a.medium",
      "t3.large", "t3a.large"
    ]

    # Mixed capacity strategy
    use_mixed_instances_policy = true
    mixed_instances_policy = {
      instances_distribution = {
        on_demand_base_capacity                  = 1  # Base capacity
        on_demand_percentage_above_base_capacity = 20  # 20% On-Demand
        spot_allocation_strategy                 = "price-capacity-optimized"
      }
    }

    # Interruption handling
    metadata_options = {
      http_endpoint               = "enabled"
      http_tokens                 = "required"
      http_put_response_hop_limit = 1
    }

    # Spot instance tags
    tags = {
      "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/lifecycle" = "spot"
    }
  }
}
```

**Right-Sizing Configuration**:
```yaml
# Kubernetes Deployment with optimal resource limits
resources:
  requests:
    cpu: 500m      # Baseline
    memory: 512Mi
  limits:
    cpu: 1000m     # Target 50-70% utilization
    memory: 1Gi

# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70  # Scale at 70% CPU
```

### Gateway API Migration Path

**Migration from Ingress to Gateway API**:

1. **Parallel Running** (no downtime):
   ```bash
   # Keep existing Ingress running
   # Deploy Gateway and HTTPRoute alongside
   kubectl apply -f gateway.yaml
   kubectl apply -f httproute.yaml

   # Verify Gateway Programmed status
   kubectl wait --for=condition=Programmed gateway/production-gateway

   # Test traffic routing to new Gateway
   curl -H "Host: app.example.com" http://<gateway-ip>/

   # Once validated, delete legacy Ingress
   kubectl delete ingress app-ingress
   ```

2. **Automated Conversion** (ingress2gateway tool):
   ```bash
   # Install ingress2gateway
   go install github.com/kubernetes-sigs/ingress2gateway@latest

   # Convert existing Ingress to Gateway/HTTPRoute
   ingress2gateway print \\
     --input-file ingress.yaml \\
     --output-file httproute.yaml
   ```

3. **Validate HTTPRoute Configuration**:
   - Ensure parentRefs point to correct Gateway
   - Verify backendRefs use existing Service names
   - Check TLS configuration (certificateRefs in same namespace)
   - Test path matching and header manipulation

### Error Exit Codes Reference

All operations use consistent exit codes:

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success - All checks passed | Proceed with deployment |
| `1` | Success with warnings - MEDIUM/LOW findings | Review before production, deployable |
| `2` | Failure - CRITICAL/HIGH findings or validation errors | **DO NOT DEPLOY** - Fix issues first |

**Exit code 2 triggers**:
- Hardcoded secrets detected
- CRITICAL or (in strict mode) HIGH security findings
- Kubernetes validation failures (kubectl --dry-run=server)
- Terraform plan errors or test failures
- Helm lint failures (--strict mode)
- Gateway API configuration errors
- Version incompatibilities (K8s < 1.29 with native sidecars, TF < 1.7 with for_each imports)
- Hallucinated resource types or unverified module sources
- OPA policy violations (Phase 2 intent validation)

### Tool Dependencies Installation

**Required tools**:
```bash
# Kubernetes
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Terraform 1.7+
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip && sudo mv terraform /usr/local/bin/

# Docker
sudo apt-get update && sudo apt-get install -y docker.io

# Git
sudo apt-get install -y git
```

**Security validators**:
```bash
# Trivy (replaces tfsec for IaC scanning)
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install -y trivy

# Checkov (multi-platform IaC scanning)
pip install checkov

# OPA/Conftest (policy validation)
wget https://github.com/open-policy-agent/conftest/releases/download/v0.45.0/conftest_0.45.0_Linux_x86_64.tar.gz
tar xzf conftest_0.45.0_Linux_x86_64.tar.gz && sudo mv conftest /usr/local/bin/
```

**Verify installation**:
```bash
command -v kubectl helm terraform docker git trivy checkov conftest
```
