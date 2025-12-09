# Repository Hardening Plan

> **Status**: Active | **Last Updated**: December 8, 2025 | **Test Coverage**: 73%

## Current State

| Metric | Value | Target |
|--------|-------|--------|
| **Test Coverage** | 73% | 80% |
| **Security Posture** | 6.5/10 | 8/10 |

**Blocking Issues**: 3 Critical security vulnerabilities + God object in agent.py

---

## Priority Summary

| Priority | Remaining | Effort |
|----------|-----------|--------|
| **P0 Critical** | 4 issues | ~24h |
| **P1 High** | 3 issues | ~8h |
| **P2 Medium** | 7 issues | ~18h |
| **P3 Low** | 6 issues | ~14h |

**Total Remaining**: ~64 hours

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
- [ ] Add checkpoint sanitization for sensitive patterns

### CRIT-02: SSH Private Keys in Containers
**CVSS**: 8.8 | **Location**: `docker-compose.yml:26` | **Effort**: 4h

SSH private keys mounted directly into containers at `/home/claude/.ssh:ro`. All containers have access; compromised container = stolen credentials.

**Impact**: Repository access, lateral movement, supply chain attack

**Remediation**:
- [ ] Replace SSH keys with ephemeral tokens (GitHub/GitLab PAT)
- [ ] Use git credential helper with 24h token expiration
- [ ] Remove SSH key mounts from docker-compose.yml
- [ ] Implement container-level secret injection

### CRIT-03: User Prompts Logged Without Sanitization
**CVSS**: 7.5 | **Location**: `agent.py:494-500` | **Effort**: 4h

User prompts logged with partial content, potentially capturing API keys, passwords, PII, and business logic.

**Impact**: PII leakage, credential exposure, compliance violations

**Remediation**:
- [ ] Implement regex-based log sanitization
- [ ] Hash prompts instead of storing plaintext
- [ ] Add sensitive pattern filters (API keys, emails, passwords)
- [ ] Implement log retention policy (30 days max)

### God Object Refactoring
**Location**: `agent.py` (981 LOC) | **Effort**: 8h

`AgentSession` handles 9+ responsibilities, causing poor testability and maintenance burden.

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
| Bash command bypass flag | 8.8 | `autonomous.py:25` | 2h |
| Redis password in env vars | 7.0 | `.env.example:162` | 2h |

### HIGH-04: Bash Command Bypass Flag
The `--allow-all-commands` flag completely bypasses security validation, allowing `rm -rf /`, arbitrary code execution, and credential theft.

**Remediation**:
- [ ] Remove flag entirely or restrict to non-production
- [ ] Add mandatory audit logging even when bypassed
- [ ] Require admin approval for bypass mode

---

## P2: Medium (Should Address)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Security headers | 6.5 | `docker-compose.prod.yml` | 3h |
| Docker socket exposure | 9.0 | `mcp_servers/docker` | 4h |
| Checkpoint cleanup race | - | `checkpoint.py` | 2h |
| Session timeout enforcement | 5.3 | `config.py:38` | 2h |
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
| Default passwords | 3.0 | `.env.example:162-165` | 1h |
| Metrics endpoint auth | 3.5 | `monitoring.py:122-140` | 2h |

---

## Testing Gaps

| Module | Coverage | Notes |
|--------|----------|-------|
| cli.py | 45% | Deferred (UI work) |
| interactive.py | 0% | Deferred (UI work) |

To reach 80% overall: cli.py and interactive.py tests (~8h total, deferred)

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

*Last Updated: December 8, 2025*
