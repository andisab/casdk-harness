# Stage 1: Shared Protocol Layer + Resource Architect — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract implicit plugin contracts into a shared protocol layer, add a resource-architect agent, and insert a DESIGN phase between RESEARCH and GENERATE in the multi-resource pipeline.

**Architecture:** New `protocols/` subpackage under `src/harness/optimization/` containing signal parsing, resource type registry, quality scoring, state extensions, and workspace layout. A new `cgf-resource-architect` agent in the cgf-agents plugin produces `resource-plan.yaml` from SPEC + research findings. The orchestrator is refactored to use the protocol layer and gains a DESIGN phase.

**Tech Stack:** Python 3.12+, dataclasses, structlog, pytest, YAML

**Design doc:** `docs/plans/2026-03-02-cgf-eval-framework-design.md`

---

## Task 1: Signal Protocol Module

**Files:**
- Create: `src/harness/optimization/protocols/__init__.py`
- Create: `src/harness/optimization/protocols/signals.py`
- Test: `tests/unit/test_optimization/test_protocols_signals.py`

**Step 1: Write failing tests for SignalType enum and Signal dataclass**

```python
# tests/unit/test_optimization/test_protocols_signals.py
"""Tests for signal protocol module."""

import pytest

from harness.optimization.protocols.signals import Signal, SignalParser, SignalType


class TestSignalType:
    """Tests for SignalType enum."""

    def test_all_phase_signals_exist(self) -> None:
        """All pipeline phases have corresponding signal types."""
        expected = [
            "RESEARCH_COMPLETE", "DESIGN_COMPLETE", "GENERATE_COMPLETE",
            "EVAL_DESIGN_COMPLETE", "ITERATE_COMPLETE", "EVAL_COMPLETE",
            "VALIDATE_COMPLETE", "VALIDATE_ISSUES",
        ]
        for name in expected:
            assert hasattr(SignalType, name), f"Missing SignalType.{name}"

    def test_signal_type_values_are_strings(self) -> None:
        """Signal type values should be lowercase string identifiers."""
        assert SignalType.RESEARCH_COMPLETE.value == "research_complete"


class TestSignal:
    """Tests for Signal dataclass."""

    def test_signal_creation(self) -> None:
        sig = Signal(
            type=SignalType.GENERATE_COMPLETE,
            resource_path="agents/foo.md",
            metadata={"word_count": 500},
        )
        assert sig.type == SignalType.GENERATE_COMPLETE
        assert sig.resource_path == "agents/foo.md"
        assert sig.metadata["word_count"] == 500

    def test_signal_without_resource_path(self) -> None:
        sig = Signal(type=SignalType.RESEARCH_COMPLETE, metadata={})
        assert sig.resource_path is None


class TestSignalParser:
    """Tests for SignalParser."""

    def test_parse_research_complete(self) -> None:
        response = """Research findings saved.
[RESEARCH_COMPLETE]
eval_criteria_path: research/eval_criteria.yaml"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.RESEARCH_COMPLETE
        assert signals[0].metadata["eval_criteria_path"] == "research/eval_criteria.yaml"

    def test_parse_generate_complete_with_path(self) -> None:
        response = """Created agent file.
[GENERATE_COMPLETE:agents/iac-analyzer.md]
resource_type: agent
word_count: 1200"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.GENERATE_COMPLETE
        assert signals[0].resource_path == "agents/iac-analyzer.md"
        assert signals[0].metadata["resource_type"] == "agent"
        assert signals[0].metadata["word_count"] == "1200"

    def test_parse_iterate_complete_with_quality(self) -> None:
        response = """Optimization done.
[ITERATE_COMPLETE:agents/iac-analyzer.md]
version: 1
quality_overall: 0.87
quality_completeness: 0.85
quality_accuracy: 0.90
quality_clarity: 0.85
word_count: 1400"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].metadata["quality_overall"] == "0.87"
        assert signals[0].metadata["quality_completeness"] == "0.85"

    def test_parse_validate_issues(self) -> None:
        response = """Validation found problems.
[VALIDATE_ISSUES:3]
issue_1: Undefined cross-reference"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.VALIDATE_ISSUES
        assert signals[0].metadata["issue_count"] == 3

    def test_parse_validate_complete(self) -> None:
        response = """All checks passed.
[VALIDATE_COMPLETE]
coherence_score: 0.92"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.VALIDATE_COMPLETE

    def test_parse_no_signals(self) -> None:
        parser = SignalParser()
        signals = parser.parse("Just some text with no signals.")
        assert signals == []

    def test_parse_multiple_signals(self) -> None:
        response = """Created two resources.
[GENERATE_COMPLETE:agents/foo.md]
resource_type: agent
[GENERATE_COMPLETE:skills/bar/SKILL.md]
resource_type: skill"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 2
        assert signals[0].resource_path == "agents/foo.md"
        assert signals[1].resource_path == "skills/bar/SKILL.md"

    def test_parse_design_complete(self) -> None:
        response = """Architecture plan created.
[DESIGN_COMPLETE]
resource_plan_path: resource-plan.yaml
total_resources: 3"""
        parser = SignalParser()
        signals = parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.DESIGN_COMPLETE
        assert signals[0].metadata["resource_plan_path"] == "resource-plan.yaml"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_signals.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement the protocols package and signals module**

```python
# src/harness/optimization/protocols/__init__.py
"""Shared protocol layer for multi-resource optimization.

Formalizes the contracts between plugins (cgf-agents, context-engineering,
research-team) into explicit, versioned schemas and utilities.
"""

from .signals import Signal, SignalParser, SignalType

