---
name: aws-eks
description: >
  AWS EKS cluster provisioning, configuration best practices, security hardening, cost optimization,
  IRSA (IAM Roles for Service Accounts), VPC CNI networking, node group management, cluster addons,
  and Kubernetes 1.31+ features including Gateway API v1 and native sidecar containers.

  Activate when user mentions: AWS EKS, Elastic Kubernetes Service, EKS cluster, eksctl, EKS node groups,
  managed node groups, self-managed nodes, Fargate profiles, EKS addons, VPC CNI, CoreDNS, kube-proxy,
  EKS OIDC provider, IRSA, IAM roles for service accounts, EKS security groups, pod security groups,
  EKS encryption, KMS encryption, EKS logging, control plane logs, EKS access entries, EKS cluster autoscaler,
  Karpenter, Gateway API on EKS, AWS Load Balancer Controller, EBS CSI driver, EFS CSI driver.

  Use for: EKS cluster architecture design, Terraform/Pulumi EKS provisioning, security configuration,
  IRSA setup, VPC networking for EKS, node group optimization, spot instance integration, cluster addon
  management, multi-AZ high availability, disaster recovery, cost optimization strategies.

  Do NOT use for: Generic Kubernetes manifests (use kubernetes-native skill), GitOps deployment patterns
  (use gitops-flux or gitops-argocd skills), container image creation (use container-analysis skill),
  GCP GKE clusters (use gcp-gke skill), Azure AKS clusters.
---

# AWS EKS Skill

## Purpose

Provides comprehensive patterns for AWS Elastic Kubernetes Service (EKS) cluster provisioning, configuration, security hardening, and operational best practices. This skill is referenced by the `iac-generator` agent when creating EKS infrastructure and by `iac-analyzer` when evaluating existing EKS clusters for optimization opportunities.

## Core Capabilities

### 1. EKS Cluster Architecture and Provisioning

Design and provision production-ready EKS clusters with proper networking, security, and high availability:

#### Cluster Configuration Best Practices

- **Control Plane**: Managed by AWS, multi-AZ by default, automated upgrades available
- **API Server Endpoint**: Private, public, or both (prefer private for production security)
- **Kubernetes Version**: Use n-1 version policy (stay within 1 minor version of latest)
- **Encryption**: Enable envelope encryption at rest using AWS KMS for secrets
- **Logging**: Enable all control plane log types (api, audit, authenticator, controllerManager, scheduler)
- **Access Management**: Use EKS access entries (EKS API) instead of aws-auth ConfigMap for Kubernetes 1.30+

**Networking Architecture:**

- **VPC Design**: Minimum 2 AZs (prefer 3 for production), separate subnets for public/private resources
- **Subnet Tagging**: Required tags for EKS resource discovery and load balancer provisioning
  - `kubernetes.io/cluster/<cluster-name>`: `shared` or `owned`
  - `kubernetes.io/role/elb`: `1` (public subnets for internet-facing load balancers)
  - `kubernetes.io/role/internal-elb`: `1` (private subnets for internal load balancers)
- **VPC CNI**: Uses native AWS networking, each Pod gets ENI IP from VPC CIDR
- **IP Capacity Planning**: Calculate max pods based on instance type ENI limits (not /24 per node assumption)
- **Security Groups**: Cluster security group (created by EKS), additional SGs for nodes, pod security groups for granular control

**High Availability and Disaster Recovery:**

- **Multi-AZ Node Distribution**: Spread node groups across 3 AZs (minimum 2)
- **Control Plane SLA**: 99.95% uptime SLA for production clusters (AWS managed)
- **Backup Strategy**: etcd backups managed by AWS, application-level backups using Velero
- **Cross-Region DR**: Use GitOps (Flux/ArgoCD) for cluster configuration replication
- **RTO/RPO Targets**: Typically 15-30 min RTO with GitOps cluster rebuild patterns

#### Terraform EKS Module Pattern

