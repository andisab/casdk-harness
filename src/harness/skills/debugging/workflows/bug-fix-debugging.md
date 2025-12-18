---
title: Bug Fix & Debugging Workflow
description: Systematic approach to diagnosing, fixing, and verifying bug resolutions with root cause analysis
tags: [workflow, debugging, bug-fix, root-cause-analysis, troubleshooting]
type: workflow
version: "1.0.0"
orchestration:
  pattern: iterative-diagnosis-fix-verify
  agents: 5
  estimatedTime: "25-45 minutes"
  complexity: medium-high
---

# Bug Fix & Debugging Workflow

## Overview

This workflow orchestrates a systematic debugging process from initial bug report through verified fix and prevention measures. It uses an iterative approach of diagnosis → hypothesis → fix → verify, ensuring thorough root cause analysis and preventing regression.

**Use this workflow when:**
- Investigating production bugs or incidents
- Debugging complex issues across multiple components
- Performing root cause analysis for critical failures
- Ensuring comprehensive bug fixes with regression tests
- Learning from failures to prevent future issues

**Pattern:** Iterative diagnosis → Fix implementation → Comprehensive verification
**Estimated execution:** 25-45 minutes depending on bug complexity
**Token usage:** ~60K-100K tokens across all agents

## Agent Roles

### 1. Orchestrator Agent
- **Responsibility**: Coordinate debugging process, maintain investigation state, decide next steps
- **Tools**: `Task`, `TodoWrite`, `Read`, `Grep`, `Write`
- **Permissions**: Read-only on codebase, full access to agent management
- **Context**: Bug tracking, investigation patterns, escalation criteria

### 2. Bug Analyzer Agent
- **Responsibility**: Initial triage, impact assessment, reproduction steps
- **Tools**: `Read`, `Grep`, `Bash`
- **Permissions**: Read-only on source code, logs, and database
- **Context**: Log analysis, error patterns, system architecture, common failure modes

### 3. Code Investigator Agent
- **Responsibility**: Deep code analysis, identify root cause, trace execution flow
- **Tools**: `Read`, `Grep`, `Bash` (git blame, git log)
- **Permissions**: Read-only on source code and git history
- **Context**: Debugging techniques, code tracing, dependency analysis, git forensics

### 4. Fix Implementer Agent
- **Responsibility**: Implement fix, add defensive code, update error handling
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to source code and tests
- **Context**: Coding standards, defensive programming, error handling patterns

### 5. Regression Tester Agent
- **Responsibility**: Verify fix, create regression tests, check for side effects
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to test files and test runners
- **Context**: Test frameworks, regression testing, edge case identification

## Orchestration Flow

### Phase 1: Bug Triage & Reproduction (Bug Analyzer)
**Agent:** Bug Analyzer
**Actions:**
- Parse bug report and error messages
- Assess severity and impact (P0/critical → P4/low)
- Identify affected components and versions
- Analyze logs and stack traces
- Attempt to reproduce the issue
- Document reproduction steps
- Gather system state and context

**Key Questions:**
- Can we reproduce the bug consistently?
- What's the blast radius (users affected, data at risk)?
- Is this a regression (was it working before)?
- Are there workarounds available?

**Output:**
- Severity classification (P0-P4)
- Reproduction steps (if reproducible)
- Affected components and versions
- Initial hypothesis about root cause
- Logs and stack traces

**Duration:** 5-8 minutes

### Phase 2: Root Cause Investigation (Code Investigator)
**Agent:** Code Investigator
**Actions:**
- Trace code execution flow leading to error
- Analyze recent code changes (git blame, git log)
- Identify suspicious code patterns
- Check for race conditions or timing issues
- Review related past bugs and fixes
- Examine data states and edge cases
- Use debugging techniques (binary search, printf debugging)

**Investigation Techniques:**
- **Stack trace analysis**: Follow the error back through call stack
- **Git archaeology**: Find when bug was introduced
- **Differential analysis**: Compare working vs. broken states
- **Dependency analysis**: Check for library updates or conflicts
- **Data flow tracing**: Track data transformation through system

**Output:**
- Root cause hypothesis with confidence level
- Suspicious code sections with line numbers
- Related historical issues
- Data states that trigger the bug
- Recommended fix approach

**Duration:** 10-15 minutes

### Phase 3: Hypothesis Validation (Code Investigator + Bug Analyzer)
**Agent:** Code Investigator (with Bug Analyzer validation)
**Actions:**
- Test root cause hypothesis
- Create minimal reproduction case
- Verify hypothesis explains all symptoms
- Identify edge cases and boundary conditions
- Document evidence supporting hypothesis