__all__ = ["Signal", "SignalParser", "SignalType"]
```

```python
# src/harness/optimization/protocols/signals.py
"""Signal protocol for agent-to-orchestrator communication.

Agents emit structured signals that the orchestrator parses to transition
state. This module replaces scattered regex patterns with a unified parser.

Signal format:
    [SIGNAL_TYPE]              — phase-level signal
    [SIGNAL_TYPE:resource_path] — resource-level signal
    key: value                  — metadata lines following the signal
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    """All signal types emitted by pipeline agents."""

    RESEARCH_COMPLETE = "research_complete"
    DESIGN_COMPLETE = "design_complete"
    GENERATE_COMPLETE = "generate_complete"
    EVAL_DESIGN_COMPLETE = "eval_design_complete"
    ITERATE_COMPLETE = "iterate_complete"
    EVAL_COMPLETE = "eval_complete"
    VALIDATE_COMPLETE = "validate_complete"
    VALIDATE_ISSUES = "validate_issues"


# Map from signal tag text to SignalType
_SIGNAL_TAG_MAP: dict[str, SignalType] = {
    "RESEARCH_COMPLETE": SignalType.RESEARCH_COMPLETE,
    "DESIGN_COMPLETE": SignalType.DESIGN_COMPLETE,
    "GENERATE_COMPLETE": SignalType.GENERATE_COMPLETE,
    "EVAL_DESIGN_COMPLETE": SignalType.EVAL_DESIGN_COMPLETE,
    "ITERATE_COMPLETE": SignalType.ITERATE_COMPLETE,
    "EVAL_COMPLETE": SignalType.EVAL_COMPLETE,
    "VALIDATE_COMPLETE": SignalType.VALIDATE_COMPLETE,
    "VALIDATE_ISSUES": SignalType.VALIDATE_ISSUES,
}

# Regex to match signal tags: [TAG] or [TAG:path] or [TAG:number]
_SIGNAL_PATTERN = re.compile(
    r"\[("
    + "|".join(re.escape(tag) for tag in _SIGNAL_TAG_MAP)
    + r")(?::([^\]]+))?\]"
)

# Regex to match metadata lines: key: value (indented or not)
_METADATA_PATTERN = re.compile(r"^\s*(\w+):\s*(.+)$", re.MULTILINE)


@dataclass
class Signal:
    """A parsed signal from an agent response.

    Attributes:
        type: The signal type enum value
        resource_path: Optional resource path (for per-resource signals)
        metadata: Key-value pairs from lines following the signal
    """

    type: SignalType
    resource_path: str | None = None
    metadata: dict[str, str | int] = field(default_factory=dict)


class SignalParser:
    """Unified parser for all agent signals.

    Replaces scattered regex patterns in multi_resource_orchestrator.py.
    Handles permissive parsing with fallbacks for agent output variations.
    """

    def parse(self, response: str) -> list[Signal]:
        """Parse all signals from an agent response.

        Args:
            response: Full text response from an agent

        Returns:
            List of parsed Signal objects in order of appearance
        """
        signals: list[Signal] = []

        # Find all signal tags and their positions
        matches = list(_SIGNAL_PATTERN.finditer(response))
        if not matches:
            return signals

        for i, match in enumerate(matches):
            tag_text = match.group(1)
            path_or_arg = match.group(2)
            signal_type = _SIGNAL_TAG_MAP[tag_text]

            # Determine resource_path vs numeric argument
            resource_path: str | None = None
            metadata: dict[str, str | int] = {}

            if path_or_arg is not None:
                if signal_type == SignalType.VALIDATE_ISSUES:
                    # [VALIDATE_ISSUES:3] — numeric argument
                    try:
                        metadata["issue_count"] = int(path_or_arg)
                    except ValueError:
                        metadata["issue_count"] = path_or_arg
                else:
                    # [GENERATE_COMPLETE:agents/foo.md] — resource path
                    resource_path = path_or_arg.strip()

            # Extract metadata from lines between this signal and the next
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(response)
            metadata_text = response[start:end]

            for meta_match in _METADATA_PATTERN.finditer(metadata_text):
                key = meta_match.group(1)
                value = meta_match.group(2).strip()
                metadata[key] = value

            signals.append(Signal(
                type=signal_type,
                resource_path=resource_path,
                metadata=metadata,
            ))

        return signals
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_signals.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/harness/optimization/protocols/ tests/unit/test_optimization/test_protocols_signals.py
git commit -m "feat(protocols): add signal protocol module with unified parser"
```

---

## Task 2: Resource Types Registry

**Files:**
- Create: `src/harness/optimization/protocols/resource_types.py`
- Modify: `src/harness/optimization/protocols/__init__.py`
- Test: `tests/unit/test_optimization/test_protocols_resource_types.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_optimization/test_protocols_resource_types.py
"""Tests for resource type registry."""

import pytest

from harness.optimization.protocols.resource_types import (
    ResourceType,
    ResourceTypeConfig,
    ResourceTypeRegistry,
)


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_all_types_exist(self) -> None:
        expected = ["AGENT", "SKILL", "COMMAND", "HOOK", "MCP_TOOL", "MCP_SERVER", "PLUGIN"]
        for name in expected:
            assert hasattr(ResourceType, name)

    def test_values_are_lowercase(self) -> None:
        assert ResourceType.AGENT.value == "agent"
        assert ResourceType.MCP_SERVER.value == "mcp_server"


class TestResourceTypeConfig:
    """Tests for ResourceTypeConfig."""

    def test_agent_config(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.AGENT,
            path_pattern="agents/{name}.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="agent-definition-creation",
            eval_strategy="content_and_execution",
            supports_versioning=True,
        )
        assert config.type == ResourceType.AGENT
        assert "{name}" in config.path_pattern

    def test_mcp_tool_config(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.MCP_TOOL,
            path_pattern="tools/{name}.py",
            generator_agent="context-engineering:context-engineer",
            generator_skill="mcp-tool-creation",
            eval_strategy="executable",
            supports_versioning=True,
        )
        assert config.eval_strategy == "executable"

    def test_resolve_path(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.AGENT,
            path_pattern="agents/{name}.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="agent-definition-creation",
            eval_strategy="content_and_execution",
            supports_versioning=True,
        )
        assert config.resolve_path("iac-analyzer") == "agents/iac-analyzer.md"

    def test_resolve_path_skill(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.SKILL,
            path_pattern="skills/{name}/SKILL.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="skill-creation",
            eval_strategy="content_only",
            supports_versioning=True,
        )
        assert config.resolve_path("compliance-rules") == "skills/compliance-rules/SKILL.md"


class TestResourceTypeRegistry:
    """Tests for ResourceTypeRegistry."""

    def test_default_registry_has_all_types(self) -> None:
        registry = ResourceTypeRegistry.default()
        for rt in ResourceType:
            assert registry.get(rt) is not None, f"Missing config for {rt.name}"

    def test_get_by_string(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get_by_string("agent")
        assert config is not None
        assert config.type == ResourceType.AGENT

    def test_get_by_string_unknown(self) -> None:
        registry = ResourceTypeRegistry.default()
        assert registry.get_by_string("unknown_type") is None

    def test_register_custom_type(self) -> None:
        registry = ResourceTypeRegistry.default()
        custom = ResourceTypeConfig(
            type=ResourceType.PLUGIN,
            path_pattern="{name}/",
            generator_agent="context-engineering:context-engineer",
            generator_skill="plugin-development",
            eval_strategy="content_only",
            supports_versioning=False,
        )
        registry.register(custom)
        assert registry.get(ResourceType.PLUGIN) == custom

    def test_resolve_path_from_registry(self) -> None:
        registry = ResourceTypeRegistry.default()
        path = registry.resolve_path(ResourceType.AGENT, "iac-analyzer")
        assert path == "agents/iac-analyzer.md"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_resource_types.py -v`
Expected: FAIL

**Step 3: Implement resource types module**

```python
# src/harness/optimization/protocols/resource_types.py
"""Resource type registry for multi-resource optimization.

