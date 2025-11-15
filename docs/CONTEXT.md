# Claude Resources Loading - Hybrid Implementation Plan

**Created**: November 14, 2025
**Status**: Planning Phase
**Approach**: Hybrid - Static startup loading + Dynamic MCP for knowledge

## Architecture Overview

This document outlines the implementation plan for loading `.claude/` resources using a hybrid approach:
- **Static resources** loaded at startup for core SDK functionality
- **Dynamic resources** accessed via MCP for flexible knowledge retrieval

### Resource Classification

```
STATIC (Startup-time Loading)          DYNAMIC (MCP Runtime Loading)
├── Agents (44 definitions)             ├── Patterns (architectural)
├── Hooks (action logging)              ├── Templates (scaffolds)
├── Settings (permissions)              ├── Workflows (orchestrations)
└── CLAUDE.md (runtime context)         ├── Specs (standards, schemas)
                                        └── Skills metadata (references)
```

## Architecture Constraints

### Key SDK Limitation
- `ClaudeAgentOptions` is created once at startup (`src/harness/agent.py:207-214`)
- Options are immutable after SDK client creation
- Agents must be registered at startup for Task delegation to work
- Runtime discovery can only provide knowledge, not register new agents

### Current State
```python
# src/harness/agent.py - Line 207-214 (BEFORE - no agents registered)
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch"],
    permission_mode=self.config.claude_permission_mode,
    max_turns=self.config.claude_max_turns,
    cwd=str(self.config.workspace_dir),
    model=self.config.claude_model,
    mcp_servers=self.mcp_servers,
    # Missing: agents parameter - agents not discoverable for delegation
)
```

## Phase 1: Static Content Loading (Local Code)

### 1.1 Create Static Resource Loader
**File**: `src/harness/static_resource_loader.py`

```python
from pathlib import Path
from typing import Dict, List, Any
import json
import yaml
import logging

logger = logging.getLogger(__name__)

class StaticResourceLoader:
    """
    Load static .claude resources at startup.
    Handles: agents, hooks, settings, CLAUDE.md
    """

    def __init__(self, claude_dir: Path = Path("/app/.claude")):
        self.claude_dir = claude_dir
        self._agents_cache = {}

    def load_agents_for_sdk(self) -> Dict[str, Dict]:
        """
        Load all agents from .claude/agents/ for SDK registration.

        Returns:
            Dict suitable for ClaudeAgentOptions.agents parameter:
            {
                "dev-python-expert": {
                    "description": "Python development specialist",
                    "tools": ["Read", "Write", "Task"],
                    "model": "opus"
                },
                ...
            }
        """
        agents = {}
        agents_dir = self.claude_dir / "agents"

        if not agents_dir.exists():
            logger.warning(f"Agents directory not found: {agents_dir}")
            return agents

        for agent_file in agents_dir.glob("*.md"):
            try:
                metadata = self._parse_frontmatter(agent_file)
                agent_name = agent_file.stem  # e.g., "dev-python-expert"

                agents[agent_name] = {
                    "description": metadata.get("description", ""),
                    "tools": self._parse_tools(metadata.get("tools", "")),
                    "model": metadata.get("model", "sonnet")
                }

                # Cache full content for potential later use
                self._agents_cache[agent_name] = agent_file.read_text()

            except Exception as e:
                logger.warning(f"Failed to load agent {agent_file}: {e}")

        logger.info(f"Loaded {len(agents)} agents for SDK registration")
        return agents

    def load_hooks_config(self) -> Dict:
        """
        Load hooks.json configuration for action logging.

        Returns:
            Dict with hook configuration or empty dict if not found
        """
        hooks_file = self.claude_dir / "hooks" / "hooks.json"

        if not hooks_file.exists():
            logger.info("No hooks.json found")
            return {}

        try:
            hooks = json.loads(hooks_file.read_text())
            logger.info(f"Loaded {len(hooks.get('hooks', {}))} hook configurations")
            return hooks
        except Exception as e:
            logger.error(f"Failed to load hooks.json: {e}")
            return {}

    def load_settings(self) -> Dict:
        """
        Load settings.json with local overrides merged.

        Returns:
            Merged settings dictionary
        """
        settings = {}
        settings_file = self.claude_dir / "settings.json"

        # Load base settings
        if settings_file.exists():
            try:
                settings = json.loads(settings_file.read_text())
                logger.info("Loaded base settings.json")
            except Exception as e:
                logger.error(f"Failed to load settings.json: {e}")

        # Merge local overrides if present
        local_file = self.claude_dir / "settings.local.json"
        if local_file.exists():
            try:
                local = json.loads(local_file.read_text())
                settings = self._deep_merge(settings, local)
                logger.info("Merged settings.local.json overrides")
            except Exception as e:
                logger.error(f"Failed to load settings.local.json: {e}")

        return settings

    def _parse_frontmatter(self, file_path: Path) -> Dict:
        """Extract YAML frontmatter from markdown file."""
        content = file_path.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1])
        return {}

    def _parse_tools(self, tools_str: str) -> List[str]:
        """Parse tools string/list into list format."""
        if isinstance(tools_str, list):
            return tools_str
        if isinstance(tools_str, str):
            return [t.strip() for t in tools_str.split(",") if t.strip()]
        return []

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
```

