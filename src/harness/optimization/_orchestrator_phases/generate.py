"""GENERATE phase implementation.

Delegates to the ``context-engineer`` agent (one invocation per pending
resource).  Parses ``[GENERATE_COMPLETE:{path}]`` signals and validates
that the file actually got written before marking the resource as
generated.  Retries once with a simplified prompt when the first attempt
produces no file.

Functions mounted onto :class:`MultiResourceOrchestrator` as:

- ``_delegate_generation`` ← :func:`delegate`
- ``_setup_workspace_dirs`` ← :func:`setup_workspace_dirs`
- ``_get_resource_purpose`` ← :func:`get_resource_purpose`
- ``_get_resource_instructions`` ← :func:`get_resource_instructions`
- ``_generate_plugin_json`` ← :func:`generate_plugin_json`
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from harness.optimization._orchestrator_helpers import (
    AGENT_GENERATE,
    validate_write_path,
)
from harness.optimization.protocols.signals import SignalType

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate resource generation to context-engineer agent.

    Spawns context-engineer for each pending resource.
    Parses [GENERATE_COMPLETE:{path}] signals.
    """
    if not self._spec or not self._state:
        return

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir
    pending = self._state.get_pending_resources()

    logger.info(
        "GENERATE: Creating resources",
        total=len(pending),
    )

    self._setup_workspace_dirs(workspace)

    # Load research findings for context
    eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
    research_context = ""
    if eval_criteria_path.exists():
        research_context = f"\nEval criteria: {eval_criteria_path}"

    for resource in pending:
        # Backup original if it exists (for v0 preservation)
        self._backup_original_resource(resource.path)

        self._state.update_resource(resource.path, status="in_progress")
        self._save_state()

        # Find resource info from spec
        name = Path(resource.path).stem
        if resource.resource_type == "skill":
            name = Path(resource.path).parent.name

        purpose = self._get_resource_purpose(name, resource.resource_type)

        # Build resource-specific instructions
        resource_instructions = self._get_resource_instructions(
            name, resource.resource_type, purpose
        )

        prompt = f"""Generate a {resource.resource_type} for multi-resource plugin.

Workspace: {workspace}
Plugin: {self._spec.name}
Output path: {workspace / resource.path}

Resource Details:
- Name: {name}
- Type: {resource.resource_type}
- Purpose: {purpose}

{resource_instructions}

Constraints from SPEC.md:
{chr(10).join(f'- {c}' for c in self._spec.constraints[:5])}
{research_context}

Create the {resource.resource_type} following standard templates and best practices.
Write the file to {workspace / resource.path}.

When complete, emit signal:
[GENERATE_COMPLETE:{resource.path}]
resource_type: {resource.resource_type}
word_count: {{count}}
output_path: {workspace / resource.path}
"""

        logger.info(
            "GENERATE: Creating resource",
            path=resource.path,
            type=resource.resource_type,
            timeout=self.config.generate_timeout,
        )
        self._emit_progress("GENERATE", resource.path, "in_progress")

        try:
            # Pass timeout directly to agent
            response = await call_agent_simple(
                AGENT_GENERATE,
                prompt,
                verbose=self.config.verbose or self.config.follow_logs,
                timeout=float(self.config.generate_timeout),
            )

            # Parse signal
            gen_signals = self._signal_parser.parse(response)
            gen_complete = [
                s for s in gen_signals
                if s.type == SignalType.GENERATE_COMPLETE
                and s.resource_path == resource.path
            ]
            if gen_complete:
                # Validate file actually exists before marking as generated
                full_path = workspace / resource.path
                if full_path.exists():
                    self._state.update_resource(
                        resource.path, status="generated", version=0
                    )
                    logger.info("GENERATE: Resource created", path=resource.path)
                    self._emit_progress("GENERATE", resource.path, "complete")
                else:
                    logger.error(
                        "GENERATE: Signal received but file not found",
                        signal_path=resource.path,
                        expected_path=str(full_path),
                    )
                    self._state.update_resource(
                        resource.path,
                        status="failed",
                        error=f"Signal received but file not created at {full_path}",
                    )
                    self._emit_progress(
                        "GENERATE", resource.path, "failed - file not found"
                    )
            else:
                # Check if file was created anyway
                full_path = workspace / resource.path
                if full_path.exists():
                    self._state.update_resource(
                        resource.path, status="generated", version=0
                    )
                    logger.info(
                        "GENERATE: Resource created (no signal)",
                        path=resource.path,
                    )
                else:
                    self._state.update_resource(
                        resource.path,
                        status="failed",
                        error="Generation failed - file not created",
                    )
                    logger.warning(
                        "GENERATE: Resource not created",
                        path=resource.path,
                    )

        except TimeoutError:
            logger.error(
                "GENERATE: Resource timed out",
                path=resource.path,
                timeout=self.config.generate_timeout,
            )
            self._state.update_resource(
                resource.path,
                status="failed",
                error=f"Generation timed out after {self.config.generate_timeout}s",
            )
            self._emit_progress(
                "GENERATE", resource.path,
                f"timeout after {self.config.generate_timeout}s"
            )
        except Exception as e:
            logger.error(
                "GENERATE: Resource failed",
                path=resource.path,
                error=str(e),
            )
            self._state.update_resource(
                resource.path, status="failed", error=str(e)
            )

        # Retry once with simplified prompt if generation failed
        full_path = workspace / resource.path
        if (
            self._state.resources[resource.path].status == "failed"
            and not full_path.exists()
        ):
            logger.info(
                "GENERATE: Retrying with simplified prompt",
                path=resource.path,
            )
            self._emit_progress(
                "GENERATE", resource.path, "retrying"
            )
            retry_prompt = (
                f"Create {resource.resource_type} file.\n"
                f"Write to: {full_path}\n"
                f"Name: {name}\n"
                f"Purpose: {purpose}\n"
                f"Keep it focused and concise.\n"
                f"When done, emit: "
                f"[GENERATE_COMPLETE:{resource.path}]"
            )
            try:
                await call_agent_simple(
                    AGENT_GENERATE,
                    retry_prompt,
                    verbose=self.config.verbose
                    or self.config.follow_logs,
                    timeout=float(self.config.generate_timeout),
                )
                if full_path.exists():
                    self._state.update_resource(
                        resource.path,
                        status="generated",
                        version=0,
                    )
                    logger.info(
                        "GENERATE: Resource created on retry",
                        path=resource.path,
                    )
                    self._emit_progress(
                        "GENERATE", resource.path, "complete"
                    )
                else:
                    logger.warning(
                        "GENERATE: Retry also failed",
                        path=resource.path,
                    )
            except Exception as retry_err:
                logger.error(
                    "GENERATE: Retry failed",
                    path=resource.path,
                    error=str(retry_err),
                )

        self._save_state()

    # Generate plugin.json
    await self._generate_plugin_json()

    logger.info(
        "GENERATE: Complete",
        generated=len(self._state.get_generated_resources()),
        failed=len(self._state.get_failed_resources()),
    )


