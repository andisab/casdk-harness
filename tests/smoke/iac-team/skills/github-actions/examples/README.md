# GitHub Actions Workflow Examples

This directory contains complete, production-ready GitHub Actions workflow examples for infrastructure-as-code deployments.

## Available Examples

### terraform-aws-oidc.yml
Complete Terraform workflow for AWS deployments using OIDC authentication.

**Features**:
- OIDC authentication (no long-lived AWS credentials)
- Plan on pull request with automatic PR comments
- Apply on merge to main branch
- Scheduled drift detection
- State management with S3 and DynamoDB locking
- Security scanning with tfsec

**Use when**: Deploying Terraform infrastructure to AWS

---

### kubernetes-deploy.yml
Kubernetes manifest deployment with progressive rollout and validation gates.

**Features**:
- Multi-stage validation (syntax, security, dry-run)
- Progressive rollout with canary deployments
- Environment-based deployments (dev → staging → production)
- Health checks and automatic rollback
- Security scanning with kubesec
- Manual approval gates for production

**Use when**: Deploying Kubernetes manifests to EKS or other clusters

---

## Coming Soon

- `helm-release.yml` - Helm chart deployment with multi-environment promotion
- `multi-cloud.yml` - Matrix deployment to AWS, Azure, and GCP
- `promotion-pipeline.yml` - Artifact promotion between environments

## Usage

1. Copy the relevant example to your repository's `.github/workflows/` directory
2. Replace placeholder values (secrets, cluster names, regions, etc.)
3. Configure GitHub environments in repository settings
4. Set up OIDC provider in your cloud account (see templates/ directory)
5. Configure required secrets in GitHub repository or environment settings

## Security Notes

- All examples use OIDC authentication (no long-lived credentials)
- Minimal permissions are granted to workflow tokens
- Secrets are never hardcoded in workflow files
- Security scanning is included in validation steps
- Manual approval gates are required for production deployments

## Testing

Before using in production:
1. Test workflows in a non-production environment
2. Verify OIDC authentication works correctly
3. Test approval gates and rollback procedures
4. Validate that security scans catch issues
5. Confirm drift detection works as expected
