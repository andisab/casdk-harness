# Repository Hardening Plan

> **Status**: Active | **Last Updated**: January 28, 2026 | **Test Coverage**: ~65-70%

## Current State

| Metric | Value | Target |
|--------|-------|--------|
| **Test Coverage** | ~65-70% | 80% |
| **Security Posture** | 6/10 | 8/10 |

**Blocking Issues**:
- 2 Critical security vulnerabilities (unchanged)
- God object in agent.py (now 1706 LOC, worse than originally assessed)
- CGF orchestrator untested (1,335 LOC, 0 tests)

---

## Recently Resolved

| Issue | CVSS | Resolution |
|-------|------|------------|
| ~~CRIT-03: Log sanitization~~ | 7.5 | Added `sanitize_sensitive_data()` in `security.py`, applied to prompt storage |
| ~~HIGH-04: Bash bypass flag~~ | 8.8 | Removed `--allow-all-commands` flag entirely |
| ~~P2: Session timeout~~ | 5.3 | Added `_check_session_timeout()` enforcing `claude_session_timeout` |
| ~~P3: Default passwords~~ | 3.0 | Changed to `CHANGE_ME_BEFORE_PRODUCTION` placeholders |
| ~~P3: Metrics auth~~ | 3.5 | Added optional basic auth via `METRICS_AUTH_TOKEN` |

---

## Priority Summary

| Priority | Remaining | Effort |
|----------|-----------|--------|
| **P0 Critical** | 3 issues | ~20h |
| **P1 High** | 3 issues | ~22h |
| **P2 Medium** | 6 issues | ~16h |
| **P3 Low** | 4 issues | ~11h |

**Total Remaining**: ~69 hours (includes CGF testing gaps)

---

## P0: Critical (Block Release)

### CRIT-01: Plaintext Checkpoint Data
**CVSS**: 9.1 | **Location**: `checkpoint.py:51-77` | **Effort**: 8h

Checkpoints store complete agent state in plaintext JSON, including conversation history (may contain API keys, passwords), workspace snapshots, and session tokens.

**Impact**: PII exposure, credential leakage, GDPR/HIPAA violations

**Remediation**:
- [ ] Implement AES-256-GCM encryption for checkpoint files
- [ ] Store encryption keys in secure vault (AWS KMS, HashiCorp Vault)
- [ ] Add integrity verification (HMAC-SHA256)
- [ ] Implement key rotation (30-day)
- [x] Add checkpoint sanitization for sensitive patterns (via sanitize_sensitive_data)

### CRIT-02: SSH Private Keys in Containers
**CVSS**: 8.8 | **Location**: `docker-compose.yml:26` | **Effort**: 4h

SSH private keys mounted directly into containers at `/home/claude/.ssh:ro`. All containers have access; compromised container = stolen credentials.

**Impact**: Repository access, lateral movement, supply chain attack

**Remediation**:
- [ ] Replace SSH keys with ephemeral tokens (GitHub/GitLab PAT)
- [ ] Use git credential helper with 24h token expiration
- [ ] Remove SSH key mounts from docker-compose.yml
- [ ] Implement container-level secret injection

### God Object Refactoring
**Location**: `agent.py` (1706 LOC) | **Effort**: 8h

`AgentSession` handles 9+ responsibilities, causing poor testability and maintenance burden. **Note**: Situation has worsened from original 1000+ LOC assessment.

**Proposed Structure**:
```
AgentSession (~300 LOC)
├── MCPServerManager (~200 LOC) - MCP lifecycle
├── PluginManager (~150 LOC) - Plugin discovery
├── SessionManager (~150 LOC) - State management
├── CheckpointManager (~300 LOC) - Already separate
└── MetricsCollector (~400 LOC) - Already separate
```

---

## P1: High (Fix Before Production)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Missing rate limiting | 7.5 | `autonomous.py` | 4h |
| Redis password in env vars | 7.0 | `.env.example:162` | 2h |
| CGF framework testing gaps | - | `src/harness/optimization/` | 16h |

### CGF Framework Testing Gaps
**Priority**: P1 | **Location**: `src/harness/optimization/` | **Effort**: ~16h

Critical modules lack test coverage while being the default optimization path:

| Module | LOC | Tests | Status |
|--------|-----|-------|--------|
| `orchestrator.py` | 1,335 | 0 | CRITICAL - Core orchestration untested |
| `api.py` | 434 | 0 | Public API untested |
| `cli/optimize.py` | ~200 | 0 | Entry point untested |
| `cli/section_optimize.py` | ~300 | 0 | Entry point untested |
| `agentic_optimizer.py` | ~400 | 7 | Default strategy, lightest coverage |

**Impact**: Default optimization path (agentic) significantly under-tested.

**Remediation**:
- [ ] Add orchestrator unit tests (8h)
- [ ] Add API layer tests (4h)
- [ ] Add CLI integration tests (4h)

---

## P2: Medium (Should Address)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Security headers | 6.5 | `docker-compose.prod.yml` | 3h |
| Docker socket exposure | 9.0 | `mcp_servers/docker` | 4h |
| Checkpoint cleanup race | - | `checkpoint.py` | 2h |
| Error message sanitization | 5.0 | `agent.py:607-630` | 2h |
| Dependency vulnerability scanning | 5.5 | `pyproject.toml` | 2h |
| Cost budget enforcement | 4.0 | `monitoring.py:286-338` | 3h |

---

## P3: Low (Best Practices)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Memory graph encryption | 5.0 | `mcp_servers/memory` | 4h |
| Container image signing | 5.0 | Build pipeline | 3h |
| Redis stream ACLs | 4.5 | `messaging.py` | 3h |
| Test workspace isolation | 6.0 | `docker-compose.yml` | 1h |

---

## Testing Gaps

| Module | Coverage | Notes |
|--------|----------|-------|
| `orchestrator.py` | 0% | CRITICAL - 1,335 LOC untested |
| `api.py` | 0% | 434 LOC, public API untested |
| `cli/*.py` | 0% | Entry points untested |
| `agentic_optimizer.py` | ~10% | Only 7 tests, default strategy |
| `cli.py` | 45% | Deferred (UI work) |
| `interactive.py` | 0% | Deferred (UI work) |

**Test Count Reconciliation** (726 total, not 802+):
- Unit tests: 628 across 16 files
- E2E tests: 82 across 4 files
- Integration tests: 16 in test_cgf_pipeline.py

To reach 80%: orchestrator + api + CLI tests (~16h), then cli.py/interactive.py (~8h)

---

## Active Workarounds

| Item | Location | Notes |
|------|----------|-------|
| Plugin SDK Workaround | `agent.py:64-72` | Manual skill discovery - remove when SDK fixed |

---

## References

- [OWASP Cryptographic Storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP API Security](https://owasp.org/API-Security/)

---

*Last Updated: January 28, 2026*
