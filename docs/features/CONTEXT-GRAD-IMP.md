
# ContextGrad Framework - Implementation Guide
**Companion to:** CONTEXT-GRAD-SPEC.md
**Purpose:** Tactical implementation steps and code examples
**Date:** December 15, 2025

---

## Prerequisites

**Phase 1: Plugin System Integration** must be completed before implementing CGF. See [PLUGIN-SYSTEM-INTEGRATION.md](./PLUGIN-SYSTEM-INTEGRATION.md).

CGF depends on:
- `PluginManager` class for loading context-engineering and research-team plugins
- `HookRegistry` for lifecycle hooks
- Plugin configuration settings in `HarnessConfig`

---

## Integration with Existing Modules

CGF leverages existing casdk-harness infrastructure. The following modules can be reused:

| Module | Location | Reusable Components |
|--------|----------|---------------------|
| Agent Definitions | `harness.agents.definitions` | `AgentDefinition`, `parse_agent_md_file()`, `load_agent_from_md()` |
| Checkpoint System | `harness.checkpoint` | `CheckpointManager` for iteration snapshots |
| Monitoring | `harness.monitoring` | `MetricsCollector` patterns, Prometheus integration |
| Configuration | `harness.config` | `HarnessConfig` (extend with CGF fields) |
| Agent Session | `harness.agent` | `AgentSession` for test execution |

**Key imports already available:**
```python
from harness.agents.definitions import AgentDefinition, parse_agent_md_file
from harness.checkpoint import CheckpointManager
from harness.config import HarnessConfig
```

---

## Dependencies

Add these to `pyproject.toml`:

```toml
[project.optional-dependencies]
optimization = [
    "dspy>=3.0",
    "textgrad>=0.1.6",
]
```

Install with: `pip install -e ".[optimization]"`

---

## Quick Start Checklist

### Pre-Implementation (Week 0)

- [ ] Review main specification document
- [ ] Verify casdk-harness is working: `make doctor`
- [ ] Install DSPy: `pip install dspy`
- [ ] Install TextGrad: `pip install textgrad`
- [ ] Set up test AWS account/profile for staging tests
- [ ] Create optimization config template
- [ ] Document 6 test repository requirements

### Phase 1: Foundation (Weeks 1-2)

- [ ] Create `src/harness/optimization/` module structure
- [ ] Implement `ResourceManager` with git integration
- [ ] Implement basic `TestHarness` (Stages 1-3)
- [ ] Implement `MetricsCollector`
- [ ] Add Makefile targets
- [ ] Write unit tests
- [ ] Update documentation

### Phase 2: Test Generation (Week 3)

- [ ] Create Test Case Generator agent definition
- [ ] Implement test repository setup automation
- [ ] Create Terraform validation scripts
- [ ] Document test case specifications
- [ ] Test the generator with 2-3 real repos

### Phase 3-6: Optimization & Testing (Weeks 4-8)

See main specification for detailed breakdown.

---

## Code Templates

### 1. Resource Manager

**File:** `src/harness/optimization/resource_manager.py`

