---
name: gitlab-ci
description: >
  GitLab CI/CD pipeline patterns for Infrastructure-as-Code deployments. Provides secure
  .gitlab-ci.yml configurations with OIDC authentication, DAG pipeline optimization, GitLab
  Agent for Kubernetes GitOps integration, reusable job templates, multi-environment deployment
  strategies, and security scanning with modern validation tools.

  Activate when user mentions: GitLab CI, .gitlab-ci.yml, GitLab pipelines, DAG pipelines,
  GitLab Agent, GitLab Runner, GitLab GitOps, CI/CD pipelines, stages, jobs, rules, needs,
  artifacts, GitLab deployment, GitLab security scanning, parent-child pipelines, pipeline
  efficiency, Flux integration with GitLab Agent.

  Use for: Generating GitLab CI/CD pipelines for Terraform, Kubernetes, Helm, Docker builds
  with security best practices (OIDC, workload identity, DAG optimization, security scanning,
  validation gates, artifact management, and GitLab Agent for GitOps).

  Do NOT use for: GitHub Actions, Jenkins, CircleCI, or other CI/CD platforms. For those,
  recommend platform-specific tooling.
---

# GitLab CI/CD Skill

This skill provides secure GitLab CI/CD pipeline patterns for infrastructure-as-code deployments, with emphasis on OIDC authentication, DAG pipeline optimization, GitLab Agent for Kubernetes GitOps, security scanning integration (Trivy 2026), and efficient artifact management for multi-environment deployments.

## Core Capabilities

### 1. DAG Pipeline Architecture
- **Needs-Based Dependencies**: Explicit job dependencies using `needs:` keyword for parallel execution
- **Hybrid Pipelines**: Combine stage-based and DAG patterns for optimal workflow
- **Parent-Child Pipelines**: Monorepo support with dynamic child pipeline triggering
- **Rules and Changes**: Conditional job execution based on file path changes (`rules: changes`)
- **Dynamic Pipelines**: Runtime generation of pipeline configuration for complex scenarios
- **YAML Anchors**: Reduce configuration duplication with reusable definitions
- **Artifact Optimization**: Pass artifacts between dependent jobs efficiently

### 2. OIDC and Workload Identity
- **AWS OIDC**: Configure GitLab OIDC provider for AWS with restrictive IAM trust policies
- **Azure Workload Identity**: Federated identity with Azure service principals
- **GCP Workload Identity Federation**: Service account impersonation without long-lived keys
- **GitLab Agent OIDC**: Secure Kubernetes access through agent authentication
- **Trust Policy Hardening**: Project and branch restrictions in cloud IAM policies
- **Short-Lived Tokens**: Eliminate long-lived credentials from CI/CD workflows
- **Service Principal Migration**: Replace personal access tokens with automated authentication

### 3. GitLab Agent for Kubernetes GitOps
- **Flux Integration**: Combined agentk + Flux for declarative cluster management (post-16.2)
- **OCI Image Sources**: Package delivery repositories as OCI images for Flux
- **Immediate Reconciliation**: Flux Receiver integration for git push detection
- **Cluster Observability**: Visualize cluster state through GitLab UI via agent
- **Multi-Cluster Management**: Single agent managing multiple cluster connections
- **Certificate Migration**: Transition from deprecated certificate-based integration (sunsets May 2026)
- **Security Scanning**: Integrated vulnerability scanning for cluster workloads

### 4. Pipeline Structures
- **Terraform Pipelines**: Validate → Plan → Apply with approval gates and state locking
- **Kubernetes Pipelines**: Manifest validation, dry-run, progressive rollout with health checks
- **Helm Pipelines**: Chart linting, template validation, staged releases with rollback
- **Docker Build Optimization**: Layer caching, multi-stage builds, registry integration
- **Multi-Environment**: Dev → staging → production with environment-specific variables
- **Matrix Jobs**: Parallel testing across multiple configurations with dependencies
- **Artifact Passing**: Build once, deploy multiple times pattern

