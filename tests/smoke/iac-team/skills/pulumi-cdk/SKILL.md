---
name: pulumi-cdk
description: >
  Pulumi and AWS CDK patterns for Infrastructure-as-Code using modern programming languages (TypeScript, Python, Go).
  Type-safe infrastructure with real language features (loops, conditionals, functions), reusable components,
  multi-cloud abstractions, and GitOps integration patterns. Includes AI-assisted generation validation and
  security-first deployment workflows.

  Activate when user mentions: Pulumi, AWS CDK, CDK for Terraform (CDKTF), infrastructure as real code,
  TypeScript infrastructure, Python infrastructure, Go infrastructure, Pulumi stacks, CDK constructs,
  ComponentResource, pulumi up, cdk deploy, cdk diff, Pulumi ESC, Pulumi Automation API, CDK Pipelines,
  L1/L2/L3 constructs, CrossGuard policies, pulumi preview, infrastructure components, multi-cloud abstractions,
  AI-generated infrastructure, policy-as-code validation.

  Use for: Type-safe infrastructure code generation, component library development, multi-cloud abstractions,
  testing infrastructure with real language test frameworks (Jest, pytest, Go testing), imperative deployment workflows,
  Automation API integrations, infrastructure validation with policy-as-code (CrossGuard, cdk-nag, OPA/Rego),
  AI-assisted IaC with validation pipelines, brownfield infrastructure enhancement.

  Do NOT use for: Pure declarative HCL (use terraform-modules skill), Kubernetes-native YAML manifests
  (use kubernetes-native skill), Helm charts (use helm-charts skill), cloud-specific CLI operations
  (use aws-cli or gcloud-cli skills).
---

# Pulumi and AWS CDK Skill

## Purpose

Provides patterns and best practices for infrastructure-as-code using modern programming languages through Pulumi and AWS CDK frameworks. Enables type-safe infrastructure definitions with real language features (conditionals, loops, functions, classes), reusable component libraries, comprehensive testing with standard language test frameworks, and multi-cloud abstractions. This skill is referenced by the `iac-generator` agent when creating programmatic infrastructure and by `iac-analyzer` when evaluating existing Pulumi/CDK codebases. **Includes specialized guidance for AI-assisted generation, validation pipelines, and security-first workflows aligned with 2026 best practices.**

## Core Capabilities

### 1. Pulumi Stack Architecture and Best Practices

