---
name: aws-cli
description: >
  Amazon Web Services CLI operations and infrastructure patterns for AWS resource management.

  Activate when user mentions: aws, AWS, Amazon Web Services, EC2, EKS, ECS, S3, RDS,
  Lambda, CloudFormation, CloudWatch, IAM roles, IAM policies, aws cli commands,
  AWS deployment, AWS infrastructure, ECR, ALB, NLB, VPC, Route53, DynamoDB, SQS,
  SNS, EventBridge, Systems Manager, Secrets Manager, CloudTrail, AWS Organizations.

  Use for: AWS resource provisioning, aws cli commands, AWS service configuration,
  infrastructure-as-code for AWS, AWS best practices, OIDC authentication, IAM roles
  for service accounts (IRSA), AWS security patterns, multi-region deployments,
  high availability configurations, cost optimization, disaster recovery, Spot instances.

  Do NOT use for: GCP-specific resources, Azure-specific resources, Kubernetes manifests
  (use kubernetes-native skill), generic shell scripting unrelated to AWS, Terraform/Pulumi
  DSL syntax (use terraform-modules or pulumi-cdk skills for IaC DSLs).
---

# aws CLI Operations Skill

## Overview

This skill provides comprehensive Amazon Web Services CLI patterns, commands, and infrastructure-as-code practices for AWS resource management. It enables autonomous activation when AWS-related tasks are detected and supplies battle-tested patterns for secure, production-ready AWS deployments with emphasis on cost optimization, high availability, and GitOps integration.

## Core Capabilities

### 1. AWS Resource Provisioning
- **EC2 (Elastic Compute Cloud)**: Instances, Auto Scaling groups, launch templates, Spot instances, placement groups
- **EKS (Elastic Kubernetes Service)**: Cluster creation, managed node groups, Fargate profiles, IRSA, addons
- **ECS (Elastic Container Service)**: Fargate and EC2 launch types, task definitions, services, capacity providers
- **S3 (Simple Storage Service)**: Buckets, lifecycle policies, versioning, replication, encryption, access points
- **RDS (Relational Database Service)**: Multi-AZ instances, read replicas, automated backups, snapshot management
- **VPC & Networking**: VPCs, subnets, security groups, NAT gateways, VPC endpoints, Transit Gateway, PrivateLink
- **ECR (Elastic Container Registry)**: Repositories, image scanning, lifecycle policies, replication

### 2. Identity & Access Management
- **IAM Roles**: Service roles, instance profiles, cross-account access, permission boundaries
- **IAM Policies**: Managed policies, inline policies, resource-based policies, session policies, SCPs
- **IRSA (IAM Roles for Service Accounts)**: EKS pod-level IAM with OIDC provider integration
- **OIDC for CI/CD**: GitHub Actions, GitLab CI keyless authentication with federated identity
- **STS (Security Token Service)**: AssumeRole, temporary credentials, session tags, MFA enforcement

### 3. Security Best Practices
- **No long-lived credentials**: Prefer OIDC/IRSA over IAM access keys
- **Least privilege**: Minimal IAM permissions with permission boundaries and SCPs
- **Secret management**: Secrets Manager and Parameter Store integration, no hardcoded credentials
- **Audit logging**: CloudTrail configuration with S3/CloudWatch Logs integration
- **Network security**: Security groups, NACLs, VPC endpoints, PrivateLink, WAF, Shield
- **Supply chain security**: ECR image scanning (Trivy, Clair), Binary Authorization patterns
- **Encryption**: KMS encryption at rest, TLS in transit, envelope encryption patterns

### 4. Infrastructure Validation
- **Dry-run support**: EC2 dry-run mode for validation before execution
- **Policy validation**: IAM policy simulator, Access Analyzer, CloudFormation linting
- **Cost estimation**: AWS Pricing Calculator, Cost Explorer forecasting
- **Security scanning**: Trivy for IaC (successor to tfsec), Checkov for multi-platform validation
- **Config compliance**: AWS Config rules, conformance packs, remediation automation

### 5. Cost Optimization
- **Spot Instances**: Price-capacity-optimized allocation, interruption handling, 66-90% savings
- **Right-sizing**: Compute Optimizer recommendations, target 40-70% CPU utilization
- **Savings Plans**: Compute and EC2 Savings Plans for 30-75% discounts
- **Reserved Instances**: Strategic commitments for stable workloads, 1-year/3-year terms
- **Storage optimization**: S3 Intelligent-Tiering, lifecycle policies (IA, Glacier, Deep Archive)
- **Auto Scaling**: Dynamic scaling policies based on CloudWatch metrics
- **Cost monitoring**: Budgets, Cost Anomaly Detection, detailed billing reports

### 6. High Availability & Disaster Recovery
- **Multi-AZ deployments**: RDS Multi-AZ, ELB cross-zone balancing, Auto Scaling across AZs
- **Multi-region architectures**: Route53 failover, S3 Cross-Region Replication, Global Accelerator
- **Automated backups**: RDS automated backups, EBS snapshots, S3 versioning
- **Health checks**: Route53 health checks, ALB/NLB target health monitoring
- **Failover strategies**: Active-active, active-passive patterns with automated DNS failover
- **Point-in-time recovery**: RDS PITR, DynamoDB PITR, S3 object versioning

## Usage Guidelines

