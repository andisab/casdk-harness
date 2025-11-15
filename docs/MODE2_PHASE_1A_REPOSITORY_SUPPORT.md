# MODE2 Phase 1A: Repository Support

**Phase**: 1A - Repository Support Infrastructure
**Status**: Planning Phase
**Last Updated**: November 13, 2024
**Dependencies**: Phase 0.7 (Enhanced Observability) complete ✅
**Blocks**: Phase 2A (Foundation) - Objective YAML requires `workspace_path`

## Documentation Navigation

- [MODE2_OVERVIEW.md](./MODE2_OVERVIEW.md) - Executive summary and architecture
- **MODE2_PHASE_1A_REPOSITORY_SUPPORT.md** (this file) - Repository management infrastructure
- [MODE2_PHASE_2A_FOUNDATION.md](./MODE2_PHASE_2A_FOUNDATION.md) - Foundation components
- [MODE2_PHASE_2B_ORCHESTRATION.md](./MODE2_PHASE_2B_ORCHESTRATION.md) - Multi-agent orchestration
- [MODE2_PHASE_2C_EXECUTION.md](./MODE2_PHASE_2C_EXECUTION.md) - Autonomous execution
- [MODE2_PHASE_2D_OBSERVABILITY.md](./MODE2_PHASE_2D_OBSERVABILITY.md) - Monitoring & observability

## Executive Summary

This phase implements comprehensive support for working with external repositories in the Claude Agent SDK Harness. This is **essential infrastructure** that enables both Mode 1 (interactive sessions) and Mode 2 (autonomous sessions) to work with user codebases beyond the default `./workspace` directory.

The implementation provides three complementary approaches:
1. **Git Clone** - Zero-config cloning into workspace
2. **Volume Mounting** - Direct access to local repositories via Docker volumes
3. **Automated Workflows** - Programmatic repository management via Python API

This infrastructure is a **prerequisite** for Mode 2's objective system, as the objective YAML's `environment.workspace_path` field depends on these repository management capabilities.

## Current State vs Requirements

### What Already Exists
- ✅ `cwd` parameter in `ClaudeAgentOptions` (agent.py line 210)
- ✅ Git MCP server for git operations
- ✅ Docker volume mounts for workspace
- ✅ Configurable workspace directory via `config.workspace_dir`
- ✅ Phase 0.7 (Enhanced Observability) complete

### What's Missing
- ❌ Configuration for external repositories
- ❌ Automated git clone workflows
- ❌ Dynamic volume mounting
- ❌ Example workflows for external repos
- ❌ Documentation and guides

## Mode 2 Integration

This repository support infrastructure is critical for Mode 2 autonomous sessions:

### How It Enables Mode 2

1. **Phase 2A (Foundation)**:
   - Objective YAML specifies `environment.workspace_path`
   - ObjectiveBuilder needs to know available repositories
   - Repository selection happens during Discussion phase

2. **Phase 2B (Orchestration)**:
   - Multi-agent coordination may span repositories
   - Task assignment considers repository context
   - Agent handoffs preserve repository state

3. **Phase 2C (Execution)**:
   - Autonomous execution starts in configured workspace
   - Checkpoints include repository state
   - Recovery restores to correct repository

4. **Three-Phase Workflow Integration**:
   - **Understanding**: Scan available repositories for context
   - **Discussion**: User selects target repository
   - **Execution**: Agent works in selected repository

### Example Objective YAML Usage
```yaml
# After Phase 1A implementation enables this:
environment:
  workspace_path: "/projects/my-app"  # Requires repository support
  models:
    main: "sonnet"
```

## Three Approaches

### Approach 1: Git Clone Into Workspace

**Best for**: Quick experiments, single-use tasks, simple testing

#### How It Works
1. Agent receives prompt with repository URL
2. Clones repository into `/workspace/projects/repo-name`
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
- ✅ Zero configuration required
- ✅ Works immediately with existing setup
- ✅ Repositories persist between sessions
- ❌ Workspace can get cluttered
- ❌ No isolation between projects
- ❌ Manual cleanup needed

### Approach 2: Volume Mounting (Recommended for Development)

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
    environment:
      - WORKSPACE_DIR=/projects/my-app
```

#### Pros & Cons
- ✅ Direct access to local repositories
- ✅ Changes persist outside container
- ✅ Git history preserved
- ✅ Can use local IDE simultaneously
- ❌ Requires docker-compose modification
- ❌ One repository per configuration

### Approach 3: Automated Workflows (Most Flexible)

**Best for**: Multi-project workflows, production deployments, CI/CD integration

#### How It Works
1. Python scripts manage repository lifecycle
2. Repositories cloned/mounted dynamically via API
3. Agent sessions configured programmatically
4. Clean separation between projects

#### Example Implementation
```python
from harness.utils.repository import clone_repository

