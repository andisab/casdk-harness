# Lost Changes - 2025-11-18

**Context**: During debugging of interactive mode failure, changes were lost via `git checkout` without being stashed or committed.

## What Was Lost

### 1. src/harness/agent.py

Repository context switching code (can be reconstructed):

- Instance variables: `self.current_repo`, `self.current_cwd`
- Method: `set_working_repository(repo_name)` 
- Method: `reset_to_harness()`
- Changed `cwd` parameter to use dynamic `self.current_cwd`
- Added "Skill" to allowed_tools
- **(POSSIBLY BREAKING)** Added `setting_sources=["user", "project"]`

### 2. docker-compose.yml  

Mount location changes:
- Changed `./.claude:/app/.claude:ro` → `./.claude:/workspace/.claude:ro` for all agents

### 3. agents/main/Dockerfile

- Removed symlink: `ln -s /app/.claude /workspace/.claude`  
- Added: `mkdir -p /workspace/projects`

## Recovery Plan

1. Test if original configuration works
2. If yes, our changes broke it - find minimal breaking change
3. Reconstruct changes carefully with testing at each step

## Changes Still Preserved

These were NOT lost:
- `src/harness/config.py` - projects_dir field ✓
- `.claude/CLAUDE.md` - documentation ✓
- `README.md` - documentation ✓  
- `.claude/settings.json` - permission patterns (may need revert)
- `.claude/hooks/hooks.json` - disabled hooks (may need revert)
