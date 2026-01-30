# Multi-Resource Spec: IaC Team (Example)

> This is an example SPEC.md file for **multi-resource** CGF optimization.
> Unlike single-resource specs, this defines **requirements** for generating
> an entire plugin, skill set, or workflow with multiple coordinated components.
>
> Copy this template to your workspace directory and customize for your needs.

---

## Quick Start

1. Create a workspace directory: `mkdir -p workspace/my-plugin`
2. Copy this file: `cp docs/examples/MULTI_RESOURCE_SPEC.example.md workspace/my-plugin/SPEC.md`
3. Edit SPEC.md with your requirements (purpose, capabilities, constraints)
4. Run: `make optimize WORKSPACE=workspace/my-plugin`

The pipeline will:
1. **RESEARCH** - Determine optimal structure based on requirements
2. **Q&A** - Gather user input on structure decisions
3. **GENERATE** - Create resources based on research + user input
4. **ITERATE** - Agentic improvement of each resource until quality >= 0.85
5. **VALIDATE** - Cross-resource coherence check

---

## Purpose

Multi-agent plugin for Infrastructure-as-Code automation that can:
- Analyze existing repositories to understand structure and dependencies
- Generate containerization and deployment resources (Docker, K8s, Terraform)
- Validate security and best practices before deployment
- Support AWS and GCP cloud platforms

## Target Users

- Platform engineers adding IaC to existing applications
- DevOps teams standardizing deployment patterns
- Developers needing production-ready infrastructure templates

## Capabilities

### Core Workflows

1. **Repository Analysis** - Scan codebase, identify services, map dependencies
2. **Resource Generation** - Create Dockerfiles, K8s manifests, Terraform modules
3. **Security Validation** - Scan generated resources, ensure policy compliance
4. **CI/CD Integration** - GitHub Actions and GitLab CI pipeline generation

### Platform Support

- **AWS**: EKS, ECS, ECR, IRSA, AWS CLI operations
- **GCP**: GKE, Cloud Run, Artifact Registry, Workload Identity, gcloud CLI
- **GitOps**: ArgoCD, Flux patterns
- **IaC Tools**: Terraform, Helm, Kustomize, Crossplane, Pulumi/CDK

## Constraints

- Generated resources must pass security scanning (no CRITICAL/HIGH findings)
- Terraform modules under 300 lines each
- Code examples under 40 lines
- No hardcoded secrets in any generated resource
- Prefer OIDC over long-lived credentials for CI/CD

## Quality Criteria

| Metric | Target |
|--------|--------|
| Dockerfile build success | 100% |
| K8s manifest validation | Pass kubeconform |
| Terraform plan success | Zero errors |
| Helm lint | Pass --strict |

## Research Topics

> These topics guide the RESEARCH phase. The system will gather current
> best practices and incorporate them into generated resources.

- Kubernetes 1.31+ features (Gateway API, sidecar containers)
- Terraform 1.7+ patterns (testing framework, import blocks)
- GitHub Actions 2025 patterns (OIDC, reusable workflows)
- AI-assisted IaC best practices

## Proposed Structure (Optional)

> **This section is optional.** If provided, the RESEARCH phase will validate
> and may counter-propose a better structure during Q&A.

### Agents

- **iac-analyzer** - Repository analysis and dependency mapping
- **iac-generator** - Resource generation from analysis
- **iac-validator** - Security and policy validation

### Skills

- **kubernetes-native** - K8s manifest patterns
- **terraform-modules** - Terraform/OpenTofu patterns
- **github-actions** - CI/CD workflow patterns
- (additional skills to be determined by research)

### Commands

- **/iac** - Main entry point for IaC operations

---

## Alternative Formats

### Minimal Spec (Requirements Only)

If you don't want to propose structure, just describe what you need:

```markdown
# Multi-Resource Spec: IaC Team

## Purpose

Multi-agent plugin for Infrastructure-as-Code automation.

## Capabilities

- Repository analysis and dependency mapping
- Docker, K8s, Terraform resource generation
- Security validation
- CI/CD integration (GitHub Actions, GitLab CI)

## Constraints

- No hardcoded secrets
- Terraform modules < 300 lines
```

CGF will determine the optimal structure through research.

### Skill Set Spec (Multiple Related Skills)

For creating a set of related skills without agents:

