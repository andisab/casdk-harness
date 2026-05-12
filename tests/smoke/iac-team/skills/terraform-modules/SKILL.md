---
name: terraform-modules
description: >
  Terraform and OpenTofu module patterns, best practices, and code generation.
  Provides reusable infrastructure patterns for AWS, GCP, Azure, and Kubernetes.

  Activate when user mentions: terraform, opentofu, HCL, tf files, module development,
  terraform modules, infrastructure modules, terraform best practices, terraform security,
  provider configuration, state management, terraform workspaces, remote state, terraform testing,
  terraform mocking, infrastructure cost optimization, spot instances.

  Use for: Generating terraform modules, terraform code patterns, provider configurations,
  variable definitions, output blocks, module composition, security patterns, native testing,
  cost optimization strategies, AI-assisted IaC validation.

  Do NOT use for: Kubernetes-native manifests (use kubernetes-native skill), repository
  analysis (use iac-analyzer agent), or executing terraform commands.
---

# Terraform Modules Skill

## Purpose

Provides Terraform/OpenTofu module patterns, best practices, and secure code generation for the iac-generator agent. This skill supplies reusable infrastructure patterns that follow security, operational, and cost optimization best practices with modern Terraform 1.7+ features.

## Core Capabilities

### Module Structure Patterns

**Standard Module Layout**:
```
module-name/
├── main.tf           # Primary resources
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── versions.tf       # Provider version constraints
├── README.md         # Module documentation
├── tests/            # Terraform native tests (1.6+)
│   ├── basic.tftest.hcl
│   ├── integration.tftest.hcl
│   └── mocks.tftest.hcl
└── examples/         # Usage examples
    └── basic/
        ├── main.tf
        └── variables.tf
```

**Key Principles**:
- One resource type per module for composability
- Clear variable naming with descriptions and validation
- Meaningful outputs for module composition
- Version constraints for provider stability (Terraform >= 1.7.0 for advanced features)
- Native test coverage using .tftest.hcl files

### Security Best Practices

**Credential Management**:
- ✅ Use OIDC authentication for CI/CD (AWS, GCP, Azure)
- ✅ Reference secrets from environment variables or secret managers
- ✅ Use `.env.example` → `.env.local` pattern for local development
- ✅ Implement workload identity federation for automated flows
- ❌ NEVER hardcode credentials in `.tf` files
- ❌ NEVER commit `.tfvars` files with secrets
- ❌ NEVER use long-lived service account keys or personal access tokens

**Provider Authentication Examples**:
```hcl
# AWS - OIDC for GitHub Actions
provider "aws" {
  region = var.aws_region
  # OIDC authentication via AWS_ROLE_ARN environment variable
  # No static credentials needed
  # GitHub Actions workflow configures id-token: write permission
}

# GCP - Workload Identity
provider "google" {
  project = var.project_id
  region  = var.region
  # Uses GOOGLE_APPLICATION_CREDENTIALS or Workload Identity
  # GitHub Actions: google-github-actions/auth@v2
}

# Azure - Managed Identity
provider "azurerm" {
  features {}
  # Uses Azure CLI auth or Managed Identity
  use_msi = true
  # GitHub Actions: azure/login@v2 with OIDC
}
```

**GitHub Actions OIDC Configuration**:
```yaml
# .github/workflows/terraform.yml
permissions:
  id-token: write   # Required for OIDC token requests
  contents: read    # Required for code checkout

steps:
  - uses: actions/checkout@v4

  - name: Configure AWS credentials
    uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/github-actions-terraform
      aws-region: us-east-1
      # IAM role trust policy restricts to specific repository and branch
      # condition: token.actions.githubusercontent.com:sub = "repo:org/repo:ref:refs/heads/main"

  - name: Terraform Apply
    run: terraform apply -auto-approve
```

**State Management Security**:
```hcl
# Remote state with encryption
terraform {
  required_version = ">= 1.7.0"

  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "prod/infrastructure.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:123456789:key/..."
    dynamodb_table = "terraform-locks"
  }
}
```

### Variable Patterns

**Input Variables with Validation**:
```hcl
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"

  validation {
    condition     = can(regex("^t3\\.", var.instance_type))
    error_message = "Instance type must be a t3 family instance."
  }
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
```

