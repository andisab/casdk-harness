# External Repository Support - Implementation Plan

**Status**: Proposed
**Created**: October 6, 2025
**Purpose**: Add comprehensive support for working with external repositories in the Claude Agent SDK Harness

---

## Table of Contents

- [Overview](#overview)
- [Research Summary](#research-summary)
- [Three Approaches](#three-approaches)
- [Implementation Plan](#implementation-plan)
- [File Changes](#file-changes)
- [Success Criteria](#success-criteria)
- [Timeline & Scope](#timeline--scope)

---

## Overview

### Problem Statement

Users need to run the Claude Agent SDK Harness against external repositories (both local and remote) to build, test, and fix code in their own projects. Currently, the harness only works with code placed directly in the `./workspace` directory.

### Solution

Implement three complementary approaches:
1. **Git Clone** - Simple cloning into workspace (zero config)
2. **Volume Mounting** - Direct access to local repositories
3. **Automated Workflows** - Programmatic repository management

All three approaches will coexist, giving users flexibility based on their use case.

---

## Research Summary

### Key Findings from Claude Agent SDK Documentation

1. **`cwd` Parameter**: The SDK supports `ClaudeAgentOptions(cwd="/path/to/project")` to set working directory
2. **Setting Sources**: Use `setting_sources=["project"]` to auto-load `CLAUDE.md` from target repository
3. **Current Implementation**: Harness already uses `cwd` but hardcoded to `/workspace`
4. **MCP Servers**: Git MCP server already implemented (`git_status`, `git_diff`, `git_log`)

### Community Best Practices

- **CLAUDE.md in Repository**: Context file auto-loaded by agent
- **Sub-Agents**: Specialized agents for different tasks (reviewer, tester)
- **Git Worktrees**: Multiple branches in separate directories
- **Remote Sandboxes**: Services like Depot support `depot claude --repository <url>`

### Current Harness Configuration

**Existing support**:
- ✅ `cwd` parameter in `ClaudeAgentOptions` (line 210 in `agent.py`)
- ✅ Git MCP server for git operations
- ✅ Docker volume mounts for workspace
- ✅ Configurable workspace directory via `config.workspace_dir`

**What's missing**:
- ❌ Configuration for external repositories
- ❌ Automated git clone workflows
- ❌ Dynamic volume mounting
- ❌ Example workflows for external repos
- ❌ Documentation and guides

---

## Three Approaches

### Approach 1: Git Clone Into Workspace

**Best for**: Quick experiments, single-use tasks, simple testing

#### How It Works
1. Agent receives prompt with repository URL
2. Clones repository into `/workspace/repo-name`
3. Agent works in cloned directory
4. Repository persists after containers stop

#### Example Usage
```python
# Via Python API
session = AgentSession(agent_name="main")
await session.execute(
    "Clone https://github.com/user/my-app and run tests"
)

# Via Makefile
make work-on REPO=https://github.com/user/my-app TASK="Fix linting errors"
```

#### Pros & Cons
✅ Zero configuration required
✅ Works immediately with existing setup
✅ Repositories persist between sessions
❌ Workspace can get cluttered
❌ No isolation between projects
❌ Manual cleanup needed

---

### Approach 2: Volume Mounting (Recommended)

**Best for**: Working on existing local repositories, long-term projects, development workflow

#### How It Works
1. User adds volume mount to `docker-compose.override.yml`
2. Local repository mapped into container
3. Agent configured with `cwd` pointing to mounted repo
4. Changes made by agent immediately visible on host

#### Example Configuration
```yaml
# docker-compose.override.yml (user-created, gitignored)
services:
  main-agent:
    volumes:
      - ~/Projects/my-app:/projects/my-app:delegated
```

```bash
# Environment configuration
export WORKSPACE_DIR=/projects/my-app

# Start harness
make up
```

#### Pros & Cons
✅ Direct access to local repositories
✅ Changes persist outside container
✅ Git history preserved
✅ Can use local IDE simultaneously
❌ Requires docker-compose modification
❌ One repository per configuration

---

### Approach 3: Automated Workflows (Most Flexible)

**Best for**: Multi-project workflows, production deployments, CI/CD integration

#### How It Works
1. Python scripts manage repository lifecycle
2. Repositories cloned/mounted dynamically via API
3. Agent sessions configured programmatically
4. Clean separation between projects

#### Example Implementation
```python
# examples/external_repo_workflow.py
from harness.utils.repository import clone_repository, configure_workspace

async def work_on_repository(
    repo_url: str,
    task: str,
    branch: str = "main"
):
    # Clone repository
    repo_path = await clone_repository(
        url=repo_url,
        branch=branch,
        workspace_dir=Path("/workspace/projects")
    )

    # Create session for this repository
    session = AgentSession(
        agent_name="main",
        workspace_dir=repo_path,
        setting_sources=["project"]  # Load CLAUDE.md from repo
    )

    # Execute task
    await session.execute(task)

    # Return results
    return await session.get_state()
```

#### Example Usage
```bash
# Via Python API
await work_on_repository(
    repo_url="https://github.com/user/api-service",
    task="Add authentication to /users endpoint",
    branch="feature/auth"
)

# Via CLI
python scripts/work_on_repo.py \
    --repo https://github.com/user/api-service \
    --branch feature/auth \
    --task "Add authentication to /users endpoint"
```

#### Pros & Cons
✅ Fully automated
✅ Supports any repository
✅ Clean project separation
✅ Scriptable and composable
✅ Production-ready
❌ Requires custom scripting (but reusable)
❌ More complex setup initially

---

## Implementation Plan

### Phase 1: Configuration & Core Utilities

#### 1.1 Environment Variables
**File**: `.env.example`

Add new configuration options:
```bash
# =============================================================================
# External Repository Configuration
# =============================================================================

# Git Repository Settings
EXTERNAL_REPO_URL=                      # Repository to clone (optional)
EXTERNAL_REPO_BRANCH=main               # Branch to checkout
EXTERNAL_REPO_DEPTH=1                   # Clone depth (1 for shallow)

# Local Repository Settings
LOCAL_REPO_PATH=                        # Path to local repo to mount (optional)

# Workspace Organization
WORKSPACE_SUBDIR=projects               # Subdirectory for external projects
AUTO_LOAD_CLAUDE_MD=true                # Load CLAUDE.md from repos

# Git Configuration
GIT_USER_NAME=Claude Agent              # Git commit author name
GIT_USER_EMAIL=agent@claude.local      # Git commit author email
GIT_SSH_KEY_PATH=                       # Path to SSH key for private repos
```

#### 1.2 Configuration Class Updates
**File**: `src/harness/config.py`

Add fields to `HarnessConfig`:
```python
class HarnessConfig(BaseSettings):
    # ... existing fields ...

    # External Repository Configuration
    external_repo_url: str = Field(default="", description="Git repository URL")
    external_repo_branch: str = Field(default="main")
    external_repo_depth: int = Field(default=1)

    local_repo_path: Path | None = Field(default=None)
    workspace_subdir: str = Field(default="projects")
    auto_load_claude_md: bool = Field(default=True)

    git_user_name: str = Field(default="Claude Agent")
    git_user_email: str = Field(default="agent@claude.local")

    @property
    def projects_dir(self) -> Path:
        """Get projects directory for external repositories."""
        return self.workspace_dir / self.workspace_subdir
```

#### 1.3 Repository Utilities
**File**: `src/utils/repository.py` (new)

Core functionality:
```python
"""Repository management utilities for external codebases."""

import asyncio
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


async def clone_repository(
    url: str,
    destination: Path,
    branch: str = "main",
    depth: int = 1,
    ssh_key: Optional[Path] = None
) -> Path:
    """
    Clone a git repository.

    Args:
        url: Git repository URL (https or ssh)
        destination: Target directory
        branch: Branch to checkout
        depth: Clone depth (1 for shallow)
        ssh_key: Optional SSH key for private repos

    Returns:
        Path to cloned repository
    """
    # Implementation
    pass


async def validate_local_repository(path: Path) -> bool:
    """Validate that path is a valid git repository."""
    pass


async def get_repository_info(repo_path: Path) -> dict:
    """Get repository metadata (branch, commit, remote)."""
    pass


async def setup_git_credentials(
    repo_path: Path,
    user_name: str,
    user_email: str
) -> None:
    """Configure git user for commits."""
    pass
```

#### 1.4 Agent Session Updates
**File**: `src/harness/agent.py`

Enhance `AgentSession.__init__()`:
```python
def __init__(
    self,
    agent_name: str = "main",
    config: HarnessConfig | None = None,
    checkpoint_manager: CheckpointManager | None = None,
    metrics_collector: MetricsCollector | None = None,
    repository_url: str | None = None,  # NEW
    repository_branch: str = "main",     # NEW
    workspace_dir: Path | None = None,   # NEW
) -> None:
    """
    Initialize agent session.

    Args:
        agent_name: Name of the agent
        config: Configuration object
        checkpoint_manager: Checkpoint manager instance
        metrics_collector: Metrics collector instance
        repository_url: Optional git repository to clone
        repository_branch: Branch to checkout
        workspace_dir: Override default workspace directory
    """
    self.agent_name = agent_name
    self.config = config or get_config()

    # Handle repository cloning if URL provided
    if repository_url:
        self.repository_path = await self._clone_repository(
            url=repository_url,
            branch=repository_branch
        )
        # Override workspace to repository path
        workspace_dir = self.repository_path

    # Override workspace if provided
    if workspace_dir:
        self.config.workspace_dir = workspace_dir

    # ... rest of initialization ...
```

Update `ClaudeAgentOptions`:
```python
# In _execute_with_retry() method
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch"],
    permission_mode=self.config.claude_permission_mode,
    max_turns=self.config.claude_max_turns,
    cwd=str(self.config.workspace_dir),  # Updated workspace
    model=self.config.claude_model,
    mcp_servers=self.mcp_servers,
    setting_sources=["project"] if self.config.auto_load_claude_md else [],  # NEW
)
```

---

### Phase 2: Docker & Orchestration

#### 2.1 Override Template
**File**: `docker-compose.override.yml.example` (new)

Template for user customization:
```yaml
# =============================================================================
# Docker Compose Override Template for External Repositories
# =============================================================================
# Copy this file to docker-compose.override.yml (gitignored)
# Customize with your local repository paths

services:
  main-agent:
    volumes:
      # Mount your local repositories here
      # Format: - /host/path:/container/path:delegated

      # Example: Python project
      # - ~/Projects/my-api:/projects/my-api:delegated

      # Example: Multiple repositories
      # - ~/Projects/frontend:/projects/frontend:delegated
      # - ~/Projects/backend:/projects/backend:delegated

      # Example: Monorepo
      # - ~/Work/monorepo:/projects/monorepo:delegated

    environment:
      # Override workspace to point to mounted repository
      # - WORKSPACE_DIR=/projects/my-api
      pass

  reviewer-agent:
    volumes:
      # Mount same repos as read-only for reviewer
      # - ~/Projects/my-api:/projects/my-api:ro
      pass

  tester-agent:
    volumes:
      # Mount repos for testing
      # - ~/Projects/my-api:/projects/my-api:delegated
      pass
```

#### 2.2 Gitignore Updates
**File**: `.gitignore`

Add:
```
# Docker Compose overrides (user-specific)
docker-compose.override.yml

# User workspace projects
workspace/projects/
```

---

### Phase 3: Scripts & Automation

#### 3.1 Clone Repository Script
**File**: `scripts/clone_repo.py` (new)

```python
#!/usr/bin/env python3
"""Clone external repository into workspace."""

import asyncio
import sys
from pathlib import Path
import click
import structlog

from harness.config import get_config
from utils.repository import clone_repository, setup_git_credentials

logger = structlog.get_logger(__name__)


@click.command()
@click.option('--url', required=True, help='Git repository URL')
@click.option('--branch', default='main', help='Branch to checkout')
@click.option('--depth', default=1, help='Clone depth')
@click.option('--name', help='Custom directory name (defaults to repo name)')
async def main(url: str, branch: str, depth: int, name: str | None):
    """Clone external repository into workspace."""
    config = get_config()

    # Determine destination
    repo_name = name or url.split('/')[-1].replace('.git', '')
    destination = config.projects_dir / repo_name

    logger.info("Cloning repository", url=url, destination=str(destination))

    try:
        repo_path = await clone_repository(
            url=url,
            destination=destination,
            branch=branch,
            depth=depth
        )

        await setup_git_credentials(
            repo_path=repo_path,
            user_name=config.git_user_name,
            user_email=config.git_user_email
        )

        logger.info("Repository cloned successfully", path=str(repo_path))
        print(f"✅ Repository cloned to: {repo_path}")

    except Exception as e:
        logger.error("Failed to clone repository", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

#### 3.2 Mount Local Repository Script
**File**: `scripts/mount_local_repo.sh` (new)

```bash
#!/usr/bin/env bash
# Mount local repository and restart services

set -euo pipefail

REPO_PATH="${1:?Usage: $0 <local-repo-path>}"
REPO_NAME="$(basename "$REPO_PATH")"

echo "🔍 Validating repository: $REPO_PATH"

if [ ! -d "$REPO_PATH/.git" ]; then
    echo "❌ Error: Not a git repository: $REPO_PATH"
    exit 1
fi

echo "📝 Creating docker-compose.override.yml"

cat > docker-compose.override.yml <<EOF
# Auto-generated override for $REPO_NAME
# Created: $(date)

services:
  main-agent:
    volumes:
      - $REPO_PATH:/projects/$REPO_NAME:delegated
    environment:
      - WORKSPACE_DIR=/projects/$REPO_NAME

  reviewer-agent:
    volumes:
      - $REPO_PATH:/projects/$REPO_NAME:ro

  tester-agent:
    volumes:
      - $REPO_PATH:/projects/$REPO_NAME:delegated
EOF

echo "✅ Override file created"
echo "🔄 Restarting services..."

make down
make up

echo "✅ Services restarted with mounted repository"
echo "📂 Repository available at: /projects/$REPO_NAME"
```

#### 3.3 Unified Workflow Script
**File**: `scripts/work_on_repo.py` (new)

```python
#!/usr/bin/env python3
"""Work on external repository with Claude Agent."""

import asyncio
import click
from pathlib import Path

from harness.agent import AgentSession
from harness.config import get_config


@click.command()
@click.option('--repo', 'repo_url', required=True, help='Git repository URL')
@click.option('--branch', default='main', help='Branch to checkout')
@click.option('--task', required=True, help='Task for the agent')
@click.option('--agent', default='main', help='Agent to use (main/reviewer/tester)')
async def main(repo_url: str, branch: str, task: str, agent: str):
    """Work on external repository with specified task."""

    print(f"🚀 Starting agent: {agent}")
    print(f"📦 Repository: {repo_url} (branch: {branch})")
    print(f"📋 Task: {task}\n")

    # Create session with repository
    session = AgentSession(
        agent_name=agent,
        repository_url=repo_url,
        repository_branch=branch
    )

    await session.start()

    try:
        # Execute task
        async for message in session.execute(task):
            print(message)

        print("\n✅ Task completed successfully")

    except Exception as e:
        print(f"\n❌ Task failed: {e}")
        raise

    finally:
        await session.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### Phase 4: Example Workflows

#### 4.1 Simple Feature Development
**File**: `examples/simple-feature/clone_and_test.py`

```python
"""Example: Clone repository, run tests, fix failures."""

import asyncio
from harness.agent import AgentSession


async def main():
    """Clone repo and fix test failures."""

    session = AgentSession(
        agent_name="main",
        repository_url="https://github.com/user/my-app",
        repository_branch="main"
    )

    await session.start()

    # Task: Run tests and fix failures
    task = """
    1. Run the test suite using pytest
    2. Analyze any test failures
    3. Fix the failing tests
    4. Re-run tests to verify fixes
    5. Create a summary of changes made
    """

    async for message in session.execute(task):
        print(message)

    await session.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

**File**: `examples/simple-feature/README.md`
```markdown
# Simple Feature Example

## Overview
Demonstrates cloning a repository and working on a simple feature.

## Usage
```bash
python examples/simple-feature/clone_and_test.py
```

## What It Does
1. Clones the specified repository
2. Runs existing test suite
3. Fixes any failing tests
4. Verifies fixes

## Customization
Edit the script to:
- Change repository URL
- Modify task prompt
- Use different agent (reviewer, tester)
```

#### 4.2 Bug Fix Workflow
**File**: `examples/bug-fix/analyze_and_fix.py`

```python
"""Example: Analyze GitHub issue and implement fix."""

import asyncio
from harness.agent import AgentSession


async def fix_github_issue(
    repo_url: str,
    issue_number: int,
    branch_name: str = "bugfix"
):
    """Analyze issue and create fix."""

    session = AgentSession(
        agent_name="main",
        repository_url=repo_url,
        repository_branch="main"
    )

    await session.start()

    task = f"""
    1. Fetch GitHub issue #{issue_number} details
    2. Analyze the bug report and reproduce the issue
    3. Implement a fix
    4. Add/update tests to prevent regression
    5. Create a new branch '{branch_name}' with the fix
    6. Generate a summary for pull request description
    """

    async for message in session.execute(task):
        print(message)

    await session.shutdown()


if __name__ == "__main__":
    asyncio.run(fix_github_issue(
        repo_url="https://github.com/user/my-app",
        issue_number=42,
        branch_name="fix-issue-42"
    ))
```

#### 4.3 Multi-Repository Coordinator
**File**: `examples/full-project/multi_repo_coordinator.py`

```python
"""Example: Coordinate changes across multiple repositories."""

import asyncio
from harness.agent import AgentSession


async def coordinate_multi_repo_change():
    """Make coordinated changes across frontend and backend."""

    # Backend changes
    backend = AgentSession(
        agent_name="main",
        repository_url="https://github.com/user/backend-api"
    )

    # Frontend changes
    frontend = AgentSession(
        agent_name="main",
        repository_url="https://github.com/user/frontend-app"
    )

    await backend.start()
    await frontend.start()

    # Step 1: Update backend API
    backend_task = """
    Add a new /api/users/profile endpoint that returns:
    - user_id
    - username
    - email
    - created_at
    Include tests and update API documentation.
    """

    async for message in backend.execute(backend_task):
        print(f"[BACKEND] {message}")

    # Step 2: Update frontend to use new endpoint
    frontend_task = """
    Update the UserProfile component to:
    1. Fetch data from /api/users/profile
    2. Display all fields returned by the API
    3. Add loading and error states
    4. Write component tests
    """

    async for message in frontend.execute(frontend_task):
        print(f"[FRONTEND] {message}")

    await backend.shutdown()
    await frontend.shutdown()


if __name__ == "__main__":
    asyncio.run(coordinate_multi_repo_change())
```

---

### Phase 5: Makefile Integration

**File**: `Makefile` (additions)

```makefile
# =============================================================================
# External Repository Operations
# =============================================================================

.PHONY: clone-repo
clone-repo: ## Clone external repository into workspace
	@python scripts/clone_repo.py --url $(REPO) --branch $(BRANCH)

.PHONY: mount-local
mount-local: ## Mount local repository as volume
	@bash scripts/mount_local_repo.sh $(PATH)

.PHONY: work-on
work-on: check-env ## Work on external repository with specified task
	@python scripts/work_on_repo.py \
		--repo $(REPO) \
		--branch $(BRANCH) \
		--task "$(TASK)"

.PHONY: list-repos
list-repos: ## List all cloned repositories in workspace
	@echo "$(GREEN)Cloned Repositories:$(NC)"
	@find workspace/projects -maxdepth 1 -type d -name ".git" -execdir pwd \; 2>/dev/null || echo "No repositories found"

.PHONY: clean-repos
clean-repos: ## Remove all cloned repositories
	@echo "$(YELLOW)Warning: This will delete all repositories in workspace/projects$(NC)"
	@read -p "Continue? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf workspace/projects/*; \
		echo "$(GREEN)Repositories cleaned$(NC)"; \
	fi

# =============================================================================
# Example Workflows
# =============================================================================

.PHONY: example-simple
example-simple: ## Run simple feature example
	python examples/simple-feature/clone_and_test.py

.PHONY: example-bugfix
example-bugfix: ## Run bug fix example
	python examples/bug-fix/analyze_and_fix.py

.PHONY: example-multi
example-multi: ## Run multi-repository example
	python examples/full-project/multi_repo_coordinator.py
```

---

### Phase 6: Documentation

#### 6.1 CLAUDE.md Updates
**File**: `CLAUDE.md`

Add new section after "Verification Checklist":

```markdown
## Working with External Repositories

### Overview

The harness supports three approaches for working with external codebases:

1. **Git Clone** - Clone repositories into workspace (zero config)
2. **Volume Mounting** - Mount local repositories (development)
3. **Automated Workflows** - Programmatic repository management (production)

### Quick Start

#### Approach 1: Clone Repository

```bash
# Via Makefile
make clone-repo REPO=https://github.com/user/my-app BRANCH=main

# Via Python
python scripts/clone_repo.py --url https://github.com/user/my-app --branch main

# Work on cloned repository
make work-on REPO=https://github.com/user/my-app TASK="Fix linting errors"
```

#### Approach 2: Mount Local Repository

```bash
# Mount local repository
make mount-local PATH=~/Projects/my-app

# Repository available at /projects/my-app in containers
# Changes persist to your local filesystem
```

#### Approach 3: Automated Workflow

```python
from harness.agent import AgentSession

session = AgentSession(
    agent_name="main",
    repository_url="https://github.com/user/my-app",
    repository_branch="feature/auth"
)

await session.execute("Add authentication to /users endpoint")
```

### Configuration

#### Environment Variables

```bash
# .env
EXTERNAL_REPO_URL=https://github.com/user/my-app
EXTERNAL_REPO_BRANCH=main
WORKSPACE_SUBDIR=projects
AUTO_LOAD_CLAUDE_MD=true
```

#### Docker Compose Override

```bash
# Create override file
cp docker-compose.override.yml.example docker-compose.override.yml

# Edit to add your repositories
# volumes:
#   - ~/Projects/my-app:/projects/my-app:delegated
```

### Best Practices

#### 1. Use CLAUDE.md in Target Repository

```markdown
# Project: My App
- Language: Python 3.12
- Framework: FastAPI
- Test command: pytest tests/
- Build command: make build
```

#### 2. Configure Git Credentials

```bash
# .env
GIT_USER_NAME=Claude Agent
GIT_USER_EMAIL=agent@claude.local
```

#### 3. Use Sub-Agents

```python
# Reviewer for read-only analysis
reviewer = AgentSession(
    agent_name="reviewer",
    repository_url="https://github.com/user/my-app"
)

# Main agent for modifications
main = AgentSession(
    agent_name="main",
    repository_url="https://github.com/user/my-app"
)
```

### Examples

See `examples/` directory for complete workflows:
- `simple-feature/` - Clone and test
- `bug-fix/` - Fix GitHub issues
- `full-project/` - Multi-repository coordination

### Troubleshooting

**Issue**: Repository not found
```bash
# Check URL is accessible
git ls-remote https://github.com/user/my-app

# Check SSH key for private repos
ssh -T git@github.com
```

**Issue**: Permission denied
```bash
# Ensure proper permissions on mounted directories
chmod -R 755 ~/Projects/my-app
```

**Issue**: CLAUDE.md not loaded
```bash
# Verify setting in .env
AUTO_LOAD_CLAUDE_MD=true

# Check CLAUDE.md exists in repository
ls /projects/my-app/CLAUDE.md
```
```

#### 6.2 README.md Updates
**File**: `README.md`

Add new section after "🔧 Configuration":

```markdown
## 🔗 Working with External Repositories

The harness supports multiple ways to work with external codebases, both local and remote.

### Quick Examples

**Clone and work on remote repository**:
```bash
make clone-repo REPO=https://github.com/user/my-app BRANCH=main
make work-on REPO=https://github.com/user/my-app TASK="Fix test failures"
```

**Mount local repository**:
```bash
make mount-local PATH=~/Projects/my-app
# Your local repository is now available at /projects/my-app in containers
```

**Programmatic workflow**:
```python
from harness.agent import AgentSession

session = AgentSession(
    agent_name="main",
    repository_url="https://github.com/user/my-app"
)

await session.execute("Add authentication middleware")
```

### Three Approaches

| Approach | Best For | Setup |
|----------|----------|-------|
| **Git Clone** | Quick experiments, testing | Zero config |
| **Volume Mount** | Local development | Add to docker-compose.override.yml |
| **Automated** | Production, CI/CD | Python API |

See [CLAUDE.md](./CLAUDE.md#working-with-external-repositories) for detailed guides and examples.
```

---

## File Changes

### New Files (13)

1. `PLAN.md` - This document
2. `scripts/clone_repo.py` - Clone repository utility
3. `scripts/mount_local_repo.sh` - Volume mounting helper
4. `scripts/work_on_repo.py` - Unified workflow script
5. `src/utils/repository.py` - Repository management utilities
6. `docker-compose.override.yml.example` - Template for user overrides
7. `examples/simple-feature/clone_and_test.py` - Example workflow
8. `examples/simple-feature/README.md` - Example documentation
9. `examples/bug-fix/analyze_and_fix.py` - Bug fix workflow
10. `examples/bug-fix/README.md` - Bug fix documentation
11. `examples/full-project/multi_repo_coordinator.py` - Multi-repo example
12. `examples/full-project/README.md` - Multi-repo documentation
13. `examples/refactoring/refactor_workflow.py` - Refactoring example

### Modified Files (5)

1. `.env.example` - Add external repository configuration
2. `.gitignore` - Ignore docker-compose.override.yml and workspace/projects/
3. `src/harness/config.py` - Add repository configuration fields
4. `src/harness/agent.py` - Add repository URL support to AgentSession
5. `Makefile` - Add repository operation targets
6. `CLAUDE.md` - Add "Working with External Repositories" section
7. `README.md` - Add quick reference for external repositories

### Directory Structure After Implementation

```
claudeagentsdk-harness/
├── PLAN.md                             # NEW - This document
├── scripts/                            # NEW - Utility scripts
│   ├── clone_repo.py
│   ├── mount_local_repo.sh
│   └── work_on_repo.py
├── src/
│   ├── harness/
│   │   ├── agent.py                    # MODIFIED
│   │   └── config.py                   # MODIFIED
│   └── utils/
│       ├── __init__.py
│       └── repository.py               # NEW
├── examples/
│   ├── simple-feature/
│   │   ├── clone_and_test.py          # NEW
│   │   └── README.md                  # NEW
│   ├── bug-fix/
│   │   ├── analyze_and_fix.py         # NEW
│   │   └── README.md                  # NEW
│   ├── refactoring/
│   │   ├── refactor_workflow.py       # NEW
│   │   └── README.md                  # NEW
│   └── full-project/
│       ├── multi_repo_coordinator.py  # NEW
│       └── README.md                  # NEW
├── docker-compose.override.yml.example # NEW
├── .env.example                        # MODIFIED
├── .gitignore                          # MODIFIED
├── Makefile                            # MODIFIED
├── CLAUDE.md                           # MODIFIED
└── README.md                           # MODIFIED
```

---

## Success Criteria

### Functional Requirements

- [ ] User can clone any public repository with single command
- [ ] User can mount local repository with volume binding
- [ ] User can run agent on external repository via Python API
- [ ] All three approaches work independently and can be combined
- [ ] CLAUDE.md auto-loaded from target repositories
- [ ] Git credentials configured automatically
- [ ] Examples demonstrate all approaches

### Quality Requirements

- [ ] All code follows existing harness standards (ruff, mypy, pytest)
- [ ] Comprehensive error handling for git operations
- [ ] Logging for all repository operations
- [ ] Unit tests for repository utilities (80%+ coverage)
- [ ] Integration tests for each approach
- [ ] Documentation complete with examples

### Compatibility Requirements

- [ ] Changes are backward compatible
- [ ] Existing workflows unaffected
- [ ] No breaking changes to public APIs
- [ ] Works on macOS (OrbStack) and Linux (Docker)

### User Experience Requirements

- [ ] Clear error messages for common issues
- [ ] Helpful defaults (main branch, shallow clone)
- [ ] Makefile targets for common operations
- [ ] Examples are copy-paste ready
- [ ] Documentation includes troubleshooting section

---

## Timeline & Scope

### Estimated Effort

**Total**: ~800-1000 lines of new code + documentation

| Phase | Files | LOC | Time Estimate |
|-------|-------|-----|---------------|
| Phase 1: Configuration | 2 modified | ~100 | 2 hours |
| Phase 2: Docker | 2 new | ~50 | 1 hour |
| Phase 3: Scripts | 3 new | ~250 | 3 hours |
| Phase 4: Examples | 9 new | ~300 | 3 hours |
| Phase 5: Makefile | 1 modified | ~50 | 1 hour |
| Phase 6: Documentation | 2 modified | ~200 | 2 hours |
| Testing & Validation | - | ~150 | 3 hours |
| **Total** | **18 files** | **~1100** | **15 hours** |

### Implementation Order

**Recommended sequence**:

1. **Phase 1** - Core configuration (foundation)
2. **Phase 3** - Repository utilities (required for examples)
3. **Phase 2** - Docker overrides (enables volume mounting)
4. **Phase 4** - Example workflows (validates utilities)
5. **Phase 5** - Makefile targets (user convenience)
6. **Phase 6** - Documentation (after testing)

### Milestones

**M1: Core Functionality** (Phases 1-3)
- ✅ Configuration in place
- ✅ Repository utilities working
- ✅ Can clone and mount repositories

**M2: User-Facing Features** (Phases 4-5)
- ✅ Example workflows complete
- ✅ Makefile commands available
- ✅ All three approaches working

**M3: Production Ready** (Phase 6 + Testing)
- ✅ Documentation complete
- ✅ Tests passing (80%+ coverage)
- ✅ Ready for use

---

## Next Steps

1. **Review this plan** - Verify approach aligns with requirements
2. **Confirm scope** - Adjust if needed before implementation
3. **Approve to proceed** - Grant permission to begin coding
4. **Phase-by-phase implementation** - Build incrementally with testing
5. **Final validation** - Test all approaches end-to-end

---

## Questions for Review

Before proceeding, please consider:

1. **Scope**: Is this the right level of functionality?
2. **Approaches**: Are all three approaches valuable, or focus on 1-2?
3. **Priority**: Which examples are most important?
4. **Breaking Changes**: Any concerns about API modifications?
5. **Security**: Additional considerations for private repositories?
6. **Testing**: Any specific test scenarios to cover?

---

**Status**: Awaiting approval to begin implementation
