>[toc]

# Claude Agent SDK Harness: Critical Success Factors

**Project**: claudeagentsdk-harness
**Date**: November 21, 2025
**Purpose**: Condensed troubleshooting learnings and operational requirements

---

## Critical Configuration Requirements

### 1. Valid Permission Mode (BLOCKING)

**Problem**: Using invalid permission mode causes 60-second timeout during SDK initialization.

**Valid Values**:
- `acceptEdits` - Auto-approve file edits (recommended default)
- `bypassPermissions` - Auto-approve all operations (testing)
- `default` - SDK default behavior
- `dontAsk` - No permission prompts
- `plan` - Planning mode

**Invalid Values** (will cause timeout):
- `manual`, `acceptAll`, or any other string

**Configuration**:
```python
# src/harness/config.py
claude_permission_mode: Literal[
    "acceptEdits", "bypassPermissions", "default", "dontAsk", "plan"
] = Field(default="acceptEdits")
```

**Verification**:
```bash
docker compose exec main-agent python -c "
from harness.config import get_config
print(get_config().claude_permission_mode)
"
# Should output: acceptEdits (or another valid value)
```

---

### 2. Unbuffered Python Output (BLOCKING)

**Problem**: Without unbuffered mode, subprocess stdout uses 8KB block buffering in containers. Messages accumulate and never flush until buffer fills or process exits.

**Required Configuration**:

**Dockerfile**:
```dockerfile
ENV PYTHONUNBUFFERED=1
```

**docker-compose.yml**:
```yaml
environment:
  - PYTHONUNBUFFERED=1
```

**Verification**:
```bash
docker compose exec main-agent env | grep PYTHONUNBUFFERED
# Should output: PYTHONUNBUFFERED=1
```

---

### 3. Tini as PID 1 (IMPORTANT for Graceful Shutdown)

**Problem**: Shell-form CMD makes `/bin/sh` PID 1, which doesn't forward SIGTERM to child processes.

**Required Configuration**:

**Dockerfile**:
```dockerfile
# Install tini
RUN apt-get update && apt-get install -y tini

# Set as PID 1
ENTRYPOINT ["/usr/bin/tini", "--"]

# Use exec form (array syntax)
CMD ["python", "-m", "harness.agent"]
```

**Verification**:
```bash
docker compose exec main-agent which tini && docker compose exec main-agent tini --version
# Should output: /usr/bin/tini and version number
```

---

### 4. Signal Handlers in Python Code (IMPORTANT for Cleanup)

**Required**: Explicit signal handlers that flush streams during graceful shutdown.

**Implementation** (src/harness/agent.py:540-568):
```python
async def graceful_shutdown(signame):
    logger.info(f"Received {signame}, starting graceful shutdown...")
    sys.stdout.flush()  # Critical: flush before exit
    sys.stderr.flush()
    # Cancel tasks, shutdown services...

loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(
        sig,
        lambda s=sig: asyncio.create_task(graceful_shutdown(signal.Signals(s).name))
    )
```

---

## Performance Benchmarks

### Expected SDK Performance (with valid config)

| Operation | Duration | Status |
|-----------|----------|--------|
| SDK Initialization | 0.8-1.0s | ✅ Normal |
| Simple Query | 2-4s | ✅ Normal |
| First Query (total) | 3-5s | ✅ Normal |

### Performance Red Flags

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| 60s timeout on init | Invalid permission mode | Use valid mode from list above |
| No messages, hangs | Buffering issue | Set PYTHONUNBUFFERED=1 |
| Partial messages | Buffer not flushed | Add signal handlers with flush |
| Container restarting | Config error or missing API key | Check logs, verify .env |

---

## Troubleshooting Decision Tree

```
Agent not responding?
├─ Does it timeout after 60s?
│  └─ YES → Check permission mode (must be valid value)
│  └─ NO → Continue
│
├─ Are there any messages at all?
│  └─ NO → Check PYTHONUNBUFFERED=1 in container
│  └─ YES → Continue
│
├─ Is container restarting?
│  └─ YES → Check docker compose logs for error
│  └─ NO → Continue
│
└─ Messages delayed or partial?
   └─ Check signal handlers and stream flushing
```

---

## Quick Diagnostic Commands

```bash
# 1. Check permission mode
docker compose exec main-agent python -c "from harness.config import get_config; print(get_config().claude_permission_mode)"

# 2. Verify PYTHONUNBUFFERED
docker compose exec main-agent env | grep PYTHONUNBUFFERED

# 3. Verify tini installed
docker compose exec main-agent which tini

# 4. Check container health
docker compose ps

# 5. View recent logs
docker compose logs main-agent --tail 50

# 6. Test SDK directly
docker compose exec main-agent python tests/integration/test_valid_permission_mode.py
```

---

## Key Learnings from Troubleshooting

### 1. SDK Permission Modes Are Strictly Validated

**Learning**: The Claude Agent SDK validates permission mode at CLI subprocess startup. Invalid values cause immediate subprocess failure, but SDK still tries to communicate with the dead process, resulting in 60-second control request timeout.

