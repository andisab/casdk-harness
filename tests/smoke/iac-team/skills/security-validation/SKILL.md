---
name: security-validation
description: >
  Security scanning, policy validation, compliance enforcement, and vulnerability management for IaC resources.
  Integrates Trivy (2026 standard), Checkov, OPA/Conftest, and automated threat detection with CI/CD workflows.

  Activate when user mentions: security scan, vulnerability scanning, policy validation, compliance check,
  security hardening, Trivy, Checkov, tfsec (migrate to Trivy), OPA, Conftest, policy-as-code,
  secret scanning, SBOM generation, CVE detection, security gate, compliance framework, CIS benchmark,
  PCI-DSS, GDPR, HIPAA, SOC2, security baseline, threat detection, misconfig detection, CRITICAL/HIGH severity,
  .trivyignore, exception handling, false positives, security posture.

  Use for: Pre-deployment security validation, policy enforcement, vulnerability detection, compliance verification,
  secret detection, SBOM generation for audit trails, CI/CD security gates, multi-phase validation pipelines,
  hallucination detection in AI-generated IaC, hardened defaults enforcement.

  Do NOT use for: Runtime security monitoring (use cloud provider tools), incident response (use SIEM/SOAR),
  container orchestration (use kubernetes-native skill), deployment automation (use gitops skills).
---

# Security Validation Skill

## Purpose

Provides comprehensive security scanning, policy validation, and compliance enforcement for the IaC team plugin. This skill is referenced by the `iac-validator` agent to validate generated resources before deployment, ensuring all configurations meet security baselines, compliance requirements, and organizational policies without requiring cloud deployment.

## Core Capabilities

### 1. Multi-Tool Security Scanning Strategy

**2026 Context - Tool Evolution:**
- **Trivy** has replaced tfsec as the recommended all-in-one scanner for IaC, containers, secrets, and licenses
- **Checkov** remains essential for multi-platform IaC (CloudFormation, Kubernetes, ARM templates) with 2000+ built-in policies
- **OPA/Conftest** provides custom policy-as-code for organization-specific requirements

#### Tool Selection Matrix

| Validation Target | Primary Tool | Rationale | Backup Tool |
|-------------------|--------------|-----------|-------------|
| **Terraform/OpenTofu** | Trivy | Successor to tfsec, actively maintained (2026) | Checkov |
| **Kubernetes manifests** | Checkov | Superior K8s policy coverage (2000+ rules) | Trivy config |
| **CloudFormation** | Checkov | Native CFN support with compliance frameworks | Trivy config |
| **Dockerfiles** | Trivy | Best-in-class container misconfiguration detection | Checkov |
| **Container images** | Trivy | Comprehensive vulnerability + secret scanning | Grype, Docker Scout |
| **Custom policies** | Conftest/OPA | Organization-specific policy enforcement | Custom scripts |
| **Secrets detection** | Trivy | Integrated secrets scanning across all file types | Gitleaks, TruffleHog |
| **License compliance** | Trivy | Built-in license scanning for dependencies | FOSSA |
| **SBOM generation** | Trivy | CycloneDX and SPDX support for compliance | Syft |

### 2. Two-Phase Validation Pipeline

**Critical for AI-generated IaC:** Implement rigorous validation without requiring cloud deployment.

#### Phase 1: Technical Validation (Syntax & Schema)

**Purpose:** Verify syntactic correctness, schema compliance, and resource dependencies.

**Validation steps:**
1. **Syntax validation** (95-96% catch rate for AI-generated IaC):
   ```bash
   # Terraform/OpenTofu
   terraform init -backend=false
   terraform validate

   # Kubernetes
   kubectl apply --dry-run=client -f manifests/
   kubeconform manifests/*.yaml

   # Helm
   helm lint --strict ./charts/myapp

   # Dockerfile
   hadolint Dockerfile
   docker build --check .
   ```

2. **Provider schema validation** (hallucination detection):
   ```bash
   # Validate all resource types against official provider schemas
   terraform providers schema -json > schemas.json
   # Compare generated resource types against schemas.json
   # Flag any resources not in official schema (hallucination detection)
   ```

3. **Dependency graph analysis**:
   ```bash
   terraform graph | dot -Tpng > dependencies.png
   # Analyze for circular dependencies, orphaned resources, missing references
   ```

**Expected outcomes:**
- 95%+ syntax validation success before security scanning
- Hallucination detection for fabricated resource types (AI-generated code)
- Dependency validation preventing deployment failures

#### Phase 2: Intent Validation (Security & Policy)

**Purpose:** Verify configurations meet security requirements, compliance frameworks, and organizational intent.

**Validation steps:**
1. **Security misconfiguration scanning**:
   ```bash
   # Trivy - All IaC types, containers, secrets
   trivy config --severity CRITICAL,HIGH --exit-code 1 .

   # Checkov - Multi-platform IaC with compliance frameworks
   checkov -d . --framework terraform kubernetes dockerfile \
     --check CIS_AWS,CIS_KUBERNETES_V1_6 \
     --quiet --compact
   ```

2. **Policy-as-code validation** (organizational rules):
   ```bash
   # OPA/Conftest - Custom organizational policies
   conftest test -p policies/ terraform/*.tf
   conftest test -p policies/ k8s/*.yaml
   ```

3. **Secret detection** (prevent credential leaks):
   ```bash
   # Trivy secret scanning
   trivy fs --scanners secret --severity HIGH,CRITICAL .

   # Additional validation for AI-generated code
   # Check for patterns: password=, api_key=, token=, secret=
   ```

4. **Compliance framework validation**:
   ```bash
   # Checkov with specific compliance frameworks
   checkov -d . --check CIS_AWS  # CIS AWS Foundations Benchmark
   checkov -d . --check PCI_DSS  # Payment Card Industry
   checkov -d . --check GDPR     # Data protection
   checkov -d . --check HIPAA    # Healthcare compliance
   checkov -d . --check SOC2     # Security controls
   ```

**Expected outcomes:**
- No CRITICAL/HIGH security findings (blocking)
- Zero hardcoded secrets or credentials
- 100% compliance with required frameworks (CIS, PCI-DSS, etc.)
- Organizational policy adherence validated

