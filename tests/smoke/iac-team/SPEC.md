# Plugin Spec: IaC Team (AWS + Kubernetes)

## Purpose

Multi-agent plugin for Infrastructure-as-Code automation that can:
- Analyze existing repositories to understand structure and dependencies
- Generate containerization and deployment resources (Docker, Kubernetes, Terraform)
- Validate security and best practices before deployment
- Support **AWS and Kubernetes** with GitOps workflows

> **Smoke-test scope note (2026-05-11):** Trimmed from the original
> multi-cloud SPEC to AWS + Kubernetes only. GCP-specific resources
> (gcloud-cli, gcp-gke) were removed so that smoke runs can validate
> against a single, locally-provisionable infrastructure stack
> (kind / localstack or real AWS via `setup.sh`).

## Target Users

- Platform engineers adding IaC to existing applications
- DevOps teams standardizing deployment patterns
- Developers needing production-ready infrastructure templates

## Capabilities

### Core Workflows

1. **Repository Analysis** - Scan codebase, identify services, map dependencies, detect patterns
2. **Resource Generation** - Create Dockerfiles, K8s manifests, Terraform modules, CI/CD pipelines
3. **Security Validation** - Scan generated resources, ensure policy compliance, dry-run validation
4. **CI/CD Integration** - GitHub Actions and GitLab CI pipeline generation with OIDC auth

### Platform Support

- **AWS**: EKS, ECS, ECR, IRSA, AWS CLI operations
- **GitOps**: ArgoCD, Flux patterns with progressive delivery (Kubernetes-native)
- **IaC Tools**: Terraform, Helm, Kustomize, Crossplane, Pulumi/CDK

## Constraints

- Generated resources must pass security scanning (no CRITICAL/HIGH findings)
- No hardcoded secrets in any generated resource (use an `.env.example` -> `.env.local` and `.env.production` pattern for storing secrets)
- Prefer OIDC over long-lived credentials for CI/CD
- Kubernetes manifests must pass `kubectl --dry-run=client` validation
- Helm charts must pass `helm lint --strict`

## Quality Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| Dockerfile build success | 100% | `docker build` (local) |
| K8s manifest validation | Pass `kubeconform` | local CLI |
| Terraform syntax | Zero errors | `terraform validate` (no init needed) |
| Helm lint | Pass `--strict` | `helm lint` (local) |
| Security scan | No CRITICAL/HIGH | `tfsec`, `trivy fs`, `checkov` (local) |
| GitOps manifest | Renders ArgoCD/Flux YAML | local schema validation |

> **Note on cloud-required checks:** This SPEC was trimmed so eval graders
> can run against locally-provisioned infrastructure (kind cluster +
> optional localstack). Graders that need real cloud (e.g.,
> `aws eks describe-cluster`) should be replaced with their CLI-only
> equivalents (e.g., `terraform validate`).

## Research Topics

- Kubernetes 1.31+ features (Gateway API, sidecar containers)
- Terraform 1.7+ patterns (testing framework, import blocks)
- GitHub Actions 2025 patterns (OIDC, reusable workflows, matrix strategies)
- GitLab CI/CD patterns (DAG pipelines, GitLab Agent for K8s)
- AI-assisted IaC best practices
- Container security hardening (Trivy, tfsec, checkov)
- Cost optimization (spot instances, autoscaling, right-sizing)

## Proposed Structure

> Research should validate and may suggest improvements.

### Agents

- **iac-analyzer** - Repository analysis and dependency mapping
  - Skills: repo-analysis
  - Purpose: Understand codebase before generating resources

- **iac-generator** - Resource generation from analysis
  - Skills: container-analysis, kubernetes-native, helm-charts, terraform-modules, aws-eks, gitops-argocd, gitops-flux, github-actions, gitlab-ci, aws-cli, crossplane, pulumi-cdk
  - Purpose: Generate production-ready IaC resources

- **iac-validator** - Security and policy validation
  - Skills: security-validation
  - Purpose: Validate generated resources before deployment

### Skills

| Skill | Purpose | Agent |
|-------|---------|-------|
| repo-analysis | Codebase understanding | iac-analyzer |
| container-analysis | Dockerfile generation | iac-generator |
| kubernetes-native | K8s resource generation | iac-generator |
| helm-charts | Helm chart development | iac-generator |
| terraform-modules | Terraform/OpenTofu patterns | iac-generator |
| gitops-argocd | ArgoCD patterns | iac-generator |
| gitops-flux | Flux patterns | iac-generator |
| aws-eks | AWS EKS/ECS specialization | iac-generator |
| aws-cli | AWS CLI operations | iac-generator |
| crossplane | Crossplane compositions | iac-generator |
| pulumi-cdk | Pulumi/CDK patterns | iac-generator |
| github-actions | GitHub Actions CI/CD | iac-generator |
| gitlab-ci | GitLab CI/CD patterns | iac-generator |
| security-validation | Security scanning | iac-validator |

### Commands

- **/iac** - Main entry point for IaC operations
  - `/iac analyze --repo <path>` - Analyze repository
  - `/iac generate --target <platform>` - Generate resources
  - `/iac validate --path <path>` - Validate resources
  - `/iac deploy --repo <path> --gitops <tool>` - Full pipeline

## Optimization Focus

### Priority 1: Agent Quality
- Improve agent instruction clarity and completeness
- Ensure proper skill loading and handoff protocols
- Validate agent coordination in multi-step workflows

### Priority 2: Skill Coverage
- Ensure each skill covers current tool versions (2025+)
- Add reference links to latest documentation for each language/tool
- Add missing patterns identified in research
- Remove outdated practices

### Priority 3: Security Hardening
- Validate security patterns in all generated resources
- Ensure OIDC patterns are current
- Add supply chain security (SLSA, Sigstore)

## Pipeline Guidance

1. **RESEARCH** - Gather current best practices for each skill domain
2. **GENERATE** - Create full content for the placeholder skills
3. **ITERATE** - Generate or improve all resources based on research
4. **VALIDATE** - Cross-resource coherence check
