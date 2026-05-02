"""Workspace layout protocol for multi-resource optimization pipeline.

Provides a single object that resolves all standard paths within an
optimization workspace, given only the root directory.

Usage:
    from harness.optimization.protocols.workspace import WorkspaceLayout

    layout = WorkspaceLayout(root=Path("workspace/my-agent"))
    spec_path = layout.spec          # workspace/my-agent/SPEC.md
    layout.ensure_dirs()             # create all standard directories
"""

from __future__ import annotations

from pathlib import Path


class WorkspaceLayout:
    """Resolve standard paths within an optimization workspace.

    The workspace root is the directory containing ``SPEC.md``.
    All other paths are derived relative to that root.

    Args:
        root: Absolute or relative path to the workspace root directory.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    # -- top-level files -------------------------------------------------------

    @property
    def spec(self) -> Path:
        """Path to the optimization spec file."""
        return self._root / "SPEC.md"

    @property
    def resource_plan(self) -> Path:
        """Path to the resource plan file."""
        return self._root / "RESOURCE_PLAN.md"

    @property
    def changelog(self) -> Path:
        """Path to the human-readable changelog."""
        return self._root / "CHANGELOG.md"

    # -- resource directories --------------------------------------------------

    @property
    def agents_dir(self) -> Path:
        """Directory for agent definition files."""
        return self._root / "agents"

    @property
    def skills_dir(self) -> Path:
        """Directory for skill definition files."""
        return self._root / "skills"

    @property
    def commands_dir(self) -> Path:
        """Directory for command definition files."""
        return self._root / "commands"

    @property
    def tools_dir(self) -> Path:
        """Directory for MCP tool files."""
        return self._root / "tools"

    @property
    def mcp_servers_dir(self) -> Path:
        """Directory for MCP server directories."""
        return self._root / "mcp-servers"

    # -- research directories --------------------------------------------------

    @property
    def research_dir(self) -> Path:
        """Root directory for research artifacts."""
        return self._root / "research"

    @property
    def research_notes(self) -> Path:
        """Directory for research note YAML files."""
        return self._root / "research" / "notes"

    @property
    def eval_criteria(self) -> Path:
        """Path to the evaluation criteria YAML file."""
        return self._root / "research" / "eval_criteria.yaml"

    @property
    def reviews_dir(self) -> Path:
        """Directory for review markdown files."""
        return self._root / "research" / "reviews"

    # -- eval directories ------------------------------------------------------

    @property
    def eval_dir(self) -> Path:
        """Root directory for evaluation artifacts."""
        return self._root / "eval"

    @property
    def eval_suite(self) -> Path:
        """Path to the evaluation test suite YAML file."""
        return self._root / "eval" / "eval_suite.yaml"

    @property
    def eval_results(self) -> Path:
        """Directory for evaluation result files."""
        return self._root / "eval" / "results"

    @property
    def eval_transcripts(self) -> Path:
        """Directory for evaluation transcript files."""
        return self._root / "eval" / "transcripts"

    # -- session directories ---------------------------------------------------

    @property
    def sessions_dir(self) -> Path:
        """Directory for runtime session state files."""
        return self._root / "sessions"

    @property
    def optimization_state(self) -> Path:
        """Path to the optimization state JSON file."""
        return self._root / "sessions" / "optimization-state.json"

    # -- directory creation ----------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create all standard directories if they do not already exist."""
        dirs = [
            self.agents_dir,
            self.skills_dir,
            self.commands_dir,
            self.tools_dir,
            self.mcp_servers_dir,
            self.research_dir,
            self.research_notes,
            self.reviews_dir,
            self.eval_dir,
            self.eval_results,
            self.eval_transcripts,
            self.sessions_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