async def work_on_repository(repo_url: str, task: str):
    # Clone repository
    repo_path = await clone_repository(
        url=repo_url,
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
```

#### Pros & Cons
- ✅ Fully automated
- ✅ Supports any repository
- ✅ Clean project separation
- ✅ Scriptable and composable
- ✅ Production-ready
- ❌ Requires custom scripting (but reusable)
- ❌ More complex setup initially

## Implementation Plan

### Phase 1: Configuration & Core Utilities

Add repository configuration to environment and config classes:
- Update `.env.example` with repository settings
- Extend `HarnessConfig` with repository fields
- Create `src/utils/repository.py` for git operations
- Update `AgentSession` to support repository URLs

### Phase 2: Docker & Orchestration

Enable volume mounting for local repositories:
- Create `docker-compose.override.yml.example` template
- Update `.gitignore` for user overrides
- Document volume mounting patterns

### Phase 3: Scripts & Automation

Provide utility scripts for common operations:
- `scripts/clone_repo.py` - Clone external repositories
- `scripts/mount_local_repo.sh` - Setup volume mounts
- `scripts/work_on_repo.py` - Unified workflow

### Phase 4: Example Workflows

Create examples demonstrating each approach:
- `examples/simple-feature/` - Clone and test workflow
- `examples/bug-fix/` - GitHub issue resolution
- `examples/full-project/` - Multi-repository coordination

### Phase 5: Makefile Integration

Add convenient Make targets:
```makefile
make clone-repo REPO=https://github.com/user/my-app
make mount-local PATH=~/Projects/my-app
make work-on REPO=... TASK="..."
make list-repos
make clean-repos
```

### Phase 6: Documentation

Update documentation with usage guides:
- Add "Working with External Repositories" to CLAUDE.md
- Update README.md with quick examples
- Create troubleshooting section

## Success Criteria

### Functional Requirements
- [ ] User can clone any public repository with single command
- [ ] User can mount local repository with volume binding
- [ ] User can run agent on external repository via Python API
- [ ] All three approaches work independently and can be combined
- [ ] CLAUDE.md auto-loaded from target repositories
- [ ] Git credentials configured automatically
- [ ] Examples demonstrate all approaches

### Mode 2 Integration Requirements
- [ ] Repository path configurable in objective YAML
- [ ] ObjectiveBuilder can list available repositories
- [ ] Repository context preserved in checkpoints
- [ ] Multiple agents can access same repository
- [ ] Repository state included in session reports

### Quality Requirements
- [ ] All code follows existing harness standards
- [ ] Comprehensive error handling for git operations
- [ ] Unit tests for repository utilities (80%+ coverage)
- [ ] Integration tests for each approach
- [ ] Documentation complete with examples

## Out of Scope

The following features are explicitly **NOT** part of Phase 1A:

### Deferred to Phase 3+
- **Multi-objective concurrent sessions** - Running multiple objectives simultaneously
- **Git worktrees** - Parallel development on different branches (see MODE2_OVERVIEW.md)
- **Repository access control** - Fine-grained permissions per agent
- **Multi-repository atomic commits** - Coordinated commits across repos
- **Remote repository caching** - Persistent cache of frequently used repos
- **Repository templates** - Pre-configured repository setups

### Not Planned
- **Private repository authentication UI** - Use environment variables
- **Repository browsing interface** - Use filesystem tools
- **Git GUI integration** - Command-line git only
- **Repository migration tools** - Manual process

## Timeline & Effort

**Total Estimated Effort**: ~15 hours, ~1100 lines of code

| Component | Files | LOC | Time |
|-----------|-------|-----|------|
| Configuration | 2 modified | ~100 | 2 hours |
| Docker Setup | 2 new | ~50 | 1 hour |
| Scripts | 3 new | ~250 | 3 hours |
| Examples | 9 new | ~300 | 3 hours |
| Makefile | 1 modified | ~50 | 1 hour |
| Documentation | 2 modified | ~200 | 2 hours |
| Testing | - | ~150 | 3 hours |

## Next Steps

After Phase 1A completion:

1. **Phase 2A (Foundation)** can proceed with:
   - ObjectiveBuilder using repository support
   - Objective YAML with `workspace_path`
   - Repository selection in Discussion phase

2. **Immediate Benefits**:
   - Mode 1 (interactive) users can work on their repos
   - Examples provide templates for common workflows
   - Foundation ready for Mode 2 objectives

3. **Future Enhancements** (Phase 3+):
   - Git worktrees for parallel development
   - Multi-repository objective coordination
   - Repository template library

## Implementation Order

The recommended implementation sequence:

**Phase Progression**:
```
Phase 0.7 (Observability) ✅
    ↓
Phase 1A (Repository Support) 👈 Current
    ↓
Phase 2A (Foundation)
    ↓
Phase 2B (Orchestration)
    ↓
Phase 2C (Execution)
    ↓
Phase 2D (Observability)
```

This ensures each phase builds on solid infrastructure from the previous phase.