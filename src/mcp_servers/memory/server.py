"""Memory MCP server for Claude Agent SDK.

Provides a knowledge graph-based persistent memory system through the Model Context Protocol.
Stores entities, observations, and relations in a local JSONL file.

Tools:
    - create_entities: Create new entities with type and observations
    - create_relations: Create relations between entities
    - add_observations: Add observations to existing entities
    - delete_entities: Remove entities and their relations
    - delete_observations: Remove specific observations from entities
    - delete_relations: Remove specific relations
    - read_graph: Get the entire knowledge graph
    - search_nodes: Search entities by name, type, or observation content
    - open_nodes: Get specific entities by name with their relations
"""

import json
import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


class KnowledgeGraph:
    """In-memory knowledge graph with JSONL persistence.

    Stores entities (nodes) and relations (edges) in a graph structure.
    Persists to JSONL file for durability across sessions.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize the knowledge graph.

        Args:
            storage_path: Path to JSONL storage file. If None, uses in-memory only.
        """
        self.storage_path = storage_path
        self.entities: dict[str, dict[str, Any]] = {}  # name -> {entityType, observations[]}
        self.relations: list[dict[str, str]] = []  # [{from, to, relationType}]

        if self.storage_path:
            self._load()

    def _load(self) -> None:
        """Load graph from JSONL file."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if record.get("type") == "entity":
                        self.entities[record["name"]] = {
                            "entityType": record["entityType"],
                            "observations": record.get("observations", []),
                        }
                    elif record.get("type") == "relation":
                        self.relations.append({
                            "from": record["from"],
                            "to": record["to"],
                            "relationType": record["relationType"],
                        })
        except (json.JSONDecodeError, KeyError) as e:
            # Log error but continue with empty graph
            print(f"Warning: Failed to load knowledge graph: {e}")

    def _save(self) -> None:
        """Save graph to JSONL file (full rewrite)."""
        if not self.storage_path:
            return

        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.storage_path, "w") as f:
            # Write entities
            for name, data in self.entities.items():
                record = {
                    "type": "entity",
                    "name": name,
                    "entityType": data["entityType"],
                    "observations": data["observations"],
                }
                f.write(json.dumps(record) + "\n")

            # Write relations
            for rel in self.relations:
                record = {
                    "type": "relation",
                    "from": rel["from"],
                    "to": rel["to"],
                    "relationType": rel["relationType"],
                }
                f.write(json.dumps(record) + "\n")

    def create_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create new entities. Skips duplicates (same name).

        Args:
            entities: List of {name, entityType, observations[]}

        Returns:
            List of created entities
        """
        created = []
        for entity in entities:
            name = entity.get("name", "").strip()
            if not name or name in self.entities:
                continue  # Skip duplicates

            self.entities[name] = {
                "entityType": entity.get("entityType", "unknown"),
                "observations": entity.get("observations", []),
            }
            created.append({
                "name": name,
                "entityType": self.entities[name]["entityType"],
                "observations": self.entities[name]["observations"],
            })

        if created:
            self._save()
        return created

    def create_relations(self, relations: list[dict[str, str]]) -> list[dict[str, str]]:
        """Create new relations. Skips duplicates.

        Args:
            relations: List of {from, to, relationType}

        Returns:
            List of created relations
        """
        created = []
        for rel in relations:
            from_entity = rel.get("from", "").strip()
            to_entity = rel.get("to", "").strip()
            rel_type = rel.get("relationType", "").strip()

            if not all([from_entity, to_entity, rel_type]):
                continue

            # Check for duplicate
            is_duplicate = any(
                r["from"] == from_entity and r["to"] == to_entity and r["relationType"] == rel_type
                for r in self.relations
            )
            if is_duplicate:
                continue

            new_rel = {"from": from_entity, "to": to_entity, "relationType": rel_type}
            self.relations.append(new_rel)
            created.append(new_rel)

        if created:
            self._save()
        return created

    def add_observations(
        self, observations: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Add observations to existing entities.

        Args:
            observations: List of {entityName, contents[]}

        Returns:
            Dict mapping entity names to added observations
        """
        added: dict[str, list[str]] = {}
        for obs in observations:
            entity_name = obs.get("entityName", "").strip()
            contents = obs.get("contents", [])

            if not entity_name or entity_name not in self.entities:
                continue

            # Add new observations (avoid duplicates)
            existing = set(self.entities[entity_name]["observations"])
            new_obs = [c for c in contents if c not in existing]

            if new_obs:
                self.entities[entity_name]["observations"].extend(new_obs)
                added[entity_name] = new_obs

        if added:
            self._save()
        return added

    def delete_entities(self, entity_names: list[str]) -> list[str]:
        """Delete entities and cascade to their relations.

        Args:
            entity_names: List of entity names to delete

        Returns:
            List of deleted entity names
        """
        deleted = []
        for name in entity_names:
            name = name.strip()
            if name in self.entities:
                del self.entities[name]
                deleted.append(name)

                # Cascade: remove relations involving this entity
                self.relations = [
                    r for r in self.relations
                    if r["from"] != name and r["to"] != name
                ]

        if deleted:
            self._save()
        return deleted

    def delete_observations(
        self, deletions: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Delete specific observations from entities.

        Args:
            deletions: List of {entityName, observations[]}

        Returns:
            Dict mapping entity names to deleted observations
        """
        deleted: dict[str, list[str]] = {}
        for deletion in deletions:
            entity_name = deletion.get("entityName", "").strip()
            obs_to_delete = set(deletion.get("observations", []))

            if not entity_name or entity_name not in self.entities:
                continue

            original = self.entities[entity_name]["observations"]
            remaining = [o for o in original if o not in obs_to_delete]
            removed = [o for o in original if o in obs_to_delete]

            if removed:
                self.entities[entity_name]["observations"] = remaining
                deleted[entity_name] = removed

        if deleted:
            self._save()
        return deleted

    def delete_relations(self, relations: list[dict[str, str]]) -> list[dict[str, str]]:
        """Delete specific relations.

        Args:
            relations: List of {from, to, relationType}

        Returns:
            List of deleted relations
        """
        deleted = []
        for rel in relations:
            from_entity = rel.get("from", "").strip()
            to_entity = rel.get("to", "").strip()
            rel_type = rel.get("relationType", "").strip()

            # Find and remove matching relation
            for i, r in enumerate(self.relations):
                if r["from"] == from_entity and r["to"] == to_entity and r["relationType"] == rel_type:
                    deleted.append(self.relations.pop(i))
                    break

        if deleted:
            self._save()
        return deleted

    def read_graph(self) -> dict[str, Any]:
        """Get the entire knowledge graph.

        Returns:
            Dict with 'entities' and 'relations' keys
        """
        entities_list = [
            {
                "name": name,
                "entityType": data["entityType"],
                "observations": data["observations"],
            }
            for name, data in self.entities.items()
        ]
        return {
            "entities": entities_list,
            "relations": self.relations.copy(),
        }

    def search_nodes(self, query: str) -> dict[str, Any]:
        """Search entities by name, type, or observation content.

        Args:
            query: Search string (case-insensitive)

        Returns:
            Dict with matching 'entities' and their interconnecting 'relations'
        """
        query_lower = query.lower()
        matching_names = set()

        for name, data in self.entities.items():
            # Match name
            if query_lower in name.lower():
                matching_names.add(name)
                continue

            # Match entity type
            if query_lower in data["entityType"].lower():
                matching_names.add(name)
                continue

            # Match observations
            for obs in data["observations"]:
                if query_lower in obs.lower():
                    matching_names.add(name)
                    break

        # Get entities
        entities_list = [
            {
                "name": name,
                "entityType": self.entities[name]["entityType"],
                "observations": self.entities[name]["observations"],
            }
            for name in matching_names
        ]

        # Get relations between matching entities
        relations_list = [
            r for r in self.relations
            if r["from"] in matching_names and r["to"] in matching_names
        ]

        return {
            "entities": entities_list,
            "relations": relations_list,
        }

    def open_nodes(self, names: list[str]) -> dict[str, Any]:
        """Get specific entities by name with their relations.

        Args:
            names: List of entity names to retrieve

        Returns:
            Dict with requested 'entities' and their interconnecting 'relations'
        """
        found_names = set()
        entities_list = []

        for name in names:
            name = name.strip()
            if name in self.entities:
                found_names.add(name)
                entities_list.append({
                    "name": name,
                    "entityType": self.entities[name]["entityType"],
                    "observations": self.entities[name]["observations"],
                })

        # Get relations between found entities
        relations_list = [
            r for r in self.relations
            if r["from"] in found_names and r["to"] in found_names
        ]

        return {
            "entities": entities_list,
            "relations": relations_list,
        }


# Initialize singleton graph with persistent storage
# Use environment variable or default path
_storage_path = Path(os.getenv("MEMORY_STORAGE_PATH", "/memory/knowledge_graph.jsonl"))
_graph = KnowledgeGraph(_storage_path)


# --- Raw Handler Functions (for testing) ---

async def _create_entities_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Create new entities in the knowledge graph."""
    if "entities" not in args:
        return {
            "content": [{"type": "text", "text": "Error: entities array is required"}]
        }
    entities = args["entities"]

    try:
        created = _graph.create_entities(entities)
        if not created:
            return {
                "content": [{"type": "text", "text": "No new entities created (all duplicates or invalid)"}]
            }

        result = f"Created {len(created)} entities:\n"
        for e in created:
            result += f"  - {e['name']} ({e['entityType']})\n"
        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error creating entities: {e}"}]}


async def _create_relations_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Create new relations between entities."""
    relations = args.get("relations", [])
    if not relations:
        return {
            "content": [{"type": "text", "text": "Error: relations array is required"}]
        }

    try:
        created = _graph.create_relations(relations)
        if not created:
            return {
                "content": [{"type": "text", "text": "No new relations created (all duplicates or invalid)"}]
            }

        result = f"Created {len(created)} relations:\n"
        for r in created:
            result += f"  - {r['from']} --[{r['relationType']}]--> {r['to']}\n"
        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error creating relations: {e}"}]}


async def _add_observations_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Add observations to existing entities."""
    observations = args.get("observations", [])
    if not observations:
        return {
            "content": [{"type": "text", "text": "Error: observations array is required"}]
        }

    try:
        added = _graph.add_observations(observations)
        if not added:
            return {
                "content": [{"type": "text", "text": "No observations added (entities not found or duplicates)"}]
            }

        result = "Added observations:\n"
        for entity_name, obs_list in added.items():
            result += f"  {entity_name}:\n"
            for obs in obs_list:
                result += f"    - {obs}\n"
        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error adding observations: {e}"}]}


async def _delete_entities_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Delete entities and their relations."""
    entity_names = args.get("entityNames", [])
    if not entity_names:
        return {
            "content": [{"type": "text", "text": "Error: entityNames array is required"}]
        }

    try:
        deleted = _graph.delete_entities(entity_names)
        if not deleted:
            return {
                "content": [{"type": "text", "text": "No entities deleted (not found)"}]
            }

        result = f"Deleted {len(deleted)} entities: {', '.join(deleted)}"
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error deleting entities: {e}"}]}


async def _delete_observations_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Delete specific observations from entities."""
    deletions = args.get("deletions", [])
    if not deletions:
        return {
            "content": [{"type": "text", "text": "Error: deletions array is required"}]
        }

    try:
        deleted = _graph.delete_observations(deletions)
        if not deleted:
            return {
                "content": [{"type": "text", "text": "No observations deleted (not found)"}]
            }

        result = "Deleted observations:\n"
        for entity_name, obs_list in deleted.items():
            result += f"  {entity_name}: {len(obs_list)} observations\n"
        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error deleting observations: {e}"}]}


async def _delete_relations_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Delete specific relations."""
    relations = args.get("relations", [])
    if not relations:
        return {
            "content": [{"type": "text", "text": "Error: relations array is required"}]
        }

    try:
        deleted = _graph.delete_relations(relations)
        if not deleted:
            return {
                "content": [{"type": "text", "text": "No relations deleted (not found)"}]
            }

        result = f"Deleted {len(deleted)} relations:\n"
        for r in deleted:
            result += f"  - {r['from']} --[{r['relationType']}]--> {r['to']}\n"
        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error deleting relations: {e}"}]}


async def _read_graph_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Get the entire knowledge graph."""
    try:
        graph = _graph.read_graph()

        if not graph["entities"] and not graph["relations"]:
            return {"content": [{"type": "text", "text": "Knowledge graph is empty"}]}

        result = f"Knowledge Graph ({len(graph['entities'])} entities, {len(graph['relations'])} relations):\n\n"

        if graph["entities"]:
            result += "Entities:\n"
            for e in graph["entities"]:
                result += f"  [{e['entityType']}] {e['name']}\n"
                for obs in e["observations"]:
                    result += f"    - {obs}\n"

        if graph["relations"]:
            result += "\nRelations:\n"
            for r in graph["relations"]:
                result += f"  {r['from']} --[{r['relationType']}]--> {r['to']}\n"

        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error reading graph: {e}"}]}


async def _search_nodes_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Search entities by name, type, or observation content."""
    query = args.get("query", "").strip()
    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query is required"}]
        }

    try:
        results = _graph.search_nodes(query)

        if not results["entities"]:
            return {"content": [{"type": "text", "text": f"No entities found matching '{query}'"}]}

        result = f"Search results for '{query}' ({len(results['entities'])} entities):\n\n"

        for e in results["entities"]:
            result += f"  [{e['entityType']}] {e['name']}\n"
            for obs in e["observations"]:
                result += f"    - {obs}\n"

        if results["relations"]:
            result += "\nRelations between results:\n"
            for r in results["relations"]:
                result += f"  {r['from']} --[{r['relationType']}]--> {r['to']}\n"

        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error searching: {e}"}]}