```python
"""Resource management with git integration for CGF."""

import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from harness.agents.definitions import AgentDefinition, parse_agent_md_file


class ResourceType(str, Enum):
    """Resource type enumeration with phase information.

    CGF uses a phased approach:
    - Phase 1 (MVP): Agents
    - Phase 2: Skills
    - Phase 3: Commands, Plugins
    """
    AGENT = "agent"
    SKILL = "skill"
    COMMAND = "command"
    PLUGIN = "plugin"
    WORKFLOW = "workflow"  # Legacy, may be deprecated
    TOOL = "tool"  # Legacy, may be deprecated
    SPEC = "spec"  # Legacy, may be deprecated

    @classmethod
    def mvp_types(cls) -> List['ResourceType']:
        """Return resource types supported in MVP (Phase 1)."""
        return [cls.AGENT]

    @classmethod
    def phase2_types(cls) -> List['ResourceType']:
        """Return resource types for Phase 2."""
        return [cls.AGENT, cls.SKILL]

    @classmethod
    def all_supported_types(cls) -> List['ResourceType']:
        """Return all optimizable resource types."""
        return [cls.AGENT, cls.SKILL, cls.COMMAND, cls.PLUGIN]

    def is_mvp(self) -> bool:
        """Check if this type is supported in MVP."""
        return self in self.mvp_types()


# NOTE: Using @dataclass for simplicity. These are compatible with Pydantic models
# used elsewhere in casdk-harness. Can convert to Pydantic BaseModel if needed
# for validation features.

@dataclass
class Resource:
    """Base class for optimizable resources."""
    type: str
    name: str
    version: str
    content: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_agent_definition(cls, agent_def: AgentDefinition) -> 'Resource':
        """Create Resource from AgentDefinition."""
        return cls(
            type=ResourceType.AGENT,
            name=agent_def.name,
            version="baseline",
            content=agent_def.system_prompt,
            metadata={
                "description": agent_def.description,
                "model": agent_def.model,
                "tools": agent_def.tools,
                "max_turns": agent_def.max_turns
            }
        )


class ResourceManager:
    """Manages CRUD operations for optimization resources."""

    def __init__(self, config: 'HarnessConfig'):
        """Initialize resource manager.

        Args:
            config: HarnessConfig instance for path resolution

        Note:
            Paths are derived from HarnessConfig to maintain consistency
            with existing casdk-harness patterns. Do not hardcode paths.
        """
        self.config = config
        self.workspace_root = Path(config.workspace_dir).parent  # /app or project root
        self.agents_dir = self.workspace_root / "src" / "harness" / "agents" / "configs"
        self.optimization_dir = Path(config.workspace_dir) / "optimization-runs"
        
    def load_agent(self, name: str) -> Resource:
        """Load an agent definition as a Resource.
        
        Args:
            name: Agent name (e.g., 'aws-infra-agent')
            
        Returns:
            Resource object
            
        Raises:
            FileNotFoundError: If agent not found
        """
        agent_file = self.agents_dir / f"{name}.md"
        if not agent_file.exists():
            raise FileNotFoundError(f"Agent not found: {agent_file}")
        
        parsed = parse_agent_md_file(agent_file)
        
        return Resource(
            type=ResourceType.AGENT,
            name=parsed["name"],
            version="baseline",
            content=parsed["body"],
            metadata={
                "description": parsed["description"],
                "model": parsed["model"],
                "tools": parsed["tools"]
            }
        )
    
    def save_resource(self, 
                     resource: Resource, 
                     commit_msg: str,
                     branch: Optional[str] = None) -> str:
        """Save resource and commit to git.
        
        Args:
            resource: Resource to save
            commit_msg: Commit message
            branch: Git branch (default: current branch)
            
        Returns:
            Commit hash
        """
        # 1. Write resource to file
        if resource.type == ResourceType.AGENT:
            filepath = self.agents_dir / f"{resource.name}.md"
            self._write_agent_md(filepath, resource)
        else:
            raise NotImplementedError(f"Resource type {resource.type} not yet supported")
        
        # 2. Git add and commit
        try:
            subprocess.run(
                ["git", "add", str(filepath)],
                cwd=self.workspace_root,
                check=True,
                capture_output=True
            )
            
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.workspace_root,
                check=True,
                capture_output=True
            )
            
            # Get commit hash
            commit_hash = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.workspace_root,
                check=True,
                capture_output=True,
                text=True
            ).stdout.strip()
            
            return commit_hash
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git commit failed: {e.stderr.decode()}")
    
    def create_optimization_branch(self, resource_name: str) -> str:
        """Create a new optimization branch.
        
        Args:
            resource_name: Name of resource being optimized
            
        Returns:
            Branch name
        """
        branch_name = f"optimize/{resource_name}"
        
        try:
            # Check if branch exists
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch_name],
                cwd=self.workspace_root,
                capture_output=True
            )
            
            if result.returncode == 0:
                # Branch exists, check it out
                subprocess.run(
                    ["git", "checkout", branch_name],
                    cwd=self.workspace_root,
                    check=True
                )
            else:
                # Create new branch
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=self.workspace_root,
                    check=True
                )
            
            return branch_name
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Branch creation failed: {e}")
    
    def list_versions(self, resource_name: str) -> List[Dict[str, str]]:
        """List all git commits for a resource.
        
        Args:
            resource_name: Name of resource
            
        Returns:
            List of commits with hash, message, date
        """
        if resource_name.startswith("agent/"):
            filepath = f"src/harness/agents/configs/{resource_name[6:]}.md"
        else:
            filepath = f"src/harness/agents/configs/{resource_name}.md"
        
        try:
            result = subprocess.run(
                ["git", "log", "--format=%H|%s|%ai", "--", filepath],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    hash_val, msg, date = line.split('|', 2)
                    commits.append({
                        "hash": hash_val[:8],
                        "message": msg,
                        "date": date
                    })
            
            return commits
            
        except subprocess.CalledProcessError:
            return []
    
    def rollback(self, resource_name: str, commit_hash: str):
        """Rollback resource to a specific commit.
        
        Args:
            resource_name: Name of resource
            commit_hash: Git commit hash to rollback to
        """
        if resource_name.startswith("agent/"):
            filepath = f"src/harness/agents/configs/{resource_name[6:]}.md"
        else:
            filepath = f"src/harness/agents/configs/{resource_name}.md"
        
        try:
            subprocess.run(
                ["git", "checkout", commit_hash, "--", filepath],
                cwd=self.workspace_root,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Rollback failed: {e}")
    
    def _write_agent_md(self, filepath: Path, resource: Resource):
        """Write agent resource to .md file with YAML frontmatter."""
        metadata = resource.metadata
        
        frontmatter = f"""---
name: {resource.name}
description: {metadata.get('description', '')}
model: {metadata.get('model', 'sonnet')}
tools: {', '.join(metadata.get('tools', []))}
---

{resource.content}
"""
        filepath.write_text(frontmatter)
```

### 2. Metrics Collection

**File:** `src/harness/optimization/metrics.py`