Maps resource types to their creation agents, skills, path patterns,
and evaluation strategies. Extensible: new types plug in by adding
a ResourceTypeConfig entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):
    """Supported resource types in the optimization pipeline."""

    AGENT = "agent"
    SKILL = "skill"
    COMMAND = "command"
    HOOK = "hook"
    MCP_TOOL = "mcp_tool"
    MCP_SERVER = "mcp_server"
    PLUGIN = "plugin"


@dataclass(frozen=True)
class ResourceTypeConfig:
    """Configuration for a resource type.

    Attributes:
        type: The resource type enum
        path_pattern: Template with {name} placeholder (e.g., "agents/{name}.md")
        generator_agent: Agent that creates this type (namespaced)
        generator_skill: Skill that guides creation
        eval_strategy: How to evaluate ("content_only", "content_and_execution",
                        "executable", "server")
        supports_versioning: Whether -v{N} versioning applies
    """

    type: ResourceType
    path_pattern: str
    generator_agent: str
    generator_skill: str
    eval_strategy: str
    supports_versioning: bool

    def resolve_path(self, name: str) -> str:
        """Resolve path pattern with a resource name."""
        return self.path_pattern.replace("{name}", name)


class ResourceTypeRegistry:
    """Registry mapping resource types to their configurations.

    Use ResourceTypeRegistry.default() for the standard set.
    Call register() to add custom types.
    """

    def __init__(self) -> None:
        self._configs: dict[ResourceType, ResourceTypeConfig] = {}

    def register(self, config: ResourceTypeConfig) -> None:
        """Register or update a resource type configuration."""
        self._configs[config.type] = config

    def get(self, resource_type: ResourceType) -> ResourceTypeConfig | None:
        """Get configuration for a resource type."""
        return self._configs.get(resource_type)

    def get_by_string(self, type_string: str) -> ResourceTypeConfig | None:
        """Get configuration by string name (e.g., 'agent', 'mcp_tool')."""
        try:
            rt = ResourceType(type_string)
        except ValueError:
            return None
        return self._configs.get(rt)

    def resolve_path(self, resource_type: ResourceType, name: str) -> str:
        """Resolve path for a resource type and name."""
        config = self.get(resource_type)
        if not config:
            raise ValueError(f"No config registered for {resource_type}")
        return config.resolve_path(name)

    @classmethod
    def default(cls) -> ResourceTypeRegistry:
        """Create registry with all default resource type configs."""
        registry = cls()
        ce = "context-engineering:context-engineer"

        defaults = [
            ResourceTypeConfig(
                type=ResourceType.AGENT,
                path_pattern="agents/{name}.md",
                generator_agent=ce,
                generator_skill="agent-definition-creation",
                eval_strategy="content_and_execution",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.SKILL,
                path_pattern="skills/{name}/SKILL.md",
                generator_agent=ce,
                generator_skill="skill-creation",
                eval_strategy="content_only",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.COMMAND,
                path_pattern="commands/{name}.md",
                generator_agent=ce,
                generator_skill="command-creation",
                eval_strategy="content_only",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.HOOK,
                path_pattern="hooks/{name}.json",
                generator_agent=ce,
                generator_skill="hook-configuration",
                eval_strategy="content_only",
                supports_versioning=False,
            ),
            ResourceTypeConfig(
                type=ResourceType.MCP_TOOL,
                path_pattern="tools/{name}.py",
                generator_agent=ce,
                generator_skill="mcp-tool-creation",
                eval_strategy="executable",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.MCP_SERVER,
                path_pattern="mcp-servers/{name}/",
                generator_agent=ce,
                generator_skill="mcp-server-creation",
                eval_strategy="server",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.PLUGIN,
                path_pattern="{name}/",
                generator_agent=ce,
                generator_skill="plugin-development",
                eval_strategy="content_only",
                supports_versioning=False,
            ),
        ]

        for config in defaults:
            registry.register(config)

        return registry
```

**Step 4: Update `__init__.py`**

Add to `src/harness/optimization/protocols/__init__.py`:
```python
from .resource_types import ResourceType, ResourceTypeConfig, ResourceTypeRegistry
```

And update `__all__`.

**Step 5: Run tests to verify they pass**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_resource_types.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/harness/optimization/protocols/resource_types.py \
  src/harness/optimization/protocols/__init__.py \
  tests/unit/test_optimization/test_protocols_resource_types.py
git commit -m "feat(protocols): add resource type registry with MCP support"
```

---

## Task 3: Quality and State Protocol Modules

**Files:**
- Create: `src/harness/optimization/protocols/quality.py`
- Create: `src/harness/optimization/protocols/state.py`
- Create: `src/harness/optimization/protocols/workspace.py`
- Modify: `src/harness/optimization/protocols/__init__.py`
- Test: `tests/unit/test_optimization/test_protocols_quality.py`
- Test: `tests/unit/test_optimization/test_protocols_state.py`

**Step 1: Write failing tests for quality module**

```python
# tests/unit/test_optimization/test_protocols_quality.py
"""Tests for quality protocol module."""

import pytest

from harness.optimization.protocols.quality import (
    CombinedScore,
    ExecutionScore,
    QualityScore,
)


class TestQualityScore:
    def test_auto_calculate_overall(self) -> None:
        qs = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        # 0.35*0.8 + 0.35*0.9 + 0.30*0.7 = 0.28 + 0.315 + 0.21 = 0.805
        assert abs(qs.overall - 0.805) < 0.001

    def test_meets_threshold(self) -> None:
        qs = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        assert qs.meets_threshold(0.85)
        assert not qs.meets_threshold(0.95)

    def test_to_dict_roundtrip(self) -> None:
        qs = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        d = qs.to_dict()
        qs2 = QualityScore.from_dict(d)
        assert abs(qs.overall - qs2.overall) < 0.001

    def test_from_dict_missing_fields_default_zero(self) -> None:
        qs = QualityScore.from_dict({})
        assert qs.completeness == 0.0
        assert qs.overall == 0.0


class TestExecutionScore:
    def test_creation(self) -> None:
        es = ExecutionScore(
            pass_at_1=0.8, pass_at_k=0.93, pass_pow_k=0.67,
            k=3, total_scenarios=15,
            by_level={"unit": 0.83, "trajectory": 0.60, "e2e": 0.50},
            by_capability={"cap_1": 0.75},
        )
        assert es.pass_pow_k == 0.67
        assert es.by_level["unit"] == 0.83

    def test_to_dict_roundtrip(self) -> None:
        es = ExecutionScore(
            pass_at_1=0.8, pass_at_k=0.93, pass_pow_k=0.67,
            k=3, total_scenarios=15,
        )
        d = es.to_dict()
        es2 = ExecutionScore.from_dict(d)
        assert es2.pass_pow_k == 0.67

    def test_no_execution_yet(self) -> None:
        es = ExecutionScore.none()
        assert es.pass_at_1 == 0.0
        assert es.total_scenarios == 0


class TestCombinedScore:
    def test_recommendation_accept(self) -> None:
        cs = CombinedScore(
            quality=QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9),
            execution=ExecutionScore(pass_at_1=0.9, pass_at_k=0.95, pass_pow_k=0.85, k=3, total_scenarios=10),
        )
        assert cs.recommendation == "ACCEPT"

    def test_recommendation_refine_low_execution(self) -> None:
        cs = CombinedScore(
            quality=QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9),
            execution=ExecutionScore(pass_at_1=0.5, pass_at_k=0.7, pass_pow_k=0.3, k=3, total_scenarios=10),
        )
        assert cs.recommendation == "REFINE"

    def test_recommendation_no_execution(self) -> None:
        """Before execution eval, recommendation based on quality only."""
        cs = CombinedScore(
            quality=QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9),
            execution=ExecutionScore.none(),
        )
        assert cs.recommendation == "ACCEPT"  # quality-only judgment
```