**Context (2026)**: Pulumi 3.x provides mature multi-language support (TypeScript, Python, Go, C#, Java, YAML) with native cloud provider SDKs. Pulumi ESC (Environments, Secrets, and Configuration) provides centralized secret management replacing previous patterns.

#### Stack Organization Patterns

**Monorepo Pattern** (Recommended for multi-environment deployments):
```typescript
// pulumi/
//   infrastructure/       # Shared infrastructure (VPC, networking)
//   services/
//     api/               # API service stack
//     frontend/          # Frontend stack
//   components/          # Reusable ComponentResources
//   policies/            # CrossGuard policy packs
//   validation/          # OPA/Rego policies for AI-generated code

// infrastructure/index.ts
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { NetworkComponent } from "../components/network";

// Stack for shared infrastructure
const config = new pulumi.Config();
const environment = pulumi.getStack(); // dev, staging, prod

// Create network component
const network = new NetworkComponent("network", {
    cidrBlock: config.require("vpcCidr"),
    availabilityZones: config.requireObject<string[]>("azs"),
    environment: environment,
    // Tag all resources for cost tracking and governance
    tags: {
        Environment: environment,
        ManagedBy: "pulumi",
        Project: pulumi.getProject(),
        // Add AI-generation metadata for audit trails
        GenerationMethod: config.get("generationMethod") || "manual",
    },
});

// Export VPC outputs for consumption by service stacks
export const vpcId = network.vpcId;
export const privateSubnetIds = network.privateSubnetIds;
export const publicSubnetIds = network.publicSubnetIds;
```

**StackReference Pattern** (Cross-stack dependencies):
```typescript
// services/api/index.ts
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

// Reference infrastructure stack outputs
const infraStack = new pulumi.StackReference(
    `organization/infrastructure/${pulumi.getStack()}`
);

const vpcId = infraStack.getOutput("vpcId");
const privateSubnetIds = infraStack.getOutput("privateSubnetIds");

// Use infrastructure outputs in service stack
const apiCluster = new aws.ecs.Cluster("api-cluster", {
    name: `api-${pulumi.getStack()}`,
    tags: {
        Environment: pulumi.getStack(),
        ManagedBy: "pulumi",
    },
});

// ECS service in private subnets from infrastructure stack
const apiService = new aws.ecs.Service("api-service", {
    cluster: apiCluster.arn,
    taskDefinition: apiTaskDefinition.arn,
    desiredCount: 3,
    launchType: "FARGATE",
    networkConfiguration: {
        subnets: privateSubnetIds,
        securityGroups: [apiSecurityGroup.id],
        assignPublicIp: false,
    },
});
```

#### Pulumi ESC Integration (2026 Pattern)

```typescript
// Replace old Config pattern with ESC
import * as pulumi from "@pulumi/pulumi";

// Pulumi ESC automatically injects environment variables
// No need for config.get() - use native environment access
const dbPassword = process.env.DB_PASSWORD!; // From ESC
const apiKey = process.env.API_KEY!; // From ESC

// For Pulumi-specific config, still use Config
const config = new pulumi.Config();
const instanceType = config.get("instanceType") || "t3.medium";

// ESC supports hierarchical environments
// pulumi/environments/dev.yaml:
// imports:
//   - base
//   - aws/dev
// values:
//   dbPassword:
//     fn::secret: ${vault.dev.database.password}
//   apiKey:
//     fn::secret: ${vault.dev.api.key}
```

#### ComponentResource Pattern (Reusable Components)

```typescript
// components/network.ts
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

export interface NetworkComponentArgs {
    cidrBlock: string;
    availabilityZones: string[];
    environment: string;
    enableNatGateway?: boolean;
    tags?: { [key: string]: string };
}

export class NetworkComponent extends pulumi.ComponentResource {
    public readonly vpcId: pulumi.Output<string>;
    public readonly privateSubnetIds: pulumi.Output<string[]>;
    public readonly publicSubnetIds: pulumi.Output<string[]>;

    constructor(name: string, args: NetworkComponentArgs, opts?: pulumi.ComponentResourceOptions) {
        super("custom:network:NetworkComponent", name, {}, opts);

        // Validate inputs (critical for AI-generated code)
        if (!args.cidrBlock.match(/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/)) {
            throw new Error(`Invalid CIDR block format: ${args.cidrBlock}`);
        }
        if (args.availabilityZones.length < 2) {
            throw new Error("At least 2 availability zones required for high availability");
        }

        // Create VPC
        const vpc = new aws.ec2.Vpc(`${name}-vpc`, {
            cidrBlock: args.cidrBlock,
            enableDnsHostnames: true,
            enableDnsSupport: true,
            tags: {
                Name: `${args.environment}-vpc`,
                ...args.tags,
            },
        }, { parent: this });

        // Create Internet Gateway
        const igw = new aws.ec2.InternetGateway(`${name}-igw`, {
            vpcId: vpc.id,
            tags: {
                Name: `${args.environment}-igw`,
                ...args.tags,
            },
        }, { parent: this });

        // Create public subnets
        const publicSubnets = args.availabilityZones.map((az, index) => {
            return new aws.ec2.Subnet(`${name}-public-${index}`, {
                vpcId: vpc.id,
                cidrBlock: `10.0.${index}.0/24`,
                availabilityZone: az,
                mapPublicIpOnLaunch: true,
                tags: {
                    Name: `${args.environment}-public-${az}`,
                    Type: "public",
                    ...args.tags,
                },
            }, { parent: this });
        });

        // Create NAT Gateways (one per AZ for high availability)
        const natGateways = args.enableNatGateway !== false
            ? args.availabilityZones.map((az, index) => {
                const eip = new aws.ec2.Eip(`${name}-nat-eip-${index}`, {
                    vpc: true,
                    tags: {
                        Name: `${args.environment}-nat-eip-${az}`,
                        ...args.tags,
                    },
                }, { parent: this });

                return new aws.ec2.NatGateway(`${name}-nat-${index}`, {
                    allocationId: eip.id,
                    subnetId: publicSubnets[index].id,
                    tags: {
                        Name: `${args.environment}-nat-${az}`,
                        ...args.tags,
                    },
                }, { parent: this });
            })
            : [];

        // Create private subnets
        const privateSubnets = args.availabilityZones.map((az, index) => {
            return new aws.ec2.Subnet(`${name}-private-${index}`, {
                vpcId: vpc.id,
                cidrBlock: `10.0.${index + 10}.0/24`,
                availabilityZone: az,
                tags: {
                    Name: `${args.environment}-private-${az}`,
                    Type: "private",
                    ...args.tags,
                },
            }, { parent: this });
        });

        // Route tables
        const publicRouteTable = new aws.ec2.RouteTable(`${name}-public-rt`, {
            vpcId: vpc.id,
            routes: [{
                cidrBlock: "0.0.0.0/0",
                gatewayId: igw.id,
            }],
            tags: {
                Name: `${args.environment}-public-rt`,
                ...args.tags,
            },
        }, { parent: this });

        // Associate public subnets with public route table
        publicSubnets.forEach((subnet, index) => {
            new aws.ec2.RouteTableAssociation(`${name}-public-rta-${index}`, {
                subnetId: subnet.id,
                routeTableId: publicRouteTable.id,
            }, { parent: this });
        });

        // Private route tables (one per NAT gateway for HA)
        privateSubnets.forEach((subnet, index) => {
            if (natGateways.length > 0) {
                const privateRouteTable = new aws.ec2.RouteTable(`${name}-private-rt-${index}`, {
                    vpcId: vpc.id,
                    routes: [{
                        cidrBlock: "0.0.0.0/0",
                        natGatewayId: natGateways[index].id,
                    }],
                    tags: {
                        Name: `${args.environment}-private-rt-${args.availabilityZones[index]}`,
                        ...args.tags,
                    },
                }, { parent: this });

                new aws.ec2.RouteTableAssociation(`${name}-private-rta-${index}`, {
                    subnetId: subnet.id,
                    routeTableId: privateRouteTable.id,
                }, { parent: this });
            }
        });

        // Register outputs
        this.vpcId = vpc.id;
        this.privateSubnetIds = pulumi.output(privateSubnets.map(s => s.id));
        this.publicSubnetIds = pulumi.output(publicSubnets.map(s => s.id));

        this.registerOutputs({
            vpcId: this.vpcId,
            privateSubnetIds: this.privateSubnetIds,
            publicSubnetIds: this.publicSubnetIds,
        });
    }
}
```

### 2. AWS CDK Construct Library Patterns

**Context (2026)**: AWS CDK v2 consolidated all AWS service constructs into a single package (`aws-cdk-lib`). CDK for Terraform (CDKTF) enables using CDK patterns with Terraform providers.

#### CDK L3 Construct Pattern (High-Level Abstractions)

```typescript
// lib/api-stack.ts
import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export interface ApiStackProps extends cdk.StackProps {
    environment: string;
    tableName: string;
}

export class ApiStack extends cdk.Stack {
    public readonly api: apigateway.RestApi;
    public readonly table: dynamodb.Table;

    constructor(scope: Construct, id: string, props: ApiStackProps) {
        super(scope, id, props);

        // DynamoDB table with best practices
        this.table = new dynamodb.Table(this, 'ApiTable', {
            tableName: `${props.environment}-${props.tableName}`,
            partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            pointInTimeRecovery: props.environment === 'prod',
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: props.environment === 'prod'
                ? cdk.RemovalPolicy.RETAIN
                : cdk.RemovalPolicy.DESTROY,
            stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            tags: {
                Environment: props.environment,
                ManagedBy: 'cdk',
            },
        });

        // Lambda function with CDK-managed IAM policies
        const apiFunction = new lambda.Function(this, 'ApiFunction', {
            runtime: lambda.Runtime.NODEJS_20_X,
            handler: 'index.handler',
            code: lambda.Code.fromAsset('lambda'),
            environment: {
                TABLE_NAME: this.table.tableName,
                ENVIRONMENT: props.environment,
            },
            timeout: cdk.Duration.seconds(30),
            memorySize: 512,
            // CDK automatically creates IAM role
            description: `API Lambda for ${props.environment}`,
        });

        // Grant DynamoDB permissions (CDK manages IAM policies)
        this.table.grantReadWriteData(apiFunction);

        // API Gateway with Lambda integration
        this.api = new apigateway.RestApi(this, 'Api', {
            restApiName: `${props.environment}-api`,
            description: `API for ${props.environment} environment`,
            deployOptions: {
                stageName: props.environment,
                throttlingRateLimit: 1000,
                throttlingBurstLimit: 2000,
                // Enable X-Ray tracing
                tracingEnabled: true,
                // Enable CloudWatch Logs
                dataTraceEnabled: true,
                loggingLevel: apigateway.MethodLoggingLevel.INFO,
            },
            // Enable CORS
            defaultCorsPreflightOptions: {
                allowOrigins: apigateway.Cors.ALL_ORIGINS,
                allowMethods: apigateway.Cors.ALL_METHODS,
            },
        });

        // Add resources and methods
        const items = this.api.root.addResource('items');
        items.addMethod('GET', new apigateway.LambdaIntegration(apiFunction));
        items.addMethod('POST', new apigateway.LambdaIntegration(apiFunction));

        const item = items.addResource('{id}');
        item.addMethod('GET', new apigateway.LambdaIntegration(apiFunction));
        item.addMethod('PUT', new apigateway.LambdaIntegration(apiFunction));
        item.addMethod('DELETE', new apigateway.LambdaIntegration(apiFunction));

        // CloudFormation outputs
        new cdk.CfnOutput(this, 'ApiUrl', {
            value: this.api.url,
            description: 'API Gateway endpoint URL',
            exportName: `${props.environment}-api-url`,
        });

        new cdk.CfnOutput(this, 'TableName', {
            value: this.table.tableName,
            description: 'DynamoDB table name',
            exportName: `${props.environment}-table-name`,
        });
    }
}
```

#### Custom L3 Construct (Reusable Pattern Library)

```typescript
// lib/constructs/static-website.ts
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

export interface StaticWebsiteProps {
    domainName: string;
    certificateArn: string;
    sourceAssetPath: string;
    environment: string;
}

export class StaticWebsite extends Construct {
    public readonly bucket: s3.Bucket;
    public readonly distribution: cloudfront.Distribution;
    public readonly domainName: string;

    constructor(scope: Construct, id: string, props: StaticWebsiteProps) {
        super(scope, id);

        // S3 bucket for website content
        this.bucket = new s3.Bucket(this, 'WebsiteBucket', {
            bucketName: `${props.environment}-${props.domainName.replace(/\./g, '-')}`,
            // Block all public access (CloudFront uses OAI)
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            encryption: s3.BucketEncryption.S3_MANAGED,
            versioned: true,
            removalPolicy: props.environment === 'prod'
                ? cdk.RemovalPolicy.RETAIN
                : cdk.RemovalPolicy.DESTROY,
            autoDeleteObjects: props.environment !== 'prod',
            lifecycleRules: [
                {
                    // Delete old versions after 90 days
                    noncurrentVersionExpiration: cdk.Duration.days(90),
                },
            ],
        });

        // Import existing certificate
        const certificate = acm.Certificate.fromCertificateArn(
            this,
            'Certificate',
            props.certificateArn
        );

        // CloudFront distribution
        this.distribution = new cloudfront.Distribution(this, 'Distribution', {
            defaultBehavior: {
                origin: new origins.S3Origin(this.bucket),
                viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                compress: true,
            },
            domainNames: [props.domainName],
            certificate: certificate,
            minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            defaultRootObject: 'index.html',
            errorResponses: [
                {
                    httpStatus: 404,
                    responseHttpStatus: 200,
                    responsePagePath: '/index.html',
                    // SPA routing support
                    ttl: cdk.Duration.minutes(5),
                },
            ],
            enableLogging: true,
            comment: `${props.environment} - ${props.domainName}`,
        });

        // Deploy website content to S3
        new s3deploy.BucketDeployment(this, 'DeployWebsite', {
            sources: [s3deploy.Source.asset(props.sourceAssetPath)],
            destinationBucket: this.bucket,
            distribution: this.distribution,
            distributionPaths: ['/*'],
            // Cache control headers
            cacheControl: [
                s3deploy.CacheControl.setPublic(),
                s3deploy.CacheControl.maxAge(cdk.Duration.hours(1)),
            ],
        });

        this.domainName = props.domainName;

        // Outputs
        new cdk.CfnOutput(this, 'DistributionDomainName', {
            value: this.distribution.distributionDomainName,
            description: 'CloudFront distribution domain name',
        });

        new cdk.CfnOutput(this, 'BucketName', {
            value: this.bucket.bucketName,
            description: 'S3 bucket name',
        });
    }
}
```

### 3. Multi-Cloud Abstractions with Pulumi

```typescript
// Multi-cloud Kubernetes cluster abstraction
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as eks from "@pulumi/eks";
import * as gcp from "@pulumi/gcp";
import * as k8s from "@pulumi/kubernetes";

export interface CloudKubernetesClusterArgs {
    provider: "aws" | "gcp";
    name: string;
    version: string;
    nodeCount: number;
    nodeInstanceType: string;
    environment: string;
}

export class CloudKubernetesCluster extends pulumi.ComponentResource {
    public readonly kubeconfig: pulumi.Output<string>;
    public readonly clusterName: pulumi.Output<string>;
    public readonly provider: k8s.Provider;

    constructor(name: string, args: CloudKubernetesClusterArgs, opts?: pulumi.ComponentResourceOptions) {
        super("custom:k8s:CloudKubernetesCluster", name, {}, opts);

        if (args.provider === "aws") {
            // Create EKS cluster
            const cluster = new eks.Cluster(`${name}-eks`, {
                name: `${args.environment}-${args.name}`,
                version: args.version,
                instanceType: args.nodeInstanceType,
                desiredCapacity: args.nodeCount,
                minSize: args.nodeCount,
                maxSize: args.nodeCount * 2,
                // Enable OIDC for IRSA
                createOidcProvider: true,
                // Managed node group for simplicity
                nodeAmiId: undefined, // Use EKS-optimized AMI
                tags: {
                    Environment: args.environment,
                    ManagedBy: "pulumi",
                    Provider: "aws",
                },
            }, { parent: this });

            this.kubeconfig = cluster.kubeconfig;
            this.clusterName = cluster.eksCluster.name;
            this.provider = cluster.provider;

        } else if (args.provider === "gcp") {
            // Create GKE cluster
            const cluster = new gcp.container.Cluster(`${name}-gke`, {
                name: `${args.environment}-${args.name}`,
                location: "us-central1",
                initialNodeCount: 1,
                minMasterVersion: args.version,
                // Autopilot mode for managed experience
                enableAutopilot: false,
                nodeConfig: {
                    machineType: args.nodeInstanceType,
                    oauthScopes: [
                        "https://www.googleapis.com/auth/cloud-platform",
                    ],
                },
                // Enable Workload Identity
                workloadIdentityConfig: {
                    workloadPool: `${gcp.config.project}.svc.id.goog`,
                },
                resourceLabels: {
                    environment: args.environment,
                    managedby: "pulumi",
                    provider: "gcp",
                },
            }, { parent: this });

            // Get cluster credentials
            const clusterAuth = gcp.container.getClusterOutput({
                name: cluster.name,
                location: cluster.location,
            });

            this.kubeconfig = pulumi.all([
                cluster.name,
                cluster.endpoint,
                cluster.masterAuth,
            ]).apply(([name, endpoint, auth]) => {
                return JSON.stringify({
                    apiVersion: "v1",
                    kind: "Config",
                    clusters: [{
                        name: name,
                        cluster: {
                            server: `https://${endpoint}`,
                            "certificate-authority-data": auth.clusterCaCertificate,
                        },
                    }],
                    contexts: [{
                        name: name,
                        context: { cluster: name, user: name },
                    }],
                    "current-context": name,
                    users: [{
                        name: name,
                        user: { "auth-provider": { name: "gcp" } },
                    }],
                });
            });

            this.clusterName = cluster.name;
            this.provider = new k8s.Provider(`${name}-k8s-provider`, {
                kubeconfig: this.kubeconfig,
            }, { parent: this });
        }

        this.registerOutputs({
            kubeconfig: this.kubeconfig,
            clusterName: this.clusterName,
        });
    }
}
```

### 4. AI-Assisted Generation and Validation Patterns

**Context (2026)**: AI-generated infrastructure code requires rigorous validation to prevent deployment of syntactically valid but semantically incorrect or insecure configurations. Industry benchmarks show <20% pass@1 rates for complex compositional requirements, making multi-phase validation critical.

#### Two-Phase Validation Pipeline

```typescript
// validation/validate-infrastructure.ts
import * as pulumi from "@pulumi/pulumi/automation";
import { execSync } from "child_process";
import * as fs from "fs";