**Validation Methods:**
- Add logging at suspected failure points
- Inject test cases that trigger suspected code path
- Compare against similar working scenarios
- Check if fix hypothesis addresses all symptoms

**Output:**
- Validated root cause with evidence
- Minimal reproduction test case
- Explanation of why bug occurs
- List of edge cases to address

**Decision Point:** If hypothesis doesn't validate, return to Phase 2

**Duration:** 5-10 minutes

### Phase 4: Fix Implementation (Fix Implementer)
**Agent:** Fix Implementer
**Actions:**
- Implement targeted fix for root cause
- Add defensive programming (null checks, validation)
- Improve error handling and logging
- Update comments explaining the fix
- Add inline documentation for tricky code
- Consider performance implications
- Ensure backward compatibility

**Fix Principles:**
- **Minimal change**: Fix the root cause, not symptoms
- **Defensive**: Add guards against similar issues
- **Observable**: Add logging for future debugging
- **Tested**: Include fix validation in implementation

**Output:**
- Code changes implementing the fix
- Enhanced error handling
- Additional logging for observability
- Updated code comments
- Migration plan if breaking changes

**Duration:** 8-15 minutes

### Phase 5: Regression Test Creation (Regression Tester)
**Agent:** Regression Tester
**Actions:**
- Create test that fails before fix, passes after
- Add unit tests for the specific bug
- Add integration tests for the workflow
- Test edge cases and boundary conditions
- Verify fix doesn't break existing tests
- Create test fixtures for the bug scenario
- Document test rationale

**Test Coverage:**
- **Reproduction test**: Exact scenario from bug report
- **Edge cases**: Boundary conditions that might trigger similar bugs
- **Integration**: End-to-end workflow testing
- **Regression**: Ensure old behavior still works

**Output:**
- Regression test suite
- Test documentation
- Coverage report showing new coverage
- Verification that all tests pass

**Duration:** 8-12 minutes

### Phase 6: Verification & Validation (Regression Tester + Orchestrator)
**Agent:** Regression Tester (with Orchestrator oversight)
**Actions:**
- Run full test suite (unit, integration, E2E)
- Verify fix resolves original bug
- Check for unintended side effects
- Performance testing (if performance-related)
- Manual testing of critical paths
- Validate in staging environment
- Check error rates and metrics

**Verification Checklist:**
- ✅ Original bug is fixed
- ✅ New regression tests pass
- ✅ All existing tests still pass
- ✅ No performance degradation
- ✅ Logs show expected behavior
- ✅ Metrics within acceptable range

**Output:**
- Verification report
- Test results (all passing)
- Performance comparison (before/after)
- Staging deployment validation

**Duration:** 5-8 minutes

### Phase 7: Documentation & Prevention (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Document root cause and fix in bug tracker
- Update troubleshooting guides
- Add to known issues documentation
- Create post-mortem if critical bug
- Identify prevention measures
- Update monitoring/alerting if needed
- Share learnings with team

**Documentation Includes:**
- Root cause explanation
- Fix description
- Steps to reproduce
- Prevention recommendations
- Links to related issues
- Timeline of investigation

**Output:**
- Updated bug ticket with resolution
- Post-mortem document (if applicable)
- Prevention recommendations
- Updated documentation

**Duration:** 3-5 minutes

## Bug Fix Report Structure

