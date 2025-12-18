# Multi-Agent Coordination Protocol - TODO

> **Status**: Shelved for future implementation
> **Created**: December 2025
> **Priority**: Low (Phase 2+ feature)

## Summary

Create a **coordination protocol** for peer-to-peer communication between the three Docker container agent instances (main, reviewer, tester) via Redis. This is separate from the internal orchestrator-worker pattern that main-agent already uses with SDK subagents.

**Architecture Clarification:**
- **Within main-agent**: Uses Task tool to spawn SDK subagents (orchestrator-worker, already working)
- **Between containers**: Peer-to-peer coordination via Redis (this plan)

---

## Research Background

This section synthesizes research on best practices for multi-agent LLM coordination.

---

## Key Findings from Industry Research

### 1. Orchestrator-Worker Pattern (Anthropic's Recommended Approach)

From [Anthropic's Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system):

> "Multi-agent systems excel especially for breadth-first queries that involve pursuing multiple independent directions simultaneously. A multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2%."

**Key Elements:**
- **Lead/Orchestrator Agent**: Analyzes queries, develops strategy, spawns subagents
- **Specialized Workers**: Each receives an objective, output format, tool guidance, and clear task boundaries
- **External Memory**: Agents save plans/results externally rather than passing through conversation history

### 2. Handoff Patterns

From [How Agent Handoffs Work](https://towardsdatascience.com/how-agent-handoffs-work-in-multi-agent-systems/) and [AI Agent Orchestration Best Practices](https://skywork.ai/blog/ai-agent-orchestration-best-practices-handoffs/):

| Pattern | Description | Best For |
|---------|-------------|----------|
| **Agent-as-Tool** | Main agent calls sub-agents like tools, incorporates results | Simple workflows, single control thread |
| **Sequential Handoff** | Relay race - agents pass control as task progresses | Pipeline workflows |
| **Parallel Workers** | Orchestrator spawns multiple workers simultaneously | Breadth-first exploration |
| **Consumer Groups** | Load-balanced message consumption | High-throughput scenarios |

### 3. Critical Best Practices

**Structured Handoff Contracts:**
> "Free-text handoffs are the main source of context loss. Treat inter-agent transfer like a public API: use JSON Schema-based structured outputs."

**Context Management:**
- Agents should summarize completed work before handing off
- Store essential information in external memory
- Pass lightweight references, not full outputs
- Spawn fresh subagents with clean contexts when approaching limits

**Avoiding Common Pitfalls:**
- Hard caps on steps/costs to prevent infinite loops
- Termination criteria for each task
- Periodic checkpoints for recovery
- Avoid mutable shared state between concurrent agents

---

## Existing Infrastructure

The codebase already has **production-ready Redis infrastructure** in `src/harness/messaging.py`:

### Available Primitives

```python
# Publishing task results
session.publish_task_result(task_id, result)  # → Redis stream "agent:tasks"

# Waiting for dependencies
result = await session.wait_for_dependency(agent_name, task_id, timeout)

# Direct stream operations
broker.publish_result(agent_id, result, stream_name)
messages = broker.consume_results(stream_name, last_id, count, block)

# Consumer groups for load balancing
broker.create_consumer_group(stream, group)
broker.read_group(stream, group, consumer)
broker.acknowledge_message(stream, group, msg_id)
```

### Message Format (Already Implemented)

```json
{
  "message_id": "1234567890000-0",
  "agent_id": "reviewer",
  "timestamp": 1234567890.123,
  "content": {
    "task_id": "review-task-001",
    "status": "success",
    "data": { ... }
  }
}
```

---

## Recommended Approach: Prompt-Based Coordination Protocol

Rather than building complex orchestration code, the most practical approach is to **embed coordination instructions directly into agent prompts**. This leverages existing infrastructure while keeping the system simple.

### Coordination Protocol for Agent Prompts

Each agent's system prompt should include a **"Multi-Agent Coordination"** section defining:

1. **Their role** in the multi-agent system
2. **How to publish results** when they complete tasks
3. **How to check for dependencies** from other agents
4. **Standard message formats** for consistency
5. **Handoff procedures** for task transitions

---

## Implementation Options

### Option A: Prompt-Only (Minimal Implementation)

**Add coordination sections to existing prompts:**
- `reviewer-agent.md` - How to receive review requests, publish findings
- `tester-agent.md` - How to receive test requests, publish results
- `main-interactivedev-agent.md` - How to request reviews/tests

**Pros**: No code changes, fast to implement
**Cons**: Relies on LLM following instructions consistently

### Option B: Prompt + Shared Protocol File (Recommended)

**Create a shared protocol document** that all agents reference:
- `src/harness/prompts/coordination-protocol.md` - Shared by all agents
- Append to each agent's prompt automatically in `_load_system_prompt()`

**Pros**: Single source of truth, consistent across agents
**Cons**: Small code change needed

### Option C: Full Orchestration Layer (Future)

**Build proper orchestration with task queue:**
- Task definition schema with dependencies
- Orchestrator service that assigns tasks
- Worker agents that pull from queue

**Pros**: Most robust, handles complex workflows
**Cons**: Significant implementation effort, higher token costs

---

## Implementation Plan (Option B)

### Phase 1: Create Coordination Protocol File

**New file**: `src/harness/prompts/coordination-protocol.md`

```markdown
# Inter-Container Agent Coordination Protocol

## Architecture Overview

This protocol governs communication between separate Docker container agent instances:
- **main-agent**: Primary development agent (may also use internal SDK subagents)
- **reviewer-agent**: Code review specialist
- **tester-agent**: Testing specialist

All three operate as **peers** - any agent can request work from any other.

## Communication Channel

All inter-agent communication uses Redis Streams via the `session` object:
- Stream: `agent:coordination`
- All agents can publish and consume from this stream

## Message Schema

Every message MUST follow this structure:

```json
{
  "request_id": "uuid-v4",
  "from_agent": "main|reviewer|tester",
  "to_agent": "main|reviewer|tester|all",
  "message_type": "request|response|broadcast",
  "task_type": "review|test|info|custom",
  "status": "pending|accepted|in_progress|completed|failed|rejected",
  "payload": {
    "title": "Brief description",
    "files": ["path/to/file.py"],
    "context": "Additional context",
    "priority": "low|normal|high",
    "data": {}
  },
  "timestamp": "ISO-8601"
}
```

## Standard Task Types

| Task Type | From | To | Purpose |
|-----------|------|-----|---------|
| `review` | any | reviewer | Request code review |
| `test` | any | tester | Request test writing/execution |
| `info` | any | any | Share information/status |
| `sync` | any | all | Broadcast state synchronization |

## Fallback: File-Based Coordination

When Redis is unavailable, use `/workspace/context/coordination/`:
- `requests.json`: Pending requests
- `responses.json`: Completed responses
- `status.json`: Agent status updates
```

### Phase 2: Update Agent.py to Load Protocol

**Modify**: `src/harness/agent.py:_load_system_prompt()`

Add logic to append coordination protocol when running in multi-agent mode:
- Check if `AGENT_NAME` is set (indicates container mode)
- Load and append `coordination-protocol.md`

```python
def _load_system_prompt(self) -> str:
    # ... existing prompt loading ...

    # Append coordination protocol for container agents
    agent_name = os.environ.get("AGENT_NAME")
    if agent_name in ["main", "reviewer", "tester"]:
        protocol_file = Path(__file__).parent / "prompts" / "coordination-protocol.md"
        if protocol_file.exists():
            system_prompt += "\n\n---\n\n" + protocol_file.read_text()
            logger.info("Appended coordination protocol", agent_name=agent_name)

    return system_prompt
```

### Phase 3: Add Role-Specific Context to Each Agent Prompt

**Modify**: `src/harness/prompts/reviewer-agent.md`
- Add section: "Your Role in Multi-Agent Coordination"
- Specify: Listens for `task_type=review` requests
- Specify: Publishes responses with findings

**Modify**: `src/harness/prompts/tester-agent.md`
- Add section: "Your Role in Multi-Agent Coordination"
- Specify: Listens for `task_type=test` requests
- Specify: Publishes responses with test results

**Modify**: `src/harness/prompts/main-interactivedev-agent.md`
- Add section: "Requesting Help from Peer Agents"
- Specify: How to request reviews/tests from container peers

### Phase 4: Update Documentation

**Modify**: `CLAUDE.md`
- Add section explaining inter-container coordination
- Document the coordination protocol
- Distinguish from internal SDK subagents

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/harness/prompts/coordination-protocol.md` | CREATE | Shared peer-to-peer protocol |
| `src/harness/agent.py` | MODIFY | Append protocol to container agents |
| `src/harness/prompts/reviewer-agent.md` | MODIFY | Add role-specific coordination |
| `src/harness/prompts/tester-agent.md` | MODIFY | Add role-specific coordination |
| `src/harness/prompts/main-interactivedev-agent.md` | MODIFY | Add peer request instructions |
| `CLAUDE.md` | MODIFY | Document multi-agent coordination |

---

## Testing Plan

1. Start multi-agent mode: `make up-multi`
2. Verify all agents load the coordination protocol (check logs)
3. Manually test message publishing/consuming via Redis CLI
4. Optional: Create integration test for message flow

---

## Sources

- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic: Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Towards Data Science: How Agent Handoffs Work in Multi-Agent Systems](https://towardsdatascience.com/how-agent-handoffs-work-in-multi-agent-systems/)
- [SkyWork: Best Practices for Multi-Agent Orchestration and Reliable Handoffs](https://skywork.ai/blog/ai-agent-orchestration-best-practices-handoffs/)
- [Microsoft Azure: AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [OpenAI Cookbook: Multi-Agent Portfolio Collaboration](https://cookbook.openai.com/examples/agents_sdk/multi-agent-portfolio-collaboration/multi_agent_portfolio_collaboration)