### 5. Security and Validation
- **Modern Scanning Tools**: Trivy (replaces tfsec 2026), Checkov for IaC validation
- **SAST/DAST Integration**: Early security scanning in pipeline stages
- **Dependency Scanning**: Vulnerability detection in third-party libraries with hash verification
- **Severity Thresholds**: Fail on CRITICAL/HIGH, warn on MEDIUM/LOW
- **Secret Management**: GitLab CI/CD variables, SOPS encryption, no hardcoded secrets
- **Validation Gates**: Required checks, manual approvals, compliance scanning
- **Policy Enforcement**: OPA/Rego policies, Kyverno, custom validation rules

### 6. Performance Optimization
- **DAG Parallelization**: Enable parallel execution with explicit dependencies
- **Docker Registry Caching**: Reduce build time by 60-80% with layer caching
- **Artifact Reuse**: Build once, pass to dependent jobs avoiding rebuilds
- **Dependency Caching**: Cache dependencies between pipeline runs
- **Selective Pipeline Triggers**: Use `rules: changes` to run only affected jobs
- **Fast Failure**: Stop pipeline early on critical errors

## Usage Instructions

### When Generating GitLab CI Pipelines

1. **Identify Deployment Target**
   - What infrastructure? (Terraform, Kubernetes, Helm, Docker)
   - Which cloud provider? (AWS, GCP, Azure)
   - Environment strategy? (Single, multi-env, progressive rollout)
   - Pipeline complexity? (Simple, DAG, parent-child for monorepo)

2. **Configure Authentication**
   - **Always prefer OIDC** over long-lived credentials (eliminate secrets)
   - Configure cloud provider OIDC trust policies with project/branch restrictions
   - Use GitLab Agent for Kubernetes authentication (preferred over certificates)
   - Migrate from certificate-based K8s integration (sunsets May 2026)
   - Use workload identity federation for maximum security

3. **Implement DAG Pipeline Architecture**
   - Use `needs:` to specify exact job dependencies (enable parallelization)
   - Combine stages for high-level organization with needs for fine-grained control
   - Implement `rules: changes` for monorepo path-based triggering
   - Use parent-child pipelines for complex multi-service repositories
   - Avoid circular dependencies in needs relationships

4. **Add Security Scanning**
   - **Use Trivy** (2026 standard, replaces deprecated tfsec)
     - Container vulnerabilities, IaC misconfigurations, secrets, licenses
     - Update vulnerability database before each scan
     - Use `--severity CRITICAL,HIGH` and `--ignore-unfixed` flags
     - Cache database between pipeline runs for performance
   - **Use Checkov** for multi-platform IaC (CloudFormation, Kubernetes, ARM)
     - 2000+ built-in policies for compliance (CIS, PCI-DSS, GDPR)
     - Kubernetes manifest and Dockerfile configuration scanning
   - **Set severity-based thresholds**: Fail on CRITICAL/HIGH, warn on MEDIUM/LOW
   - Document exceptions in `.trivyignore` with review dates and approvals

5. **Add Validation Gates**
   - `terraform validate` and `terraform plan` before apply
   - `kubectl --dry-run=server` for Kubernetes manifests
   - `helm lint --strict` for Helm charts
   - Security scanning with appropriate failure thresholds
   - Manual approval for production deployments using `when: manual`