```python
"""Metrics collection and aggregation for CGF."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class Metrics:
    """Performance metrics for an optimization iteration."""
    task_completion_rate: float  # 0.0 to 1.0
    accuracy_score: float  # Domain-specific
    avg_latency_seconds: float
    cost_per_run_usd: float
    token_usage: int
    test_stages_passed: int  # 0-5
    error_rate: float
    custom_metrics: Optional[Dict[str, float]] = None
    
    def aggregate_score(self, weights: Dict[str, float]) -> float:
        """Calculate weighted aggregate score.
        
        Args:
            weights: Dictionary of metric_name -> weight
            
        Returns:
            Weighted score (0.0-1.0)
        """
        score = 0.0
        total_weight = 0.0
        
        for metric_name, weight in weights.items():
            if hasattr(self, metric_name):
                value = getattr(self, metric_name)
                # Normalize values to 0-1 range
                if metric_name in ['cost_per_run_usd', 'avg_latency_seconds', 'error_rate']:
                    # Lower is better - invert
                    value = 1.0 - min(value, 1.0)
                score += value * weight
                total_weight += weight
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def improvement_over(self, baseline: 'Metrics') -> Dict[str, float]:
        """Calculate percentage improvements over baseline.
        
        Args:
            baseline: Baseline metrics to compare against
            
        Returns:
            Dictionary of metric_name -> percentage change
        """
        improvements = {}
        
        for field in ['task_completion_rate', 'accuracy_score', 'avg_latency_seconds', 
                      'cost_per_run_usd', 'error_rate']:
            current = getattr(self, field)
            baseline_val = getattr(baseline, field)
            
            if baseline_val == 0:
                improvements[field] = 0.0
            else:
                pct_change = ((current - baseline_val) / baseline_val) * 100
                improvements[field] = pct_change
        
        return improvements
    
    def is_improvement_over(self, 
                           baseline: 'Metrics', 
                           weights: Dict[str, float],
                           threshold: float = 0.05) -> bool:
        """Check if this represents an improvement over baseline.
        
        Args:
            baseline: Baseline metrics
            weights: Metric weights for aggregate score
            threshold: Minimum improvement threshold (default: 5%)
            
        Returns:
            True if improvement exceeds threshold
        """
        current_score = self.aggregate_score(weights)
        baseline_score = baseline.aggregate_score(weights)
        
        improvement = (current_score - baseline_score) / baseline_score
        return improvement >= threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class TestResult:
    """Result from running a single test case."""
    test_case_id: str
    status: str  # 'pass', 'fail', 'error'
    latency_seconds: float
    cost_usd: float
    token_usage: int
    error_message: Optional[str] = None
    validation_details: Optional[Dict[str, Any]] = None


class MetricsCollector:
    """Collects and aggregates test metrics."""
    
    def __init__(self, optimization_dir: Path):
        """Initialize metrics collector.
        
        Args:
            optimization_dir: Directory for storing metrics logs
        """
        self.optimization_dir = optimization_dir
        self.optimization_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate(self, test_results: List[TestResult]) -> Metrics:
        """Aggregate test results into metrics.
        
        Args:
            test_results: List of test results
            
        Returns:
            Aggregated metrics
        """
        if not test_results:
            return Metrics(
                task_completion_rate=0.0,
                accuracy_score=0.0,
                avg_latency_seconds=0.0,
                cost_per_run_usd=0.0,
                token_usage=0,
                test_stages_passed=0,
                error_rate=1.0
            )
        
        passed = sum(1 for r in test_results if r.status == 'pass')
        total = len(test_results)
        
        return Metrics(
            task_completion_rate=passed / total,
            accuracy_score=self._calculate_accuracy(test_results),
            avg_latency_seconds=sum(r.latency_seconds for r in test_results) / total,
            cost_per_run_usd=sum(r.cost_usd for r in test_results) / total,
            token_usage=sum(r.token_usage for r in test_results),
            test_stages_passed=3,  # Assuming integration tests
            error_rate=(total - passed) / total
        )
    
    def _calculate_accuracy(self, test_results: List[TestResult]) -> float:
        """Calculate domain-specific accuracy score.
        
        For now, returns task completion rate. Override for custom logic.
        """
        passed = sum(1 for r in test_results if r.status == 'pass')
        return passed / len(test_results) if test_results else 0.0
    
    def log_iteration(self,
                     iteration_num: int,
                     optimizer_name: str,
                     metrics: Metrics,
                     test_results: List[TestResult],
                     commit_hash: str,
                     resource_name: str):
        """Log metrics for an iteration.
        
        Args:
            iteration_num: Iteration number
            optimizer_name: Name of optimizer (e.g., 'dspy.MIPROv2')
            metrics: Aggregated metrics
            test_results: Individual test results
            commit_hash: Git commit hash
            resource_name: Name of resource being optimized
        """
        log_file = self.optimization_dir / f"iteration-{iteration_num:03d}.json"
        
        log_data = {
            "iteration": iteration_num,
            "timestamp": datetime.utcnow().isoformat(),
            "optimizer": optimizer_name,
            "resource_name": resource_name,
            "commit_hash": commit_hash,
            "metrics": metrics.to_dict(),
            "test_results": [asdict(r) for r in test_results]
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def load_iteration_log(self, iteration_num: int) -> Dict[str, Any]:
        """Load metrics log for a specific iteration.
        
        Args:
            iteration_num: Iteration number
            
        Returns:
            Log data dictionary
        """
        log_file = self.optimization_dir / f"iteration-{iteration_num:03d}.json"
        
        if not log_file.exists():
            raise FileNotFoundError(f"Log not found: {log_file}")
        
        with open(log_file) as f:
            return json.load(f)
    
    def get_iteration_trend(self, metric_name: str) -> List[float]:
        """Get trend of a specific metric across iterations.
        
        Args:
            metric_name: Name of metric (e.g., 'task_completion_rate')
            
        Returns:
            List of metric values in order
        """
        values = []
        iteration_num = 1
        
        while True:
            try:
                log_data = self.load_iteration_log(iteration_num)
                values.append(log_data['metrics'][metric_name])
                iteration_num += 1
            except FileNotFoundError:
                break
        
        return values
```