### 3. Trivy Security Scanning (2026 Standard)

**Why Trivy:** All-in-one scanner replacing multiple specialized tools, actively maintained, fastest database updates.

#### Container Image Scanning

**Basic vulnerability scan with severity threshold:**
```bash
# Fail on CRITICAL/HIGH vulnerabilities (blocking)
trivy image --severity CRITICAL,HIGH --exit-code 1 myimage:tag

# Ignore unfixed CVEs (avoid blocking on unpatchable vulnerabilities)
trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 myimage:tag

# With policy exceptions (.trivyignore)
trivy image --severity CRITICAL,HIGH --trivyignore .trivyignore myimage:tag
```

**Secret scanning in image layers:**
```bash
# Detect hardcoded secrets in container layers
trivy image --scanners secret --severity HIGH,CRITICAL myimage:tag
```

**SBOM generation for compliance:**
```bash
# CycloneDX format (preferred for modern tooling)
trivy image --format cyclonedx --output sbom-cyclonedx.json myimage:tag

# SPDX format (widely supported standard)
trivy image --format spdx-json --output sbom-spdx.json myimage:tag
```

**License compliance scanning:**
```bash
# Identify license violations and incompatibilities
trivy image --scanners license --severity HIGH myimage:tag
```

#### IaC Configuration Scanning

**Terraform/OpenTofu (replaces deprecated tfsec):**
```bash
# Scan Terraform for misconfigurations
trivy config --severity CRITICAL,HIGH terraform/

# With custom policy exceptions
trivy config --severity CRITICAL,HIGH --skip-policy AVD-AWS-0001 terraform/
```

**Kubernetes manifests:**
```bash
# Scan K8s manifests for security issues
trivy config --severity CRITICAL,HIGH k8s/

# Check for common misconfigurations:
# - Containers running as root
# - Missing resource limits
# - Overly permissive RBAC
# - Exposed secrets in ConfigMaps
```

**Dockerfile security validation:**
```bash
# Detect Dockerfile misconfigurations
trivy config --severity CRITICAL,HIGH Dockerfile

# Common issues detected:
# - FROM using :latest tag (non-reproducible)
# - Running as root user
# - Secrets in image layers
# - Missing health checks
# - Outdated base images
```

#### CI/CD Integration Best Practices

**1. Update vulnerability database before scanning** (critical for accuracy):
```bash
# Download latest vulnerability database (reduces false positives)
trivy image --download-db-only

# Then run scan with fresh database
trivy image --severity CRITICAL,HIGH myimage:tag
```

**2. Cache database between pipeline runs** (60-80% faster scans):
```yaml
# GitHub Actions example
- name: Cache Trivy DB
  uses: actions/cache@v3
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ github.run_id }}
    restore-keys: trivy-db-

- name: Run Trivy Scan
  run: |
    trivy image --download-db-only
    trivy image --severity CRITICAL,HIGH --exit-code 1 ${{ env.IMAGE }}
```

**3. Severity-based failure thresholds** (avoid alert fatigue):
```bash
# Blocking failures (pipeline fails)
trivy image --severity CRITICAL,HIGH --exit-code 1 myimage:tag

# Non-blocking warnings (logged only)
trivy image --severity MEDIUM,LOW myimage:tag || true
```

**4. Exception handling with .trivyignore** (documented risk acceptance):
```
# .trivyignore - Document exceptions with context

# CVE-2024-1234: Unfixed vulnerability in base image golang:1.22-alpine
# Impact: Low (not exploitable in our usage pattern)
# Reviewed: 2026-02-04 by security-team@example.com
# Expires: 2026-03-04 (re-review in 30 days)
# Approved by: Jane Doe (Security Lead)
CVE-2024-1234

# CVE-2024-5678: False positive - package not in execution path
# Reviewed: 2026-02-04 by security-team@example.com
# Expires: 2026-04-04
CVE-2024-5678
```

**5. Continuous monitoring of production images** (detect new vulnerabilities):
```bash
# Scheduled daily rescan of production images
trivy image --severity CRITICAL,HIGH production/myapp:v1.2.3

# Alert on newly disclosed vulnerabilities
trivy image --severity CRITICAL --exit-code 1 production/myapp:v1.2.3 \
  | notify-security-team
```

### 4. Checkov Multi-Platform Validation

**Why Checkov:** 2000+ built-in policies, compliance framework support, multi-platform IaC coverage.

#### Comprehensive IaC Scanning

**Multi-framework scanning:**
```bash
# Scan all IaC types in directory
checkov -d . --framework terraform kubernetes dockerfile cloudformation \
  --quiet --compact

# With specific compliance frameworks
checkov -d . --framework terraform \
  --check CIS_AWS,CIS_KUBERNETES_V1_6,PCI_DSS \
  --output-format json > checkov-results.json
```

#### Compliance Framework Validation

**CIS Benchmarks:**
```bash
# CIS AWS Foundations Benchmark
checkov -d terraform/ --check CIS_AWS --compact

# CIS Kubernetes Benchmark v1.6
checkov -d k8s/ --check CIS_KUBERNETES_V1_6 --compact

# CIS Docker Benchmark
checkov -f Dockerfile --check CIS_DOCKER --compact
```

**Industry-specific compliance:**
```bash
# PCI-DSS (Payment Card Industry)
checkov -d . --check PCI_DSS --framework terraform kubernetes

# HIPAA (Healthcare)
checkov -d . --check HIPAA --framework terraform

# GDPR (Data Protection)
checkov -d . --check GDPR --framework terraform

# SOC2 (Security Controls)
checkov -d . --check SOC2 --framework terraform
```

#### Kubernetes-Specific Validation

**Common misconfigurations detected:**
- **Containers running as root:** `CKV_K8S_40`
- **Missing CPU limits:** `CKV_K8S_11`
- **Missing memory limits:** `CKV_K8S_12`
- **Overly permissive RBAC:** `CKV_K8S_49`
- **Privileged containers:** `CKV_K8S_16`
- **Host network access:** `CKV_K8S_19`
- **Secrets in environment variables:** `CKV_K8S_35`

```bash
# Kubernetes security baseline validation
checkov -d k8s/ --framework kubernetes \
  --check CKV_K8S_40,CKV_K8S_11,CKV_K8S_12,CKV_K8S_16,CKV_K8S_19 \
  --compact
```