### When to Activate

This skill activates autonomously when detecting:

1. **Direct AWS mentions**: "deploy to AWS", "create an EKS cluster", "setup Lambda function"
2. **AWS service names**: EC2, S3, RDS, Lambda, DynamoDB, ECS, EKS, CloudFormation, CloudWatch
3. **aws commands**: Any reference to `aws` CLI tool or AWS SDK operations
4. **AWS infrastructure patterns**: "AWS load balancer", "VPC peering", "security groups", "IAM roles"
5. **AWS authentication**: "IAM role", "IRSA", "OIDC for AWS", "AssumeRole"
6. **Cost optimization**: "reduce AWS costs", "Spot instances", "right-sizing", "Savings Plans"
7. **Multi-region/HA**: "high availability on AWS", "disaster recovery", "multi-region deployment"

### When NOT to Use

- **GCP resources**: Defer to GCP-specific skills (gcloud-cli, gcp-gke)
- **Azure resources**: Defer to Azure-specific skills
- **Kubernetes manifests**: Use `kubernetes-native` skill for YAML generation
- **Generic scripting**: Non-AWS shell operations
- **Terraform/Pulumi DSL**: Use `terraform-modules` or `pulumi-cdk` skills for IaC language syntax
- **Helm charts**: Use `helm-charts` skill for Helm-specific templating

### Integration with IaC Generator Agent

When the `iac-generator` agent invokes this skill:

**Skill receives context:**
```yaml
# Provided by iac-generator via skill invocation metadata
analysis_output:
  cloud_provider: aws
  services: [web-app, api-backend, workers]
  compute_target: eks  # or ecs, ec2
  region: us-east-1
  ha_required: true
  cost_sensitivity: high
  security_requirements: [oidc_auth, no_access_keys, secrets_manager]
```

**Skill returns patterns:**
```yaml
# Output provided back to iac-generator
aws_commands:
  - phase: "setup"
    commands: [cluster creation, networking, IAM roles, OIDC provider]
  - phase: "deploy"
    commands: [ECR push, service deploy, ALB configuration]
security_validations:
  - aws ec2 describe-security-groups --filters "Name=ip-permission.cidr,Values=0.0.0.0/0"
  - aws iam get-account-authorization-details --filter Role
cost_warnings:
  - "EKS cluster management: $0.10/hour per cluster"
  - "Consider Fargate for serverless compute (pay-per-pod)"
  - "Use Spot instances for 66-90% cost savings on worker nodes"
```

**Handoff protocol:**
1. iac-generator invokes aws-cli skill with context
2. Skill generates context-appropriate commands (not generic templates)
3. Skill includes validation steps and security checks
4. iac-generator wraps commands in CI/CD pipeline (github-actions/gitlab-ci skills)

## Command Patterns

### Authentication & Configuration

```bash
# OIDC-based authentication (preferred for CI/CD)
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME \
  --role-session-name SESSION_NAME \
  --web-identity-token $OIDC_TOKEN \
  --duration-seconds 3600

# AssumeRole for cross-account access (no long-lived keys)
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT:role/ROLE_NAME \
  --role-session-name SESSION_NAME \
  --duration-seconds 3600 \
  --external-id EXTERNAL_ID

# Set default region and output format
aws configure set region us-east-1
aws configure set output json

# Use named profiles for multi-account management
aws configure --profile production set region us-east-1
aws --profile production s3 ls

# Verify current identity
aws sts get-caller-identity
```

### IAM Role Management (Secure Patterns)

```bash
# Create IAM role with trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name MyEC2Role \
  --assume-role-policy-document file://trust-policy.json \
  --description "Role for EC2 instances with S3 access" \
  --tags Key=ManagedBy,Value=iac-team Key=Environment,Value=production

# Attach managed policy (least privilege)
aws iam attach-role-policy \
  --role-name MyEC2Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Create inline policy with specific permissions
cat > inline-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name MyEC2Role \
  --policy-name S3SpecificAccess \
  --policy-document file://inline-policy.json

# Create instance profile (required for EC2)
aws iam create-instance-profile --instance-profile-name MyEC2InstanceProfile
aws iam add-role-to-instance-profile \
  --instance-profile-name MyEC2InstanceProfile \
  --role-name MyEC2Role

# Validate IAM policy before deployment
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/MyEC2Role \
  --action-names s3:GetObject s3:PutObject \
  --resource-arns arn:aws:s3:::my-bucket/*

# AVOID: Creating IAM access keys (security risk)
# NEVER: aws iam create-access-key --user-name USERNAME
```

### OIDC for GitHub Actions (No Long-Lived Keys)

```bash
# 1. Create OIDC identity provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# 2. Create IAM role with OIDC trust policy
cat > github-actions-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:ORG/REPO:ref:refs/heads/main"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GitHubActionsDeployRole \
  --assume-role-policy-document file://github-actions-trust-policy.json \
  --description "Role for GitHub Actions OIDC deployment" \
  --tags Key=ManagedBy,Value=iac-team

# 3. Attach deployment permissions
aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSClusterPolicy
```