```markdown
# Multi-Resource Spec: Terraform Modules

## Type

skill-set

## Purpose

Collection of Terraform skills for multi-cloud infrastructure.

## Capabilities

### AWS Module Skill
- VPC, EKS, RDS patterns
- IRSA configuration
- AWS-specific best practices

### GCP Module Skill
- VPC, GKE, Cloud SQL patterns
- Workload Identity configuration
- GCP-specific best practices

### Azure Module Skill
- VNet, AKS, Azure SQL patterns
- Managed Identity configuration
- Azure-specific best practices

## Constraints

- All modules must pass terraform validate
- Use terraform-docs for documentation
- Include examples/ directory per module
```

### Workflow Spec (Coordinated Agents)

For creating a multi-agent workflow pipeline:

```markdown
# Multi-Resource Spec: Research Pipeline

## Type

workflow

## Purpose

Multi-stage research pipeline with coordinated agents.

## Capabilities

### Stage 1: Discovery
- Agent: research-lead
- Analyzes topic, identifies sources
- Outputs: research-plan.yaml

### Stage 2: Investigation
- Agent: research-specialist (parallelizable)
- Deep-dives into assigned topics
- Outputs: findings/*.yaml

### Stage 3: Synthesis
- Agent: report-writer
- Combines findings into report
- Outputs: report.md

## Dependencies

- Stage 2 depends on Stage 1 output
- Stage 3 depends on all Stage 2 outputs
- Parallel execution of Stage 2 agents recommended
```

---

## Workspace Structure After Optimization

After running `make optimize`, your workspace will contain:

```
workspace/my-plugin/
├── SPEC.md                       # This file (requirements spec)
├── CHANGELOG.md                  # Human-readable optimization history
├── .claude-plugin/
│   └── plugin.json               # Generated plugin metadata
├── agents/
│   ├── iac-analyzer.md           # Generated agent
│   ├── iac-analyzer-v1.md        # Optimized version (if improved)
│   ├── iac-generator.md
│   └── iac-validator.md
├── skills/
│   ├── kubernetes-native/
│   │   └── SKILL.md
│   ├── terraform-modules/
│   │   └── SKILL.md
│   └── github-actions/
│       └── SKILL.md
├── commands/
│   └── iac.md
├── research/
│   ├── notes/
│   │   ├── kubernetes-patterns.yaml
│   │   └── terraform-patterns.yaml
│   ├── eval_criteria.yaml
│   ├── structure-recommendation.yaml  # Research-proposed structure
│   └── reviews/
│       └── coherence-report.md
└── sessions/
    ├── optimization-state.json    # Pipeline state (for resumption)
    ├── qa-decisions.json          # User decisions from Q&A
    └── *.summary.json             # Machine-readable summaries
```

### CHANGELOG.md

The `CHANGELOG.md` accumulates entries for each resource optimized:

```markdown
# CGF Multi-Resource Optimization: iac-team

**Spec:** SPEC.md
**Type:** plugin
**Started:** 2026-01-29
**Status:** IN_PROGRESS

---

## Current Progress

| Resource | Status | Quality | Version |
|----------|--------|---------|---------|
| agents/iac-analyzer | optimized | 0.92 | v2 |
| agents/iac-generator | in_progress | 0.78 | v1 |
| agents/iac-validator | pending | - | - |
| skills/kubernetes-native | pending | - | - |

---

## iac-analyzer (2026-01-29)

**Output:** agents/iac-analyzer-v2.md
**Quality:** 0.78 → 0.92

### Improvements
- Added AST-based dependency detection
- Improved monorepo support
- Enhanced service boundary detection

---

## iac-generator (2026-01-29)

**Output:** agents/iac-generator-v1.md
**Quality:** 0.78 (below threshold, iteration continues)

### Current State
- Basic Dockerfile generation working
- K8s manifests need multi-container support
- Terraform modules need variable extraction
```

---

## State Management

### Resumption

`make optimize` automatically resumes from the last phase:

| State File | When Present | Action |
|------------|--------------|--------|
| `sessions/optimization-state.json` | Continue from `current_phase` |
| Only `SPEC.md` | Start fresh with RESEARCH |

### Reset Strategies

- **Soft reset**: Delete `sessions/` → Restart from RESEARCH
- **Hard reset**: Delete everything except `SPEC.md` → Full restart
- **Selective reset**: Delete specific `research/` files → Re-run that research