6. **Structure Multi-Environment Pipelines**
   - Separate jobs for plan/validate vs. apply/deploy
   - Use environment-specific variables for configuration
   - **Build once, promote artifacts** (don't rebuild for each environment)
   - Use `needs:` for explicit job dependencies across environments
   - Implement rollback automation triggered on health check failures

7. **Optimize Pipeline Performance**
   - Use DAG with `needs:` to parallelize independent jobs
   - Enable Docker registry caching to reduce build time 60-80%
   - Cache dependencies (Terraform modules, npm packages, pip dependencies)
   - Use `rules: changes` to skip jobs when files unchanged
   - Set reasonable timeouts to prevent hung pipelines

8. **Handle Secrets Securely**
   - Never hardcode secrets in .gitlab-ci.yml files
   - Use GitLab CI/CD variables (project or group level) with masking
   - Use `protected: true` for production secrets
   - Reference `.env.example` pattern for required secret documentation
   - Rotate credentials regularly (or eliminate with OIDC/workload identity)

### Pattern Selection Guide

| Use Case | Recommended Pattern | Key Features |
|----------|---------------------|-------------|
| Terraform on AWS | OIDC + DAG + plan-on-MR | Restrictive trust policy, apply-on-merge, drift detection |
| Kubernetes deploy | GitLab Agent + Flux + progressive rollout | Health checks, canary deployment, auto-rollback |
| Helm release | GitLab Agent + staged release | Chart lint, environment-specific values, approval gates |
| Multi-cloud IaC | DAG matrix + OIDC | Parallel cloud deployments, workload identity |
| Monorepo CI/CD | Parent-child + rules changes | Path-based triggering, test only changed services |
| Docker build optimization | Registry cache + multi-stage | 60-80% time reduction, layer reuse |

## Security Best Practices

### OIDC Configuration

**AWS OIDC with GitLab Trust Policy**:
```yaml
# .gitlab-ci.yml
aws-deploy:
  stage: deploy
  image: amazon/aws-cli:latest
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://gitlab.com
  before_script:
    - >
      export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s"
      $(aws sts assume-role-with-web-identity
      --role-arn ${ROLE_ARN}
      --role-session-name "GitLabRunner-${CI_PROJECT_ID}-${CI_PIPELINE_ID}"
      --web-identity-token ${GITLAB_OIDC_TOKEN}
      --duration-seconds 3600
      --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]'
      --output text))
  script:
    - aws s3 ls  # Verify authentication works
  variables:
    ROLE_ARN: "arn:aws:iam::123456789012:role/gitlab-oidc-role"
```

**AWS IAM Trust Policy Example** (restrictive):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "gitlab.com:aud": "https://gitlab.com",
        "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main"
      }
    }
  }]
}
```

**GCP Workload Identity Federation**:
```yaml
gcp-deploy:
  stage: deploy
  image: google/cloud-sdk:alpine
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/gitlab-pool/providers/gitlab-provider
  before_script:
    - echo ${GITLAB_OIDC_TOKEN} > token.txt
    - gcloud iam workload-identity-pools create-cred-config
        projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/gitlab-pool/providers/gitlab-provider
        --service-account=gitlab-sa@PROJECT_ID.iam.gserviceaccount.com
        --credential-source-file=token.txt
        --output-file=creds.json
    - export GOOGLE_APPLICATION_CREDENTIALS=creds.json
  script:
    - gcloud auth list
    - gcloud projects list
```

### Secret Management Best Practices

- Use `.env.example` with placeholder values (NEVER real secrets)
- Document required secrets in README with descriptions
- Enable secret detection in GitLab (Settings → Security & Compliance)
- Use `gitleaks` or `truffleHog` in pre-commit hooks
- Rotate credentials quarterly or eliminate with OIDC
- Use `protected: true` for production CI/CD variables

### GitLab Agent for Kubernetes (Preferred Pattern)

**Agent Configuration** (`.gitlab/agents/production/config.yaml`):
```yaml
gitops:
  manifest_projects:
    - id: mygroup/k8s-manifests
      paths:
        - glob: 'production/**/*.yaml'
      reconcile_timeout: 3600s
      dry_run_strategy: none
      prune: true
      prune_timeout: 3600s
      inventory_policy: must_match

flux_integration:
  enabled: true
  sources:
    - kind: OCIRepository
      namespace: flux-system
      name: app-manifests

ci_access:
  projects:
    - id: mygroup/myproject
      agent_authorizations:
        - agent: production
          environment: production
```

**Pipeline using GitLab Agent**:
```yaml
deploy-k8s:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl config use-context mygroup/myproject:production
    - kubectl apply -f k8s/manifests/ --dry-run=server
    - kubectl apply -f k8s/manifests/
    - kubectl rollout status deployment/myapp -n production
  environment:
    name: production
    kubernetes:
      namespace: production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