**GitHub Actions Workflow Integration:**
```yaml
# .github/workflows/deploy.yaml
jobs:
  deploy:
    permissions:
      id-token: write  # Required for OIDC
      contents: read

    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsDeployRole
          aws-region: us-east-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Push image to ECR
        run: |
          docker tag app:${{ github.sha }} ${{ steps.login-ecr.outputs.registry }}/app:${{ github.sha }}
          docker push ${{ steps.login-ecr.outputs.registry }}/app:${{ github.sha }}
```

### OIDC for GitLab CI (Keyless Authentication)

```bash
# 1. Create OIDC identity provider for GitLab
aws iam create-open-id-connect-provider \
  --url https://gitlab.com \
  --client-id-list https://gitlab.com \
  --thumbprint-list 7e04dce4dbe10b0c05afe0c5c84c81fb96a9b9e0

# 2. Create IAM role with GitLab OIDC trust policy
cat > gitlab-ci-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/gitlab.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.com:aud": "https://gitlab.com"
        },
        "StringLike": {
          "gitlab.com:sub": "project_path:GROUP/PROJECT:ref_type:branch:ref:main"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GitLabCIDeployRole \
  --assume-role-policy-document file://gitlab-ci-trust-policy.json \
  --description "Role for GitLab CI OIDC deployment"
```

### EKS Cluster Management

```bash
# Create EKS cluster with OIDC provider (for IRSA)
aws eks create-cluster \
  --name production-cluster \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/EKSClusterRole \
  --resources-vpc-config subnetIds=subnet-xxx,subnet-yyy,subnet-zzz,securityGroupIds=sg-xxx \
  --kubernetes-version 1.31 \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}' \
  --tags ManagedBy=iac-team,Environment=production

# Wait for cluster to be active
aws eks wait cluster-active --name production-cluster

# Create OIDC identity provider for cluster (enables IRSA)
OIDC_PROVIDER=$(aws eks describe-cluster --name production-cluster --query "cluster.identity.oidc.issuer" --output text | sed 's|https://||')
OIDC_FINGERPRINT=$(echo | openssl s_client -servername oidc.eks.us-east-1.amazonaws.com -connect oidc.eks.us-east-1.amazonaws.com:443 2>&- | openssl x509 -fingerprint -noout | sed 's/://g' | cut -d'=' -f2)

aws iam create-open-id-connect-provider \
  --url https://$OIDC_PROVIDER \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list $OIDC_FINGERPRINT

# Create managed node group with Spot instances (cost optimization)
aws eks create-nodegroup \
  --cluster-name production-cluster \
  --nodegroup-name spot-workers \
  --node-role arn:aws:iam::ACCOUNT_ID:role/EKSNodeRole \
  --subnets subnet-xxx subnet-yyy subnet-zzz \
  --capacity-type SPOT \
  --instance-types t3.medium t3a.medium t3.large \
  --scaling-config minSize=2,maxSize=10,desiredSize=3 \
  --disk-size 50 \
  --labels workload=stateless,cost=optimized \
  --tags ManagedBy=iac-team,Environment=production

# Create on-demand node group for stable workloads
aws eks create-nodegroup \
  --cluster-name production-cluster \
  --nodegroup-name on-demand-workers \
  --node-role arn:aws:iam::ACCOUNT_ID:role/EKSNodeRole \
  --subnets subnet-xxx subnet-yyy subnet-zzz \
  --capacity-type ON_DEMAND \
  --instance-types t3.medium \
  --scaling-config minSize=1,maxSize=5,desiredSize=2 \
  --labels workload=stateful,cost=standard

# Create Fargate profile (serverless, pay-per-pod)
aws eks create-fargate-profile \
  --cluster-name production-cluster \
  --fargate-profile-name app-profile \
  --pod-execution-role-arn arn:aws:iam::ACCOUNT_ID:role/EKSFargateRole \
  --selectors namespace=app,labels={app=web} \
  --subnets subnet-xxx subnet-yyy

# Install EKS addons (VPC CNI, CoreDNS, kube-proxy)
aws eks create-addon \
  --cluster-name production-cluster \
  --addon-name vpc-cni \
  --addon-version v1.18.0-eksbuild.1 \
  --resolve-conflicts OVERWRITE

aws eks create-addon \
  --cluster-name production-cluster \
  --addon-name kube-proxy \
  --addon-version v1.31.0-eksbuild.1

aws eks create-addon \
  --cluster-name production-cluster \
  --addon-name coredns \
  --addon-version v1.11.3-eksbuild.1

# Update kubeconfig for kubectl access
aws eks update-kubeconfig \
  --name production-cluster \
  --region us-east-1 \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/EKSAdminRole

# IRSA: Create IAM role for service account (pod-level permissions)
cat > irsa-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/$OIDC_PROVIDER"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "$OIDC_PROVIDER:sub": "system:serviceaccount:app:s3-access-sa",
          "$OIDC_PROVIDER:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name AppS3AccessRole \
  --assume-role-policy-document file://irsa-trust-policy.json \
  --description "IRSA role for app pods accessing S3"

aws iam attach-role-policy \
  --role-name AppS3AccessRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

**Kubernetes ServiceAccount for IRSA:**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: s3-access-sa
  namespace: app
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/AppS3AccessRole
---
apiVersion: v1
kind: Pod
metadata:
  name: app
  namespace: app
spec:
  serviceAccountName: s3-access-sa
  containers:
  - name: app
    image: app:latest
    # Pod automatically gets AWS credentials via IRSA
```

### EC2 Instances with Spot and Auto Scaling