**Sensitive Variables**:
```hcl
variable "database_password" {
  description = "Database master password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.database_password) >= 16
    error_message = "Password must be at least 16 characters."
  }
}
```

### Output Patterns

**Structured Outputs for Composition**:
```hcl
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.main.id
}

# Complex outputs for module chaining
output "database_connection" {
  description = "Database connection details"
  value = {
    endpoint = aws_db_instance.main.endpoint
    port     = aws_db_instance.main.port
    name     = aws_db_instance.main.db_name
  }
  sensitive = true
}
```

### Provider Version Constraints

**Versions File Pattern**:
```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }
}
```

### Module Composition

**Calling Child Modules**:
```hcl
module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = "10.0.0.0/16"
  availability_zones  = ["us-east-1a", "us-east-1b"]

  tags = local.common_tags
}

module "database" {
  source = "./modules/rds"

  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  security_group_id = module.vpc.database_sg_id

  instance_class = "db.t3.micro"
  engine_version = "15.4"

  tags = local.common_tags
}
```

### Local Values and Data Sources

**Computed Values**:
```hcl
locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = var.project_name
  }

  name_prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Dynamic AMI selection to avoid hardcoded values
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}
```

## Terraform 1.7+ Native Testing Framework

### Test Structure

**Basic Unit Test with Command = Plan**:
```hcl
# tests/basic.tftest.hcl
variables {
  environment  = "test"
  project_name = "terraform-test"
}

run "validate_vpc_creation" {
  command = plan

  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR block should be 10.0.0.0/16"
  }

  assert {
    condition     = aws_vpc.main.enable_dns_hostnames == true
    error_message = "DNS hostnames should be enabled"
  }
}

run "validate_subnet_count" {
  command = plan

  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Should create 2 private subnets"
  }
}
```

**Integration Test with Command = Apply**:
```hcl
# tests/integration.tftest.hcl
run "create_and_validate_vpc" {
  command = apply

  assert {
    condition     = output.vpc_id != ""
    error_message = "VPC ID should be populated"
  }

  assert {
    condition     = length(output.private_subnet_ids) == 2
    error_message = "Should output 2 private subnet IDs"
  }
}

run "validate_tagging" {
  command = plan

  assert {
    condition     = aws_vpc.main.tags["Environment"] == var.environment
    error_message = "VPC should have Environment tag"
  }
}
```

### Mocking for Unit Tests (Terraform 1.7+)

**Testing Without Cloud API Calls**:
```hcl
# tests/mocks.tftest.hcl
mock_provider "aws" {
  # Mock all AWS resources to avoid API calls
  mock_resource "aws_vpc" {
    defaults = {
      id         = "vpc-mock12345"
      cidr_block = "10.0.0.0/16"
      arn        = "arn:aws:ec2:us-east-1:123456789:vpc/vpc-mock12345"
    }
  }

  mock_resource "aws_subnet" {
    defaults = {
      id               = "subnet-mock12345"
      availability_zone = "us-east-1a"
      cidr_block       = "10.0.1.0/24"
    }
  }
}

variables {
  environment  = "test"
  project_name = "mock-test"
}

run "test_module_logic" {
  command = plan

  assert {
    condition     = aws_vpc.main.enable_dns_hostnames == true
    error_message = "DNS hostnames logic should be correct"
  }
}
```

**Mocking Specific Resource Instances**:
```hcl
# Override specific instance while keeping real provider for others
override_resource {
  target = aws_db_instance.main
  values = {
    endpoint = "mock-db.us-east-1.rds.amazonaws.com:5432"
    arn      = "arn:aws:rds:us-east-1:123456789:db:mock-db"
  }
}
```

**Important Mocking Considerations**:
- Mocked providers generate default values for computed attributes (0, false, empty, random strings)
- Provide explicit mock values that satisfy strict validation (UUIDs, email formats, ARNs)
- Use mocking for unit tests of logic; always validate with real provider integration tests
- Mocked behavior may not match actual provider API behavior

### Import Blocks with for_each (Terraform 1.7+)

