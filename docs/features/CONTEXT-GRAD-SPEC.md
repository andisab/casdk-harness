# ContextGrad Framework (CGF)
## Meta-Optimization for AI Context Engineering Resources

**Version:** 1.0.0-draft  
**Author:** Andis A. Blukis  
**Date:** December 15, 2025  
**Status:** Design Specification

---

## Executive Summary

The ContextGrad Framework (CGF) is a meta-optimization system that uses DSPy and TextGrad to automatically refine AI context engineering resources: agent definitions, MCP plugins, skills, and workflows. Built as an extension to `casdk-harness`, CGF enables systematic, measurable improvement of AI agents through reinforcement learning-style iteration with git-based versioning and comprehensive evaluation metrics.

**Example Use Case:** Develop an AWS infrastructure deployment agent that can autonomously generate Terraform configurations for any repository placed in the workspace, starting with EC2 + networking and expanding to EKS, RDS, IAM, etc.

**Supported Resource Types:**
- **Agents** (MVP - Phase 1): Agent definitions with YAML frontmatter
- **Skills** (Phase 2): Skill definitions in SKILL.md format
- **Commands** (Phase 3): Slash commands from plugins
- **Plugins** (Phase 3): Complete plugin optimization

**Key Innovation:** Treats context engineering artifacts as optimizable parameters in a learning system, using LLM-based optimization (DSPy/TextGrad) combined with real-world testing to achieve measurable improvements.

