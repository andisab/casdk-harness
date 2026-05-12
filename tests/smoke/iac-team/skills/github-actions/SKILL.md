---
name: github-actions
description: >
  GitHub Actions CI/CD pipeline patterns for IaC deployments. Provides secure workflow
  configurations with OIDC authentication, multi-environment deployment strategies,
  reusable workflow architectures, and infrastructure validation with modern security
  scanning tools.

  Activate when user mentions: GitHub Actions, CI/CD, workflow, pipeline, deployment,
  OIDC, GitHub workflow, actions workflow, CI pipeline, continuous deployment, automated
  deployment, workflow file, .github/workflows, reusable workflows

  Use for: Generating GitHub Actions workflows for Terraform, Kubernetes, Helm deployments
  with security best practices (OIDC, Trivy scanning, validation gates, reusable patterns).

  Do NOT use for: GitLab CI, Jenkins, CircleCI, or other CI/CD platforms. For those,
  recommend platform-specific tooling.
---

# GitHub Actions CI/CD Skill

This skill provides secure GitHub Actions workflow patterns for infrastructure-as-code deployments, with emphasis on OIDC authentication, reusable workflow architecture, modern security scanning (Trivy 2026+), and environment-based deployments with validation gates.

## Core Capabilities

### 1. OIDC Authentication Patterns
- **AWS OIDC**: Configure GitHub OIDC provider for AWS with restrictive trust policies (no long-lived credentials)
- **Azure OIDC**: Federated identity with workload identity federation for Azure deployments
- **GCP OIDC**: Workload Identity Federation for GCP with service account impersonation
- **Kubernetes OIDC**: Service account token projection for direct cluster authentication
- **Trust Policy Hardening**: Repository and branch restrictions in cloud IAM policies
- **Token Lifecycle Management**: Handle expiration and renewal for long-running jobs

### 2. Reusable Workflow Architecture
- **Workflow Templates**: Centralized pipeline patterns using `workflow_call` trigger
- **Version Pinning**: Commit SHA or semantic version tags (never `@main` in production)
- **Input/Output Contracts**: Explicit inputs/secrets/outputs with documentation
- **Composite Actions**: Task-level reusability (distinct from pipeline orchestration)
- **Multi-Repository Patterns**: Organization-wide workflow libraries with up to 10 nesting levels
- **Breaking Change Management**: Versioning strategies to protect existing callers

### 3. Workflow Structures
- **Terraform Workflows**: Plan on PR, apply on merge, drift detection on schedule
- **Kubernetes Workflows**: Manifest validation, dry-run, progressive rollout with health checks
- **Helm Workflows**: Chart linting, template validation, staged releases with approval gates
- **Multi-Environment**: Dev → staging → production promotion with artifact reuse (build once)
- **Matrix Strategies**: Parallel testing with fail-fast, dynamic generation for monorepos
- **Artifact Management**: Build once, pass artifacts between stages (no rebuilds)

### 4. Security Controls
- **Modern Scanning Tools**: Trivy (replaces tfsec 2026), Checkov for multi-platform IaC
- **Severity-Based Thresholds**: Fail on CRITICAL/HIGH, warn on MEDIUM/LOW
- **Secret Management**: GitHub secrets, environment secrets, OIDC tokens (never hardcoded)
- **Validation Gates**: Required checks, manual approvals, security scanning with --ignore-unfixed
- **Audit Logging**: Deployment tracking, change attribution, compliance reporting
- **Least Privilege**: Minimal token permissions (id-token: write, contents: read), scoped OIDC roles

### 5. Performance Optimization
- **Docker Build Caching**: type=gha cache reducing build time by 80%+
- **Matrix Optimization**: include/exclude rules, max-parallel tuning, fail-fast: true
- **Database Caching**: Trivy vulnerability database caching between runs
- **Dependency Management**: Artifact passing, same build scripts locally and in CI

## Usage Instructions

### When Generating Workflows

1. **Identify Deployment Target**
   - What infrastructure? (Terraform, Kubernetes, Helm)
   - Which cloud provider? (AWS, Azure, GCP)
   - Environment strategy? (Single, multi-env, progressive rollout)
   - Reusability needs? (Single repo or organization-wide template)

