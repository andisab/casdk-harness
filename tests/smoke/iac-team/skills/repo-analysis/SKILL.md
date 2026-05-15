---
name: repo-analysis
description: >
  Codebase analysis patterns for infrastructure projects. Identifies dependencies,
  service architecture, resource patterns, IaC tool usage, security posture, and
  cost optimization opportunities across repositories.

  Activate when user mentions: analyze repository, scan codebase, dependency mapping,
  service discovery, infrastructure audit, IaC detection, analyze project structure,
  understand services, map dependencies, detect frameworks, security assessment,
  cost analysis

  Use for: Understanding existing infrastructure codebases, identifying patterns,
  mapping service dependencies, detecting IaC tools and frameworks, assessing
  security posture, identifying cost optimization opportunities

  Do NOT use for: Generating new infrastructure code, modifying existing resources,
  deployment operations, runtime debugging, active penetration testing
---

# Repository Analysis

Systematic codebase analysis for infrastructure and application projects with security and cost optimization focus.

## Core Capabilities

### 1. Service Discovery
- Identify all services and applications in repository
- Map service types (web, api, worker, database, cache, serverless)
- Detect service boundaries and ownership
- Extract service metadata (ports, protocols, dependencies)
- Identify deployment patterns (monolith, microservices, serverless)

### 2. Dependency Mapping
- Scan for dependency declarations (package.json, requirements.txt, go.mod, pom.xml, Cargo.toml)
- Identify infrastructure dependencies (databases, message queues, caches, object storage)
- Map inter-service dependencies and communication patterns
- Detect external service integrations (AWS, GCP, Azure services)
- Identify version constraints and compatibility requirements

### 3. IaC Tool Detection
- Identify IaC tools in use (Terraform, CloudFormation, Pulumi, CDK, Helm, Kustomize)
- Locate configuration files and directory structures
- Detect tool versions and providers (AWS, GCP, Azure, Kubernetes)
- Map tool coverage across services
- Identify modern features usage (Terraform 1.7+ testing, import blocks with for_each)

### 4. Configuration Analysis
- Extract environment variables and configuration patterns
- Identify secrets management approach (env files, vaults, secret managers, OIDC)
- Map configuration hierarchy (dev, staging, production)
- Detect configuration file formats (YAML, JSON, HCL, TOML)
- Analyze GitOps patterns and CD configuration

### 5. Architecture Patterns
- Identify deployment patterns (containerized, VM-based, serverless, hybrid)
- Detect orchestration platforms (Kubernetes, ECS, Lambda, Cloud Run)
- Map networking patterns (service mesh, Gateway API, ingress, load balancers)
- Identify security patterns (RBAC, network policies, secrets management)
- Detect Kubernetes modern features (Gateway API v1, native sidecars)

### 6. Security Posture Assessment
- Scan for hardcoded secrets and credentials (AWS keys, API tokens, passwords)
- Detect IaC misconfigurations (overly permissive IAM, security group issues)
- Identify authentication patterns (OIDC vs long-lived credentials)
- Check for security scanning tool integration (Trivy, Checkov, tfsec)
- Validate secrets management practices (vault, sealed-secrets, external-secrets)
- Assess container security (root user, resource limits, base image vulnerabilities)

### 7. Cost Optimization Opportunities
- Identify resource right-sizing opportunities (oversized instances, idle resources)
- Detect spot instance usage and optimization potential
- Find abandoned resources (unattached volumes, unused IPs, old snapshots)
- Analyze Reserved Instance and Savings Plan usage
- Identify auto-scaling configurations and efficiency
- Check for non-production resources running 24/7

## Analysis Workflow

### Phase 1: Initial Scan
```
1. Scan root directory for standard markers:
   - package.json, requirements.txt, go.mod, Cargo.toml → Application type
   - terraform/, cloudformation/, pulumi/, cdk/ → IaC tooling
   - docker-compose.yml, Dockerfile, .dockerignore → Containerization
   - .github/workflows/, .gitlab-ci.yml, azure-pipelines.yml → CI/CD
   - k8s/, kubernetes/, manifests/, helm/ → Orchestration

2. Build repository map:
   {
     "services": [],
     "iac_tools": [],
     "dependencies": {},
     "config_patterns": [],
     "security_posture": {},
     "cost_optimization": {}
   }
```