**Implication**: Always use `Literal` type hints in configuration to catch invalid values at development time, not runtime.

### 2. Container Subprocess Communication Is Different

**Learning**: Standard Python subprocess practices don't work the same in containers:
- No TTY = block-buffered stdout (8KB buffer)
- Shell-form CMD breaks signal propagation
- Environment variables must be explicitly passed to subprocesses

**Implication**: Always use unbuffered mode, tini as PID 1, and exec-form commands in containers.

### 3. HTTP Mocking Tools Don't Work with SDK

**Learning**: The SDK uses subprocess communication (stdin/stdout) to talk to the Claude CLI, not HTTP. VCR.py and similar HTTP recording/mocking libraries cannot intercept subprocess I/O.

**Implication**: Integration tests must make real API calls. Keep tests minimal to control costs. Use token budgets and test markers (`@pytest.mark.slow`) to skip expensive tests during development.

### 4. Documentation Drift Happens Fast

**Learning**: The original troubleshooting docs described the "manual" permission mode bug as unsolved, but the code had already been fixed. The disconnect between docs and code caused confusion.

**Implication**: Always verify documentation claims with running tests. Don't trust implementation documentation without verification.

---

## Redis Streams for Multi-Agent Communication

**Status**: ✅ Fully implemented and tested (367 lines of production code, 7/7 tests passing)

**Purpose**: Enable communication between agents running in separate containers (stdio pipes don't cross container boundaries).

**Implementation**: `src/harness/messaging.py` - RedisMessageBroker class

**Usage**:
```python
# Agent 1: Publish result
await session.publish_task_result(
    task_id="task-123",
    result={"status": "complete", "data": {...}}
)

# Agent 2: Wait for dependency
result = await session.wait_for_dependency(
    dependency_task_id="task-123",
    timeout=300
)
```

**Benefits**:
- Works across container boundaries
- Survives container restarts
- Automatic message ordering
- Load balancing with consumer groups
- Queue depth monitoring

---

## Production Deployment Checklist

**Before deploying**, verify these critical factors:

- [ ] **Permission mode** is valid value (`acceptEdits`, `bypassPermissions`, etc.)
- [ ] **PYTHONUNBUFFERED=1** in both Dockerfile and docker-compose.yml
- [ ] **Tini installed** and configured as `ENTRYPOINT`
- [ ] **Exec-form CMD** (array syntax: `["python", "-m", "harness.agent"]`)
- [ ] **Signal handlers** implemented with `sys.stdout.flush()`
- [ ] **ANTHROPIC_API_KEY** set in `.env` file
- [ ] **Test suite passing** - run `docker compose exec main-agent python tests/integration/test_valid_permission_mode.py`
- [ ] **Container health** shows "healthy" - run `docker compose ps`
- [ ] **Redis accessible** if using multi-agent coordination

**Quick Validation**:
```bash
# Run this one command to test everything critical
docker compose exec main-agent python tests/integration/test_valid_permission_mode.py

# Expected output:
# ✓ SUCCESS! Initialized in 0.8-1.0 seconds
# ✓ Query completed in 2-4 seconds
# Total duration: 3-5 seconds
```

---

## Common Failure Modes & Fixes

### Failure: "Control request timeout: initialize"

**Cause**: Invalid permission mode or subprocess failure

**Fix**:
1. Check permission mode value in config
2. Ensure it's one of: `acceptEdits`, `bypassPermissions`, `default`, `dontAsk`, `plan`
3. Rebuild containers: `make build && make dev`

### Failure: Agent hangs with no output

**Cause**: Stream buffering (missing PYTHONUNBUFFERED)

**Fix**:
1. Add `ENV PYTHONUNBUFFERED=1` to Dockerfile
2. Add `PYTHONUNBUFFERED=1` to docker-compose.yml environment
3. Rebuild: `make build && make dev`

### Failure: Container status "Restarting"

**Cause**: Configuration error or missing dependencies

**Fix**:
1. Check logs: `docker compose logs [service-name] --tail 50`
2. Verify ANTHROPIC_API_KEY in `.env`
3. Check for error messages in logs
4. Verify all dependencies installed in Dockerfile

---

## References

### Implementation Files
- `agents/main/Dockerfile` - Container config (lines 69, 77, 84, 128, 140, 143)
- `src/harness/config.py` - Permission mode validation (lines 30-35)
- `src/harness/agent.py` - Signal handlers (lines 540-568)
- `src/harness/messaging.py` - Redis Streams IPC (367 lines)
- `docker-compose.yml` - Service orchestration (lines 33, 95, 139)

### Test Files
- `tests/integration/test_valid_permission_mode.py` - SDK initialization test
- `tests/integration/test_container_buffering.py` - Buffering tests (183 lines)
- `tests/integration/test_signal_handling.py` - Signal tests (220 lines)
- `tests/integration/test_multi_agent.py` - Multi-agent tests (243 lines)

---

**Version**: 1.0
**Last Updated**: November 21, 2025
**Status**: Production-Ready
