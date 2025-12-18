# Claude-UI Integration Guide

This document outlines integration approaches for connecting **claude-ui** (React frontend) with the harness interactive mode.

**Status**: Planning / Documentation
**Last Updated**: December 2025

---

## Overview

[claude-ui](https://gitlab.provectus.com/provectus-ai-eng/claude-ui) is a React-based chat interface similar to Claude.ai, featuring conversation management, artifact rendering, and streaming responses. Integrating it with the harness enables a web-based frontend for interactive development sessions.

### Why Integrate?

| Benefit | Description |
|---------|-------------|
| **Web Access** | Access harness agents from browser instead of CLI |
| **Rich UI** | Syntax highlighting, artifact preview, conversation history |
| **Collaboration** | Multiple users can access shared harness instance |
| **Harness Features** | Expose subagents, skills, MCP servers through UI |

### Compatibility Summary

**High compatibility** - Both systems use SSE-style streaming, making integration straightforward.

---

## Architecture Comparison

| Aspect | Claude-UI | Harness | Compatible? |
|--------|-----------|---------|-------------|
| **Streaming** | Server-Sent Events (SSE) | AsyncGenerator | ✅ Yes |
| **Message format** | JSON events | SDK Message types | ⚠️ Needs serializer |
| **Auth** | Bearer + CSRF tokens | None | ⚠️ Needs implementation |
| **Conversations** | SQLite database | Checkpoint files | ⚠️ Different storage |
| **Models** | Claude API | Claude SDK | ✅ Same models |
| **Port** | 3001 (Express.js) | 8080 (health server) | ✅ Configurable |

### Claude-UI Stack
- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: Express.js + SQLite (port 3001)
- **Streaming**: SSE via `fetch()` with ReadableStream
- **API Base**: Hardcoded `http://localhost:3001/api`

### Harness Stack
- **Core**: `AgentSession.execute()` → `AsyncGenerator[Message, None]`
- **HTTP**: aiohttp health server (port 8080)
- **Dependencies**: FastAPI in pyproject.toml (available but unused)
- **SDK Messages**: SystemMessage, AssistantMessage, ResultMessage

---

## High-Level Integration Approach

### Why SSE Streaming Works

Both systems stream responses token-by-token:

**Claude-UI expects**:
```json
{"type": "start", "messageId": "msg_xyz"}
{"type": "content", "text": "Hello"}
{"type": "content", "text": " world"}
{"type": "done"}
```

**Harness provides**:
```python
async for message in session.execute(prompt):
    # AssistantMessage with TextBlock, ToolUseBlock, etc.
    yield message
```

The async generator pattern maps naturally to SSE events.

---

## Option A: Harness API Adapter (Recommended)

Add FastAPI endpoints to harness that speak Claude-UI's protocol.

```
┌─────────────────┐       ┌─────────────────────────────────────┐
│   Claude-UI     │       │         Harness Container           │
│   (React App)   │       │                                     │
│                 │  SSE  │  ┌─────────────┐  ┌──────────────┐  │
│  API_BASE ──────┼───────┼─►│ api.py      │──│ AgentSession │  │
│  localhost:8080 │       │  │ (FastAPI)   │  │ .execute()   │  │
│                 │       │  └─────────────┘  └──────────────┘  │
└─────────────────┘       └─────────────────────────────────────┘
```

### Pros
- Minimal Claude-UI changes (just configure API_BASE)
- Leverage existing harness infrastructure (checkpoints, MCP servers, agents)
- Single deployment (harness container serves both API and agent)
- Full access to harness features (subagents, skills, autonomous mode)

### Cons
- Loses Claude-UI's SQLite features (full-text search, export, sharing)
- Need to implement conversation persistence in harness
- Some features won't work (artifact versioning, message branching)

### Implementation Steps
1. Create `src/harness/api.py` with FastAPI router
2. Add `src/harness/serializers.py` for SDK Message → JSON
3. Implement SSE streaming endpoint matching Claude-UI's format
4. Add conversation storage (extend checkpoints or add simple SQLite)
5. Configure Claude-UI to point to harness port

---

## Option B: Replace Claude-UI Backend

Fork Claude-UI and integrate harness directly into its backend.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Integrated Application                        │
│                                                                  │
│  ┌─────────────────┐       ┌─────────────────────────────────┐  │
│  │  Claude-UI      │       │       Harness Backend            │  │
│  │  Frontend       │       │                                  │  │
│  │  (React)        │ SSE   │  ┌───────────┐  ┌─────────────┐ │  │
│  │                 │───────┼─►│ Modified  │──│ AgentSession│ │  │
│  │                 │       │  │ routes.js │  │             │ │  │
│  └─────────────────┘       │  └───────────┘  └─────────────┘ │  │
│                            └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Pros
- Keep all Claude-UI features (SQLite, search, export, artifacts, branching)
- Tighter integration - can add harness-specific UI elements
- Single codebase for UI + agent logic
- Expose harness features in UI (agent selector, skill browser)

### Cons
- Larger scope - need to modify Claude-UI backend significantly
- Two repos to maintain (or merge into one)
- More complex deployment (Node.js + Python)
- Claude-UI's Anthropic SDK calls need replacing with harness SDK calls

### Implementation Steps
1. Fork claude-ui repo
2. Modify `server/routes/messages.js` to call harness instead of Anthropic SDK
3. Add Python-to-Node bridge (subprocess or gRPC)
4. Keep SQLite for conversation/artifact storage
5. Add harness-specific UI components

---

## Comparison

| Factor | Option A (Adapter) | Option B (Replace) |
|--------|-------------------|-------------------|
| **Effort** | Lower (~2-3 weeks) | Higher (~4-6 weeks) |
| **Claude-UI changes** | Minimal (config only) | Significant (backend) |
| **Feature parity** | Partial | Full |
| **Deployment** | Simpler (one container) | Complex (Node + Python) |
| **Maintainability** | Easier | Harder (two systems) |

**Recommendation**: Start with **Option A** for faster integration, consider Option B for production deployment with full features.

---

## Technical Specification

### 1. Required API Endpoints

Claude-UI expects these endpoints from its backend:

| Endpoint | Method | Claude-UI Usage | Harness Implementation |
|----------|--------|-----------------|------------------------|
| `/api/conversations` | GET | List conversations | Read from storage |
| `/api/conversations` | POST | Create conversation | Create session |
| `/api/conversations/:id/messages` | GET | Fetch history | Read from storage |
| `/api/conversations/:id/messages` | POST | Send message (SSE) | `session.execute()` |
| `/api/auth/login` | POST | Authentication | Optional |

### 2. Message Serialization

**SDK Message Types → JSON**:

```python
# src/harness/serializers.py

def serialize_message(message: Message) -> dict:
    """Convert SDK message to Claude-UI JSON format."""

    if isinstance(message, AssistantMessage):
        return {
            "type": "assistant",
            "blocks": [serialize_block(b) for b in message.content]
        }

    elif isinstance(message, ResultMessage):
        return {
            "type": "result",
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
            "cost": message.total_cost_usd
        }

def serialize_block(block) -> dict:
    if isinstance(block, TextBlock):
        return {"type": "text", "content": block.text}

    elif isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "name": block.name,
            "input": block.input
        }
```

### 3. SSE Streaming Protocol

**Response headers**:
```python
headers = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}
```

**Event format**:
```
data: {"type": "start", "messageId": "msg_123"}\n\n
data: {"type": "content", "text": "Hello"}\n\n
data: {"type": "content", "text": " world"}\n\n
data: {"type": "done"}\n\n
```

**FastAPI implementation sketch**:
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

@app.post("/api/conversations/{conv_id}/messages")
async def send_message(conv_id: str, request: MessageRequest):

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'messageId': msg_id})}\n\n"

        async for message in session.execute(request.content):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield f"data: {json.dumps({'type': 'content', 'text': block.text})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 4. Conversation State Management