**Step 2: Write failing tests for state extensions**

```python
# tests/unit/test_optimization/test_protocols_state.py
"""Tests for state protocol extensions."""

import pytest

from harness.optimization.protocols.state import (
    PHASE_ORDER,
    is_valid_transition,
)
from harness.progress import OptimizationPhase


class TestPhaseOrder:
    def test_design_comes_after_research(self) -> None:
        assert PHASE_ORDER.index("DESIGN") > PHASE_ORDER.index("RESEARCH")

    def test_eval_design_comes_after_generate(self) -> None:
        assert PHASE_ORDER.index("EVAL_DESIGN") > PHASE_ORDER.index("GENERATE")

    def test_execution_eval_comes_after_iterate(self) -> None:
        assert PHASE_ORDER.index("EXECUTION_EVAL") > PHASE_ORDER.index("ITERATE")

    def test_complete_is_last(self) -> None:
        assert PHASE_ORDER[-1] == "COMPLETE"


class TestPhaseTransition:
    def test_valid_forward_transition(self) -> None:
        assert is_valid_transition("RESEARCH", "DESIGN")
        assert is_valid_transition("DESIGN", "GENERATE")

    def test_invalid_skip_transition(self) -> None:
        assert not is_valid_transition("RESEARCH", "GENERATE")

    def test_backward_transition_for_refinement(self) -> None:
        """EXECUTION_EVAL can loop back to ITERATE."""
        assert is_valid_transition("EXECUTION_EVAL", "ITERATE")

    def test_validate_can_loop_to_iterate(self) -> None:
        """VALIDATE can loop back to ITERATE for refinement."""
        assert is_valid_transition("VALIDATE", "ITERATE")
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_quality.py tests/unit/test_optimization/test_protocols_state.py -v`
Expected: FAIL

**Step 4: Implement quality module**

```python
# src/harness/optimization/protocols/quality.py
"""Quality scoring protocol for resource evaluation.

Unifies quality scoring from LLM-judge assessment and execution-based
evaluation into a combined score with recommendation logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

COMPLETENESS_WEIGHT = 0.35
ACCURACY_WEIGHT = 0.35
CLARITY_WEIGHT = 0.30

# Thresholds for recommendation logic
ACCEPT_QUALITY_THRESHOLD = 0.85
ACCEPT_EXECUTION_THRESHOLD = 0.80
REFINE_EXECUTION_THRESHOLD = 0.50


@dataclass
class QualityScore:
    """LLM-judge quality assessment (fast iteration feedback).

    Attributes:
        completeness: Coverage of required capabilities (0.0-1.0)
        accuracy: Correctness of patterns/examples (0.0-1.0)
        clarity: Organization and readability (0.0-1.0)
        overall: Auto-calculated weighted average
    """

    completeness: float = 0.0
    accuracy: float = 0.0
    clarity: float = 0.0
    overall: float = 0.0

    def __post_init__(self) -> None:
        if self.overall == 0.0 and (self.completeness or self.accuracy or self.clarity):
            self.overall = (
                COMPLETENESS_WEIGHT * self.completeness
                + ACCURACY_WEIGHT * self.accuracy
                + CLARITY_WEIGHT * self.clarity
            )

    def meets_threshold(self, threshold: float) -> bool:
        return self.overall >= threshold

    def to_dict(self) -> dict[str, float]:
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "clarity": self.clarity,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityScore:
        return cls(
            completeness=data.get("completeness", 0.0),
            accuracy=data.get("accuracy", 0.0),
            clarity=data.get("clarity", 0.0),
            overall=data.get("overall", 0.0),
        )


@dataclass
class ExecutionScore:
    """Execution-based evaluation results (sandboxed agent sessions).

    Attributes:
        pass_at_1: Fraction of scenarios passing on first trial
        pass_at_k: Fraction passing at least once in k trials
        pass_pow_k: Fraction passing ALL k trials (production metric)
        k: Number of trials per scenario
        total_scenarios: Total number of eval scenarios
        by_level: Breakdown by eval level (unit, trajectory, e2e)
        by_capability: Breakdown by SPEC capability
    """

    pass_at_1: float = 0.0
    pass_at_k: float = 0.0
    pass_pow_k: float = 0.0
    k: int = 3
    total_scenarios: int = 0
    by_level: dict[str, float] = field(default_factory=dict)
    by_capability: dict[str, float] = field(default_factory=dict)

    @classmethod
    def none(cls) -> ExecutionScore:
        """Sentinel for 'no execution eval has run yet'."""
        return cls()

    @property
    def has_results(self) -> bool:
        return self.total_scenarios > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_at_1": self.pass_at_1,
            "pass_at_k": self.pass_at_k,
            "pass_pow_k": self.pass_pow_k,
            "k": self.k,
            "total_scenarios": self.total_scenarios,
            "by_level": self.by_level,
            "by_capability": self.by_capability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionScore:
        return cls(
            pass_at_1=data.get("pass_at_1", 0.0),
            pass_at_k=data.get("pass_at_k", 0.0),
            pass_pow_k=data.get("pass_pow_k", 0.0),
            k=data.get("k", 3),
            total_scenarios=data.get("total_scenarios", 0),
            by_level=data.get("by_level", {}),
            by_capability=data.get("by_capability", {}),
        )


@dataclass
class CombinedScore:
    """Combined quality + execution score with recommendation.

    Recommendation logic:
    - ACCEPT: quality >= threshold AND (no execution OR execution pass^k >= threshold)
    - REFINE: quality meets threshold but execution is below
    - REJECT: quality below threshold
    """

    quality: QualityScore
    execution: ExecutionScore

    @property
    def recommendation(self) -> str:
        quality_ok = self.quality.meets_threshold(ACCEPT_QUALITY_THRESHOLD)

        if not self.execution.has_results:
            # No execution eval yet — judge on quality alone
            return "ACCEPT" if quality_ok else "REFINE"

        execution_ok = self.execution.pass_pow_k >= ACCEPT_EXECUTION_THRESHOLD

        if quality_ok and execution_ok:
            return "ACCEPT"
        elif quality_ok or self.execution.pass_pow_k >= REFINE_EXECUTION_THRESHOLD:
            return "REFINE"
        else:
            return "REJECT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality.to_dict(),
            "execution": self.execution.to_dict(),
            "recommendation": self.recommendation,
        }
```