**Prerequisite:** This framework depends on the Plugin System Integration (Phase 1) documented in [PLUGIN-SYSTEM-INTEGRATION.md](./PLUGIN-SYSTEM-INTEGRATION.md). The plugin infrastructure must be implemented before CGF can leverage the `context-engineering` and `research-team` plugins as optimization tools.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Data Models](#data-models)
4. [Optimization Workflow](#optimization-workflow)
5. [Git-Based Versioning Strategy](#git-based-versioning-strategy)
6. [Evaluation Framework](#evaluation-framework)
7. [Implementation Phases](#implementation-phases)
8. [Technical Specifications](#technical-specifications)
9. [Example: AWS Infrastructure Agent Optimization](#example-aws-infrastructure-agent-optimization)
10. [Resource Type Examples](#resource-type-examples)
11. [Future Enhancements](#future-enhancements)

---

## 1. Architecture Overview

### 1.1 High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ContextGrad Framework                           │
│                  (Extension to casdk-harness)                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼────────┐        ┌─────────▼─────────┐      ┌─────────▼─────────┐
│   Resource     │        │   Test Harness    │      │   Optimization    │
│   Manager      │        │   & Evaluation    │      │     Engine        │
└───────┬────────┘        └─────────┬─────────┘      └─────────┬─────────┘
        │                           │                           │
        │ ┌─────────────────────────┼─────────────────────┐     │
        │ │                         │                     │     │
┌───────▼─▼──────┐        ┌─────────▼─────────┐ ┌──────▼─────▼──────┐
│  Git Versioning│        │  Metrics Collector │ │ DSPy ↔ TextGrad  │
│  & Checkpoints │        │  & Observability   │ │  Coordinator      │
└────────────────┘        └────────────────────┘ └───────────────────┘
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            ┌───────▼────────┐            ┌─────────▼────────┐
            │  Test Case     │            │  Human Review    │
            │  Generator     │            │   Interface      │
            │  Agent         │            │  (Checkpoint)    │
            └────────────────┘            └──────────────────┘
```

### 1.2 Integration with casdk-harness

CGF extends casdk-harness by:
- **Leveraging existing infrastructure**: Docker, monitoring (Grafana/Prometheus), checkpoint system
- **Adding new autonomous mode**: `make optimize-agent` for meta-optimization loops
- **Reusing agent architecture**: Tech Lead → Specialist pattern
- **Extending configuration**: New optimization-specific settings in `.env`
- **Orchestration patterns**: TestHarness and parallel execution can leverage patterns from [`docs/ORCHESTRATION.md`](../ORCHESTRATION.md) (Sequential Pipeline for test stages, Broadcast for parallel configs)

### 1.3 Supported Resource Types

CGF uses a phased approach to resource optimization, starting with the highest-complexity resources:

| Resource Type | Phase | Priority | Description |
|---------------|-------|----------|-------------|
| **Agent** | MVP | HIGH | Agent definitions with YAML frontmatter (`.md` files) |
| **Skill** | 2 | MEDIUM | Skill definitions (`SKILL.md` format) |
| **Command** | 3 | LOW | Slash commands from plugins |
| **Plugin** | 3 | LOW | Complete plugin packages |

**Why Agents First:**
- **Highest complexity**: Agent definitions include system prompts, tool selections, and behavioral patterns
- **Most value**: Optimizing agents directly improves task completion and quality
- **Best test bed**: Validates the optimization framework before expanding scope
- **Clear metrics**: Agent performance is measurable through test case execution

**Existing Agents Available for Optimization:**

The following 14 agents in `src/harness/agents/configs/` serve as examples and optimization targets:

| Agent | Domain | Potential Optimization Goals |
|-------|--------|------------------------------|
| `python-expert` | Development | Type safety, async patterns, Pydantic usage |
| `typescript-expert` | Development | Type inference, module patterns |
| `go-expert` | Development | Idiomatic Go, concurrency patterns |
| `nodejs-expert` | Development | Async/await, error handling |
| `react-expert` | Frontend | Component patterns, hooks usage |
| `postgres-expert` | Database | Query optimization, schema design |
| `sql-expert` | Database | Query performance, indexing |
| `docker-engineer` | Infrastructure | Dockerfile optimization, multi-stage builds |
| `k8s-engineer` | Infrastructure | Manifest generation, Helm patterns |
| `gcp-architect` | Cloud | GCP service selection, IAM |
| `gitlab-ci-expert` | CI/CD | Pipeline optimization, caching |
| `refactor-agent` | Code Quality | Pattern extraction, code simplification |
| `code-review-expert` | Code Quality | Review depth, issue detection |
| `sdet-expert` | Testing | Test coverage, test quality |

### 1.4 Plugin Integration Overview

CGF uses two plugins as **tools** (not resources to optimize):

```
┌─────────────────────────────────────────────────────────────────┐
│                    ContextGrad Framework v2.0                    │
├─────────────────────────────────────────────────────────────────┤
│  INPUTS                 CGF CORE                 OUTPUTS        │
│  - Goal Definition  ──▶ Optimization Engine ──▶ Optimized       │
│  - Research (opt)       (DSPy + TextGrad)       Resources       │
│  - Test Cases                                   + Metrics       │
├─────────────────────────────────────────────────────────────────┤
│  PLUGIN INTEGRATION LAYER                                        │
│  ┌─────────────────────┐     ┌────────────────────────┐         │
│  │ context-engineering │     │ research-team          │         │
│  │ (Templates/Patterns)│     │ (On-Demand Research)   │         │
│  └─────────────────────┘     └────────────────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│  EXISTING AGENTS (Examples for optimization)                     │
│  src/harness/agents/configs/ - 14 agents                        │
└─────────────────────────────────────────────────────────────────┘
```

**context-engineering plugin** provides:
- Templates for agent/skill/command definitions
- Pattern documentation (progressive disclosure, multi-agent orchestration)
- Goal definition guidance through skills

**research-team plugin** provides:
- On-demand research for best practices
- Multi-agent research coordination
- Research report generation

See [Section 2.5](#25-plugin-integration) for detailed integration specifications.

---

## 2. Core Components

### 2.1 Resource Manager

**Purpose:** CRUD operations for context engineering artifacts with versioning.

**Responsibilities:**
- Load/save agent definitions, skills, workflows, tools
- Version control integration (git branching, commits)
- Artifact validation and schema enforcement
- Template instantiation for new resources

**Key Classes:**
```python
class ResourceManager:
    def load_resource(self, resource_type: str, name: str) -> Resource
    def save_resource(self, resource: Resource, commit_msg: str) -> str
    def create_branch(self, resource_name: str) -> str
    def list_versions(self, resource_name: str) -> List[Commit]
    def rollback(self, resource_name: str, commit_hash: str)
```

**Supported Resource Types:**
- `agent`: Agent definitions (.md files with YAML frontmatter)
- `skill`: Skill definitions (SKILL.md format)
- `workflow`: Multi-step workflows (JSON or YAML)
- `tool`: Custom tool implementations (Python modules)
- `spec`: Specification files (SPEC.md format)

### 2.2 Test Harness & Evaluation

**Purpose:** Execute agents in controlled environments and collect metrics.

**Responsibilities:**
- Sandbox execution (Docker containers, test repos)
- Multi-stage testing (syntax → unit → integration → staging → live)
- Metrics collection (task completion, accuracy, latency, cost)
- Test result aggregation and reporting

**Testing Stages:**
```
Stage 1: Syntax & Static Analysis
    ↓ (pass threshold)
Stage 2: Unit Tests (mocked dependencies)
    ↓ (pass threshold)
Stage 3: Integration Tests (test repos, sandboxed)
    ↓ (pass threshold)
Stage 4: Staging Environment (real infrastructure, read-only)
    ↓ (pass threshold)
Stage 5: Live Environment (actual deployment, reversible)
```

**Key Classes:**
```python
class TestHarness:
    def execute_test_stage(self, 
                          stage: TestStage, 
                          agent: AgentDefinition,
                          test_case: TestCase) -> TestResult
    
    def collect_metrics(self, execution_id: str) -> Metrics
    
    def aggregate_results(self, 
                         test_results: List[TestResult]) -> AggregateScore

class TestCase:
    id: str
    repository: str  # Path to test repo
    task: str        # What the agent should do
    expected_outputs: List[str]  # Files/configs to verify
    validation_script: str  # Custom validation logic
    constraints: Dict[str, Any]  # Time, cost, etc.
```

### 2.3 Optimization Engine

**Purpose:** Coordinate DSPy and TextGrad to improve context engineering resources.

**Strategy: Hybrid Approach (DSPy → TextGrad)**

**Phase 1: DSPy Compilation (Compile-Time)**
- Train on multiple test cases to learn general patterns
- Use BootstrapFewShot or MIPROv2 optimizers
- Optimize system prompts and few-shot examples
- Produce baseline optimized agent

**Phase 2: TextGrad Refinement (Test-Time)**
- Iteratively refine on specific test cases
- Use textual gradients for instance-specific improvements
- Target remaining failure cases
- Stop at 80% automated improvement threshold

**Phase 3: Human Review (Checkpoint)**
- Present candidate improvements to user
- A/B comparison with previous versions
- User decides: accept, refine further, or rollback
- Capture user feedback for next iteration

**Key Classes:**
```python
class OptimizationEngine:
    def __init__(self, dspy_config, textgrad_config):
        self.dspy_optimizer = DSPyOptimizer(dspy_config)
        self.textgrad_optimizer = TextGradOptimizer(textgrad_config)
        self.checkpoint_manager = CheckpointManager()
    
    def optimize(self, 
                resource: Resource, 
                test_cases: List[TestCase],
                target_metric: str = "task_completion_rate") -> Resource:
        
        # Phase 1: DSPy
        compiled_resource = self.dspy_optimizer.compile(
            resource, test_cases, metric=target_metric
        )
        
        # Phase 2: TextGrad
        refined_resource = self.textgrad_optimizer.refine(
            compiled_resource, test_cases, 
            max_iterations=10,
            stop_threshold=0.80
        )
        
        # Phase 3: Human checkpoint
        if self.checkpoint_manager.should_review(refined_resource):
            return self.checkpoint_manager.request_human_review(
                refined_resource, 
                original=resource
            )
        
        return refined_resource
```

### 2.4 Git-Based Versioning

**Purpose:** Track optimization iterations with full history and reproducibility.

**Strategy:**
- **Branch per resource**: `optimize/agent-aws-infra`, `optimize/skill-terraform`
- **Commit per iteration**: Each optimization loop commits with metadata
- **Log file per commit**: Performance metrics stored alongside code
- **Tag milestones**: `v1.0-baseline`, `v1.1-dspy`, `v1.2-textgrad`, `v1.3-human-approved`

**Commit Message Format:**
```
[CGF] Iteration 5: DSPy optimization (MIPROv2)

Metrics:
- Task completion: 65% → 72% (+7%)
- Avg latency: 45s → 38s (-7s)
- Cost per run: $0.23 → $0.19 (-17%)

Changes:
- Updated system prompt with step-by-step reasoning
- Added 3 new few-shot examples
- Refined tool selection criteria

Optimizer: dspy.MIPROv2
Test cases: 6/6 passed stage 3
```

**Log File Format** (JSON):
```json
{
  "iteration": 5,
  "timestamp": "2025-12-15T14:32:10Z",
  "optimizer": "dspy.MIPROv2",
  "resource_type": "agent",
  "resource_name": "aws-infra-agent",
  "metrics": {
    "task_completion_rate": 0.72,
    "avg_latency_seconds": 38.2,
    "cost_per_run_usd": 0.19,
    "test_stages_passed": 3
  },
  "test_results": [
    {"test_case": "simple-flask-app", "status": "pass", "latency": 35.1},
    {"test_case": "django-postgres", "status": "pass", "latency": 41.3},
    // ...
  ],
  "commit_hash": "a3f8b92c",
  "parent_commit": "d7e2c45a"
}
```

### 2.5 Plugin Integration

CGF integrates with two plugins from the Plugin System (see [PLUGIN-SYSTEM-INTEGRATION.md](./PLUGIN-SYSTEM-INTEGRATION.md)):

#### context-engineering Plugin

**Purpose:** Provides templates, patterns, and skills for defining optimization goals.

**Integration Points:**

| Component | CGF Usage |
|-----------|-----------|
| `templates/subagent-template.md` | Template for new agent definitions |
| `templates/skill-template.md` | Template for new skill definitions |
| `skills/agent-definition-creation/` | Guidance for goal criteria definition |
| `patterns/progressive-disclosure.md` | Token management patterns |

**Loading context-engineering Resources:**

```python
from harness.plugin_manager import PluginManager

# Load context-engineering plugin
plugin_manager = PluginManager(config)
ce_plugin = plugin_manager.load_plugin("context-engineering")

# Get agent template
template_path = ce_plugin.path / "templates" / "subagent-template.md"
agent_template = template_path.read_text()

# Load goal definition skill
goal_skill = next(
    s for s in ce_plugin.skills
    if s.name == "agent-definition-creation"
)
```

#### research-team Plugin

**Purpose:** Provides on-demand research capabilities for best practices and patterns.

**Integration Points:**

| Component | CGF Usage |
|-----------|-----------|
| `agents/lead-research-coordinator.md` | Orchestrates research requests |
| `agents/research-specialist.md` | Performs focused research |
| `agents/research-report-writer.md` | Generates research reports |
| `skills/joplin-research/` | Research formatting guidelines |

**Research Workflow:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Optional Research Phase                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. User requests research on optimization target               │
│     "Research best practices for Python FastAPI agents"         │
│                                                                  │
│  2. CGF invokes research-team plugin                            │
│     - lead-research-coordinator plans research                  │
│     - research-specialists gather information                   │
│     - research-report-writer compiles findings                  │
│                                                                  │
│  3. Research insights inform Goal Definition                    │
│     - Best practices to encode                                  │
│     - Anti-patterns to avoid                                    │
│     - Quality metrics to measure                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Note:** Research is optional. Users can skip this phase and proceed directly to Goal Definition if they have sufficient domain knowledge.

### 2.6 Test Case Generator Agent

**Purpose:** Create and curate test cases through dialogue with user.

**Interaction Pattern:**
```
User: I want to optimize an AWS infrastructure agent.

Generator: I'll help create test cases. Let's start with repositories.
           What tech stacks should we cover?

User: Flask, Django, Node.js Express, and a static site.

Generator: Got it. For each stack, should I:
           1. Find real-world examples to clone?
           2. Generate minimal synthetic repos?
           3. Both?

User: Find real examples and strip their deployment configs.

Generator: [Searches GitHub, finds candidates]
           Here are 6 repositories I found:
           1. simple-flask-api (12 files, REST API)
           2. django-blog-cms (38 files, PostgreSQL)
           ...
           
           Should I clone these to workspace/test-repos/?

User: Yes. Also create a validation script for each.

Generator: [Creates test repos and validation scripts]
           Done. Each repo now has:
           - /deployment/ (empty, agent will populate)
           - /tests/validate_infra.sh (checks Terraform syntax)
           - /tests/expected_resources.json (what to verify)
           
           Ready to start optimization?
```

**Agent Definition:**
```yaml
name: test-case-generator
description: Creates test repositories and validation scripts for optimization
model: sonnet
tools:
  - WebSearch
  - Bash
  - Read
  - Write
  - Glob
system_prompt: |
  You are a test case architect. Your job is to create realistic
  test scenarios for optimizing AI agents. For infrastructure agents,
  you should find or generate representative repositories, strip
  deployment configs, and create validation scripts.
  
  Always confirm with the user before cloning external repos or
  generating synthetic data. Document your test case design.
```

---

## 3. Data Models

### 3.1 Resource

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

class ResourceType(Enum):
    AGENT = "agent"
    SKILL = "skill"
    WORKFLOW = "workflow"
    TOOL = "tool"
    SPEC = "spec"

@dataclass
class Resource:
    """Base class for all optimizable resources."""
    type: ResourceType
    name: str
    version: str
    content: str  # Markdown, YAML, or code
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        pass
    
    @classmethod
    def from_file(cls, filepath: str) -> 'Resource':
        """Load from file."""
        pass

@dataclass
class AgentResource(Resource):
    """Agent-specific resource."""
    description: str
    model: str
    tools: List[str]
    system_prompt: str
    max_turns: int = 100
```

### 3.2 Metrics

```python
@dataclass
class Metrics:
    """Performance metrics for an optimization iteration."""
    task_completion_rate: float  # 0.0 to 1.0
    accuracy_score: float  # Domain-specific (e.g., Terraform validation)
    avg_latency_seconds: float
    cost_per_run_usd: float
    token_usage: int
    test_stages_passed: int  # 0-5
    error_rate: float
    
    # Optional domain-specific metrics
    custom_metrics: Dict[str, float] = None
    
    def aggregate_score(self, weights: Dict[str, float]) -> float:
        """Weighted combination of metrics."""
        pass
    
    def improvement_over(self, baseline: 'Metrics') -> Dict[str, float]:
        """Calculate percentage improvements."""
        pass
```

### 3.3 TestCase

```python
@dataclass
class TestCase:
    """A single test scenario for evaluating an agent."""
    id: str
    name: str
    repository_path: str
    task_description: str
    expected_outputs: List[str]  # Files to check
    validation_script: Optional[str]
    constraints: Dict[str, Any]  # {'max_cost_usd': 0.50, 'timeout_seconds': 120}
    
    def validate(self, output_dir: str) -> bool:
        """Run validation script and check expected outputs."""
        pass
```

### 3.4 OptimizationRun

```python
@dataclass
class OptimizationRun:
    """Tracks a complete optimization session."""
    id: str
    resource_name: str
    start_time: datetime
    end_time: Optional[datetime]
    iterations: List['Iteration']
    baseline_metrics: Metrics
    best_metrics: Metrics
    best_iteration: int
    status: str  # 'running', 'paused', 'complete', 'failed'
    
    def add_iteration(self, iteration: 'Iteration'):
        """Add a new iteration."""
        pass
    
    def get_improvement_trend(self) -> List[float]:
        """Get task completion rate over iterations."""
        pass

@dataclass
class Iteration:
    """A single optimization iteration."""
    number: int
    optimizer: str  # 'dspy.MIPROv2', 'textgrad.TGD'
    metrics: Metrics
    commit_hash: str
    test_results: List[TestResult]
    duration_seconds: float
```

---

## 4. Optimization Workflow

### 4.0 Goal Definition Phase (Required)

Before optimization begins, users must define clear goals for the resource being optimized. This phase uses the `context-engineering` plugin's templates and skills.

**Goal Definition Workflow:**

```
┌──────────────────────────────────────────────────────────────────┐
│ Phase 0: Goal Definition (Required)                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Step 1: Load context-engineering skill                          │
│          → agent-definition-creation skill provides guidance     │
│                                                                   │
│  Step 2: Load resource template                                  │
│          → subagent-template.md for agents                       │
│          → skill-template.md for skills                          │
│                                                                   │
│  Step 3: Interactive goal elicitation                            │
│          → Primary goals (what the agent should excel at)        │
│          → Secondary goals (nice-to-have improvements)           │
│          → Anti-goals (what the agent should NOT do)             │
│          → Success metrics definition                            │
│                                                                   │
│  Step 4: Generate goal-definition.yaml                           │
│          → Machine-readable goal specification                   │
│          → Maps to optimization metrics                          │
│                                                                   │
│  Step 5: Validate and commit                                     │
│          → Verify goals are measurable                           │
│          → Commit to optimization branch                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ Phase 0.5: Research (Optional)                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  If user requests research on best practices:                    │
│                                                                   │
│  Step 1: Invoke research-team plugin                             │
│          → lead-research-coordinator plans research              │
│                                                                   │
│  Step 2: Parallel research execution                             │
│          → research-specialists gather domain knowledge          │
│                                                                   │
│  Step 3: Research report generation                              │
│          → research-report-writer compiles findings              │
│                                                                   │
│  Step 4: Update Goal Definition                                  │
│          → Integrate research insights into goals                │
│          → Add discovered best practices                         │
│          → Refine success metrics                                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Goal Definition Template:**

```yaml
# goal-definition.yaml
resource:
  type: agent
  name: python-expert
  baseline_version: current

goals:
  primary:
    - Generate type-safe Python code using Pydantic models
    - Use async/await patterns for I/O operations
    - Follow PEP 8 style guidelines

  secondary:
    - Include comprehensive docstrings
    - Suggest appropriate error handling
    - Recommend relevant libraries

  anti_goals:
    - Do NOT generate code with type: ignore comments
    - Do NOT use raw string SQL queries
    - Do NOT suggest deprecated libraries

success_definition:
  task_completion_rate: 0.85  # 85% minimum
  quality_metrics:
    type_safety: 0.95  # 95% of code should be type-annotated
    pep8_compliance: 0.90  # 90% pass rate on ruff checks

  custom_metrics:
    pydantic_usage: 0.80  # 80% of models should use Pydantic
    async_pattern_usage: 0.70  # 70% of I/O should be async

research_insights: []  # Populated if research phase used
```

**Code Example - Goal Definition Phase:**

```python
class GoalDefinitionPhase:
    """Manages the required Goal Definition phase."""

    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self.ce_plugin = plugin_manager.load_plugin("context-engineering")

    async def create_goal_definition(
        self,
        resource_type: str,
        resource_name: str
    ) -> GoalDefinition:
        """Guide user through goal definition."""

        # Step 1: Load skill for guidance
        skill = self._load_skill("agent-definition-creation")

        # Step 2: Load appropriate template
        template = self._get_template(resource_type)

        # Step 3: Interactive elicitation
        goals = await self._elicit_goals(template, skill)

        # Step 4: Generate YAML
        goal_def = GoalDefinition(
            resource_type=resource_type,
            resource_name=resource_name,
            **goals
        )

        # Step 5: Validate
        self._validate_goals(goal_def)

        return goal_def
```

### 4.1 End-to-End Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Initialization                                                │
│    - User specifies resource to optimize (e.g., python-expert)   │
│    - System loads baseline version                               │
│    - Creates optimization branch: optimize/python-expert         │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. Goal Definition (Required) - See Section 4.0                  │
│    - Load context-engineering templates and skills               │
│    - Interactive goal elicitation                                │
│    - Generate goal-definition.yaml                               │
│    - Optional: Research phase for best practices                 │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. Test Case Generation                                          │
│    - Tech Lead agent interviews user                             │
│    - Generates/selects test repositories                         │
│    - Creates validation scripts                                  │
│    - Documents test case specifications                          │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. Baseline Evaluation                                           │
│    - Run agent on all test cases (Stage 1-3)                     │
│    - Collect baseline metrics                                    │
│    - Identify failure patterns                                   │
│    - Commit: "Baseline evaluation: 42% task completion"          │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 4. DSPy Compilation Phase                                        │
│    - Select optimizer (MIPROv2 recommended)                      │
│    - Define metric function (task completion + accuracy)         │
│    - Run optimization loop (5-10 iterations)                     │
│    - Each iteration: test → evaluate → update → commit           │
│    - Commit: "DSPy iteration N: 68% task completion"             │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 5. TextGrad Refinement Phase                                     │
│    - Load DSPy-optimized agent                                   │
│    - Focus on remaining failure cases                            │
│    - Iterative refinement with textual gradients                 │
│    - Stop at 80% threshold or 10 iterations                      │
│    - Commit: "TextGrad iteration N: 79% task completion"         │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 6. Human Review Checkpoint                                       │
│    - Pause optimization                                          │
│    - Present metrics comparison to user                          │
│    - Show A/B examples (baseline vs optimized)                   │
│    - User decides: accept, continue, or rollback                 │
│    - Tag: "v1.3-human-approved" if accepted                      │
└──────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│ 7. Advanced Testing (Optional)                                   │
│    - Stage 4: Staging environment (if user approves)             │
│    - Stage 5: Live deployment (with rollback plan)               │
│    - Final metrics collection                                    │
│    - Merge to main if all stages pass                            │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Iteration Loop Detail

**Within each optimization phase (DSPy or TextGrad):**

```python
def optimization_iteration(
    resource: Resource, 
    test_cases: List[TestCase],
    optimizer: Union[DSPyOptimizer, TextGradOptimizer]
) -> Tuple[Resource, Metrics]:
    
    # 1. Generate candidate improvement
    candidate_resource = optimizer.generate_candidate(resource)
    
    # 2. Test candidate on all test cases
    test_results = []
    for test_case in test_cases:
        result = test_harness.execute_test_stage(
            stage=TestStage.INTEGRATION,
            agent=candidate_resource,
            test_case=test_case
        )
        test_results.append(result)
    
    # 3. Collect metrics
    metrics = metrics_collector.aggregate(test_results)
    
    # 4. Commit to git
    commit_hash = resource_manager.save_resource(
        candidate_resource,
        commit_msg=f"[CGF] Iteration {iter_num}: {optimizer.name}"
    )
    
    # 5. Save metrics log
    log_metrics(metrics, commit_hash, test_results)
    
    # 6. Decide: keep or revert
    if metrics.is_improvement_over(previous_metrics):
        return candidate_resource, metrics
    else:
        resource_manager.rollback(previous_commit_hash)
        return previous_resource, previous_metrics
```

---

## 5. Git-Based Versioning Strategy

### 5.1 Branch Structure

```
main
  ├── agents/
  │     └── aws-infra-agent.md  (production version)
  │
  └── optimize/aws-infra-agent  (optimization branch)
        ├── agents/
        │     └── aws-infra-agent.md  (evolving)
        ├── optimization-logs/
        │     ├── iteration-001.json
        │     ├── iteration-002.json
        │     └── ...
        └── test-cases/
              ├── simple-flask-app/
              ├── django-postgres/
              └── ...
```

### 5.2 Commit Strategy

**Each iteration creates a commit with:**
1. Updated resource files (agent.md, skill.md, etc.)
2. Metrics log JSON file
3. Descriptive commit message with performance delta

**Example commit history:**
```
a3f8b92c [CGF] Iteration 10: TextGrad refinement - 82% completion (+3%)
f7d3e21a [CGF] Iteration 9: TextGrad refinement - 79% completion (+2%)
b4c1a89d [CGF] Iteration 8: TextGrad refinement - 77% completion (+1%)
9e8f7c3b [CGF] Iteration 7: DSPy MIPROv2 - 76% completion (+8%)
...
c2d8e45f [CGF] Baseline evaluation - 42% completion
```

### 5.3 Merge Strategy

After human approval:
```bash
# Squash merge to main with summary
git checkout main
git merge --squash optimize/aws-infra-agent
git commit -m "[CGF] Optimized aws-infra-agent: 42% → 82% completion

Summary:
- 10 DSPy iterations + 5 TextGrad iterations
- Improved system prompt with structured reasoning
- Added 5 new few-shot examples
- Reduced cost by 23% ($0.26 → $0.20 per run)
- Reduced latency by 15% (48s → 41s average)

Tested on 6 repositories across 4 tech stacks.
All test cases pass Stage 3 (integration tests).
Human-reviewed and approved."

# Tag the release
git tag -a v1.4.0 -m "Optimized AWS infrastructure agent"
```

---

## 6. Evaluation Framework

### 6.1 Metrics Configuration

Users define success criteria in a configuration file:

```yaml
# optimization-config.yaml
resource:
  type: agent
  name: aws-infra-agent

optimization:
  target_metric: weighted_score
  weights:
    task_completion_rate: 0.5
    accuracy_score: 0.3
    cost_efficiency: 0.1
    latency_efficiency: 0.1
  
  thresholds:
    min_improvement: 0.05  # 5% improvement to keep iteration
    human_review_at: 0.80  # Review at 80% completion
    stage_progression: 0.70  # 70% to move to next stage
  
  dspy:
    optimizer: MIPROv2
    max_iterations: 10
    model: gpt-4o
  
  textgrad:
    optimizer: TGD
    max_iterations: 10
    model: gpt-4o
    backward_engine: gpt-4o

test_cases:
  - id: simple-flask-app
    weight: 1.0
  - id: django-postgres
    weight: 1.5  # More important
  - id: nodejs-express
    weight: 1.0
  - id: static-site
    weight: 0.8  # Less critical
```

### 6.2 Custom Metrics

For AWS infrastructure agent, define domain-specific metrics:

```python
class TerraformMetrics(Metrics):
    """Infrastructure-specific metrics."""
    terraform_syntax_valid: bool
    resources_created: int
    resources_expected: int
    security_best_practices_score: float  # 0.0-1.0
    cost_optimization_score: float
    
    def accuracy_score(self) -> float:
        """Calculate accuracy as resources_created / resources_expected."""
        return self.resources_created / max(self.resources_expected, 1)
    
    def validate_terraform(self, terraform_dir: str) -> Dict[str, Any]:
        """Run terraform validate and return results."""
        # subprocess.run(['terraform', 'validate'])
        pass
```

### 6.3 Test Execution

```python
class TerraformTestCase(TestCase):
    """Test case for infrastructure agent."""
    
    def validate(self, output_dir: str) -> TerraformMetrics:
        """Validate Terraform output."""
        metrics = TerraformMetrics()
        
        # 1. Check Terraform syntax
        terraform_dir = Path(output_dir) / "deployment"
        result = subprocess.run(
            ['terraform', 'validate'],
            cwd=terraform_dir,
            capture_output=True
        )
        metrics.terraform_syntax_valid = (result.returncode == 0)
        
        # 2. Parse terraform plan
        plan_result = subprocess.run(
            ['terraform', 'plan', '-json'],
            cwd=terraform_dir,
            capture_output=True
        )
        plan_data = json.loads(plan_result.stdout)
        
        # 3. Check expected resources
        expected = self.load_expected_resources()
        actual = self.extract_resources_from_plan(plan_data)
        metrics.resources_expected = len(expected)
        metrics.resources_created = len(actual.intersection(expected))
        
        # 4. Security checks (e.g., no hardcoded credentials)
        metrics.security_best_practices_score = self.check_security(terraform_dir)
        
        # 5. Cost estimation
        metrics.cost_optimization_score = self.estimate_cost_efficiency(plan_data)
        
        return metrics
```

---

## 7. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Goals:**
- Integrate CGF into casdk-harness
- Implement Resource Manager with git integration
- Create basic Test Harness (Stages 1-3)

**Deliverables:**
- `src/harness/optimization/` module structure
- Git branching and commit automation
- Metrics collection infrastructure
- CLI: `make optimize-agent AGENT=aws-infra-agent`

### Phase 2: Test Case Generation (Week 3)

**Goals:**
- Implement Test Case Generator agent
- Create 6 test repositories
- Develop validation scripts for Terraform

**Deliverables:**
- Test Case Generator agent definition
- 6 test repositories in `workspace/test-repos/`
- Validation scripts and expected output specs
- CLI: `make generate-test-cases`

### Phase 3: DSPy Integration (Week 4)

**Goals:**
- Integrate DSPy optimizers
- Implement baseline evaluation
- Run first optimization cycle

**Deliverables:**
- DSPy optimizer wrapper classes
- Baseline metrics for aws-infra-agent
- 5-10 iterations of DSPy optimization
- Performance tracking dashboard (Grafana)

### Phase 4: TextGrad Integration (Week 5)

**Goals:**
- Integrate TextGrad for refinement
- Implement 80% threshold checkpoint
- Human review interface

**Deliverables:**
- TextGrad optimizer wrapper
- Automatic pause at 80% completion
- CLI for human review: `make review-optimization`
- A/B comparison reports

### Phase 5: Advanced Testing & Staging (Week 6)

**Goals:**
- Implement Stage 4 (staging environment)
- AWS infrastructure testing with real resources
- Rollback mechanisms

**Deliverables:**
- Staging environment test harness
- AWS account integration for testing
- Cost tracking and limits
- Rollback automation

### Phase 6: Production & Refinement (Week 7-8)

**Goals:**
- Complete MVP: optimized AWS infra agent
- Demonstrate 80%+ task completion
- Document optimization process
- Plan expansion to EKS, RDS, IAM

**Deliverables:**
- Production-ready aws-infra-agent v1.0
- Optimization report with metrics
- Framework documentation
- Roadmap for additional infrastructure types

---

## 8. Technical Specifications

### 8.1 Technology Stack

**Core Framework:**
- Python 3.12+
- casdk-harness (base infrastructure)
- DSPy 3.0+
- TextGrad 0.1.6+

**Dependencies (add to `pyproject.toml`):**
```toml
[project.optional-dependencies]
optimization = [
    "dspy>=3.0",
    "textgrad>=0.1.6",
]
```

**Testing & Validation:**
- Terraform 1.5+
- Docker (sandboxed execution)
- pytest (unit tests)
- AWS CLI (staging/live tests)

**Observability:**
- Prometheus (metrics)
- Grafana (dashboards)
- JSON logs (structured data)

**Version Control:**
- Git (branching, commits, tags)
- GitLab/GitHub (optional: PR-based reviews)

### 8.2 Directory Structure

```
casdk-harness/
├── src/harness/
│   ├── optimization/              # NEW: CGF module
│   │   ├── __init__.py
│   │   ├── resource_manager.py
│   │   ├── test_harness.py
│   │   ├── optimization_engine.py
│   │   ├── checkpoint_manager.py
│   │   ├── metrics.py
│   │   ├── dspy_optimizer.py
│   │   ├── textgrad_optimizer.py
│   │   └── git_versioning.py
│   │
│   ├── agents/
│   │   └── configs/
│   │       ├── test-case-generator.md     # NEW
│   │       ├── aws-infra-agent.md         # NEW (to be optimized)
│   │       └── ...
│   │
│   └── ...
│
├── workspace/
│   ├── test-repos/                # NEW: Test repositories
│   │   ├── simple-flask-app/
│   │   ├── django-postgres/
│   │   ├── nodejs-express/
│   │   └── static-site/
│   │
│   └── optimization-runs/         # NEW: Per-run artifacts
│       └── aws-infra-agent-20251215/
│           ├── optimization-logs/
│           │   ├── iteration-001.json
│           │   └── ...
│           └── test-results/
│               ├── simple-flask-app-iter001.json
│               └── ...
│
├── config/
│   └── optimization-config.yaml   # NEW
│
├── Makefile
│   # NEW targets:
│   # make optimize-agent AGENT=aws-infra-agent
│   # make generate-test-cases
│   # make review-optimization RUN_ID=...
│   # make optimization-status RUN_ID=...
│
└── ...
```

### 8.3 Configuration

CGF uses a two-tier configuration approach:
- **`.env` file**: Runtime settings (API keys, feature flags, resource limits) - integrated with existing `HarnessConfig`
- **YAML file**: Per-optimization-run configuration (see Section 6.1 for `optimization-config.yaml`)

> **Note:** Paths like `workspace/test-repos` are resolved at runtime via `HarnessConfig.workspace_dir`.

**New `.env` variables (add to `HarnessConfig`):**
```bash
# Optimization settings
CGF_ENABLED=true
CGF_DEFAULT_OPTIMIZER=dspy.MIPROv2
CGF_AUTO_CHECKPOINT_AT=0.80
CGF_MAX_ITERATIONS_DSPY=10
CGF_MAX_ITERATIONS_TEXTGRAD=10

# DSPy settings
DSPY_MODEL=gpt-4o
DSPY_API_KEY=${ANTHROPIC_API_KEY}

# TextGrad settings
TEXTGRAD_MODEL=gpt-4o
TEXTGRAD_BACKWARD_ENGINE=gpt-4o

# Testing settings
CGF_TEST_REPO_DIR=workspace/test-repos
CGF_STAGING_AWS_PROFILE=casdk-staging
CGF_MAX_COST_PER_TEST=0.50  # USD
CGF_TEST_TIMEOUT=300  # seconds
```

---

## 9. Example: AWS Infrastructure Agent Optimization

> **Note:** This section demonstrates CGF usage with ONE example. The framework applies equally to any of the 14 agents in `src/harness/agents/configs/` or any new agents you create. See [Section 10](#10-resource-type-examples) for additional examples.

### 9.1 Initial Agent Definition (Baseline)

**File:** `agents/configs/aws-infra-agent.md`

```markdown
---
name: aws-infra-agent
description: Generates AWS infrastructure (Terraform) for application repositories
model: sonnet
tools: Read, Write, Glob, Grep, Bash
---

You are an AWS infrastructure specialist. Given a code repository, you analyze
the application and generate Terraform configurations for deploying it to AWS.

Start with EC2 + VPC networking. Create:
- VPC with public and private subnets
- Internet Gateway and NAT Gateway
- Security Groups
- EC2 instance with appropriate instance type
- Application deployment script

Follow AWS best practices for security and cost optimization.
```

### 9.2 Test Cases

**Test Case 1: Simple Flask App**
```yaml
id: simple-flask-app
name: Flask REST API
repository: workspace/test-repos/simple-flask-app
task: Generate Terraform for deploying this Flask API to AWS EC2
expected_outputs:
  - deployment/main.tf
  - deployment/variables.tf
  - deployment/outputs.tf
  - deployment/networking.tf
  - deployment/compute.tf
validation_script: tests/validate_terraform.sh
constraints:
  max_cost_usd: 0.50
  timeout_seconds: 120
expected_resources:
  - aws_vpc.main
  - aws_subnet.public
  - aws_subnet.private
  - aws_internet_gateway.main
  - aws_nat_gateway.main
  - aws_security_group.app
  - aws_instance.app
```

**Test Case 2-6:** Similar structure for Django, Node.js, static site, etc.

### 9.3 Expected Optimization Results

**Baseline (before optimization):**
- Task completion: 42% (2.5/6 test cases pass)
- Common failures: missing security groups, incorrect subnet configs
- Avg cost per run: $0.26
- Avg latency: 48 seconds

**After DSPy (Phase 1):**
- Task completion: 68% (4/6 test cases pass)
- Learned patterns: structured Terraform modules, proper variable usage
- Avg cost per run: $0.21 (-19%)
- Avg latency: 42 seconds (-13%)

**After TextGrad (Phase 2):**
- Task completion: 82% (5/6 test cases pass)
- Refined: edge case handling, better error messages
- Avg cost per run: $0.20 (-23%)
- Avg latency: 41 seconds (-15%)

**Target (post-human review):**
- Task completion: 90%+ (5.5+/6 test cases)
- All security best practices met
- Cost-optimized instance selection

### 9.4 Expansion Roadmap

After MVP proves successful:

**Phase 2 Resources:**
- EKS (Kubernetes clusters)
- RDS (managed databases)
- S3 (object storage)
- IAM (roles and policies)

**Phase 3 Resources:**
- CloudFront (CDN)
- Route53 (DNS)
- ALB/NLB (load balancers)
- CloudWatch (monitoring)

Each expansion follows same optimization workflow.

### 9.5 Alternative Example: Python Expert Agent

This demonstrates CGF applied to an existing agent from `src/harness/agents/configs/`:

**Goal Definition:**

```yaml
# goal-definition.yaml for python-expert
resource:
  type: agent
  name: python-expert
  baseline_version: current

goals:
  primary:
    - Generate type-safe Python code with Pydantic models
    - Use async/await patterns for I/O-bound operations
    - Follow FastAPI best practices for API development

  secondary:
    - Include comprehensive type hints
    - Suggest appropriate testing patterns
    - Recommend relevant libraries from PyPI

  anti_goals:
    - Do NOT use type: ignore comments
    - Do NOT suggest synchronous I/O in async contexts
    - Do NOT recommend deprecated libraries

success_definition:
  task_completion_rate: 0.90
  quality_metrics:
    type_coverage: 0.95
    ruff_compliance: 0.95
    mypy_pass_rate: 0.90
```

**Test Cases for Python Expert:**

| Test Case | Description | Expected Outputs |
|-----------|-------------|------------------|
| `fastapi-crud` | Generate CRUD API endpoints | `main.py`, `models.py`, `schemas.py` |
| `async-worker` | Create async background worker | `worker.py`, `tasks.py` |
| `pydantic-validation` | Implement complex validation | `validators.py`, `models.py` |
| `sqlalchemy-models` | Generate database models | `models.py`, `database.py` |

---

## 10. Resource Type Examples

This section provides optimization examples for each supported resource type.

### 10.1 Agent Optimization Examples

| Agent | Domain | Optimization Focus | Test Case Types |
|-------|--------|-------------------|-----------------|
| `python-expert` | Development | Type safety, async patterns | Code generation tasks |
| `postgres-expert` | Database | Query optimization, schema design | SQL generation tasks |
| `docker-engineer` | Infrastructure | Dockerfile patterns, multi-stage builds | Container config tasks |
| `code-review-expert` | Quality | Review depth, issue detection | Code review scenarios |

### 10.2 Skill Optimization (Phase 2)

> **Note:** Skill optimization will follow the same workflow as agent optimization, with skill-specific test cases and metrics.

**Planned approach:**
- Load skill from `skills/*/SKILL.md`
- Define skill-specific goals (capability coverage, accuracy)
- Create skill invocation test cases
- Measure skill effectiveness metrics

**Example skill optimization targets:**
- `api-development` skill: API design completeness
- `debugging` skill: Root cause identification accuracy
- `testing-strategies` skill: Test coverage recommendations

### 10.3 Command/Plugin Optimization (Phase 3)

> **Note:** Command and plugin optimization will be documented after Phase 2 completion.

---

## 11. Future Enhancements

### 11.1 Multi-Agent Optimization

Extend framework to optimize entire agent teams:
- Optimize lead agent + specialist agents together
- Coordinate inter-agent communication patterns
- Optimize task delegation strategies

### 11.2 Transfer Learning

Enable optimization across related resources:
- Learn from aws-infra-agent to bootstrap gcp-infra-agent
- Transfer patterns from terraform-agent to cloudformation-agent
- Build library of reusable optimization insights

### 11.3 Continuous Optimization

Implement production feedback loop:
- Monitor deployed agent performance
- Automatically trigger re-optimization on drift
- A/B test optimized versions in production

### 11.4 Cost Optimization

Add cost awareness to optimization:
- Track API costs per iteration
- Budget constraints for optimization runs
- Pareto frontier: performance vs cost

### 11.5 Human-in-the-Loop Improvements

- Interactive refinement during optimization
- Natural language feedback integration
- Preference learning from human decisions

### 11.6 Skill Marketplace Integration

- Optimize skills for sharing/selling
- Standardized quality metrics for skills
- Automated skill certification process

---

## Appendix A: CLI Commands

```bash
# Initialize optimization for an agent
make optimize-agent AGENT=aws-infra-agent

# Generate test cases interactively
make generate-test-cases

# Check optimization status
make optimization-status RUN_ID=aws-infra-agent-20251215

# Review optimization at checkpoint
make review-optimization RUN_ID=aws-infra-agent-20251215

# View metrics comparison
make optimization-report RUN_ID=aws-infra-agent-20251215

# Rollback to previous version
make optimization-rollback AGENT=aws-infra-agent COMMIT=a3f8b92c

# Merge optimized agent to main
make optimization-merge RUN_ID=aws-infra-agent-20251215

# List all optimization runs
make list-optimizations

# Clean up old optimization branches
make cleanup-optimizations DAYS=30
```

## Appendix B: Example Optimization Session

```bash
$ make optimize-agent AGENT=aws-infra-agent

[CGF] ContextGrad Framework v1.0.0
[CGF] Initializing optimization for: aws-infra-agent
[CGF] Creating branch: optimize/aws-infra-agent

[TEST GENERATION]
Starting Test Case Generator agent...

Generator: I'll help create test cases for the AWS infrastructure agent.
           Do you have specific repositories in mind, or should I search for examples?

You: Search for examples. I need Flask, Django, Node.js Express, and a static site.

Generator: [Searching GitHub...]
           Found candidates:
           1. pallets/flask-example (minimal Flask API)
           2. django/djangoproject.com (Django blog)
           3. expressjs/express-starter (Node.js Express)
           4. jamstack/jamstack-site (static site generator)
           
           Should I clone these to workspace/test-repos/ and strip deployment configs?

You: Yes, do it.

Generator: [Cloning and preparing test repositories...]
           Created 4 test repositories with validation scripts.
           Each repo has /tests/validate_terraform.sh and expected_resources.json
           
           Ready to start optimization.

[BASELINE EVALUATION]
Running baseline tests...

Test 1/4: simple-flask-app............... FAIL (missing security group)
Test 2/4: django-postgres................ FAIL (incorrect RDS config)
Test 3/4: nodejs-express................. PASS
Test 4/4: static-site.................... PASS

Baseline metrics:
- Task completion: 50% (2/4)
- Avg latency: 45s
- Avg cost: $0.24

[CGF] Saved baseline: commit c2d8e45f

[DSPY OPTIMIZATION]
Starting DSPy MIPROv2 optimizer...

Iteration 1/10: Generating candidate with new system prompt...
  Testing... 2/4 pass (50%)
  No improvement, reverting.

Iteration 2/10: Adding few-shot examples...
  Testing... 3/4 pass (75%) ✓ IMPROVEMENT
  Commit: a9e7f1c2

Iteration 3/10: Refining variable structure...
  Testing... 3/4 pass (75%)
  No improvement, reverting.

Iteration 4/10: Enhancing error handling...
  Testing... 4/4 pass (100%) ✓ IMPROVEMENT
  Commit: d3f8b21a

DSPy phase complete. Best iteration: 4
Task completion: 100% (4/4)
Saved checkpoint.

[TEXTGRAD REFINEMENT]
Starting TextGrad TGD optimizer...

(All test cases passing - skipping TextGrad refinement)

[HUMAN REVIEW CHECKPOINT]
Optimization complete. Results:

              Baseline    Optimized   Delta
Completion    50%         100%        +50%
Latency       45s         39s         -13%
Cost          $0.24       $0.19       -21%

Review changes? (y/n): y

[Displaying diff of system prompt changes...]

Accept optimized version? (y/n/refine): y

[CGF] Merging to main branch...
[CGF] Tagged: v1.1.0
[CGF] Optimization complete!

Run 'make test-agent AGENT=aws-infra-agent' to try the optimized version.
```

---

## Appendix C: Metrics Dashboard (Grafana)

**New dashboard panels for CGF:**

1. **Optimization Progress**
   - Task completion rate over iterations
   - Cost trend
   - Latency trend

2. **Per-Iteration Breakdown**
   - Test case pass/fail status
   - Optimizer type (DSPy/TextGrad)
   - Commit hash

3. **Resource Performance**
   - Heatmap of agent success by test case
   - Comparison across optimization runs

4. **Cost Analysis**
   - API costs per iteration
   - Total optimization cost
   - ROI calculation (improvement vs cost)

---

## Conclusion

The ContextGrad Framework provides a systematic, measurable approach to improving AI agents through automated optimization. By combining DSPy's compile-time learning with TextGrad's test-time refinement, integrated with git-based versioning and human-in-the-loop checkpoints, CGF enables rapid, reproducible improvements to context engineering resources.

The AWS infrastructure agent MVP demonstrates the framework's practical value: transforming a 50% success rate baseline into a 100% production-ready agent through automated optimization.

Future expansions to EKS, RDS, IAM, and beyond will leverage the same optimization infrastructure, accelerating agent development across the entire infrastructure-as-code domain.

---

**Next Steps:**
1. Review and refine this specification
2. Implement Phase 1 (Foundation)
3. Create Test Case Generator agent
4. Run first optimization cycle on aws-infra-agent
5. Iterate based on real-world results