### Phase 2: Deep Analysis
```
1. For each service directory:
   - Extract service metadata (language, framework, runtime)
   - Map dependencies (internal + external)
   - Identify deployment configuration
   - Detect framework and runtime requirements
   - Analyze resource requests and limits
   - Check for spot instance compatibility (stateless vs stateful)

2. For each IaC directory:
   - Identify tool and version (check for Terraform 1.7+, K8s 1.29+)
   - Extract resource definitions
   - Map provider usage (aws, gcp, azure, kubernetes)
   - Detect modules and reusable components
   - Check for modern features (Gateway API, native sidecars)
   - Validate test coverage (*.tftest.hcl files)

3. Security scanning integration:
   - Check for Trivy, Checkov, or tfsec configuration
   - Validate CI/CD security scanning stages
   - Review vulnerability scan results and policies
   - Check for SBOM generation (CycloneDX/SPDX)
```

### Phase 3: Dependency Resolution
```
1. Build dependency graph:
   - Service → Service connections
   - Service → Infrastructure connections
   - IaC → Managed resources
   - External API dependencies

2. Identify critical paths:
   - Core services (highest dependency count)
   - Single points of failure
   - External dependencies and vendor lock-in
   - Circular dependencies

3. Security dependency analysis:
   - Third-party library vulnerabilities
   - Outdated dependency versions
   - License compliance issues
```

### Phase 4: Pattern Extraction & Validation
```
1. Analyze configuration patterns:
   - How are secrets managed? (OIDC, workload identity, or long-lived credentials?)
   - Where are environment configs stored?
   - What naming conventions are used?
   - Are there validation gates? (terraform plan, OPA policies)

2. Analyze deployment patterns:
   - Containerized vs serverless vs VM-based
   - Orchestration approach (K8s, ECS, Lambda)
   - CI/CD integration points and security gates
   - GitOps workflows (Flux, ArgoCD, GitLab Agent)

3. Validate IaC quality:
   - Run terraform validate/plan (if Terraform detected)
   - Check for Terraform test files (*.tftest.hcl)
   - Validate Kubernetes manifests (kubectl --dry-run)
   - Run helm lint for Helm charts
   - Check for policy-as-code (OPA/Rego files)

4. Identify AI-assisted IaC indicators:
   - Two-phase validation pipeline (technical + intent)
   - RAG/knowledge injection patterns
   - Hallucination detection mechanisms
   - Human-in-the-loop approval gates
   - Brownfield context awareness (state file usage)
```

### Phase 5: Security & Cost Assessment
```
1. Security assessment:
   - Run secret detection patterns (never expose actual secrets)
   - Check IAM policies for least-privilege violations
   - Validate OIDC authentication configuration
   - Identify containers running as root
   - Check for missing resource limits
   - Review network policies and security groups

2. Cost optimization analysis:
   - Identify oversized instances (>70% or <40% CPU utilization)
   - Find idle resources (stopped instances, unattached volumes)
   - Check spot instance configuration and diversification
   - Analyze Reserved Instance/Savings Plan coverage
   - Identify non-production resources without auto-shutdown
   - Calculate potential savings from right-sizing

3. Generate recommendations:
   - Security improvements (HIGH/MEDIUM/LOW priority)
   - Cost optimization opportunities (estimated savings)
   - Modernization suggestions (Gateway API, native sidecars, Terraform 1.7+)
   - Best practice alignment (CI/CD, GitOps, testing)
```

## File Pattern Recognition

### Application Dependencies
```yaml
Node.js:
  - package.json, package-lock.json, yarn.lock, pnpm-lock.yaml
  - Look for: dependencies, devDependencies, scripts

Python:
  - requirements.txt, setup.py, pyproject.toml, Pipfile, poetry.lock
  - Look for: package names, version constraints

Go:
  - go.mod, go.sum
  - Look for: module path, require statements, replace directives

Java:
  - pom.xml, build.gradle, settings.gradle, gradle.properties
  - Look for: dependencies, plugins, repositories

Rust:
  - Cargo.toml, Cargo.lock
  - Look for: dependencies, dev-dependencies, features

.NET:
  - *.csproj, packages.config, nuget.config
  - Look for: PackageReference, dependencies
```