```hcl
# Terraform EKS cluster provisioning using terraform-aws-modules/eks
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"  # Use latest stable version

  cluster_name    = "production-eks"
  cluster_version = "1.31"  # Kubernetes 1.31+ for Gateway API v1 GA

  # Cluster endpoint configuration (prefer private for production)
  cluster_endpoint_public_access  = false  # Restrict to VPN/Direct Connect
  cluster_endpoint_private_access = true

  # Enable OIDC provider for IRSA (IAM Roles for Service Accounts)
  enable_irsa = true

  # Control plane logging (enable all for production visibility)
  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  # Encryption at rest using KMS (required for compliance)
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  # VPC and networking
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets  # Dedicated for control plane ENIs

  # Cluster access management (EKS API method for K8s 1.30+)
  enable_cluster_creator_admin_permissions = true
  access_entries = {
    admin_sso = {
      principal_arn = "arn:aws:iam::123456789012:role/AWSReservedSSO_AdministratorAccess_*"
      type          = "STANDARD"
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  # EKS managed node groups (production-ready configuration)
  eks_managed_node_groups = {
    # On-Demand node group for critical workloads (system pods, stateful apps)
    on_demand = {
      name           = "on-demand-general"
      instance_types = ["m5.xlarge", "m6i.xlarge"]  # Intel + AMD diversity
      capacity_type  = "ON_DEMAND"

      min_size     = 3  # Minimum 1 per AZ for 3 AZ deployment
      max_size     = 12
      desired_size = 6

      # Subnet distribution (multi-AZ)
      subnet_ids = module.vpc.private_subnets

      # IAM role for nodes (with SSM for debugging)
      iam_role_additional_policies = {
        AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
      }

      # Labels and taints
      labels = {
        workload-type = "on-demand"
        environment   = "production"
      }

      # EKS optimized AMI (AL2023 recommended for Kubernetes 1.30+)
      ami_type = "AL2023_x86_64_STANDARD"

      # User data for custom configurations
      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        # Set max pods based on ENI limits (not default /24 assumption)
        # m5.xlarge supports 58 pods (4 ENIs * 15 IPs - 1 for node = 59, minus system overhead)
        echo "MAX_PODS=58" >> /etc/environment
      EOT

      # Block device mappings (right-size root volume)
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100  # GB (sufficient for system + image cache)
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            encrypted             = true
            kms_key_id            = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }

      # Metadata options (IMDSv2 required for security)
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"  # IMDSv2 only
        http_put_response_hop_limit = 1
        instance_metadata_tags      = "enabled"
      }

      # Update configuration
      update_config = {
        max_unavailable_percentage = 25  # 25% rolling update for faster deployments
      }

      # Tags
      tags = {
        "karpenter.sh/discovery" = "production-eks"  # For Karpenter discovery if using
      }
    }

    # Spot node group for fault-tolerant workloads (70% cost savings)
    spot = {
      name           = "spot-optimized"
      instance_types = ["m5.xlarge", "m5a.xlarge", "m6i.xlarge", "m6a.xlarge"]  # Diverse instance types
      capacity_type  = "SPOT"

      min_size     = 0  # Scale to zero when not needed
      max_size     = 20
      desired_size = 3

      subnet_ids = module.vpc.private_subnets

      iam_role_additional_policies = {
        AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
      }

      labels = {
        workload-type = "spot-optimized"
        environment   = "production"
      }

      taints = [
        {
          key    = "spot"
          value  = "true"
          effect = "NoSchedule"
        }
      ]

      ami_type = "AL2023_x86_64_STANDARD"

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            encrypted             = true
            kms_key_id            = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
      }

      update_config = {
        max_unavailable_percentage = 50  # Aggressive updates for Spot (already fault-tolerant)
      }

      tags = {
        "karpenter.sh/discovery" = "production-eks"
      }
    }
  }

  # EKS addons (managed by AWS for automatic updates)
  cluster_addons = {
    # VPC CNI for Pod networking
    vpc-cni = {
      most_recent = true
      configuration_values = jsonencode({
        enableNetworkPolicy = "true"  # Enable network policies (Kubernetes 1.25+)
        env = {
          ENABLE_PREFIX_DELEGATION = "true"  # Increase IP efficiency (30+ pods per node)
          ENABLE_POD_ENI           = "true"  # For pod security groups
          POD_SECURITY_GROUP_ENFORCING_MODE = "standard"
        }
      })
    }

    # CoreDNS for service discovery
    coredns = {
      most_recent = true
      configuration_values = jsonencode({
        computeType = "Fargate"  # Optional: Run CoreDNS on Fargate for resilience
      })
    }

    # kube-proxy for service networking
    kube-proxy = {
      most_recent = true
    }

    # EBS CSI driver for persistent volumes
    aws-ebs-csi-driver = {
      most_recent           = true
      service_account_role_arn = aws_iam_role.ebs_csi_driver.arn
    }

    # EFS CSI driver for shared persistent storage
    aws-efs-csi-driver = {
      most_recent           = true
      service_account_role_arn = aws_iam_role.efs_csi_driver.arn
    }

    # Pod Identity Agent (for EKS Pod Identity)
    eks-pod-identity-agent = {
      most_recent = true
    }
  }

  # Node security group rules
  node_security_group_additional_rules = {
    # Allow nodes to communicate with control plane (required for webhooks)
    ingress_cluster_api_webhook = {
      description                   = "Cluster API to node webhook"
      protocol                      = "tcp"
      from_port                     = 443
      to_port                       = 443
      type                          = "ingress"
      source_cluster_security_group = true
    }

    # Allow nodes to reach EFS (if using EFS CSI)
    egress_efs = {
      description = "Node to EFS"
      protocol    = "tcp"
      from_port   = 2049
      to_port     = 2049
      type        = "egress"
      cidr_blocks = [module.vpc.vpc_cidr_block]
    }
  }

  tags = {
    Environment = "production"
    Terraform   = "true"
    ManagedBy   = "iac-team"
  }
}
```

### 2. IRSA (IAM Roles for Service Accounts)

Implement secure AWS API access for Kubernetes workloads without long-lived credentials:

**IRSA Benefits:**
- **No hardcoded credentials**: Pods receive temporary credentials via STS AssumeRoleWithWebIdentity
- **Fine-grained permissions**: Separate IAM roles per service account (least privilege)
- **Automatic credential rotation**: STS tokens expire after 1 hour (configurable)
- **Audit trail**: CloudTrail logs show which pods assumed which roles
- **Kubernetes-native**: Standard ServiceAccount resources with annotations

