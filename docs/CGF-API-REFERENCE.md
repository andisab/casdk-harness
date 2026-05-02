# CGF API Reference

Technical reference for the Context Gradient Feedback (CGF) optimization pipeline.

## CLI Reference

### Make Targets

Primary interface for running CGF optimization.

```bash
# Initialize a new workspace
make cgf-init NAME=<agent-name>

# Run optimization (discovers SPEC.md automatically)
make optimize

# Run optimization with explicit workspace
make optimize WORKSPACE=<workspace_path>

# Run optimization with direct goal (skips Q&A)
make optimize WORKSPACE=<workspace_path> GOAL="<optimization_goal>"

# Validate setup without executing
make optimize-dryrun WORKSPACE=<workspace_path>

# Check optimization status
make cgf-status

# Clean session state files
make cgf-clean

# Full reset (remove all workspaces)
make cgf-reset
```

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CGF_ITERATIONS` | int | `10` | Maximum optimization iterations per section |
| `CGF_ITERATION_REVIEW` | bool | `false` | Pause for review after each iteration |
| `CGF_EVAL_MODEL` | string | `sonnet` | Eval model for LLM validators: `haiku`, `sonnet`, `opus` |
| `CGF_VERBOSE` | bool | `true` | Show progress output |
| `CGF_EARLY_STOP` | float | `0.01` | Early stopping threshold |

### Examples

```bash
# Initialize workspace and copy resource
make cgf-init NAME=python-expert
cp src/harness/agents/configs/python-expert.md workspace/python-expert/

# Run optimization with Q&A phase
make optimize WORKSPACE=workspace/python-expert

# Skip Q&A with direct goal
make optimize WORKSPACE=workspace/python-expert \
  GOAL="improve async/await pattern explanations"

# Enable review mode (pause after each iteration)
CGF_ITERATION_REVIEW=true make optimize WORKSPACE=workspace/python-expert

# Validate setup
make optimize-dryrun WORKSPACE=workspace/python-expert
```

### Resuming Optimization

Optimization state is tracked in `sessions/`. To resume from checkpoint:

```bash
# Re-run with same workspace (auto-resumes from checkpoint)
make optimize WORKSPACE=workspace/python-expert

# To reset and start over, delete sessions directory
rm -rf workspace/python-expert/sessions/
make optimize WORKSPACE=workspace/python-expert
```

### Optimization Status

```bash
make cgf-status
```

#### Output

```
Workspace: workspace/python-expert
Status: RUNNING
Phase: OPTIMIZE
Progress: Iteration 3/10
Scores: 0.65 → 0.78 (+20.0%)
```

---

## State Machine

### Pipeline Phases (RunPhase)

| Phase | Description | Transitions To |
|-------|-------------|----------------|
| `INIT` | Pipeline initialized | `LOAD_RESOURCES`, `FAILED` |
| `LOAD_RESOURCES` | Loading agent and test suite | `VALIDATE`, `FAILED` |
| `VALIDATE` | Validating configuration | `BASELINE`, `FAILED` |
| `BASELINE` | Computing baseline scores | `OPTIMIZE`, `FAILED` |
| `OPTIMIZE` | Running optimization iterations | `SAVE`, `FAILED` |
| `SAVE` | Saving optimized resource | `COMPLETE`, `FAILED` |
| `COMPLETE` | Pipeline completed successfully | - |
| `FAILED` | Pipeline failed | - |

### Run Status

| Status | Description |
|--------|-------------|
| `PENDING` | Run created but not started |
| `RUNNING` | Run currently executing |
| `COMPLETED` | Run finished successfully |
| `FAILED` | Run encountered an error |

### Phase Diagram

```
INIT → LOAD_RESOURCES → VALIDATE → BASELINE → OPTIMIZE → SAVE → COMPLETE
  ↓          ↓             ↓          ↓          ↓        ↓