def setup_workspace_dirs(
    self: MultiResourceOrchestrator, workspace: Path
) -> None:
    """Create directory structure for resource generation.

    Only creates directories for resource types present in the SPEC.
    The .claude-plugin directory is always created (needed for plugin.json).
    """
    (workspace / ".claude-plugin").mkdir(parents=True, exist_ok=True)

    if self._spec.proposed_agents:
        (workspace / "agents").mkdir(parents=True, exist_ok=True)
    if self._spec.proposed_commands:
        (workspace / "commands").mkdir(parents=True, exist_ok=True)
    for skill in self._spec.proposed_skills:
        (workspace / "skills" / skill.name).mkdir(parents=True, exist_ok=True)
    if self._spec.proposed_mcp_tools:
        (workspace / "tools").mkdir(parents=True, exist_ok=True)
    if self._spec.proposed_mcp_servers:
        (workspace / "mcp-servers").mkdir(parents=True, exist_ok=True)


def get_resource_purpose(
    self: MultiResourceOrchestrator,
    name: str,
    resource_type: str,
) -> str:
    """Get purpose for a resource from the spec."""
    if not self._spec:
        return ""

    if resource_type == "agent":
        for agent in self._spec.proposed_agents:
            if agent.name == name:
                return agent.purpose
    elif resource_type == "skill":
        for skill in self._spec.proposed_skills:
            if skill.name == name:
                return skill.purpose
    elif resource_type == "command":
        for cmd in self._spec.proposed_commands:
            if cmd.name.lstrip("/") == name:
                return cmd.purpose
    elif resource_type == "mcp_tool":
        for tool in self._spec.proposed_mcp_tools:
            if tool.name == name:
                return tool.purpose
    elif resource_type == "mcp_server":
        for server in self._spec.proposed_mcp_servers:
            if server.name == name:
                return server.purpose
    return ""


