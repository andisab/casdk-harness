"""Tests for MCP resource generation — skills, templates, orchestrator support.

Covers:
- Skill existence and frontmatter validation
- Template existence and syntax validation
- Resource-type-guide MCP sections
- Context-engineer agent MCP references
- Orchestrator MCP type handling
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

# Base paths
PLUGIN_ROOT = Path("src/harness/plugins/context-engineering")
SKILLS_DIR = PLUGIN_ROOT / "skills"
TEMPLATES_DIR = PLUGIN_ROOT / "templates"
AGENT_PATH = PLUGIN_ROOT / "agents" / "context-engineer.md"
GUIDE_PATH = TEMPLATES_DIR / "resource-type-guide.md"


# ──────────────────────────────────────────────
# Content existence tests
# ──────────────────────────────────────────────


class TestMCPToolSkill:
    """Tests for mcp-tool-creation skill."""

    skill_dir = SKILLS_DIR / "mcp-tool-creation"

    def test_skill_exists(self) -> None:
        """SKILL.md exists at the expected path."""
        assert (self.skill_dir / "SKILL.md").is_file()

    def test_skill_has_valid_frontmatter(self) -> None:
        """SKILL.md has valid YAML frontmatter with required fields."""
        content = (self.skill_dir / "SKILL.md").read_text()
        # Extract frontmatter between --- markers
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md must have YAML frontmatter between --- markers"
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["name"] == "mcp-tool-creation"
        assert "description" in frontmatter
        # Description should be multi-line (pushy, detailed)
        assert len(frontmatter["description"]) > 100

    def test_skill_has_references(self) -> None:
        """references/tool-design-patterns.md exists."""
        assert (self.skill_dir / "references" / "tool-design-patterns.md").is_file()

    def test_skill_mentions_fastmcp(self) -> None:
        """SKILL.md references FastMCP as the primary pattern."""
        content = (self.skill_dir / "SKILL.md").read_text()
        assert "FastMCP" in content

    def test_skill_mentions_signal_protocol(self) -> None:
        """SKILL.md includes signal protocol for multi-resource pipeline."""
        content = (self.skill_dir / "SKILL.md").read_text()
        assert "GENERATE_COMPLETE" in content


class TestMCPServerSkill:
    """Tests for mcp-server-creation skill."""

    skill_dir = SKILLS_DIR / "mcp-server-creation"

    def test_skill_exists(self) -> None:
        """SKILL.md exists at the expected path."""
        assert (self.skill_dir / "SKILL.md").is_file()

    def test_skill_has_valid_frontmatter(self) -> None:
        """SKILL.md has valid YAML frontmatter with required fields."""
        content = (self.skill_dir / "SKILL.md").read_text()
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md must have YAML frontmatter between --- markers"
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["name"] == "mcp-server-creation"
        assert "description" in frontmatter
        assert len(frontmatter["description"]) > 100

    def test_skill_has_python_reference(self) -> None:
        """references/python-server-patterns.md exists."""
        assert (self.skill_dir / "references" / "python-server-patterns.md").is_file()

    def test_skill_has_typescript_reference(self) -> None:
        """references/typescript-server-patterns.md exists."""
        assert (self.skill_dir / "references" / "typescript-server-patterns.md").is_file()

    def test_skill_has_testing_reference(self) -> None:
        """references/server-testing-guide.md exists."""
        assert (self.skill_dir / "references" / "server-testing-guide.md").is_file()

    def test_skill_mentions_signal_protocol(self) -> None:
        """SKILL.md includes signal protocol."""
        content = (self.skill_dir / "SKILL.md").read_text()
        assert "GENERATE_COMPLETE" in content


# ──────────────────────────────────────────────
# Template validation
# ──────────────────────────────────────────────


class TestMCPToolTemplate:
    """Tests for mcp-tool-template.py."""

    template_path = TEMPLATES_DIR / "mcp-tool-template.py"

    def test_template_exists(self) -> None:
        """Template file exists."""
        assert self.template_path.is_file()

    def test_python_template_syntax(self) -> None:
        """Template is valid Python (ignoring placeholder names)."""
        content = self.template_path.read_text()
        # Replace placeholders so ast.parse can work
        sanitized = content.replace("{server-name}", "server_name")
        sanitized = sanitized.replace("{tool_name}", "tool_name")
        sanitized = sanitized.replace("{One-line summary of what this tool does.}", "Summary.")
        sanitized = sanitized.replace(
            "{2-3 sentences: when to use this tool, what it returns, and when NOT\n"
            "    to use it (suggest the alternative tool instead).}",
            "Details.",
        )
        sanitized = sanitized.replace(
            "{What this parameter means, expected format, constraints.}",
            "Parameter description.",
        )
        sanitized = sanitized.replace("{this_file}", "this_file")
        # Should parse without SyntaxError
        ast.parse(sanitized)


class TestMCPServerPythonTemplate:
    """Tests for mcp-server-python-template/."""

    template_dir = TEMPLATES_DIR / "mcp-server-python-template"

    def test_directory_exists(self) -> None:
        """Template directory exists."""
        assert self.template_dir.is_dir()

    def test_has_pyproject_toml(self) -> None:
        """pyproject.toml exists."""
        assert (self.template_dir / "pyproject.toml").is_file()

    def test_has_server_py(self) -> None:
        """server.py exists in src directory."""
        assert (self.template_dir / "src" / "server_name" / "server.py").is_file()

    def test_has_example_tool(self) -> None:
        """Example tool file exists."""
        assert (self.template_dir / "src" / "server_name" / "tools" / "example.py").is_file()

    def test_has_tests(self) -> None:
        """Test directory with test file exists."""
        assert (self.template_dir / "tests" / "test_tools.py").is_file()

    def test_has_readme(self) -> None:
        """README.md exists."""
        assert (self.template_dir / "README.md").is_file()


class TestMCPServerTypeScriptTemplate:
    """Tests for mcp-server-typescript-template/."""

    template_dir = TEMPLATES_DIR / "mcp-server-typescript-template"

    def test_directory_exists(self) -> None:
        """Template directory exists."""
        assert self.template_dir.is_dir()

    def test_has_package_json(self) -> None:
        """package.json exists."""
        assert (self.template_dir / "package.json").is_file()

    def test_package_json_valid(self) -> None:
        """package.json is valid JSON with required fields."""
        content = (self.template_dir / "package.json").read_text()
        pkg = json.loads(content)
        assert "bin" in pkg
        assert "type" in pkg
        assert pkg["type"] == "module"
        assert "@modelcontextprotocol/sdk" in pkg.get("dependencies", {})

    def test_has_tsconfig(self) -> None:
        """tsconfig.json exists."""
        assert (self.template_dir / "tsconfig.json").is_file()

    def test_has_index_ts(self) -> None:
        """Entry point exists."""
        assert (self.template_dir / "src" / "index.ts").is_file()

    def test_has_server_ts(self) -> None:
        """Server file exists."""
        assert (self.template_dir / "src" / "server.ts").is_file()

    def test_has_example_tool(self) -> None:
        """Example tool file exists."""
        assert (self.template_dir / "src" / "tools" / "example.ts").is_file()

    def test_has_tests(self) -> None:
        """Test file exists."""
        assert (self.template_dir / "tests" / "tools.test.ts").is_file()

    def test_has_readme(self) -> None:
        """README.md exists."""
        assert (self.template_dir / "README.md").is_file()


# ──────────────────────────────────────────────
# Resource-type-guide tests
# ──────────────────────────────────────────────


class TestResourceTypeGuide:
    """Tests for MCP sections in resource-type-guide.md."""

    @pytest.fixture(autouse=True)
    def _load_guide(self) -> None:
        self.content = GUIDE_PATH.read_text()

    def test_guide_contains_mcp_tool_section(self) -> None:
        """Guide has an MCP Tool section heading."""
        assert "## MCP Tool" in self.content

    def test_guide_contains_mcp_server_section(self) -> None:
        """Guide has an MCP Server section heading."""
        assert "## MCP Server" in self.content

    def test_guide_decision_matrix_has_mcp_entries(self) -> None:
        """Decision matrix includes MCP Tool and MCP Server rows."""
        assert "MCP Tool" in self.content
        assert "MCP Server" in self.content
        # Should be in the decision matrix table
        assert "Single utility function" in self.content
        assert "Multi-tool service" in self.content

    def test_guide_has_mcp_quality_checklists(self) -> None:
        """Guide has MCP Tool Quality and MCP Server Quality checklists."""
        assert "### MCP Tool Quality" in self.content
        assert "### MCP Server Quality" in self.content

    def test_guide_has_mcp_templates(self) -> None:
        """Guide references MCP templates."""
        assert "mcp-tool-template.py" in self.content
        assert "mcp-server-python-template" in self.content
        assert "mcp-server-typescript-template" in self.content


# ──────────────────────────────────────────────
# Context-engineer agent tests
# ──────────────────────────────────────────────


class TestContextEngineerAgent:
    """Tests for MCP references in context-engineer.md."""

    @pytest.fixture(autouse=True)
    def _load_agent(self) -> None:
        self.content = AGENT_PATH.read_text()

    def test_agent_references_mcp_tool_skill(self) -> None:
        """Agent lists mcp-tool-creation skill."""
        assert "mcp-tool-creation" in self.content

    def test_agent_references_mcp_server_skill(self) -> None:
        """Agent lists mcp-server-creation skill."""
        assert "mcp-server-creation" in self.content

    def test_agent_lists_mcp_component_types(self) -> None:
        """Agent lists MCP Tools and MCP Servers in component types."""
        assert "MCP Tools" in self.content
        assert "MCP Servers" in self.content

    def test_agent_lists_mcp_templates(self) -> None:
        """Agent references MCP templates."""
        assert "mcp-tool-template.py" in self.content
        assert "mcp-server-python-template" in self.content
        assert "mcp-server-typescript-template" in self.content

    def test_agent_has_mcp_signal_examples(self) -> None:
        """Agent includes MCP signal protocol examples."""
        assert "resource_type: mcp_tool" in self.content
        assert "resource_type: mcp_server" in self.content


# ──────────────────────────────────────────────
# Orchestrator tests
# ──────────────────────────────────────────────


class TestOrchestratorMCPSupport:
    """Tests for MCP type handling in multi_resource_orchestrator."""

    def _make_orchestrator(
        self,
        mcp_tools: list | None = None,
        mcp_servers: list | None = None,
    ):
        """Create an orchestrator with mock spec containing MCP resources."""
        from unittest.mock import MagicMock

        from harness.optimization.multi_resource_spec import (
            ProposedMCPServer,
            ProposedMCPTool,
        )

        spec = MagicMock()
        spec.proposed_agents = []
        spec.proposed_skills = []
        spec.proposed_commands = []
        spec.proposed_mcp_tools = [
            ProposedMCPTool(**t) for t in (mcp_tools or [])
        ]
        spec.proposed_mcp_servers = [
            ProposedMCPServer(**s) for s in (mcp_servers or [])
        ]
        spec.name = "test-plugin"
        spec.purpose = "Test plugin"
        spec.spec_type = MagicMock()
        spec.spec_type.name = "PLUGIN"
        spec.capabilities = []

        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceOrchestrator,
        )

        config = MagicMock()
        config.workspace_dir = Path("/tmp/test-workspace")
        orch = MultiResourceOrchestrator(config)
        orch._spec = spec
        return orch

    def test_get_resource_purpose_mcp_tool(self) -> None:
        """Returns purpose for mcp_tool type."""
        orch = self._make_orchestrator(
            mcp_tools=[{"name": "search", "purpose": "Full-text search"}],
        )
        purpose = orch._get_resource_purpose("search", "mcp_tool")
        assert purpose == "Full-text search"

    def test_get_resource_purpose_mcp_server(self) -> None:
        """Returns purpose for mcp_server type."""
        orch = self._make_orchestrator(
            mcp_servers=[{
                "name": "data-service",
                "purpose": "Data management tools",
                "language": "python",
                "tools": ["query", "insert"],
            }],
        )
        purpose = orch._get_resource_purpose("data-service", "mcp_server")
        assert purpose == "Data management tools"

    def test_get_resource_purpose_unknown_mcp_tool(self) -> None:
        """Returns empty string for unknown mcp_tool name."""
        orch = self._make_orchestrator(mcp_tools=[])
        purpose = orch._get_resource_purpose("nonexistent", "mcp_tool")
        assert purpose == ""

    def test_get_resource_instructions_mcp_tool(self) -> None:
        """Returns non-empty instructions for mcp_tool type."""
        orch = self._make_orchestrator(
            mcp_tools=[{"name": "search", "purpose": "Search"}],
        )
        instructions = orch._get_resource_instructions("search", "mcp_tool", "Search")
        assert instructions
        assert "mcp-tool-creation" in instructions
        assert "FastMCP" in instructions

    def test_get_resource_instructions_mcp_server(self) -> None:
        """Returns non-empty instructions for mcp_server type."""
        orch = self._make_orchestrator(
            mcp_servers=[{
                "name": "data-service",
                "purpose": "Data tools",
                "language": "python",
                "tools": ["query"],
            }],
        )
        instructions = orch._get_resource_instructions(
            "data-service", "mcp_server", "Data tools"
        )
        assert instructions
        assert "mcp-server-creation" in instructions
        assert "FastMCP" in instructions

    def test_get_resource_instructions_mcp_server_typescript(self) -> None:
        """Returns TypeScript-specific instructions for TS mcp_server."""
        orch = self._make_orchestrator(
            mcp_servers=[{
                "name": "web-tools",
                "purpose": "Web tools",
                "language": "typescript",
                "tools": ["fetch"],
            }],
        )
        instructions = orch._get_resource_instructions(
            "web-tools", "mcp_server", "Web tools"
        )
        assert "@modelcontextprotocol/sdk" in instructions

    def test_setup_dirs_creates_tools_when_mcp_tools(self, tmp_path: Path) -> None:
        """tools/ directory is created when spec has mcp_tools."""
        orch = self._make_orchestrator(
            mcp_tools=[{"name": "search", "purpose": "Search"}],
        )
        orch._setup_workspace_dirs(tmp_path)
        assert (tmp_path / "tools").is_dir()

    def test_setup_dirs_skips_tools_when_no_mcp_tools(self, tmp_path: Path) -> None:
        """tools/ directory is NOT created when spec has no mcp_tools."""
        orch = self._make_orchestrator()
        orch._setup_workspace_dirs(tmp_path)
        assert not (tmp_path / "tools").exists()

    def test_setup_dirs_creates_mcp_servers_when_servers(self, tmp_path: Path) -> None:
        """mcp-servers/ directory is created when spec has mcp_servers."""
        orch = self._make_orchestrator(
            mcp_servers=[{
                "name": "data-service",
                "purpose": "Data tools",
                "language": "python",
                "tools": ["query"],
            }],
        )
        orch._setup_workspace_dirs(tmp_path)
        assert (tmp_path / "mcp-servers").is_dir()

    def test_setup_dirs_skips_mcp_servers_when_no_servers(self, tmp_path: Path) -> None:
        """mcp-servers/ directory is NOT created when spec has no mcp_servers."""
        orch = self._make_orchestrator()
        orch._setup_workspace_dirs(tmp_path)
        assert not (tmp_path / "mcp-servers").exists()

    @pytest.mark.asyncio
    async def test_generate_plugin_json_includes_mcp_resources(
        self, tmp_path: Path
    ) -> None:
        """plugin.json includes mcp_tools and mcp_servers in components."""
        orch = self._make_orchestrator(
            mcp_tools=[{"name": "search", "purpose": "Search"}],
            mcp_servers=[{
                "name": "data-service",
                "purpose": "Data tools",
                "language": "python",
                "tools": ["query"],
            }],
        )
        orch.config.workspace_dir = tmp_path
        (tmp_path / ".claude-plugin").mkdir(parents=True, exist_ok=True)

        await orch._generate_plugin_json()

        plugin_path = tmp_path / ".claude-plugin" / "plugin.json"
        assert plugin_path.is_file()

        with open(plugin_path) as f:
            plugin_json = json.load(f)

        assert "mcp_tools" in plugin_json["components"]
        assert "mcp_servers" in plugin_json["components"]
        assert "search" in plugin_json["components"]["mcp_tools"]
        assert "data-service" in plugin_json["components"]["mcp_servers"]