**IRSA Setup Pattern:**

```hcl
# 1. OIDC provider (created by EKS module with enable_irsa = true)
data "tls_certificate" "eks" {
  url = module.eks.cluster_oidc_issuer_url
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = module.eks.cluster_oidc_issuer_url

  tags = {
    Name = "${module.eks.cluster_name}-oidc-provider"
  }
}

# 2. IAM role for specific service account (example: EBS CSI driver)
data "aws_iam_policy_document" "ebs_csi_driver_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi_driver" {
  name               = "${module.eks.cluster_name}-ebs-csi-driver"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_driver_assume_role.json

  tags = {
    ServiceAccount = "ebs-csi-controller-sa"
    Namespace      = "kube-system"
  }
}

# 3. Attach AWS managed policy (or custom policy)
resource "aws_iam_role_policy_attachment" "ebs_csi_driver" {
  role       = aws_iam_role.ebs_csi_driver.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# 4. Kubernetes ServiceAccount with IRSA annotation
resource "kubernetes_service_account" "ebs_csi_controller" {
  metadata {
    name      = "ebs-csi-controller-sa"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.ebs_csi_driver.arn
    }
  }
}
```

**Application IRSA Example (S3 Access):**

```hcl
# IAM policy for S3 bucket access
resource "aws_iam_policy" "app_s3_access" {
  name        = "${module.eks.cluster_name}-app-s3-access"
  description = "S3 bucket access for application pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.app_data.arn,
          "${aws_s3_bucket.app_data.arn}/*"
        ]
      }
    ]
  })
}

# IAM role for app service account
data "aws_iam_policy_document" "app_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:apps:myapp-sa"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${module.eks.cluster_name}-myapp"
  assume_role_policy = data.aws_iam_policy_document.app_assume_role.json
}

resource "aws_iam_role_policy_attachment" "app_s3" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.app_s3_access.arn
}
```

**Kubernetes Deployment Using IRSA:**

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: myapp-sa
  namespace: apps
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/production-eks-myapp
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: apps
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      serviceAccountName: myapp-sa  # CRITICAL: Reference IRSA service account
      containers:
      - name: app
        image: myapp:latest
        # Application code uses AWS SDK to automatically discover credentials
        # SDK reads environment variables injected by EKS:
        # AWS_ROLE_ARN, AWS_WEB_IDENTITY_TOKEN_FILE, AWS_REGION
        env:
        - name: S3_BUCKET
          value: "myapp-data-bucket"
```

### 3. VPC CNI and Networking Optimization

Optimize EKS networking for IP efficiency, performance, and security:

#### IP Address Management

**Challenge**: Default VPC CNI allocates entire ENI per node, limiting pod density.

**Solutions:**

1. **Prefix Delegation Mode** (Recommended for most workloads):
   - Allocates /28 IPv4 prefixes instead of individual IPs
   - Increases pod density: 110+ pods per m5.xlarge (vs. 58 default)
   - Enable: `ENABLE_PREFIX_DELEGATION=true`

2. **Custom Networking** (For IP exhaustion scenarios):
   - Pods use separate CIDR from nodes (100.64.0.0/10 RFC6598)
   - Nodes use primary VPC CIDR, pods use secondary CIDR
   - Enable: `AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true`

3. **IPv6 Mode** (For future-proofing):
   - Unlimited IP address space
   - Requires IPv6-enabled VPC and subnets
   - Enable at cluster creation (cannot migrate existing clusters)

**VPC CNI Configuration via EKS Addon:**

```hcl
cluster_addons = {
  vpc-cni = {
    most_recent = true
    configuration_values = jsonencode({
      enableNetworkPolicy = "true"  # Kubernetes NetworkPolicy support
      env = {
        # Prefix delegation for increased pod density
        ENABLE_PREFIX_DELEGATION = "true"
        WARM_PREFIX_TARGET       = "1"  # Keep 1 warm prefix (/28 = 16 IPs) per node

        # Pod security groups (granular security control)
        ENABLE_POD_ENI                     = "true"
        POD_SECURITY_GROUP_ENFORCING_MODE  = "standard"

        # IP address management tuning
        WARM_IP_TARGET    = "3"   # Keep 3 warm IPs per node (for fast pod startup)
        MINIMUM_IP_TARGET = "10"  # Minimum IPs per node

        # Logging and observability
        ENABLE_POD_ENI_METRICS = "true"
        AWS_VPC_K8S_CNI_LOG_FILE = "/var/log/aws-routed-eni/plugin.log"
      }
    })
  }
}
```

#### Pod Security Groups

**Use Cases:**
- Database pods requiring specific security group rules
- Multi-tenant clusters with namespace-level network isolation
- Compliance requirements for traffic control at pod level

**Setup Pattern:**

```yaml
# 1. SecurityGroupPolicy CRD (created by VPC CNI)
apiVersion: vpcresources.k8s.aws/v1beta1
kind: SecurityGroupPolicy
metadata:
  name: database-pods-sg
  namespace: data