```markdown
# Bug Fix Report

**Bug ID:** BUG-1234
**Title:** User authentication fails intermittently with 500 error
**Severity:** P1 (High)
**Status:** ✅ Fixed and Verified
**Time to Resolution:** 38 minutes

---

## 🐛 Bug Description

Users experiencing intermittent 500 errors during login process. Approximately 2-5% of login attempts failing, especially during peak hours.

**Reported By:** Customer Support (15 tickets)
**First Occurred:** 2025-10-20T14:30:00Z
**Environment:** Production
**Affected Users:** ~200 users/day

---

## 🔍 Root Cause Analysis

### Initial Symptoms
- 500 Internal Server Error during POST /api/auth/login
- Error rate: 2-5% of attempts
- Pattern: More frequent during peak hours (>100 concurrent users)

### Investigation Process

1. **Log Analysis** (Bug Analyzer - 6 min)
   - Found `NullPointerException` in auth service logs
   - Stack trace points to token generation: `src/auth/jwt.ts:45`
   - Error occurs when Redis connection pool exhausted

2. **Code Investigation** (Code Investigator - 12 min)
   - Traced execution: login → generate token → Redis lookup → crash
   - `git blame` shows connection pool added in commit `abc123` (Oct 15)
   - Connection pool size hardcoded to 10, insufficient for peak load
   - No connection timeout configured, causing pool exhaustion

3. **Hypothesis Validation** (Code Investigator - 8 min)
   - Created load test: 50 concurrent logins
   - Reproduced 500 error after 10th concurrent request
   - Verified hypothesis: connection pool exhaustion causes crash

### Root Cause

**Issue:** Redis connection pool size hardcoded to 10 connections without timeout configuration.

**Why it occurred:**
- Recent optimization (Oct 15) added connection pooling
- Pool size not configured for production load
- No connection timeout → connections never released on error
- No monitoring alerts for pool exhaustion

**Code Location:** `src/auth/jwt.ts:12-18`

```typescript
// Problematic code
const redisPool = new RedisPool({
  maxConnections: 10,  // Too small for production
  // Missing: timeout, retry logic
});
```

---

## 🔧 Fix Implementation

### Changes Made

**File:** `src/auth/jwt.ts`

```typescript
// Fixed code
const redisPool = new RedisPool({
  maxConnections: process.env.REDIS_POOL_SIZE || 50,  // Configurable, default 50
  timeout: 5000,  // 5 second timeout
  retry: {
    maxAttempts: 3,
    backoff: 'exponential'
  },
  onError: (err) => logger.error('Redis pool error', { error: err })
});
```

**Additional Changes:**
- Added environment variable `REDIS_POOL_SIZE` to config
- Added connection pool monitoring metrics
- Enhanced error logging with pool status
- Updated deployment docs with new env var

### Fix Validation

- Load test with 100 concurrent logins: ✅ All pass
- Sustained load over 5 minutes: ✅ Zero errors
- Connection pool metrics: 45/50 peak usage
- Error rate: 0% (down from 2-5%)

---

## 🧪 Regression Tests

### Tests Added

1. **Unit Test:** `auth.test.ts::test_connection_pool_exhaustion`
   - Simulates pool exhaustion scenario
   - Verifies graceful degradation with timeout

2. **Integration Test:** `auth-load.test.ts::test_concurrent_logins`
   - 100 concurrent login requests
   - Validates all complete successfully within timeout

3. **E2E Test:** `login-flow.e2e.ts::test_peak_load_login`
   - Simulates peak traffic scenario
   - Validates user experience during high load

### Test Results
- All new tests: ✅ Passing
- Existing test suite: ✅ 234/234 passing
- Coverage: +4.2% in auth module

---

## ✅ Verification

### Pre-Fix State
- Error rate: 2-5% of login attempts
- Peak errors: 15-20/hour during traffic spikes
- User impact: Login failures, retry required

### Post-Fix State
- Error rate: 0% over 24 hour monitoring period
- Peak concurrent connections: 45/50 (healthy margin)
- User impact: Zero login failures
- Performance: No degradation, same latency

### Deployment Validation
- Staging: ✅ Deployed, tested for 2 hours, zero errors
- Production: ✅ Deployed during low-traffic window
- Rollback plan: ✅ Previous version tagged, ready if needed
- Monitoring: ✅ Dashboards updated, alerts configured

---

## 📚 Prevention Measures

### Immediate Actions
1. ✅ Add connection pool size monitoring to dashboards
2. ✅ Create alert: pool usage >80% for >5 minutes
3. ✅ Document Redis configuration in runbook
4. ✅ Add load testing to CI/CD pipeline

### Long-term Improvements
1. 🔄 Review all connection pools for similar issues
2. 🔄 Implement circuit breaker pattern for Redis
3. 🔄 Add connection pool metrics to all services
4. 🔄 Create load testing strategy for critical paths

### Lessons Learned
- Always configure timeouts for external service connections
- Connection pools must be sized for peak load, not average
- Load testing should be part of deployment process
- Monitoring critical: alerts prevented larger outage

---

## 📊 Impact & Metrics

**User Impact:**
- Before: 200 users/day affected (~15-20 support tickets)
- After: 0 users affected, 0 tickets

**Business Impact:**
- Eliminated login failures during peak hours
- Improved user trust and experience
- Reduced support burden

**Technical Metrics:**
- Fix time: 38 minutes (triage to verification)
- Code changes: 15 lines modified
- Test coverage: +4.2%
- Deployment time: 12 minutes

---

## 🔗 Related Issues

- BUG-1180: Similar Redis timeout issue in cache service (Aug 2025)
- FEATURE-456: Add connection pool monitoring (completed as part of fix)
- INCIDENT-89: Production outage from database pool exhaustion (June 2025)

---

**Fixed By:** AI Agent Workflow (Bug Fix & Debugging)
**Reviewed By:** @tech-lead
**Deployed:** 2025-10-25T16:45:00Z
**Status:** Resolved and Monitored
```

## Best Practices