**Step 5: Implement state module**

```python
# src/harness/optimization/protocols/state.py
"""State protocol extensions for the revised pipeline.

Defines the extended phase order (with DESIGN, EVAL_DESIGN, EXECUTION_EVAL)
and valid phase transitions including refinement loops.
"""

from __future__ import annotations

# Canonical phase order for the revised pipeline
PHASE_ORDER: list[str] = [
    "RESEARCH",
    "DESIGN",
    "QA",
    "GENERATE",
    "EVAL_DESIGN",
    "ITERATE",
    "EXECUTION_EVAL",
    "VALIDATE",
    "COMPLETE",
]

# Valid backward transitions (refinement loops)
_BACKWARD_TRANSITIONS: set[tuple[str, str]] = {
    ("EXECUTION_EVAL", "ITERATE"),  # Execution failures trigger re-optimization
    ("VALIDATE", "ITERATE"),        # Coherence issues trigger re-optimization
}


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    """Check whether a phase transition is valid.

    Valid transitions:
    - Forward by exactly one step in PHASE_ORDER
    - Specific backward transitions for refinement loops

    Args:
        from_phase: Current phase name
        to_phase: Target phase name

    Returns:
        True if the transition is valid
    """
    if (from_phase, to_phase) in _BACKWARD_TRANSITIONS:
        return True

    try:
        from_idx = PHASE_ORDER.index(from_phase)
        to_idx = PHASE_ORDER.index(to_phase)
    except ValueError:
        return False

    return to_idx == from_idx + 1
```

**Step 6: Implement workspace module**

```python
# src/harness/optimization/protocols/workspace.py
"""Workspace layout protocol.

Defines the canonical directory structure for optimization workspaces.
All components agree on where files go.
"""

from __future__ import annotations

from pathlib import Path


class WorkspaceLayout:
    """Canonical paths within an optimization workspace.

    Usage:
        layout = WorkspaceLayout(Path("workspace/iac-team"))
        layout.research_notes  # -> workspace/iac-team/research/notes
        layout.eval_suite      # -> workspace/iac-team/eval/eval-suite.yaml
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    # Top-level files
    @property
    def spec(self) -> Path:
        return self.root / "SPEC.md"

    @property
    def resource_plan(self) -> Path:
        return self.root / "resource-plan.yaml"

    @property
    def changelog(self) -> Path:
        return self.root / "CHANGELOG.md"

    # Resource directories
    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def commands_dir(self) -> Path:
        return self.root / "commands"

    @property
    def tools_dir(self) -> Path:
        return self.root / "tools"

    @property
    def mcp_servers_dir(self) -> Path:
        return self.root / "mcp-servers"

    # Research directory
    @property
    def research_dir(self) -> Path:
        return self.root / "research"

    @property
    def research_notes(self) -> Path:
        return self.root / "research" / "notes"

    @property
    def eval_criteria(self) -> Path:
        return self.root / "research" / "eval_criteria.yaml"

    @property
    def reviews_dir(self) -> Path:
        return self.root / "research" / "reviews"

    # Eval directory
    @property
    def eval_dir(self) -> Path:
        return self.root / "eval"

    @property
    def eval_suite(self) -> Path:
        return self.root / "eval" / "eval-suite.yaml"

    @property
    def eval_results(self) -> Path:
        return self.root / "eval" / "eval-results.json"

    @property
    def eval_transcripts(self) -> Path:
        return self.root / "eval" / "transcripts"

    # Session directory
    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def optimization_state(self) -> Path:
        return self.root / "sessions" / "optimization-state.json"

    def ensure_dirs(self) -> None:
        """Create all standard directories."""
        for d in [
            self.agents_dir, self.skills_dir, self.commands_dir,
            self.tools_dir, self.mcp_servers_dir,
            self.research_notes, self.reviews_dir,
            self.eval_dir, self.eval_transcripts,
            self.sessions_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
```

**Step 7: Update `__init__.py` with all exports**

**Step 8: Run all protocol tests**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_protocols_*.py -v`
Expected: All PASS

**Step 9: Commit**

```bash
git add src/harness/optimization/protocols/ tests/unit/test_optimization/test_protocols_*.py
git commit -m "feat(protocols): add quality, state, and workspace modules"
```

---

## Task 4: Extend OptimizationPhase Enum and MultiResourceState

**Files:**
- Modify: `src/harness/progress.py:575-587` (OptimizationPhase enum)
- Modify: `src/harness/progress.py:693-873` (MultiResourceState)
- Modify: `tests/unit/test_multi_resource_orchestrator.py` (update existing tests)
- Test: `tests/unit/test_optimization/test_protocols_state.py` (already created in Task 3)

**Step 1: Add new phases to OptimizationPhase enum**

Modify `src/harness/progress.py:575-587` to add:
```python
class OptimizationPhase(Enum):
    RESEARCH = auto()
    DESIGN = auto()        # NEW — resource architecture decision
    QA = auto()
    GENERATE = auto()
    EVAL_DESIGN = auto()   # NEW — eval suite generation
    ITERATE = auto()
    EXECUTION_EVAL = auto() # NEW — sandboxed execution evaluation
    VALIDATE = auto()
    COMPLETE = auto()
