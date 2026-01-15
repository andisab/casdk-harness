# CGF API Reference

Technical reference for the Context Gradient Feedback (CGF) optimization pipeline.

## CLI Reference

### cgf optimize

Run the optimization pipeline on a resource.

```bash
cgf optimize <resource_path> --goal <optimization_goal> [options]
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `resource_path` | Path to the resource file to optimize |
| `--goal` | Optimization goal describing desired improvements |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--optimizer` | string | `dspy` | Optimizer to use: `dspy`, `textgrad` |
| `--review` | flag | `false` | Enable review mode with checkpoints |
| `--max-iterations` | int | `10` | Maximum optimization iterations |
| `--early-stop` | float | `0.01` | Early stopping threshold (score improvement) |
| `--output` | path | auto | Output path for optimized resource |
| `--output-format` | string | `markdown` | Output format: `markdown`, `json`, `yaml` |
| `--save-iterations` | flag | `false` | Save each iteration's results |
| `--dry-run` | flag | `false` | Validate configuration without executing |
| `--verbose` | flag | `false` | Enable verbose logging |

#### Examples

```bash
# Basic optimization
cgf optimize agents/python-expert.md --goal "async programming"

# With review mode and custom output
cgf optimize agents/python-expert.md \
  --goal "error handling" \
  --review \
  --output workspace/python-expert-v2.md

# Using TextGrad optimizer with more iterations
cgf optimize skills/research.md \
  --goal "trigger accuracy" \
  --optimizer textgrad \
  --max-iterations 20

# Dry run to validate configuration
cgf optimize commands/deploy.md \
  --goal "validation errors" \
  --dry-run
```

### cgf resume

Resume a paused optimization run from checkpoint.

```bash
cgf resume --workspace <workspace_path> [options]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--workspace` | path | Path to workspace directory (required) |
| `--accept` | flag | Accept current recommendation and continue |
| `--refine` | flag | Request refinement iteration |
| `--reject` | flag | Reject optimization and stop |

### cgf status

Check status of an optimization run.

```bash
cgf status --workspace <workspace_path>
```

#### Output

```
Run ID: opt_python-expert_20250115_120000
Status: RUNNING
Phase: OPTIMIZE
Progress: Iteration 3/10
Scores: 0.65 → 0.78 (+20.0%)
```

---

## State Machine

### States

| State | Description | Transitions To |
|-------|-------------|----------------|
| `INIT` | Pipeline initialized | `RESEARCH`, `FAILED` |
| `RESEARCH` | Analyzing resource and goal | `TEST_GEN`, `FAILED` |
| `TEST_GEN` | Generating test suite | `OPTIMIZE`, `FAILED` |
| `OPTIMIZE` | Running optimization iterations | `EVALUATE`, `FAILED` |
| `EVALUATE` | Reviewing optimization results | `FINALIZE`, `OPTIMIZE`, `FAILED` |
| `FINALIZE` | Processing evaluation decision | `COMPLETE`, `OPTIMIZE`, `FAILED` |
| `COMPLETE` | Pipeline completed successfully | - |
| `FAILED` | Pipeline failed | - |

### State Diagram

```
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE
   ↓       ↓          ↓          ↓         ↓   ↑        ↓
 FAILED  FAILED    FAILED     FAILED    FAILED ←    FAILED
                                           ↓
                                      (REFINE)
                                           ↓
                                       OPTIMIZE
```

### State Events

| Event | Trigger | Data |
|-------|---------|------|
| `state_changed` | State transition | `{from: str, to: str, timestamp: str}` |
| `checkpoint_created` | Checkpoint saved | `{state: str, path: str}` |
| `iteration_completed` | Optimization iteration done | `{iteration: int, score: float}` |
| `artifact_created` | New artifact generated | `{type: str, path: str}` |

---

## Artifact Schemas

### run_state.json

Tracks pipeline execution state.