### 1.2 Create Static Index Generator
**File**: `src/harness/static_indexer.py`

```python
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json

class StaticIndexer:
    """
    Generate index of static resources only.
    Dynamic content is referenced but not fully indexed.
    """

    def __init__(self, claude_dir: Path = Path("/app/.claude")):
        self.claude_dir = claude_dir

    def generate_static_index(self, agents: Dict, hooks: Dict, settings: Dict) -> str:
        """
        Generate INDEX.md for static resources.

        Args:
            agents: Loaded agents dictionary
            hooks: Loaded hooks configuration
            settings: Loaded settings

        Returns:
            Markdown formatted index content
        """
        lines = [
            "# Claude Resources Index",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Resource Overview",
            "",
            f"- **Static Resources**: {len(agents)} agents, hooks, settings (loaded at startup)",
            f"- **Dynamic Resources**: Skills, patterns, templates, workflows, specs (available via MCP)",
            "",
            "---",
            "",
            "## Static Resources (Loaded at Startup)",
            ""
        ]

        # Add agents section
        lines.extend(self._index_agents(agents))

        # Add hooks section
        lines.extend(self._index_hooks(hooks))

        # Add settings section
        lines.extend(self._index_settings(settings))

        # Add dynamic resources reference
        lines.extend([
            "---",
            "",
            "## Dynamic Resources (Available via MCP)",
            "",
            "Access dynamic content using `mcp__conventions__` tools:",
            "",
            "### Available Tools",
            "- `mcp__conventions__search(query, type)` - Search all dynamic content",
            "- `mcp__conventions__list_skills()` - List available skills",
            "- `mcp__conventions__get_skill(name)` - Get skill metadata",
            "- `mcp__conventions__get_pattern(skill, pattern)` - Load specific pattern",
            "- `mcp__conventions__get_template(skill, template)` - Load template",
            "- `mcp__conventions__get_workflow(skill, workflow)` - Load workflow",
            "- `mcp__conventions__get_spec(name)` - Load coding standard",
            "- `mcp__conventions__suggest_for_task(description)` - Get AI suggestions",
            "",
            "### Example Usage",
            "```python",
            '# Search for authentication patterns',
            'results = mcp__conventions__search("authentication fastapi")',
            '',
            '# Get specific pattern',
            'pattern = mcp__conventions__get_pattern("api-development", "authentication-patterns")',
            '',
            '# Get suggestions for task',
            'suggestions = mcp__conventions__suggest_for_task("Build REST API with PostgreSQL")',
            "```",
            ""
        ])

        return "\n".join(lines)

    def _index_agents(self, agents: Dict) -> List[str]:
        """Generate agents section grouped by category."""
        lines = ["### Agents (Task Delegation)", ""]

        # Group agents by prefix
        agent_groups = {}
        for agent_name in agents:
            prefix = agent_name.split("-")[0]
            if prefix not in agent_groups:
                agent_groups[prefix] = []
            agent_groups[prefix].append(agent_name)

        # Category names mapping
        category_names = {
            "dev": "Development Languages",
            "db": "Database Systems",
            "infra": "Infrastructure & Cloud",
            "ml": "Machine Learning",
            "web": "Web & Frontend",
            "build": "Build & Orchestration",
            "doc": "Documentation",
            "data": "Data Engineering"
        }

        for prefix in sorted(agent_groups.keys()):
            category = category_names.get(prefix, f"{prefix.capitalize()} Agents")
            lines.append(f"**{category}** ({len(agent_groups[prefix])} agents):")

            for agent_name in sorted(agent_groups[prefix]):
                lines.append(f"- `{agent_name}`")

            lines.append("")

        lines.extend([
            "**Usage**: `Task('description', subagent_type='agent-name')`",
            ""
        ])

        return lines

    def _index_hooks(self, hooks: Dict) -> List[str]:
        """Generate hooks section."""
        lines = ["### Hooks Configuration", ""]

        if not hooks or not hooks.get("hooks"):
            lines.append("*No hooks configured*")
            lines.append("")
            return lines

        for event_type, configs in hooks.get("hooks", {}).items():
            lines.append(f"**{event_type}**:")
            for config in configs:
                script = config.get("script", "unknown")
                desc = config.get("description", "No description")
                lines.append(f"- `{script}`: {desc}")
            lines.append("")

        lines.append(f"**Location**: `/app/.claude/hooks/hooks.json`")
        lines.append("")

        return lines

    def _index_settings(self, settings: Dict) -> List[str]:
        """Generate settings section."""
        lines = ["### Settings & Permissions", ""]

        if settings:
            lines.append(f"**Output Style**: {settings.get('outputStyle', 'default')}")

            if "permissions" in settings:
                perms = settings["permissions"]
                allow_count = len(perms.get("allow", []))
                deny_count = len(perms.get("deny", []))
                lines.append(f"**Permissions**: {allow_count} allowed, {deny_count} denied")

            lines.append("")
        else:
            lines.append("*No settings configured*")
            lines.append("")

        lines.append("**Locations**:")
        lines.append("- Base: `/app/.claude/settings.json`")
        lines.append("- Local overrides: `/app/.claude/settings.local.json`")
        lines.append("")

        return lines