spec:
  podSelector:
    matchLabels:
      role: database
  securityGroups:
    groupIds:
      - sg-0123456789abcdef0  # Security group allowing RDS access
---
# 2. Deployment using pod security group
apiVersion: apps/v1
kind: Deployment
metadata:
  name: database-client
  namespace: data
spec:
  replicas: 2
  selector:
    matchLabels:
      role: database
  template:
    metadata:
      labels:
        role: database  # Matches SecurityGroupPolicy selector
    spec:
      containers:
      - name: app
        image: myapp:latest
```

#### Network Policies

**Kubernetes NetworkPolicy** (supported by VPC CNI with `enableNetworkPolicy=true`):

```yaml
# Deny all ingress by default (Zero Trust)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: apps
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
# Allow ingress from specific namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: apps
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: frontend
    ports:
    - protocol: TCP
      port: 8080
```

### 4. Cluster Addons and Essential Services

Deploy and configure essential EKS cluster services:

#### AWS Load Balancer Controller

**Purpose**: Provisions AWS ALB/NLB for Kubernetes Ingress and Service resources.

**Installation via Helm + IRSA:**

```hcl
# IAM role for AWS Load Balancer Controller
data "aws_iam_policy_document" "aws_lb_controller_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "aws_iam_role" "aws_lb_controller" {
  name               = "${module.eks.cluster_name}-aws-lb-controller"
  assume_role_policy = data.aws_iam_policy_document.aws_lb_controller_assume_role.json
}

# Attach AWS Load Balancer Controller IAM policy
resource "aws_iam_role_policy_attachment" "aws_lb_controller" {
  role       = aws_iam_role.aws_lb_controller.name
  policy_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/AWSLoadBalancerControllerIAMPolicy"
}

# Helm release
resource "helm_release" "aws_lb_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.8.0"  # Use latest stable version

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_lb_controller.arn
  }

  set {
    name  = "region"
    value = data.aws_region.current.name
  }

  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }
}
```

**Usage with Ingress (ALB):**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: apps
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip  # For VPC CNI Pod IPs
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-west-2:123456789012:certificate/abc123
    alb.ingress.kubernetes.io/tags: Environment=production,ManagedBy=iac-team
spec:
  ingressClassName: alb
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: app-service
            port:
              number: 80
```

#### Gateway API v1 on EKS (Kubernetes 1.31+)

**Advantages over Ingress:**
- Role-oriented design (Gateway for cluster operators, HTTPRoute for developers)
- More expressive routing rules (header-based, method-based, query parameter)
- Traffic splitting for canary deployments
- BackendTLSPolicy for TLS to backends
- Better multi-tenancy support

**Installation (Envoy Gateway):**

```bash
# Install Gateway API CRDs
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.1.0/standard-install.yaml

# Install Envoy Gateway
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.1.0 -n envoy-gateway-system --create-namespace
```

**Gateway Configuration with AWS NLB:**

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: envoy-gateway
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
---
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: production-gateway
  namespace: gateway-system
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "external"
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  gatewayClassName: envoy-gateway
  listeners:
  - name: http
    protocol: HTTP
    port: 80
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - name: wildcard-cert
        kind: Secret
        group: ""
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: apps
spec:
  parentRefs:
  - name: production-gateway
    namespace: gateway-system
  hostnames:
  - "app.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api
    backendRefs:
    - name: backend-service
      port: 8080
      weight: 90  # 90% traffic to stable
  - matches:
    - path:
        type: PathPrefix
        value: /api
    backendRefs:
    - name: backend-service-canary
      port: 8080
      weight: 10  # 10% traffic to canary (progressive delivery)
```

#### Cluster Autoscaler vs Karpenter

**Cluster Autoscaler** (Traditional approach):
- Scales node groups based on pending pods
- Works with ASGs (Auto Scaling Groups)
- Simpler to understand and configure
- Good for predictable workloads

**Karpenter** (Modern approach, recommended for new clusters):
- Direct EC2 instance provisioning (no ASG dependency)
- Faster scaling: provisions nodes in ~1 minute vs. 3-5 minutes
- Cost optimization: automatically selects cheapest instance types
- Bin-packing: consolidates pods to minimize node count
- Spot instance support with automatic fallback to On-Demand

**Karpenter Installation:**

```hcl
# IAM role for Karpenter controller
data "aws_iam_policy_document" "karpenter_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:karpenter:karpenter"]
    }
  }
}

resource "aws_iam_role" "karpenter_controller" {
  name               = "${module.eks.cluster_name}-karpenter-controller"
  assume_role_policy = data.aws_iam_policy_document.karpenter_assume_role.json
}

# Attach Karpenter controller policy
resource "aws_iam_role_policy_attachment" "karpenter_controller" {
  role       = aws_iam_role.karpenter_controller.name
  policy_arn = aws_iam_policy.karpenter_controller.arn
}