### 3. Test Harness (Basic)

**File:** `src/harness/optimization/test_harness.py`

```python
"""Test execution and validation for CGF."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from harness.optimization.metrics import TestResult


class TestStage(Enum):
    """Test execution stages."""
    SYNTAX = 1
    UNIT = 2
    INTEGRATION = 3
    STAGING = 4
    LIVE = 5


@dataclass
class TestCase:
    """A single test scenario."""
    id: str
    name: str
    repository_path: Path
    task_description: str
    expected_outputs: List[str]
    validation_script: Optional[Path]
    constraints: Dict[str, Any]
    
    def validate(self, output_dir: Path) -> bool:
        """Run validation script.
        
        Args:
            output_dir: Directory containing agent outputs
            
        Returns:
            True if validation passes
        """
        if not self.validation_script:
            # Default validation: check expected files exist
            return all((output_dir / f).exists() for f in self.expected_outputs)
        
        try:
            result = subprocess.run(
                [str(self.validation_script), str(output_dir)],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False


class TestHarness:
    """Executes agents in test environments and collects results."""

    def __init__(self, config: 'HarnessConfig'):
        """Initialize test harness.

        Args:
            config: HarnessConfig instance for path resolution
        """
        self.config = config
        self.workspace_root = Path(config.workspace_dir).parent
        self.test_repos_dir = Path(config.workspace_dir) / "test-repos"
    
    def execute_test_stage(self,
                          stage: TestStage,
                          agent_config: Dict[str, Any],
                          test_case: TestCase) -> TestResult:
        """Execute a test case at a specific stage.
        
        Args:
            stage: Test stage to execute
            agent_config: Agent configuration
            test_case: Test case to run
            
        Returns:
            Test result with metrics
        """
        if stage == TestStage.INTEGRATION:
            return self._run_integration_test(agent_config, test_case)
        else:
            raise NotImplementedError(f"Stage {stage} not yet implemented")
    
    def _run_integration_test(self,
                             agent_config: Dict[str, Any],
                             test_case: TestCase) -> TestResult:
        """Run integration test in sandboxed environment.
        
        This is a simplified version. Full implementation would:
        1. Spin up Docker container
        2. Mount test repository
        3. Run agent with casdk
        4. Collect outputs
        5. Run validation
        6. Measure metrics
        """
        # TODO: Implement full integration test execution
        # For now, return mock result
        
        return TestResult(
            test_case_id=test_case.id,
            status='pass',
            latency_seconds=42.0,
            cost_usd=0.20,
            token_usage=15000,
            validation_details={"mock": True}
        )
    
    def load_test_cases(self) -> List[TestCase]:
        """Load all test cases from test-repos directory.
        
        Returns:
            List of test cases
        """
        test_cases = []
        
        for repo_dir in self.test_repos_dir.iterdir():
            if not repo_dir.is_dir():
                continue
            
            spec_file = repo_dir / "tests" / "test_spec.json"
            if not spec_file.exists():
                continue
            
            with open(spec_file) as f:
                spec = json.load(f)
            
            test_case = TestCase(
                id=spec['id'],
                name=spec['name'],
                repository_path=repo_dir,
                task_description=spec['task'],
                expected_outputs=spec['expected_outputs'],
                validation_script=repo_dir / spec.get('validation_script', 'tests/validate.sh'),
                constraints=spec.get('constraints', {})
            )
            test_cases.append(test_case)
        
        return test_cases
```

#### 3.1 Enhanced TestHarness with Orchestration Patterns

For parallel test execution and complex test pipelines, TestHarness can leverage orchestration patterns from [`docs/ORCHESTRATION_PATTERNS.md`](../ORCHESTRATION_PATTERNS.md).

```python
"""Enhanced TestHarness using orchestration patterns.

See: docs/ORCHESTRATION_ROADMAP.md Phase 5 (CGF Integration)
"""

from harness.orchestration import SequentialPipeline, BroadcastMultiPerspective
from harness.orchestration.patterns import HierarchicalCoordinator

class OrchestrationTestHarness(TestHarness):
    """TestHarness extended with orchestration pattern support.

    Uses Sequential Pipeline for ordered test stage execution
    and Broadcast pattern for running tests across multiple configurations.
    """

    def __init__(self, config: 'HarnessConfig'):
        super().__init__(config)

        # Sequential pipeline for test stages
        self.stage_pipeline = SequentialPipeline([
            (TestStage.SYNTAX, "syntax-validator"),
            (TestStage.UNIT, "unit-test-runner"),
            (TestStage.INTEGRATION, "integration-test-runner"),
            (TestStage.STAGING, "staging-test-runner"),
        ])

        # Broadcast for parallel configuration testing
        self.config_broadcaster = BroadcastMultiPerspective([
            "python-expert",      # Python-specific validation
            "security-auditor",   # Security review
            "sdet-expert",        # Test coverage analysis
        ])

    async def run_full_pipeline(self,
                                agent_config: Dict[str, Any],
                                test_case: TestCase) -> Dict[str, TestResult]:
        """Run all test stages in sequence using orchestration pipeline.

        Args:
            agent_config: Agent configuration to test
            test_case: Test case to run

        Returns:
            Dict mapping stage names to results
        """
        context = {
            "agent_config": agent_config,
            "test_case": test_case,
        }

        # Execute stages in order, stopping on first failure
        results = await self.stage_pipeline.execute(
            input_data=context,
            stop_on_failure=True
        )

        return results

    async def run_parallel_validation(self,
                                     agent_config: Dict[str, Any],
                                     test_case: TestCase) -> List[Dict[str, Any]]:
        """Run multiple validation perspectives in parallel.

        Uses Broadcast pattern to get diverse validation feedback
        from different expert agents simultaneously.
        """
        context = {
            "agent_config": agent_config,
            "test_case": test_case,
            "validation_focus": "comprehensive",
        }

        # All validators run in parallel
        perspectives = await self.config_broadcaster.execute(context)

        return perspectives
```

