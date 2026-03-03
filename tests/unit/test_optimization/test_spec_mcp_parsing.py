"""Unit tests for MCP tool and server parsing in multi_resource_spec."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from harness.optimization.multi_resource_spec import (
    MultiResourceSpec,
    ProposedMCPServer,
    ProposedMCPTool,
    SpecType,
    _parse_proposed_mcp_servers,
    _parse_proposed_mcp_tools,
    parse_multi_resource_spec,
)


class TestProposedMCPTool:
    """Tests for ProposedMCPTool dataclass."""

    def test_creation_defaults(self) -> None:
        """Test creating a tool with default language."""
        tool = ProposedMCPTool(name="search", purpose="Full-text search")
        assert tool.name == "search"
        assert tool.purpose == "Full-text search"
        assert tool.language == "python"

    def test_creation_custom_language(self) -> None:
        """Test creating a tool with custom language."""
        tool = ProposedMCPTool(name="fetch", purpose="HTTP requests", language="typescript")
        assert tool.language == "typescript"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        tool = ProposedMCPTool(name="search", purpose="Full-text search", language="python")
        result = tool.to_dict()
        assert result == {"name": "search", "purpose": "Full-text search", "language": "python"}

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {"name": "search", "purpose": "Full-text search", "language": "typescript"}
        tool = ProposedMCPTool.from_dict(data)
        assert tool.name == "search"
        assert tool.purpose == "Full-text search"
        assert tool.language == "typescript"

    def test_from_dict_default_language(self) -> None:
        """Test deserialization without language uses default."""
        data = {"name": "search", "purpose": "Full-text search"}
        tool = ProposedMCPTool.from_dict(data)
        assert tool.language == "python"

    def test_roundtrip(self) -> None:
        """Test to_dict/from_dict roundtrip."""
        original = ProposedMCPTool(name="fetch", purpose="HTTP requests", language="go")
        restored = ProposedMCPTool.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.purpose == original.purpose
        assert restored.language == original.language


class TestProposedMCPServer:
    """Tests for ProposedMCPServer dataclass."""

    def test_creation_defaults(self) -> None:
        """Test creating a server with defaults."""
        server = ProposedMCPServer(name="memory-server", purpose="Knowledge graph persistence")
        assert server.name == "memory-server"
        assert server.purpose == "Knowledge graph persistence"
        assert server.language == "python"
        assert server.tools == []

    def test_creation_with_tools(self) -> None:
        """Test creating a server with tools list."""
        server = ProposedMCPServer(
            name="docker-server",
            purpose="Container management",
            tools=["list_containers", "run_container", "stop_container"],
        )
        assert len(server.tools) == 3
        assert "list_containers" in server.tools

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        server = ProposedMCPServer(
            name="docker-server",
            purpose="Container management",
            language="python",
            tools=["list_containers"],
        )
        result = server.to_dict()
        assert result == {
            "name": "docker-server",
            "purpose": "Container management",
            "language": "python",
            "tools": ["list_containers"],
        }

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "name": "docker-server",
            "purpose": "Container management",
            "language": "typescript",
            "tools": ["list_containers", "run_container"],
        }
        server = ProposedMCPServer.from_dict(data)
        assert server.name == "docker-server"
        assert server.language == "typescript"
        assert len(server.tools) == 2

    def test_from_dict_defaults(self) -> None:
        """Test deserialization without optional fields uses defaults."""
        data = {"name": "memory-server", "purpose": "Knowledge graph"}
        server = ProposedMCPServer.from_dict(data)
        assert server.language == "python"
        assert server.tools == []

    def test_roundtrip(self) -> None:
        """Test to_dict/from_dict roundtrip."""
        original = ProposedMCPServer(
            name="search-server",
            purpose="Search index",
            language="go",
            tools=["index", "query"],
        )
        restored = ProposedMCPServer.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.purpose == original.purpose
        assert restored.language == original.language
        assert restored.tools == original.tools


class TestParseMCPTools:
    """Tests for _parse_proposed_mcp_tools."""

    def test_parse_bullet_items(self) -> None:
        """Test parsing bold-name bullet items."""
        content = dedent("""\
            - **search** - Full-text search across documents
            - **fetch** - HTTP request handling
        """)
        tools = _parse_proposed_mcp_tools(content)
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[0].purpose == "Full-text search across documents"
        assert tools[1].name == "fetch"

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content returns empty list."""
        tools = _parse_proposed_mcp_tools("")
        assert tools == []

    def test_parse_no_matching_items(self) -> None:
        """Test parsing content without tool items."""
        content = "Some text without any tool definitions."
        tools = _parse_proposed_mcp_tools(content)
        assert tools == []

    def test_parse_with_language_sub_item(self) -> None:
        """Test parsing tools with language sub-items."""
        content = dedent("""\
            - **search** - Full-text search
              - language: typescript
            - **fetch** - HTTP requests
        """)
        tools = _parse_proposed_mcp_tools(content)
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[0].language == "typescript"
        assert tools[1].name == "fetch"
        assert tools[1].language == "python"  # default

    def test_parse_with_asterisk_markers(self) -> None:
        """Test parsing with * list markers."""
        content = dedent("""\
            * **search** - Full-text search
            * **fetch** - HTTP requests
        """)
        tools = _parse_proposed_mcp_tools(content)
        assert len(tools) == 2

    def test_parse_with_en_dash(self) -> None:
        """Test parsing with en-dash separator."""
        content = "- **search** \u2013 Full-text search across documents\n"
        tools = _parse_proposed_mcp_tools(content)
        assert len(tools) == 1
        assert tools[0].purpose == "Full-text search across documents"