**Bulk Resource Import**:
```hcl
# Import multiple existing resources using for_each
variable "existing_namespaces" {
  type = map(object({
    name = string
  }))
  default = {
    dev     = { name = "development" }
    staging = { name = "staging" }
    prod    = { name = "production" }
  }
}

import {
  for_each = var.existing_namespaces
  to       = kubernetes_namespace.app[each.key]
  id       = each.value.name
}

resource "kubernetes_namespace" "app" {
  for_each = var.existing_namespaces

  metadata {
    name = each.value.name
    labels = {
      environment = each.key
    }
  }
}
```

**Complex Resource ID Import**:
```hcl
# Import resources with complex IDs requiring string interpolation
variable "security_groups" {
  type = map(object({
    vpc_id  = string
    sg_name = string
  }))
}

import {
  for_each = var.security_groups
  to       = aws_security_group.app[each.key]
  id       = "${each.value.vpc_id}/${each.value.sg_name}"
}
```

**Version Compatibility**: Requires Terraform >= 1.7.0 for for_each on import blocks

## Multi-Cloud Patterns

### AWS

**Common Resources**:
- VPC with public/private subnets
- EC2 instances with user data
- RDS databases with encryption
- S3 buckets with versioning and encryption
- IAM roles with OIDC for GitHub Actions
- Security groups with minimal access

**Cost-Optimized EC2 with Spot Instances**:
```hcl
# Auto Scaling group with Spot instances for 66-90% cost savings
resource "aws_autoscaling_group" "app" {
  name                = "${local.name_prefix}-asg"
  vpc_zone_identifier = var.subnet_ids
  min_size            = 1
  max_size            = 10
  desired_capacity    = 3

  mixed_instances_policy {
    instances_distribution {
      # Use price-capacity-optimized for lowest price and interruption risk
      spot_allocation_strategy            = "price-capacity-optimized"
      on_demand_base_capacity             = 1    # Always keep 1 On-Demand
      on_demand_percentage_above_base     = 20   # 20% On-Demand, 80% Spot
      spot_instance_pools                 = 4    # Diversify across 4+ pools
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.app.id
        version            = "$Latest"
      }

      # Diversify across 4+ instance types to reduce interruption risk
      override {
        instance_type = "t3.medium"
      }
      override {
        instance_type = "t3a.medium"
      }
      override {
        instance_type = "t3.large"
      }
      override {
        instance_type = "t3a.large"
      }
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-spot-instance"
    propagate_at_launch = true
  }
}

# EventBridge rule for Spot interruption handling
resource "aws_cloudwatch_event_rule" "spot_interruption" {
  name        = "${local.name_prefix}-spot-interruption"
  description = "Capture EC2 Spot Instance Interruption Warnings"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
}

resource "aws_cloudwatch_event_target" "spot_handler" {
  rule      = aws_cloudwatch_event_rule.spot_interruption.name
  target_id = "SpotInterruptionHandler"
  arn       = aws_lambda_function.spot_handler.arn
}
```

**Right-Sizing and Auto-Scaling**:
```hcl
# Target tracking scaling policy for optimal 40-70% CPU utilization
resource "aws_autoscaling_policy" "cpu_target" {
  name                   = "${local.name_prefix}-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60.0  # Maintain 60% CPU for optimal cost-performance
  }
}

# Scheduled scaling for non-production environments (70% cost savings)
resource "aws_autoscaling_schedule" "scale_down_off_hours" {
  count                  = var.environment != "prod" ? 1 : 0
  scheduled_action_name  = "${local.name_prefix}-scale-down-nights"
  autoscaling_group_name = aws_autoscaling_group.app.name
  min_size               = 0
  max_size               = 0
  desired_capacity       = 0
  recurrence             = "0 22 * * MON-FRI"  # 10 PM weeknights
}

resource "aws_autoscaling_schedule" "scale_up_business_hours" {
  count                  = var.environment != "prod" ? 1 : 0
  scheduled_action_name  = "${local.name_prefix}-scale-up-mornings"
  autoscaling_group_name = aws_autoscaling_group.app.name
  min_size               = 1
  max_size               = 10
  desired_capacity       = 3
  recurrence             = "0 8 * * MON-FRI"  # 8 AM weekday mornings
}
```