```bash
# Create launch template with Spot pricing and user data
cat > user-data.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent
systemctl enable amazon-cloudwatch-agent
EOF

aws ec2 create-launch-template \
  --launch-template-name web-server-template \
  --version-description "v1 with Spot and CloudWatch" \
  --launch-template-data '{
    "ImageId": "ami-0c55b159cbfafe1f0",
    "InstanceType": "t3.medium",
    "IamInstanceProfile": {"Name": "MyEC2InstanceProfile"},
    "SecurityGroupIds": ["sg-xxx"],
    "UserData": "'$(base64 -w 0 user-data.sh)'",
    "TagSpecifications": [{
      "ResourceType": "instance",
      "Tags": [
        {"Key": "Name", "Value": "web-server"},
        {"Key": "ManagedBy", "Value": "iac-team"}
      ]
    }],
    "MetadataOptions": {
      "HttpTokens": "required",
      "HttpPutResponseHopLimit": 1
    },
    "Monitoring": {"Enabled": true}
  }'

# Create Auto Scaling group with Spot instances (price-capacity-optimized)
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name web-server-asg \
  --mixed-instances-policy '{
    "LaunchTemplate": {
      "LaunchTemplateSpecification": {
        "LaunchTemplateName": "web-server-template",
        "Version": "$Latest"
      },
      "Overrides": [
        {"InstanceType": "t3.medium"},
        {"InstanceType": "t3a.medium"},
        {"InstanceType": "t3.large"},
        {"InstanceType": "t3a.large"}
      ]
    },
    "InstancesDistribution": {
      "OnDemandPercentageAboveBaseCapacity": 20,
      "SpotAllocationStrategy": "price-capacity-optimized",
      "SpotInstancePools": 4
    }
  }' \
  --min-size 2 \
  --max-size 10 \
  --desired-capacity 4 \
  --vpc-zone-identifier "subnet-xxx,subnet-yyy,subnet-zzz" \
  --health-check-type ELB \
  --health-check-grace-period 300 \
  --tags Key=Name,Value=web-server,PropagateAtLaunch=true Key=ManagedBy,Value=iac-team,PropagateAtLaunch=true

# Create target tracking scaling policy (maintain 50% CPU)
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name web-server-asg \
  --policy-name target-cpu-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    },
    "TargetValue": 50.0
  }'

# Handle Spot instance interruptions with EventBridge
aws events put-rule \
  --name SpotInterruptionWarning \
  --event-pattern '{
    "source": ["aws.ec2"],
    "detail-type": ["EC2 Spot Instance Interruption Warning"]
  }'

aws events put-targets \
  --rule SpotInterruptionWarning \
  --targets Id=1,Arn=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:HandleSpotInterruption
```

### ECR (Elastic Container Registry)

```bash
# Create ECR repository with image scanning
aws ecr create-repository \
  --repository-name app/backend \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 \
  --image-tag-mutability IMMUTABLE \
  --tags Key=ManagedBy,Value=iac-team

# Set lifecycle policy (delete old images)
cat > lifecycle-policy.json <<EOF
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 10 images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
EOF

aws ecr put-lifecycle-policy \
  --repository-name app/backend \
  --lifecycle-policy-text file://lifecycle-policy.json

# Set repository policy (grant cross-account pull access)
cat > repository-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::OTHER_ACCOUNT:root"
      },
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ]
    }
  ]
}
EOF

aws ecr set-repository-policy \
  --repository-name app/backend \
  --policy-text file://repository-policy.json

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Push image to ECR
docker tag app:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app/backend:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app/backend:latest

# Describe image scan findings
aws ecr describe-image-scan-findings \
  --repository-name app/backend \
  --image-id imageTag=latest \
  --query 'imageScanFindings.findings[?severity==`CRITICAL` || severity==`HIGH`]'
```

### S3 Buckets & Storage Optimization

```bash
# Create S3 bucket with versioning and encryption
aws s3api create-bucket \
  --bucket my-app-data \
  --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1

aws s3api put-bucket-versioning \
  --bucket my-app-data \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket my-app-data \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
      },
      "BucketKeyEnabled": true
    }]
  }'

# Block public access (security best practice)
aws s3api put-public-access-block \
  --bucket my-app-data \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Enable S3 Intelligent-Tiering (automatic cost optimization)
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket my-app-data \
  --id IntelligentTieringConfig \
  --intelligent-tiering-configuration '{
    "Id": "IntelligentTieringConfig",
    "Status": "Enabled",
    "Tierings": [
      {
        "Days": 90,
        "AccessTier": "ARCHIVE_ACCESS"
      },
      {
        "Days": 180,
        "AccessTier": "DEEP_ARCHIVE_ACCESS"
      }
    ]
  }'

# Set lifecycle policy (transition to cheaper storage classes)
cat > lifecycle-policy.json <<EOF
{
  "Rules": [
    {
      "Id": "TransitionToIA",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER_IR"
        },
        {
          "Days": 365,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ],
      "NoncurrentVersionTransitions": [
        {
          "NoncurrentDays": 30,
          "StorageClass": "GLACIER_IR"
        }
      ],
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 90
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket my-app-data \
  --lifecycle-configuration file://lifecycle-policy.json

# Enable Cross-Region Replication (disaster recovery)
cat > replication-config.json <<EOF
{
  "Role": "arn:aws:iam::ACCOUNT_ID:role/S3ReplicationRole",
  "Rules": [
    {
      "Status": "Enabled",
      "Priority": 1,
      "DeleteMarkerReplication": { "Status": "Enabled" },
      "Filter": {},
      "Destination": {
        "Bucket": "arn:aws:s3:::my-app-data-replica",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": { "Minutes": 15 }
        },
        "Metrics": {
          "Status": "Enabled",
          "EventThreshold": { "Minutes": 15 }
        }
      }
    }
  ]
}
EOF

aws s3api put-bucket-replication \
  --bucket my-app-data \
  --replication-configuration file://replication-config.json
```