2. **Configure Authentication**
   - **Always prefer OIDC** over long-lived credentials (eliminate secrets)
   - Set `permissions:` block explicitly (principle of least privilege)
   - Use restrictive IAM trust policies with repository and branch conditions
   - Configure environment protection rules when using OIDC with environments
   - Handle token expiration for jobs >1 hour duration

3. **Implement Reusable Patterns**
   - Use `workflow_call` for pipeline templates (job orchestration)
   - Use composite actions for task templates (step-level reuse)
   - Pin workflow references to commit SHA or tags in production (`uses: org/repo/.github/workflows/ci.yml@v1.2.3`)
   - Define explicit inputs/secrets/outputs with documentation
   - Version workflows using semantic versioning for breaking changes

4. **Add Security Scanning**
   - **Use Trivy** (2026 standard, replaces deprecated tfsec)
     - Container vulnerabilities, IaC misconfigurations, secrets, licenses
     - Update vulnerability database before each scan
     - Use `--severity CRITICAL,HIGH` and `--ignore-unfixed` flags
     - Cache database between pipeline runs for performance
   - **Use Checkov** for multi-platform IaC (CloudFormation, Kubernetes, ARM)
     - 2000+ built-in policies for compliance (CIS, PCI-DSS, GDPR)
     - Dockerfile and K8s manifest configuration scanning
   - **Set severity-based thresholds**: Fail on CRITICAL/HIGH, warn on MEDIUM/LOW
   - Document exceptions in `.trivyignore` with review dates and approvals

5. **Add Validation Gates**
   - `terraform validate` and `terraform plan` before apply
   - `kubectl --dry-run=server` for Kubernetes manifests
   - `helm lint --strict` for Helm charts
   - Security scanning with appropriate failure thresholds
   - Manual approval gates for production deployments

6. **Structure Multi-Environment Pipelines**
   - Separate jobs for plan/validate vs. apply/deploy
   - Use `environment:` for approval gates and environment-specific secrets
   - **Build once, promote artifacts** (don't rebuild for each environment)
   - Use `needs:` for explicit job dependencies (enable parallelization)
   - Implement rollback automation triggered on health check failures

7. **Optimize Performance**
   - Use type=gha cache for Docker builds (80% time reduction)
   - Enable `fail-fast: true` on matrix builds to cancel on first failure
   - Cache Trivy vulnerability database between runs
   - Set appropriate `max-parallel` for runner pool capacity
   - Implement dynamic matrix generation for monorepos (test only changed services)

8. **Handle Secrets Securely**
   - Never hardcode secrets in workflow files
   - Use GitHub secrets (repository-level) or environment secrets
   - Reference `.env.example` pattern for required secret documentation
   - Rotate credentials regularly (or eliminate with OIDC)
   - Use `secrets: inherit` for reusable workflows that need access

### Pattern Selection Guide

| Use Case | Recommended Pattern | Key Features |
|----------|---------------------|-------------|
| Terraform on AWS | OIDC + reusable workflow + plan-on-PR | Restrictive trust policy, apply-on-merge, drift detection |
| Kubernetes deploy | OIDC + dry-run + progressive rollout | Health checks, canary deployment, auto-rollback |
| Helm release | Reusable workflow + staged release | Chart lint, environment-specific values, approval gates |
| Multi-cloud IaC | Matrix strategy + OIDC | price-capacity-optimized, 4+ instance types/AZs |
| Organization library | Reusable workflow with workflow_call | Pinned versions, input contracts, centralized maintenance |
| Monorepo CI/CD | Dynamic matrix + artifact caching | Path-based triggering, test only changed services |

## Security Best Practices

### OIDC Configuration

**AWS OIDC with Restrictive Trust Policy**:
```yaml
permissions:
  id-token: write  # Required for OIDC token generation
  contents: read   # Minimal read access
  # NEVER use: write-all or permissions: write

- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789012:role/github-oidc-terraform-role
    aws-region: us-east-1
    # Role trust policy MUST include:
    # - Condition on token.actions.githubusercontent.com:sub for specific repo/branch
    # - Condition on token.actions.githubusercontent.com:aud: "sts.amazonaws.com"
```

**AWS IAM Trust Policy Example** (restrictive):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main"
      }
    }
  }]
}
```

**Azure OIDC with Workload Identity**:
```yaml
permissions:
  id-token: write
  contents: read