FAILED     FAILED       FAILED     FAILED     FAILED   FAILED
```

### State Events

| Event | Trigger | Data |
|-------|---------|------|
| `phase_changed` | Phase transition | `{from: str, to: str, timestamp: str}` |
| `checkpoint_created` | Checkpoint saved | `{phase: str, path: str}` |
| `iteration_completed` | Optimization iteration done | `{iteration: int, score: float}` |
| `artifact_created` | New artifact generated | `{type: str, path: str}` |

---

## Artifact Schemas

### run_state.json

Tracks pipeline execution state.

```json
{
  "run_id": "opt_python-expert_20250115_120000",
  "phase": "OPTIMIZE",
  "status": "RUNNING",
  "resource": {
    "id": "python-expert",
    "type": "agent",
    "path": "workspace/python-expert/python-expert.md",
    "optimization_goal": "improve async programming guidance"
  },
  "strategy": "prompt_optimization",
  "optimizer_mode": "agentic",
  "options": {
    "max_iterations": 10,
    "early_stopping_threshold": 0.01,
    "review_mode": false
  },
  "artifacts": {
    "run_config": "workspace/python-expert/run_config.yaml",
    "eval_criteria": "workspace/python-expert/research/eval_criteria.yaml",
    "test_suite": "workspace/python-expert/tests/test_suite.yaml"
  },
  "timestamps": {
    "created": "2025-01-15T12:00:00Z",
    "updated": "2025-01-15T12:05:00Z"
  },
  "checkpoints": [
    {
      "state": "RESEARCH",
      "timestamp": "2025-01-15T12:01:00Z",
      "path": "workspace/python-expert/checkpoint_research.json"
    }
  ],
  "iterations": [
    {
      "iteration": 1,
      "score": 0.72,
      "timestamp": "2025-01-15T12:03:00Z"
    }
  ],
  "error": null
}
```

### run_config.yaml

Pipeline configuration.

```yaml
resource:
  path: workspace/python-expert/python-expert.md
  type: agent
  id: python-expert
  optimization_goal: improve async programming guidance

strategy: prompt_optimization

options:
  max_iterations: 10
  early_stopping_threshold: 0.01
  review_mode: false
  eval_model: sonnet  # haiku, sonnet, or opus
```

### eval_criteria.yaml

Evaluation criteria from research phase.

```yaml
resource_id: python-expert
resource_type: agent
optimization_goal: improve async programming guidance

competencies:
  - name: Async Pattern Explanation
    description: Explains async/await patterns clearly
    importance: high
    indicators:
      - Uses practical examples
      - Explains event loop concepts
      - Covers error handling in async code
  - name: Code Quality Guidance
    description: Provides maintainable async code patterns
    importance: medium
    indicators:
      - Suggests proper exception handling
      - Recommends structured concurrency
      - Addresses common pitfalls

edge_cases:
  - scenario: Mixing sync and async code
    expected_handling: Explains proper integration patterns
  - scenario: Nested async contexts
    expected_handling: Warns about deadlock risks

common_mistakes:
  - mistake: Blocking calls in async functions
    impact: high
  - mistake: Missing error propagation
    impact: medium

best_practices:
  - practice: Use asyncio.gather for concurrent operations
    source: Python documentation
  - practice: Prefer structured concurrency patterns
    source: Industry standards
```

### test_suite.yaml

Test suite for optimization evaluation.

```yaml
name: python-expert-async-tests
agent_name: python-expert
version: "1.0"

test_cases:
  - id: async-001
    prompt: Explain how async/await works in Python
    expected_behavior: |
      Provides clear explanation of event loop,
      coroutines, and async execution model
    validation:
      type: llm_judge
      criteria: |
        Response explains event loop concept,
        shows practical examples,
        mentions await points
    tags:
      - core
      - explanation
    difficulty: basic

  - id: async-002
    prompt: Show me how to run multiple API calls concurrently
    expected_behavior: Uses asyncio.gather or similar patterns
    validation:
      type: contains
      criteria: asyncio.gather
    tags:
      - practical
      - concurrency
    difficulty: intermediate

  - id: async-003
    prompt: How do I handle errors in async code?
    expected_behavior: |
      Demonstrates try/except in async functions,
      exception groups, error propagation
    validation:
      type: llm_judge
      criteria: |
        Shows error handling patterns,
        mentions exception propagation,
        discusses cleanup
    tags:
      - error-handling
      - advanced
    difficulty: advanced
