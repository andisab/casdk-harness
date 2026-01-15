"""E2E test fixtures for CGF optimization pipeline.

Provides fixtures for:
- Isolated workspace creation and cleanup
- Mock resource generation (agents, skills, commands)
- Pipeline state tracking
- Optimizer mocking for deterministic testing
"""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml


@dataclass
class MockOptimizationResult:
    """Mock result from optimization run."""

    success: bool = True
    original_score: float = 0.65
    final_score: float = 0.82
    improvement: float = 0.17
    improvement_percent: float = 26.15
    iterations: int = 5
    duration_seconds: float = 10.0
    error: str | None = None


@dataclass
class CGFWorkspace:
    """CGF workspace manager for E2E tests.

    Provides methods to:
    - Create workspace structure
    - Generate mock artifacts
    - Validate state transitions
    - Clean up after tests
    """

    root: Path
    resource_id: str
    resource_type: str = "agent"

    def __post_init__(self) -> None:
        """Initialize workspace directories."""
        self.workspace_dir = self.root / "workspace" / self.resource_id
        self.research_dir = self.workspace_dir / "research"
        self.notes_dir = self.research_dir / "notes"
        self.tests_dir = self.workspace_dir / "tests"
        self.reviews_dir = self.workspace_dir / "reviews"

    def create(self) -> None:
        """Create workspace directory structure."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def write_run_state(self, state: str, **kwargs: Any) -> Path:
        """Write run_state.json with given state.

        Args:
            state: Current pipeline state (INIT, RESEARCH, etc.)
            **kwargs: Additional fields to include in state

        Returns:
            Path to run_state.json
        """
        config_path = str(self.workspace_dir / "run_config.yaml")
        run_state = {
            "run_id": f"cgf-{self.resource_id[:8]}",
            "state": state,
            "resource": {
                "id": self.resource_id,
                "type": self.resource_type,
                "path": f"agents/configs/{self.resource_id}.md",
                "optimization_goal": "test optimization",
            },
            "strategy": self._get_strategy(),
            "optimizer": "dspy",
            "options": {
                "max_iterations": 10,
                "review_mode": False,
            },
            "artifacts": {
                "run_config": config_path,
                "eval_criteria": None,
                "test_suite": None,
            },
            "timestamps": {
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
            },
            "checkpoints": [],
            "iterations": [],
            "error": None,
            **kwargs,
        }

        state_path = self.workspace_dir / "run_state.json"
        state_path.write_text(json.dumps(run_state, indent=2))
        return state_path

    def write_run_config(self, goal: str = "test optimization") -> Path:
        """Write run_config.yaml.

        Args:
            goal: Optimization goal

        Returns:
            Path to run_config.yaml
        """
        config = {
            "resource": {
                "path": f"agents/configs/{self.resource_id}.md",
                "type": self.resource_type,
                "id": self.resource_id,
                "optimization_goal": goal,
            },
            "strategy": self._get_strategy(),
            "optimizer": "dspy",
            "options": {
                "max_iterations": 10,
                "early_stopping_threshold": 0.01,
                "review_mode": False,
            },
        }

        config_path = self.workspace_dir / "run_config.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))
        return config_path

    def write_eval_criteria(
        self, competencies: list[dict] | None = None
    ) -> Path:
        """Write eval_criteria.yaml with mock competencies.

        Args:
            competencies: Optional list of competency dicts

        Returns:
            Path to eval_criteria.yaml
        """
        if competencies is None:
            competencies = [
                {
                    "name": "Test Competency 1",
                    "description": "First test competency",
                    "importance": "high",
                    "indicators": ["indicator1", "indicator2"],
                },
                {
                    "name": "Test Competency 2",
                    "description": "Second test competency",
                    "importance": "medium",
                    "indicators": ["indicator3"],
                },
                {
                    "name": "Test Competency 3",
                    "description": "Third test competency",
                    "importance": "low",
                    "indicators": ["indicator4"],
                },
            ]

        criteria = {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "optimization_goal": "test optimization",
            "competencies": competencies,
            "edge_cases": [
                {
                    "scenario": "Edge case 1",
                    "expected_handling": "Handle gracefully",
                },
            ],
            "common_mistakes": [
                {"mistake": "Common mistake 1", "impact": "medium"},
            ],
            "best_practices": [
                {"practice": "Best practice 1", "source": "research"},
            ],
        }

        criteria_path = self.research_dir / "eval_criteria.yaml"
        criteria_path.write_text(yaml.dump(criteria, default_flow_style=False))
        return criteria_path

    def write_test_suite(
        self, test_cases: list[dict] | None = None
    ) -> Path:
        """Write test_suite.yaml with mock test cases.

        Args:
            test_cases: Optional list of test case dicts

        Returns:
            Path to test_suite.yaml
        """
        if test_cases is None:
            test_cases = [
                {
                    "id": "test-001",
                    "prompt": "Test prompt 1",
                    "expected_behavior": "Expected behavior 1",
                    "validation": {
                        "type": "contains",
                        "criteria": "expected",
                    },
                    "tags": ["basic"],
                    "difficulty": "basic",
                },
                {
                    "id": "test-002",
                    "prompt": "Test prompt 2",
                    "expected_behavior": "Expected behavior 2",
                    "validation": {
                        "type": "llm_judge",
                        "criteria": "Verify response quality",
                    },
                    "tags": ["intermediate"],
                    "difficulty": "intermediate",
                },
                {
                    "id": "test-003",
                    "prompt": "Test prompt 3",
                    "expected_behavior": "Expected behavior 3",
                    "validation": {"type": "regex", "criteria": r"\d+"},
                    "tags": ["advanced"],
                    "difficulty": "advanced",
                },
            ]

        suite = {
            "name": f"{self.resource_id}-tests",
            "agent_name": self.resource_id,
            "version": "1.0",
            "test_cases": test_cases,
        }

        suite_path = self.tests_dir / "test_suite.yaml"
        suite_path.write_text(yaml.dump(suite, default_flow_style=False))
        return suite_path

    def write_optimized_resource(
        self, version: int = 1, score: float = 0.82
    ) -> Path:
        """Write mock optimized resource file.

        Args:
            version: Version number
            score: Final optimization score

        Returns:
            Path to optimized resource
        """
        improvement = (score - 0.65) / 0.65 * 100
        content = f"""---