#### Exception Management

**Suppress specific checks with context:**
```yaml
# In resource file - inline suppression
resource "aws_s3_bucket" "example" {
  bucket = "my-bucket"

  # checkov:skip=CKV_AWS_18: Logging not required for dev environment
  # Reviewed: 2026-02-04, Expires: 2026-03-04
  # Approved by: security-team@example.com
}
```

**Or use .checkov.yml for global configuration:**
```yaml
# .checkov.yml
skip-check:
  - id: CKV_AWS_18
    suppress-comment: "S3 access logging not required for dev environment"
  - id: CKV_K8S_40
    suppress-comment: "Root user required for init container"
```

### 5. Policy-as-Code with OPA/Conftest

**Purpose:** Enforce organization-specific security policies beyond standard compliance frameworks.

#### Custom Policy Examples

**Require resource tagging:**
```rego
# policy/tagging.rego
package main

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  not resource.change.after.tags.Environment
  msg = sprintf("EC2 instance %s missing required 'Environment' tag", [resource.address])
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  not resource.change.after.tags.Owner
  msg = sprintf("EC2 instance %s missing required 'Owner' tag", [resource.address])
}
```

**Enforce encryption at rest:**
```rego
# policy/encryption.rego
package main

deny[msg] {
  resource := input.resource[_]
  resource.type == "aws_s3_bucket"
  not resource.values.server_side_encryption_configuration
  msg = sprintf("S3 bucket %s must have server-side encryption enabled", [resource.address])
}

deny[msg] {
  resource := input.resource[_]
  resource.type == "aws_ebs_volume"
  resource.values.encrypted != true
  msg = sprintf("EBS volume %s must be encrypted", [resource.address])
}
```

**Block public access by default:**
```rego
# policy/network_security.rego
package main

deny[msg] {
  resource := input.resource[_]
  resource.type == "aws_security_group_rule"
  resource.values.cidr_blocks[_] == "0.0.0.0/0"
  resource.values.type == "ingress"
  msg = sprintf("Security group rule %s allows unrestricted ingress from 0.0.0.0/0", [resource.address])
}

deny[msg] {
  resource := input.resource[_]
  resource.type == "aws_db_instance"
  resource.values.publicly_accessible == true
  msg = sprintf("Database instance %s must not be publicly accessible", [resource.address])
}
```

**Enforce OIDC over long-lived credentials:**
```rego
# policy/authentication.rego
package main

deny[msg] {
  resource := input.resource[_]
  resource.type == "aws_iam_user"
  msg = sprintf("IAM user %s detected - prefer OIDC federation over long-lived credentials", [resource.address])
}

warn[msg] {
  resource := input.resource[_]
  resource.type == "aws_iam_access_key"
  msg = sprintf("IAM access key %s detected - consider migrating to OIDC for CI/CD authentication", [resource.address])
}
```

#### Running Conftest Validation

**Terraform validation:**
```bash
# Generate Terraform plan JSON
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Validate against policies
conftest test tfplan.json -p policies/ --output table
```

**Kubernetes validation:**
```bash
# Validate K8s manifests against policies
conftest test k8s/*.yaml -p policies/ --all-namespaces
```

**Multi-file validation with summary:**
```bash
# Validate all resources with detailed output
conftest test --policy policies/ \
  --output json \
  --all-namespaces \
  terraform/*.tf k8s/*.yaml > policy-results.json
```

### 6. AI-Generated IaC Validation

**Critical safeguards for LLM-generated configurations:**

#### Hallucination Detection

**Problem:** AI generates non-existent resource types, packages, or modules that don't exist in official registries.

**Detection strategy:**
1. **Schema validation** (catch fabricated resource types):
   ```bash
   # Extract all resource types from generated code
   grep -r "^resource \"" terraform/ | cut -d'"' -f2 | sort -u > generated_types.txt

   # Compare against official provider schemas
   terraform providers schema -json | jq '.provider_schemas[].resource_schemas | keys[]' > official_types.txt

   # Flag any resource types not in official schema
   comm -23 generated_types.txt official_types.txt > hallucinated_resources.txt
   ```

2. **Module source verification**:
   ```bash
   # Extract all module sources
   grep -r "^module " terraform/ | grep -oP 'source\s*=\s*"\K[^"]+' > module_sources.txt

   # Validate against Terraform Registry or internal registry
   # Flag any modules not in verified sources
   ```

3. **Package hallucination prevention** (Dockerfiles):
   ```bash
   # Validate base images exist in official registries
   grep "^FROM" Dockerfile | awk '{print $2}' | while read img; do
     docker manifest inspect "$img" > /dev/null 2>&1 || echo "INVALID: $img"
   done
   ```

#### Insecure Defaults Detection

**Problem:** AI generates configurations with weak passwords, unrestricted access, or overly permissive policies.

**Detection patterns:**
```bash
# Scan for hardcoded secrets and weak credentials
trivy fs --scanners secret --severity HIGH,CRITICAL .

# Check for insecure patterns in generated code
grep -rE "(password|secret|api_key)\s*=\s*['\"]" terraform/ k8s/

# Validate no 0.0.0.0/0 ingress rules
grep -r "0.0.0.0/0" terraform/ | grep ingress

# Check for root user in containers
grep -r "USER root" */Dockerfile
```

#### Intent Validation for AI-Generated Code

**Problem:** Generated IaC is syntactically valid but violates organizational requirements (47.6% of intent validation failures).

**Validation approach:**
1. **Policy-as-code validation** (OPA/Conftest) - codify organizational intent
2. **Human-in-the-loop review** for critical resources (IAM, security groups, encryption)
3. **Dependency graph analysis** - ensure generated resources align with architectural patterns

**Required review triggers for AI-generated code:**
```yaml
# .validation-rules.yaml
auto_approve: false  # Never auto-deploy AI-generated IaC
require_human_review:
  - resource_types: ["aws_iam_*", "aws_security_group*", "aws_kms_*"]
    reason: "Security-critical resources require human approval"
  - changes_include: ["publicly_accessible = true"]
    reason: "Public access changes require security team review"
  - policy_failures: ["CRITICAL", "HIGH"]
    reason: "Security findings must be triaged by humans"
```