### 4. Goal Definition (Plugin Integration)

**File:** `src/harness/optimization/goal_definition.py`

These classes integrate with the Plugin System (Phase 1) to load templates and skills from the `context-engineering` plugin.

```python
"""Goal definition for CGF optimization runs.

Integrates with context-engineering plugin for templates and patterns.
Requires Plugin System Integration (Phase 1) to be complete.
"""

import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from harness.plugin_manager import PluginManager, Plugin
from harness.optimization.metrics import Metrics


@dataclass
class GoalDefinition:
    """Structured goal definition for optimization.

    This class represents the output of the Goal Definition Phase,
    capturing user-specified goals, anti-goals, and success criteria.
    """
    resource_type: str
    resource_name: str
    baseline_version: str = "current"

    # Goal categories
    primary_goals: List[str] = field(default_factory=list)
    secondary_goals: List[str] = field(default_factory=list)
    anti_goals: List[str] = field(default_factory=list)

    # Success definition
    task_completion_rate: float = 0.85
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    # Optional research insights
    research_insights: List[str] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Serialize to YAML format."""
        data = {
            "resource": {
                "type": self.resource_type,
                "name": self.resource_name,
                "baseline_version": self.baseline_version,
            },
            "goals": {
                "primary": self.primary_goals,
                "secondary": self.secondary_goals,
                "anti_goals": self.anti_goals,
            },
            "success_definition": {
                "task_completion_rate": self.task_completion_rate,
                "quality_metrics": self.quality_metrics,
                "custom_metrics": self.custom_metrics,
            },
            "research_insights": self.research_insights,
        }
        return yaml.dump(data, default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'GoalDefinition':
        """Create from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(
            resource_type=data["resource"]["type"],
            resource_name=data["resource"]["name"],
            baseline_version=data["resource"].get("baseline_version", "current"),
            primary_goals=data["goals"].get("primary", []),
            secondary_goals=data["goals"].get("secondary", []),
            anti_goals=data["goals"].get("anti_goals", []),
            task_completion_rate=data["success_definition"].get("task_completion_rate", 0.85),
            quality_metrics=data["success_definition"].get("quality_metrics", {}),
            custom_metrics=data["success_definition"].get("custom_metrics", {}),
            research_insights=data.get("research_insights", []),
        )

    def to_metrics_config(self) -> Dict[str, Any]:
        """Convert to metrics configuration for optimization engine."""
        weights = {"task_completion_rate": 0.5}

        # Add quality metrics with distributed weights
        remaining_weight = 0.5
        if self.quality_metrics:
            per_metric_weight = remaining_weight / len(self.quality_metrics)
            for metric_name in self.quality_metrics:
                weights[metric_name] = per_metric_weight

        return {
            "target_metric": "weighted_score",
            "weights": weights,
            "thresholds": {
                "task_completion_rate": self.task_completion_rate,
                **self.quality_metrics,
            },
        }


class TemplateLoader:
    """Loads templates and patterns from context-engineering plugin.

    This class provides access to plugin resources for the Goal Definition
    and optimization phases.
    """

    # Template mappings by resource type
    TEMPLATE_MAP = {
        "agent": "templates/subagent-template.md",
        "skill": "templates/skill-template.md",
        "command": "templates/slash-command-template.md",
        "plugin": "templates/plugin-structure.md",
    }

    # Skill mappings by resource type
    SKILL_MAP = {
        "agent": "agent-definition-creation",
        "skill": "skill-creation",
        "command": "command-creation",
        "plugin": "plugin-development",
    }

    def __init__(self, plugin_manager: PluginManager):
        """Initialize template loader.

        Args:
            plugin_manager: PluginManager instance from Phase 1
        """
        self.plugin_manager = plugin_manager
        self._ce_plugin: Optional[Plugin] = None

    @property
    def ce_plugin(self) -> Plugin:
        """Lazy-load context-engineering plugin."""
        if self._ce_plugin is None:
            self._ce_plugin = self.plugin_manager.load_plugin("context-engineering")
        return self._ce_plugin

    def get_template(self, resource_type: str) -> str:
        """Get template content for a resource type.

        Args:
            resource_type: One of 'agent', 'skill', 'command', 'plugin'

        Returns:
            Template content as string

        Raises:
            ValueError: If resource type not supported
            FileNotFoundError: If template file not found
        """
        if resource_type not in self.TEMPLATE_MAP:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        template_path = self.ce_plugin.path / self.TEMPLATE_MAP[resource_type]

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        return template_path.read_text()

    def get_skill_guidance(self, resource_type: str) -> str:
        """Get skill guidance content for goal definition.

        Args:
            resource_type: One of 'agent', 'skill', 'command', 'plugin'

        Returns:
            Skill content as string
        """
        if resource_type not in self.SKILL_MAP:
            raise ValueError(f"No skill defined for resource type: {resource_type}")

        skill_name = self.SKILL_MAP[resource_type]

        # Find skill in plugin
        for skill in self.ce_plugin.skills:
            if skill.name == skill_name:
                return skill.path.read_text()

        raise FileNotFoundError(f"Skill not found: {skill_name}")

    def get_pattern(self, pattern_name: str) -> str:
        """Get a pattern document from the plugin.

        Args:
            pattern_name: Name of pattern (e.g., 'progressive-disclosure')

        Returns:
            Pattern content as string
        """
        pattern_path = self.ce_plugin.path / "patterns" / f"{pattern_name}.md"

        if not pattern_path.exists():
            raise FileNotFoundError(f"Pattern not found: {pattern_path}")

        return pattern_path.read_text()


class GoalDefinitionPhase:
    """Manages the required Goal Definition phase.

    This phase guides users through defining optimization goals using
    templates and skills from the context-engineering plugin.
    """

    def __init__(self, plugin_manager: PluginManager):
        """Initialize goal definition phase.

        Args:
            plugin_manager: PluginManager instance from Phase 1
        """
        self.plugin_manager = plugin_manager
        self.template_loader = TemplateLoader(plugin_manager)

    async def create_goal_definition(
        self,
        resource_type: str,
        resource_name: str,
        interactive: bool = True
    ) -> GoalDefinition:
        """Guide user through goal definition.

        Args:
            resource_type: Type of resource to optimize
            resource_name: Name of resource
            interactive: Whether to prompt user interactively

        Returns:
            GoalDefinition with user-specified goals
        """
        # Step 1: Load skill for guidance
        skill_content = self.template_loader.get_skill_guidance(resource_type)

        # Step 2: Load appropriate template
        template_content = self.template_loader.get_template(resource_type)

        # Step 3: Interactive elicitation (simplified)
        if interactive:
            goals = await self._elicit_goals_interactive(
                resource_type,
                resource_name,
                template_content,
                skill_content
            )
        else:
            # Non-interactive: use defaults
            goals = self._get_default_goals(resource_type)

        # Step 4: Create GoalDefinition
        goal_def = GoalDefinition(
            resource_type=resource_type,
            resource_name=resource_name,
            **goals
        )

        # Step 5: Validate
        self._validate_goals(goal_def)

        return goal_def

    async def _elicit_goals_interactive(
        self,
        resource_type: str,
        resource_name: str,
        template: str,
        skill: str
    ) -> Dict[str, Any]:
        """Interactive goal elicitation.

        This is a simplified implementation. The full version would use
        an agent session to guide the user through goal definition.
        """
        # TODO: Implement full interactive elicitation with agent
        return self._get_default_goals(resource_type)

    def _get_default_goals(self, resource_type: str) -> Dict[str, Any]:
        """Get default goals for a resource type."""
        defaults = {
            "agent": {
                "primary_goals": [
                    "Complete tasks accurately",
                    "Follow best practices for the domain",
                    "Produce well-structured output",
                ],
                "secondary_goals": [
                    "Minimize token usage",
                    "Provide clear explanations",
                ],
                "anti_goals": [
                    "Do not hallucinate information",
                    "Do not skip validation steps",
                ],
                "task_completion_rate": 0.85,
                "quality_metrics": {"accuracy": 0.90},
            },
            "skill": {
                "primary_goals": [
                    "Provide comprehensive guidance",
                    "Include practical examples",
                ],
                "secondary_goals": [
                    "Support progressive disclosure",
                ],
                "anti_goals": [
                    "Do not include outdated information",
                ],
                "task_completion_rate": 0.80,
                "quality_metrics": {"coverage": 0.85},
            },
        }
        return defaults.get(resource_type, defaults["agent"])

    def _validate_goals(self, goal_def: GoalDefinition) -> None:
        """Validate goal definition completeness.

        Raises:
            ValueError: If goals are invalid or incomplete
        """
        if not goal_def.primary_goals:
            raise ValueError("At least one primary goal is required")

        if goal_def.task_completion_rate < 0 or goal_def.task_completion_rate > 1:
            raise ValueError("task_completion_rate must be between 0 and 1")


class OptionalResearchPhase:
    """Manages the optional Research phase using research-team plugin.

    This phase enables on-demand research to inform goal definition
    with best practices and patterns from the field.
    """

    def __init__(self, plugin_manager: PluginManager):
        """Initialize research phase.

        Args:
            plugin_manager: PluginManager instance from Phase 1
        """
        self.plugin_manager = plugin_manager
        self._rt_plugin: Optional[Plugin] = None

    @property
    def rt_plugin(self) -> Plugin:
        """Lazy-load research-team plugin."""
        if self._rt_plugin is None:
            self._rt_plugin = self.plugin_manager.load_plugin("research-team")
        return self._rt_plugin

    async def research_best_practices(
        self,
        resource_type: str,
        domain: str,
        specific_topics: List[str]
    ) -> List[str]:
        """Research best practices for a domain.

        Args:
            resource_type: Type of resource being optimized
            domain: Domain area (e.g., 'Python FastAPI', 'AWS Terraform')
            specific_topics: List of specific topics to research

        Returns:
            List of research insights as strings
        """
        # Build research request
        request = self._build_research_request(resource_type, domain, specific_topics)

        # TODO: Invoke research-team agents
        # This would use the Task tool to spawn research agents
        insights = await self._execute_research(request)

        return insights

    def _build_research_request(
        self,
        resource_type: str,
        domain: str,
        topics: List[str]
    ) -> Dict[str, Any]:
        """Build a research request for the research-team plugin."""
        return {
            "type": "best_practices_research",
            "resource_type": resource_type,
            "domain": domain,
            "topics": topics,
            "output_format": "insights_list",
        }

    async def _execute_research(self, request: Dict[str, Any]) -> List[str]:
        """Execute research request.

        This is a placeholder. Full implementation would:
        1. Spawn lead-research-coordinator agent
        2. Wait for parallel research execution
        3. Collect and return compiled insights
        """
        # TODO: Implement full research execution
        return [
            f"[Placeholder] Best practices for {request['domain']}",
            f"[Placeholder] Research on {request['topics']}",
        ]

    async def update_goal_definition_with_research(
        self,
        goal_def: GoalDefinition,
        insights: List[str]
    ) -> GoalDefinition:
        """Update goal definition with research insights.

        Args:
            goal_def: Existing goal definition
            insights: Research insights to incorporate

        Returns:
            Updated GoalDefinition
        """
        # Add insights to goal definition
        goal_def.research_insights.extend(insights)

        # Optionally refine goals based on insights
        # This could use an LLM to suggest goal improvements

        return goal_def
```

