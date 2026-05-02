"""Agentic quality evaluation for multi-resource optimization.

Provides LLM-based quality assessment measuring completeness, accuracy, and clarity
without requiring a test suite. Used for quality-based iteration in multi-resource
generation.

Example usage:
    from harness.optimization.quality_evaluator import (
        QualityEvaluator,
        QualityScore,
        evaluate_resource_quality,
    )

    # Evaluate a single resource
    evaluator = QualityEvaluator()
    score = await evaluator.evaluate(
        resource_content=agent_content,
        resource_type="agent",
        spec=multi_resource_spec,
        research_findings=findings,
    )

    print(f"Overall: {score.overall:.2f}")
    print(f"Completeness: {score.completeness:.2f}")
    print(f"Accuracy: {score.accuracy:.2f}")
    print(f"Clarity: {score.clarity:.2f}")

    if score.overall >= 0.85:
        print("Resource meets quality threshold!")
    else:
        print(f"Improvements needed: {score.improvement_suggestions}")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import anthropic
import structlog

if TYPE_CHECKING:
    from harness.optimization.multi_resource_spec import (
        Capability,
        MultiResourceSpec,
    )

logger = structlog.get_logger(__name__)

# Default quality threshold
DEFAULT_QUALITY_THRESHOLD = 0.85

# Quality dimension weights
COMPLETENESS_WEIGHT = 0.35
ACCURACY_WEIGHT = 0.35
CLARITY_WEIGHT = 0.30


@dataclass
class QualityScore:
    """Quality score for a resource.

    Attributes:
        completeness: Coverage of required capabilities (0.0-1.0)
        accuracy: Correctness of patterns/examples (0.0-1.0)
        clarity: Organization and readability (0.0-1.0)
        overall: Weighted average score
        improvement_suggestions: Specific improvements to make
        missing_capabilities: Capabilities not addressed
        accuracy_issues: Specific accuracy problems found
        clarity_issues: Specific clarity problems found
        raw_evaluation: Full evaluation response for debugging
    """

    completeness: float
    accuracy: float
    clarity: float
    overall: float = 0.0
    improvement_suggestions: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    accuracy_issues: list[str] = field(default_factory=list)
    clarity_issues: list[str] = field(default_factory=list)
    raw_evaluation: str = ""

    def __post_init__(self) -> None:
        """Calculate overall score if not provided."""
        if self.overall == 0.0:
            self.overall = (
                self.completeness * COMPLETENESS_WEIGHT
                + self.accuracy * ACCURACY_WEIGHT
                + self.clarity * CLARITY_WEIGHT
            )

    @property
    def meets_threshold(self) -> bool:
        """Check if score meets default threshold."""
        return self.overall >= DEFAULT_QUALITY_THRESHOLD

    def meets_custom_threshold(self, threshold: float) -> bool:
        """Check if score meets a custom threshold."""
        return self.overall >= threshold

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "clarity": self.clarity,
            "overall": self.overall,
            "improvement_suggestions": self.improvement_suggestions,
            "missing_capabilities": self.missing_capabilities,
            "accuracy_issues": self.accuracy_issues,
            "clarity_issues": self.clarity_issues,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityScore:
        """Deserialize from dictionary."""
        return cls(
            completeness=data.get("completeness", 0.0),
            accuracy=data.get("accuracy", 0.0),
            clarity=data.get("clarity", 0.0),
            overall=data.get("overall", 0.0),
            improvement_suggestions=data.get("improvement_suggestions", []),
            missing_capabilities=data.get("missing_capabilities", []),
            accuracy_issues=data.get("accuracy_issues", []),
            clarity_issues=data.get("clarity_issues", []),
        )


def _build_completeness_criteria(
    resource_type: str,
    spec: MultiResourceSpec,
    resource_name: str | None = None,  # noqa: ARG001
) -> str:
    """Build completeness evaluation criteria based on spec.

    Args:
        resource_type: Type of resource (agent, skill, command)
        spec: The multi-resource spec
        resource_name: Optional specific resource name (reserved for future use)

    Returns:
        Criteria string for completeness evaluation
    """
    criteria_parts = []

    # Add resource-type specific requirements
    if resource_type == "agent":
        criteria_parts.extend(
            [
                "Has clear role definition and domain expertise",
                "Includes discovery-optimized description with examples",
                "Specifies appropriate tools with least-privilege access",
                "Defines constraints and boundaries",
                "Contains working code examples",
            ]
        )
    elif resource_type == "skill":
        criteria_parts.extend(
            [
                "Has specific trigger terms in description",
                "Defines clear 'Use for' and 'Do NOT use for' boundaries",
                "Contains reusable patterns or templates",
                "Uses progressive disclosure structure",
                "Includes practical examples",
            ]
        )
    elif resource_type == "command":
        criteria_parts.extend(
            [
                "Documents all arguments clearly",
                "Provides default values for optional args",
                "Includes usage examples",
                "Specifies allowed tools appropriately",
                "Has error handling guidance",
            ]
        )

    # Add spec-specific capabilities
    for capability in spec.capabilities:
        for subcap in capability.subcapabilities[:3]:  # Top 3 per capability
            criteria_parts.append(f"Addresses: {subcap}")

    # Add constraint coverage
    for constraint in spec.constraints[:3]:
        criteria_parts.append(f"Respects constraint: {constraint}")

    return "\n".join(f"- {c}" for c in criteria_parts)


def _build_accuracy_criteria(
    resource_type: str,
    research_findings: dict[str, Any] | None = None,
) -> str:
    """Build accuracy evaluation criteria.

    Args:
        resource_type: Type of resource
        research_findings: Optional research findings to check against

    Returns:
        Criteria string for accuracy evaluation
    """
    criteria_parts = [
        "Code examples are syntactically valid",
        "Patterns follow current best practices",
        "Tool configurations are correct",
        "Technical claims are accurate",
        "Examples produce expected outputs",
    ]

    if resource_type == "agent":
        criteria_parts.extend(
            [
                "Model selection is appropriate for the task",
                "Tool access matches described capabilities",
            ]
        )
    elif resource_type == "skill":
        criteria_parts.extend(
            [
                "Trigger terms are specific and accurate",
                "Pattern descriptions match implementation",
            ]
        )
    elif resource_type == "command":
        criteria_parts.extend(
            [
                "Argument syntax is correct",
                "Bash commands are properly escaped",
            ]
        )

    if research_findings:
        # Add checks against research findings
        if "best_practices" in research_findings:
            criteria_parts.append("Aligns with researched best practices")
        if "patterns" in research_findings:
            criteria_parts.append("Uses researched patterns correctly")

    return "\n".join(f"- {c}" for c in criteria_parts)


def _build_clarity_criteria(resource_type: str) -> str:
    """Build clarity evaluation criteria.

    Args:
        resource_type: Type of resource

    Returns:
        Criteria string for clarity evaluation
    """
    criteria_parts = [
        "Well-organized with clear section structure",
        "No ambiguous or confusing instructions",
        "Appropriate level of detail (not too sparse/verbose)",
        "Consistent terminology throughout",
        "Examples clearly illustrate concepts",
        "Easy to scan and find information",
    ]

    if resource_type == "agent":
        criteria_parts.extend(
            [
                "Role and responsibilities clearly defined",
                "Workflow steps are actionable",
            ]
        )
    elif resource_type == "skill":
        criteria_parts.extend(
            [
                "Activation conditions are unambiguous",
                "Capabilities are clearly scoped",
            ]
        )
    elif resource_type == "command":
        criteria_parts.extend(
            [
                "Arguments clearly documented",
                "Expected behavior is obvious",
            ]
        )

    return "\n".join(f"- {c}" for c in criteria_parts)


class QualityEvaluator:
    """Agentic quality evaluator for multi-resource optimization.

    Uses LLM self-critique to assess resource quality across three dimensions:
    completeness, accuracy, and clarity.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the evaluator.

        Args:
            model: Model to use for evaluation. Defaults to CGF_EVAL_MODEL
                   or claude-sonnet-4-20250514.
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
        """
        self.model = model or os.environ.get("CGF_EVAL_MODEL", "claude-sonnet-4-20250514")
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    async def evaluate(
        self,
        resource_content: str,
        resource_type: str,
        spec: MultiResourceSpec,
        resource_name: str | None = None,
        research_findings: dict[str, Any] | None = None,
    ) -> QualityScore:
        """Evaluate resource quality.

        Args:
            resource_content: Full content of the resource
            resource_type: Type (agent, skill, command)
            spec: The multi-resource spec
            resource_name: Optional specific resource name
            research_findings: Optional research findings to check against

        Returns:
            QualityScore with dimension scores and improvement suggestions
        """
        logger.info(
            "Evaluating resource quality",
            resource_type=resource_type,
            resource_name=resource_name,
        )

        # Build evaluation criteria
        completeness_criteria = _build_completeness_criteria(resource_type, spec, resource_name)
        accuracy_criteria = _build_accuracy_criteria(resource_type, research_findings)
        clarity_criteria = _build_clarity_criteria(resource_type)

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            resource_content=resource_content,
            resource_type=resource_type,
            spec=spec,
            completeness_criteria=completeness_criteria,
            accuracy_criteria=accuracy_criteria,
            clarity_criteria=clarity_criteria,
        )

        # Call LLM for evaluation
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            evaluation_text = response.content[0].text

            # Parse the structured response
            score = self._parse_evaluation_response(evaluation_text)
            score.raw_evaluation = evaluation_text

            logger.info(
                "Quality evaluation complete",
                resource_type=resource_type,
                overall=f"{score.overall:.2f}",
                completeness=f"{score.completeness:.2f}",
                accuracy=f"{score.accuracy:.2f}",
                clarity=f"{score.clarity:.2f}",
            )

            return score

        except anthropic.APIError as e:
            logger.error("API error during evaluation", error=str(e))
            # Return a conservative score on error
            return QualityScore(
                completeness=0.5,
                accuracy=0.5,
                clarity=0.5,
                improvement_suggestions=["Evaluation failed - manual review needed"],
            )

    def _build_evaluation_prompt(
        self,
        resource_content: str,
        resource_type: str,
        spec: MultiResourceSpec,
        completeness_criteria: str,
        accuracy_criteria: str,
        clarity_criteria: str,
    ) -> str:
        """Build the evaluation prompt for the LLM."""
        return f"""You are evaluating a Claude Code {resource_type} for quality.