### Infrastructure as Code
```yaml
Terraform:
  - *.tf files, terraform.tfvars, .terraform.lock.hcl
  - *.tftest.hcl (Terraform 1.6+ native testing)
  - Key patterns: resource, module, provider, variable, data
  - Modern features: import blocks with for_each (1.7+), test mocking

Kubernetes:
  - *.yaml in k8s/, kubernetes/, manifests/, base/, overlays/
  - Key patterns: apiVersion, kind, metadata
  - Modern patterns: Gateway API v1 (HTTPRoute, Gateway, BackendTLSPolicy)
  - Native sidecars: init containers with restartPolicy Always (1.29+)

Helm:
  - Chart.yaml, values.yaml, templates/, charts/
  - Key patterns: chart metadata, template syntax {{ }}, values references

CloudFormation:
  - *.yaml, *.json with Resources, Parameters, Outputs
  - Key patterns: AWS::*, Ref, !GetAtt, !Sub

Pulumi:
  - Pulumi.yaml, Pulumi.<stack>.yaml, __main__.py|ts|go
  - Key patterns: pulumi.Config(), pulumi.export()

AWS CDK:
  - cdk.json, lib/, bin/, package.json
  - Key patterns: @aws-cdk/*, Stack, Construct
```

### Security Scanning Configuration
```yaml
Trivy:
  - trivy.yaml, .trivyignore
  - Look for: severity thresholds, --ignore-unfixed flag
  - SBOM generation: --format cyclonedx|spdx

Checkov:
  - .checkov.yaml, .checkov.baseline
  - Look for: framework checks, policy IDs, skip checks
  - Compliance frameworks: CIS, PCI-DSS, GDPR, HIPAA

tfsec (deprecated - migrate to Trivy):
  - .tfsec/ directory, tfsec.yml
  - Note: Recommend migration to Trivy for unified scanning
```

### Configuration Files
```yaml
Environment Config:
  - .env.example (safe - no actual secrets)
  - config/*.yaml, config/*.json
  - docker-compose.yml, docker-compose.override.yml
  - secrets/ (should be gitignored)

CI/CD:
  - .github/workflows/*.yml (GitHub Actions)
  - .gitlab-ci.yml (GitLab CI)
  - azure-pipelines.yml (Azure DevOps)
  - Jenkinsfile (Jenkins)
  - buildkite.yml (Buildkite)

GitOps:
  - flux-system/, kustomization.yaml (Flux)
  - argocd/, application.yaml (ArgoCD)
  - .gitlab/agents/ (GitLab Agent)
  - Look for: OCI image sources, reconciliation configs

Containerization:
  - Dockerfile, .dockerignore
  - docker-compose.yml, docker-compose.*.yml
  - .hadolint.yaml (Dockerfile linter)
```

## Output Format

### Analysis Report Structure
```json
{
  "repository": {
    "name": "string",
    "primary_language": "string",
    "iac_tools": ["terraform", "helm"],
    "deployment_target": "kubernetes",
    "modern_features": {
      "terraform_1.7+": true,
      "k8s_gateway_api": true,
      "k8s_native_sidecars": false
    }
  },
  "services": [
    {
      "name": "api-service",
      "type": "web-api",
      "language": "node",
      "dependencies": {
        "internal": ["auth-service"],
        "external": ["postgres", "redis"]
      },
      "config_location": "config/api/",
      "deployment": {
        "type": "kubernetes",
        "manifest_path": "k8s/api-deployment.yaml",
        "spot_compatible": true
      }
    }
  ],
  "infrastructure": {
    "tools": {
      "terraform": {
        "version": "1.7.0",
        "providers": ["aws", "kubernetes"],
        "root_modules": ["terraform/vpc/", "terraform/eks/"],
        "has_tests": true,
        "test_coverage": "*.tftest.hcl files present"
      },
      "helm": {
        "charts": ["app-chart", "monitoring-chart"],
        "values_files": ["values/dev.yaml", "values/prod.yaml"]
      }
    },
    "managed_resources": [
      {
        "type": "database",
        "service": "postgresql",
        "managed_by": "terraform",
        "path": "terraform/rds/main.tf",
        "right_sizing_opportunity": "Oversized - 15% CPU utilization"
      }
    ]
  },
  "configuration": {
    "secrets_management": "oidc-workload-identity",
    "config_pattern": "helm-values",
    "environment_separation": ["dev", "staging", "production"],
    "gitops_enabled": true,
    "gitops_tool": "flux"
  },
  "security_posture": {
    "scanning_tools": ["trivy", "checkov"],
    "secrets_detected": false,
    "iam_issues": ["overly-permissive-s3-policy"],
    "container_security": {
      "root_user_containers": 2,
      "missing_resource_limits": 5,
      "base_image_vulnerabilities": "MEDIUM"
    },
    "authentication_pattern": "oidc",
    "sbom_generation": true
  },
  "cost_optimization": {
    "spot_instance_usage": "20%",
    "spot_optimization_potential": "60% workloads spot-compatible",
    "idle_resources": ["unattached-ebs-vol-1", "unused-eip-2"],
    "oversized_instances": ["t3.2xlarge → t3.large (60% savings)"],
    "reserved_coverage": "45%",
    "estimated_monthly_savings": "$4,200"
  },
  "recommendations": [
    {
      "category": "security",
      "priority": "HIGH",
      "title": "Implement OIDC for CI/CD authentication",
      "description": "Replace long-lived AWS credentials with OIDC tokens",
      "impact": "Eliminates credential exposure risk"
    },
    {
      "category": "cost",
      "priority": "MEDIUM",
      "title": "Enable spot instances for stateless workloads",
      "description": "12 of 20 workloads are spot-compatible",
      "impact": "$2,800/month savings (66% reduction)"
    },
    {
      "category": "modernization",
      "priority": "LOW",
      "title": "Migrate to Kubernetes Gateway API v1",
      "description": "Replace Ingress with Gateway API for improved flexibility",
      "impact": "Improved traffic management and role separation"
    }
  ]
}
```