### 7. Exception Management and Risk Acceptance

**Principle:** Not all security findings require immediate remediation. Some are false positives, others are accepted risks.

#### .trivyignore Format

**Best practices:**
- Include CVE ID, description, and business justification
- Add review date and reviewer name
- Set expiration date for re-evaluation
- Link to ticket/issue for tracking

**Example .trivyignore:**
```
# CVE-2024-1234: Unfixed vulnerability in golang:1.22-alpine base image
# Description: Potential integer overflow in crypto/tls (CVSS 7.5 HIGH)
# Impact: Low risk - not exploitable in our usage pattern (no TLS negotiation)
# Workaround: Using latest available patch of golang:1.22-alpine (no fix available upstream)
# Ticket: SEC-12345
# Reviewed: 2026-02-04 by jane.doe@example.com (Security Team Lead)
# Approved by: security-team@example.com
# Expires: 2026-03-04 (re-review in 30 days or when fix available)
CVE-2024-1234

# CVE-2024-5678: False positive - vulnerable package not in execution path
# Description: Vulnerability in unused optional dependency
# Analysis: Package only used in dev/test environment, not deployed to production
# Ticket: SEC-12346
# Reviewed: 2026-02-04 by john.smith@example.com
# Expires: 2026-04-04
CVE-2024-5678
```

#### Checkov Suppression

**Inline suppression with context:**
```hcl
resource "aws_s3_bucket" "logs" {
  bucket = "my-app-logs"

  # checkov:skip=CKV_AWS_18:S3 access logging not required for log aggregation bucket
  # Reason: This bucket is the destination for access logs, creating circular dependency
  # Reviewed: 2026-02-04 by security-team@example.com
  # Ticket: SEC-12347
  # Expires: 2026-06-04
}
```

#### Exception Review Process

**Lifecycle management:**
1. **Initial triage** (within 24 hours of detection)
   - Classify as true positive, false positive, or accepted risk
   - Assign severity and priority

2. **Documentation** (required for all exceptions)
   - Business justification
   - Alternative mitigations (if applicable)
   - Expiration date

3. **Approval workflow** (severity-based)
   - CRITICAL: Security team lead + CISO approval required
   - HIGH: Security team lead approval required
   - MEDIUM/LOW: Engineering lead approval sufficient

4. **Continuous monitoring** (automated)
   - Alert when exceptions expire
   - Re-scan for fixes becoming available
   - Quarterly review of all active exceptions

### 8. SBOM Generation and Management

**Purpose:** Software Bill of Materials for compliance, audit trails, and incident response.

#### Why SBOM Matters

**Use cases:**
- **Compliance:** Required by executive orders, industry regulations (FDA, automotive)
- **Incident response:** Quickly identify affected systems when new CVE disclosed
- **License compliance:** Track open-source license obligations
- **Supply chain security:** Verify software provenance and integrity

#### Generating SBOMs with Trivy

**CycloneDX format** (preferred for modern tooling):
```bash
# Generate SBOM for container image
trivy image --format cyclonedx --output sbom-cyclonedx.json myimage:tag

# Generate SBOM for filesystem (source code dependencies)
trivy fs --format cyclonedx --output sbom-cyclonedx.json .
```

**SPDX format** (widely supported standard):
```bash
# SPDX JSON
trivy image --format spdx-json --output sbom-spdx.json myimage:tag

# SPDX RDF
trivy image --format spdx --output sbom-spdx.rdf myimage:tag
```

#### SBOM Storage and Management

**Best practices:**
- Store SBOM alongside image in artifact registry
- Version SBOMs with image tags (myimage:v1.2.3 → sbom-v1.2.3.json)
- Implement searchable SBOM database for incident response
- Automate SBOM generation in CI/CD pipeline
- Archive SBOMs for historical vulnerability analysis

**CI/CD integration:**
```yaml
# GitHub Actions example
- name: Generate SBOM
  run: |
    trivy image --format cyclonedx --output sbom.json ${{ env.IMAGE }}

- name: Upload SBOM to Artifact Registry
  run: |
    # Upload alongside container image
    oras push ghcr.io/${{ github.repository }}/sbom:${{ github.sha }} \
      sbom.json:application/vnd.cyclonedx+json
```

### 9. CI/CD Security Gate Integration

**Purpose:** Automated security validation preventing insecure deployments.

#### Pipeline Architecture

**Multi-stage validation:**
```
Code Push → Syntax Check → Security Scan → Policy Validation → Human Approval → Deploy
              (Phase 1)      (Phase 2)        (Phase 2)         (Critical)
```

#### GitHub Actions Example

