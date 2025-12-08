# Context Window Management Strategies

## Overview

This document explores approaches for managing context window limits in long-running autonomous agent sessions. The goal is to ensure sessions end cleanly before context exhaustion, with proper state preservation for seamless continuation.

## Current State

### What Exists
- **`max_turns=1000`** - Hard limit on conversation turns (not token-based)
- **Session restart triggers**: User quit, task complete, all tasks done
- **No token tracking** - System doesn't know context window usage
- **No automatic session restart** when approaching limits

### Problems
1. Sessions can run until context exhausts, causing incomplete work
2. No warning to agent about approaching limits
3. No graceful handoff between sessions
4. Context files may not be updated before forced termination

---

## Proposed Approaches

### Approach 1: Turn-Based Warnings (Simple)

**Concept**: Use turn count as proxy for context usage. Inject warnings at thresholds.

**Implementation**:
```python
# In autonomous.py, during message loop
if session_entry.total_turns >= 30:
    # Inject warning into next prompt
    warning = "[SYSTEM: 30+ turns reached. Consider wrapping up.]"

if session_entry.total_turns >= 50:
    warning = "[SYSTEM: 50+ turns. Update context files and end session soon.]"
```

**Prompt additions** (continuation.md):
```markdown
## Context Management

Watch for system warnings about turn count:
- **30+ turns**: Consider wrapping up current work unit
- **50+ turns**: Finish current subtask, update context files, commit
- **70+ turns**: Stop new work, save state, signal session end

When you see `[SYSTEM: ... turns]`, prioritize:
1. Committing working code
2. Updating `/workspace/context/` files
3. Signaling `[SESSION_ENDING: context_limit]`
```

**Pros**:
- Simple to implement
- No API changes needed
- Agent can self-regulate

**Cons**:
- Turn count is imprecise proxy for tokens
- Some turns use few tokens, others many
- Doesn't account for tool output size

---

### Approach 2: Token Budget Tracking (Accurate)

**Concept**: Track actual token usage from API responses. Calculate remaining budget.

**Implementation**:
```python
# Track in AgentSession
class AgentSession:
    def __init__(self, ...):
        self.token_budget = 180_000  # ~90% of 200k context
        self.tokens_used = 0

    async def execute(self, prompt: str):
        async for message in self._execute_with_tracking(prompt):
            # Extract usage from response
            if hasattr(message, 'usage'):
                self.tokens_used += message.usage.total_tokens

            # Check budget
            if self.tokens_used > self.token_budget * 0.8:
                yield self._create_warning_message()

            yield message
```

**Warning injection**:
```python
def _create_warning_message(self) -> dict:
    remaining = self.token_budget - self.tokens_used
    percent_used = (self.tokens_used / self.token_budget) * 100
    return {
        "type": "system",
        "content": f"[CONTEXT_WARNING: {percent_used:.0f}% used, ~{remaining:,} tokens remaining]"
    }
```

**Pros**:
- Accurate measurement
- Predictable session boundaries
- Can calculate remaining work capacity

**Cons**:
- Requires parsing SDK responses for usage
- More complex implementation
- May not have access to all token counts

---

### Approach 3: Proactive Session Boundaries (Structured)

**Concept**: Define explicit work units that fit within safe context budgets.

**Implementation**:
- Each task gets a "complexity score" in task_list.json
- System estimates context needed per task
- Sessions are pre-planned to fit within limits

**Task list extension**:
```json
{
  "id": "task-003",
  "title": "Implement wall kicks",
  "complexity": "medium",
  "estimated_turns": 25,
  "context_budget": 50000
}
```

**Session planning**:
```python
def plan_session_tasks(task_list, available_budget=150000):
    """Select tasks that fit within context budget."""
    planned = []
    remaining_budget = available_budget

    for task in task_list.get_pending_tasks():
        if task.context_budget <= remaining_budget:
            planned.append(task)
            remaining_budget -= task.context_budget

    return planned
```

**Pros**:
- Predictable session boundaries
- Better planning for multi-task sessions
- Can optimize task ordering

**Cons**:
- Requires accurate complexity estimation
- More upfront configuration
- May under-utilize context window

---

### Approach 4: Checkpoint-Based Recovery (Resilient)

**Concept**: Frequent automatic checkpoints allow recovery from any point.