```

### 1.3 Modify Agent Session
**File**: `src/harness/agent.py` (modifications)

```python
# Add to imports
from harness.static_resource_loader import StaticResourceLoader
from harness.static_indexer import StaticIndexer

# In AgentSession class
class AgentSession:

    async def start(self) -> None:
        """Start agent session with static resources and MCP servers."""
        try:
            # Initialize MCP servers first (including conventions MCP)
            await self._setup_mcp_servers()

            # Load static resources
            loader = StaticResourceLoader(Path("/app/.claude"))

            # Load agents for SDK registration
            available_agents = loader.load_agents_for_sdk()
            logger.info(f"Loaded {len(available_agents)} agents for delegation")

            # Load hooks and settings
            hooks = loader.load_hooks_config()
            settings = loader.load_settings()

            # Apply settings if needed
            if settings:
                # Apply permission settings, output style, etc.
                self._apply_settings(settings)

            # Generate static index
            indexer = StaticIndexer(Path("/app/.claude"))
            index_content = indexer.generate_static_index(available_agents, hooks, settings)

            # Write index to .claude/INDEX.md
            index_path = Path("/app/.claude/INDEX.md")
            index_path.write_text(index_content)
            logger.info(f"Generated resource index at {index_path}")

            # Create SDK options with loaded agents
            options = ClaudeAgentOptions(
                agents=available_agents,  # ✅ Agents now available for delegation
                allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch"],
                permission_mode=self.config.claude_permission_mode,
                max_turns=self.config.claude_max_turns,
                cwd=str(self.config.workspace_dir),
                model=self.config.claude_model,
                mcp_servers=self.mcp_servers,  # Including conventions MCP
            )

            # Create SDK client with options
            self.client = ClaudeSDKClient(api_key=self.api_key)

            # ... rest of initialization
```

## Phase 2: Dynamic Content MCP Server

### 2.1 Create Conventions MCP Server
**File**: `src/mcp/conventions/server.py`

```python
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import yaml
import logging

logger = logging.getLogger(__name__)