/**
 * Phase 1: Technical Validation
 * Validates syntax, resource types, and dependency correctness
 */
async function technicalValidation(stackDir: string): Promise<ValidationResult> {
    const results: ValidationResult = {
        phase: "technical",
        passed: true,
        errors: [],
    };

    try {
        // 1. Pulumi preview for syntax and resource validation
        const stack = await pulumi.LocalWorkspace.createOrSelectStack({
            stackName: "validation",
            workDir: stackDir,
        });

        const previewResult = await stack.preview();

        // Check for errors in preview
        if (previewResult.changeSummary && previewResult.changeSummary.same === 0) {
            results.errors.push({
                type: "preview_failure",
                message: "Pulumi preview detected errors in resource definitions",
                severity: "high",
            });
            results.passed = false;
        }

        // 2. Validate against provider schemas (hallucination detection)
        const schemaValidation = await validateResourceSchemas(stackDir);
        if (!schemaValidation.valid) {
            results.errors.push({
                type: "schema_violation",
                message: "Resources use non-existent properties or invalid types",
                details: schemaValidation.errors,
                severity: "high",
            });
            results.passed = false;
        }

        // 3. Dependency graph analysis
        const dagValidation = validateDependencyGraph(previewResult);
        if (!dagValidation.valid) {
            results.errors.push({
                type: "circular_dependency",
                message: "Circular dependencies detected in resource graph",
                details: dagValidation.cycles,
                severity: "high",
            });
            results.passed = false;
        }

    } catch (error) {
        results.passed = false;
        results.errors.push({
            type: "technical_error",
            message: `Technical validation failed: ${error}`,
            severity: "high",
        });
    }

    return results;
}