```

### Validation Types

| Type | Description | Criteria Format | Mode |
|------|-------------|-----------------|------|
| `exact` | Exact string match | Expected string | Deterministic |
| `contains` | Check if response contains text | Substring to find | Deterministic |
| `regex` | Match response against regex | Regex pattern | Deterministic |
| `code` | Execute Python code to validate | Python expression returning bool | Deterministic |
| `code_syntax` | Validate code syntax | Language identifier | Deterministic |
| `llm_judge` | AI evaluation of response | Natural language criteria | LLM-based |
| `code_llm` | LLM-based code quality assessment | Natural language criteria | LLM-based |


### sessions/{resource}-v{n}.summary.json

Optimization run summary (machine-readable, stored in sessions/ folder).

```json
{
  "run_id": "opt_python-expert_20250115_120000",
  "timestamp": "2025-01-15T12:10:00Z",
  "agent": {
    "name": "python-expert",
    "path": "workspace/python-expert/python-expert.md"
  },
  "test_suite": {
    "name": "python-expert-async-tests",
    "path": "workspace/python-expert/tests/tests.yaml",
    "test_count": 15
  },
  "optimizer_mode": "agentic",
  "scores": {
    "original": 0.65,
    "final": 0.82,
    "improvement": 0.17,
    "improvement_percent": 26.15
  },
  "iterations": 5,
  "duration_seconds": 120.5,
  "output_path": "workspace/python-expert/python-expert-v1.md",
  "config": {
    "max_iterations": 10,
    "eval_model": "sonnet",
    "early_stopping_threshold": 0.01
  }
}
```

---

## Python API

### Agentic Optimization (Default)

The default and recommended approach uses the agentic optimizer with LLM self-critique.

```python
from harness.optimization import (
    get_agentic_optimizer,
    AgentResource,
    AgenticOptimizationConfig,
)

# Load resource
resource = AgentResource.load("workspace/python-expert/python-expert.md")

# Configure agentic optimization
config = AgenticOptimizationConfig(
    max_iterations=10,
    eval_model="sonnet",  # haiku, sonnet, or opus
)

# Get optimizer and run
optimizer = get_agentic_optimizer()
result = await optimizer.optimize(resource, config)

# Check results
if result.success:
    print(f"Optimization improved score by {result.improvement_percent:.1f}%")
    print(f"Optimized prompt:\n{result.optimized_prompt}")
else:
    print(f"Optimization failed: {result.error}")
```

### OptimizationRun (Pipeline)

Full pipeline orchestrator for workspace-based optimization.

```python
from harness.optimization.pipeline import OptimizationRun, PipelineConfig, OutputFormat

# Configure pipeline
config = PipelineConfig(
    agent_path="workspace/python-expert/python-expert.md",
    test_suite_path="workspace/python-expert/tests/tests.yaml",  # optional for agentic
    output_path="workspace/python-expert/python-expert-v1.md",
    output_format=OutputFormat.MARKDOWN,
    dry_run=False,
    save_iterations=False,
)

# Create and execute run
run = OptimizationRun(config)
result = await run.execute()