---

## Configuration Templates

CGF uses a two-tier configuration approach:
- **`.env` file**: Runtime settings (API keys, feature flags, resource limits) - loaded by `HarnessConfig`
- **YAML file**: Per-optimization-run configuration (target metrics, test cases, thresholds)

### Optimization Config (YAML)

**File:** `config/optimization-config.yaml`

> **Note:** Paths like `workspace/test-repos` are configurable via `HarnessConfig.workspace_dir`.
> The YAML config references logical paths; the runtime resolves them using the config object.

```yaml
# ContextGrad Framework Configuration

resource:
  type: agent
  name: aws-infra-agent
  baseline_version: v1.0.0

optimization:
  target_metric: weighted_score
  
  # Metric weights (must sum to 1.0)
  weights:
    task_completion_rate: 0.5
    accuracy_score: 0.3
    cost_efficiency: 0.1
    latency_efficiency: 0.1
  
  # Optimization thresholds
  thresholds:
    min_improvement: 0.05  # 5% improvement to keep iteration
    human_review_at: 0.80  # Pause at 80% completion
    stage_progression: 0.70  # 70% to move to next test stage
  
  # DSPy configuration
  dspy:
    optimizer: MIPROv2  # Options: MIPROv2, BootstrapFewShot, COPRO
    max_iterations: 10
    model: gpt-4o
    trainset_size: auto  # Use all available test cases
  
  # TextGrad configuration
  textgrad:
    optimizer: TGD
    max_iterations: 10
    model: gpt-4o
    backward_engine: gpt-4o
    learning_rate: 0.1

# Test case configuration
test_cases:
  - id: simple-flask-app
    weight: 1.0
    enabled: true
  
  - id: django-postgres
    weight: 1.5  # More important
    enabled: true
  
  - id: nodejs-express
    weight: 1.0
    enabled: true
  
  - id: static-site
    weight: 0.8  # Less critical
    enabled: true
  
  - id: react-spa
    weight: 1.0
    enabled: false  # Skip for now
  
  - id: fastapi-ml
    weight: 1.2
    enabled: false

# Testing configuration
testing:
  stages:
    - name: syntax
      enabled: true
      timeout_seconds: 30
    
    - name: unit
      enabled: true
      timeout_seconds: 60
    
    - name: integration
      enabled: true
      timeout_seconds: 180
      sandbox: docker
    
    - name: staging
      enabled: false  # Enable after integration passes
      timeout_seconds: 300
      aws_profile: casdk-staging
    
    - name: live
      enabled: false  # Manual only
      timeout_seconds: 600
      aws_profile: casdk-production

# Cost and resource limits
limits:
  max_cost_per_iteration: 2.00  # USD
  max_cost_total: 50.00  # USD
  max_iterations_total: 30
  max_duration_hours: 8

# Git configuration
git:
  auto_commit: true
  commit_prefix: "[CGF]"
  branch_prefix: "optimize/"
  tag_format: "v{version}-{stage}"  # e.g., v1.1-dspy

# Monitoring
monitoring:
  enable_grafana: true
  enable_prometheus: true
  log_level: INFO
  save_detailed_logs: true
```