/**
 * Phase 2: Intent Validation
 * Validates infrastructure against organizational policies and security requirements
 */
async function intentValidation(
    stackDir: string,
    policyDir: string
): Promise<ValidationResult> {
    const results: ValidationResult = {
        phase: "intent",
        passed: true,
        errors: [],
    };

    try {
        // 1. Run CrossGuard policies (Pulumi native)
        const policyPackPath = `${policyDir}/crossguard`;
        if (fs.existsSync(policyPackPath)) {
            execSync(
                `pulumi preview --policy-pack ${policyPackPath}`,
                { cwd: stackDir, stdio: "pipe" }
            );
        }

        // 2. Run OPA/Rego policies for semantic validation
        const opaValidation = await validateWithOPA(stackDir, policyDir);
        if (!opaValidation.valid) {
            results.errors.push({
                type: "policy_violation",
                message: "Infrastructure violates organizational policies",
                details: opaValidation.violations,
                severity: "high",
            });
            results.passed = false;
        }

        // 3. Security baseline validation
        const securityValidation = await validateSecurityBaseline(stackDir);
        if (!securityValidation.valid) {
            results.errors.push({
                type: "security_violation",
                message: "Security requirements not met",
                details: securityValidation.findings,
                severity: "critical",
            });
            results.passed = false;
        }

    } catch (error) {
        results.passed = false;
        results.errors.push({
            type: "intent_error",
            message: `Intent validation failed: ${error}`,
            severity: "high",
        });
    }

    return results;
}

interface ValidationResult {
    phase: "technical" | "intent";
    passed: boolean;
    errors: Array<{
        type: string;
        message: string;
        details?: any;
        severity: "low" | "medium" | "high" | "critical";
    }>;
}
```

#### OPA/Rego Policy Example

```rego
# validation/policies/require-encryption.rego
package pulumi.validation

# Deny S3 buckets without server-side encryption
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:s3/bucket:Bucket"
    not resource.properties.serverSideEncryptionConfiguration

    msg := sprintf("S3 bucket '%s' must have server-side encryption enabled", [resource.name])
}

# Deny DynamoDB tables without encryption at rest
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:dynamodb/table:Table"
    not resource.properties.serverSideEncryption

    msg := sprintf("DynamoDB table '%s' must have encryption at rest enabled", [resource.name])
}

# Deny RDS instances without encryption
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/instance:Instance"
    not resource.properties.storageEncrypted == true

    msg := sprintf("RDS instance '%s' must have storage encryption enabled", [resource.name])
}

# Require backup retention for production RDS
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/instance:Instance"
    environment := resource.properties.tags.Environment
    environment == "prod"
    backup_retention := resource.properties.backupRetentionPeriod
    backup_retention < 7

    msg := sprintf("Production RDS instance '%s' must have backup retention >= 7 days", [resource.name])
}
```

#### Brownfield Context Injection

```typescript
// generation/brownfield-context.ts
import * as pulumi from "@pulumi/pulumi/automation";
import * as aws from "@pulumi/aws";

/**
 * Inject existing infrastructure context for AI-assisted generation
 * Prevents LLM assumption of clean environment causing resource conflicts
 */
export async function buildBrownfieldContext(
    stackName: string,
    projectDir: string
): Promise<BrownfieldContext> {
    const stack = await pulumi.LocalWorkspace.selectStack({
        stackName: stackName,
        workDir: projectDir,
    });

    // Read existing state file
    const stackState = await stack.exportStack();

    // Extract deployed resources
    const deployedResources = stackState.deployment?.resources || [];

    // Build resource inventory
    const context: BrownfieldContext = {
        existingVpcs: [],
        existingSubnets: [],
        existingSecurityGroups: [],
        existingIamRoles: [],
        resourceTags: new Map(),
        dependencies: [],
    };

    // Parse existing resources
    for (const resource of deployedResources) {
        switch (resource.type) {
            case "aws:ec2/vpc:Vpc":
                context.existingVpcs.push({
                    id: resource.id,
                    cidrBlock: resource.outputs?.cidrBlock,
                    tags: resource.outputs?.tags,
                });
                break;

            case "aws:ec2/subnet:Subnet":
                context.existingSubnets.push({
                    id: resource.id,
                    vpcId: resource.outputs?.vpcId,
                    cidrBlock: resource.outputs?.cidrBlock,
                    availabilityZone: resource.outputs?.availabilityZone,
                });
                break;

            case "aws:ec2/securityGroup:SecurityGroup":
                context.existingSecurityGroups.push({
                    id: resource.id,
                    vpcId: resource.outputs?.vpcId,
                    rules: resource.outputs?.ingress,
                });
                break;
        }

        // Extract dependencies
        if (resource.dependencies && resource.dependencies.length > 0) {
            context.dependencies.push({
                resource: resource.urn,
                dependsOn: resource.dependencies,
            });
        }
    }

    return context;
}

export interface BrownfieldContext {
    existingVpcs: Array<{ id: string; cidrBlock?: string; tags?: any }>;
    existingSubnets: Array<{ id: string; vpcId?: string; cidrBlock?: string; availabilityZone?: string }>;
    existingSecurityGroups: Array<{ id: string; vpcId?: string; rules?: any }>;
    existingIamRoles: Array<{ arn: string; name: string; policies?: string[] }>;
    resourceTags: Map<string, any>;
    dependencies: Array<{ resource: string; dependsOn: string[] }>;
}

/**
 * Format context for AI prompt injection
 */
export function formatContextForPrompt(context: BrownfieldContext): string {
    return `
EXISTING INFRASTRUCTURE CONTEXT:

VPCs (${context.existingVpcs.length}):
${context.existingVpcs.map(vpc => `- ${vpc.id}: ${vpc.cidrBlock}`).join('\n')}

Subnets (${context.existingSubnets.length}):
${context.existingSubnets.map(subnet => `- ${subnet.id} in ${subnet.vpcId} (${subnet.cidrBlock})`).join('\n')}

Security Groups (${context.existingSecurityGroups.length}):
${context.existingSecurityGroups.map(sg => `- ${sg.id} in ${sg.vpcId}`).join('\n')}

IMPORTANT:
- Reuse existing VPC ${context.existingVpcs[0]?.id} instead of creating new one
- Use existing subnets for resource placement
- Reference existing security groups where appropriate
- Follow established tagging conventions: ${JSON.stringify(context.resourceTags)}
`;
}
```

### 5. Testing Infrastructure Code

#### Pulumi Unit Tests (TypeScript + Jest)

```typescript
// __tests__/network.test.ts
import * as pulumi from "@pulumi/pulumi";
import { NetworkComponent } from "../components/network";