class ConventionsMCPServer:
    """
    MCP server for dynamic convention resources.
    Handles: patterns, templates, workflows, specs, skills metadata.

    These resources are "dynamic" because they:
    1. Can be searched and filtered at runtime
    2. Support progressive disclosure (metadata → full content)
    3. Can be extended without restarting the session
    """

    def __init__(self, claude_dir: Path = Path("/app/.claude")):
        self.claude_dir = claude_dir
        self._index = None  # Built on first use
        self._cache = {}  # Content cache

        # Register MCP tools
        self.tools = {
            # Discovery tools
            "mcp__conventions__search": self.search,
            "mcp__conventions__list_skills": self.list_skills,

            # Metadata tools
            "mcp__conventions__get_skill": self.get_skill,

            # Content loading tools
            "mcp__conventions__get_pattern": self.get_pattern,
            "mcp__conventions__get_template": self.get_template,
            "mcp__conventions__get_workflow": self.get_workflow,
            "mcp__conventions__get_spec": self.get_spec,

            # Advanced features
            "mcp__conventions__suggest_for_task": self.suggest_for_task,
        }

    def _ensure_index(self):
        """Build index of dynamic content on first use."""
        if self._index is None:
            self._index = self._build_dynamic_index()
            logger.info(f"Built dynamic index with {len(self._index['skills'])} skills")

    def _build_dynamic_index(self) -> Dict:
        """
        Index skills directory structure and specs.
        This enables runtime discovery without loading full content.
        """
        index = {
            "skills": {},
            "specs": {}
        }

        # Index skills with their subdirectories
        skills_dir = self.claude_dir / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                try:
                    metadata = self._parse_frontmatter(skill_file)

                    index["skills"][skill_dir.name] = {
                        "description": metadata.get("description", ""),
                        "category": metadata.get("category", "general"),
                        "tags": metadata.get("tags", []),
                        "patterns": self._list_files(skill_dir / "patterns"),
                        "templates": self._list_files(skill_dir / "templates"),
                        "workflows": self._list_files(skill_dir / "workflows"),
                        "path": str(skill_dir)
                    }
                except Exception as e:
                    logger.warning(f"Failed to index skill {skill_dir.name}: {e}")

        # Index spec files
        specs_dir = self.claude_dir / "specs"
        if specs_dir.exists():
            for spec_file in specs_dir.glob("*.md"):
                try:
                    # Read first 500 chars for summary
                    content = spec_file.read_text()[:500]
                    index["specs"][spec_file.stem] = {
                        "summary": self._extract_summary(content),
                        "path": str(spec_file)
                    }
                except Exception as e:
                    logger.warning(f"Failed to index spec {spec_file}: {e}")

        return index

    def search(self, query: str, type: Optional[str] = None) -> List[Dict]:
        """
        Search across all dynamic content.

        Args:
            query: Search terms
            type: Filter by type (pattern|template|workflow|spec|skill)

        Returns:
            List of matching resources with metadata
        """
        self._ensure_index()
        results = []
        query_lower = query.lower()

        # Search skills and their components
        for skill_name, skill_data in self._index["skills"].items():
            # Check skill metadata
            if query_lower in skill_name.lower() or \
               query_lower in skill_data["description"].lower():

                if not type or type == "skill":
                    results.append({
                        "type": "skill",
                        "name": skill_name,
                        "description": skill_data["description"],
                        "components": {
                            "patterns": len(skill_data["patterns"]),
                            "templates": len(skill_data["templates"]),
                            "workflows": len(skill_data["workflows"])
                        }
                    })

                # Search within skill components
                if not type or type == "pattern":
                    for pattern in skill_data["patterns"]:
                        if query_lower in pattern.lower():
                            results.append({
                                "type": "pattern",
                                "skill": skill_name,
                                "name": pattern,
                                "path": f"{skill_name}/patterns/{pattern}"
                            })

                # Similar for templates and workflows...

        # Search specs
        if not type or type == "spec":
            for spec_name, spec_data in self._index["specs"].items():
                if query_lower in spec_name.lower() or \
                   query_lower in spec_data["summary"].lower():
                    results.append({
                        "type": "spec",
                        "name": spec_name,
                        "summary": spec_data["summary"]
                    })

        return results[:20]  # Limit results

    def list_skills(self) -> Dict[str, Dict]:
        """
        List all available skills with metadata.

        Returns:
            Dictionary of skill names to metadata
        """
        self._ensure_index()
        return {
            name: {
                "description": data["description"],
                "patterns": len(data["patterns"]),
                "templates": len(data["templates"]),
                "workflows": len(data["workflows"])
            }
            for name, data in self._index["skills"].items()
        }

    def get_skill(self, name: str) -> Dict:
        """
        Get skill metadata without loading full content.

        Args:
            name: Skill name (e.g., "api-development")

        Returns:
            Skill metadata including available components
        """
        self._ensure_index()

        if name not in self._index["skills"]:
            raise ValueError(f"Skill '{name}' not found")

        return self._index["skills"][name]

    def get_pattern(self, skill: str, pattern: str) -> str:
        """
        Load specific pattern from skill.

        Args:
            skill: Skill name (e.g., "api-development")
            pattern: Pattern name (e.g., "authentication-patterns")

        Returns:
            Full pattern content
        """
        cache_key = f"pattern:{skill}:{pattern}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.claude_dir / "skills" / skill / "patterns" / f"{pattern}.md"

        if not path.exists():
            raise FileNotFoundError(f"Pattern '{pattern}' not found in skill '{skill}'")

        content = path.read_text()
        self._cache[cache_key] = content
        return content

    def get_template(self, skill: str, template: str) -> str:
        """Load specific template from skill."""
        cache_key = f"template:{skill}:{template}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.claude_dir / "skills" / skill / "templates" / f"{template}.md"

        if not path.exists():
            raise FileNotFoundError(f"Template '{template}' not found in skill '{skill}'")

        content = path.read_text()
        self._cache[cache_key] = content
        return content

    def get_workflow(self, skill: str, workflow: str) -> str:
        """Load specific workflow from skill."""
        cache_key = f"workflow:{skill}:{workflow}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.claude_dir / "skills" / skill / "workflows" / f"{workflow}.md"

        if not path.exists():
            raise FileNotFoundError(f"Workflow '{workflow}' not found in skill '{skill}'")

        content = path.read_text()
        self._cache[cache_key] = content
        return content

    def get_spec(self, name: str) -> str:
        """
        Load coding standard/spec.

        Args:
            name: Spec name (e.g., "python", "typescript")

        Returns:
            Full spec content
        """
        cache_key = f"spec:{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.claude_dir / "specs" / f"{name}.md"

        if not path.exists():
            raise FileNotFoundError(f"Spec '{name}' not found")

        content = path.read_text()
        self._cache[cache_key] = content
        return content

    def suggest_for_task(self, task_description: str) -> Dict:
        """
        AI-powered suggestion of relevant conventions.

        Args:
            task_description: Natural language task description

        Returns:
            Dictionary with suggested resources
        """
        self._ensure_index()

        # Simple keyword matching (could be enhanced with embeddings)
        suggestions = {
            "skills": [],
            "patterns": [],
            "templates": [],
            "specs": []
        }

        task_lower = task_description.lower()

        # Match skills based on keywords
        skill_keywords = {
            "api-development": ["api", "rest", "graphql", "endpoint"],
            "database-management": ["database", "sql", "postgres", "schema"],
            "deployment-operations": ["deploy", "docker", "kubernetes", "ci/cd"],
            "security": ["auth", "security", "encryption", "vulnerability"],
            "testing-strategies": ["test", "unit", "integration", "coverage"],
            "frontend-development": ["frontend", "react", "ui", "component"],
            "microservices-architecture": ["microservice", "distributed", "service"],
            "performance-optimization": ["performance", "optimize", "cache", "speed"]
        }

        for skill, keywords in skill_keywords.items():
            if any(kw in task_lower for kw in keywords):
                if skill in self._index["skills"]:
                    suggestions["skills"].append(skill)

                    # Suggest specific patterns/templates
                    skill_data = self._index["skills"][skill]

                    # Add relevant patterns
                    for pattern in skill_data["patterns"]:
                        if any(kw in pattern.lower() for kw in keywords):
                            suggestions["patterns"].append(f"{skill}/{pattern}")

                    # Add relevant templates
                    for template in skill_data["templates"]:
                        suggestions["templates"].append(f"{skill}/{template}")

        # Match specs based on language keywords
        if "python" in task_lower or "fastapi" in task_lower:
            suggestions["specs"].append("python")
        if "typescript" in task_lower or "react" in task_lower:
            suggestions["specs"].append("typescript")
        if "javascript" in task_lower or "node" in task_lower:
            suggestions["specs"].append("javascript")

        return suggestions

    def _parse_frontmatter(self, file_path: Path) -> Dict:
        """Extract YAML frontmatter from markdown file."""
        content = file_path.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1])
        return {}

    def _list_files(self, directory: Path) -> List[str]:
        """List markdown files in directory (without extension)."""
        if not directory.exists():
            return []
        return [f.stem for f in directory.glob("*.md")]

    def _extract_summary(self, content: str) -> str:
        """Extract summary from content (first paragraph or line)."""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:200] + ("..." if len(line) > 200 else "")
        return "No summary available"