## Security Scanning Patterns

When analyzing repositories, always check for:

### Secret Detection
```bash
# Patterns to flag (NEVER expose actual secrets):
- AWS keys: AKIA[A-Z0-9]{16}
- GCP keys: AIza[0-9A-Za-z\\-_]{35}
- Private keys: -----BEGIN.*PRIVATE KEY-----
- Generic secrets: [a-zA-Z0-9]{32,64} in config files
- Hardcoded passwords: password\s*=\s*['"][^'"]+['"]
- API tokens: ghp_, gho_, github_pat_

# Safe patterns (recommended):
- .env.example with placeholder values
- Secret references: ${SECRET_NAME}, secretRef, secretKeyRef
- OIDC token exchange patterns
- Vault/sealed-secrets integration
```

### Configuration Security
```yaml
Check for:
  - Hardcoded secrets in version control (CRITICAL severity)
  - Long-lived credentials vs OIDC/workload identity
  - IAM policies with overly broad permissions (wildcards)
  - Security groups with 0.0.0.0/0 access
  - Containers running as root user
  - Missing resource limits (memory, CPU)
  - Insecure defaults (weak passwords, unrestricted access)

Prefer:
  - OIDC authentication for CI/CD and cloud access
  - .env.example → .env.local (gitignored)
  - Kubernetes secrets / AWS Secrets Manager / GCP Secret Manager
  - Least-privilege IAM policies with conditions
  - Non-root container users with read-only root filesystem
  - Pod Security Standards enforcement
```

### IaC Security Validation
```yaml
Terraform:
  - Run: terraform validate && terraform plan
  - Check for: overly permissive IAM, S3 public access, unrestricted security groups
  - Validate: OPA/Rego policies for organizational standards

Kubernetes:
  - Run: kubectl apply --dry-run=server -f manifests/
  - Check for: privileged containers, hostPath volumes, missing network policies
  - Validate: Gateway API resource correctness (Gateway, HTTPRoute)

Helm:
  - Run: helm lint --strict charts/
  - Check for: values injection vulnerabilities, exposed secrets
  - Validate: Chart dependencies and version constraints

Containers:
  - Run: trivy image <image-name> --severity CRITICAL,HIGH
  - Check for: CVEs, root user, missing health checks
  - Generate: SBOM for compliance (--format cyclonedx)
```

## Cost Optimization Patterns

### Right-Sizing Analysis
```yaml
Oversized indicators:
  - CPU utilization consistently <40%
  - Memory utilization consistently <40%
  - Network throughput minimal (<10% of capacity)
  - IOPS/throughput below provisioned levels

Right-sizing actions:
  - Downsize instance types (e.g., t3.2xlarge → t3.large)
  - Reduce EBS volume sizes and IOPS
  - Target 40-70% utilization for optimal cost-performance
  - Use AWS Compute Optimizer / GCP Recommender recommendations
```