# Helm release
resource "helm_release" "karpenter" {
  namespace        = "karpenter"
  create_namespace = true
  name             = "karpenter"
  repository       = "oci://public.ecr.aws/karpenter"
  chart            = "karpenter"
  version          = "1.0.0"

  set {
    name  = "settings.clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "settings.clusterEndpoint"
    value = module.eks.cluster_endpoint
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.karpenter_controller.arn
  }

  set {
    name  = "settings.interruptionQueue"
    value = aws_sqs_queue.karpenter.name
  }
}
```

**Karpenter NodePool Configuration:**

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
      - key: "karpenter.sh/capacity-type"
        operator: In
        values: ["spot", "on-demand"]  # Prefer Spot, fallback to On-Demand
      - key: "kubernetes.io/arch"
        operator: In
        values: ["amd64"]
      - key: "karpenter.k8s.aws/instance-category"
        operator: In
        values: ["c", "m", "r"]  # Compute, general, memory optimized
      - key: "karpenter.k8s.aws/instance-generation"
        operator: Gt
        values: ["5"]  # Instance generation >= 5

      nodeClassRef:
        name: default

      # Taints for Spot instances (optional)
      taints:
      - key: "spot"
        value: "true"
        effect: "NoSchedule"

  # Limits and disruption budget
  limits:
    cpu: "1000"
    memory: "1000Gi"

  disruption:
    consolidationPolicy: WhenUnderutilized
    consolidateAfter: 30s  # Aggressively consolidate for cost savings
    expireAfter: 720h  # Recycle nodes after 30 days

---
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2023  # Amazon Linux 2023
  role: "KarpenterNodeRole-production-eks"
  subnetSelectorTerms:
  - tags:
      karpenter.sh/discovery: "production-eks"
  securityGroupSelectorTerms:
  - tags:
      karpenter.sh/discovery: "production-eks"
  userData: |
    #!/bin/bash
    echo "MAX_PODS=110" >> /etc/environment
  blockDeviceMappings:
  - deviceName: /dev/xvda
    ebs:
      volumeSize: 100Gi
      volumeType: gp3
      iops: 3000
      throughput: 125
      encrypted: true
      deleteOnTermination: true
  metadataOptions:
    httpEndpoint: enabled
    httpProtocolIPv6: disabled
    httpPutResponseHopLimit: 1
    httpTokens: required  # IMDSv2
  tags:
    ManagedBy: "karpenter"
    Environment: "production"
```

### 5. Security Best Practices

Implement defense-in-depth security for EKS clusters:

#### Control Plane Security

- **Private API Endpoint**: Restrict access to VPC/VPN/Direct Connect only
- **EKS Access Entries**: Use EKS API for access management (prefer over aws-auth ConfigMap for K8s 1.30+)
- **Audit Logging**: Enable all control plane log types, ship to CloudWatch Logs
- **Encryption**: Enable envelope encryption at rest using AWS KMS for etcd secrets
- **Network Policies**: Enforce Zero Trust with default-deny network policies

#### Node Security

- **IMDSv2**: Require IMDSv2 (http_tokens = "required") to prevent SSRF attacks
- **SSM Session Manager**: Use SSM for node access instead of SSH (no bastion hosts, no SSH keys)
- **Minimal IAM Permissions**: Node IAM roles should only have ECR pull, CloudWatch logs, and EKS cluster join
- **Encrypted EBS**: Encrypt all node EBS volumes using KMS
- **Security Group Hardening**: Restrict node security groups to minimum required ports
- **Amazon Linux 2023**: Use AL2023 AMI for latest security patches and longer support

#### Pod Security

**Pod Security Standards** (PSS) enforcement using Pod Security Admission:

```yaml
# Enforce restricted PSS at namespace level
apiVersion: v1
kind: Namespace
metadata:
  name: apps
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```

**Pod Security Policy (deprecated in K8s 1.25+, use PSS above):**

- Use non-root users (runAsNonRoot: true)
- Drop all capabilities, add only required ones
- Read-only root filesystem where possible
- No privilege escalation (allowPrivilegeEscalation: false)
- Use seccomp profiles (RuntimeDefault or Localhost)

**Example Secure Pod Spec:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secure-app
  namespace: apps
spec:
  replicas: 3
  selector:
    matchLabels:
      app: secure-app
  template:
    metadata:
      labels:
        app: secure-app
    spec:
      serviceAccountName: myapp-sa  # IRSA service account
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: app
        image: myapp:latest
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /app/cache
      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir: {}
```

#### Secrets Management

**AWS Secrets Manager / Systems Manager Parameter Store Integration:**

Use External Secrets Operator to sync secrets from AWS into Kubernetes:

```yaml
# External Secrets Operator SecretStore
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: apps
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa  # IRSA service account
---
# ExternalSecret resource
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
  namespace: apps
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: app-secrets
    creationPolicy: Owner
  data:
  - secretKey: database-password
    remoteRef:
      key: production/app/database
      property: password
  - secretKey: api-key
    remoteRef:
      key: production/app/api
      property: key