```

**Step 2: Add new fields to MultiResourceState**

Add to the MultiResourceState dataclass (after existing fields):
```python
resource_plan_path: str = ""      # Path to resource-plan.yaml from DESIGN phase
eval_suite_path: str = ""         # Path to eval-suite.yaml from EVAL_DESIGN phase
eval_results_path: str = ""       # Path to eval-results.json from EXECUTION_EVAL phase
feedback_history: list[dict[str, Any]] = field(default_factory=list)  # Execution feedback passed to optimizer
```

Update `to_dict()` and `from_dict()` to include these fields.

**Step 3: Run existing tests to check for breakage**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_multi_resource_orchestrator.py -v`
Expected: Tests should still PASS (new enum values don't break existing ones). If any tests hardcode phase sequences, update them.

**Step 4: Run all tests**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/ -v --timeout=30`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/harness/progress.py tests/
git commit -m "feat(progress): add DESIGN, EVAL_DESIGN, EXECUTION_EVAL phases to pipeline"
```

---

## Task 5: Extend SPEC Parser for MCP Resource Types

**Files:**
- Modify: `src/harness/optimization/multi_resource_spec.py:60-104` (add ProposedMCPTool, ProposedMCPServer)
- Modify: `src/harness/optimization/multi_resource_spec.py:156-275` (add to MultiResourceSpec)
- Modify: `src/harness/optimization/multi_resource_spec.py:495-630` (add parsing functions)
- Test: `tests/unit/test_optimization/test_spec_mcp_parsing.py`

**Step 1: Write failing tests for MCP spec parsing**

```python
# tests/unit/test_optimization/test_spec_mcp_parsing.py
"""Tests for MCP resource type parsing in SPEC.md."""

from pathlib import Path
from textwrap import dedent

import pytest

from harness.optimization.multi_resource_spec import (
    MultiResourceSpec,
    ProposedMCPServer,
    ProposedMCPTool,
    parse_multi_resource_spec,
)


class TestProposedMCPTool:
    def test_creation(self) -> None:
        tool = ProposedMCPTool(name="terraform-parser", purpose="Parse HCL files")
        assert tool.name == "terraform-parser"
        assert tool.language == "python"  # default

    def test_to_dict(self) -> None:
        tool = ProposedMCPTool(name="tf-parser", purpose="Parse HCL", language="python")
        d = tool.to_dict()
        assert d["name"] == "tf-parser"
        assert d["language"] == "python"


class TestProposedMCPServer:
    def test_creation(self) -> None:
        server = ProposedMCPServer(
            name="compliance-api",
            purpose="Integration with compliance policy database",
            language="python",
            tools=["check_policy", "list_violations"],
        )
        assert server.name == "compliance-api"
        assert len(server.tools) == 2


class TestSpecMCPParsing:
    def test_parse_mcp_tools_section(self, tmp_path: Path) -> None:
        spec_content = dedent("""\
            # IaC Compliance Team

            ## Purpose
            Infrastructure compliance analysis

            ## Capabilities
            - **Terraform Analysis**: Parse and validate Terraform files

            ## Proposed Structure

            ### MCP Tools
            - **terraform-parser** - Parse and validate HCL files

            ### Agents
            - **iac-analyzer** - Analyze IaC for compliance
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_mcp_tools) == 1
        assert spec.proposed_mcp_tools[0].name == "terraform-parser"

    def test_parse_mcp_servers_section(self, tmp_path: Path) -> None:
        spec_content = dedent("""\
            # IaC Compliance Team

            ## Purpose
            Infrastructure compliance analysis

            ## Capabilities
            - **Policy Lookup**: Query compliance policy database

            ## Proposed Structure

            ### MCP Servers
            - **compliance-api** - Integration with compliance policy database
              - language: python
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_mcp_servers) == 1
        assert spec.proposed_mcp_servers[0].name == "compliance-api"

    def test_total_proposed_includes_mcp(self, tmp_path: Path) -> None:
        spec_content = dedent("""\
            # Test

            ## Purpose
            Test plugin

            ## Capabilities
            - **Cap 1**: Description

            ## Proposed Structure

            ### Agents
            - **agent-1** - Purpose

            ### MCP Tools
            - **tool-1** - Purpose

            ### MCP Servers
            - **server-1** - Purpose
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert spec.total_proposed_resources == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_spec_mcp_parsing.py -v`
Expected: FAIL (ImportError for ProposedMCPTool)

**Step 3: Implement MCP dataclasses and parsing**

Add to `multi_resource_spec.py` after existing ProposedCommand (line ~104):

```python
@dataclass
class ProposedMCPTool:
    """A proposed MCP tool from SPEC.md."""
    name: str
    purpose: str
    language: str = "python"

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "purpose": self.purpose, "language": self.language}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ProposedMCPTool:
        return cls(name=data["name"], purpose=data["purpose"], language=data.get("language", "python"))


@dataclass
class ProposedMCPServer:
    """A proposed MCP server from SPEC.md."""
    name: str
    purpose: str
    language: str = "python"
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "purpose": self.purpose, "language": self.language, "tools": self.tools}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposedMCPServer:
        return cls(
            name=data["name"], purpose=data["purpose"],
            language=data.get("language", "python"), tools=data.get("tools", []),
        )
```

Add `proposed_mcp_tools` and `proposed_mcp_servers` fields to MultiResourceSpec.
Add `_parse_proposed_mcp_tools()` and `_parse_proposed_mcp_servers()` functions.
Update `total_proposed_resources` property to include MCP counts.
Call the new parse functions from `parse_multi_resource_spec()`.

**Step 4: Run tests**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_spec_mcp_parsing.py -v`
Expected: All PASS

**Step 5: Run full test suite to check for breakage**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/ -v --timeout=30`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/harness/optimization/multi_resource_spec.py tests/unit/test_optimization/test_spec_mcp_parsing.py
git commit -m "feat(spec): add MCP tool and server parsing to SPEC.md"
```

---

## Task 6: Resource Architect Agent Definition

**Files:**
- Create: `src/harness/plugins/cgf-agents/agents/cgf-resource-architect.md`
- Create: `src/harness/plugins/cgf-agents/schemas/resource_plan.schema.json`
- Modify: `src/harness/plugins/cgf-agents/.claude-plugin/plugin.json` (update agent count if needed)

**Step 1: Create the resource plan schema**

Create `src/harness/plugins/cgf-agents/schemas/resource_plan.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Resource Plan",
  "description": "Output from cgf-resource-architect: what resources to build, why, and in what order",
  "type": "object",
  "required": ["plan_version", "rationale", "resources", "generation_order"],
  "properties": {
    "plan_version": { "type": "integer", "minimum": 1 },
    "spec_hash": { "type": "string" },
    "rationale": { "type": "string", "minLength": 10 },
    "resources": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "type", "purpose", "capabilities_served", "priority"],
        "properties": {
          "path": { "type": "string" },
          "type": { "type": "string", "enum": ["agent", "skill", "command", "hook", "mcp_tool", "mcp_server"] },
          "purpose": { "type": "string" },
          "capabilities_served": { "type": "array", "items": { "type": "string" } },
          "depends_on": { "type": "array", "items": { "type": "string" }, "default": [] },
          "model": { "type": "string" },
          "tools": { "type": "array", "items": { "type": "string" } },
          "language": { "type": "string", "enum": ["python", "typescript"] },
          "triggers": { "type": "array", "items": { "type": "string" } },
          "priority": { "type": "integer", "minimum": 0 }
        }
      }
    },
    "generation_order": {
      "type": "array",
      "items": { "type": "string" }
    },
    "rejected_proposals": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "original": { "type": "string" },
          "reason": { "type": "string" }
        }
      },
      "default": []
    }
  }
}
```

**Step 2: Create the resource-architect agent definition**

Create `src/harness/plugins/cgf-agents/agents/cgf-resource-architect.md` with YAML frontmatter and system prompt. The agent:
- Model: opus (highest-stakes design decision)
- Tools: Read, Write, Glob, Grep
- Max turns: 50
- Reads SPEC.md, research findings, and resource-type-guide.md
- Applies decision matrix to map capabilities → resource types
- Respects dependency ordering (tools before agents that use them)
- Validates or overrides user-proposed structure with justification
- Outputs resource-plan.yaml following the schema
- Emits `[DESIGN_COMPLETE]` signal

The agent prompt should reference:
- The resource-type-guide.md from context-engineering templates
- The resource_plan.schema.json for output format
- Decision heuristics from the design doc (Section: Component 1)

**Step 3: Verify agent loads correctly**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run python -m harness.direct_agent --info cgf-agents:cgf-resource-architect`
Expected: Shows agent metadata (name, model, tools, description)