---

## Makefile Extensions

Add these targets to casdk-harness `Makefile`:

```makefile
# ContextGrad Framework targets

.PHONY: optimize-agent
optimize-agent:
	@echo "Starting optimization for: $(AGENT)"
	docker compose exec main-agent python -m harness.optimization.cli optimize \
		--agent $(AGENT) \
		--config config/optimization-config.yaml

.PHONY: generate-test-cases
generate-test-cases:
	@echo "Starting test case generator..."
	docker compose exec main-agent python -m harness.optimization.cli generate-tests

.PHONY: optimization-status
optimization-status:
	@echo "Optimization status for: $(RUN_ID)"
	docker compose exec main-agent python -m harness.optimization.cli status \
		--run-id $(RUN_ID)

.PHONY: review-optimization
review-optimization:
	@echo "Starting human review for: $(RUN_ID)"
	docker compose exec main-agent python -m harness.optimization.cli review \
		--run-id $(RUN_ID)

.PHONY: optimization-report
optimization-report:
	@echo "Generating report for: $(RUN_ID)"
	docker compose exec main-agent python -m harness.optimization.cli report \
		--run-id $(RUN_ID) \
		--output workspace/reports/optimization-report-$(RUN_ID).md

.PHONY: list-optimizations
list-optimizations:
	@echo "Listing all optimization runs..."
	docker compose exec main-agent python -m harness.optimization.cli list

.PHONY: optimization-rollback
optimization-rollback:
	@echo "Rolling back $(AGENT) to commit $(COMMIT)"
	docker compose exec main-agent python -m harness.optimization.cli rollback \
		--agent $(AGENT) \
		--commit $(COMMIT)
```