**Flux Integration with GitLab Agent**:
```yaml
# .gitlab-ci.yml - Build and push OCI image
build-manifests:
  stage: build
  image: alpine:latest
  before_script:
    - apk add --no-cache oras
  script:
    - cd k8s/manifests
    - oras push ${CI_REGISTRY_IMAGE}/manifests:${CI_COMMIT_SHA}
        --artifact-type application/vnd.cncf.flux.config.v1+yaml
        $(find . -type f -name "*.yaml")
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - k8s/manifests/**/*

# Flux automatically reconciles from OCI repository via GitLab Agent
```

## DAG Pipeline Patterns

### Basic DAG with Parallel Execution

```yaml
stages:
  - build
  - test
  - deploy

# Build jobs run in parallel
build-frontend:
  stage: build
  script:
    - npm run build
  artifacts:
    paths:
      - frontend/dist

build-backend:
  stage: build
  script:
    - go build -o backend
  artifacts:
    paths:
      - backend

# Test jobs use needs to start immediately after their build completes
test-frontend:
  stage: test
  needs: ["build-frontend"]
  script:
    - npm test

test-backend:
  stage: test
  needs: ["build-backend"]
  script:
    - go test ./...

# Deploy only needs successful tests, not entire test stage
deploy-production:
  stage: deploy
  needs:
    - job: test-frontend
      artifacts: false
    - job: test-backend
      artifacts: false
    - job: build-frontend
      artifacts: true
    - job: build-backend
      artifacts: true
  script:
    - ./deploy.sh
  environment:
    name: production
  when: manual
```

### Monorepo Parent-Child Pipeline with Path Triggers

**Parent Pipeline** (`.gitlab-ci.yml`):
```yaml
stages:
  - trigger

.service_template:
  stage: trigger
  trigger:
    include:
      - local: services/$SERVICE/ci.yml
    strategy: depend
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - services/$SERVICE/**/*

trigger-api:
  extends: .service_template
  variables:
    SERVICE: api

trigger-web:
  extends: .service_template
  variables:
    SERVICE: web

trigger-worker:
  extends: .service_template
  variables:
    SERVICE: worker
```

**Child Pipeline** (`services/api/ci.yml`):
```yaml
stages:
  - validate
  - test
  - build
  - deploy

validate:
  stage: validate
  script:
    - cd services/api
    - go vet ./...
    - golangci-lint run

test:
  stage: test
  needs: ["validate"]
  script:
    - cd services/api
    - go test -cover ./...

build:
  stage: build
  needs: ["test"]
  script:
    - cd services/api
    - docker build -t $CI_REGISTRY_IMAGE/api:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE/api:$CI_COMMIT_SHA

deploy-dev:
  stage: deploy
  needs: ["build"]
  script:
    - kubectl set image deployment/api api=$CI_REGISTRY_IMAGE/api:$CI_COMMIT_SHA -n dev
  environment:
    name: dev
```

### Hybrid Stage + DAG Pattern

```yaml
stages:
  - validate
  - build
  - test
  - security
  - deploy

# Stage 1: Validation runs first (no dependencies)
terraform-validate:
  stage: validate
  script:
    - terraform fmt -check
    - terraform validate

# Stage 2: Build can start after validation
terraform-plan:
  stage: build
  needs: ["terraform-validate"]
  script:
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - tfplan

# Stage 3: Tests run in parallel after plan
unit-tests:
  stage: test
  needs: ["terraform-plan"]
  script:
    - terraform test

# Stage 4: Security scans also depend on plan
trivy-scan:
  stage: security
  needs: ["terraform-plan"]
  image: aquasec/trivy:latest
  script:
    - trivy config --severity CRITICAL,HIGH .

checkov-scan:
  stage: security
  needs: ["terraform-plan"]
  image: bridgecrew/checkov:latest
  script:
    - checkov -d . --framework terraform

# Stage 5: Deploy only after ALL security checks pass
terraform-apply:
  stage: deploy
  needs:
    - job: terraform-plan
      artifacts: true
    - job: unit-tests
      artifacts: false
    - job: trivy-scan
      artifacts: false
    - job: checkov-scan
      artifacts: false
  script:
    - terraform apply tfplan
  when: manual
  environment:
    name: production
```