### GCP

**Common Resources**:
- VPC networks with subnets
- Compute instances with service accounts
- Cloud SQL with private IP
- GCS buckets with uniform access
- Workload Identity for GKE
- Firewall rules with tags

**Cost-Optimized Compute with Preemptible Instances**:
```hcl
resource "google_compute_instance_template" "app" {
  name_prefix  = "${local.name_prefix}-template-"
  machine_type = "e2-medium"  # E2 instances for cost efficiency

  scheduling {
    preemptible         = true   # 60-91% discount vs standard
    automatic_restart   = false
    on_host_maintenance = "TERMINATE"
  }

  disk {
    source_image = data.google_compute_image.debian.self_link
    auto_delete  = true
    boot         = true
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

### Azure

**Common Resources**:
- Virtual networks with subnets
- Virtual machines with managed identities
- Azure SQL with firewall rules
- Storage accounts with encryption
- Azure AD service principals
- Network security groups

## Kubernetes Provider Integration

**Provisioning Kubernetes Resources**:
```hcl
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca_cert)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name",
      module.eks.cluster_name
    ]
  }
}

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_namespace

    labels = {
      environment = var.environment
    }
  }
}

# Resource limits for cost control
resource "kubernetes_limit_range" "app" {
  metadata {
    name      = "resource-limits"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "500m"
        memory = "512Mi"
      }
      default_request = {
        cpu    = "100m"
        memory = "128Mi"
      }
    }
  }
}
```

## AI-Assisted IaC Validation and Security

### Validation Pipeline Pattern

**Two-Phase Validation**:
```hcl
# Technical validation: terraform plan + syntax check
# Intent validation: OPA/Rego policy enforcement

# .github/workflows/terraform-validate.yml
name: Terraform Validation

on: [pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Phase 1: Technical validation
      - name: Terraform Format Check
        run: terraform fmt -check -recursive

      - name: Terraform Init
        run: terraform init -backend=false

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        run: terraform plan -out=tfplan

      # Phase 2: Security scanning (Trivy replaces tfsec as of 2026)
      - name: Run Trivy IaC Scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'config'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'  # Fail on CRITICAL/HIGH only
          ignore-unfixed: true  # Don't block on vulnerabilities without fixes

      # Phase 3: Policy-as-code validation (OPA)
      - name: Run OPA Policy Check
        run: |
          opa test policies/
          conftest test tfplan --policy policies/
```

### Security Scanning Best Practices

**Trivy Configuration** (successor to tfsec):
```bash
# Scan Terraform code for misconfigurations
trivy config . \
  --severity CRITICAL,HIGH \
  --ignore-unfixed \
  --format json \
  --output trivy-report.json

# Update vulnerability database before scanning
trivy image --download-db-only

# Scan with custom policies and exceptions
trivy config . \
  --config trivy-config.yaml \
  --ignorefile .trivyignore
```

**.trivyignore Format**:
```
# Temporary exception for testing environment (expires 2026-06-01)
# Approved by: security-team@example.com
# Reason: Dev environment only, acceptable risk
AVD-AWS-0123

# Permanent exception - business justification
# This security group rule is required for legacy integration
AVD-AWS-0456
```

**Checkov for Multi-Platform IaC**:
```bash
# Scan with compliance framework enforcement
checkov -d . \
  --framework terraform \
  --check CIS_AWS \
  --compact \
  --quiet

# Scan Kubernetes manifests
checkov -f k8s/deployment.yaml \
  --framework kubernetes \
  --skip-check CKV_K8S_8  # Document exceptions
```

### Hallucination Prevention and Validation

**Resource Type Validation Against Provider Schema**:
```hcl
# Always validate generated resource types against official schemas
# Use terraform providers schema -json to verify resource types exist

# Example validation check in CI/CD
terraform providers schema -json | jq -r '.provider_schemas[] | .resource_schemas | keys[]'
```

**Module Source Validation**:
```hcl
# ✅ GOOD: Use verified module sources
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.2"  # Pin to specific version
}