```

### 2.2 Register Conventions MCP
**File**: `src/harness/agent.py` (additional modification)

```python
from mcp.conventions.server import ConventionsMCPServer

class AgentSession:

    async def _setup_mcp_servers(self):
        """Setup MCP servers including conventions for dynamic content."""

        # Existing MCP servers
        git_server = GitMCPServer()
        docker_server = DockerMCPServer()

        # NEW: Conventions MCP for dynamic content
        conventions_server = ConventionsMCPServer(Path("/app/.claude"))

        self.mcp_servers = {
            "git": git_server,
            "docker": docker_server,
            "conventions": conventions_server,  # ✅ Dynamic content access
            # ... other existing servers
        }

        logger.info("MCP servers initialized, including conventions server")
```

## Phase 3: Documentation Updates

### 3.1 Update .claude/CLAUDE.md

Add section about resource discovery:

```markdown
### Resource Discovery

#### Static Resources (Pre-loaded at Startup)
- **Agents**: 44 specialists available for Task delegation
- **Hooks**: Action logging configured
- **Settings**: Permissions and configuration applied
- **Index**: `/app/.claude/INDEX.md` lists all static resources

#### Dynamic Resources (MCP Runtime Access)
Access patterns, templates, workflows, specs via `mcp__conventions__` tools:

```python
# Search for relevant patterns
results = mcp__conventions__search("authentication fastapi")

# Get skill metadata
skill = mcp__conventions__get_skill("api-development")

# Load specific pattern
pattern = mcp__conventions__get_pattern("api-development", "authentication-patterns")

# Get AI suggestions for task
suggestions = mcp__conventions__suggest_for_task("Build REST API with PostgreSQL")
```

### Progressive Loading Workflow

1. **Startup**: Agents loaded, static index generated
2. **Discovery**: Use MCP search to find relevant resources
3. **Metadata**: Get skill/spec summaries first
4. **Full Content**: Load specific patterns/templates as needed
5. **Delegation**: Use pre-loaded agents with Task tool
```

### 3.2 Update .gitignore

Add generated index:

```
# Generated indices
.claude/INDEX.md
```

## Phase 4: Testing Strategy

### 4.1 Static Loading Tests
**File**: `tests/unit/test_static_loader.py`

```python
import pytest
from pathlib import Path
from harness.static_resource_loader import StaticResourceLoader

def test_load_agents_for_sdk():
    """Test agent loading and SDK format conversion."""
    loader = StaticResourceLoader(Path("test_fixtures/.claude"))
    agents = loader.load_agents_for_sdk()

    assert "dev-python-expert" in agents
    assert agents["dev-python-expert"]["model"] in ["opus", "sonnet", "haiku"]
    assert isinstance(agents["dev-python-expert"]["tools"], list)

def test_load_hooks_config():
    """Test hooks.json loading."""
    loader = StaticResourceLoader(Path("test_fixtures/.claude"))
    hooks = loader.load_hooks_config()

    assert isinstance(hooks, dict)
    if hooks:
        assert "hooks" in hooks

def test_load_settings_with_overrides():
    """Test settings merge logic."""
    loader = StaticResourceLoader(Path("test_fixtures/.claude"))
    settings = loader.load_settings()

    assert isinstance(settings, dict)
    # Verify local overrides are applied
```

### 4.2 Dynamic MCP Tests
**File**: `tests/unit/test_conventions_mcp.py`

```python
import pytest
from pathlib import Path
from mcp.conventions.server import ConventionsMCPServer