```

**Never Hardcode Secrets:**
- Use AWS Secrets Manager or Parameter Store
- Use External Secrets Operator or Secrets Store CSI Driver
- Use IRSA for AWS API access (no long-lived credentials)
- Rotate secrets regularly (automated via Secrets Manager)

### 6. Cost Optimization Strategies

Implement cost optimization for EKS workloads (target: 30-70% cost reduction):

#### Spot Instances

**Savings**: 70-90% discount vs. On-Demand pricing

**Best Practices:**
- Mix Spot (70-80%) and On-Demand (20-30%) for reliability
- Diversify instance types (4-5 types per node group)
- Use Karpenter for automatic Spot/On-Demand fallback
- Handle interruptions gracefully (120s termination grace period)
- Use Spot placement score API to select best AZs

**Spot-Friendly Workloads:**
- Stateless applications (can restart without data loss)
- Batch jobs and data processing
- CI/CD build agents
- Development and staging environments

**Spot-Unfriendly Workloads:**
- Databases and stateful services
- Real-time processing with strict SLAs
- Single-replica critical services

#### Right-Sizing

**Target**: 40-70% CPU/memory utilization for optimal cost-performance ratio

**Tools:**
- Vertical Pod Autoscaler (VPA): Recommends resource requests/limits
- Kubernetes Metrics Server: Provides actual usage data
- AWS Cost Explorer: Shows EKS compute costs by node group

**Right-Sizing Process:**

```bash
# 1. Install VPA
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-1.1.0/vpa-v1.1.0.yaml

# 2. Create VPA in recommendation mode
kubectl apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: app-vpa
  namespace: apps
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  updatePolicy:
    updateMode: "Off"  # Recommendation only, no auto-update
EOF

# 3. Wait 24-48 hours for data collection

# 4. Get recommendations
kubectl describe vpa app-vpa -n apps
# Output shows: Lower Bound, Target, Uncapped Target, Upper Bound
```

#### Savings Plans and Reserved Instances

- **Compute Savings Plans**: 1 or 3-year commitment, 66% savings, flexible across instance types
- **EC2 Instance Savings Plans**: Higher discount (72%) but locked to instance family
- **Reserved Instances**: Legacy option, use Savings Plans instead
- **Recommendation**: 20-30% Savings Plans coverage for baseline On-Demand usage

#### Non-Production Environment Optimization

**Staging/Dev Clusters:**
- Use 100% Spot instances (acceptable interruption risk)
- Scale to zero during off-hours (nights/weekends)
- Use smaller instance types (t3.medium instead of m5.xlarge)
- Single AZ deployment (no multi-AZ overhead)

**Automation for Non-Prod Shutdown:**

```yaml
# CronJob to scale down deployments during off-hours
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down
  namespace: kube-system
spec:
  schedule: "0 19 * * 1-5"  # 7 PM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: autoscaler
          containers:
          - name: kubectl
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              kubectl scale deployment --all --replicas=0 -n apps
              kubectl scale deployment --all --replicas=0 -n data
          restartPolicy: OnFailure
---
# CronJob to scale up deployments during business hours
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-up
  namespace: kube-system
spec:
  schedule: "0 8 * * 1-5"  # 8 AM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: autoscaler
          containers:
          - name: kubectl
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              # Restore replicas from annotations
              flux reconcile kustomization apps --with-source
          restartPolicy: OnFailure
```

#### Kubernetes Native Cost Optimization

- **Horizontal Pod Autoscaler (HPA)**: Scale replicas based on CPU/memory/custom metrics
- **Cluster Autoscaler / Karpenter**: Scale node count based on pending pods
- **Pod Disruption Budgets (PDB)**: Allow safe node termination during scaling events
- **Resource Quotas**: Prevent over-provisioning at namespace level
- **Limit Ranges**: Set default resource requests/limits to prevent unbounded consumption

### 7. Monitoring and Observability

Implement comprehensive monitoring for EKS clusters:

#### Control Plane Logs

**Enable all log types** (recommended for production):

```hcl
cluster_enabled_log_types = [
  "api",              # API server logs
  "audit",            # Kubernetes audit logs (who did what)
  "authenticator",    # AWS IAM Authenticator logs
  "controllerManager", # Controller manager logs
  "scheduler"         # Scheduler logs
]
```

**Ship to CloudWatch Logs, retain 30-90 days, then archive to S3 for cost savings.**

#### Container Insights

**AWS Container Insights** provides:
- Pod and node CPU/memory utilization
- Container-level metrics
- Performance dashboard in CloudWatch
- Log aggregation from pods

**Installation via Helm:**

```bash
# CloudWatch agent for Container Insights
helm repo add aws-observability https://aws-observability.github.io/helm-charts
helm install aws-cloudwatch-metrics aws-observability/aws-cloudwatch-metrics \
  --namespace amazon-cloudwatch \
  --create-namespace \
  --set clusterName=production-eks