// Mock Pulumi runtime
pulumi.runtime.setMocks({
    newResource: (args: pulumi.runtime.MockResourceArgs): { id: string; state: any } => {
        return {
            id: `${args.name}_id`,
            state: args.inputs,
        };
    },
    call: (args: pulumi.runtime.MockCallArgs) => {
        return args.inputs;
    },
});

describe("NetworkComponent", () => {
    let network: NetworkComponent;

    beforeAll(() => {
        // Create component
        network = new NetworkComponent("test-network", {
            cidrBlock: "10.0.0.0/16",
            availabilityZones: ["us-east-1a", "us-east-1b"],
            environment: "test",
            enableNatGateway: true,
        });
    });

    it("creates VPC with correct CIDR block", (done) => {
        pulumi.all([network.vpcId]).apply(([vpcId]) => {
            expect(vpcId).toBeDefined();
            expect(vpcId).toContain("_id");
            done();
        });
    });

    it("creates public and private subnets", (done) => {
        pulumi.all([
            network.publicSubnetIds,
            network.privateSubnetIds,
        ]).apply(([publicSubnets, privateSubnets]) => {
            expect(publicSubnets).toHaveLength(2);
            expect(privateSubnets).toHaveLength(2);
            done();
        });
    });

    it("tags resources with environment", (done) => {
        // Test that component properly tags resources
        pulumi.all([network.vpcId]).apply(() => {
            // Verify tagging logic
            done();
        });
    });

    // AI-generation validation test
    it("validates input parameters to prevent hallucinated values", () => {
        expect(() => {
            new NetworkComponent("invalid-network", {
                cidrBlock: "invalid-cidr", // Invalid format
                availabilityZones: ["us-east-1a"],
                environment: "test",
            });
        }).toThrow("Invalid CIDR block format");

        expect(() => {
            new NetworkComponent("invalid-network", {
                cidrBlock: "10.0.0.0/16",
                availabilityZones: ["us-east-1a"], // Only 1 AZ (requires 2+)
                environment: "test",
            });
        }).toThrow("At least 2 availability zones required");
    });
});
```

#### CDK Tests (TypeScript + Jest)

```typescript
// test/api-stack.test.ts
import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { ApiStack } from '../lib/api-stack';

describe('ApiStack', () => {
    let app: cdk.App;
    let stack: ApiStack;
    let template: Template;

    beforeEach(() => {
        app = new cdk.App();
        stack = new ApiStack(app, 'TestApiStack', {
            environment: 'test',
            tableName: 'test-table',
        });
        template = Template.fromStack(stack);
    });

    test('DynamoDB table created with correct properties', () => {
        template.hasResourceProperties('AWS::DynamoDB::Table', {
            BillingMode: 'PAY_PER_REQUEST',
            TableName: 'test-test-table',
            StreamSpecification: {
                StreamViewType: 'NEW_AND_OLD_IMAGES',
            },
        });
    });

    test('Lambda function has DynamoDB table environment variable', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Runtime: 'nodejs20.x',
            Environment: Match.objectLike({
                Variables: Match.objectLike({
                    TABLE_NAME: Match.anyValue(),
                    ENVIRONMENT: 'test',
                }),
            }),
        });
    });

    test('API Gateway created with correct stage', () => {
        template.hasResourceProperties('AWS::ApiGateway::RestApi', {
            Name: 'test-api',
        });

        template.hasResourceProperties('AWS::ApiGateway::Stage', {
            StageName: 'test',
        });
    });

    test('Lambda has read/write permissions to DynamoDB table', () => {
        template.hasResourceProperties('AWS::IAM::Policy', {
            PolicyDocument: Match.objectLike({
                Statement: Match.arrayWith([
                    Match.objectLike({
                        Action: Match.arrayWith([
                            'dynamodb:BatchGetItem',
                            'dynamodb:GetItem',
                            'dynamodb:PutItem',
                            'dynamodb:UpdateItem',
                            'dynamodb:DeleteItem',
                        ]),
                        Effect: 'Allow',
                    }),
                ]),
            }),
        });
    });

    test('Stack creates CloudFormation outputs', () => {
        template.hasOutput('ApiUrl', {});
        template.hasOutput('TableName', {});
    });

    test('Production stack retains DynamoDB table on delete', () => {
        const prodApp = new cdk.App();
        const prodStack = new ApiStack(prodApp, 'ProdApiStack', {
            environment: 'prod',
            tableName: 'prod-table',
        });
        const prodTemplate = Template.fromStack(prodStack);

        prodTemplate.hasResource('AWS::DynamoDB::Table', {
            DeletionPolicy: 'Retain',
        });
    });
});
```

#### Matrix Testing for Multi-Language Support

```yaml
# .github/workflows/test-infrastructure.yml
name: Test Infrastructure Components

on:
  pull_request:
    paths:
      - 'components/**'
      - 'lib/**'
      - '__tests__/**'
      - 'test/**'

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: true
      matrix:
        language: [typescript, python, go]
        include:
          - language: typescript
            runtime: nodejs
            version: '20'
            test_command: 'npm test'
          - language: python
            runtime: python
            version: '3.11'
            test_command: 'pytest tests/'
          - language: go
            runtime: go
            version: '1.21'
            test_command: 'go test ./...'

    steps:
      - uses: actions/checkout@v4

      - name: Setup ${{ matrix.runtime }}
        uses: actions/setup-${{ matrix.runtime }}@v4
        with:
          ${{ matrix.runtime }}-version: ${{ matrix.version }}

      - name: Install dependencies
        run: |
          cd ${{ matrix.language }}
          if [ "${{ matrix.language }}" == "typescript" ]; then
            npm ci
          elif [ "${{ matrix.language }}" == "python" ]; then
            pip install -r requirements.txt
          elif [ "${{ matrix.language }}" == "go" ]; then
            go mod download
          fi

      - name: Run tests
        run: |
          cd ${{ matrix.language }}
          ${{ matrix.test_command }}

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.language }}
          path: ${{ matrix.language }}/test-results/
```

### 6. Policy as Code (Validation)

#### Pulumi CrossGuard Policies

```typescript
// policies/index.ts
import * as pulumi from "@pulumi/policy";