class TestParseMCPServers:
    """Tests for _parse_proposed_mcp_servers."""

    def test_parse_bullet_items(self) -> None:
        """Test parsing bold-name bullet items."""
        content = dedent("""\
            - **memory-server** - Knowledge graph persistence
            - **docker-server** - Container management
        """)
        servers = _parse_proposed_mcp_servers(content)
        assert len(servers) == 2
        assert servers[0].name == "memory-server"
        assert servers[0].purpose == "Knowledge graph persistence"

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content returns empty list."""
        servers = _parse_proposed_mcp_servers("")
        assert servers == []

    def test_parse_with_language_sub_item(self) -> None:
        """Test parsing servers with language sub-item."""
        content = dedent("""\
            - **memory-server** - Knowledge graph persistence
              - language: typescript
            - **docker-server** - Container management
        """)
        servers = _parse_proposed_mcp_servers(content)
        assert len(servers) == 2
        assert servers[0].language == "typescript"
        assert servers[1].language == "python"  # default

    def test_parse_with_tools_sub_item(self) -> None:
        """Test parsing servers with tools sub-item."""
        content = dedent("""\
            - **docker-server** - Container management
              - tools: list_containers, run_container, stop_container
        """)
        servers = _parse_proposed_mcp_servers(content)
        assert len(servers) == 1
        assert servers[0].tools == ["list_containers", "run_container", "stop_container"]

    def test_parse_with_all_sub_items(self) -> None:
        """Test parsing servers with both language and tools sub-items."""
        content = dedent("""\
            - **search-server** - Full-text search index
              - language: go
              - tools: index, query, delete
        """)
        servers = _parse_proposed_mcp_servers(content)
        assert len(servers) == 1
        assert servers[0].name == "search-server"
        assert servers[0].language == "go"
        assert servers[0].tools == ["index", "query", "delete"]


class TestMultiResourceSpecMCPFields:
    """Tests for MCP fields on MultiResourceSpec."""

    def test_default_empty_mcp_lists(self) -> None:
        """Test that MCP fields default to empty lists."""
        spec = MultiResourceSpec(name="test", spec_type=SpecType.PLUGIN, purpose="test")
        assert spec.proposed_mcp_tools == []
        assert spec.proposed_mcp_servers == []

    def test_total_proposed_resources_includes_mcp(self) -> None:
        """Test that total_proposed_resources counts MCP tools and servers."""
        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_agents=[],
            proposed_skills=[],
            proposed_commands=[],
            proposed_mcp_tools=[
                ProposedMCPTool(name="search", purpose="Search"),
                ProposedMCPTool(name="fetch", purpose="Fetch"),
            ],
            proposed_mcp_servers=[
                ProposedMCPServer(name="memory", purpose="Memory"),
            ],
        )
        assert spec.total_proposed_resources == 3

    def test_total_proposed_resources_mixed(self) -> None:
        """Test total_proposed_resources with all resource types."""
        from harness.optimization.multi_resource_spec import ProposedAgent, ProposedSkill

        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_agents=[ProposedAgent(name="a", purpose="agent")],
            proposed_skills=[ProposedSkill(name="s", purpose="skill")],
            proposed_commands=[],
            proposed_mcp_tools=[ProposedMCPTool(name="t", purpose="tool")],
            proposed_mcp_servers=[ProposedMCPServer(name="sv", purpose="server")],
        )
        assert spec.total_proposed_resources == 4

    def test_has_proposed_structure_with_mcp_tools(self) -> None:
        """Test has_proposed_structure is True when only MCP tools exist."""
        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_mcp_tools=[ProposedMCPTool(name="search", purpose="Search")],
        )
        assert spec.has_proposed_structure is True

    def test_has_proposed_structure_with_mcp_servers(self) -> None:
        """Test has_proposed_structure is True when only MCP servers exist."""
        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_mcp_servers=[ProposedMCPServer(name="memory", purpose="Memory")],
        )
        assert spec.has_proposed_structure is True

    def test_to_dict_includes_mcp(self) -> None:
        """Test to_dict includes MCP tool and server fields."""
        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_mcp_tools=[
                ProposedMCPTool(name="search", purpose="Search", language="go"),
            ],
            proposed_mcp_servers=[
                ProposedMCPServer(
                    name="memory",
                    purpose="Memory",
                    language="typescript",
                    tools=["save", "load"],
                ),
            ],
        )
        d = spec.to_dict()
        assert "proposed_mcp_tools" in d
        assert len(d["proposed_mcp_tools"]) == 1
        assert d["proposed_mcp_tools"][0]["name"] == "search"
        assert d["proposed_mcp_tools"][0]["language"] == "go"
        assert "proposed_mcp_servers" in d
        assert len(d["proposed_mcp_servers"]) == 1
        assert d["proposed_mcp_servers"][0]["tools"] == ["save", "load"]

    def test_from_dict_includes_mcp(self) -> None:
        """Test from_dict reconstructs MCP fields."""
        spec = MultiResourceSpec(
            name="test",
            spec_type=SpecType.PLUGIN,
            purpose="test",
            proposed_mcp_tools=[
                ProposedMCPTool(name="search", purpose="Search"),
            ],
            proposed_mcp_servers=[
                ProposedMCPServer(name="memory", purpose="Memory", tools=["save"]),
            ],
        )
        restored = MultiResourceSpec.from_dict(spec.to_dict())
        assert len(restored.proposed_mcp_tools) == 1
        assert restored.proposed_mcp_tools[0].name == "search"
        assert len(restored.proposed_mcp_servers) == 1
        assert restored.proposed_mcp_servers[0].name == "memory"
        assert restored.proposed_mcp_servers[0].tools == ["save"]

    def test_from_dict_missing_mcp_defaults_empty(self) -> None:
        """Test from_dict without MCP fields defaults to empty lists."""
        data = {
            "name": "test",
            "spec_type": "PLUGIN",
            "purpose": "test",
            "parsed_at": "2026-01-01T00:00:00+00:00",
        }
        spec = MultiResourceSpec.from_dict(data)
        assert spec.proposed_mcp_tools == []
        assert spec.proposed_mcp_servers == []


class TestParseFullSpecWithMCP:
    """Tests for parsing full SPEC.md files containing MCP sections."""

    def test_spec_with_mcp_tools_section(self, tmp_path: Path) -> None:
        """Test parsing a SPEC.md with ### MCP Tools section."""
        spec_content = dedent("""\
            # Multi-Resource Spec: Test Plugin

            ## Purpose
            A test plugin for MCP tools.

            ## Capabilities
            ### Core
            - Search functionality
            - HTTP fetching

            ## Proposed Structure

            ### MCP Tools
            - **search** - Full-text search across documents
            - **fetch** - HTTP request handling

            ### Agents
            - **test-agent** - Runs tests
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_mcp_tools) == 2
        assert spec.proposed_mcp_tools[0].name == "search"
        assert spec.proposed_mcp_tools[1].name == "fetch"
        assert len(spec.proposed_agents) == 1

    def test_spec_with_mcp_servers_section(self, tmp_path: Path) -> None:
        """Test parsing a SPEC.md with ### MCP Servers section."""
        spec_content = dedent("""\
            # Multi-Resource Spec: Server Plugin

            ## Purpose
            A test plugin for MCP servers.

            ## Capabilities
            ### Core
            - Memory management

            ## Proposed Structure

            ### MCP Servers
            - **memory-server** - Knowledge graph persistence
              - language: typescript
              - tools: save_entity, load_entity, search
            - **docker-server** - Container management
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_mcp_servers) == 2
        assert spec.proposed_mcp_servers[0].name == "memory-server"
        assert spec.proposed_mcp_servers[0].language == "typescript"
        assert spec.proposed_mcp_servers[0].tools == ["save_entity", "load_entity", "search"]
        assert spec.proposed_mcp_servers[1].name == "docker-server"
        assert spec.proposed_mcp_servers[1].language == "python"  # default

    def test_spec_with_all_resource_types(self, tmp_path: Path) -> None:
        """Test parsing a SPEC.md with agents, skills, commands, MCP tools, and MCP servers."""
        spec_content = dedent("""\
            # Multi-Resource Spec: Full Plugin

            ## Purpose
            A complete plugin with all resource types.

            ## Capabilities
            ### Core
            - Everything

            ## Proposed Structure

            ### Agents
            - **analyzer** - Analyzes code

            ### Skills
            - **linting** - Code linting skill

            ### Commands
            - **/analyze** - Run code analysis

            ### MCP Tools
            - **search** - Search tool

            ### MCP Servers
            - **memory-server** - Persistence layer
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_agents) == 1
        assert len(spec.proposed_skills) == 1
        assert len(spec.proposed_commands) == 1
        assert len(spec.proposed_mcp_tools) == 1
        assert len(spec.proposed_mcp_servers) == 1
        assert spec.total_proposed_resources == 5

    def test_spec_without_mcp_sections_backward_compat(self, tmp_path: Path) -> None:
        """Test that specs without MCP sections still parse correctly."""
        spec_content = dedent("""\
            # Multi-Resource Spec: Legacy Plugin

            ## Purpose
            A plugin without MCP sections.

            ## Capabilities
            ### Core
            - Basic functionality

            ## Proposed Structure

            ### Agents
            - **test-agent** - Runs tests

            ### Skills
            - **testing** - Testing skill
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert len(spec.proposed_agents) == 1
        assert len(spec.proposed_skills) == 1
        assert spec.proposed_mcp_tools == []
        assert spec.proposed_mcp_servers == []
        assert spec.total_proposed_resources == 2

    def test_spec_with_only_mcp_resources(self, tmp_path: Path) -> None:
        """Test a SPEC.md that only has MCP tools and servers, no agents/skills."""
        spec_content = dedent("""\
            # Multi-Resource Spec: MCP Only Plugin

            ## Purpose
            A plugin providing only MCP resources.

            ## Capabilities
            ### Core
            - Provide MCP tools and servers

            ## Proposed Structure

            ### MCP Tools
            - **search** - Full-text search
            - **fetch** - HTTP requests
            - **validate** - Data validation

            ### MCP Servers
            - **cache-server** - Caching layer
        """)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(spec_content)

        spec = parse_multi_resource_spec(spec_file)
        assert spec.proposed_agents == []
        assert spec.proposed_skills == []
        assert spec.proposed_commands == []
        assert len(spec.proposed_mcp_tools) == 3
        assert len(spec.proposed_mcp_servers) == 1
        assert spec.total_proposed_resources == 4
        assert spec.has_proposed_structure is True