### RDS (Relational Database Service)

```bash
# Create RDS PostgreSQL instance with Multi-AZ and encryption
aws rds create-db-instance \
  --db-instance-identifier production-postgres \
  --db-instance-class db.r6g.large \
  --engine postgres \
  --engine-version 16.1 \
  --master-username dbadmin \
  --master-user-password $(aws secretsmanager get-secret-value --secret-id db-master-password --query SecretString --output text) \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID \
  --multi-az \
  --db-subnet-group-name my-db-subnet-group \
  --vpc-security-group-ids sg-xxx \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00" \
  --enable-cloudwatch-logs-exports postgresql \
  --auto-minor-version-upgrade \
  --deletion-protection \
  --copy-tags-to-snapshot \
  --tags Key=Name,Value=production-postgres Key=ManagedBy,Value=iac-team

# Enable automated backups with point-in-time recovery
aws rds modify-db-instance \
  --db-instance-identifier production-postgres \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"

# Create read replica (for read scaling and HA)
aws rds create-db-instance-read-replica \
  --db-instance-identifier production-postgres-replica \
  --source-db-instance-identifier production-postgres \
  --db-instance-class db.r6g.large \
  --availability-zone us-east-1b \
  --publicly-accessible false

# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier production-postgres \
  --db-snapshot-identifier pre-upgrade-snapshot-$(date +%Y%m%d)

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier restored-postgres \
  --db-snapshot-identifier pre-upgrade-snapshot-20260203 \
  --db-instance-class db.r6g.large \
  --multi-az

# Point-in-time restore
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier production-postgres \
  --target-db-instance-identifier production-postgres-pitr \
  --restore-time 2026-02-03T12:00:00Z
```

### Secrets Manager (No Hardcoded Secrets)

```bash
# Store secret in Secrets Manager
aws secretsmanager create-secret \
  --name app/database/password \
  --description "Database password for production app" \
  --secret-string '{"username":"dbadmin","password":"StrongPassword123!"}' \
  --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID \
  --tags Key=ManagedBy,Value=iac-team Key=Environment,Value=production

# Rotate secret (automatic rotation)
aws secretsmanager rotate-secret \
  --secret-id app/database/password \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:ACCOUNT_ID:function:SecretsManagerRotation \
  --rotation-rules AutomaticallyAfterDays=30

# Retrieve secret value
aws secretsmanager get-secret-value \
  --secret-id app/database/password \
  --query SecretString \
  --output text | jq -r '.password'

# Grant access to IAM role (least privilege)
aws secretsmanager put-resource-policy \
  --secret-id app/database/password \
  --resource-policy '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::ACCOUNT_ID:role/AppRole"
        },
        "Action": "secretsmanager:GetSecretValue",
        "Resource": "*"
      }
    ]
  }'

# Access secret from ECS task
# (Use secretsmanager reference in task definition)
cat > task-definition.json <<EOF
{
  "family": "app",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/AppTaskRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app:latest",
      "secrets": [
        {
          "name": "DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:app/database/password:password::"
        }
      ]
    }
  ]
}
EOF
```

### Systems Manager Parameter Store

```bash
# Store parameter (alternative to Secrets Manager for non-sensitive config)
aws ssm put-parameter \
  --name /app/config/api-endpoint \
  --value "https://api.example.com" \
  --type String \
  --description "API endpoint for app" \
  --tags Key=ManagedBy,Value=iac-team

# Store secure parameter (encrypted)
aws ssm put-parameter \
  --name /app/config/api-key \
  --value "sk-1234567890abcdef" \
  --type SecureString \
  --key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID \
  --description "API key for external service"

# Retrieve parameter
aws ssm get-parameter \
  --name /app/config/api-endpoint \
  --query Parameter.Value \
  --output text

# Retrieve secure parameter (decrypted)
aws ssm get-parameter \
  --name /app/config/api-key \
  --with-decryption \
  --query Parameter.Value \
  --output text

# Get parameters by path
aws ssm get-parameters-by-path \
  --path /app/config \
  --recursive \
  --with-decryption
```

## Security Patterns

### Environment Variable Pattern (No Hardcoded Secrets)

**Project Structure:**
```
.env.example          # Template (commit to repo)
.env.local            # Local development (in .gitignore)
.env.production       # Production (Secrets Manager or CI/CD secrets)
.gitignore            # MUST include .env.local, .env.production
```

**Example .env.example:**
```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# ECR Configuration
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com

# NEVER commit actual secrets:
# DB_PASSWORD=supersecret
# API_KEY=sk-1234567890abcdef
# Use Secrets Manager references instead: app/database/password
```