def get_resource_instructions(
    self: MultiResourceOrchestrator,
    name: str,
    resource_type: str,
    _purpose: str,
) -> str:
    """Get resource-type-specific generation instructions.

    Args:
        name: Resource name.
        resource_type: Type of resource.
        _purpose: Purpose from spec (available for future use).

    Returns:
        Instruction text for the generation prompt.
    """
    if resource_type == "skill":
        # Get trigger terms if available
        triggers = []
        if self._spec:
            for skill in self._spec.proposed_skills:
                if skill.name == name:
                    triggers = skill.triggers
                    break

        trigger_text = (
            f"Trigger terms: {', '.join(triggers)}"
            if triggers
            else "Determine appropriate trigger terms from purpose"
        )

        return f"""Skill-Specific Instructions:
- Create SKILL.md with proper YAML frontmatter (name, description)
- Description must include specific trigger terms for auto-activation
- Include "Activate when user mentions:" section
- Include "Use for:" and "Do NOT use for:" boundaries
- Keep SKILL.md under 5000 tokens (core instructions only)
- Use progressive disclosure: reference examples/ and templates/ directories
- {trigger_text}

Skill Directory Structure:
  skills/{name}/
  ├── SKILL.md          # Main skill (required)
  ├── examples/         # Usage examples (optional)
  └── templates/        # Code templates (optional)"""

    elif resource_type == "agent":
        return """Agent-Specific Instructions:
- Create agent with YAML frontmatter (name, description, tools, model)
- Description must include 2-4 concrete examples with commentary
- Use "Use PROACTIVELY when..." phrases for discovery optimization
- Specify minimal necessary tool access (least privilege)
- Include clear constraints and boundaries
- Add working code examples in the system prompt"""

    elif resource_type == "command":
        return """Command-Specific Instructions:
- Create command with YAML frontmatter (name, description, allowed_tools)
- Document all arguments ($1, $2, $ARGUMENTS)
- Provide default values for optional args (${2:-default})
- Include usage examples
- Specify allowed_tools appropriately"""

    elif resource_type == "mcp_tool":
        return f"""MCP Tool-Specific Instructions:
- Create a Python file with a FastMCP @mcp.tool() decorated async handler
- Tool name: {name} (snake_case, verb_noun format)
- Write a 3-4 sentence description: what it does, when to use, when NOT to use, behavior notes
- Include parameter descriptions with format/constraint information
- Validate inputs at the top of the handler (fail fast with corrective error messages)
- Return formatted text (not raw JSON dumps)
- Use MCP content block format for claude_agent_sdk pattern
- Include a test snippet or companion test file
- Output path: tools/{name}.py
- Reference skill: mcp-tool-dev"""

    elif resource_type == "mcp_server":
        # Determine language from spec
        language = "python"
        if self._spec:
            for server in self._spec.proposed_mcp_servers:
                if server.name == name:
                    language = server.language
                    break

        return f"""MCP Server-Specific Instructions:
- Language: {language}
- Create a server directory: mcp-servers/{name}/
- {"Use FastMCP pattern with @mcp.tool() decorators" if language == "python" else "Use @modelcontextprotocol/sdk with Zod schemas"}
- Register all tools with 3-4 sentence descriptions
- {"Include pyproject.toml with [project.scripts] for uvx packaging" if language == "python" else "Include package.json with bin entry for npx packaging"}
- Implement graceful shutdown (SIGINT/SIGTERM handlers)
- All logging to stderr (stdout is JSON-RPC transport)
- Include unit tests for each tool handler
- Include README with tool listing and client configuration
- Output path: mcp-servers/{name}/
- Reference skill: mcp-server-dev"""

    return ""


async def generate_plugin_json(self: MultiResourceOrchestrator) -> None:
    """Generate plugin.json metadata file."""
    if not self._spec:
        return

    import json

    plugin_json = {
        "name": self._spec.name.lower().replace(" ", "-"),
        "version": "1.0.0",
        "description": self._spec.purpose[:200],
        "keywords": [
            self._spec.spec_type.name.lower(),
            *[cap.name.lower() for cap in self._spec.capabilities[:3]],
        ],
        "components": {
            "agents": [a.name for a in self._spec.proposed_agents],
            "skills": [s.name for s in self._spec.proposed_skills],
            "commands": [c.name for c in self._spec.proposed_commands],
            "mcp_tools": [t.name for t in self._spec.proposed_mcp_tools],
            "mcp_servers": [s.name for s in self._spec.proposed_mcp_servers],
        },
    }

    workspace = self.config.workspace_dir
    plugin_path = workspace / ".claude-plugin" / "plugin.json"

    # Validate path
    validate_write_path(plugin_path, workspace)

    with open(plugin_path, "w") as f:
        json.dump(plugin_json, f, indent=2)

    logger.info("GENERATE: Created plugin.json")