name: {self.resource_id}-optimized
description: Optimized version of {self.resource_id}
model: sonnet
tools: ["Read", "Write"]
optimization:
  original_score: 0.65
  final_score: {score}
  improvement_percent: "{improvement:.1f}%"
  iterations: 5
  optimizer: dspy
---

This is the optimized system prompt for {self.resource_id}.
It has been enhanced through CGF optimization.
"""
        filename = f"{self.resource_id}-v{version}.md"
        resource_path = self.workspace_dir / filename
        resource_path.write_text(content)

        # Also write summary JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = {
            "run_id": f"opt_{self.resource_id}_{timestamp}",
            "scores": {
                "original": 0.65,
                "final": score,
                "improvement": score - 0.65,
                "improvement_percent": improvement,
            },
            "iterations": 5,
            "duration_seconds": 10.0,
            "config": {
                "max_iterations": 10,
                "optimizer": "dspy",
            },
        }
        summary_path = resource_path.with_suffix(".md.summary.json")
        summary_path.write_text(json.dumps(summary, indent=2))

        return resource_path

    def write_original_resource(self) -> Path:
        """Write mock original resource file.

        Returns:
            Path to original resource
        """
        content = f"""---
name: {self.resource_id}
description: Original {self.resource_type} for testing
model: sonnet
tools: ["Read", "Write"]
---