## Spec Context

**Purpose**: {spec.purpose}

**Required Capabilities**:
{self._format_capabilities(spec.capabilities)}

**Constraints**:
{self._format_list(spec.constraints)}

## Resource to Evaluate

```markdown
{resource_content}
```

## Evaluation Criteria

### Completeness (weight: 35%)
Does this resource fully address the required capabilities?

{completeness_criteria}

### Accuracy (weight: 35%)
Are the patterns, examples, and technical details correct?

{accuracy_criteria}

### Clarity (weight: 30%)
Is this resource well-organized and easy to understand?

{clarity_criteria}

## Instructions

Evaluate the resource and respond with a JSON object in this exact format:

```json
{{
  "completeness": 0.XX,
  "completeness_reasoning": "Brief explanation",
  "missing_capabilities": ["list", "of", "missing", "items"],

  "accuracy": 0.XX,
  "accuracy_reasoning": "Brief explanation",
  "accuracy_issues": ["list", "of", "issues", "found"],

  "clarity": 0.XX,
  "clarity_reasoning": "Brief explanation",
  "clarity_issues": ["list", "of", "issues", "found"],

  "improvement_suggestions": [
    "Specific actionable improvement 1",
    "Specific actionable improvement 2",
    "Specific actionable improvement 3"
  ]
}}
```