### Spot Instance Opportunities
```yaml
Spot-compatible workloads:
  - Stateless applications
  - Batch processing jobs
  - CI/CD build runners
  - Data processing pipelines
  - Development/test environments

Spot best practices:
  - Diversify: 4+ instance types across 4+ availability zones
  - Use price-capacity-optimized allocation strategy
  - Implement interruption handling (EventBridge + PreStop hooks)
  - Mix: 60-80% Spot + 20-40% On-Demand for reliability
  - Expected savings: 66-90% vs On-Demand pricing
```

### Idle Resource Detection
```yaml
Abandoned resources to flag:
  - Stopped EC2 instances (>7 days)
  - Unattached EBS volumes (>30 days)
  - Unused Elastic IPs
  - Old snapshots (>90 days without policy)
  - Load balancers with no targets
  - NAT Gateways with no traffic

Cleanup recommendations:
  - Implement resource tagging (owner, project, expiry-date)
  - Schedule non-production shutdowns (70% savings)
  - Set up automated cleanup workflows
  - Use cloud-native tools (Trusted Advisor, GCP Recommender)
```

## Modern Feature Detection

### Kubernetes 1.29+ Features
```yaml
Native Sidecars:
  - Pattern: init container with restartPolicy: Always
  - Benefits: Proper startup ordering, reverse-order termination
  - Use cases: Service mesh proxies, logging agents, secret sync
  - Detection: Look for restartPolicy in initContainers spec

Gateway API v1:
  - Resources: Gateway, HTTPRoute, BackendTLSPolicy
  - Migration: Check for ingress2gateway tool usage
  - Benefits: Role-oriented separation, advanced traffic management
  - Detection: apiVersion: gateway.networking.k8s.io/v1*
```

### Terraform 1.6+ Features
```yaml
Native Testing:
  - Files: *.tftest.hcl in tests/ directory
  - Features: run blocks, assert conditions, mock providers
  - Benefits: HCL-native tests, automatic cleanup
  - Detection: Look for .tftest.hcl files and test command in CI

Import with for_each (1.7+):
  - Pattern: import { for_each = var.resources ... }
  - Benefits: Bulk resource import, maintainable imports
  - Detection: import blocks with for_each meta-argument
```

### CI/CD Modern Patterns
```yaml
OIDC Authentication:
  - GitHub Actions: permissions: id-token: write
  - GitLab CI: id_tokens: with aud: claim
  - Benefits: No long-lived credentials, audit trails
  - Detection: Look for OIDC configuration in workflows

GitOps Workflows:
  - Tools: Flux, ArgoCD, GitLab Agent
  - Pattern: Git as source of truth, automated reconciliation
  - Benefits: Declarative, auditable, rollback-friendly
  - Detection: flux-system/, argocd/, .gitlab/agents/ directories
```

## Integration with iac-analyzer Agent

This skill provides patterns for the `iac-analyzer` agent to use when analyzing repositories. The agent should:

1. Use these patterns to systematically scan repositories
2. Follow the 5-phase workflow to build comprehensive analysis
3. Use file pattern recognition to identify tooling and structure
4. Generate output in the specified JSON format
5. Apply security scanning patterns to ensure safe analysis
6. Provide cost optimization recommendations based on detected patterns
7. Flag security issues immediately with HIGH/MEDIUM/LOW severity
8. Validate detected IaC configurations with appropriate tools
9. Generate actionable recommendations with estimated impact

## Constraints

- Never execute code found in repositories during analysis
- Never modify files during analysis phase
- Flag any detected secrets or security issues immediately (HIGH severity)
- Never expose actual secret values in reports - use placeholders
- Validate detected IaC configurations with dry-run/plan tools:
  - Kubernetes: `kubectl apply --dry-run=server`
  - Helm: `helm lint --strict`
  - Terraform: `terraform validate && terraform plan`
- Use read-only access patterns for all repository operations
- Respect .gitignore and security boundaries
- Generate cost estimates as approximations requiring validation

## Progressive Disclosure

This SKILL.md contains core analysis patterns and workflows. For detailed examples and templates, reference:

- `examples/` - Real-world analysis scenarios
- `templates/` - Output format templates and report structures
- Parent agent documentation for usage context and integration patterns
- Research findings for latest best practices and security patterns