```json
{
  "run_id": "opt_python-expert_20250115_120000",
  "state": "OPTIMIZE",
  "resource": {
    "id": "python-expert",
    "type": "agent",
    "path": "agents/configs/python-expert.md",
    "optimization_goal": "improve async programming guidance"
  },
  "strategy": "prompt_optimization",
  "optimizer": "dspy",
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
  path: agents/configs/python-expert.md
  type: agent
  id: python-expert
  optimization_goal: improve async programming guidance

strategy: prompt_optimization
optimizer: dspy

options:
  max_iterations: 10
  early_stopping_threshold: 0.01
  review_mode: false
  learning_rate: 0.1
  batch_size: 4
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

| Type | Description | Criteria Format |
|------|-------------|-----------------|
| `contains` | Check if response contains text | Substring to find |
| `not_contains` | Check if response does NOT contain text | Substring to exclude |
| `regex` | Match response against regex | Regex pattern |
| `llm_judge` | AI evaluation of response | Natural language criteria |
| `exact` | Exact string match | Expected string |
| `json_schema` | Validate JSON structure | JSON Schema |

### {resource}-v{n}.md.summary.json

Optimization run summary.

```json
{
  "run_id": "opt_python-expert_20250115_120000",
  "timestamp": "2025-01-15T12:10:00Z",
  "agent": {
    "name": "python-expert",
    "path": "agents/configs/python-expert.md"
  },
  "test_suite": {
    "name": "python-expert-async-tests",
    "path": "workspace/python-expert/tests/test_suite.yaml",
    "test_count": 15
  },
  "optimizer": "dspy",
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
    "learning_rate": 0.1,
    "early_stopping_threshold": 0.01
  }
}
```

---

## Python API

### OptimizationRun

Main pipeline orchestrator.

```python
from harness.optimization.pipeline import OptimizationRun, PipelineConfig
from harness.optimization.optimizers import OptimizerType

# Configure pipeline
config = PipelineConfig(
    agent_path="agents/configs/python-expert.md",
    test_suite_path="tests/optimization/python_expert_tests.yaml",
    optimizer_type=OptimizerType.DSPY,
    max_iterations=10,
    early_stopping_threshold=0.01,
)

# Create and execute run
run = OptimizationRun(config)
result = await run.execute()

# Check results
if result.success:
    print(f"Optimization improved score by {result.improvement_percent:.1f}%")
    print(f"Optimized prompt:\n{result.optimized_prompt}")
else:
    print(f"Optimization failed: {result.error}")

# Get run summary
summary = run.get_summary()
print(f"Run ID: {summary.run_id}")
print(f"Status: {summary.status}")
```

### PipelineConfig

Configuration dataclass.

```python
@dataclass
class PipelineConfig:
    agent_path: str | Path
    test_suite_path: str | Path
    optimizer_type: OptimizerType = OptimizerType.DSPY
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

### Custom Validators

Add custom validation types for test cases.

```python
from harness.optimization.testcases.validators import (
    ValidatorRegistry,
    BaseValidator,
    ValidationResult,
)

class CustomValidator(BaseValidator):
    """Custom validation implementation."""

    name = "custom_check"

    async def validate(
        self,
        response: str,
        criteria: str,
        context: dict[str, Any] | None = None,
    ) -> ValidationResult:
        # Implement custom validation logic
        passed = self._check_custom_criteria(response, criteria)

        return ValidationResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reasoning="Custom validation result",
            details={"criteria": criteria},
        )

# Register validator
ValidatorRegistry.register(CustomValidator())

# Use in test cases
test_case = {
    "id": "custom-001",
    "prompt": "Test prompt",
    "expected_behavior": "Expected behavior",
    "validation": {
        "type": "custom_check",
        "criteria": "custom criteria"
    }
}
```

### Custom Optimizers

Implement custom optimization strategies.

```python
from harness.optimization.optimizers.protocol import (
    OptimizerProtocol,
    OptimizationResult,
)

class CustomOptimizer(OptimizerProtocol):
    """Custom optimizer implementation."""

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
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
            ...
        )

# Register optimizer
from harness.optimization.optimizers import OptimizerRegistry
OptimizerRegistry.register("custom", CustomOptimizer)
```

### Custom Resource Types

Add support for new resource types.

```python
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

# Register resource type
from harness.optimization.resources import ResourceRegistry
ResourceRegistry.register("custom", CustomResource)
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
