# Repository Hardening Plan

> **Status**: Active | **Last Updated**: December 8, 2025 | **Test Coverage**: 73% | **Architecture Issues Fixed**: 6/9

## Objective

Evaluate ab-casdk-harness for production readiness and identify security/architecture issues requiring remediation before enterprise deployment.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Remaining Work](#remaining-work)
- [Production-Ready Features](#production-ready-features)
- [Architecture Review](#architecture-review)
- [Security Audit](#security-audit)
- [Consolidated Priority List](#consolidated-priority-list)
- [Implementation Timeline](#implementation-timeline)
- [Testing Progress](#testing-progress)
- [Template Extraction Strategy](#template-extraction-strategy)
- [References](#references)

---

## Executive Summary

### Current State

| Metric | Value | Target |
|--------|-------|--------|
| **Test Coverage** | 73% | 80% |
| **Architecture Readiness** | 65% | 80% |
| **Security Posture** | 6.5/10 | 8/10 |
| **Unit Tests** | 455+ | - |

### Key Findings

**Architecture Strengths**:
- Clear separation of concerns (config, checkpoint, monitoring)
- Pydantic validation, Tenacity retry, structured logging
- Two-tier MCP architecture (in-process + subprocess)

**Critical Issues (Block Release)**:
- 3 Critical security vulnerabilities (plaintext checkpoints, SSH keys, log exposure)
- God object anti-pattern in agent.py (981 LOC)
- Unbounded Prometheus metric cardinality

---

## Remaining Work

### Testing (73% → 80%)

| Item | Status | Effort | Notes |
|------|--------|--------|-------|
| security.py tests | ✅ Done | - | 71% → 95% |
| cli.py Rich console | Deferred | ~4h | UI work |
| interactive.py | Deferred | ~4h | UI work |

### Active Workarounds

| Item | Location | Notes |
|------|----------|-------|
| Plugin SDK Workaround | `agent.py:64-72` | Manual skill discovery - remove when SDK fixed |

### Infrastructure

| Item | Status | Effort |
|------|--------|--------|
| ~~Agent Health Checks~~ | ✅ Implemented | - |

---

## Production-Ready Features

| Feature | LOC | Evidence | Confidence |
|---------|-----|----------|------------|
| Interactive Mode | 259 | Error handling, checkpoint recovery, Rich UI | HIGH |
| Autonomous Mode | 942 | Two-phase architecture, signal handling | HIGH |
| 12 Base Skills | ~6000 | Well-documented SKILL.md files | HIGH |
| 6 MCP Servers | ~1500 | 3 in-process + 3 subprocess | HIGH |
| CLI Tools | N/A | git, gh, glab integrated | HIGH |
| Checkpoint/Recovery | 269 | Auto-save hourly, recovery tested | HIGH |
| Prometheus/Grafana | ~500 | Dashboards verified | HIGH |
| Docker Orchestration | ~300 | Multi-stage Dockerfile | HIGH |
| Pydantic Config | 156 | Type-safe, validated | HIGH |
| Bash Security | 389 | Allowlist/blocklist, 95% test coverage | HIGH |

---

## Architecture Review

> Review Date: December 8, 2025 | Production Readiness: **45%**

### Strengths

- ✅ Clear separation of concerns (config, checkpoint, monitoring separate)
- ✅ Pydantic validation for all settings
- ✅ Tenacity retry with exponential backoff (3 attempts, 4-10s wait)
- ✅ Structured logging with structlog
- ✅ Comprehensive metrics (15+ Prometheus metrics)
- ✅ Two-tier MCP architecture (in-process fast, subprocess external)
- ✅ Comprehensive bash command security (95% test coverage)

### Critical Issues

| Issue | Location | Impact | Effort | Priority |
|-------|----------|--------|--------|----------|
| ~~Unbounded metric cardinality~~ | `monitoring.py` | ~~Prometheus OOM~~ | - | ✅ Fixed |
| **God object anti-pattern** | `agent.py` (980 LOC) | Poor testability | 8h | P0 |
| ~~Missing error recovery~~ | `agent.py` | ~~Silent Redis failures~~ | - | ✅ Fixed |
| ~~Placeholder implementations~~ | `checkpoint.py` | ~~Broken recovery~~ | - | ✅ Fixed |

### Major Issues

| Issue | Location | Impact | Effort | Priority |
|-------|----------|--------|--------|----------|
| ~~No health check endpoints~~ | ~~All agents~~ | ~~Can't verify liveness~~ | - | ✅ Fixed |
| ~~Missing request timeouts~~ | ~~`agent.py:475-533`~~ | ~~Hung requests~~ | - | ✅ Fixed |
| No rate limiting | `autonomous.py` | API quota exhaustion | 3h | P1 |
| ~~**No circuit breaker for Redis**~~ | ~~`messaging.py:34-54`~~ | ~~Cascade failures~~ | - | ✅ Fixed |
| ~~**SDK client lifecycle leaks**~~ | ~~`agent.py:854-880`~~ | ~~Resource exhaustion~~ | - | ✅ Fixed |
| ~~No signal propagation~~ | ~~`autonomous.py:85-91`~~ | ~~Orphaned processes~~ | - | ✅ Fixed |
| ~~Magic numbers everywhere~~ | ~~Multiple files~~ | ~~Hard to tune~~ | - | ✅ Fixed |

### Proposed Refactoring

**Current**: `AgentSession` (981 LOC) handles 9+ responsibilities

**Proposed**:
```
AgentSession (~300 LOC)
├── MCPServerManager (~200 LOC) - MCP lifecycle
├── PluginManager (~150 LOC) - Plugin discovery
├── SessionManager (~150 LOC) - State management
├── CheckpointManager (~300 LOC) - Already separate
└── MetricsCollector (~400 LOC) - Already separate
```

### Scalability Limits

| Dimension | Current Limit | Bottleneck |
|-----------|--------------|------------|
| Concurrent agents | ~10 | Redis connection pool |
| Session duration | 20 hours | No issue (designed for) |
| Messages per session | Unlimited | Prometheus cardinality |
| Checkpoint size | <100MB | No compression |

---

## Security Audit

> Audit Date: December 8, 2025 | Security Posture: **6.5/10**

### Risk Overview

| Severity | Count | Status |
|----------|-------|--------|
| **Critical** | 3 | Requires immediate fix |
| **High** | 5 | Fix before production |
| **Medium** | 8 | Should address |
| **Low** | 5 | Best practices |

### Strengths

- ✅ Comprehensive bash command allowlist/blocklist in `security.py` (95% coverage)
- ✅ Non-root containers with dedicated `claude` user
- ✅ No hardcoded secrets in repository
- ✅ Proper .gitignore for sensitive files
- ✅ Environment-based configuration with Pydantic validation
- ✅ Structured logging framework

### Critical Vulnerabilities

#### CRIT-01: Plaintext Checkpoint Data
**CVSS**: 9.1 | **CWE**: CWE-312 | **Location**: `checkpoint.py:51-77`

Checkpoints store complete agent state in plaintext JSON, including conversation history (may contain API keys, passwords), workspace snapshots, and session tokens.

**Impact**: PII exposure, credential leakage, GDPR/HIPAA violations

**Remediation**:
- [ ] Implement AES-256-GCM encryption for checkpoint files
- [ ] Store encryption keys in secure vault (AWS KMS, HashiCorp Vault)
- [ ] Add integrity verification (HMAC-SHA256)
- [ ] Implement key rotation (30-day)
- [ ] Add checkpoint sanitization for sensitive patterns

#### CRIT-02: SSH Private Keys in Containers
**CVSS**: 8.8 | **CWE**: CWE-522 | **Location**: `docker-compose.yml:26`

SSH private keys mounted directly into containers at `/home/claude/.ssh:ro`. All containers have access; compromised container = stolen credentials.

**Impact**: Repository access, lateral movement, supply chain attack

**Remediation**:
- [ ] Replace SSH keys with ephemeral tokens (GitHub/GitLab PAT)
- [ ] Use git credential helper with 24h token expiration
- [ ] Remove SSH key mounts from docker-compose.yml
- [ ] Implement container-level secret injection

#### CRIT-03: User Prompts Logged Without Sanitization
**CVSS**: 7.5 | **CWE**: CWE-532 | **Location**: `agent.py:494-500`

User prompts logged with partial content, potentially capturing API keys, passwords, PII, and business logic.

**Impact**: PII leakage, credential exposure, compliance violations

**Remediation**:
- [ ] Implement regex-based log sanitization
- [ ] Hash prompts instead of storing plaintext
- [ ] Add sensitive pattern filters (API keys, emails, passwords)
- [ ] Implement log retention policy (30 days max)

### High-Risk Issues

| ID | Issue | CVSS | Location | Effort |
|----|-------|------|----------|--------|
| HIGH-01 | Missing rate limiting | 7.5 | `monitoring.py` | 4h |
| HIGH-02 | Redis password in env vars | 7.0 | `.env.example:162` | 2h |
| HIGH-04 | Bash command bypass flag | 8.8 | `autonomous.py:25` | 2h |
| HIGH-05 | Missing security headers | 6.5 | `docker-compose.prod.yml` | 3h |
| HIGH-06 | Docker socket exposure risk | 9.0 | `mcp_servers/docker` | 4h |

#### HIGH-04: Bash Command Bypass Flag
The `--allow-all-commands` flag completely bypasses security validation, allowing `rm -rf /`, arbitrary code execution, and credential theft.

**Remediation**:
- [ ] Remove flag entirely or restrict to non-production
- [ ] Add mandatory audit logging even when bypassed
- [ ] Require admin approval for bypass mode

### Medium-Risk Issues

| ID | Issue | CVSS | Location | Effort |
|----|-------|------|----------|--------|
| MED-01 | Session timeout not enforced | 5.3 | `config.py:38` | 2h |
| MED-02 | Error messages too detailed | 5.0 | `agent.py:607-630` | 2h |
| MED-03 | Workspace writable by tester | 6.0 | `docker-compose.yml` | 1h |
| MED-04 | No dependency vulnerability scanning | 5.5 | `pyproject.toml` | 2h |
| MED-05 | Memory graph unencrypted | 5.0 | `mcp_servers/memory` | 4h |
| MED-06 | No container image signing | 5.0 | Build pipeline | 3h |
| MED-07 | Redis streams not access-controlled | 4.5 | `messaging.py` | 3h |
| MED-08 | No cost budget enforcement | 4.0 | `monitoring.py:286-338` | 3h |

### Low-Risk Issues

| ID | Issue | CVSS | Location |
|----|-------|------|----------|
| LOW-01 | Default passwords in .env.example | 3.0 | `.env.example:162-165` |
| LOW-02 | Metrics endpoint unauthenticated | 3.5 | `monitoring.py:122-140` |
| LOW-03 | Container group permissions | 3.0 | `Dockerfile:90-92` |
| LOW-04 | Debug mode validation | 2.5 | `.env.example:225` |
| LOW-05 | Predictable project name | 2.0 | `.env.example:211` |

---

## Consolidated Priority List

### P0: Critical (Block Release)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| ~~1~~ | ~~Unbounded metric cardinality~~ | ~~Arch~~ | ✅ Fixed |
| 2 | Plaintext checkpoint data (CRIT-01) | Sec | 8h |
| 3 | God object refactoring (`agent.py`) | Arch | 8h |
| 4 | SSH keys in containers (CRIT-02) | Sec | 4h |
| 5 | User prompts logged (CRIT-03) | Sec | 4h |
| ~~6~~ | ~~Missing Redis error recovery~~ | ~~Arch~~ | ✅ Fixed |

**P0 Remaining: ~24 hours (~3 days)**

### P1: High (Fix Before Production)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| 6 | Missing rate limiting (HIGH-01) | Sec | 4h |
| ~~7~~ | ~~Redis circuit breaker~~ | ~~Arch~~ | ✅ Fixed |
| ~~8~~ | ~~SDK client lifecycle leaks~~ | ~~Arch~~ | ✅ Fixed |
| ~~9~~ | ~~Health check endpoints~~ | ~~Arch~~ | ✅ Fixed |
| ~~10~~ | ~~Request timeouts~~ | ~~Arch~~ | ✅ Fixed |
| 11 | Bash command bypass (HIGH-04) | Sec | 2h |
| 12 | Redis password security (HIGH-02) | Sec | 2h |

**P1 Remaining: ~8 hours (~1 day)** *(was ~19h)*

### P2: Medium (Should Address)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| 13 | Security headers (HIGH-05) | Sec | 3h |
| 14 | Docker socket proxy (HIGH-06) | Sec | 4h |
| 15 | Checkpoint cleanup race | Arch | 2h |
| ~~16~~ | ~~Signal propagation~~ | ~~Arch~~ | ✅ Fixed |
| ~~17~~ | ~~Centralize magic numbers~~ | ~~Arch~~ | ✅ Fixed |
| 18 | Session timeout enforcement | Sec | 2h |
| 19 | Error message sanitization | Sec | 2h |
| 20 | Dependency vulnerability scanning | Sec | 2h |
| 21 | Cost budget enforcement | Sec | 3h |

**P2 Remaining: ~18 hours (~3 days)** *(was ~25h)*

### P3: Low (Best Practices)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| 22 | Memory graph encryption | Sec | 4h |
| 23 | Container image signing | Sec | 3h |
| 24 | Redis stream ACLs | Sec | 3h |
| 25 | Test workspace isolation | Sec | 1h |
| 26 | Default passwords | Sec | 1h |
| 27 | Metrics endpoint auth | Sec | 2h |

**P3 Total: ~14 hours (~2 days)**

---

## Implementation Timeline

### Week 1: Critical Fixes (P0)
- [ ] CRIT-01: Implement checkpoint encryption
- [ ] CRIT-02: Replace SSH keys with tokens
- [ ] CRIT-03: Add log sanitization
- [x] Fix Prometheus cardinality (remove session_id) ✅
- [x] Fix Redis error recovery (explicit disabled state) ✅
- [x] Implement workspace snapshots (git-based) ✅

### Week 2: High Priority (P1)
- [ ] Add rate limiting with Redis
- [x] Implement circuit breaker for Redis ✅ (messaging.py)
- [x] Add health check endpoints ✅ (health.py)
- [x] Add request timeouts ✅ (agent.py)
- [x] Implement SDK client lifecycle tracking ✅ (agent.py)
- [x] Implement async signal propagation ✅ (autonomous.py)
- [x] Centralize magic numbers in config ✅ (config.py)
- [ ] Remove bash bypass flag or restrict to dev

### Week 3: Simplification & Export
- [ ] Refactor agent.py (extract managers)
- [ ] Simplify docker-compose (single agent)
- [ ] Simplify Makefile (35 targets)
- [ ] Export to casdk-harness
- [ ] Create new README.md

### Week 4+: Hardening (P2/P3)
- [ ] Address medium/low priority issues
- [ ] Documentation polish

---

## Testing Progress

> **Current: 73% (414 tests)** | Target: 80%

### Phase Summary

| Phase | Module | Tests | Coverage | Status |
|-------|--------|-------|----------|--------|
| 1 | checkpoint.py | +27 | 45% → 91% | ✅ |
| 2 | monitoring.py | +41 | 69% → 99% | ✅ |
| 3 | E2E tests | +2 | Quality | ✅ |
| 4 | agent.py | +21 | 50% → 63% | ✅ |
| 5 | cli.py | +29 | 22% → 45% | ✅ |
| 6 | autonomous.py | +71 | 23% → 83% | ✅ |
| 7 | security.py | +45 | 71% → 95% | ✅ |

### Current Module Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| monitoring.py | 98.55% | ✅ |
| mcp_loader.py | 97.27% | ✅ |
| progress.py | 96.97% | ✅ |
| security.py | 95.24% | ✅ |
| checkpoint.py | 91.04% | ✅ |
| autonomous.py | 82.64% | ✅ |
| config.py | 82.76% | Good |
| agent.py | 63.06% | ✅ |
| cli.py | 44.64% | Deferred |
| interactive.py | 0.00% | Deferred |

### To Reach 80%
- cli.py Rich console tests (deferred to UI work)
- interactive.py tests (deferred to UI work)

---

## Template Extraction Strategy

### Files to Copy As-Is
- `src/harness/config.py`, `checkpoint.py`, `monitoring.py`, `cli.py`
- `src/harness/mcp_loader.py`, `security.py`, `progress.py`
- `src/mcp_servers/` (all 3 directories)
- `.claude/skills/` (all 12 directories)
- `config/monitoring/` (entire directory)

### Files to Simplify
- `agent.py` (981 → ~700 LOC) - Remove Redis messaging
- `autonomous.py` (942 → ~700 LOC) - Simplify signals
- `docker-compose.yml` - Single agent, no Redis
- `Makefile` (71 → ~35 targets)

### Files to Exclude
- `messaging.py` (Redis, untested)
- `.claude/agents/` (SDK doesn't load)
- `.claude/plugins/` (SDK bug)

---

## References

- [OWASP Cryptographic Storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP API Security](https://owasp.org/API-Security/)

---

*Generated: December 8, 2025*
*Architecture Review + Security Audit consolidated*
*Test coverage: 73% (414 tests, 7 phases complete)*