## Security Scanning Integration

### Trivy Security Scanning (2026 Standard)

**Trivy replaces tfsec** as of 2026 - provides:
- Container vulnerability scanning
- IaC misconfiguration detection (Terraform, CloudFormation, Kubernetes, Dockerfile)
- Secret detection in code
- License scanning (SBOM generation)

**Trivy Configuration** (recommended):
```yaml
.trivy_template:
  image: aquasec/trivy:latest
  before_script:
    - trivy --version
    # Update vulnerability database
    - trivy image --download-db-only
  cache:
    key: trivy-db
    paths:
      - .trivy-cache/

trivy-iac-scan:
  extends: .trivy_template
  stage: security
  script:
    - trivy config
        --severity CRITICAL,HIGH
        --ignore-unfixed
        --exit-code 1
        --format sarif
        --output trivy-iac-results.sarif
        infrastructure/
  artifacts:
    reports:
      sast: trivy-iac-results.sarif
    when: always

trivy-container-scan:
  extends: .trivy_template
  stage: security
  needs: ["docker-build"]
  script:
    - trivy image
        --severity CRITICAL,HIGH
        --ignore-unfixed
        --exit-code 1
        ${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
```

**Trivy Exception Handling** (`.trivyignore`):
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

```yaml
checkov-kubernetes:
  stage: security
  image: bridgecrew/checkov:latest
  script:
    - checkov
        --directory k8s/
        --framework kubernetes
        --soft-fail false
        --skip-check CKV_K8S_8,CKV_K8S_9
        --output sarif
        --output-file-path checkov-results.sarif
  artifacts:
    reports:
      sast: checkov-results.sarif
    when: always

checkov-terraform:
  stage: security
  image: bridgecrew/checkov:latest
  script:
    - checkov
        --directory terraform/
        --framework terraform
        --soft-fail false
        --compact
        --check CKV_AWS_*,CKV2_AWS_*
        --output cli,sarif,json
  artifacts:
    reports:
      sast: results_sarif.sarif
    when: always
```

### SAST/DAST Integration

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/DAST.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml

# Override default SAST configuration
sast:
  stage: security
  variables:
    SAST_EXCLUDED_PATHS: "spec,test,tests,tmp,vendor"
    FAIL_NEVER: 0  # Fail pipeline on findings

# Override DAST configuration
dast:
  stage: security
  variables:
    DAST_WEBSITE: https://staging.example.com
    DAST_FULL_SCAN_ENABLED: "true"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Workflow Examples

### Complete Terraform AWS Workflow with OIDC and DAG