### CLI Commands

```bash
# Check optimization status
make cgf-status

# Clean session state (keeps artifacts)
make cgf-clean

# Full reset (destructive)
make cgf-reset

# Resume with verbose output
make optimize WORKSPACE=workspace/my-plugin VERBOSE=true

# Skip to specific phase
make optimize WORKSPACE=workspace/my-plugin PHASE=ITERATE

# Force restart
make optimize WORKSPACE=workspace/my-plugin RESET=true
```

---

## Quality-Based Iteration

Each resource iterates until quality >= 0.85 (configurable):

```
┌─────────┐     ┌──────────┐     ┌─────────┐
│ GENERATE │ ──► │ EVALUATE │ ──► │ quality │
│    v0    │     │          │     │ >= 0.85 │
└─────────┘     └──────────┘     └────┬────┘
                     │                 │
                     │ < 0.85          │ >= 0.85
                     ▼                 ▼
              ┌──────────┐       ┌─────────┐
              │  ITERATE │       │  DONE   │
              │ improve  │       │         │
              └────┬─────┘       └─────────┘
                   │
                   │ max iterations?
                   ▼
              ┌──────────────┐
              │ ESCALATE to  │
              │ human review │
              └──────────────┘
```

### Quality Dimensions

| Dimension | Description | Weight |
|-----------|-------------|--------|
| **Completeness** | Covers all SPEC.md capabilities | 0.35 |
| **Accuracy** | Patterns/examples are correct and current | 0.35 |
| **Clarity** | Well-organized, clear instructions | 0.30 |

### Configuration

```bash
# In .env or command line
CGF_QUALITY_THRESHOLD=0.85     # Quality target per resource
CGF_MAX_ITERATIONS=5           # Max iterations before escalation
CGF_ITERATION_REVIEW=false     # Pause for review between iterations
CGF_EVAL_MODEL=sonnet          # Model for quality evaluation
```

---

## Tips

1. **Be specific in Purpose**: Vague purpose leads to generic resources. Describe exact use cases.

2. **List concrete capabilities**: Each capability should map to observable behavior.

3. **Define constraints upfront**: Constraints prevent over-engineering and guide decisions.

4. **Research topics matter**: Good research topics lead to current, relevant generated content.

5. **Proposed structure is optional**: If unsure, let research determine the structure.

6. **Trust the iteration loop**: Initial generation may be rough - iteration improves quality.

7. **Use Q&A wisely**: The Q&A phase resolves ambiguity - provide clear answers.

8. **Monitor quality scores**: If a resource is stuck below threshold, refine SPEC.md.

---

## Multi-Resource Type Detection

CGF detects spec type from content:

| Type | Detection Signal | Example |
|------|------------------|---------|
| **Single Resource** | `## Resource` section with `**File:**` | CGF_SPEC.example.md |
| **Plugin** | `## Capabilities` + agents/skills/commands | This example |
| **Skill Set** | `## Type: skill-set` | Terraform modules |
| **Workflow** | `## Type: workflow` + stages | Research pipeline |

---

## Environment Variables

```bash
# Multi-resource settings
CGF_QUALITY_THRESHOLD=0.85     # Per-resource quality target
CGF_MAX_ITERATIONS=5           # Max iterations before escalation
CGF_PARALLEL_GENERATION=true   # Generate independent resources in parallel

# Shared settings (same as single-resource)
CGF_OPTIMIZER_MODE=agentic     # agentic (default), python, or both
CGF_EVAL_MODEL=sonnet          # sonnet (default), haiku, or opus
CGF_VERBOSE=true               # Show progress output
CGF_ITERATION_REVIEW=false     # Pause for review after each iteration
```

---

## Comparison: Single vs Multi-Resource

| Aspect | Single Resource | Multi-Resource |
|--------|-----------------|----------------|
| SPEC.md | `## Resource` section | `## Capabilities` section |
| Output | One optimized file | Plugin/skill-set/workflow structure |
| Pipeline | RESEARCH → OPTIMIZE → EVALUATE | RESEARCH → Q&A → GENERATE → ITERATE → VALIDATE |
| Iteration | Section-based | Resource-based |
| Coherence | Within file | Across all resources |
| State | `sessions/task_list.json` | `sessions/optimization-state.json` |