This is the original system prompt for {self.resource_id}.
It needs optimization for test purposes.
"""
        resource_path = self.workspace_dir / f"{self.resource_id}-orig.md"
        resource_path.write_text(content)
        return resource_path

    def write_review(
        self, version: int = 1, recommendation: str = "ACCEPT"
    ) -> Path:
        """Write mock review report.

        Args:
            version: Version number being reviewed
            recommendation: ACCEPT, REFINE, or REJECT

        Returns:
            Path to review file
        """
        if recommendation == "ACCEPT":
            reasoning = "The optimization achieved significant improvement."
        elif recommendation == "REFINE":
            reasoning = "Further refinement needed."
        else:
            reasoning = "The optimization did not meet quality standards."

        content = f"""# Evaluation Report: {self.resource_id} v{version}

## Summary

| Metric | Value |
|--------|-------|
| Original Score | 0.65 |
| Final Score | 0.82 |
| Improvement | 26.2% |
| Iterations | 5 |
| Duration | 10s |
| Recommendation | **{recommendation}** |

## Multi-Dimensional Evaluation

### 1. COHERENCE (Structure & Readability)

The optimized prompt maintains clear structure.

**Assessment:** GOOD

### 2. ALIGNMENT (Goal Fidelity)

Optimization addresses the stated goal.

**Assessment:** GOOD

### 3. IMPROVEMENT (What Got Better)

Significant improvements in target competencies.

### 4. REGRESSION (What Was Lost)

No significant regressions detected.

## Recommendation

**{recommendation}**

### Reasoning