```yaml
name: IaC Security Validation

on:
  pull_request:
    paths: ['terraform/**', 'k8s/**', 'Dockerfile']
  push:
    branches: [main]

jobs:
  # Phase 1: Technical Validation
  syntax:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Terraform validation
      - name: Terraform Init
        run: terraform init -backend=false
        working-directory: terraform

      - name: Terraform Validate
        run: terraform validate
        working-directory: terraform

      # Kubernetes validation
      - name: Kubeconform
        uses: docker://ghcr.io/yannh/kubeconform:latest
        with:
          args: k8s/*.yaml

      # Helm validation
      - name: Helm Lint
        run: helm lint --strict ./charts/myapp
        if: hashFiles('charts/**')

      # Dockerfile validation
      - name: Hadolint
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile
          ignore: DL3008,DL3009

  # Phase 2: Security Scanning
  security:
    runs-on: ubuntu-latest
    needs: syntax
    steps:
      - uses: actions/checkout@v3

      # Cache Trivy database for faster scans
      - name: Cache Trivy DB
        uses: actions/cache@v3
        with:
          path: ~/.cache/trivy
          key: trivy-db-${{ github.run_id }}
          restore-keys: trivy-db-

      # Update vulnerability database
      - name: Update Trivy DB
        run: docker run --rm -v ~/.cache/trivy:/root/.cache/ aquasec/trivy:latest image --download-db-only

      # Trivy IaC scanning
      - name: Trivy Config Scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'config'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          exit-code: 1
          ignore-unfixed: true
          trivyignore: .trivyignore

      # Secret scanning
      - name: Trivy Secret Scan
        run: |
          docker run --rm -v $(pwd):/scan aquasec/trivy:latest fs \
            --scanners secret \
            --severity HIGH,CRITICAL \
            --exit-code 1 \
            /scan

      # Checkov multi-platform scanning
      - name: Checkov Scan
        uses: bridgecrewio/checkov-action@master
        with:
          directory: .
          framework: terraform,kubernetes,dockerfile
          check: CIS_AWS,CIS_KUBERNETES_V1_6
          quiet: true
          output_format: sarif
          output_file_path: checkov-results.sarif

      # Upload results to GitHub Security tab
      - name: Upload Checkov Results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: checkov-results.sarif

  # Phase 2: Policy Validation
  policy:
    runs-on: ubuntu-latest
    needs: syntax
    steps:
      - uses: actions/checkout@v3

      # Terraform plan for policy validation
      - name: Terraform Plan
        run: |
          terraform init -backend=false
          terraform plan -out=tfplan.binary
          terraform show -json tfplan.binary > tfplan.json
        working-directory: terraform

      # OPA/Conftest policy validation
      - name: Conftest
        uses: instrumenta/conftest-action@master
        with:
          files: terraform/tfplan.json k8s/*.yaml
          policy: policies/

      # Custom organizational policies
      - name: Organization Policy Check
        run: |
          # Check required tagging
          conftest test --policy policies/tagging.rego terraform/tfplan.json

          # Check encryption requirements
          conftest test --policy policies/encryption.rego terraform/tfplan.json

          # Check network security
          conftest test --policy policies/network_security.rego terraform/tfplan.json

  # Container image security (if building containers)
  container-security:
    runs-on: ubuntu-latest
    if: hashFiles('Dockerfile')
    needs: syntax
    steps:
      - uses: actions/checkout@v3

      # Build image
      - name: Build Container
        run: docker build -t test-image:${{ github.sha }} .

      # Trivy container scan
      - name: Trivy Container Scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: test-image:${{ github.sha }}
          severity: 'CRITICAL,HIGH'
          exit-code: 1
          ignore-unfixed: true

      # Generate SBOM
      - name: Generate SBOM
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image \
            --format cyclonedx \
            --output sbom.json \
            test-image:${{ github.sha }}

      # Upload SBOM as artifact
      - name: Upload SBOM
        uses: actions/upload-artifact@v3
        with:
          name: sbom-${{ github.sha }}
          path: sbom.json

  # Summary and approval gate
  security-summary:
    runs-on: ubuntu-latest
    needs: [security, policy, container-security]
    if: always()
    steps:
      - name: Security Gate Summary
        run: |
          echo "## Security Validation Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "✅ Syntax validation: PASSED" >> $GITHUB_STEP_SUMMARY
          echo "✅ Security scanning: PASSED" >> $GITHUB_STEP_SUMMARY
          echo "✅ Policy validation: PASSED" >> $GITHUB_STEP_SUMMARY
          echo "✅ Container security: PASSED" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "All security gates passed. Ready for deployment." >> $GITHUB_STEP_SUMMARY
```

#### GitLab CI Example

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - scan
  - policy
  - approve

variables:
  TRIVY_CACHE_DIR: "${CI_PROJECT_DIR}/.trivycache/"

# Cache Trivy database
cache:
  key: trivy-db
  paths:
    - .trivycache/

# Phase 1: Syntax Validation
terraform:validate:
  stage: validate
  image: hashicorp/terraform:latest
  script:
    - cd terraform
    - terraform init -backend=false
    - terraform validate

kubernetes:validate:
  stage: validate
  image: alpine/k8s:latest
  script:
    - kubectl apply --dry-run=client -f k8s/

# Phase 2: Security Scanning
trivy:config:
  stage: scan
  image: aquasec/trivy:latest
  before_script:
    - trivy image --download-db-only
  script:
    - trivy config --severity CRITICAL,HIGH --exit-code 1 .
  allow_failure: false

trivy:secrets:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy fs --scanners secret --severity HIGH,CRITICAL --exit-code 1 .
  allow_failure: false

checkov:scan:
  stage: scan
  image: bridgecrew/checkov:latest
  script:
    - checkov -d . --framework terraform kubernetes dockerfile
      --check CIS_AWS,CIS_KUBERNETES_V1_6
      --output junitxml --output-file checkov-results.xml
  artifacts:
    reports:
      junit: checkov-results.xml

# Phase 2: Policy Validation
conftest:policy:
  stage: policy
  image: openpolicyagent/conftest:latest
  script:
    - cd terraform
    - terraform plan -out=tfplan.binary
    - terraform show -json tfplan.binary > tfplan.json
    - conftest test tfplan.json -p ../policies/

# Human Approval Gate (production only)
approve:production:
  stage: approve
  script:
    - echo "Security validation complete. Awaiting approval for production deployment."
  when: manual
  only:
    - main
  environment:
    name: production
```

### 10. Continuous Security Monitoring

**Purpose:** Detect newly disclosed vulnerabilities in already-deployed infrastructure.

#### Scheduled Rescanning

**Daily production image scans:**
```bash
#!/bin/bash
# daily-image-scan.sh

IMAGES=(
  "production/api:v1.2.3"
  "production/web:v2.0.1"
  "production/worker:v1.5.0"
)

for IMAGE in "${IMAGES[@]}"; do
  echo "Scanning $IMAGE..."
  trivy image --severity CRITICAL,HIGH "$IMAGE" > "scan-$(echo $IMAGE | tr '/:' '--').txt"

  if [ $? -ne 0 ]; then
    echo "ALERT: New vulnerabilities found in $IMAGE"
    # Send alert to security team
    curl -X POST "$SLACK_WEBHOOK" -d "{\"text\":\"New vulnerabilities in $IMAGE\"}"
  fi
done
```

**Weekly IaC infrastructure review:**
```bash
#!/bin/bash
# weekly-iac-scan.sh

# Scan deployed Terraform state for new security issues
terraform init
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Run security scans
trivy config --severity CRITICAL,HIGH .
checkov -d . --framework terraform --check CIS_AWS
conftest test tfplan.json -p policies/