**Step 4: Commit**

```bash
git add src/harness/plugins/cgf-agents/agents/cgf-resource-architect.md \
  src/harness/plugins/cgf-agents/schemas/resource_plan.schema.json
git commit -m "feat(cgf): add resource-architect agent and plan schema"
```

---

## Task 7: Add DESIGN Phase to Orchestrator

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py:115-120` (add AGENT_DESIGN constant)
- Modify: `src/harness/optimization/multi_resource_orchestrator.py:330-358` (_create_initial_state — defer resource creation)
- Modify: `src/harness/optimization/multi_resource_orchestrator.py:360-399` (_run_pipeline — add DESIGN phase)
- Create: New method `_delegate_design()` in orchestrator
- Create: New method `_load_resource_plan()` to parse resource-plan.yaml into state
- Test: `tests/unit/test_optimization/test_orchestrator_design_phase.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_optimization/test_orchestrator_design_phase.py
"""Tests for the DESIGN phase in the multi-resource orchestrator."""

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.multi_resource_orchestrator import (
    AGENT_DESIGN,
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.optimization.protocols.signals import SignalType
from harness.progress import MultiResourceState, OptimizationPhase


class TestDesignPhaseConstants:
    def test_agent_design_constant_exists(self) -> None:
        assert AGENT_DESIGN == "cgf-agents:cgf-resource-architect"


class TestCreateInitialState:
    """State should start at RESEARCH with NO pre-populated resources."""

    def test_initial_state_starts_at_research(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        # Mock spec
        orchestrator._spec = MagicMock()
        orchestrator._spec.source_path = tmp_path / "SPEC.md"
        orchestrator._spec.spec_type.name = "PLUGIN"
        orchestrator._spec.content_hash = "abc123"
        orchestrator._spec.proposed_agents = []
        orchestrator._spec.proposed_skills = []
        orchestrator._spec.proposed_commands = []

        state = orchestrator._create_initial_state()
        assert state.current_phase == OptimizationPhase.RESEARCH
        # Resources should NOT be pre-populated (architect decides later)
        assert len(state.resources) == 0


class TestLoadResourcePlan:
    """Verify resource-plan.yaml parsing populates state."""

    def test_load_plan_adds_resources(self, tmp_path: Path) -> None:
        plan_content = dedent("""\
            plan_version: 1
            spec_hash: abc123
            rationale: "Two agents and one MCP tool"
            resources:
              - path: agents/iac-analyzer.md
                type: agent
                purpose: "Analyze IaC"
                capabilities_served: [cap_1]
                depends_on: [tools/terraform-parser.py]
                priority: 1
              - path: tools/terraform-parser.py
                type: mcp_tool
                purpose: "Parse HCL"
                capabilities_served: [cap_1]
                depends_on: []
                priority: 0
            generation_order:
              - tools/terraform-parser.py
              - agents/iac-analyzer.md
            rejected_proposals: []
        """)
        plan_file = tmp_path / "resource-plan.yaml"
        plan_file.write_text(plan_content)

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._state = MultiResourceState(
            spec_path="SPEC.md", spec_type="PLUGIN",
            spec_hash="abc123", current_phase=OptimizationPhase.DESIGN,
        )

        orchestrator._load_resource_plan(plan_file)

        assert len(orchestrator._state.resources) == 2
        assert "agents/iac-analyzer.md" in orchestrator._state.resources
        assert "tools/terraform-parser.py" in orchestrator._state.resources
        agent = orchestrator._state.resources["agents/iac-analyzer.md"]
        assert agent.resource_type == "agent"
        assert agent.depends_on == ["tools/terraform-parser.py"]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_orchestrator_design_phase.py -v`
Expected: FAIL

**Step 3: Implement changes to orchestrator**

1. Add `AGENT_DESIGN = "cgf-agents:cgf-resource-architect"` at line ~120
2. Modify `_create_initial_state()` (line 330): Remove the for-loops that pre-populate resources from proposed structure. State starts empty; resources are added after DESIGN phase.
3. Add `_delegate_design()` method: builds prompt with SPEC + research findings + resource-type-guide reference, calls `call_agent_simple(AGENT_DESIGN, ...)`, parses `[DESIGN_COMPLETE]` signal, loads resource-plan.yaml.
4. Add `_load_resource_plan()` method: reads YAML, adds resources to state with types and dependencies.
5. Update `_run_pipeline()` (line 360): insert DESIGN phase between RESEARCH and QA:

```python
elif phase == OptimizationPhase.DESIGN:
    await self._delegate_design()
    self._advance_phase(OptimizationPhase.QA)
```

Update RESEARCH → DESIGN transition:
```python
if phase == OptimizationPhase.RESEARCH:
    ...
    self._advance_phase(OptimizationPhase.DESIGN)  # was QA
```

**Step 4: Run tests**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/test_optimization/test_orchestrator_design_phase.py tests/unit/test_multi_resource_orchestrator.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/ -v --timeout=30`
Expected: All PASS (may need to update tests that hardcode phase sequences)

**Step 6: Commit**

```bash
git add src/harness/optimization/multi_resource_orchestrator.py \
  tests/unit/test_optimization/test_orchestrator_design_phase.py \
  tests/unit/test_multi_resource_orchestrator.py
git commit -m "feat(orchestrator): add DESIGN phase with resource-architect delegation"
```

---

## Task 8: Refactor Signal Parsing to Use Protocol Layer

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py` (replace regex with SignalParser)
- Test: Run existing tests to verify no regressions

**Step 1: Add SignalParser to orchestrator imports**

At top of `multi_resource_orchestrator.py`, add:
```python
from .protocols.signals import Signal, SignalParser, SignalType
```

**Step 2: Add `self._signal_parser = SignalParser()` in `__init__`**

**Step 3: Replace regex in `_delegate_research()` (line 663)**

Before:
```python
if "[RESEARCH_COMPLETE]" in response:
    ...
    match = re.search(r"eval_criteria_path:\s*(.+)", response)
```

After:
```python
signals = self._signal_parser.parse(response)
research_signals = [s for s in signals if s.type == SignalType.RESEARCH_COMPLETE]
if research_signals:
    signal = research_signals[0]
    ...
    eval_path = signal.metadata.get("eval_criteria_path", "")
```

**Step 4: Replace regex in other delegation methods similarly**

Apply the same pattern to:
- `_delegate_generation()` — replace `[GENERATE_COMPLETE:...]` parsing
- `_delegate_iteration()` — replace `[ITERATE_COMPLETE:...]` + quality parsing
- `_delegate_validation()` — replace `[VALIDATE_COMPLETE]` / `[VALIDATE_ISSUES:N]` parsing

**Step 5: Run full test suite**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/unit/ -v --timeout=30`
Expected: All PASS — behavior identical, just cleaner code

**Step 6: Commit**

```bash
git add src/harness/optimization/multi_resource_orchestrator.py
git commit -m "refactor(orchestrator): replace ad-hoc regex with SignalParser protocol"
```

---

## Task 9: Integration Test — Full DESIGN Phase Round-Trip

**Files:**
- Create: `tests/integration/test_design_phase_integration.py`

**Step 1: Write integration test**

This test verifies the full DESIGN phase round-trip with a mock agent response:

```python
# tests/integration/test_design_phase_integration.py
"""Integration test for DESIGN phase in multi-resource pipeline.

Tests the full flow: SPEC.md → research (mocked) → resource-architect (mocked) →
resource-plan.yaml → state populated with resources.
"""

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, patch

import pytest

from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import OptimizationPhase


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with SPEC.md and mock research findings."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # SPEC.md
    (ws / "SPEC.md").write_text(dedent("""\
        # IaC Compliance Team

        ## Purpose
        Infrastructure compliance analysis

        ## Capabilities
        - **Terraform Analysis**: Parse and validate Terraform files
        - **Policy Checking**: Check against compliance policies

        ## Constraints
        - Must support Terraform and CloudFormation
    """))

    # Mock research findings
    research_dir = ws / "research" / "notes"
    research_dir.mkdir(parents=True)
    (research_dir / "terraform_findings.yaml").write_text("findings: [test]")
    (ws / "research" / "eval_criteria.yaml").write_text("criteria: [test]")

    return ws


@pytest.mark.asyncio
async def test_design_phase_populates_state(workspace: Path) -> None:
    """DESIGN phase should parse resource-plan.yaml and populate state."""
    config = MultiResourceConfig(workspace_dir=workspace, skip_research=True, skip_qa=True)

    # Mock the resource-architect agent response
    plan_yaml = dedent("""\
        plan_version: 1
        spec_hash: test
        rationale: "Two resources needed"
        resources:
          - path: agents/iac-analyzer.md
            type: agent
            purpose: "Analyze IaC"
            capabilities_served: [terraform_analysis]
            depends_on: []
            priority: 0
          - path: skills/compliance-rules/SKILL.md
            type: skill
            purpose: "Compliance rules"
            capabilities_served: [policy_checking]
            depends_on: []
            priority: 0
        generation_order:
          - skills/compliance-rules/SKILL.md
          - agents/iac-analyzer.md
        rejected_proposals: []
    """)

    # Write the plan file (simulating what agent would create)
    (workspace / "resource-plan.yaml").write_text(plan_yaml)

    mock_response = f"""Analyzed SPEC and research findings.
[DESIGN_COMPLETE]
resource_plan_path: resource-plan.yaml
total_resources: 2"""

    with patch("harness.direct_agent.call_agent_simple", new_callable=AsyncMock, return_value=mock_response):
        orchestrator = MultiResourceOrchestrator(config)
        # Run just through DESIGN phase
        await orchestrator._load_spec()
        orchestrator._state = orchestrator._create_initial_state()

        # Advance past RESEARCH (skipped) to DESIGN
        orchestrator._state.current_phase = OptimizationPhase.DESIGN
        await orchestrator._delegate_design()

        assert len(orchestrator._state.resources) == 2
        assert "agents/iac-analyzer.md" in orchestrator._state.resources
        assert orchestrator._state.resource_plan_path == "resource-plan.yaml"
```

**Step 2: Run integration test**

Run: `cd /Users/andisblukis/Projects/ab-github/ab-casdk-harness && uv run pytest tests/integration/test_design_phase_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_design_phase_integration.py
git commit -m "test(integration): add DESIGN phase round-trip integration test"
```

---

## Task 10: Update Documentation

**Files:**
- Modify: `CLAUDE.md` — Update pipeline diagram, phase list, agent count, resource type list
- Modify: `src/harness/plugins/cgf-agents/.claude-plugin/plugin.json` — Update agent count if needed

**Step 1: Update CLAUDE.md**

Key sections to update:
- Pipeline diagram: add DESIGN, EVAL_DESIGN, EXECUTION_EVAL phases
- Agent count: 14 harness + 13 plugin (was 12)
- Phase-to-Agent Mapping table: add DESIGN → cgf-resource-architect
- Resource types: add MCP_TOOL, MCP_SERVER to supported types
- State Machine diagram: add new phases
- Workspace Structure: add tools/, mcp-servers/, eval/, resource-plan.yaml

**Step 2: Verify CLAUDE.md accuracy**

Cross-reference all counts and paths against actual codebase.

**Step 3: Commit**

```bash
git add CLAUDE.md src/harness/plugins/cgf-agents/.claude-plugin/plugin.json
git commit -m "docs: update CLAUDE.md for Stage 1 protocol layer and resource architect"
```

---

## Summary

| Task | Component | New Files | Modified Files |
|------|-----------|-----------|----------------|
| 1 | Signal Protocol | 2 (module + test) | 0 |
| 2 | Resource Types | 2 (module + test) | 1 (__init__) |
| 3 | Quality + State + Workspace | 3 (modules) + 2 (tests) | 1 (__init__) |
| 4 | Phase Enum Extension | 0 | 2 (progress.py + existing tests) |
| 5 | SPEC MCP Parsing | 1 (test) | 1 (multi_resource_spec.py) |
| 6 | Resource Architect Agent | 2 (agent + schema) | 1 (plugin.json) |
| 7 | DESIGN Phase in Orchestrator | 1 (test) | 2 (orchestrator + existing tests) |
| 8 | Signal Parsing Refactor | 0 | 1 (orchestrator) |
| 9 | Integration Test | 1 (test) | 0 |
| 10 | Documentation | 0 | 2 (CLAUDE.md + plugin.json) |
| **Total** | | **14 new** | **11 modified** |

Each task produces a working, testable increment. Run `uv run pytest tests/ -v --timeout=30` after each task to catch regressions.