- name: Azure Login
  uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
    # Uses workload identity federation (no client secrets)
```

**GCP OIDC with Workload Identity Federation**:
```yaml
permissions:
  id-token: write
  contents: read

- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/123456789/locations/global/workloadIdentityPools/github/providers/github-provider
    service_account: github-actions@project-id.iam.gserviceaccount.com
```

### Secret Scanning Prevention

- Use `.env.example` with placeholder values (NEVER real secrets)
- Document required secrets in README with descriptions
- Enable GitHub secret scanning in repository settings
- Use `gitleaks` or `truffleHog` in pre-commit hooks
- Rotate credentials regularly (quarterly minimum) or eliminate with OIDC

### Minimal Permissions

**Principle of least privilege** for workflow tokens:
```yaml
permissions:
  id-token: write      # OIDC token generation only
  contents: read       # Checkout code (read-only)
  pull-requests: write # Comment on PRs (if needed)
  # NEVER grant: write-all, contents: write, actions: write (unless absolutely required)
```

## Reusable Workflow Patterns

### Creating Reusable Workflows

**Reusable workflow definition** (`.github/workflows/terraform-reusable.yml`):
```yaml
name: Reusable Terraform Workflow

on:
  workflow_call:
    inputs:
      terraform_version:
        required: false
        type: string
        default: "1.7.0"
      working_directory:
        required: true
        type: string
      environment:
        required: true
        type: string
    secrets:
      aws_role_arn:
        required: true
    outputs:
      plan_exitcode:
        description: "Terraform plan exit code"
        value: ${{ jobs.terraform.outputs.exitcode }}

jobs:
  terraform:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    outputs:
      exitcode: ${{ steps.plan.outputs.exitcode }}
    permissions:
      id-token: write
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.aws_role_arn }}
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ inputs.terraform_version }}

      - name: Terraform Init
        working-directory: ${{ inputs.working_directory }}
        run: terraform init

      - name: Terraform Plan
        id: plan
        working-directory: ${{ inputs.working_directory }}
        run: terraform plan -no-color -out=tfplan
        continue-on-error: true

      - name: Comment Plan on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const output = `#### Terraform Plan 📋
            <details><summary>Show Plan</summary>

            \`\`\`terraform
            ${{ steps.plan.outputs.stdout }}
            \`\`\`

            </details>`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            });
```

**Calling reusable workflow** (in another repository):
```yaml
name: Deploy Infrastructure

on:
  push:
    branches: [main]
    paths: ['infrastructure/**']
  pull_request:
    branches: [main]
    paths: ['infrastructure/**']

jobs:
  terraform-dev:
    uses: org/shared-workflows/.github/workflows/terraform-reusable.yml@v1.2.3  # Pin to version!
    with:
      working_directory: infrastructure/dev
      environment: dev
      terraform_version: "1.7.0"
    secrets:
      aws_role_arn: ${{ secrets.AWS_DEV_ROLE_ARN }}

  terraform-prod:
    needs: terraform-dev
    if: github.ref == 'refs/heads/main'
    uses: org/shared-workflows/.github/workflows/terraform-reusable.yml@v1.2.3
    with:
      working_directory: infrastructure/prod
      environment: production  # Requires manual approval
      terraform_version: "1.7.0"
    secrets:
      aws_role_arn: ${{ secrets.AWS_PROD_ROLE_ARN }}
```

**Key reusable workflow principles**:
- Pin to commit SHA or semantic version tags (NEVER `@main` in production)
- Define explicit inputs with types and defaults
- Use `secrets: inherit` or explicit secrets parameters
- Document all inputs/outputs in workflow comments
- Use semantic versioning for breaking changes (v1.x.x → v2.0.0)

## Security Scanning Integration

### Trivy Security Scanning (2026 Standard)

**Trivy replaces tfsec** as of 2026 - it provides:
- Container vulnerability scanning
- IaC misconfiguration detection (Terraform, CloudFormation, Kubernetes, Dockerfile)
- Secret detection in code
- License scanning (SBOM generation)

**Trivy configuration** (recommended):
```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'config'  # For IaC scanning
    scan-ref: 'infrastructure/'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'  # Fail on CRITICAL/HIGH only
    ignore-unfixed: true  # Don't block on vulnerabilities without fixes
    # Database caching for performance:
    cache-dir: .trivy-cache