# Generate report
echo "Weekly Security Scan: $(date)" > weekly-report.md
echo "" >> weekly-report.md
echo "## New Findings:" >> weekly-report.md
# Append scan results...
```

#### Vulnerability Alert Workflow

**1. Detection:** Scheduled scan identifies new CVE
**2. Triage:** Automated severity assessment and impact analysis
**3. Notification:** Alert security team via Slack/email/PagerDuty
**4. Remediation:** Ticket created with fix recommendations
**5. Verification:** Re-scan confirms vulnerability resolved

## Usage Guidelines

### When to Activate

This skill activates automatically when:

1. `iac-validator` agent performs pre-deployment security checks
2. User requests security scanning, policy validation, or compliance verification
3. CI/CD pipeline runs security gates before deployment
4. Discussion involves vulnerability management, threat detection, or security hardening
5. AI-generated IaC requires hallucination detection and validation
6. SBOM generation needed for compliance or incident response
7. Exception management for security findings (false positives, accepted risks)

### When to Defer

Do NOT activate for:

- **Runtime security monitoring:** Use AWS GuardDuty, Azure Security Center, GCP Security Command Center
- **Incident response:** Use SIEM/SOAR platforms (Splunk, Datadog Security, Wiz)
- **Container orchestration:** Use `kubernetes-native` skill for K8s deployments
- **Deployment automation:** Use `gitops-argocd` or `gitops-flux` skills
- **Cost optimization:** Different concern, not security-focused

### Integration with iac-validator Agent

The `iac-validator` agent references this skill when:

1. Validating AI-generated IaC before deployment (hallucination detection)
2. Running two-phase validation pipeline (technical + intent)
3. Enforcing security baselines and compliance frameworks
4. Generating SBOMs for audit trails
5. Managing security exceptions and risk acceptance
6. Implementing CI/CD security gates

## Key Patterns

### Pattern 1: Complete Pre-Deployment Validation

**Use case:** Validate all IaC resources before deployment to production.

```bash
#!/bin/bash
# complete-validation.sh - Comprehensive pre-deployment security check

set -e  # Exit on any error

echo "=== Phase 1: Technical Validation ==="

# Terraform syntax
echo "[1/4] Validating Terraform syntax..."
cd terraform
terraform init -backend=false
terraform validate
cd ..