const stackValidation = new pulumi.PolicyPack("stack-validation", {
    policies: [
        {
            name: "require-tags",
            description: "All resources must have required tags for governance and cost tracking",
            enforcementLevel: "mandatory",
            validateResource: (args, reportViolation) => {
                const requiredTags = ["Environment", "ManagedBy", "Project"];

                if (args.type.startsWith("aws:")) {
                    const tags = args.props.tags || {};
                    const missingTags = requiredTags.filter(tag => !(tag in tags));

                    if (missingTags.length > 0) {
                        reportViolation(
                            `Resource missing required tags: ${missingTags.join(", ")}`
                        );
                    }
                }
            },
        },
        {
            name: "s3-bucket-encryption",
            description: "S3 buckets must have server-side encryption enabled",
            enforcementLevel: "mandatory",
            validateResource: (args, reportViolation) => {
                if (args.type === "aws:s3/bucket:Bucket") {
                    const encryption = args.props.serverSideEncryptionConfiguration;
                    if (!encryption) {
                        reportViolation(
                            "S3 bucket must have server-side encryption enabled"
                        );
                    }
                }
            },
        },
        {
            name: "no-public-s3-buckets",
            description: "S3 buckets cannot be publicly accessible",
            enforcementLevel: "mandatory",
            validateResource: (args, reportViolation) => {
                if (args.type === "aws:s3/bucket:Bucket") {
                    const acl = args.props.acl;
                    if (acl === "public-read" || acl === "public-read-write") {
                        reportViolation(
                            "S3 bucket cannot have public ACL"
                        );
                    }
                }
            },
        },
        {
            name: "require-iam-role-description",
            description: "IAM roles must have meaningful descriptions for audit purposes",
            enforcementLevel: "advisory",
            validateResource: (args, reportViolation) => {
                if (args.type === "aws:iam/role:Role") {
                    const description = args.props.description;
                    if (!description || description.length < 10) {
                        reportViolation(
                            "IAM role should have a meaningful description (minimum 10 characters)"
                        );
                    }
                }
            },
        },
        {
            name: "require-rds-backup",
            description: "RDS instances must have automated backups enabled with minimum retention",
            enforcementLevel: "mandatory",
            validateResource: (args, reportViolation) => {
                if (args.type === "aws:rds/instance:Instance") {
                    const backupRetention = args.props.backupRetentionPeriod;
                    if (!backupRetention || backupRetention < 7) {
                        reportViolation(
                            "RDS instance must have backup retention period of at least 7 days"
                        );
                    }
                }
            },
        },
        {
            name: "validate-resource-names",
            description: "Detect hallucinated or malformed resource names that may indicate AI generation errors",
            enforcementLevel: "advisory",
            validateResource: (args, reportViolation) => {
                const name = args.name;

                // Check for common hallucination patterns
                if (name.includes("PLACEHOLDER") || name.includes("FIXME") || name.includes("TODO")) {
                    reportViolation(
                        `Resource name '${name}' contains placeholder text indicating incomplete generation`
                    );
                }

                // Check for suspiciously generic names
                if (name === "resource" || name === "default" || name === "example") {
                    reportViolation(
                        `Resource name '${name}' is too generic and may not reflect actual purpose`
                    );
                }
            },
        },
    ],
});
```

#### CDK Aspects for Validation (cdk-nag)

```typescript
// bin/app.ts
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions } from 'cdk-nag';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();

const apiStack = new ApiStack(app, 'ApiStack', {
    environment: 'prod',
    tableName: 'api-table',
    env: {
        account: process.env.CDK_DEFAULT_ACCOUNT,
        region: process.env.CDK_DEFAULT_REGION,
    },
});

// Apply AWS Solutions security checks
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

// Suppress specific findings with justification (document why)
NagSuppressions.addStackSuppressions(apiStack, [
    {
        id: 'AwsSolutions-IAM4',
        reason: 'Using AWS managed policies for standard Lambda execution role - acceptable for this use case',
    },
]);

app.synth();
```

### 7. Automation API (Programmatic Deployment)

```typescript
// automation/deploy.ts
import * as pulumi from "@pulumi/pulumi/automation";
import * as path from "path";

async function deployStack(
    stackName: string,
    projectName: string,
    config: Record<string, string>
): Promise<void> {
    const stackDir = path.join(__dirname, "..", "infrastructure");

    // Create or select stack
    const stack = await pulumi.LocalWorkspace.createOrSelectStack({
        stackName: stackName,
        projectName: projectName,
        workDir: stackDir,
    });

    console.log(`Stack: ${stackName}`);

    // Set configuration
    for (const [key, value] of Object.entries(config)) {
        await stack.setConfig(key, { value: value });
    }

    // Install dependencies
    console.log("Installing dependencies...");
    await stack.workspace.installPluginDependencies();

    // Run preview
    console.log("Running preview...");
    const previewResult = await stack.preview({ onOutput: console.log });
    console.log(`Preview result: ${JSON.stringify(previewResult.changeSummary)}`);

    // Run update
    console.log("Running update...");
    const upResult = await stack.up({ onOutput: console.log });

    console.log(`Update summary: ${JSON.stringify(upResult.summary.resourceChanges)}`);
    console.log(`Outputs: ${JSON.stringify(upResult.outputs, null, 2)}`);
}

// Usage
deployStack("dev", "infrastructure", {
    "aws:region": "us-east-1",
    "vpcCidr": "10.0.0.0/16",
    "azs": JSON.stringify(["us-east-1a", "us-east-1b", "us-east-1c"]),
}).catch(err => {
    console.error(err);
    process.exit(1);
});
```

### 8. GitOps Integration Patterns

#### Pulumi with GitHub Actions (OIDC + Multi-Cloud)

```yaml
# .github/workflows/pulumi.yml
name: Pulumi Deploy

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

permissions:
  id-token: write  # Required for OIDC token generation
  contents: read
  pull-requests: write  # For preview comments

jobs:
  preview:
    name: Preview Changes
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      # AWS OIDC Authentication (no long-lived credentials)
      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          role-session-name: pulumi-preview-session
          aws-region: us-east-1

      # GCP OIDC Authentication
      - name: Authenticate to Google Cloud (OIDC)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'pulumi-deploy@project-id.iam.gserviceaccount.com'

      - name: Install dependencies
        working-directory: infrastructure
        run: npm install

      - name: Pulumi Preview
        uses: pulumi/actions@v5
        with:
          command: preview
          stack-name: dev
          work-dir: infrastructure
          comment-on-pr: true
          github-token: ${{ secrets.GITHUB_TOKEN }}
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}

      # Run AI-validation pipeline
      - name: Validate AI-Generated Code
        working-directory: infrastructure
        run: |
          npm run validate:technical
          npm run validate:intent

  deploy:
    name: Deploy to Multi-Cloud
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: production
      url: ${{ steps.pulumi.outputs.apiUrl }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      # Multi-cloud OIDC authentication
      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          role-session-name: pulumi-deploy-session
          aws-region: us-east-1

      - name: Authenticate to Google Cloud (OIDC)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'pulumi-deploy@project-id.iam.gserviceaccount.com'

      - name: Install dependencies
        working-directory: infrastructure
        run: npm install

      - name: Pulumi Up
        id: pulumi
        uses: pulumi/actions@v5
        with:
          command: up
          stack-name: prod
          work-dir: infrastructure
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}

      - name: Output Summary
        run: |
          echo "API URL: ${{ steps.pulumi.outputs.apiUrl }}"
          echo "Deployment completed successfully"
```

#### IAM Trust Policy for OIDC (Restrictive)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:my-org/my-repo:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

#### CDK with CDK Pipelines (Self-Mutating)

```typescript
// lib/pipeline-stack.ts
import * as cdk from 'aws-cdk-lib';
import * as pipelines from 'aws-cdk-lib/pipelines';
import { Construct } from 'constructs';
import { ApiStack } from './api-stack';