# ❌ BAD: Unverified or AI-generated module references
module "vpc" {
  source = "github.com/random-user/maybe-fake-vpc-module"  # Potential hallucination
}

# Maintain allowlist of approved module sources
variable "approved_module_sources" {
  type = list(string)
  default = [
    "registry.terraform.io/hashicorp/",
    "registry.terraform.io/terraform-aws-modules/",
    "github.com/your-org/"
  ]
}
```

**Policy-as-Code for Intent Validation (OPA/Rego)**:
```rego
# policies/security.rego
package terraform.security

deny[msg] {
  resource := input.resource.aws_security_group[_]
  rule := resource.ingress[_]
  rule.cidr_blocks[_] == "0.0.0.0/0"
  rule.from_port == 22

  msg := sprintf("Security group '%s' allows SSH from anywhere", [resource.name])
}

deny[msg] {
  resource := input.resource.aws_s3_bucket[_]
  not resource.versioning[0].enabled

  msg := sprintf("S3 bucket '%s' should have versioning enabled", [resource.name])
}
```

## Validation and Testing

### Pre-Commit Checks

**Required Validations**:
```bash
# Format check
terraform fmt -check -recursive

# Validation
terraform init -backend=false
terraform validate

# Security scanning with Trivy (replaces tfsec)
trivy config . --severity HIGH,CRITICAL --exit-code 1

# Native testing (Terraform 1.6+)
terraform test

# Documentation generation
terraform-docs markdown table . > README.md
```

### Workspace Strategy

**Environment Separation**:
```hcl
# Using workspaces for environment isolation
terraform {
  backend "s3" {
    bucket = "terraform-state"
    key    = "infrastructure.tfstate"
    region = "us-east-1"

    workspace_key_prefix = "env"
  }
}

# Access current workspace
locals {
  environment = terraform.workspace

  instance_counts = {
    dev     = 1
    staging = 2
    prod    = 3
  }

  instance_count = local.instance_counts[local.environment]
}
```

## Common Anti-Patterns to Avoid

❌ **Hardcoded Values**:
```hcl
# BAD
resource "aws_instance" "web" {
  ami           = "ami-12345678"  # Hardcoded AMI
  instance_type = "t3.micro"
  subnet_id     = "subnet-abc123"  # Hardcoded subnet
}
```

✅ **Use Variables and Data Sources**:
```hcl
# GOOD
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  subnet_id     = var.subnet_id
}
```

❌ **Over-Permissive Security**:
```hcl
# BAD
resource "aws_security_group_rule" "allow_all" {
  type        = "ingress"
  from_port   = 0
  to_port     = 65535
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]
}
```

✅ **Principle of Least Privilege**:
```hcl
# GOOD
resource "aws_security_group_rule" "https" {
  type        = "ingress"
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = var.allowed_cidr_blocks
}
```

❌ **No Cost Optimization**:
```hcl
# BAD - Always On-Demand at full price
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "m5.xlarge"  # Expensive, always On-Demand
}
```

✅ **Cost-Optimized with Spot and Right-Sizing**:
```hcl
# GOOD - Use Auto Scaling with Spot instances
resource "aws_autoscaling_group" "app" {
  mixed_instances_policy {
    instances_distribution {
      spot_allocation_strategy        = "price-capacity-optimized"
      on_demand_percentage_above_base = 20  # 80% Spot for 66-90% savings
    }
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.app.id
      }
      # Diversify instance types based on actual workload needs
      override { instance_type = "t3.large" }    # Right-sized based on metrics
      override { instance_type = "t3a.large" }
      override { instance_type = "m5.large" }
    }
  }
}
```

❌ **Long-Lived Credentials in CI/CD**:
```bash
# BAD - Stored in GitHub Secrets
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

✅ **OIDC Authentication**:
```yaml
# GOOD - GitHub Actions with OIDC
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/github-actions
      aws-region: us-east-1
```

## Environment Variable Pattern

**Local Development Setup**:
```bash
# .env.example (commit this)
AWS_REGION=us-east-1
TF_VAR_environment=dev
TF_VAR_project_name=myproject

# .env.local (DO NOT commit)
AWS_PROFILE=dev-account
TF_VAR_database_password=SecurePassword123!

# .env.production (DO NOT commit)
# Uses OIDC in CI/CD, no static credentials
TF_VAR_environment=prod
TF_VAR_instance_type=t3.large
```