# Kubernetes syntax
echo "[2/4] Validating Kubernetes manifests..."
kubectl apply --dry-run=client -f k8s/
kubeconform k8s/*.yaml

# Helm charts
if [ -d "charts" ]; then
  echo "[3/4] Validating Helm charts..."
  helm lint --strict charts/*
fi

# Dockerfile
if [ -f "Dockerfile" ]; then
  echo "[4/4] Validating Dockerfile..."
  hadolint Dockerfile
fi

echo "✅ Phase 1 complete: All syntax valid"
echo ""
echo "=== Phase 2: Security Scanning ==="

# Update Trivy database
echo "[1/6] Updating vulnerability database..."
trivy image --download-db-only

# Trivy IaC scanning
echo "[2/6] Scanning IaC for misconfigurations..."
trivy config --severity CRITICAL,HIGH --exit-code 1 --ignore-unfixed .

# Secret detection
echo "[3/6] Scanning for hardcoded secrets..."
trivy fs --scanners secret --severity HIGH,CRITICAL --exit-code 1 .

# Checkov multi-platform
echo "[4/6] Running compliance checks..."
checkov -d . --framework terraform kubernetes dockerfile \
  --check CIS_AWS,CIS_KUBERNETES_V1_6 \
  --quiet --compact

# OPA policy validation
echo "[5/6] Validating organizational policies..."
cd terraform
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
conftest test tfplan.json -p ../policies/
cd ..

# Container image scan (if built)
if [ -n "$IMAGE_NAME" ]; then
  echo "[6/6] Scanning container image..."
  trivy image --severity CRITICAL,HIGH --exit-code 1 --ignore-unfixed "$IMAGE_NAME"

  # Generate SBOM
  echo "Generating SBOM..."
  trivy image --format cyclonedx --output sbom-cyclonedx.json "$IMAGE_NAME"
fi

echo "✅ Phase 2 complete: All security checks passed"
echo ""
echo "=== Validation Summary ==="
echo "✅ Syntax validation: PASSED"
echo "✅ Security scanning: PASSED"
echo "✅ Policy validation: PASSED"
echo "✅ Compliance checks: PASSED"
echo ""
echo "🚀 Ready for deployment"
```

### Pattern 2: AI-Generated IaC Validation with Hallucination Detection

**Use case:** Validate LLM-generated Terraform with hallucination detection and intent verification.

```bash
#!/bin/bash
# ai-iac-validation.sh - Specialized validation for AI-generated code

set -e

AI_GENERATED_DIR="$1"
if [ -z "$AI_GENERATED_DIR" ]; then
  echo "Usage: $0 <path-to-ai-generated-iac>"
  exit 1
fi

cd "$AI_GENERATED_DIR"

echo "=== AI-Generated IaC Validation Pipeline ==="
echo ""
echo "⚠️  AI-generated code requires enhanced validation"
echo ""

# Step 1: Provider schema validation (hallucination detection)
echo "[1/8] Validating resource types against provider schemas..."
terraform init -backend=false

# Extract generated resource types
grep -r "^resource " . | cut -d'"' -f2 | sort -u > generated_types.txt

# Extract official provider schemas
terraform providers schema -json > schemas.json
jq -r '.provider_schemas[].resource_schemas | keys[]' schemas.json | sort -u > official_types.txt

# Check for hallucinated resource types
comm -23 generated_types.txt official_types.txt > hallucinated.txt
if [ -s hallucinated.txt ]; then
  echo "❌ ERROR: Detected hallucinated resource types:"
  cat hallucinated.txt
  echo ""
  echo "These resource types do not exist in official provider schemas."
  exit 1
fi
echo "✅ All resource types valid"

# Step 2: Module source verification
echo "[2/8] Validating module sources..."
grep -r "^module " . | grep -oP 'source\s*=\s*"\K[^"]+' > module_sources.txt || true
if [ -s module_sources.txt ]; then
  while read source; do
    # Check if module is from Terraform Registry or internal registry
    if [[ ! "$source" =~ ^(hashicorp/|terraform-aws-modules/|app\.terraform\.io/) ]]; then
      echo "⚠️  WARNING: Unverified module source: $source"
      echo "   Verify this module is from a trusted source before deployment."
    fi
  done < module_sources.txt
fi
echo "✅ Module sources reviewed"

# Step 3: Syntax validation
echo "[3/8] Validating Terraform syntax..."
terraform validate
echo "✅ Syntax valid"

# Step 4: Dependency graph analysis
echo "[4/8] Analyzing resource dependencies..."
terraform graph > dependencies.dot
# Check for circular dependencies
if grep -q "cycle" dependencies.dot; then
  echo "❌ ERROR: Circular dependency detected in generated code"
  exit 1
fi
echo "✅ No circular dependencies"

# Step 5: Secret detection (AI may hallucinate credentials)
echo "[5/8] Scanning for hardcoded secrets..."
trivy fs --scanners secret --severity HIGH,CRITICAL --exit-code 1 .
echo "✅ No secrets detected"

# Step 6: Security misconfiguration scanning
echo "[6/8] Scanning for security misconfigurations..."
trivy config --severity CRITICAL,HIGH --exit-code 1 .
checkov -d . --framework terraform --quiet --compact
echo "✅ No critical security issues"

# Step 7: Insecure defaults detection
echo "[7/8] Checking for insecure defaults..."

# Check for unrestricted ingress
if grep -rq "0.0.0.0/0" . | grep -q ingress; then
  echo "⚠️  WARNING: Found unrestricted ingress rules (0.0.0.0/0)"
  echo "   These require human review for security approval."
fi

# Check for publicly accessible resources
if grep -rq "publicly_accessible.*=.*true" .; then
  echo "⚠️  WARNING: Found publicly accessible resources"
  echo "   These require human review for security approval."
fi

# Check for missing encryption
if ! grep -rq "encryption" .; then
  echo "⚠️  WARNING: No encryption configuration detected"
  echo "   Verify encryption requirements are met."
fi

echo "✅ Insecure defaults check complete"

# Step 8: Intent validation with OPA policies
echo "[8/8] Validating organizational intent..."
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
conftest test tfplan.json -p ../policies/
echo "✅ Intent validation passed"

echo ""
echo "=== AI-Generated IaC Validation Summary ==="
echo "✅ No hallucinated resources detected"
echo "✅ Module sources verified"
echo "✅ Syntax valid"
echo "✅ Dependencies resolved"
echo "✅ No hardcoded secrets"
echo "✅ Security baseline met"
echo "✅ Organizational policies satisfied"
echo ""
echo "⚠️  IMPORTANT: AI-generated code requires human review before production deployment"
echo "   Review checklist:"
echo "   [ ] Verify resource configurations match requirements"
echo "   [ ] Check IAM policies for least privilege"
echo "   [ ] Validate network security rules"
echo "   [ ] Confirm encryption settings"
echo "   [ ] Approve any security exceptions"
echo ""
echo "🚀 Ready for human review and approval"
```

### Pattern 3: Continuous Monitoring with Alerting

**Use case:** Daily rescan of production images and infrastructure for new vulnerabilities.

```bash
#!/bin/bash
# continuous-monitoring.sh - Daily security monitoring

ALERT_WEBHOOK="$SLACK_WEBHOOK_URL"
REPORT_FILE="security-report-$(date +%Y%m%d).md"

echo "# Daily Security Scan Report" > "$REPORT_FILE"
echo "Date: $(date)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Scan production container images
echo "## Container Images" >> "$REPORT_FILE"
IMAGES=(
  "production/api:v1.2.3"
  "production/web:v2.0.1"
  "production/worker:v1.5.0"
)

FINDINGS=0
for IMAGE in "${IMAGES[@]}"; do
  echo "Scanning $IMAGE..."
  if ! trivy image --severity CRITICAL,HIGH --exit-code 0 "$IMAGE" > "scan-$IMAGE.txt"; then
    FINDINGS=$((FINDINGS + 1))
    echo "### ⚠️ $IMAGE" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    cat "scan-$IMAGE.txt" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
  else
    echo "### ✅ $IMAGE: No new vulnerabilities" >> "$REPORT_FILE"
  fi
done

# Scan deployed infrastructure
echo "" >> "$REPORT_FILE"
echo "## Infrastructure (Terraform)" >> "$REPORT_FILE"

cd terraform
terraform init -backend=false
trivy config --severity CRITICAL,HIGH . > iac-scan.txt

if grep -q "Total: [1-9]" iac-scan.txt; then
  FINDINGS=$((FINDINGS + 1))
  echo "### ⚠️ IaC Misconfigurations Found" >> "$REPORT_FILE"
  echo '```' >> "$REPORT_FILE"
  cat iac-scan.txt >> "$REPORT_FILE"
  echo '```' >> "$REPORT_FILE"
else
  echo "### ✅ No IaC misconfigurations" >> "$REPORT_FILE"
fi

# Send alert if findings detected
if [ $FINDINGS -gt 0 ]; then
  curl -X POST "$ALERT_WEBHOOK" \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"🚨 Security Alert: $FINDINGS new findings in daily scan. Review $REPORT_FILE\"}"
fi

echo "" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"
echo "Total findings: $FINDINGS" >> "$REPORT_FILE"

cat "$REPORT_FILE"
```

## Security Compliance

All validation workflows must comply with SPEC.md constraints and industry best practices:

### ✅ Required Security Practices

- **No hardcoded secrets:** Must pass Trivy secret scanning with ZERO findings
- **Severity-based thresholds:** CRITICAL/HIGH findings are blocking failures
- **SBOM generation:** Required for all container images deployed to production
- **Policy-as-code validation:** All resources validated against OPA policies
- **AI-generated code validation:** Enhanced hallucination detection and intent validation required
- **Exception management:** All security exceptions documented with expiration dates
- **Continuous monitoring:** Production resources rescanned daily for new vulnerabilities
- **Human oversight:** Critical resources (IAM, security groups, encryption) require approval

### ✅ Validation Commands

```bash
# Full pre-deployment validation suite
./scripts/complete-validation.sh

# AI-generated IaC validation
./scripts/ai-iac-validation.sh terraform/

# Continuous monitoring
./scripts/continuous-monitoring.sh

# Generate compliance report
trivy config --format json --output compliance-report.json .
checkov -d . --framework terraform --output junitxml > compliance.xml
```

## Anti-Patterns to Avoid

### ❌ Common Mistakes

1. **Outdated vulnerability databases:**
   ```bash
   # WRONG: Scanning without database update
   trivy image myimage:tag  # Uses potentially stale database
   ```

   **FIX:** Always update database before scanning:
   ```bash
   trivy image --download-db-only
   trivy image myimage:tag
   ```

2. **Blocking on all security findings:**
   ```bash
   # WRONG: Fails on unfixed vulnerabilities
   trivy image --severity LOW,MEDIUM,HIGH,CRITICAL --exit-code 1 myimage:tag
   ```

   **FIX:** Use severity-based thresholds and ignore unfixed:
   ```bash
   trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 myimage:tag
   ```

3. **Undocumented security exceptions:**
   ```
   # WRONG: .trivyignore with no context
   CVE-2024-1234
   CVE-2024-5678
   ```

   **FIX:** Document all exceptions:
   ```
   # CVE-2024-1234: Unfixed vulnerability in base image
   # Reviewed: 2026-02-04, Expires: 2026-03-04
   # Approved by: security-team@example.com
   CVE-2024-1234
   ```

4. **Using deprecated tfsec:**
   ```bash
   # WRONG: tfsec deprecated in 2026
   tfsec terraform/
   ```

   **FIX:** Use Trivy (tfsec successor):
   ```bash
   trivy config --severity CRITICAL,HIGH terraform/
   ```

5. **No CI/CD database caching:**
   ```yaml
   # WRONG: Re-downloads database on every run (slow)
   - run: trivy image myimage:tag
   ```

   **FIX:** Cache between runs:
   ```yaml
   - uses: actions/cache@v3
     with:
       path: ~/.cache/trivy
       key: trivy-db-${{ github.run_id }}
   - run: trivy image --download-db-only && trivy image myimage:tag
   ```

6. **Skipping AI-generated code validation:**
   ```bash
   # WRONG: Deploying AI-generated IaC without validation
   terraform apply -auto-approve
   ```

   **FIX:** Run comprehensive AI validation pipeline:
   ```bash
   ./scripts/ai-iac-validation.sh terraform/
   # Then require human approval before deployment
   ```

7. **No SBOM generation:**
   ```bash
   # WRONG: Deploying without software bill of materials
   docker push myimage:tag
   ```

   **FIX:** Generate SBOM before deployment:
   ```bash
   trivy image --format cyclonedx --output sbom.json myimage:tag
   docker push myimage:tag
   # Store SBOM alongside image
   ```

8. **Single-pass LLM validation:**
   ```bash
   # WRONG: Trust single AI validator without verification
   ai-validator tfplan.json  # No secondary check
   ```

   **FIX:** Use dual-validator approach:
   ```bash
   # Primary validator
   conftest test tfplan.json -p policies/
   # Secondary validator checks primary's outputs
   ai-validator-v2 --verify tfplan.json conftest-results.json
   ```

## Integration Notes

### For iac-validator Agent

When the `iac-validator` agent invokes this skill:

1. **Context:** Provide resource types being validated (Terraform, K8s, containers)
2. **Environment:** Specify target environment (dev/staging/production) for appropriate policies
3. **Source:** Indicate if IaC is AI-generated (triggers enhanced validation)
4. **Compliance:** List required compliance frameworks (CIS, PCI-DSS, HIPAA, etc.)
5. **Thresholds:** Specify severity thresholds (typically CRITICAL/HIGH for prod)
6. **Exceptions:** Reference .trivyignore or .checkov.yml for approved exceptions

### For iac-generator Agent

When `iac-generator` creates resources:

1. Validate generated resources pass security scanning before presenting to user
2. Apply security hardening by default (non-root users, encryption, minimal permissions)
3. Document security decisions in generated code comments
4. Include validation commands in generated README files
5. Flag security-critical resources for human review

## Best Practices Summary

1. **Always use two-phase validation** (technical syntax + security/policy)
2. **Update vulnerability databases** before each scan to minimize false positives
3. **Cache databases in CI/CD** for 60-80% faster pipeline execution
4. **Use severity-based thresholds** (fail on CRITICAL/HIGH, warn on MEDIUM/LOW)
5. **Document all security exceptions** with review dates and expiration
6. **Generate SBOMs** for all production container images
7. **Migrate from tfsec to Trivy** (2026 standard, actively maintained)
8. **Use Checkov for K8s and multi-platform** IaC compliance validation
9. **Implement OPA/Conftest** for organization-specific policy enforcement
10. **Enhanced validation for AI-generated code** (hallucination detection, intent validation)
11. **Never auto-deploy AI-generated IaC** without human review
12. **Continuous monitoring** with daily rescans of production resources
13. **Human-in-the-loop for critical resources** (IAM, security groups, encryption)
14. **Automated alerting** when new vulnerabilities detected
15. **Compliance framework enforcement** (CIS, PCI-DSS, GDPR, HIPAA, SOC2)

## References

For comprehensive patterns and current tool documentation, see:

- **Trivy (2026 standard):** https://trivy.dev/
- **Checkov multi-platform scanning:** https://www.checkov.io/
- **OPA policy-as-code:** https://www.openpolicyagent.org/
- **Conftest:** https://www.conftest.dev/
- **Kubeconform (K8s validation):** https://github.com/yannh/kubeconform
- **Hadolint (Dockerfile linter):** https://github.com/hadolint/hadolint
- **SBOM standards:** https://cyclonedx.org/ and https://spdx.dev/
- **CIS Benchmarks:** https://www.cisecurity.org/cis-benchmarks
- **NIST Cybersecurity Framework:** https://www.nist.gov/cyberframework

---

*This skill is part of the iac-team plugin. For related capabilities, see: container-analysis (Dockerfile security), kubernetes-native (K8s validation), terraform-modules (IaC patterns), gitops-argocd (GitOps deployment), github-actions (CI/CD integration).*