```

#### Prometheus and Grafana

**For advanced observability:**

```bash
# Install kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi
```

**Key Metrics to Monitor:**
- Node CPU/memory utilization (target: 40-70%)
- Pod restart rate (should be near zero in steady state)
- API server request latency (p99 < 1s)
- etcd leader changes (should be rare)
- Container image pull errors
- Persistent volume attachment failures
- Load balancer 5xx error rate

### 8. Kubernetes 1.31+ Features

Leverage modern Kubernetes features for EKS 1.31+ clusters:

#### Native Sidecar Containers

**Traditional Problem**: Sidecar containers start as regular containers, causing race conditions with main application container.

**Native Sidecars** (K8s 1.29+, stable in 1.31):
- Use `restartPolicy: Always` on init containers
- Sidecar starts in init phase but doesn't block subsequent init containers
- Main containers wait for sidecar to be ready (via startupProbe)
- Sidecar terminates AFTER main containers (reverse startup order)
- Solves race conditions for logging, service mesh, monitoring sidecars

**Example: Logging Sidecar:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-with-logging-sidecar
  namespace: apps
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      initContainers:
      # Native sidecar: starts in init phase, persists during main container lifetime
      - name: log-shipper
        image: fluent/fluent-bit:latest
        restartPolicy: Always  # CRITICAL: Makes this a native sidecar
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        - name: config
          mountPath: /fluent-bit/etc/
        # Startup probe ensures sidecar is ready before main container starts
        startupProbe:
          httpGet:
            path: /api/v1/health
            port: 2020
          initialDelaySeconds: 5
          periodSeconds: 2
          failureThreshold: 30
      containers:
      # Main application container
      - name: app
        image: myapp:latest
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        # Application writes logs to /var/log, fluent-bit ships to CloudWatch
      volumes:
      - name: varlog
        emptyDir: {}
      - name: config
        configMap:
          name: fluent-bit-config
```

**Use Cases for Native Sidecars:**
- Log shipping (Fluent Bit, Fluentd)
- Service mesh proxies (Envoy, Linkerd)
- Monitoring agents (Datadog, New Relic)
- Secret fetching (Vault agent)

#### Gateway API v1 (Production Ready)

See "Gateway API v1 on EKS" section above for full details.

**Key Advantages:**
- Graduated to GA (v1) in Kubernetes 1.31
- Role-oriented design (separation of concerns)
- More expressive routing than Ingress
- Native traffic splitting for canary deployments
- Better multi-tenancy support

### 9. Disaster Recovery and Backup

Implement backup and disaster recovery strategies for EKS:

#### Cluster Configuration Backup

**GitOps Approach** (Recommended):
- Store all Kubernetes manifests in Git repositories
- Use Flux CD or ArgoCD for continuous deployment
- Cluster rebuild: Bootstrap new cluster, Flux syncs all resources
- RTO: 15-30 minutes (provision cluster + GitOps sync)

**Benefits:**
- Version control for all changes
- Declarative disaster recovery
- Consistent multi-cluster deployments
- Audit trail for changes

#### Application Data Backup

**Velero** (CNCF backup solution):

```bash
# Install Velero with AWS S3 backend
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.10.0 \
  --bucket eks-backups-production \
  --backup-location-config region=us-west-2 \
  --snapshot-location-config region=us-west-2 \
  --secret-file ./credentials-velero \
  --use-volume-snapshots=true \
  --use-node-agent
```

**Backup Schedule:**

```yaml
# Daily backup of production namespaces
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  template:
    includedNamespaces:
    - apps
    - data
    ttl: 720h  # Retain 30 days
    snapshotVolumes: true
    defaultVolumesToFsBackup: false
```

**Disaster Recovery Test:**

```bash
# Simulate disaster by deleting namespace
kubectl delete namespace apps

# Restore from backup
velero restore create --from-backup daily-backup-20260203020000

# Verify restoration
kubectl get all -n apps
```

#### Multi-Region Disaster Recovery

**Strategy**: Active-Passive or Active-Active multi-region setup

**Active-Passive Pattern:**
1. Primary cluster in us-west-2, standby in us-east-1
2. Continuous backups to S3 (replicated cross-region)
3. GitOps manifests stored in Git (region-agnostic)
4. On disaster: Provision standby cluster, restore from backup + GitOps sync
5. Update Route 53 to point to standby cluster

**Active-Active Pattern:**
1. Both clusters actively serving traffic
2. Route 53 weighted routing or latency-based routing
3. Stateless apps: Easy active-active (no data sync required)
4. Stateful apps: Database replication (RDS cross-region read replicas, DynamoDB global tables)

## Activation

This skill activates automatically when users reference:

- **EKS cluster operations**: Provisioning, upgrading, configuration, access management
- **EKS networking**: VPC CNI, pod networking, IP address management, network policies, pod security groups
- **EKS security**: IRSA, encryption, audit logging, pod security standards, secrets management
- **EKS node groups**: Managed nodes, self-managed nodes, Fargate, instance type selection, AMI configuration
- **EKS addons**: VPC CNI, CoreDNS, kube-proxy, EBS CSI, EFS CSI, AWS Load Balancer Controller
- **EKS cost optimization**: Spot instances, right-sizing, Savings Plans, Karpenter, cluster autoscaling
- **EKS observability**: Control plane logs, Container Insights, Prometheus, CloudWatch integration
- **Kubernetes 1.31+ on EKS**: Gateway API v1, native sidecar containers, modern features

## When NOT to Use This Skill