### Investigation
- **Reproduce first**: Don't fix what you can't reproduce
- **Logs are gold**: Always check logs before code
- **Git archaeology**: Use git blame/log to find when bug introduced
- **Bisect approach**: Binary search through commits if needed
- **Document hypotheses**: Track what you've tried and ruled out

### Fix Implementation
- **Minimal change**: Smallest fix that addresses root cause
- **Defensive coding**: Add guards against similar issues
- **Error visibility**: Enhance logging for future debugging
- **Performance check**: Ensure fix doesn't introduce slowdowns
- **Backward compatible**: Avoid breaking changes unless necessary

### Testing
- **Regression test first**: Write failing test before fix
- **Edge cases**: Test boundary conditions and error paths
- **Integration testing**: Verify fix in context of full system
- **Load testing**: For performance/concurrency bugs
- **Manual verification**: Test in staging before production

### Communication
- **Clear documentation**: Explain root cause and fix
- **Share learnings**: Post-mortems for critical bugs
- **Update runbooks**: Add troubleshooting steps
- **Prevention focus**: Identify how to avoid similar bugs

## Example Usage

### Triggering the Workflow

```bash
# Via Claude Code
You: "Investigate BUG-1234 using bug-fix-debugging workflow"

# Via CLI
claude-debug --workflow bug-fix-debugging --bug-id BUG-1234

# With specific context
claude-debug --workflow bug-fix-debugging \
  --error "NullPointerException in auth service" \
  --logs auth-service.log \
  --priority P1
```

### Orchestrator Prompt Example

```markdown
Investigate and fix the following bug using bug-fix-debugging workflow:

**Bug Report:**
- ID: BUG-1234
- Title: User authentication fails intermittently
- Severity: P1 (High)
- Description: 2-5% of login attempts return 500 error
- Reproduction: Occurs during peak traffic (>100 concurrent users)
- Error: "NullPointerException in token generation"

**Available Context:**
- Logs: `/var/log/auth-service.log` (last 24 hours)
- Error rate spike: 2025-10-20T14:30:00Z
- Recent changes: Redis connection pooling added Oct 15
- User reports: 15 support tickets

**Requirements:**
- Reproduce the issue consistently
- Identify root cause with evidence
- Implement minimal, tested fix
- Add regression tests
- Verify in staging before production
- Document prevention measures

**Quality Gates:**
- Must reproduce before fixing
- All tests passing after fix
- Zero performance degradation
- Complete documentation of root cause
```

## Error Handling

### Cannot Reproduce Bug
- **Action:** Gather more data (logs, user reports, environment details)
- **Escalation:** Request live debugging session or production access
- **Alternative:** Implement defensive code based on hypothesis

### Multiple Root Causes
- **Action:** Fix most critical root cause first
- **Escalation:** Create separate bugs for each root cause
- **Alternative:** Comprehensive fix addressing all causes if related

### Fix Breaks Other Tests
- **Action:** Analyze test failures, adjust fix approach
- **Escalation:** May need larger refactoring, consult with team
- **Alternative:** Implement behind feature flag for gradual rollout

### Cannot Verify Fix
- **Action:** Deploy to staging with enhanced monitoring
- **Escalation:** Canary deployment to small production subset
- **Alternative:** A/B testing to verify fix effectiveness

## Performance Metrics

### Time to Resolution by Severity

| Severity | Target | Typical | Agents Used |
|----------|--------|---------|-------------|
| P0 (Critical) | <2 hours | 45-90 min | All 5 |
| P1 (High) | <8 hours | 30-60 min | All 5 |
| P2 (Medium) | <3 days | 25-45 min | 4 agents |
| P3 (Low) | <1 week | 20-30 min | 3 agents |

### Success Metrics

- **First-time fix rate**: >85% (fix resolves issue without rework)
- **Regression prevention**: <5% of bugs recur
- **Root cause accuracy**: >90% of diagnoses correct
- **Test coverage**: 100% of fixes include regression tests

## Integration Points

### Bug Tracking Integration
```javascript
// Auto-update bug tracker with progress
bugTracker.updateStatus(bugId, {
  status: 'In Progress',
  assignedTo: 'AI Agent Workflow',
  rootCause: rootCauseAnalysis,
  estimatedResolution: '30 minutes'
});
```

### Monitoring Integration
```javascript
// Enhanced monitoring post-fix
monitoring.addMetric({
  name: 'auth.redis_pool_usage',
  threshold: 0.8,
  alert: 'Connection pool >80% for >5min'
});
```

## Related Workflows

- **Testing QA Orchestration**: Run after fix for comprehensive testing
- **Code Review Pipeline**: Review fix before deployment
- **Security Hardening**: If security-related bug
- **Documentation Generation**: Create post-mortem for critical bugs

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