export class PipelineStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // GitHub source
        const source = pipelines.CodePipelineSource.gitHub(
            'org/repo',
            'main',
            {
                authentication: cdk.SecretValue.secretsManager('github-token'),
            }
        );

        // CDK Pipeline
        const pipeline = new pipelines.CodePipeline(this, 'Pipeline', {
            pipelineName: 'ApiPipeline',
            synth: new pipelines.ShellStep('Synth', {
                input: source,
                commands: [
                    'npm ci',
                    'npm run build',
                    'npx cdk synth',
                ],
            }),
            // Self-mutation: pipeline updates itself
            selfMutation: true,
            // Enable Docker support
            dockerEnabledForSynth: true,
        });

        // Add development stage
        const devStage = new PipelineStage(this, 'Dev', {
            environment: 'dev',
            env: {
                account: '111111111111',
                region: 'us-east-1',
            },
        });
        pipeline.addStage(devStage);

        // Add production stage with manual approval
        const prodStage = new PipelineStage(this, 'Prod', {
            environment: 'prod',
            env: {
                account: '222222222222',
                region: 'us-east-1',
            },
        });
        pipeline.addStage(prodStage, {
            pre: [
                new pipelines.ManualApprovalStep('PromoteToProd'),
            ],
            post: [
                new pipelines.ShellStep('IntegrationTests', {
                    envFromCfnOutputs: {
                        API_URL: prodStage.apiUrl,
                    },
                    commands: [
                        'npm run test:integration',
                    ],
                }),
            ],
        });
    }
}

class PipelineStage extends cdk.Stage {
    public readonly apiUrl: cdk.CfnOutput;

    constructor(scope: Construct, id: string, props: cdk.StageProps & { environment: string }) {
        super(scope, id, props);

        const apiStack = new ApiStack(this, 'ApiStack', {
            environment: props.environment,
            tableName: 'api-table',
        });

        this.apiUrl = apiStack.api.urlForPath('/');
    }
}
```

#### GitLab CI/CD with DAG Pipelines

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - test
  - build
  - deploy

variables:
  PULUMI_ACCESS_TOKEN: $PULUMI_ACCESS_TOKEN
  AWS_REGION: us-east-1

# Technical validation (runs immediately)
validate:technical:
  stage: validate
  image: pulumi/pulumi:latest
  script:
    - cd infrastructure
    - npm install
    - pulumi preview --stack dev
    - npm run validate:schemas
  rules:
    - changes:
        - infrastructure/**/*

# Intent validation (runs in parallel with technical)
validate:intent:
  stage: validate
  image: openpolicyagent/opa:latest
  script:
    - cd infrastructure
    - opa test policies/
  rules:
    - changes:
        - infrastructure/**/*
        - policies/**/*

# Unit tests (starts after validation using needs)
test:unit:
  stage: test
  image: node:20
  needs: ["validate:technical", "validate:intent"]
  script:
    - cd infrastructure
    - npm ci
    - npm test
  rules:
    - changes:
        - infrastructure/**/*

# Component build (parallel with tests)
build:components:
  stage: build
  image: node:20
  needs: ["validate:technical"]
  script:
    - cd components
    - npm ci
    - npm run build
  artifacts:
    paths:
      - components/dist/
  rules:
    - changes:
        - components/**/*

# Deploy to dev (needs both test and build)
deploy:dev:
  stage: deploy
  image: pulumi/pulumi:latest
  needs: ["test:unit", "build:components"]
  script:
    - cd infrastructure
    - pulumi up --stack dev --yes
  environment:
    name: dev
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# Deploy to prod (needs dev deployment + manual approval)
deploy:prod:
  stage: deploy
  image: pulumi/pulumi:latest
  needs: ["deploy:dev"]
  script:
    - cd infrastructure
    - pulumi up --stack prod --yes
  environment:
    name: production
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Security Best Practices

### ✅ Required Security Practices

- **Secret Management**: Use Pulumi ESC or AWS Secrets Manager, never hardcode secrets
- **IAM Least Privilege**: Use CDK `.grant*` methods or Pulumi managed policies for minimal permissions
- **Encryption at Rest**: Enable encryption for S3, DynamoDB, RDS, EBS volumes
- **Encryption in Transit**: Use TLS/HTTPS for all network communication
- **Resource Tagging**: Tag all resources with Environment, ManagedBy, Project for governance
- **Version Pinning**: Pin provider/library versions in production (package.json, Pulumi.yaml)
- **State File Security**: Use Pulumi Service or CDK Toolkit with encrypted S3 backend
- **Network Segmentation**: Use VPC, security groups, NACLs with default-deny policies
- **Audit Logging**: Enable CloudTrail, VPC Flow Logs, S3 access logging
- **Policy Validation**: Use CrossGuard or cdk-nag to enforce security policies
- **OIDC Authentication**: Use OIDC for CI/CD instead of long-lived credentials
- **AI Generation Validation**: Implement two-phase validation (technical + intent) for all AI-generated code
- **Hallucination Detection**: Validate resource types against official provider schemas
- **Brownfield Context**: Inject existing infrastructure state before generating new resources

### ✅ Validation Commands

```bash
# Pulumi validation
pulumi preview --policy-pack policies/  # Validate against CrossGuard policies
pulumi preview --diff                   # Show detailed resource changes
pulumi stack output --json              # Validate outputs

# AI-generation validation
npm run validate:technical              # Phase 1: Technical validation
npm run validate:intent                 # Phase 2: Intent validation (OPA)
npm run validate:hallucination          # Check for fabricated resources

# CDK validation
cdk diff                                # Show changes before deploy
cdk synth --validation                  # Synthesize with validation
npm test                                # Run unit tests
npx cdk-nag check                       # Security scanning