**Options**:

| Approach | Pros | Cons |
|----------|------|------|
| **Extend checkpoints** | Already implemented | Limited query capabilities |
| **Add SQLite** | Rich queries, search | Another dependency |
| **In-memory + file** | Simple | Lost on restart |

**Recommended**: Add simple SQLite for conversation metadata, use checkpoints for agent state.

### 5. Configuration Changes

**Claude-UI** (`src/contexts/ChatContext.jsx`):
```javascript
// Change from hardcoded:
const API_BASE = 'http://localhost:3001/api'

// To environment variable:
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'
```

**Harness** (`.env`):
```bash
# Enable API server
API_ENABLED=true
API_PORT=8080
API_CORS_ORIGINS=http://localhost:5173
```

---

## Implementation Roadmap

### Phase 1: API Layer (~1 week)
- [ ] Create `src/harness/api.py` with FastAPI router
- [ ] Add message serializer for SDK → JSON conversion
- [ ] Implement SSE streaming endpoint
- [ ] Session management for concurrent conversations
- [ ] CORS middleware configuration

### Phase 2: State Management (~1 week)
- [ ] Conversation storage (SQLite or extended checkpoints)
- [ ] Message history retrieval
- [ ] Artifact extraction from AssistantMessages

### Phase 3: Integration Testing (~1 week)
- [ ] Configure Claude-UI API_BASE
- [ ] End-to-end message flow testing
- [ ] Error handling and retry logic
- [ ] Performance validation

---

## Open Questions

1. **Authentication**: Required for multi-user, or assume single-user local deployment?
2. **Storage**: SQLite (like Claude-UI) or extend checkpoint system?
3. **Multi-conversation**: Support multiple concurrent conversations per user?
4. **Artifacts**: Extract and store artifacts, or pass through to UI?
5. **Harness features**: Expose agent/skill selection in UI?

---

## References

- [Claude-UI Repository](https://gitlab.provectus.com/provectus-ai-eng/claude-ui)
- [Harness Interactive Mode](../src/harness/interactive.py)
- [AgentSession API](../src/harness/agent.py)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