## Usage Guidelines

### When to Use This Skill

- Generating Terraform module code from specifications
- Providing secure provider configuration patterns
- Offering variable and output structure templates
- Suggesting module composition strategies
- Recommending security best practices for IaC
- Validating Terraform code structure
- Implementing native testing with .tftest.hcl files
- Configuring cost optimization with Spot instances and right-sizing
- Setting up AI-assisted validation with Trivy/Checkov/OPA
- Implementing OIDC authentication for CI/CD
- Importing existing infrastructure with for_each import blocks

### When NOT to Use This Skill

- **Kubernetes manifests**: Use `kubernetes-native` skill for YAML manifests
- **Repository analysis**: Let `iac-analyzer` agent handle codebase exploration
- **Command execution**: This is a pattern reference, not an execution tool
- **Cloud-specific APIs**: Defer to cloud provider documentation for API details

## Integration with IaC Team

### Agent Handoffs

1. **iac-analyzer** → analyzes repository and creates dependency graph
2. **iac-generator** → uses this skill for Terraform patterns
3. **iac-generator** → uses `kubernetes-native` skill for K8s resources
4. **iac-validator** → validates security with Trivy/Checkov integration

### Output Format

When generating Terraform code:
1. Include all required files (main.tf, variables.tf, outputs.tf, versions.tf)
2. Add inline comments explaining key decisions
3. Include validation rules on variables
4. Mark sensitive outputs appropriately
5. Suggest security scanning commands (Trivy, Checkov)
6. Include native test examples in tests/ directory
7. Provide cost optimization recommendations where applicable
8. Configure OIDC authentication for CI/CD when applicable
9. Set terraform required_version >= 1.7.0 for modern features

## Cost Optimization Strategies

### Reserved Instances and Savings Plans

**Conservative Commitment Strategy**:
```hcl
# Start with 60-70% baseline coverage for predictable workloads
# Review quarterly and adjust as usage evolves

# Example: Reserved Instance data source
data "aws_ec2_instance_type_offerings" "available" {
  location_type = "availability-zone"

  filter {
    name   = "instance-type"
    values = ["t3.large", "t3a.large"]
  }
}

# Use Savings Plans for flexibility across instance families
# Combine with Spot for variable workloads
# Avoid 100% commitment before establishing usage baselines
```

### Resource Right-Sizing

**Continuous Analysis and Adjustment**:
```hcl
# Use AWS Compute Optimizer, Trusted Advisor, or GCP Recommender
# Target 40-70% CPU utilization
# Eliminate resources with <10% utilization

# Tag resources for cost tracking
resource "aws_instance" "app" {
  instance_type = var.instance_type

  tags = merge(local.common_tags, {
    CostCenter = var.cost_center
    Owner      = var.team_email
    ExpiryDate = var.expiry_date  # For lifecycle management
  })
}
```

## Additional Resources

For comprehensive examples and templates, see:
- `examples/` - Common module patterns for AWS, GCP, Azure
- `templates/` - Boilerplate code for quick module generation
- `tests/` - Native Terraform test examples with mocking

## Key Improvements in This Version

**Modern Terraform Features (1.7+)**:
- Native testing framework with .tftest.hcl files
- Mock providers for unit testing without cloud API calls
- Import blocks with for_each for bulk resource imports

**Security Enhancements**:
- Trivy integration (successor to tfsec as of 2026)
- Multi-tool security coverage (Trivy + Checkov)
- AI hallucination prevention patterns
- Policy-as-code validation with OPA/Rego

**Cost Optimization**:
- Spot instance patterns with interruption handling
- Right-sizing and auto-scaling best practices
- Reserved Instance and Savings Plan strategies
- Scheduled scaling for non-production environments

**CI/CD Integration**:
- OIDC authentication examples for GitHub Actions
- Two-phase validation pipeline (technical + intent)
- Security scanning with appropriate failure thresholds

---

**Token Optimization**: This skill uses progressive disclosure. Core patterns are inline, detailed examples available in supporting directories.
