"""Multi-resource SPEC.md parser for generative optimization.

Parses requirements-driven SPEC.md files that define multi-resource artifacts
(plugins, skill sets, workflows) and extracts structured information for
the generative optimization pipeline.

Example usage:
    from harness.optimization.multi_resource_spec import (
        MultiResourceSpec,
        parse_multi_resource_spec,
        detect_spec_type,
        SpecType,
    )

    # Parse a SPEC.md file
    spec = parse_multi_resource_spec(Path("workspace/iac-team/SPEC.md"))

    # Check spec type
    if spec.spec_type == SpecType.PLUGIN:
        print(f"Plugin: {spec.name}")
        print(f"Agents: {[a.name for a in spec.proposed_agents]}")
        print(f"Skills: {[s.name for s in spec.proposed_skills]}")

    # Detect type from content
    spec_type = detect_spec_type(content)
    if spec_type == SpecType.SINGLE_RESOURCE:
        # Use existing single-resource CGF
        pass
    else:
        # Use multi-resource orchestrator
        pass
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class SpecType(Enum):
    """Type of SPEC.md detected from content."""

    SINGLE_RESOURCE = auto()  # Has "## Resource" section with file
    PLUGIN = auto()  # Has "## Capabilities" + agents/skills/commands
    SKILL_SET = auto()  # Has "## Type: skill-set"
    WORKFLOW = auto()  # Has "## Type: workflow" + stages
    UNKNOWN = auto()  # Could not determine type


@dataclass
class ProposedAgent:
    """Agent proposed in SPEC.md structure section.

    Attributes:
        name: Agent name (e.g., "iac-analyzer")
        purpose: Brief description of agent's purpose
        tools: Proposed tool access (optional)
        model: Proposed model (sonnet/opus/haiku, optional)
    """

    name: str
    purpose: str
    tools: list[str] = field(default_factory=list)
    model: str = "sonnet"


@dataclass
class ProposedSkill:
    """Skill proposed in SPEC.md structure section.

    Attributes:
        name: Skill name (e.g., "kubernetes-native")
        purpose: Brief description of skill's purpose
        triggers: Proposed activation triggers (optional)
    """

    name: str
    purpose: str
    triggers: list[str] = field(default_factory=list)


@dataclass
class ProposedCommand:
    """Command proposed in SPEC.md structure section.

    Attributes:
        name: Command name (e.g., "/iac")
        purpose: Brief description of command's purpose
        invokes: Agent(s) the command invokes (optional)
    """

    name: str
    purpose: str
    invokes: list[str] = field(default_factory=list)


@dataclass
class WorkflowStage:
    """Stage in a workflow spec.

    Attributes:
        name: Stage name (e.g., "discovery")
        agent: Agent that executes this stage
        inputs: Expected inputs
        outputs: Produced outputs
        parallel: Whether multiple instances can run in parallel
        depends_on: Stages this stage depends on
    """

    name: str
    agent: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    parallel: bool = False
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Capability:
    """Capability extracted from SPEC.md.

    Attributes:
        name: Capability name (e.g., "Repository Analysis")
        description: What this capability does
        subcapabilities: Nested capabilities (optional)
    """

    name: str
    description: str
    subcapabilities: list[str] = field(default_factory=list)


@dataclass
class QualityCriterion:
    """Quality criterion from SPEC.md.

    Attributes:
        metric: What is measured (e.g., "Dockerfile build success")
        target: Target value (e.g., "100%", "Pass kubeconform")
    """

    metric: str
    target: str


@dataclass
class MultiResourceSpec:
    """Parsed multi-resource SPEC.md.

    Represents a requirements-driven specification for generating
    multiple coordinated resources (plugins, skill sets, workflows).

    Attributes:
        name: Spec name derived from title or directory
        spec_type: Type of multi-resource spec
        purpose: Why this exists / what problem it solves
        target_users: Who will use this
        capabilities: What it can do
        constraints: Limits and requirements
        quality_criteria: Validation requirements
        research_topics: Topics to research
        proposed_agents: User-proposed agents (may be counter-proposed)
        proposed_skills: User-proposed skills
        proposed_commands: User-proposed commands
        workflow_stages: Stages for workflow specs
        raw_content: Original SPEC.md content
        source_path: Path to SPEC.md file
        content_hash: Hash for change detection
        parsed_at: When spec was parsed
    """

    name: str
    spec_type: SpecType
    purpose: str
    target_users: list[str] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    quality_criteria: list[QualityCriterion] = field(default_factory=list)
    research_topics: list[str] = field(default_factory=list)
    proposed_agents: list[ProposedAgent] = field(default_factory=list)
    proposed_skills: list[ProposedSkill] = field(default_factory=list)
    proposed_commands: list[ProposedCommand] = field(default_factory=list)
    workflow_stages: list[WorkflowStage] = field(default_factory=list)
    raw_content: str = ""
    source_path: Path | None = None
    content_hash: str = ""
    parsed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_proposed_structure(self) -> bool:
        """Check if spec includes a proposed structure."""
        return bool(
            self.proposed_agents
            or self.proposed_skills
            or self.proposed_commands
            or self.workflow_stages
        )

    @property
    def total_proposed_resources(self) -> int:
        """Total number of proposed resources."""
        return len(self.proposed_agents) + len(self.proposed_skills) + len(self.proposed_commands)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "name": self.name,
            "spec_type": self.spec_type.name,
            "purpose": self.purpose,
            "target_users": self.target_users,
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "subcapabilities": c.subcapabilities,
                }
                for c in self.capabilities
            ],
            "constraints": self.constraints,
            "quality_criteria": [
                {"metric": q.metric, "target": q.target} for q in self.quality_criteria
            ],
            "research_topics": self.research_topics,
            "proposed_agents": [
                {
                    "name": a.name,
                    "purpose": a.purpose,
                    "tools": a.tools,
                    "model": a.model,
                }
                for a in self.proposed_agents
            ],
            "proposed_skills": [
                {
                    "name": s.name,
                    "purpose": s.purpose,
                    "triggers": s.triggers,
                }
                for s in self.proposed_skills
            ],
            "proposed_commands": [
                {
                    "name": c.name,
                    "purpose": c.purpose,
                    "invokes": c.invokes,
                }
                for c in self.proposed_commands
            ],
            "workflow_stages": [
                {
                    "name": s.name,
                    "agent": s.agent,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                    "parallel": s.parallel,
                    "depends_on": s.depends_on,
                }
                for s in self.workflow_stages
            ],
            "has_proposed_structure": self.has_proposed_structure,
            "total_proposed_resources": self.total_proposed_resources,
            "source_path": str(self.source_path) if self.source_path else None,
            "content_hash": self.content_hash,
            "parsed_at": self.parsed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiResourceSpec:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            spec_type=SpecType[data["spec_type"]],
            purpose=data["purpose"],
            target_users=data.get("target_users", []),
            capabilities=[
                Capability(
                    name=c["name"],
                    description=c["description"],
                    subcapabilities=c.get("subcapabilities", []),
                )
                for c in data.get("capabilities", [])
            ],
            constraints=data.get("constraints", []),
            quality_criteria=[
                QualityCriterion(metric=q["metric"], target=q["target"])
                for q in data.get("quality_criteria", [])
            ],
            research_topics=data.get("research_topics", []),
            proposed_agents=[
                ProposedAgent(
                    name=a["name"],
                    purpose=a["purpose"],
                    tools=a.get("tools", []),
                    model=a.get("model", "sonnet"),
                )
                for a in data.get("proposed_agents", [])
            ],
            proposed_skills=[
                ProposedSkill(
                    name=s["name"],
                    purpose=s["purpose"],
                    triggers=s.get("triggers", []),
                )
                for s in data.get("proposed_skills", [])
            ],
            proposed_commands=[
                ProposedCommand(
                    name=c["name"],
                    purpose=c["purpose"],
                    invokes=c.get("invokes", []),
                )
                for c in data.get("proposed_commands", [])
            ],
            workflow_stages=[
                WorkflowStage(
                    name=s["name"],
                    agent=s["agent"],
                    inputs=s.get("inputs", []),
                    outputs=s.get("outputs", []),
                    parallel=s.get("parallel", False),
                    depends_on=s.get("depends_on", []),
                )
                for s in data.get("workflow_stages", [])
            ],
            source_path=Path(data["source_path"]) if data.get("source_path") else None,
            content_hash=data.get("content_hash", ""),
            parsed_at=datetime.fromisoformat(data["parsed_at"])
            if data.get("parsed_at")
            else datetime.now(UTC),
        )


def detect_spec_type(content: str) -> SpecType:
    """Detect the type of SPEC.md from its content.

    Args:
        content: Raw SPEC.md content.

    Returns:
        Detected SpecType.
    """
    content_lower = content.lower()

    # Check for explicit type declaration
    type_match = re.search(r"^##\s+type[:\s]*(.+)$", content, re.MULTILINE | re.IGNORECASE)
    if type_match:
        type_value = type_match.group(1).strip().lower()
        if "skill-set" in type_value or "skillset" in type_value:
            return SpecType.SKILL_SET
        if "workflow" in type_value:
            return SpecType.WORKFLOW

    # Check for single-resource format (has "## Resource" with "**File:**")
    has_resource_section = bool(re.search(r"^##\s+resource\b", content_lower, re.MULTILINE))
    has_file_field = bool(re.search(r"\*\*file:\*\*", content_lower))
    if has_resource_section and has_file_field:
        return SpecType.SINGLE_RESOURCE

    # Check for multi-resource plugin (has "## Capabilities" section)
    has_capabilities = bool(re.search(r"^##\s+capabilities\b", content_lower, re.MULTILINE))
    if has_capabilities:
        # Check for workflow-specific patterns
        has_stages = bool(re.search(r"###\s+stage\s+\d", content_lower))
        has_depends_on = "depends_on" in content_lower or "depends on" in content_lower
        if has_stages or has_depends_on:
            return SpecType.WORKFLOW
        return SpecType.PLUGIN

    # Check for skill-set patterns
    has_skill_variants = bool(re.search(r"###\s+\w+\s+(module\s+)?skill", content_lower))
    if has_skill_variants:
        return SpecType.SKILL_SET

    return SpecType.UNKNOWN


def _extract_section(content: str, header: str) -> str | None:
    """Extract content from a markdown section.

    Args:
        content: Full markdown content.
        header: Section header to find (without ##).

    Returns:
        Section content or None if not found.
    """
    # Match the header and capture until next ## header or end
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_subsection(content: str, header: str) -> str | None:
    """Extract content from a ### subsection.

    Args:
        content: Section content.
        header: Subsection header to find (without ###).

    Returns:
        Subsection content or None if not found.
    """
    pattern = rf"^###\s+{re.escape(header)}\s*\n(.*?)(?=^###\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_list_items(content: str) -> list[str]:
    """Extract list items from markdown content.

    Args:
        content: Markdown content with list items.

    Returns:
        List of extracted items.
    """
    items = []
    # Match both - and * list markers
    for match in re.finditer(r"^[\-\*]\s+(.+)$", content, re.MULTILINE):
        items.append(match.group(1).strip())
    return items


def _extract_numbered_items(content: str) -> list[tuple[int, str]]:
    """Extract numbered list items from markdown content.

    Args:
        content: Markdown content with numbered list.

    Returns:
        List of (number, item) tuples.
    """
    items = []
    for match in re.finditer(r"^(\d+)\.\s+(.+)$", content, re.MULTILINE):
        items.append((int(match.group(1)), match.group(2).strip()))
    return items


def _extract_table_rows(content: str) -> list[dict[str, str]]:
    """Extract rows from a markdown table.

    Args:
        content: Markdown content with table.

    Returns:
        List of dictionaries mapping header to value.
    """
    rows = []

    # Find table in content
    lines = content.split("\n")
    header_idx = -1
    headers: list[str] = []

    for i, line in enumerate(lines):
        if (
            "|" in line
            and "---" not in line
            and i + 1 < len(lines)
            and re.match(r"^\|[\s\-:]+\|", lines[i + 1])
        ):
            # This is the header row
            header_idx = i
            headers = [h.strip() for h in line.strip("|").split("|")]
            break

    if header_idx < 0:
        return rows

    # Extract data rows (skip header and separator)
    for line in lines[header_idx + 2 :]:
        if "|" not in line or not line.strip():
            continue
        values = [v.strip() for v in line.strip("|").split("|")]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values, strict=False)))

    return rows


def _parse_proposed_agents(content: str) -> list[ProposedAgent]:
    """Parse proposed agents from SPEC.md.

    Args:
        content: Content of "### Agents" subsection.

    Returns:
        List of proposed agents.
    """
    agents = []

    # Match pattern: - **name** - description
    for match in re.finditer(
        r"^[\-\*]\s+\*\*([^*]+)\*\*\s*[\-\–]\s*(.+)$",
        content,
        re.MULTILINE,
    ):
        name = match.group(1).strip()
        purpose = match.group(2).strip()
        agents.append(ProposedAgent(name=name, purpose=purpose))

    return agents


def _parse_skills_table(content: str) -> list[ProposedSkill]:
    """Parse skills from a markdown table in SPEC.md.

    Looks for tables with columns like: | Skill | Purpose | Agent |
    This handles SPECs that list skills in tabular format rather than
    bullet points.

    Args:
        content: Full content of SPEC.md or section content.

    Returns:
        List of proposed skills parsed from table.
    """
    skills = []

    # Find table rows using _extract_table_rows helper
    rows = _extract_table_rows(content)

    for row in rows:
        # Look for Skill/Name column
        name = row.get("Skill", row.get("skill", row.get("Name", row.get("name", ""))))
        # Look for Purpose/Description column
        purpose = row.get(
            "Purpose",
            row.get("purpose", row.get("Description", row.get("description", ""))),
        )
        # Look for Agent column (optional, for context)
        agent = row.get("Agent", row.get("agent", ""))

        if name and purpose:
            # Clean up name (remove backticks, bold, etc.)
            name = re.sub(r"[`*]", "", name).strip()
            purpose = purpose.strip()

            # Include agent context in purpose if available
            if agent and agent not in purpose:
                purpose = f"{purpose} (used by {agent})"

            skills.append(ProposedSkill(name=name, purpose=purpose))

    return skills


def _parse_proposed_skills(content: str) -> list[ProposedSkill]:
    """Parse proposed skills from SPEC.md.

    Supports both bullet point format and table format.

    Args:
        content: Content of "### Skills" subsection.

    Returns:
        List of proposed skills.
    """
    skills = []

    # First try to parse from table format
    table_skills = _parse_skills_table(content)
    if table_skills:
        skills.extend(table_skills)

    # Also match bullet point pattern: - **name** - description
    for match in re.finditer(
        r"^[\-\*]\s+\*\*([^*]+)\*\*\s*[\-\–]\s*(.+)$",
        content,
        re.MULTILINE,
    ):
        name = match.group(1).strip()
        purpose = match.group(2).strip()
        # Avoid duplicates from table parsing
        if not any(s.name == name for s in skills):
            skills.append(ProposedSkill(name=name, purpose=purpose))

    # Also match without bold: - name - description (for skills listed without bold)
    for match in re.finditer(
        r"^[\-\*]\s+([a-z][a-z0-9\-]+)\s*[\-\–]\s*(.+)$",
        content,
        re.MULTILINE | re.IGNORECASE,
    ):
        name = match.group(1).strip()
        purpose = match.group(2).strip()
        # Avoid duplicates
        if not any(s.name == name for s in skills):
            skills.append(ProposedSkill(name=name, purpose=purpose))

    return skills


def _parse_proposed_commands(content: str) -> list[ProposedCommand]:
    """Parse proposed commands from SPEC.md.

    Args:
        content: Content of "### Commands" subsection.

    Returns:
        List of proposed commands.
    """
    commands = []

    # Match pattern: - **/name** - description or - **name** - description
    for match in re.finditer(
        r"^[\-\*]\s+\*\*/?([^*]+)\*\*\s*[\-\–]\s*(.+)$",
        content,
        re.MULTILINE,
    ):
        name = match.group(1).strip()
        if not name.startswith("/"):
            name = f"/{name}"
        purpose = match.group(2).strip()
        commands.append(ProposedCommand(name=name, purpose=purpose))

    return commands


def _parse_capabilities(content: str) -> list[Capability]:
    """Parse capabilities from SPEC.md.

    Args:
        content: Content of "## Capabilities" section.

    Returns:
        List of capabilities.
    """
    capabilities = []

    # Find ### subsections (e.g., "### Core Workflows")
    subsection_pattern = r"^###\s+(.+)$"
    subsections = list(re.finditer(subsection_pattern, content, re.MULTILINE))

    for i, match in enumerate(subsections):
        name = match.group(1).strip()

        # Get content until next subsection or end
        start = match.end()
        end = subsections[i + 1].start() if i + 1 < len(subsections) else len(content)
        subsection_content = content[start:end].strip()

        # Extract subcapabilities from list items
        subcaps = []
        for item_match in re.finditer(
            r"^(?:\d+\.|[\-\*])\s+\*\*([^*]+)\*\*\s*[\-\–]\s*(.+)$",
            subsection_content,
            re.MULTILINE,
        ):
            subcaps.append(f"{item_match.group(1)}: {item_match.group(2)}")

        # Also extract simple list items
        for item_match in re.finditer(
            r"^(?:\d+\.|[\-\*])\s+([^*\n]+)$",
            subsection_content,
            re.MULTILINE,
        ):
            item = item_match.group(1).strip()
            if item and not any(item in s for s in subcaps):
                subcaps.append(item)

        # First paragraph as description
        paragraphs = [
            p.strip()
            for p in subsection_content.split("\n\n")
            if p.strip() and not p.strip().startswith(("-", "*", "1."))
        ]
        description = paragraphs[0] if paragraphs else ""

        capabilities.append(
            Capability(
                name=name,
                description=description,
                subcapabilities=subcaps,
            )
        )

    # If no subsections, treat entire section as one capability
    if not capabilities:
        items = _extract_list_items(content)
        numbered = _extract_numbered_items(content)

        all_items = items + [item for _, item in numbered]
        if all_items:
            capabilities.append(
                Capability(
                    name="Core Capabilities",
                    description="",
                    subcapabilities=all_items,
                )
            )

    return capabilities


def _parse_quality_criteria(content: str) -> list[QualityCriterion]:
    """Parse quality criteria from SPEC.md.

    Args:
        content: Content of "## Quality Criteria" section.

    Returns:
        List of quality criteria.
    """
    criteria = []

    # Try to parse as table first
    rows = _extract_table_rows(content)
    for row in rows:
        metric = row.get("Metric", row.get("metric", ""))
        target = row.get("Target", row.get("target", ""))
        if metric and target:
            criteria.append(QualityCriterion(metric=metric, target=target))

    # If no table, try list items
    if not criteria:
        for match in re.finditer(
            r"^[\-\*]\s+(.+?):\s*(.+)$",
            content,
            re.MULTILINE,
        ):
            criteria.append(
                QualityCriterion(
                    metric=match.group(1).strip(),
                    target=match.group(2).strip(),
                )
            )

    return criteria


def _parse_workflow_stages(content: str) -> list[WorkflowStage]:
    """Parse workflow stages from SPEC.md.

    Args:
        content: Content of "## Capabilities" section for workflows.

    Returns:
        List of workflow stages.
    """
    stages = []

    # Find ### Stage N: Name or ### Stage: Name subsections
    stage_pattern = r"^###\s+Stage\s*(?:\d+)?[:\s]*(.+)$"
    subsections = list(re.finditer(stage_pattern, content, re.MULTILINE | re.IGNORECASE))

    for i, match in enumerate(subsections):
        name = match.group(1).strip()

        # Get content until next stage or end
        start = match.end()
        end = subsections[i + 1].start() if i + 1 < len(subsections) else len(content)
        stage_content = content[start:end].strip()

        # Extract agent
        agent_match = re.search(r"Agent:\s*([^\n]+)", stage_content, re.IGNORECASE)
        agent = agent_match.group(1).strip() if agent_match else ""

        # Extract inputs
        inputs_match = re.search(r"Inputs?:\s*([^\n]+)", stage_content, re.IGNORECASE)
        inputs = []
        if inputs_match:
            inputs = [i.strip() for i in inputs_match.group(1).split(",")]

        # Extract outputs
        outputs_match = re.search(r"Outputs?:\s*([^\n]+)", stage_content, re.IGNORECASE)
        outputs = []
        if outputs_match:
            outputs = [o.strip() for o in outputs_match.group(1).split(",")]

        # Check for parallel flag
        parallel = "parallel" in stage_content.lower()

        # Extract depends_on
        depends_match = re.search(r"depends_?on:\s*([^\n]+)", stage_content, re.IGNORECASE)
        depends_on = []
        if depends_match:
            depends_on = [d.strip() for d in depends_match.group(1).split(",")]

        stages.append(
            WorkflowStage(
                name=name.lower().replace(" ", "-"),
                agent=agent,
                inputs=inputs,
                outputs=outputs,
                parallel=parallel,
                depends_on=depends_on,
            )
        )

    return stages


def parse_multi_resource_spec(path: Path) -> MultiResourceSpec:
    """Parse a multi-resource SPEC.md file.

    Args:
        path: Path to SPEC.md file.

    Returns:
        Parsed MultiResourceSpec.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If spec cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"SPEC.md not found: {path}")

    content = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Detect spec type
    spec_type = detect_spec_type(content)

    logger.info(
        "Parsing multi-resource spec",
        path=str(path),
        spec_type=spec_type.name,
    )

    # Extract name from title or directory
    title_match = re.search(
        r"^#\s+(?:Multi-Resource\s+)?Spec[:\s]*(.+)$", content, re.MULTILINE | re.IGNORECASE
    )
    name = title_match.group(1).strip() if title_match else path.parent.name

    # Extract purpose
    purpose_section = _extract_section(content, "Purpose")
    purpose = ""
    if purpose_section:
        # Take first paragraph
        paragraphs = [p.strip() for p in purpose_section.split("\n\n") if p.strip()]
        purpose = paragraphs[0] if paragraphs else ""

    # Extract target users
    target_users_section = _extract_section(content, "Target Users")
    target_users = []
    if target_users_section:
        target_users = _extract_list_items(target_users_section)

    # Extract capabilities
    capabilities_section = _extract_section(content, "Capabilities")
    capabilities = []
    workflow_stages = []
    if capabilities_section:
        if spec_type == SpecType.WORKFLOW:
            workflow_stages = _parse_workflow_stages(capabilities_section)
        else:
            capabilities = _parse_capabilities(capabilities_section)

    # Extract constraints
    constraints_section = _extract_section(content, "Constraints")
    constraints = []
    if constraints_section:
        constraints = _extract_list_items(constraints_section)

    # Extract quality criteria
    quality_section = _extract_section(content, "Quality Criteria")
    quality_criteria = []
    if quality_section:
        quality_criteria = _parse_quality_criteria(quality_section)

    # Extract research topics
    research_section = _extract_section(content, "Research Topics")
    research_topics = []
    if research_section:
        research_topics = _extract_list_items(research_section)

    # Extract proposed structure
    proposed_section = _extract_section(content, "Proposed Structure")
    proposed_agents = []
    proposed_skills = []
    proposed_commands = []

    if proposed_section:
        agents_subsection = _extract_subsection(proposed_section, "Agents")
        if agents_subsection:
            proposed_agents = _parse_proposed_agents(agents_subsection)

        skills_subsection = _extract_subsection(proposed_section, "Skills")
        if skills_subsection:
            proposed_skills = _parse_proposed_skills(skills_subsection)

        commands_subsection = _extract_subsection(proposed_section, "Commands")
        if commands_subsection:
            proposed_commands = _parse_proposed_commands(commands_subsection)

    return MultiResourceSpec(
        name=name,
        spec_type=spec_type,
        purpose=purpose,
        target_users=target_users,
        capabilities=capabilities,
        constraints=constraints,
        quality_criteria=quality_criteria,
        research_topics=research_topics,
        proposed_agents=proposed_agents,
        proposed_skills=proposed_skills,
        proposed_commands=proposed_commands,
        workflow_stages=workflow_stages,
        raw_content=content,
        source_path=path,
        content_hash=content_hash,
    )


def is_multi_resource_spec(path: Path) -> bool:
    """Check if a SPEC.md file is a multi-resource spec.

    Args:
        path: Path to SPEC.md file.

    Returns:
        True if multi-resource spec, False if single-resource.
    """
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")
    spec_type = detect_spec_type(content)

    return spec_type in (SpecType.PLUGIN, SpecType.SKILL_SET, SpecType.WORKFLOW)


def save_spec_summary(spec: MultiResourceSpec, output_path: Path) -> None:
    """Save a summary of the parsed spec to YAML.

    Args:
        spec: Parsed specification.
        output_path: Path to save summary.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = spec.to_dict()

    # Remove raw content for summary
    del summary["source_path"]
    if "raw_content" in summary:
        del summary["raw_content"]

    with open(output_path, "w") as f:
        yaml.dump(summary, f, default_flow_style=False, allow_unicode=True)

    logger.info("Saved spec summary", path=str(output_path))