**Production deployment pattern:**
```bash
# Store secrets in Secrets Manager (one-time setup)
while IFS='=' read -r key value; do
  [ -z "$key" ] || [ "${key:0:1}" = "#" ] && continue
  aws secretsmanager create-secret \
    --name "app/config/$key" \
    --secret-string "$value" \
    --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID || true
done < .env.production

# Reference secrets in ECS task definition
# (See task-definition.json in Secrets Manager section above)

# Reference secrets in EKS using External Secrets Operator
# (See kubernetes-native skill for ESO CRD configuration)
```

## Validation & Testing

### Dry-Run Operations

```bash
# EC2 dry-run (validate without creating resources)
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.micro \
  --dry-run

# IAM policy simulator (test permissions before deployment)
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/MyRole \
  --action-names s3:GetObject s3:PutObject \
  --resource-arns arn:aws:s3:::my-bucket/*

# CloudFormation change set (preview changes)
aws cloudformation create-change-set \
  --stack-name my-stack \
  --change-set-name preview-changes \
  --template-body file://template.yaml \
  --parameters file://parameters.json

aws cloudformation describe-change-set \
  --stack-name my-stack \
  --change-set-name preview-changes
```

### Security Scanning with Trivy (Successor to tfsec)

```bash
# Install Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Scan Terraform IaC for misconfigurations
trivy config . \
  --severity CRITICAL,HIGH \
  --exit-code 1 \
  --ignore-unfixed

# Scan container image for vulnerabilities
trivy image \
  --severity CRITICAL,HIGH \
  --exit-code 1 \
  --ignore-unfixed \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app:latest

# Generate SBOM (CycloneDX format)
trivy image \
  --format cyclonedx \
  --output sbom.json \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app:latest

# Scan with custom .trivyignore file
cat > .trivyignore <<EOF
# CVE-2024-1234 - False positive, not exploitable in our context
# Reviewed: 2026-02-03, Approved by: security-team
# Expires: 2026-05-03
CVE-2024-1234
EOF

trivy config . --ignore-file .trivyignore
```

### Pre-Deployment Validation Checklist

```bash
# 1. Validate IAM permissions
aws sts get-caller-identity
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/DeployRole \
  --action-names eks:CreateCluster ec2:RunInstances \
  --resource-arns "*"

# 2. Check service quotas
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-1216C47A  # Running On-Demand Standard instances

# 3. Verify VPC configuration
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=production-vpc"
aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-xxx"

# 4. Test security group rules
aws ec2 describe-security-groups \
  --filters "Name=ip-permission.cidr,Values=0.0.0.0/0" \
  --query 'SecurityGroups[?IpPermissions[?FromPort!=`443` && FromPort!=`80`]]'

# 5. Verify encryption at rest
aws rds describe-db-instances \
  --query 'DBInstances[?StorageEncrypted==`false`].DBInstanceIdentifier'

aws s3api get-bucket-encryption --bucket my-bucket

# 6. Check compliance with AWS Config rules
aws configservice describe-compliance-by-config-rule \
  --compliance-types NON_COMPLIANT
```

## Cost Optimization

### Right-Sizing with Compute Optimizer

```bash
# Get EC2 instance recommendations
aws compute-optimizer get-ec2-instance-recommendations \
  --instance-arns arn:aws:ec2:us-east-1:ACCOUNT_ID:instance/i-xxx \
  --query 'instanceRecommendations[0].recommendationOptions[0].[instanceType,projectedUtilizationMetrics]'

# Get Auto Scaling group recommendations
aws compute-optimizer get-auto-scaling-group-recommendations \
  --auto-scaling-group-arns arn:aws:autoscaling:us-east-1:ACCOUNT_ID:autoScalingGroup:xxx:autoScalingGroupName/my-asg

# Get EBS volume recommendations
aws compute-optimizer get-ebs-volume-recommendations \
  --volume-arns arn:aws:ec2:us-east-1:ACCOUNT_ID:volume/vol-xxx
```

### Savings Plans and Reserved Instances

```bash
# Purchase Compute Savings Plan (flexible, 30-75% savings)
aws savingsplans create-savings-plan \
  --savings-plan-offering-id OFFERING_ID \
  --commitment 100.0 \
  --upfront-payment-amount 0.0 \
  --purchase-time $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --tags Key=ManagedBy,Value=iac-team

# List Savings Plans
aws savingsplans describe-savings-plans

# Purchase Reserved Instance (1-year No Upfront)
aws ec2 purchase-reserved-instances-offering \
  --reserved-instances-offering-id OFFERING_ID \
  --instance-count 2

# List Reserved Instances and utilization
aws ec2 describe-reserved-instances
aws ce get-reservation-utilization \
  --time-period Start=2026-01-01,End=2026-02-01 \
  --granularity MONTHLY
```

### Cost Monitoring and Budgets

```bash
# Create budget with alerts
aws budgets create-budget \
  --account-id ACCOUNT_ID \
  --budget '{
    "BudgetName": "Monthly-Production-Budget",
    "BudgetLimit": {
      "Amount": "10000",
      "Unit": "USD"
    },
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST",
    "CostFilters": {
      "TagKeyValue": ["user:Environment$production"]
    }
  }' \
  --notifications-with-subscribers '[
    {
      "Notification": {
        "NotificationType": "ACTUAL",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": 80,
        "ThresholdType": "PERCENTAGE"
      },
      "Subscribers": [
        {
          "SubscriptionType": "EMAIL",
          "Address": "devops@example.com"
        }
      ]
    }
  ]'

# Get cost and usage
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-02-01 \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Detect cost anomalies
aws ce get-anomalies \
  --date-interval Start=2026-01-01,End=2026-02-01 \
  --max-results 10
```