Score each dimension from 0.0 to 1.0 where:
- 0.0-0.3: Major deficiencies
- 0.4-0.6: Acceptable but needs work
- 0.7-0.8: Good with minor improvements needed
- 0.9-1.0: Excellent, meets or exceeds expectations

Be specific in your improvement suggestions - they should be actionable.
"""

    def _format_capabilities(self, capabilities: list[Capability]) -> str:
        """Format capabilities for prompt."""
        lines = []
        for cap in capabilities:
            lines.append(f"- **{cap.name}**: {cap.description}")
            for subcap in cap.subcapabilities[:3]:
                lines.append(f"  - {subcap}")
        return "\n".join(lines) if lines else "- (none specified)"

    def _format_list(self, items: list[str]) -> str:
        """Format a list for prompt."""
        if not items:
            return "- (none specified)"
        return "\n".join(f"- {item}" for item in items[:5])

    def _parse_evaluation_response(self, response: str) -> QualityScore:
        """Parse the LLM evaluation response."""
        # Extract JSON from response
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON without code block
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("Could not parse evaluation response")
                return QualityScore(
                    completeness=0.5,
                    accuracy=0.5,
                    clarity=0.5,
                    improvement_suggestions=["Evaluation parse failed - manual review needed"],
                )

        try:
            data = json.loads(json_str)
            return QualityScore(
                completeness=float(data.get("completeness", 0.5)),
                accuracy=float(data.get("accuracy", 0.5)),
                clarity=float(data.get("clarity", 0.5)),
                improvement_suggestions=data.get("improvement_suggestions", []),
                missing_capabilities=data.get("missing_capabilities", []),
                accuracy_issues=data.get("accuracy_issues", []),
                clarity_issues=data.get("clarity_issues", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("JSON parse error in evaluation", error=str(e))
            return QualityScore(
                completeness=0.5,
                accuracy=0.5,
                clarity=0.5,
                improvement_suggestions=[f"Evaluation parse failed: {e}"],
            )


async def evaluate_resource_quality(
    resource_content: str,
    resource_type: str,
    spec: MultiResourceSpec,
    resource_name: str | None = None,
    research_findings: dict[str, Any] | None = None,
    model: str | None = None,
) -> QualityScore:
    """Convenience function to evaluate resource quality.

    Args:
        resource_content: Full content of the resource
        resource_type: Type (agent, skill, command)
        spec: The multi-resource spec
        resource_name: Optional specific resource name
        research_findings: Optional research findings
        model: Optional model override

    Returns:
        QualityScore with evaluation results
    """
    evaluator = QualityEvaluator(model=model)
    return await evaluator.evaluate(
        resource_content=resource_content,
        resource_type=resource_type,
        spec=spec,
        resource_name=resource_name,
        research_findings=research_findings,
    )


def create_improvement_prompt(
    resource_content: str,
    resource_type: str,
    score: QualityScore,
) -> str:
    """Create a prompt for improving a resource based on quality evaluation.

    Args:
        resource_content: Current resource content
        resource_type: Type of resource
        score: Quality evaluation score

    Returns:
        Prompt string for improvement
    """
    improvements_text = "\n".join(f"- {suggestion}" for suggestion in score.improvement_suggestions)

    missing_text = ""
    if score.missing_capabilities:
        missing_text = f"""
### Missing Capabilities
{chr(10).join(f"- {cap}" for cap in score.missing_capabilities)}
"""

    accuracy_text = ""
    if score.accuracy_issues:
        accuracy_text = f"""
### Accuracy Issues to Fix
{chr(10).join(f"- {issue}" for issue in score.accuracy_issues)}
"""

    clarity_text = ""
    if score.clarity_issues:
        clarity_text = f"""
### Clarity Issues to Fix
{chr(10).join(f"- {issue}" for issue in score.clarity_issues)}
"""

    return f"""Improve this Claude Code {resource_type} based on the following evaluation.

## Current Quality Scores

- Completeness: {score.completeness:.2f} (target: 0.85+)
- Accuracy: {score.accuracy:.2f} (target: 0.85+)
- Clarity: {score.clarity:.2f} (target: 0.85+)
- Overall: {score.overall:.2f}

## Required Improvements

{improvements_text}
{missing_text}{accuracy_text}{clarity_text}

## Current Resource

```markdown
{resource_content}
```

## Instructions

Revise the resource to address all the issues listed above.
Maintain the overall structure but improve content quality.
Return the complete improved resource in a markdown code block.
"""