{reasoning}
"""
        review_path = self.reviews_dir / f"v{version}_review.md"
        review_path.write_text(content)
        return review_path

    def read_run_state(self) -> dict[str, Any]:
        """Read current run_state.json.

        Returns:
            Parsed run state dict
        """
        state_path = self.workspace_dir / "run_state.json"
        if state_path.exists():
            return json.loads(state_path.read_text())
        return {}

    def get_current_state(self) -> str:
        """Get current pipeline state.

        Returns:
            Current state string or empty string if not found
        """
        run_state = self.read_run_state()
        return run_state.get("state", "")

    def _get_strategy(self) -> str:
        """Get optimization strategy for resource type."""
        strategies = {
            "agent": "prompt_optimization",
            "skill": "trigger_optimization",
            "command": "schema_optimization",
            "workflow": "workflow_optimization",
            "mcp": "schema_optimization",
            "hook": "trigger_optimization",
        }
        return strategies.get(self.resource_type, "prompt_optimization")


@pytest.fixture
def cgf_workspace(tmp_path: Path) -> Generator[CGFWorkspace, None, None]:
    """Create isolated CGF workspace for testing.

    Yields:
        CGFWorkspace instance with test-agent resource
    """
    workspace = CGFWorkspace(
        root=tmp_path,
        resource_id="test-agent",
        resource_type="agent",
    )
    workspace.create()
    yield workspace
    # Cleanup handled by tmp_path fixture


@pytest.fixture
def cgf_agent_workspace(
    tmp_path: Path,
) -> Generator[CGFWorkspace, None, None]:
    """Create CGF workspace for agent optimization testing.

    Yields:
        CGFWorkspace configured for agent resource
    """
    workspace = CGFWorkspace(
        root=tmp_path,
        resource_id="python-expert",
        resource_type="agent",
    )
    workspace.create()
    workspace.write_original_resource()
    workspace.write_run_config(goal="async programming")
    workspace.write_run_state("INIT")
    yield workspace


@pytest.fixture
def cgf_skill_workspace(
    tmp_path: Path,
) -> Generator[CGFWorkspace, None, None]:
    """Create CGF workspace for skill optimization testing.

    Yields:
        CGFWorkspace configured for skill resource
    """
    workspace = CGFWorkspace(
        root=tmp_path,
        resource_id="joplin-research",
        resource_type="skill",
    )
    workspace.create()
    workspace.write_original_resource()
    workspace.write_run_config(goal="better trigger detection")
    workspace.write_run_state("INIT")
    yield workspace


@pytest.fixture
def cgf_command_workspace(
    tmp_path: Path,
) -> Generator[CGFWorkspace, None, None]:
    """Create CGF workspace for command optimization testing.

    Yields:
        CGFWorkspace configured for command resource
    """
    workspace = CGFWorkspace(
        root=tmp_path,
        resource_id="cgf-optimize",
        resource_type="command",
    )
    workspace.create()
    workspace.write_original_resource()
    workspace.write_run_config(goal="improved error handling")
    workspace.write_run_state("INIT")
    yield workspace


@pytest.fixture
def cgf_workflow_workspace(
    tmp_path: Path,
) -> Generator[CGFWorkspace, None, None]:
    """Create CGF workspace for workflow optimization testing.

    Yields:
        CGFWorkspace configured for workflow resource
    """
    workspace = CGFWorkspace(
        root=tmp_path,
        resource_id="deployment-flow",
        resource_type="workflow",
    )
    workspace.create()
    workspace.write_original_resource()
    workspace.write_run_config(goal="reliability improvements")
    workspace.write_run_state("INIT")
    yield workspace


@pytest.fixture
def mock_optimizer() -> Generator[MagicMock, None, None]:
    """Mock DSPy optimizer for deterministic testing.

    Yields:
        MagicMock configured as optimizer
    """
    mock = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.original_score = 0.65
    mock_result.final_score = 0.82
    mock_result.improvement = 0.17
    mock_result.improvement_percent = 26.15
    mock_result.total_iterations = 5
    mock_result.total_duration_seconds = 10.0
    mock_result.optimized_prompt = "Optimized system prompt"
    mock_result.iterations = []

    mock.optimize = AsyncMock(return_value=mock_result)
    yield mock


@pytest.fixture
def mock_research_agent() -> Generator[MagicMock, None, None]:
    """Mock research agent responses.

    Yields:
        MagicMock configured as research agent
    """
    mock = MagicMock()
    mock.return_value = "Research completed. Findings saved to research/notes/"
    yield mock


@pytest.fixture
def mock_evaluator_agent() -> Generator[MagicMock, None, None]:
    """Mock evaluator agent responses.

    Yields:
        MagicMock configured as evaluator agent
    """
    mock = MagicMock()
    result = "RECOMMENDATION: ACCEPT\n\nOptimization achieved improvement."
    mock.return_value = result
    yield mock


@pytest.fixture
def completed_workspace(cgf_workspace: CGFWorkspace) -> CGFWorkspace:
    """Create workspace with all artifacts for evaluation testing.

    Args:
        cgf_workspace: Base workspace fixture

    Returns:
        CGFWorkspace with all phases completed
    """
    cgf_workspace.write_run_config()
    cgf_workspace.write_eval_criteria()
    cgf_workspace.write_test_suite()
    cgf_workspace.write_original_resource()
    cgf_workspace.write_optimized_resource()
    cgf_workspace.write_review(recommendation="ACCEPT")

    config_path = str(cgf_workspace.workspace_dir / "run_config.yaml")
    criteria_path = str(cgf_workspace.research_dir / "eval_criteria.yaml")
    suite_path = str(cgf_workspace.tests_dir / "test_suite.yaml")

    cgf_workspace.write_run_state(
        "EVALUATE",
        artifacts={
            "run_config": config_path,
            "eval_criteria": criteria_path,
            "test_suite": suite_path,
        },
    )
    return cgf_workspace


# Markers for E2E tests
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for CGF E2E tests."""
    config.addinivalue_line(
        "markers",
        "cgf_e2e: marks tests as CGF end-to-end tests",
    )
    config.addinivalue_line(
        "markers",
        "cgf_agent: marks tests for agent optimization",
    )
    config.addinivalue_line(
        "markers",
        "cgf_skill: marks tests for skill optimization",
    )
    config.addinivalue_line(
        "markers",
        "cgf_command: marks tests for command optimization",
    )
    config.addinivalue_line(
        "markers",
        "cgf_workflow: marks tests for workflow optimization",
    )