---

## Environment Variables

Add to `.env`:

```bash
# ============================================
# ContextGrad Framework (CGF)
# ============================================

# Enable CGF features
CGF_ENABLED=true

# Optimization settings
CGF_DEFAULT_OPTIMIZER=dspy.MIPROv2
CGF_AUTO_CHECKPOINT_AT=0.80
CGF_MAX_ITERATIONS_DSPY=10
CGF_MAX_ITERATIONS_TEXTGRAD=10

# DSPy configuration
DSPY_MODEL=gpt-4o
DSPY_API_KEY=${ANTHROPIC_API_KEY}

# TextGrad configuration
TEXTGRAD_MODEL=gpt-4o
TEXTGRAD_BACKWARD_ENGINE=gpt-4o

# Testing configuration
CGF_TEST_REPO_DIR=workspace/test-repos
CGF_STAGING_AWS_PROFILE=casdk-staging
CGF_MAX_COST_PER_TEST=0.50  # USD
CGF_TEST_TIMEOUT=300  # seconds

# Git configuration
CGF_GIT_AUTO_COMMIT=true
CGF_GIT_BRANCH_PREFIX=optimize/

# Monitoring
CGF_ENABLE_DETAILED_LOGGING=true
CGF_METRICS_DIR=workspace/optimization-runs
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/optimization/test_resource_manager.py`

```python
import pytest
from pathlib import Path
from harness.optimization.resource_manager import ResourceManager, Resource, ResourceType


def test_load_agent():
    """Test loading an agent definition."""
    manager = ResourceManager(Path.cwd())
    
    # This assumes aws-infra-agent.md exists
    resource = manager.load_agent("aws-infra-agent")
    
    assert resource.type == ResourceType.AGENT
    assert resource.name == "aws-infra-agent"
    assert len(resource.content) > 0


def test_save_and_rollback(tmp_path):
    """Test saving and rolling back a resource."""
    manager = ResourceManager(tmp_path)
    
    # Create initial resource
    resource = Resource(
        type=ResourceType.AGENT,
        name="test-agent",
        version="v1",
        content="Initial prompt",
        metadata={"model": "sonnet", "tools": ["Bash"]}
    )
    
    # Save it
    commit1 = manager.save_resource(resource, "Initial version")
    
    # Modify and save again
    resource.content = "Modified prompt"
    commit2 = manager.save_resource(resource, "Modified version")
    
    # Rollback
    manager.rollback("test-agent", commit1)
    
    # Load and verify
    loaded = manager.load_agent("test-agent")
    assert loaded.content == "Initial prompt"
```

---

## Next Steps

1. **Review** this implementation guide alongside the main specification
2. **Set up** development environment with DSPy and TextGrad
3. **Create** initial agent definition for aws-infra-agent
4. **Implement** Phase 1 (Resource Manager + basic Test Harness)
5. **Test** with a simple optimization run (manual test cases)
6. **Iterate** based on real-world feedback

---

## Questions & Discussion Points

### 1. DSPy vs TextGrad Balance

The spec proposes DSPy first, then TextGrad. Should we:
- **Option A**: Always run both in sequence
- **Option B**: Skip TextGrad if DSPy achieves 90%+
- **Option C**: Let user decide per-optimization run

**Recommendation**: Option B - skip TextGrad if DSPy succeeds, but allow override.

### 2. Test Repository Curation

For the 6 test repositories, should we:
- **Option A**: Clone real open-source repos (more authentic)
- **Option B**: Generate synthetic minimal repos (more controlled)
- **Option C**: Mix of both

**Recommendation**: Option C - start with 4 real + 2 synthetic.

### 3. Human Review Interface

How should human review work?
- **Option A**: CLI-based A/B comparison with approval prompt
- **Option B**: Web UI with side-by-side diffs
- **Option C**: Integration with GitHub/GitLab PR workflow

**Recommendation**: Option A for MVP, Option C for production.

### 4. Cost Management

Should optimization runs have:
- **Hard limits**: Fail fast when budget exceeded
- **Soft limits**: Warn but continue
- **Dynamic limits**: Adjust based on progress

**Recommendation**: Hard limits to prevent runaway costs.

---

## Resources

- [DSPy Documentation](https://dspy.ai/learn/)
- [TextGrad Repository](https://github.com/zou-group/textgrad)
- [Terraform Validation](https://developer.hashicorp.com/terraform/cli/commands/validate)
- [casdk-harness](https://gitlab.provectus.com/provectus-ai-eng/casdk-harness)