```yaml
stages:
  - validate
  - plan
  - security
  - apply

variables:
  AWS_ROLE_ARN: "arn:aws:iam::123456789012:role/gitlab-oidc-terraform"
  TF_ROOT: "${CI_PROJECT_DIR}/infrastructure"
  TF_STATE_NAME: "${CI_PROJECT_NAME}"

.terraform_template:
  image:
    name: hashicorp/terraform:1.7
    entrypoint: [""]
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://gitlab.com
  before_script:
    - cd ${TF_ROOT}
    # Configure AWS credentials via OIDC
    - apk add --no-cache aws-cli
    - >
      export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s"
      $(aws sts assume-role-with-web-identity
      --role-arn ${AWS_ROLE_ARN}
      --role-session-name "GitLabRunner-${CI_PROJECT_ID}-${CI_PIPELINE_ID}"
      --web-identity-token ${GITLAB_OIDC_TOKEN}
      --duration-seconds 3600
      --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]'
      --output text))
    - terraform --version

terraform-fmt:
  extends: .terraform_template
  stage: validate
  script:
    - terraform fmt -check -recursive
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

terraform-validate:
  extends: .terraform_template
  stage: validate
  script:
    - terraform init -backend=false
    - terraform validate
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

terraform-plan:
  extends: .terraform_template
  stage: plan
  needs:
    - terraform-fmt
    - terraform-validate
  script:
    - terraform init
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - ${TF_ROOT}/tfplan
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

trivy-iac:
  stage: security
  needs: ["terraform-validate"]
  image: aquasec/trivy:latest
  script:
    - trivy config
        --severity CRITICAL,HIGH
        --ignore-unfixed
        --exit-code 1
        ${TF_ROOT}
  cache:
    key: trivy-db
    paths:
      - .trivy-cache/

checkov-iac:
  stage: security
  needs: ["terraform-validate"]
  image: bridgecrew/checkov:latest
  script:
    - checkov -d ${TF_ROOT} --framework terraform --soft-fail false

terraform-apply:
  extends: .terraform_template
  stage: apply
  needs:
    - job: terraform-plan
      artifacts: true
    - job: trivy-iac
      artifacts: false
    - job: checkov-iac
      artifacts: false
  script:
    - terraform init
    - terraform apply -auto-approve tfplan
  environment:
    name: production
    action: start
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Kubernetes Progressive Rollout with GitLab Agent

```yaml
stages:
  - build
  - validate
  - deploy-canary
  - deploy-production

variables:
  KUBE_CONTEXT: mygroup/myproject:production-agent