### Identifying Idle Resources

```bash
# Find unattached EBS volumes (wasting storage costs)
aws ec2 describe-volumes \
  --filters "Name=status,Values=available" \
  --query 'Volumes[].{ID:VolumeId,Size:Size,Created:CreateTime}' \
  --output table

# Find unattached Elastic IPs (wasting IP costs)
aws ec2 describe-addresses \
  --filters "Name=domain,Values=vpc" \
  --query 'Addresses[?AssociationId==null].{IP:PublicIp,AllocationId:AllocationId}' \
  --output table

# Find idle load balancers (no active targets)
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[].{Name:LoadBalancerName,ARN:LoadBalancerArn}' | \
  jq -r '.[] | .ARN' | while read lb_arn; do
    target_groups=$(aws elbv2 describe-target-groups --load-balancer-arn "$lb_arn" --query 'TargetGroups[].TargetGroupArn' --output text)
    for tg in $target_groups; do
      healthy=$(aws elbv2 describe-target-health --target-group-arn "$tg" --query 'TargetHealthDescriptions[?TargetHealth.State==`healthy`]' --output text)
      [ -z "$healthy" ] && echo "Idle LB: $lb_arn (no healthy targets)"
    done
  done

# Find stopped EC2 instances (paying for storage)
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=stopped" \
  --query 'Reservations[].Instances[].{ID:InstanceId,Type:InstanceType,Stopped:LaunchTime}' \
  --output table
```

## High Availability & Disaster Recovery

### Multi-AZ Application Load Balancer

```bash
# Create Application Load Balancer (cross-zone enabled)
aws elbv2 create-load-balancer \
  --name production-alb \
  --subnets subnet-xxx subnet-yyy subnet-zzz \
  --security-groups sg-xxx \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4 \
  --tags Key=Name,Value=production-alb Key=ManagedBy,Value=iac-team

# Create target group
aws elbv2 create-target-group \
  --name app-target-group \
  --protocol HTTP \
  --port 80 \
  --vpc-id vpc-xxx \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --target-type ip

# Create listener with HTTPS (TLS termination)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:ACCOUNT_ID:loadbalancer/app/production-alb/xxx \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/xxx \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT_ID:targetgroup/app-target-group/xxx

# Enable access logs
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:ACCOUNT_ID:loadbalancer/app/production-alb/xxx \
  --attributes \
    Key=access_logs.s3.enabled,Value=true \
    Key=access_logs.s3.bucket,Value=my-alb-logs \
    Key=access_logs.s3.prefix,Value=production-alb \
    Key=deletion_protection.enabled,Value=true
```

### Route53 Health Checks and Failover

```bash
# Create health check
aws route53 create-health-check \
  --caller-reference $(date +%s) \
  --health-check-config \
    Type=HTTPS,ResourcePath=/health,FullyQualifiedDomainName=api.example.com,Port=443,RequestInterval=30,FailureThreshold=3

# Create failover routing (primary and secondary)
cat > change-batch.json <<EOF
{
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "SetIdentifier": "Primary",
        "Failover": "PRIMARY",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "production-alb-xxx.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        },
        "HealthCheckId": "HEALTH_CHECK_ID"
      }
    },
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "SetIdentifier": "Secondary",
        "Failover": "SECONDARY",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "secondary-alb-xxx.us-west-2.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789ABC \
  --change-batch file://change-batch.json
```

### Disaster Recovery Runbook

```bash
# 1. Restore RDS from snapshot
aws rds describe-db-snapshots \
  --db-instance-identifier production-postgres \
  --query 'DBSnapshots[0].DBSnapshotIdentifier' \
  --output text

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier production-postgres-restored \
  --db-snapshot-identifier SNAPSHOT_ID \
  --db-instance-class db.r6g.large \
  --multi-az

# 2. Restore EBS volume from snapshot
aws ec2 describe-snapshots \
  --owner-ids self \
  --filters "Name=tag:Name,Values=production-data" \
  --query 'Snapshots[0].SnapshotId' \
  --output text

aws ec2 create-volume \
  --snapshot-id SNAPSHOT_ID \
  --availability-zone us-east-1a \
  --volume-type gp3 \
  --encrypted

# 3. Restore S3 objects from versioning
aws s3api list-object-versions \
  --bucket my-bucket \
  --prefix critical-data/ \
  --query 'Versions[?IsLatest==`false`]'

aws s3api copy-object \
  --bucket my-bucket \
  --copy-source my-bucket/critical-data/file.txt?versionId=VERSION_ID \
  --key critical-data/file.txt

# 4. Promote RDS read replica to standalone
aws rds promote-read-replica \
  --db-instance-identifier production-postgres-replica

# 5. Update Route53 to failover region
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789ABC \
  --change-batch file://failover-to-secondary.json
```

## Integration with IaC Generator

This skill is referenced by the `iac-generator` agent when:

1. **AWS provider detected** in analysis phase (via `iac-analyzer` output)
2. **User requests AWS resources** explicitly ("deploy to AWS", "create EKS cluster")
3. **IRSA configuration** needed for EKS pod-level IAM permissions
4. **OIDC authentication** setup for GitHub Actions/GitLab CI pipelines
5. **Cost optimization** required (Spot instances, Savings Plans, right-sizing)
6. **Multi-AZ/Multi-region HA** deployment requested

The iac-generator will:
- Pull aws cli command patterns from this skill based on analysis context
- Apply security constraints (no access keys, OIDC preferred, Secrets Manager usage)
- Generate CI/CD pipeline scripts that pass security scanning (Trivy)
- Include dry-run validation steps and pre-deployment checklists
- Add cost optimization recommendations (Spot, Savings Plans, right-sizing)
- Integrate monitoring and alerting setup commands (CloudWatch, EventBridge)
- Include disaster recovery procedures

**Example handoff flow:**
```
User: "Deploy my Python app to AWS with autoscaling"
  ↓
iac-analyzer: Detects Python Flask app, analyzes dependencies
  ↓
iac-generator: Invokes aws-cli skill with context:
  {
    compute_target: "ecs-fargate",
    language: "python",
    framework: "flask",
    autoscaling: true,
    region: "us-east-1",
    security: ["oidc_auth", "secrets_manager"],
    cost: "optimized"
  }
  ↓
aws-cli skill: Returns ECS Fargate deployment commands with:
  - ECR repository setup with image scanning
  - IAM role with IRSA/OIDC integration
  - Secrets Manager integration for credentials
  - ECS service with auto-scaling policies
  - ALB with health checks
  - Cost optimization (Fargate Spot, right-sized tasks)
  ↓
iac-generator: Wraps commands in GitHub Actions workflow
  (invokes github-actions skill for CI/CD pipeline generation)
  ↓
security-validation: Trivy scans generated IaC and containers
  (invokes security-validation skill)
  ↓
User: Receives complete deployment package
```

## Constraints

This skill enforces constraints from SPEC.md:

1. **Security scanning**: All generated scripts must pass Trivy security scanning
2. **No hardcoded secrets**: Use `.env.example` pattern and Secrets Manager references
3. **OIDC preferred**: Always recommend IRSA/OIDC over IAM access keys
4. **Cost awareness**: Include comments about pricing implications and optimization options
5. **Validation**: Include dry-run commands and pre-deployment checklists
6. **High availability**: Recommend Multi-AZ for production workloads
7. **Observability**: Include CloudWatch monitoring, logging, and alerting setup

## Common Pitfalls

### ❌ Avoid

```bash
# Long-lived IAM access keys (security risk)
aws iam create-access-key --user-name USERNAME

# Overly permissive IAM policies
--policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Hardcoded secrets in commands
--environment Name=API_KEY,Value=sk-1234567890abcdef

# Unrestricted security groups
--ip-permissions IpProtocol=-1,FromPort=0,ToPort=65535,IpRanges=[{CidrIp=0.0.0.0/0}]

# Single-AZ production deployments (no HA)
--availability-zones us-east-1a  # without multi-AZ

# No cost optimization (expensive defaults)
--instance-type m5.4xlarge --on-demand-only

# Skipping validation steps
# (deploy directly without dry-run or IAM policy simulation)

# No monitoring or alerting
# (blind deployment without CloudWatch metrics)

# Using deprecated tfsec instead of Trivy
tfsec .
```

### ✅ Prefer

```bash
# OIDC/IRSA (no long-lived keys)
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME \
  --web-identity-token $OIDC_TOKEN

# Least-privilege IAM policies
--policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Secrets Manager references
--secrets name=API_KEY,valueFrom=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:app/api-key

# Restricted security groups with specific ports
--ip-permissions IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=10.0.0.0/8}]

# Multi-AZ HA deployments
--availability-zones us-east-1a,us-east-1b,us-east-1c

# Cost-optimized configurations
--instance-types t3.medium,t3a.medium --capacity-type SPOT --on-demand-percentage 20

# Pre-deployment validation
aws ec2 run-instances --dry-run ...
aws iam simulate-principal-policy ...

# Monitoring and alerting
aws cloudwatch put-metric-alarm ...
aws logs create-log-group ...

# Modern security scanning with Trivy
trivy config . --severity CRITICAL,HIGH --exit-code 1
```

## Additional Resources

- **Official Docs**: https://docs.aws.amazon.com/cli/
- **Best Practices**: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
- **IRSA (IAM Roles for Service Accounts)**: https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html
- **OIDC for GitHub**: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
- **Spot Instances**: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html
- **Cost Optimization**: https://aws.amazon.com/aws-cost-management/aws-cost-optimization/
- **Security**: https://docs.aws.amazon.com/security/
- **Trivy Security Scanning**: https://trivy.dev/
- **EKS Best Practices**: https://aws.github.io/aws-eks-best-practices/
- **Savings Plans**: https://aws.amazon.com/savingsplans/

## Version

**Skill Version**: 1.0.0
**Last Updated**: 2026-02-04
**Compatible with**: aws-cli 2.15.0+
**Changelog**:
- v1.0.0: Initial release with comprehensive AWS CLI patterns, OIDC/IRSA, cost optimization, Trivy scanning