**Implementation**:
```python
# Enhanced checkpoint manager
class ContextAwareCheckpointManager:
    def __init__(self):
        self.checkpoint_interval_turns = 10  # Every 10 turns
        self.last_checkpoint_turn = 0

    def should_checkpoint(self, current_turn: int) -> bool:
        return current_turn - self.last_checkpoint_turn >= self.checkpoint_interval_turns

    def save_checkpoint(self, session_state: dict):
        checkpoint = {
            "turn": session_state["turn"],
            "tokens_used": session_state.get("tokens_used", 0),
            "current_task": session_state["current_task"],
            "git_sha": self._get_current_commit(),
            "context_files_hash": self._hash_context_files(),
            "conversation_summary": self._summarize_recent(session_state["messages"])
        }
        # Save to /memory/checkpoints/
```

**Recovery**:
```python
def resume_from_checkpoint(checkpoint_path: Path):
    checkpoint = load_checkpoint(checkpoint_path)

    # Restore git state if needed
    if checkpoint["git_sha"] != get_current_commit():
        git_checkout(checkpoint["git_sha"])

    # Build resume prompt with summary
    return f"""
Resuming from checkpoint (turn {checkpoint['turn']}).

Recent context:
{checkpoint['conversation_summary']}

Continue with: {checkpoint['current_task']}
"""
```

**Pros**:
- Resilient to crashes
- Can resume from any point
- Preserves work progress

**Cons**:
- Storage overhead
- Checkpoint management complexity
- Summary quality affects resume quality

---

### Approach 5: Hybrid (Recommended)

**Concept**: Combine multiple approaches for robustness.

**Components**:
1. **Turn-based warnings** (Approach 1) - Simple, always active
2. **Token tracking** (Approach 2) - When available from SDK
3. **Frequent checkpoints** (Approach 4) - Safety net

**Implementation phases**:

| Phase | Component | Effort |
|-------|-----------|--------|
| 1 | Turn-based warnings at 30/50/70 turns | Low |
| 2 | Checkpoint every 10 turns | Medium |
| 3 | Token tracking if SDK exposes usage | Medium |
| 4 | Task complexity estimation | High |

**Recommended first step**:
```python
# autonomous.py - Add to message loop
TURN_THRESHOLDS = {
    30: "Consider wrapping up current work unit.",
    50: "Finish current subtask and update context files.",
    70: "Stop new work. Save state and end session.",
}

async def _run_continuation_session(self, ...):
    ...
    for turn, message in enumerate(session.execute(...)):
        if turn in TURN_THRESHOLDS:
            self.console.print(f"[yellow][SYSTEM: {TURN_THRESHOLDS[turn]}][/]")
        ...
```

---

## Signal Protocol

Define clear signals for session state changes:

| Signal | Meaning | Action |
|--------|---------|--------|
| `[SESSION_ENDING: context_limit]` | Context running low | Save state, end gracefully |
| `[SESSION_ENDING: task_complete]` | Task finished | Update progress, may continue |
| `[SESSION_ENDING: blocked]` | Cannot proceed | Document blocker, end |
| `[CHECKPOINT_SAVED]` | State preserved | Continue working |

---

## Context File Maintenance

Regardless of approach, context files must be maintained:

**On session start**:
```python
# Read all context files
context = {
    "architecture": read_file("/workspace/context/architecture.md"),
    "decisions": read_file("/workspace/context/decisions.md"),
    "issues": read_file("/workspace/context/issues.md"),
    "next_steps": read_file("/workspace/context/next-steps.md"),
}
```

**On session end** (or warning threshold):
```python
# Ensure context is saved
def save_session_context(session_state):
    # Update decisions.md (append-only)
    if session_state.get("new_decisions"):
        append_to_file("/workspace/context/decisions.md",
                       format_decisions(session_state["new_decisions"]))

    # Update issues.md
    update_file("/workspace/context/issues.md",
                format_issues(session_state.get("current_issues", [])))

    # Update next-steps.md
    write_file("/workspace/context/next-steps.md",
               format_next_steps(session_state.get("next_focus")))
```

---

## Decision Points

Before implementing, clarify:

1. **SDK token visibility**: Does Claude Agent SDK expose token usage per message?
2. **Checkpoint storage**: How much disk space for checkpoints? Auto-cleanup policy?
3. **Turn thresholds**: What turn counts trigger warnings? (30/50/70 suggested)
4. **Session restart**: Should harness auto-restart or wait for user?
5. **Recovery UI**: How does user choose checkpoint to resume from?

---

## Next Steps

1. **Phase 1** (Low effort): Add turn-based warnings to continuation mode
2. **Phase 2** (Medium effort): Implement checkpoint-based recovery
3. **Phase 3** (Investigation): Determine if SDK exposes token usage
4. **Phase 4** (If needed): Add task complexity estimation

---

## References

- Claude context window: 200,000 tokens
- Safe operating range: ~150,000-180,000 tokens (75-90%)
- Average turn size: ~2,000-5,000 tokens (varies widely)
- Estimated safe turns: 30-90 depending on complexity
