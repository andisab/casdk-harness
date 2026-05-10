"""Tests for MCP resource handling in the multi-resource orchestrator.

Scope: only harness code lives here. The marketplace-content checks that
previously occupied this file (skill files, template directories,
resource-type guide and context-engineer agent contents) were deleted in
Block 3 Step 2 follow-up — those resources now live in the swe-marketplace
clone (`/opt/plugins/swe-marketplace` or `<repo>/.plugins/swe-marketplace`)
and are owned/tested by that repo, not this one. The harness validates the
clone at runtime via `claude plugin validate` and smoke tests, not unit
tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


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
        assert "mcp-tool-dev" in instructions
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
        assert "mcp-server-dev" in instructions
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