async def _open_nodes_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Get specific entities by name."""
    names = args.get("names", [])
    if not names:
        return {
            "content": [{"type": "text", "text": "Error: names array is required"}]
        }

    try:
        results = _graph.open_nodes(names)

        if not results["entities"]:
            return {"content": [{"type": "text", "text": f"No entities found with names: {', '.join(names)}"}]}

        result = f"Retrieved {len(results['entities'])} entities:\n\n"

        for e in results["entities"]:
            result += f"  [{e['entityType']}] {e['name']}\n"
            for obs in e["observations"]:
                result += f"    - {obs}\n"

        if results["relations"]:
            result += "\nRelations:\n"
            for r in results["relations"]:
                result += f"  {r['from']} --[{r['relationType']}]--> {r['to']}\n"

        return {"content": [{"type": "text", "text": result.strip()}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error opening nodes: {e}"}]}


# --- @tool Decorated Wrappers ---

@tool(
    "create_entities",
    "Create new entities in the knowledge graph",
    {"entities": list},
)
async def create_entities(args: dict[str, Any]) -> dict[str, Any]:
    """Create entities with name, entityType, and observations."""
    return await _create_entities_handler(args)


@tool(
    "create_relations",
    "Create relations between entities (in active voice)",
    {"relations": list},
)
async def create_relations(args: dict[str, Any]) -> dict[str, Any]:
    """Create relations with from, to, and relationType."""
    return await _create_relations_handler(args)


@tool(
    "add_observations",
    "Add observations to existing entities",
    {"observations": list},
)
async def add_observations(args: dict[str, Any]) -> dict[str, Any]:
    """Add observations to entities by entityName."""
    return await _add_observations_handler(args)


@tool(
    "delete_entities",
    "Delete entities and their associated relations",
    {"entityNames": list},
)
async def delete_entities(args: dict[str, Any]) -> dict[str, Any]:
    """Delete entities by name (cascades to relations)."""
    return await _delete_entities_handler(args)


@tool(
    "delete_observations",
    "Delete specific observations from entities",
    {"deletions": list},
)
async def delete_observations(args: dict[str, Any]) -> dict[str, Any]:
    """Delete observations from entities."""
    return await _delete_observations_handler(args)


@tool(
    "delete_relations",
    "Delete specific relations between entities",
    {"relations": list},
)
async def delete_relations(args: dict[str, Any]) -> dict[str, Any]:
    """Delete relations by from, to, and relationType."""
    return await _delete_relations_handler(args)


@tool(
    "read_graph",
    "Read the entire knowledge graph",
    {},
)
async def read_graph(args: dict[str, Any]) -> dict[str, Any]:
    """Get all entities and relations."""
    return await _read_graph_handler(args)


@tool(
    "search_nodes",
    "Search for entities by name, type, or observation content",
    {"query": str},
)
async def search_nodes(args: dict[str, Any]) -> dict[str, Any]:
    """Search entities with a query string."""
    return await _search_nodes_handler(args)


@tool(
    "open_nodes",
    "Open specific entities by name",
    {"names": list},
)
async def open_nodes(args: dict[str, Any]) -> dict[str, Any]:
    """Retrieve specific entities and their relations."""
    return await _open_nodes_handler(args)


# --- Create and Export MCP Server ---

memory_server = create_sdk_mcp_server(
    name="memory",
    version="1.0.0",
    tools=[
        create_entities,
        create_relations,
        add_observations,
        delete_entities,
        delete_observations,
        delete_relations,
        read_graph,
        search_nodes,
        open_nodes,
    ],
)
