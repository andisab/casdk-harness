"""Unit tests for Memory MCP server."""

import tempfile
from pathlib import Path

import pytest

# Import the server module - use handler functions and class for testing
from mcp_servers.memory.server import (
    KnowledgeGraph,
    memory_server,
)
from mcp_servers.memory.server import (
    _add_observations_handler as add_observations,
)
from mcp_servers.memory.server import (
    _create_entities_handler as create_entities,
)
from mcp_servers.memory.server import (
    _create_relations_handler as create_relations,
)
from mcp_servers.memory.server import (
    _delete_entities_handler as delete_entities,
)
from mcp_servers.memory.server import (
    _delete_observations_handler as delete_observations,
)
from mcp_servers.memory.server import (
    _delete_relations_handler as delete_relations,
)
from mcp_servers.memory.server import (
    _open_nodes_handler as open_nodes,
)
from mcp_servers.memory.server import (
    _read_graph_handler as read_graph,
)
from mcp_servers.memory.server import (
    _search_nodes_handler as search_nodes,
)


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph class."""

    def test_create_empty_graph(self):
        """Test creating empty in-memory graph."""
        graph = KnowledgeGraph(storage_path=None)
        assert graph.entities == {}
        assert graph.relations == []

    def test_create_entities(self):
        """Test creating entities."""
        graph = KnowledgeGraph(storage_path=None)
        created = graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": ["Developer"]},
            {"name": "Bob", "entityType": "person", "observations": []},
        ])
        assert len(created) == 2
        assert "Alice" in graph.entities
        assert graph.entities["Alice"]["entityType"] == "person"
        assert "Developer" in graph.entities["Alice"]["observations"]

    def test_create_entities_skips_duplicates(self):
        """Test that duplicate entities are skipped."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([{"name": "Alice", "entityType": "person", "observations": []}])
        created = graph.create_entities([
            {"name": "Alice", "entityType": "different", "observations": []},
        ])
        assert len(created) == 0
        assert graph.entities["Alice"]["entityType"] == "person"  # Unchanged

    def test_create_relations(self):
        """Test creating relations."""
        graph = KnowledgeGraph(storage_path=None)
        created = graph.create_relations([
            {"from": "Alice", "to": "Bob", "relationType": "knows"},
        ])
        assert len(created) == 1
        assert graph.relations[0]["from"] == "Alice"
        assert graph.relations[0]["to"] == "Bob"
        assert graph.relations[0]["relationType"] == "knows"

    def test_create_relations_skips_duplicates(self):
        """Test that duplicate relations are skipped."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_relations([{"from": "A", "to": "B", "relationType": "knows"}])
        created = graph.create_relations([{"from": "A", "to": "B", "relationType": "knows"}])
        assert len(created) == 0
        assert len(graph.relations) == 1

    def test_add_observations(self):
        """Test adding observations to entities."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([{"name": "Alice", "entityType": "person", "observations": []}])
        added = graph.add_observations([
            {"entityName": "Alice", "contents": ["Likes Python", "Works at Anthropic"]},
        ])
        assert "Alice" in added
        assert len(added["Alice"]) == 2
        assert "Likes Python" in graph.entities["Alice"]["observations"]

    def test_add_observations_skips_missing_entity(self):
        """Test that observations for missing entities are skipped."""
        graph = KnowledgeGraph(storage_path=None)
        added = graph.add_observations([
            {"entityName": "NonExistent", "contents": ["Some fact"]},
        ])
        assert added == {}

    def test_delete_entities(self):
        """Test deleting entities."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": []},
            {"name": "Bob", "entityType": "person", "observations": []},
        ])
        deleted = graph.delete_entities(["Alice"])
        assert "Alice" in deleted
        assert "Alice" not in graph.entities
        assert "Bob" in graph.entities

    def test_delete_entities_cascades_relations(self):
        """Test that deleting entities removes associated relations."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": []},
            {"name": "Bob", "entityType": "person", "observations": []},
        ])
        graph.create_relations([
            {"from": "Alice", "to": "Bob", "relationType": "knows"},
        ])
        graph.delete_entities(["Alice"])
        assert len(graph.relations) == 0

    def test_delete_observations(self):
        """Test deleting observations."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": ["Fact1", "Fact2"]},
        ])
        deleted = graph.delete_observations([
            {"entityName": "Alice", "observations": ["Fact1"]},
        ])
        assert "Alice" in deleted
        assert "Fact1" not in graph.entities["Alice"]["observations"]
        assert "Fact2" in graph.entities["Alice"]["observations"]

    def test_delete_relations(self):
        """Test deleting relations."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_relations([
            {"from": "A", "to": "B", "relationType": "knows"},
            {"from": "A", "to": "C", "relationType": "knows"},
        ])
        deleted = graph.delete_relations([{"from": "A", "to": "B", "relationType": "knows"}])
        assert len(deleted) == 1
        assert len(graph.relations) == 1
        assert graph.relations[0]["to"] == "C"

    def test_read_graph(self):
        """Test reading entire graph."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([{"name": "Alice", "entityType": "person", "observations": []}])
        graph.create_relations([{"from": "Alice", "to": "Bob", "relationType": "knows"}])
        result = graph.read_graph()
        assert len(result["entities"]) == 1
        assert len(result["relations"]) == 1

    def test_search_nodes_by_name(self):
        """Test searching nodes by name."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice Smith", "entityType": "person", "observations": []},
            {"name": "Bob Jones", "entityType": "person", "observations": []},
        ])
        result = graph.search_nodes("alice")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Alice Smith"

    def test_search_nodes_by_type(self):
        """Test searching nodes by type."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "developer", "observations": []},
            {"name": "Bob", "entityType": "manager", "observations": []},
        ])
        result = graph.search_nodes("developer")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Alice"

    def test_search_nodes_by_observation(self):
        """Test searching nodes by observation content."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": ["Loves Python"]},
            {"name": "Bob", "entityType": "person", "observations": ["Loves JavaScript"]},
        ])
        result = graph.search_nodes("python")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Alice"

    def test_open_nodes(self):
        """Test opening specific nodes."""
        graph = KnowledgeGraph(storage_path=None)
        graph.create_entities([
            {"name": "Alice", "entityType": "person", "observations": []},
            {"name": "Bob", "entityType": "person", "observations": []},
            {"name": "Charlie", "entityType": "person", "observations": []},
        ])
        graph.create_relations([
            {"from": "Alice", "to": "Bob", "relationType": "knows"},
            {"from": "Bob", "to": "Charlie", "relationType": "knows"},
        ])
        result = graph.open_nodes(["Alice", "Bob"])
        assert len(result["entities"]) == 2
        assert len(result["relations"]) == 1  # Only Alice->Bob, not Bob->Charlie

    def test_persistence(self):
        """Test that graph persists to file."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            storage_path = Path(f.name)

        try:
            # Create and populate graph
            graph1 = KnowledgeGraph(storage_path=storage_path)
            graph1.create_entities([{"name": "Alice", "entityType": "person", "observations": ["Fact"]}])
            graph1.create_relations([{"from": "Alice", "to": "Bob", "relationType": "knows"}])

            # Load new graph from same file
            graph2 = KnowledgeGraph(storage_path=storage_path)
            assert "Alice" in graph2.entities
            assert graph2.entities["Alice"]["observations"] == ["Fact"]
            assert len(graph2.relations) == 1
        finally:
            storage_path.unlink(missing_ok=True)


class TestCreateEntitiesHandler:
    """Tests for create_entities tool handler."""

    @pytest.mark.asyncio
    async def test_missing_entities(self):
        """Test error when entities array is missing."""
        result = await create_entities({})
        assert "content" in result
        assert "Error: entities array is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_empty_entities(self):
        """Test with empty entities array."""
        result = await create_entities({"entities": []})
        assert "content" in result
        assert "No new entities created" in result["content"][0]["text"]


class TestCreateRelationsHandler:
    """Tests for create_relations tool handler."""

    @pytest.mark.asyncio
    async def test_missing_relations(self):
        """Test error when relations array is missing."""
        result = await create_relations({})
        assert "content" in result
        assert "Error: relations array is required" in result["content"][0]["text"]


class TestAddObservationsHandler:
    """Tests for add_observations tool handler."""

    @pytest.mark.asyncio
    async def test_missing_observations(self):
        """Test error when observations array is missing."""
        result = await add_observations({})
        assert "content" in result
        assert "Error: observations array is required" in result["content"][0]["text"]


class TestDeleteEntitiesHandler:
    """Tests for delete_entities tool handler."""

    @pytest.mark.asyncio
    async def test_missing_entity_names(self):
        """Test error when entityNames array is missing."""
        result = await delete_entities({})
        assert "content" in result
        assert "Error: entityNames array is required" in result["content"][0]["text"]


class TestDeleteObservationsHandler:
    """Tests for delete_observations tool handler."""

    @pytest.mark.asyncio
    async def test_missing_deletions(self):
        """Test error when deletions array is missing."""
        result = await delete_observations({})
        assert "content" in result
        assert "Error: deletions array is required" in result["content"][0]["text"]


class TestDeleteRelationsHandler:
    """Tests for delete_relations tool handler."""

    @pytest.mark.asyncio
    async def test_missing_relations(self):
        """Test error when relations array is missing."""
        result = await delete_relations({})
        assert "content" in result
        assert "Error: relations array is required" in result["content"][0]["text"]


class TestReadGraphHandler:
    """Tests for read_graph tool handler."""

    @pytest.mark.asyncio
    async def test_empty_graph(self):
        """Test reading empty graph."""
        # Note: This test uses the global graph, which may have state
        # In production, we'd want to mock the graph
        result = await read_graph({})
        assert "content" in result
        # Result could be "empty" or have content depending on global state


class TestSearchNodesHandler:
    """Tests for search_nodes tool handler."""

    @pytest.mark.asyncio
    async def test_missing_query(self):
        """Test error when query is missing."""
        result = await search_nodes({})
        assert "content" in result
        assert "Error: query is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Test error when query is empty."""
        result = await search_nodes({"query": "  "})
        assert "content" in result
        assert "Error: query is required" in result["content"][0]["text"]


class TestOpenNodesHandler:
    """Tests for open_nodes tool handler."""

    @pytest.mark.asyncio
    async def test_missing_names(self):
        """Test error when names array is missing."""
        result = await open_nodes({})
        assert "content" in result
        assert "Error: names array is required" in result["content"][0]["text"]


class TestMemoryServer:
    """Tests for Memory server creation."""

    def test_server_is_sdk_dict(self):
        """Test server is an SDK-compatible dict."""
        assert isinstance(memory_server, dict)
        assert memory_server["type"] == "sdk"

    def test_server_has_correct_name(self):
        """Test server has correct name."""
        assert memory_server["name"] == "memory"

    def test_server_has_instance(self):
        """Test server has MCP server instance."""
        assert "instance" in memory_server
        # Instance should be an MCP Server object
        from mcp.server.lowlevel.server import Server
        assert isinstance(memory_server["instance"], Server)