docker-build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build
        --cache-from ${CI_REGISTRY_IMAGE}:latest
        -t ${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
        -t ${CI_REGISTRY_IMAGE}:latest
        .
    - docker push ${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
    - docker push ${CI_REGISTRY_IMAGE}:latest
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - src/**/*
        - Dockerfile

validate-manifests:
  stage: validate
  image: bitnami/kubectl:latest
  script:
    - kubectl apply --dry-run=server -f k8s/ --context=${KUBE_CONTEXT}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

scan-manifests:
  stage: validate
  image: bridgecrew/checkov:latest
  script:
    - checkov -d k8s/ --framework kubernetes --soft-fail false
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy-canary:
  stage: deploy-canary
  image: bitnami/kubectl:latest
  needs:
    - docker-build
    - validate-manifests
    - scan-manifests
  script:
    - kubectl config use-context ${KUBE_CONTEXT}
    - kubectl set image deployment/myapp-canary
        myapp=${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
        -n production
    - kubectl rollout status deployment/myapp-canary -n production --timeout=5m
    # Health check for canary
    - sleep 60
    - |
      ERROR_RATE=$(kubectl exec -n production deploy/myapp-canary -- \
        curl -s http://localhost:9090/metrics | grep error_rate | awk '{print $2}')
      if (( $(echo "$ERROR_RATE > 0.05" | bc -l) )); then
        echo "Canary error rate too high: $ERROR_RATE"
        exit 1
      fi
      echo "Canary health check passed: error_rate=$ERROR_RATE"
  environment:
    name: production-canary
    action: start
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy-production:
  stage: deploy-production
  image: bitnami/kubectl:latest
  needs:
    - deploy-canary
  script:
    - kubectl config use-context ${KUBE_CONTEXT}
    - kubectl set image deployment/myapp
        myapp=${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
        -n production
    - kubectl rollout status deployment/myapp -n production --timeout=10m
    # Production health check
    - sleep 30
    - |
      for i in {1..10}; do
        if curl -f https://api.production.example.com/health; then
          echo "Production health check passed"
          exit 0
        fi
        sleep 10
      done
      echo "Production health check failed - rolling back"
      kubectl rollout undo deployment/myapp -n production
      kubectl rollout undo deployment/myapp-canary -n production
      exit 1
  environment:
    name: production
    action: start
    on_stop: rollback-production
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

rollback-production:
  stage: deploy-production
  image: bitnami/kubectl:latest
  script:
    - kubectl config use-context ${KUBE_CONTEXT}
    - kubectl rollout undo deployment/myapp -n production
    - kubectl rollout undo deployment/myapp-canary -n production
    - kubectl rollout status deployment/myapp -n production --timeout=5m
  environment:
    name: production
    action: stop
  when: manual
```

### Helm Chart Deployment with Multi-Environment

```yaml
stages:
  - validate
  - deploy

.helm_template:
  image: alpine/helm:latest
  before_script:
    - helm version

helm-lint:
  extends: .helm_template
  stage: validate
  script:
    - helm lint --strict charts/myapp
    - helm template charts/myapp | kubectl apply --dry-run=client -f -

helm-security:
  stage: validate
  image: aquasec/trivy:latest
  script:
    - helm template charts/myapp > rendered-manifests.yaml
    - trivy config --severity CRITICAL,HIGH rendered-manifests.yaml

deploy-dev:
  extends: .helm_template
  stage: deploy
  needs: ["helm-lint", "helm-security"]
  script:
    - helm upgrade --install myapp charts/myapp
        --namespace dev
        --create-namespace
        --values charts/myapp/values-dev.yaml
        --set image.tag=${CI_COMMIT_SHA}
        --wait --timeout 5m
  environment:
    name: dev
    url: https://dev.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"

deploy-staging:
  extends: .helm_template
  stage: deploy
  needs: ["deploy-dev"]
  script:
    - helm upgrade --install myapp charts/myapp
        --namespace staging
        --create-namespace
        --values charts/myapp/values-staging.yaml
        --set image.tag=${CI_COMMIT_SHA}
        --wait --timeout 5m
  environment:
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy-production:
  extends: .helm_template
  stage: deploy
  needs: ["deploy-staging"]
  script:
    - helm upgrade --install myapp charts/myapp
        --namespace production
        --create-namespace
        --values charts/myapp/values-production.yaml
        --set image.tag=${CI_COMMIT_SHA}
        --wait --timeout 10m
    # Run Helm tests
    - helm test myapp --namespace production
  environment:
    name: production
    url: https://production.example.com
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Troubleshooting

### OIDC Authentication Failures

**Symptom**: `Error: Could not assume role with OIDC`

**Solutions**:
1. Verify IAM trust policy includes correct GitLab project path and branch:
   ```json
   "Condition": {
     "StringEquals": {
       "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main"
     }
   }
   ```
2. Check `id_tokens:` configured correctly in job with proper audience
3. Ensure OIDC provider configured in cloud account (AWS: Identity Provider, GCP: Workload Identity Pool)
4. Validate token claims match cloud provider expectations
5. Check GitLab runner has network access to cloud provider OIDC endpoints

### DAG Circular Dependencies

**Symptom**: `Error: Circular dependency detected`

**Solutions**:
1. Map out dependency graph before implementation
2. Use `gitlab-ci-lint` to validate pipeline configuration
3. Visualize pipeline DAG in GitLab UI (CI/CD → Pipelines → Graph)
4. Break circular dependencies by removing unnecessary needs relationships
5. Consider splitting into parent-child pipelines if too complex

### GitLab Agent Connection Issues

**Symptom**: `Error: Unable to connect to Kubernetes cluster via agent`

**Solutions**:
1. Verify agent is running: `kubectl get pods -n gitlab-agent`
2. Check agent configuration in `.gitlab/agents/<agent-name>/config.yaml`
3. Ensure project authorized in agent config under `ci_access:`
4. Verify runner can reach GitLab Agent (network policies)
5. Check agent logs: `kubectl logs -n gitlab-agent -l app=gitlab-agent`

### Certificate-Based Integration Deprecation

**Symptom**: `Warning: Certificate-based Kubernetes integration will sunset May 2026`

**Solutions**:
1. Audit projects using certificate-based integration
2. Install GitLab Agent in cluster: `helm install gitlab-agent gitlab/gitlab-agent`
3. Update pipelines to use agent context: `kubectl config use-context mygroup/myproject:agent-name`
4. Test agent functionality in non-production first
5. Document new GitOps workflows for team

### Pipeline Performance Issues

**Symptom**: Pipeline runs slowly despite DAG configuration

**Solutions**:
1. Check runner capacity - may need more concurrent runners
2. Verify `needs:` configured correctly (check pipeline graph)
3. Enable Docker registry caching for builds
4. Use `artifacts: false` in needs when artifacts not required
5. Implement `rules: changes` to skip unnecessary jobs
6. Cache dependencies (Terraform modules, npm packages, pip)

## Integration with IaC Team Plugin

This skill is designed to be referenced by the `iac-generator` agent when creating CI/CD workflows:

**Generator should**:
1. Call this skill's patterns based on detected infrastructure type
2. Generate DAG pipelines with optimal parallelization using `needs:`
3. Configure OIDC with restrictive trust policies for target cloud environment
4. Include modern security scanning (Trivy 2026) with appropriate thresholds
5. Implement artifact reuse pattern (build once, deploy multiple environments)
6. Add rollback automation triggered on health check failures
7. Use GitLab Agent for Kubernetes deployments (not certificate-based)
8. Optimize performance with Docker registry caching and selective job triggering
9. Implement parent-child pipelines for monorepo projects

**Generator should NOT**:
1. Generate pipelines without DAG optimization (always use `needs:` when appropriate)
2. Include long-lived credentials (always use OIDC/workload identity)
3. Skip validation or security scanning steps
4. Use deprecated certificate-based Kubernetes integration (migrate to agent)
5. Use deprecated tools (tfsec → Trivy)
6. Create separate pipelines for each environment (use single pipeline with environments)
7. Rebuild artifacts for each environment (build once, promote)
8. Ignore monorepo optimization opportunities (parent-child + rules changes)

## Version Compatibility

- **GitLab**: 16.2+ (for Flux-based GitOps with Agent)
- **GitLab Runner**: 16.0+
- **Trivy**: Latest (replaces tfsec 2026+)
- **Checkov**: Latest (2000+ policies)
- **Terraform**: 1.6+ (native testing), 1.7+ (import with for_each, mocking)
- **Kubernetes**: 1.29+ (native sidecars), 1.31+ (Gateway API v1 GA)
- **Helm**: 3.0+
- **GitLab Agent**: 16.0+ (for Flux integration)

## Migration Guides

### Migrating from Certificate-Based Kubernetes Integration

**Before May 2026 deadline:**

1. **Install GitLab Agent in cluster**:
```bash
helm repo add gitlab https://charts.gitlab.io
helm repo update
helm upgrade --install gitlab-agent gitlab/gitlab-agent \
  --namespace gitlab-agent \
  --create-namespace \
  --set config.token=<YOUR_AGENT_TOKEN> \
  --set config.kasAddress=wss://kas.gitlab.com
```

2. **Register agent in GitLab**:
   - Navigate to Infrastructure → Kubernetes clusters → Connect a cluster
   - Create agent configuration in `.gitlab/agents/<agent-name>/config.yaml`
   - Copy registration token

3. **Update pipeline to use agent context**:
```yaml
# Before (deprecated)
deploy:
  script:
    - kubectl apply -f k8s/

# After (agent-based)
deploy:
  script:
    - kubectl config use-context mygroup/myproject:agent-name
    - kubectl apply -f k8s/
  environment:
    kubernetes:
      namespace: production
```

4. **Test in non-production** before migrating production workloads

5. **Remove old certificate-based integration** after successful migration

## Updates and Maintenance

When updating this skill:
1. Test patterns in real GitLab projects before updating skill
2. Monitor GitLab release notes for CI/CD feature changes
3. Migrate from deprecated features (certificate-based K8s → agent)
4. Review and update OIDC trust policy recommendations
5. Validate against current GitLab CI/CD capabilities and limits
6. Update DAG pipeline examples with latest optimization patterns
7. Add new security scanning patterns as tools evolve
8. Document breaking changes with migration guides
9. Keep version compatibility matrix current
10. Test rollback and health check patterns under realistic failure scenarios