- name: Upload Trivy results to GitHub Security
  uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: 'trivy-results.sarif'

- name: Fail on Critical/High vulnerabilities
  if: steps.trivy.outputs.scan-results != '0'
  run: exit 1
```

**Trivy for container scanning**:
```yaml
- name: Build Docker image
  run: docker build -t myapp:${{ github.sha }} .

- name: Scan container image with Trivy
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'myapp:${{ github.sha }}'
    format: 'table'
    severity: 'CRITICAL,HIGH'
    ignore-unfixed: true
    vuln-type: 'os,library'
    # Update vulnerability database before scan:
    skip-db-update: false
```

**Trivy exception handling** (`.trivyignore`):
```
# CVE-2024-1234: PostgreSQL client library - no fix available
# Reviewed: 2026-01-15, Expires: 2026-04-15
# Approved by: security-team@company.com
CVE-2024-1234

# CVE-2024-5678: Low severity, false positive for our use case
# Justification: We don't use the affected module
CVE-2024-5678
```

### Checkov Multi-Platform IaC Scanning

**Checkov for Kubernetes manifests**:
```yaml
- name: Run Checkov on Kubernetes manifests
  uses: bridgecrewio/checkov-action@master
  with:
    directory: k8s/
    framework: kubernetes
    soft_fail: false  # Fail pipeline on policy violations
    skip_check: CKV_K8S_8,CKV_K8S_9  # Document why checks are skipped
    output_format: sarif
    output_file_path: checkov-results.sarif

- name: Upload Checkov results
  uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: checkov-results.sarif
```

**Checkov for Terraform with compliance frameworks**:
```yaml
- name: Run Checkov on Terraform with CIS compliance
  uses: bridgecrewio/checkov-action@master
  with:
    directory: terraform/
    framework: terraform
    soft_fail: false
    compact: true
    # Check against CIS benchmarks:
    check: CKV_AWS_*,CKV2_AWS_*
    # Generate SBOM for compliance:
    output_format: cli,sarif,json
```

## Workflow Triggers

### Common Trigger Patterns

**Plan on PR, Apply on Merge** (recommended for Terraform):
```yaml
on:
  pull_request:
    branches: [main]
    paths: ['terraform/**', 'infrastructure/**']
  push:
    branches: [main]
    paths: ['terraform/**']

jobs:
  terraform-plan:
    if: github.event_name == 'pull_request'
    # ... plan and comment on PR

  terraform-apply:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    # ... apply changes
```

**Scheduled Drift Detection**:
```yaml
on:
  schedule:
    - cron: '0 6 * * MON'  # Every Monday at 6 AM UTC
  workflow_dispatch:        # Allow manual trigger
```

**Multi-Environment Promotion**:
```yaml
on:
  push:
    branches: [main]
  release:
    types: [published]  # Production deployment on release

jobs:
  deploy-dev:
    if: github.event_name == 'push'
    # ... auto-deploy to dev

  deploy-staging:
    needs: deploy-dev
    # ... auto-deploy to staging

  deploy-production:
    if: github.event_name == 'release'
    environment: production  # Requires manual approval
    # ... deploy to production
```

**Path-based triggering for monorepos**:
```yaml
on:
  push:
    paths:
      - 'services/api/**'
      - 'infrastructure/api/**'
      - '.github/workflows/api-deploy.yml'
  # Don't trigger on documentation changes:
  paths-ignore:
    - '**.md'
    - 'docs/**'
```

## Matrix Strategy Optimization

### Efficient Matrix Builds

**Basic matrix with fail-fast**:
```yaml
strategy:
  fail-fast: true  # Cancel remaining jobs on first failure
  max-parallel: 4  # Tune based on runner availability
  matrix:
    terraform_version: ['1.6.0', '1.7.0', '1.8.0']
    cloud_provider: ['aws', 'azure', 'gcp']
    # This creates 9 jobs (3 × 3)