# Get run summary
summary = run.get_summary()
print(f"Run ID: {summary.run_id}")
print(f"Status: {summary.status}")
print(f"Phase: {summary.phase}")
```

### PipelineConfig

Configuration dataclass.

```python
@dataclass
class PipelineConfig:
    agent_path: str | Path
    test_suite_path: str | Path | None = None  # Optional for agentic mode
    output_path: str | Path | None = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    dry_run: bool = False
    save_iterations: bool = False
    optimization_config: OptimizationConfig | None = None

    def get_output_path(self) -> Path:
        """Get output path, generating if not specified."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        ...
```

### OptimizationResult

Result from optimization run.

```python
@dataclass
class OptimizationResult:
    success: bool
    original_prompt: str
    optimized_prompt: str
    original_score: float
    final_score: float
    improvement: float
    improvement_percent: float
    iterations: list[IterationResult]
    total_iterations: int
    total_duration_seconds: float
    config: OptimizationConfig
    agent_name: str
    suite_name: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        ...
```

### TestSuiteLoader

Load and validate test suites.

```python
from harness.optimization.testcases import TestSuiteLoader

# Load from file
suite = TestSuiteLoader.load("tests/optimization/agent_tests.yaml")

# Access test cases
for tc in suite.test_cases:
    print(f"{tc.id}: {tc.prompt}")

# Validate suite
errors = TestSuiteLoader.validate(suite)
if errors:
    for error in errors:
        print(f"Validation error: {error}")
```

### AgentResource

Load and manipulate agent resources.

```python
from harness.optimization.resources import AgentResource

# Load from file
resource = AgentResource.load("agents/configs/python-expert.md")

# Access properties
print(f"Name: {resource.name}")
print(f"Model: {resource.model}")
print(f"System prompt: {resource.system_prompt}")

# Create modified copy
modified = resource.with_prompt(new_prompt)
modified.save("workspace/python-expert-v1.md")
```

---

## Extension Points

### Built-in Validators

CGF provides seven built-in validators. Custom validators are not currently supported via
a registry pattern, but you can extend the framework by modifying the validator module.

```python
from harness.optimization.testcases.validators import (
    ExactValidator,
    ContainsValidator,
    RegexValidator,
    CodeValidator,
    CodeSyntaxValidator,
    LLMJudgeValidator,
    CodeLLMValidator,
)

# Example: Using validators programmatically
validator = ContainsValidator()
result = await validator.validate(
    response="The answer is asyncio.gather()",
    criteria="asyncio.gather",
)
print(f"Passed: {result.passed}, Score: {result.score}")

# LLM-based validation with eval model
llm_validator = LLMJudgeValidator(model="sonnet")
result = await llm_validator.validate(
    response="Use asyncio.gather() for concurrent execution...",
    criteria="Explains concurrent async patterns clearly",
)
print(f"Score: {result.score}, Reasoning: {result.reasoning}")
```

### Custom Optimizers

Implement custom optimization strategies by following the `OptimizerProtocol`.

```python
from harness.optimization.optimizers.protocol import (
    OptimizerProtocol,
    OptimizationResult,
    OptimizationConfig,
)
from harness.optimization import AgentResource, TestSuite

class CustomOptimizer(OptimizerProtocol):
    """Custom optimizer implementation."""

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite | None,
        config: OptimizationConfig,
    ) -> OptimizationResult:
        # Implement custom optimization logic
        original_score = await self._evaluate(resource, test_suite)

        best_prompt = resource.system_prompt
        best_score = original_score

        for iteration in range(config.max_iterations):
            # Generate candidates
            candidates = self._generate_candidates(best_prompt)

            # Evaluate candidates
            for candidate in candidates:
                score = await self._evaluate_prompt(candidate, test_suite)
                if score > best_score:
                    best_prompt = candidate
                    best_score = score

            # Check early stopping
            if best_score - original_score < config.early_stopping_threshold:
                break

        return OptimizationResult(
            success=True,
            original_prompt=resource.system_prompt,
            optimized_prompt=best_prompt,
            original_score=original_score,
            final_score=best_score,
            # ... other fields
        )

# Use custom optimizer directly (no registry pattern)
optimizer = CustomOptimizer()
result = await optimizer.optimize(resource, test_suite, config)
```

### Custom Resource Types

Add support for new resource types by extending `BaseResource`.

```python
from pathlib import Path
from harness.optimization.resources.base import BaseResource

class CustomResource(BaseResource):
    """Custom resource type."""

    resource_type = "custom"
    optimization_strategy = "custom_optimization"

    def __init__(
        self,
        name: str,
        custom_field: str,
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self.custom_field = custom_field

    @classmethod
    def load(cls, path: str | Path) -> "CustomResource":
        """Load resource from file."""
        content = Path(path).read_text()
        metadata, body = cls._parse_frontmatter(content)

        return cls(
            name=metadata["name"],
            custom_field=metadata.get("custom_field", ""),
            system_prompt=body,
        )

    def with_prompt(self, new_prompt: str) -> "CustomResource":
        """Create copy with new prompt."""
        return CustomResource(
            name=self.name,
            custom_field=self.custom_field,
            system_prompt=new_prompt,
        )

# Register in ResourceRegistry
from harness.optimization.resources import ResourceRegistry

registry = ResourceRegistry()
custom_resource = CustomResource.load("path/to/custom.md")
registry.register(custom_resource)  # Register instance, not type
```

---

## Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `E001` | Resource file not found | Check file path exists |
| `E002` | Invalid resource format | Verify YAML frontmatter |
| `E003` | Test suite validation failed | Check test case structure |
| `E004` | Optimizer not available | Install required package |
| `E005` | API rate limit exceeded | Reduce concurrency or wait |
| `E006` | State transition invalid | Check pipeline state |
| `E007` | Checkpoint not found | Verify workspace path |
| `E008` | Empty system prompt | Add content after frontmatter |
| `E009` | No test cases generated | Make goal more specific |
| `E010` | Optimization timeout | Increase timeout or iterations |