def test_dynamic_index_building():
    """Test index builds correctly on first use."""
    server = ConventionsMCPServer(Path("test_fixtures/.claude"))
    server._ensure_index()

    assert "skills" in server._index
    assert "specs" in server._index

def test_search_functionality():
    """Test search across dynamic content."""
    server = ConventionsMCPServer(Path("test_fixtures/.claude"))
    results = server.search("authentication")

    assert isinstance(results, list)
    assert all("type" in r for r in results)

def test_progressive_loading():
    """Test progressive disclosure works."""
    server = ConventionsMCPServer(Path("test_fixtures/.claude"))

    # Get metadata only
    skill = server.get_skill("api-development")
    assert "patterns" in skill

    # Load full content
    pattern = server.get_pattern("api-development", "authentication-patterns")
    assert len(pattern) > 100  # Full content loaded

def test_suggest_for_task():
    """Test AI-powered suggestions."""
    server = ConventionsMCPServer(Path("test_fixtures/.claude"))
    suggestions = server.suggest_for_task("Build REST API with authentication")

    assert "skills" in suggestions
    assert "api-development" in suggestions["skills"]
```

### 4.3 Integration Tests
**File**: `tests/integration/test_hybrid_loading.py`

```python
import pytest
from harness.agent import AgentSession

@pytest.mark.integration
async def test_static_agents_available():
    """Test agents are registered and available for delegation."""
    session = AgentSession()
    await session.start()

    # Verify agents are loaded
    assert len(session.client.options.agents) > 0
    assert "dev-python-expert" in session.client.options.agents

@pytest.mark.integration
async def test_complete_workflow():
    """Test static loading + dynamic MCP access."""
    session = AgentSession()
    await session.start()

    # Static: Agents available
    assert session.client.options.agents

    # Dynamic: MCP accessible
    assert "conventions" in session.mcp_servers

    # Can search dynamic content
    conventions = session.mcp_servers["conventions"]
    results = conventions.search("api")
    assert len(results) > 0
```

## Benefits of This Hybrid Approach

### Static Loading Benefits
- **Immediate availability**: Agents ready for SDK delegation at startup
- **No runtime overhead**: Core functionality pre-loaded
- **Reliable**: No network/filesystem delays for critical resources
- **SDK compliant**: Works within ClaudeAgentOptions constraints

### Dynamic MCP Benefits
- **Flexible discovery**: Search and filter knowledge at runtime
- **Progressive disclosure**: Load only what's needed, when needed
- **Extensible**: Add new patterns/templates without restart
- **Smart assistance**: AI-powered suggestions based on task
- **Cache efficient**: Content cached after first load

### Clear Separation of Concerns
- **Static = Infrastructure**: What the SDK needs to function (agents, hooks, settings)
- **Dynamic = Knowledge**: What agents need to know (patterns, templates, specs)
- **No confusion**: Clear boundary between startup config and runtime knowledge

## Implementation Timeline

1. **Static resource loader**: 45 min
2. **Static indexer**: 30 min
3. **Modify agent.py for static loading**: 15 min
4. **Conventions MCP server**: 90 min
5. **Integration and testing**: 60 min
6. **Documentation updates**: 30 min

**Total estimate: ~4.5 hours**

## Next Steps

1. **Phase 1**: Implement static loading first
   - Create `StaticResourceLoader` class
   - Create `StaticIndexer` class
   - Modify `agent.py` to load and register agents
   - Test that agents are available for delegation

2. **Phase 2**: Implement conventions MCP
   - Create `ConventionsMCPServer` class
   - Register with MCP servers in agent.py
   - Test progressive loading and search

3. **Phase 3**: Integration testing
   - Verify static + dynamic work together
   - Test realistic workflows
   - Update documentation with examples

## Future Enhancements

Once the hybrid system is working:

1. **Smart caching**: Cache frequently used patterns
2. **Usage analytics**: Track which resources are most used
3. **Auto-suggestions**: Proactively suggest resources based on context
4. **External sources**: Load conventions from Git repos or URLs
5. **Custom conventions**: Allow users to add their own patterns/templates

---

**Last updated**: November 14, 2025
**Status**: Ready for implementation