# Test infrastructure code
npm test                                # Jest tests for both Pulumi and CDK
```

## Anti-Patterns to Avoid

### ❌ Common Mistakes

1. **Hardcoded secrets in code**:
   ```typescript
   // WRONG: Hardcoded credentials
   const db = new aws.rds.Instance("db", {
       password: "hardcoded-password-123",
   });
   ```

   **FIX**: Use secret management:
   ```typescript
   // Use Pulumi ESC
   const dbPassword = process.env.DB_PASSWORD!;

   const db = new aws.rds.Instance("db", {
       password: dbPassword,
   });
   ```

2. **No resource tagging**:
   ```typescript
   // WRONG: No tags for governance
   const bucket = new aws.s3.Bucket("bucket", {});
   ```

   **FIX**: Always tag resources:
   ```typescript
   const bucket = new aws.s3.Bucket("bucket", {
       tags: {
           Environment: pulumi.getStack(),
           ManagedBy: "pulumi",
           Project: pulumi.getProject(),
       },
   });
   ```

3. **Over-privileged IAM policies**:
   ```typescript
   // WRONG: Wildcard permissions
   const policy = new aws.iam.Policy("policy", {
       policy: JSON.stringify({
           Version: "2012-10-17",
           Statement: [{
               Effect: "Allow",
               Action: "*",
               Resource: "*",
           }],
       }),
   });
   ```

   **FIX**: Use least-privilege with specific permissions:
   ```typescript
   // Use managed grants (CDK/Pulumi)
   table.grantReadWriteData(lambda);

   // Or specific permissions
   const policy = new aws.iam.Policy("policy", {
       policy: JSON.stringify({
           Version: "2012-10-17",
           Statement: [{
               Effect: "Allow",
               Action: [
                   "dynamodb:GetItem",
                   "dynamodb:PutItem",
               ],
               Resource: table.arn,
           }],
       }),
   });
   ```

4. **No testing of infrastructure code**:
   ```typescript
   // WRONG: No tests, manual validation only
   ```

   **FIX**: Write unit tests and integration tests:
   ```typescript
   // __tests__/infrastructure.test.ts
   describe("Infrastructure", () => {
       it("creates resources with correct configuration", () => {
           // Test using Pulumi mocks or CDK assertions
       });
   });
   ```

5. **Mixing environments in single stack**:
   ```typescript
   // WRONG: Single stack for all environments
   const isProd = process.env.ENV === "prod";
   ```

   **FIX**: Use separate stacks per environment:
   ```typescript
   // Pulumi stacks: dev, staging, prod
   const environment = pulumi.getStack();

   // CDK stages
   new PipelineStage(app, "Dev", { environment: "dev" });
   new PipelineStage(app, "Prod", { environment: "prod" });
   ```

6. **No validation before deployment**:
   ```typescript
   // WRONG: Direct deployment without preview
   ```

   **FIX**: Always preview changes:
   ```bash
   pulumi preview  # Pulumi
   cdk diff        # CDK
   ```

7. **State file in local filesystem**:
   ```typescript
   // WRONG: Local state files not shared with team
   ```

   **FIX**: Use remote state:
   ```bash
   # Pulumi Service (default)
   pulumi login

   # Self-hosted backend
   pulumi login s3://my-pulumi-state-bucket

   # CDK Toolkit
   npx cdk bootstrap aws://ACCOUNT/REGION
   ```

8. **No rollback plan**:
   ```typescript
   // WRONG: No consideration for rollback
   ```

   **FIX**: Design for rollback:
   ```typescript
   // Use CDK RemovalPolicy
   const table = new dynamodb.Table(this, "Table", {
       removalPolicy: environment === "prod"
           ? cdk.RemovalPolicy.RETAIN
           : cdk.RemovalPolicy.DESTROY,
   });

   // Pulumi: use stack rollback
   // pulumi stack history
   // pulumi update --target-stack-checkpoint <checkpoint-id>
   ```

9. **Deploying AI-generated code without validation** (NEW):
   ```typescript
   // WRONG: Direct deployment of AI-generated infrastructure
   ```

   **FIX**: Implement two-phase validation:
   ```bash
   # Phase 1: Technical validation
   npm run validate:technical

   # Phase 2: Intent validation
   npm run validate:intent

   # Then deploy
   pulumi up
   ```

10. **Ignoring brownfield context in AI generation** (NEW):
    ```typescript
    // WRONG: Generating code assuming empty environment
    ```

    **FIX**: Inject existing state:
    ```typescript
    const context = await buildBrownfieldContext("prod", "./infrastructure");
    const prompt = formatContextForPrompt(context);
    // Use prompt with AI generation to respect existing resources
    ```

11. **Using long-lived credentials in CI/CD**:
    ```yaml
    # WRONG: Storing AWS access keys as secrets
    env:
      AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
      AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    ```

    **FIX**: Use OIDC authentication:
    ```yaml
    permissions:
      id-token: write
    steps:
      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          aws-region: us-east-1
    ```

## Integration with iac-team Agents

### With iac-generator Agent

When the `iac-generator` agent invokes this skill:

1. **Context**: Provide programming language preference (TypeScript, Python, Go), target cloud (AWS, GCP, multi-cloud)
2. **Framework**: Choose Pulumi for multi-cloud or CDK for AWS-native with higher-level abstractions
3. **Components**: Generate reusable ComponentResources (Pulumi) or L3 Constructs (CDK)
4. **Testing**: Include unit tests using language-native frameworks (Jest, pytest, Go testing)
5. **Validation**: Apply policy packs (CrossGuard, cdk-nag, OPA/Rego) ensuring security compliance
6. **GitOps**: Generate CI/CD workflows with OIDC authentication and preview/deploy stages
7. **AI Validation**: For AI-generated code, implement two-phase validation pipeline
8. **Brownfield Context**: When generating for existing infrastructure, inject state file context
9. **Hallucination Detection**: Validate all resource types against official provider schemas

### With iac-analyzer Agent

When `iac-analyzer` detects Pulumi/CDK code:

1. Identify programming language and framework version
2. Analyze component/construct reusability and abstraction patterns
3. Detect security issues (hardcoded secrets, overly permissive policies)
4. Flag missing tests or policy validation
5. Recommend multi-cloud abstractions where applicable
6. Validate state management configuration (remote backend, encryption)
7. Check for AI-generation artifacts (placeholder names, incomplete implementations)
8. Verify brownfield compatibility (no resource conflicts with existing infrastructure)
9. Assess hallucination risk (non-existent resource types, fabricated properties)

## Best Practices Summary

1. **Use ComponentResources (Pulumi) or custom L3 Constructs (CDK)** for reusable patterns
2. **Write unit tests** with language-native frameworks (Jest, pytest, Go testing)
3. **Apply policy validation** using CrossGuard, cdk-nag, or OPA/Rego before deployment
4. **Never hardcode secrets** - use Pulumi ESC, AWS Secrets Manager, or environment variables
5. **Tag all resources** with Environment, ManagedBy, Project for governance
6. **Use separate stacks/stages per environment** (dev, staging, prod)
7. **Implement preview before deployment** (pulumi preview, cdk diff)
8. **Use remote state backends** (Pulumi Service, S3 with encryption)
9. **Leverage OIDC** for CI/CD authentication instead of long-lived credentials
10. **Test infrastructure code** with multiple run blocks testing create/update/destroy
11. **Design for rollback** with RemovalPolicy and version control
12. **Use managed IAM grants** (`.grant*` methods) for least-privilege access
13. **Enable encryption** for all data at rest and in transit
14. **Version pin dependencies** in production (package.json, requirements.txt)
15. **Document components** with clear interfaces and usage examples
16. **Implement two-phase validation** for AI-generated infrastructure (technical + intent) **(NEW)**
17. **Validate against provider schemas** to detect hallucinated resource types **(NEW)**
18. **Inject brownfield context** before generating code for existing environments **(NEW)**
19. **Use matrix testing** for multi-language component validation **(NEW)**
20. **Maintain audit trails** for AI-generated infrastructure changes **(NEW)**

## References

For comprehensive patterns and advanced techniques, see:

- **Pulumi Documentation**: https://www.pulumi.com/docs/
- **Pulumi Examples**: https://github.com/pulumi/examples
- **Pulumi ESC**: https://www.pulumi.com/docs/esc/
- **Pulumi Automation API**: https://www.pulumi.com/docs/using-pulumi/automation-api/
- **CrossGuard Policies**: https://www.pulumi.com/docs/using-pulumi/crossguard/
- **AWS CDK Documentation**: https://docs.aws.amazon.com/cdk/
- **AWS CDK Examples**: https://github.com/aws-samples/aws-cdk-examples
- **CDK Constructs Hub**: https://constructs.dev/
- **CDK Testing**: https://docs.aws.amazon.com/cdk/v2/guide/testing.html
- **CDK Pipelines**: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.pipelines-readme.html
- **cdk-nag**: https://github.com/cdklabs/cdk-nag
- **CDKTF (CDK for Terraform)**: https://developer.hashicorp.com/terraform/cdktf
- **OPA/Rego**: https://www.openpolicyagent.org/docs/latest/policy-language/
- **GitHub Actions OIDC**: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-cloud-providers
- **GitLab CI/CD DAG Pipelines**: https://docs.gitlab.com/ee/ci/directed_acyclic_graph/

---

**Version**: 2.0.0
**Last Updated**: 2026-02-04
**Compatible With**: Pulumi 3.x, AWS CDK v2, Node.js 20+, Python 3.9+, Go 1.21+

*This skill is part of the iac-team plugin. For related capabilities, see: terraform-modules (HCL-based IaC), kubernetes-native (K8s YAML), aws-eks (AWS specifics), gcp-gke (GCP specifics), github-actions (CI/CD), security-validation (policy scanning).*