- **Generic Kubernetes manifests**: Use `kubernetes-native` skill for Deployments, Services, ConfigMaps (platform-agnostic)
- **GitOps deployment patterns**: Use `gitops-flux` or `gitops-argocd` skills for continuous delivery
- **Container images**: Use `container-analysis` skill for Dockerfile generation and optimization
- **GCP GKE clusters**: Use `gcp-gke` skill (different managed Kubernetes service)
- **Azure AKS clusters**: Use Azure-specific skill (out of scope for iac-team plugin)
- **Helm chart creation**: Use `helm-charts` skill for chart development
- **Terraform modules**: Use `terraform-modules` skill for reusable IaC patterns

## Integration with iac-team Agents

### With iac-generator Agent

When `iac-generator` needs EKS infrastructure:

1. **Reference this skill** for EKS cluster architecture and Terraform patterns
2. **Apply security constraints**: IRSA for AWS access, no hardcoded credentials, encryption enabled
3. **Choose node strategy**: Managed node groups vs. Fargate vs. Karpenter-managed nodes
4. **Configure networking**: VPC CNI settings, IP address planning, security groups
5. **Enable cost optimization**: Spot instances for appropriate workloads, right-sized instance types
6. **Set up addons**: VPC CNI, AWS Load Balancer Controller, EBS/EFS CSI drivers
7. **Integrate with GitOps**: Reference `gitops-flux` skill for cluster configuration management

### With iac-analyzer Agent

When `iac-analyzer` reviews EKS configurations:

1. **Check IRSA usage**: Validate service accounts use IRSA instead of hardcoded credentials
2. **Verify security**: Encryption enabled, private endpoint, audit logging, IMDSv2, pod security standards
3. **Assess cost optimization**: Spot instance usage, right-sizing opportunities, Savings Plans coverage
4. **Review networking**: VPC CNI configuration, IP address capacity, network policies
5. **Validate high availability**: Multi-AZ node distribution, sufficient capacity per AZ
6. **Check addon versions**: Outdated addons, missing security patches
7. **Identify upgrade opportunities**: Kubernetes version n-1 policy, new feature availability

## Best Practices Summary

1. **Enable IRSA for all AWS API access** - No hardcoded credentials, automatic rotation, least privilege
2. **Use private API endpoint for production** - Restrict access to VPC/VPN/Direct Connect only
3. **Enable all control plane logs** - Ship to CloudWatch, retain 30-90 days, archive to S3
4. **Encrypt secrets at rest** - Use AWS KMS envelope encryption for etcd
5. **Deploy across 3 AZs** - High availability, fault tolerance, meet SLA targets
6. **Use VPC CNI prefix delegation** - Increase pod density, optimize IP address usage
7. **Implement pod security standards** - Enforce restricted PSS, non-root users, read-only root filesystem
8. **Mix Spot (70-80%) and On-Demand (20-30%)** - 70% cost savings with reliability
9. **Right-size workloads** - Target 40-70% utilization, use VPA for recommendations
10. **Use Karpenter for autoscaling** - Faster than Cluster Autoscaler, better cost optimization
11. **Migrate to Gateway API v1** - More expressive than Ingress, better multi-tenancy, production-ready
12. **Use native sidecar containers** - Solve startup/termination race conditions for logging/service mesh
13. **Implement GitOps for cluster config** - Flux CD or ArgoCD for disaster recovery, audit trail
14. **Use External Secrets Operator** - Sync secrets from AWS Secrets Manager, no hardcoded values
15. **Enable Container Insights** - Monitor pod/node metrics, troubleshoot performance issues

## Security Compliance

This skill enforces:

- ✅ IRSA for AWS API access (no long-lived credentials)
- ✅ Encryption at rest using AWS KMS for secrets
- ✅ Private API endpoint for production clusters
- ✅ IMDSv2 required on all nodes (SSRF protection)
- ✅ All control plane logs enabled (audit trail)
- ✅ Pod security standards enforced (restricted PSS)
- ✅ Network policies for Zero Trust networking
- ✅ EBS volumes encrypted using KMS
- ✅ SSM Session Manager for node access (no SSH)
- ✅ External Secrets Operator for secrets management

## References

For comprehensive patterns and official documentation, see:

- **AWS EKS Best Practices Guide**: https://aws.github.io/aws-eks-best-practices/
- **EKS Workshop**: https://www.eksworkshop.com/
- **Terraform AWS EKS Module**: https://registry.terraform.io/modules/terraform-aws-modules/eks/aws/latest
- **AWS Load Balancer Controller**: https://kubernetes-sigs.github.io/aws-load-balancer-controller/
- **Karpenter**: https://karpenter.sh/
- **Gateway API**: https://gateway-api.sigs.k8s.io/
- **Kubernetes Native Sidecars**: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/
- **VPC CNI Plugin**: https://github.com/aws/amazon-vpc-cni-k8s
- **External Secrets Operator**: https://external-secrets.io/
- **Velero Backup**: https://velero.io/

---

**Version**: 1.0.0
**Last Updated**: 2026-02-04
**Compatible With**: EKS 1.31+, Terraform 1.7+, Kubernetes 1.31+, Gateway API v1.x

*This skill is part of the iac-team plugin. For related capabilities, see: kubernetes-native (K8s manifests), gitops-flux (continuous delivery), container-analysis (Dockerfile patterns), terraform-modules (IaC patterns), gcp-gke (GCP managed Kubernetes).*