```

**Matrix with include/exclude optimization**:
```yaml
strategy:
  fail-fast: true
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    version: ['1.6', '1.7', '1.8']
    # Exclude invalid combinations:
    exclude:
      - os: macos-latest
        version: '1.6'  # Not supported
      - os: windows-latest
        version: '1.6'  # Not supported
    # Add specific combinations:
    include:
      - os: ubuntu-latest
        version: '1.9-beta'  # Test beta only on Linux
```

**Dynamic matrix generation for monorepos**:
```yaml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set-matrix.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect changed services
        id: set-matrix
        run: |
          # Generate matrix based on changed files
          changed_services=$(git diff --name-only HEAD~1 HEAD | grep '^services/' | cut -d'/' -f2 | sort -u | jq -R -s -c 'split("\n")[:-1]')
          echo "matrix={\"service\":$changed_services}" >> $GITHUB_OUTPUT

  test-changed-services:
    needs: detect-changes
    if: needs.detect-changes.outputs.matrix != '{"service":[]}'
    strategy:
      fail-fast: true
      matrix: ${{ fromJson(needs.detect-changes.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - name: Test ${{ matrix.service }}
        run: |
          echo "Testing only changed service: ${{ matrix.service }}"
          # Run tests for specific service
```

**Docker build with type=gha caching** (80% time reduction):
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and push with cache
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: myapp:${{ github.sha }}
    cache-from: type=gha  # Use GitHub Actions cache
    cache-to: type=gha,mode=max  # Cache all layers
```

## Validation Strategies

### Terraform Validation

**Complete validation pipeline**:
```yaml
- name: Terraform Format Check
  run: terraform fmt -check -recursive
  working-directory: infrastructure/

- name: Terraform Init
  run: terraform init -backend=false  # Skip backend for validation
  working-directory: infrastructure/

- name: Terraform Validate
  run: terraform validate
  working-directory: infrastructure/

- name: Security Scan with Trivy
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'config'
    scan-ref: 'infrastructure/'
    severity: 'CRITICAL,HIGH'
    ignore-unfixed: true
    exit-code: 1  # Fail on findings

- name: Terraform Plan
  id: plan
  run: terraform plan -no-color -out=tfplan
  working-directory: infrastructure/

- name: Comment Plan on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const output = `#### Terraform Plan 📋\n\`\`\`terraform\n${process.env.PLAN_OUTPUT}\n\`\`\``;
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: output
      });
  env:
    PLAN_OUTPUT: ${{ steps.plan.outputs.stdout }}
```

### Kubernetes Validation

**Manifest validation with security scanning**:
```yaml
- name: Validate Kubernetes manifests
  run: |
    # Syntax validation
    kubectl apply --dry-run=client -f manifests/ -o yaml

    # Server-side validation (if cluster available)
    kubectl apply --dry-run=server -f manifests/

- name: Security scan with Checkov
  uses: bridgecrewio/checkov-action@master
  with:
    directory: manifests/
    framework: kubernetes
    soft_fail: false

- name: Policy validation with Kubesec
  uses: controlplaneio/kubesec-action@v0.0.2
  with:
    input: manifests/*.yaml
    threshold: 7  # Minimum score

- name: Check for containers running as root
  run: |
    if grep -r "runAsUser: 0" manifests/; then
      echo "ERROR: Containers must not run as root"
      exit 1
    fi
```

### Helm Validation

**Chart validation and testing**:
```yaml
- name: Helm Lint
  run: helm lint --strict charts/my-chart

- name: Template Validation
  run: |
    # Generate templates and validate
    helm template charts/my-chart | kubectl apply --dry-run=server -f -

- name: Security scan on generated manifests
  run: |
    helm template charts/my-chart > rendered-manifests.yaml
    trivy config rendered-manifests.yaml --severity CRITICAL,HIGH

- name: Helm Test (if test chart exists)
  run: |
    helm install test-release charts/my-chart
    helm test test-release
    helm uninstall test-release
```

## Environment-Based Deployments

### GitHub Environments Setup

**Configure in repository settings → Environments**:
- **dev**:
  - Auto-deploy on push
  - No approval required
  - Dev-specific secrets (AWS_DEV_ROLE_ARN)

- **staging**:
  - Auto-deploy after dev success
  - Optional reviewers (team leads)
  - Staging-specific secrets

- **production**:
  - Required reviewers (2+ approvers)
  - Deployment branch protection (main only)
  - Production secrets
  - Wait timer (optional - e.g., 5 min delay)

### Workflow Environment Usage

**Multi-environment deployment with artifact reuse**:
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Save image as artifact
        run: |
          docker save myapp:${{ github.sha }} | gzip > image.tar.gz

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: image.tar.gz

  deploy-dev:
    needs: build
    environment: dev
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: docker-image

      - name: Load image
        run: docker load -i image.tar.gz

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEV_ROLE_ARN }}
          aws-region: us-east-1

      - name: Push to ECR and deploy
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
          docker tag myapp:${{ github.sha }} $ECR_REGISTRY/myapp:${{ github.sha }}
          docker push $ECR_REGISTRY/myapp:${{ github.sha }}
          # Deploy to dev environment

  deploy-staging:
    needs: deploy-dev
    environment: staging
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Download artifact (reuse same build!)
        uses: actions/download-artifact@v4
        with:
          name: docker-image

      # Similar deployment steps for staging

  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    environment: production  # Requires manual approval
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Download artifact (reuse same build!)
        uses: actions/download-artifact@v4
        with:
          name: docker-image

      # Production deployment with health checks

      - name: Health check
        run: |
          # Wait for deployment and check health
          for i in {1..30}; do
            if curl -f https://api.production.example.com/health; then
              echo "Health check passed"
              exit 0
            fi
            sleep 10
          done
          echo "Health check failed"
          exit 1

      - name: Rollback on failure
        if: failure()
        run: |
          # Automated rollback logic
          kubectl rollout undo deployment/myapp -n production
```

## Rollback Strategies

### Automated Rollback on Health Check Failure

```yaml
- name: Deploy to production
  id: deploy
  run: |
    kubectl set image deployment/myapp myapp=$ECR_REGISTRY/myapp:${{ github.sha }} -n production
    kubectl rollout status deployment/myapp -n production --timeout=5m

- name: Health check
  id: healthcheck
  run: |
    sleep 30  # Wait for pods to be ready
    for i in {1..10}; do
      if curl -f https://api.production.example.com/health; then
        echo "Health check passed"
        exit 0
      fi
      sleep 10
    done
    echo "Health check failed"
    exit 1

- name: Rollback on failure
  if: failure() && steps.deploy.outcome == 'success'
  run: |
    echo "Rolling back deployment due to health check failure"
    kubectl rollout undo deployment/myapp -n production
    kubectl rollout status deployment/myapp -n production --timeout=5m

- name: Notify team on rollback
  if: failure() && steps.deploy.outcome == 'success'
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '⚠️ **Automatic rollback triggered** due to failed health checks. Please investigate.'
      });
```

## Troubleshooting

### OIDC Authentication Failures

**Symptom**: `Error: Could not assume role with OIDC`

**Solutions**:
1. Verify IAM trust policy includes correct GitHub repo and branch:
   ```json
   "Condition": {
     "StringEquals": {
       "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main"
     }
   }
   ```
2. Check `permissions: id-token: write` is set in workflow
3. Ensure OIDC provider is configured in cloud account (AWS: Identity Provider, Azure: Federated Credential, GCP: Workload Identity Pool)
4. Validate token audience claim matches cloud provider expectation
5. Check environment protection rules don't conflict with OIDC access

### Token Expiration in Long-Running Jobs

**Symptom**: `Error: The security token included in the request is expired`

**Solutions**:
1. Break long deployments into smaller jobs with checkpoints
2. Configure cloud provider token duration appropriately (AWS: max 12 hours)
3. Implement token refresh logic for jobs >1 hour
4. Use job matrices to parallelize instead of sequential long-running jobs

### Permission Denied Errors

**Symptom**: `Error: Resource not accessible by integration`

**Solutions**:
1. Add required permission to `permissions:` block (e.g., `pull-requests: write` for PR comments)
2. Check repository settings allow Actions to access resource (Settings → Actions → General → Workflow permissions)
3. Verify environment protection rules allow workflow access
4. Check branch protection settings don't block Actions
5. Ensure `secrets: inherit` is used when calling reusable workflows that need secrets

### Secret Not Found

**Symptom**: `Error: Secret MY_SECRET not found`

**Solutions**:
1. Verify secret exists in repository or environment (Settings → Secrets and variables → Actions)
2. Check secret name matches exactly (case-sensitive)
3. Ensure workflow has access to environment if using environment secrets
4. Use `secrets: inherit` for reusable workflows
5. Check environment is spelled correctly in `environment:` field

### Reusable Workflow Not Found

**Symptom**: `Error: Unable to resolve action org/repo/.github/workflows/workflow.yml@v1.2.3`

**Solutions**:
1. Verify workflow file exists at specified path in repository
2. Check reference (commit SHA or tag) exists
3. Ensure repository is accessible (public or proper access for private)
4. Validate workflow has `workflow_call` trigger defined
5. Check for typos in workflow path

### Security Scan False Positives

**Symptom**: Pipeline blocked by Trivy finding that's not applicable

**Solutions**:
1. Update Trivy database: `skip-db-update: false`
2. Use `--ignore-unfixed` for vulnerabilities without available patches
3. Document exceptions in `.trivyignore` with expiration dates
4. Set severity threshold to CRITICAL/HIGH only
5. Verify finding against multiple sources before marking as false positive

## Integration with IaC Team Plugin

This skill is designed to be referenced by the `iac-generator` agent when creating CI/CD workflows:

**Generator should**:
1. Call this skill's patterns based on detected infrastructure type
2. Generate reusable workflows for organization-wide consistency
3. Configure OIDC with restrictive trust policies based on target environment
4. Include modern security scanning (Trivy 2026) with appropriate thresholds
5. Implement artifact reuse pattern (build once, deploy multiple environments)
6. Add rollback automation triggered on health check failures
7. Optimize performance with Docker build caching (type=gha) and fail-fast
8. Pin workflow versions in production (commit SHA or semantic version tags)

**Generator should NOT**:
1. Generate workflows from scratch (use reusable patterns from this skill)
2. Include long-lived credentials (always use OIDC)
3. Skip validation or security scanning steps
4. Hardcode environment-specific values (use inputs/secrets)
5. Use deprecated tools (tfsec → Trivy, certificate-based K8s → GitLab Agent)
6. Reference workflows with `@main` in production (use versioned references)
7. Create separate workflows for each environment (use reusable workflows)
8. Rebuild artifacts for each environment (build once, promote)

## Workflow Examples

### Complete Terraform AWS Workflow with OIDC and Reusable Pattern

```yaml
name: Terraform AWS Infrastructure

on:
  pull_request:
    branches: [main]
    paths: ['infrastructure/**']
  push:
    branches: [main]
    paths: ['infrastructure/**']
  schedule:
    - cron: '0 6 * * MON'  # Drift detection

permissions:
  id-token: write  # OIDC
  contents: read
  pull-requests: write

jobs:
  terraform-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Terraform Format Check
        run: terraform fmt -check -recursive
        working-directory: infrastructure/

      - name: Terraform Init
        run: terraform init -backend=false
        working-directory: infrastructure/

      - name: Terraform Validate
        run: terraform validate
        working-directory: infrastructure/

      - name: Security Scan with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'config'
          scan-ref: 'infrastructure/'
          severity: 'CRITICAL,HIGH'
          ignore-unfixed: true
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

  terraform-plan:
    needs: terraform-validate
    if: github.event_name == 'pull_request' || github.event_name == 'schedule'
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-oidc-terraform-plan
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Terraform Init
        run: terraform init
        working-directory: infrastructure/

      - name: Terraform Plan
        id: plan
        run: terraform plan -no-color -out=tfplan
        working-directory: infrastructure/
        continue-on-error: true

      - name: Comment Plan on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const output = `#### Terraform Plan 📋
            <details><summary>Show Plan</summary>

            \`\`\`terraform
            ${{ steps.plan.outputs.stdout }}
            \`\`\`

            </details>

            **Pusher**: @${{ github.actor }}
            **Action**: ${{ github.event_name }}`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            });

  terraform-apply:
    needs: terraform-validate
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-oidc-terraform-apply
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Terraform Init
        run: terraform init
        working-directory: infrastructure/

      - name: Terraform Apply
        run: terraform apply -auto-approve
        working-directory: infrastructure/
```

### Kubernetes Progressive Rollout with Health Checks

```yaml
name: Kubernetes Progressive Rollout

on:
  push:
    branches: [main]
    paths: ['k8s/**', 'src/**']

permissions:
  id-token: write
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          tags: myapp:${{ github.sha }}
          outputs: type=docker,dest=/tmp/image.tar
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: /tmp/image.tar

  deploy-canary:
    needs: build
    environment: production-canary
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: docker-image
          path: /tmp

      - name: Load image
        run: docker load -i /tmp/image.tar

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_EKS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name production-cluster --region us-east-1

      - name: Validate manifests
        run: kubectl apply --dry-run=server -f k8s/

      - name: Security scan manifests
        uses: bridgecrewio/checkov-action@master
        with:
          directory: k8s/
          framework: kubernetes
          soft_fail: false

      - name: Push image to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker tag myapp:${{ github.sha }} ${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }}
          docker push ${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }}

      - name: Deploy canary (10% traffic)
        run: |
          kubectl set image deployment/myapp-canary myapp=${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }} -n production
          kubectl rollout status deployment/myapp-canary -n production --timeout=5m

      - name: Canary health check
        id: canary-health
        run: |
          sleep 60  # Wait for metrics
          error_rate=$(kubectl exec -n production deploy/myapp-canary -- curl -s http://localhost:9090/metrics | grep error_rate | awk '{print $2}')
          if (( $(echo "$error_rate > 0.05" | bc -l) )); then
            echo "Canary error rate too high: $error_rate"
            exit 1
          fi
          echo "Canary health check passed: error_rate=$error_rate"

  deploy-production:
    needs: deploy-canary
    environment: production
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_EKS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name production-cluster --region us-east-1

      - name: Deploy production (100% traffic)
        id: deploy
        run: |
          kubectl set image deployment/myapp myapp=${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }} -n production
          kubectl rollout status deployment/myapp -n production --timeout=10m

      - name: Production health check
        id: health
        run: |
          sleep 30
          for i in {1..10}; do
            if curl -f https://api.production.example.com/health; then
              echo "Production health check passed"
              exit 0
            fi
            sleep 10
          done
          echo "Production health check failed"
          exit 1

      - name: Rollback on failure
        if: failure() && steps.deploy.outcome == 'success'
        run: |
          echo "Rolling back production deployment"
          kubectl rollout undo deployment/myapp -n production
          kubectl rollout status deployment/myapp -n production --timeout=5m

          # Also rollback canary
          kubectl rollout undo deployment/myapp-canary -n production
```

## Version Compatibility

- **GitHub Actions**: v4+ (checkout, setup actions)
- **AWS OIDC action**: v4+ (`aws-actions/configure-aws-credentials@v4`)
- **Azure Login action**: v2+ (`azure/login@v2`)
- **GCP Auth action**: v2+ (`google-github-actions/auth@v2`)
- **Trivy**: Latest (replaces tfsec 2026+)
- **Checkov**: Latest (2000+ policies)
- **Terraform**: 1.6+ (native testing), 1.7+ (import with for_each, mocking)
- **Kubernetes**: 1.29+ (native sidecars), 1.31+ (Gateway API v1 GA)
- **Helm**: 3.0+

## Updates and Maintenance

When updating this skill:
1. Test patterns in real repositories before updating skill
2. Update action versions for security patches (use Dependabot)
3. Migrate from deprecated tools (tfsec → Trivy completed in 2026)
4. Review and update OIDC trust policy recommendations
5. Validate against current GitHub Actions features and limits
6. Update reusable workflow examples with latest best practices
7. Add new security scanning patterns as tools evolve
8. Document breaking changes in workflow patterns with migration guides
9. Keep version compatibility matrix current
10. Test rollback and health check patterns under realistic failure scenarios
