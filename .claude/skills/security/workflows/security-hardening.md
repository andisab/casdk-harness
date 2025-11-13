---
title: Security Hardening Workflow
description: Comprehensive security assessment and hardening with SAST, dependency scanning, and vulnerability remediation
tags: [workflow, security, hardening, vulnerability, compliance, SAST]
type: workflow
version: "1.0.0"
orchestration:
  pattern: parallel-scanning-prioritized-remediation
  agents: 5
  estimatedTime: "20-40 minutes"
  complexity: high
---

# Security Hardening Workflow

## Overview

This workflow orchestrates comprehensive security assessment across multiple dimensions—static analysis, dependency vulnerabilities, configuration security, and code patterns—then prioritizes and remediates findings based on severity and exploitability.

**Use this workflow when:**
- Preparing for production deployment
- Conducting periodic security audits
- Responding to security incidents or CVE alerts
- Meeting compliance requirements (SOC 2, HIPAA, PCI-DSS)
- Before releasing new features or major updates
- After dependency updates or library migrations

**Pattern:** Parallel security scanning → Prioritized remediation → Verification
**Estimated execution:** 20-40 minutes depending on codebase size
**Token usage:** ~60K-110K tokens across all agents

## Agent Roles

### 1. Orchestrator Agent
- **Responsibility**: Coordinate security scans, prioritize findings, track remediation
- **Tools**: `Task`, `TodoWrite`, `Read`, `Write`, `Bash`
- **Permissions**: Read-only on source, execute security tools, write reports
- **Context**: Security standards (OWASP, CWE), compliance requirements, risk assessment

### 2. SAST Analyzer Agent
- **Responsibility**: Static Application Security Testing for code vulnerabilities
- **Tools**: `Read`, `Bash` (Semgrep, Bandit, ESLint security plugins), `Grep`
- **Permissions**: Read-only on source code
- **Context**: OWASP Top 10, injection attacks, XSS, CSRF, insecure patterns

### 3. Dependency Scanner Agent
- **Responsibility**: Scan dependencies for known vulnerabilities (CVEs)
- **Tools**: `Read`, `Bash` (npm audit, pip-audit, Snyk), `Grep`
- **Permissions**: Read package manifests, execute scanners
- **Context**: CVE database, vulnerability severity (CVSS), patch availability

### 4. Security Auditor Agent
- **Responsibility**: Manual security review, auth patterns, cryptography, secrets
- **Tools**: `Read`, `Grep`, `Bash`
- **Permissions**: Read-only on source and config files
- **Context**: Authentication patterns, encryption standards, secret management, compliance

### 5. Fix Implementer Agent
- **Responsibility**: Implement security fixes, update dependencies, harden configs
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to source code, configs, and dependencies
- **Context**: Secure coding patterns, patch management, defense-in-depth

## Orchestration Flow

### Phase 1: Security Scan Initialization (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Define scan scope (code, dependencies, configs)
- Configure security tools and thresholds
- Set compliance requirements
- Initialize vulnerability tracking
- Activate scanner agents in parallel

**Configuration:**
- CVSS severity threshold (e.g., >7.0 = critical)
- Compliance frameworks (OWASP, CWE, PCI-DSS)
- Excluded paths (vendor code, test fixtures)
- False positive suppression rules

**Output:**
- Scan configuration
- Compliance checklist
- Activated scanner agents

**Duration:** 2-3 minutes

### Phase 2: Parallel Security Scanning

Run these 3 agents **in parallel** for comprehensive coverage:

#### 2a. Static Analysis (SAST Analyzer)
**Agent:** SAST Analyzer
**Actions:**
- Run SAST tools (Semgrep, Bandit, ESLint security, etc.)
- Detect injection vulnerabilities (SQL, command, XSS)
- Find insecure cryptography usage
- Identify hardcoded secrets and credentials
- Check for insecure random number generation
- Detect path traversal vulnerabilities
- Find XML External Entity (XXE) issues
- Check for Server-Side Request Forgery (SSRF)

**Vulnerability Categories:**
- **A01: Broken Access Control**
  - Missing authorization checks
  - Insecure direct object references
  - Path traversal vulnerabilities

- **A02: Cryptographic Failures**
  - Weak encryption algorithms (MD5, SHA1)
  - Hardcoded cryptographic keys
  - Insecure random number generation
  - Missing TLS/HTTPS enforcement

- **A03: Injection**
  - SQL injection points
  - Command injection vulnerabilities
  - LDAP, NoSQL injection
  - Cross-Site Scripting (XSS)

- **A05: Security Misconfiguration**
  - Exposed debug endpoints
  - Default credentials
  - Verbose error messages
  - Missing security headers

**Output:**
- SAST findings with CWE mappings
- Severity classifications (Critical/High/Medium/Low)
- Code locations and vulnerable patterns
- Recommended remediation

**Duration:** 8-12 minutes

#### 2b. Dependency Scanning (Dependency Scanner)
**Agent:** Dependency Scanner
**Actions:**
- Scan npm/pip/maven dependencies for CVEs
- Check for outdated packages with known vulnerabilities
- Identify transitive dependency vulnerabilities
- Verify license compliance
- Check for malicious packages
- Analyze dependency confusion risks
- Review package integrity (checksums, signatures)

**Scan Coverage:**
- Direct dependencies (package.json, requirements.txt, pom.xml)
- Transitive dependencies (lock files)
- Development dependencies
- Container base images (if applicable)

**Vulnerability Assessment:**
- CVE ID and CVSS score
- Exploitability rating
- Patch availability
- Breaking change risk
- Mitigation options

**Output:**
- CVE findings with CVSS scores
- Vulnerable dependency tree
- Patch recommendations
- License compliance report

**Duration:** 6-10 minutes

#### 2c. Security Review (Security Auditor)
**Agent:** Security Auditor
**Actions:**
- Review authentication and authorization logic
- Check JWT token handling and validation
- Verify password storage (bcrypt, Argon2)
- Review session management
- Check for exposed secrets in code/config
- Validate CORS and CSP configurations
- Review API rate limiting
- Check input validation and sanitization
- Verify secure headers (HSTS, X-Frame-Options, etc.)

**Review Areas:**
- **Authentication:**
  - Password policies and storage
  - Multi-factor authentication
  - Token generation and validation
  - Session timeout and renewal

- **Authorization:**
  - Role-Based Access Control (RBAC)
  - Principle of least privilege
  - Resource-level permissions
  - API endpoint protection

- **Data Protection:**
  - Encryption at rest and in transit
  - PII handling and anonymization
  - Secure file uploads
  - Database encryption

- **Configuration Security:**
  - Environment variable usage
  - Secret management (Vault, AWS Secrets Manager)
  - CORS policies
  - Security headers

**Output:**
- Security review findings
- Configuration recommendations
- Authentication/authorization gaps
- Compliance violations

**Duration:** 8-14 minutes

### Phase 3: Finding Consolidation (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Collect findings from all scanners
- Remove duplicates across tools
- Correlate related vulnerabilities
- Calculate risk scores (CVSS + exploitability)
- Prioritize by severity and business impact
- Group by remediation strategy
- Classify as auto-fixable vs. manual

**Prioritization Factors:**
- CVSS base score (0-10)
- Exploitability (high/medium/low)
- Business criticality of affected component
- Patch availability
- Public exploit availability

**Risk Categories:**
- **P0 (Critical)**: CVSS ≥9.0, actively exploited, public-facing
- **P1 (High)**: CVSS 7.0-8.9, high exploitability
- **P2 (Medium)**: CVSS 4.0-6.9, moderate risk
- **P3 (Low)**: CVSS 0.1-3.9, minimal risk

**Output:**
- Consolidated vulnerability report
- Prioritized remediation list
- Auto-fixable vs. manual fixes
- Risk assessment summary

**Duration:** 3-5 minutes

### Phase 4: Automated Remediation (Fix Implementer)
**Agent:** Fix Implementer
**Actions:**
- Apply automated dependency updates
- Remove hardcoded secrets, use env vars
- Fix simple SAST findings (regex patterns)
- Update security headers
- Enable recommended security features
- Update outdated crypto algorithms
- Fix path traversal vulnerabilities

**Auto-fixable Issues:**
- Dependency version bumps (patch/minor)
- Hardcoded secret removal
- Missing security headers
- Simple regex-based vulnerabilities
- Outdated crypto algorithms

**Manual Review Required:**
- Breaking dependency updates (major versions)
- Complex injection vulnerabilities
- Architecture-level security changes
- Authentication/authorization redesign

**Output:**
- Code changes for automated fixes
- List of manual fixes required
- Updated dependencies
- Configuration updates

**Duration:** 8-15 minutes

### Phase 5: Manual Fix Guidance (Orchestrator + Fix Implementer)
**Agent:** Orchestrator (delegates complex fixes to Fix Implementer)
**Actions:**
- Create detailed fix guidance for manual issues
- Provide code examples and patterns
- Link to security documentation
- Estimate fix complexity and effort
- Create tickets for manual remediation
- Assign priority levels

**Fix Guidance Template:**
```markdown
### Vulnerability: SQL Injection in User Search

**Severity:** Critical (CVSS 9.8)
**Location:** src/api/users.ts:45
**CWE:** CWE-89 (SQL Injection)

**Vulnerable Code:**
```typescript
const query = `SELECT * FROM users WHERE name = '${req.query.name}'`;
db.query(query);
```

**Recommended Fix:**
```typescript
const query = 'SELECT * FROM users WHERE name = ?';
db.query(query, [req.query.name]);
```

**Testing:**
- Add unit test with malicious input: `' OR '1'='1`
- Verify parameterized query prevents injection
- Test with SQLMap to confirm fix

**References:**
- OWASP SQL Injection: https://owasp.org/...
- Framework docs: https://...
```

**Output:**
- Manual fix guidance documents
- Code examples and patterns
- Testing recommendations
- Remediation tickets

**Duration:** 5-10 minutes

### Phase 6: Verification (Security Auditor)
**Agent:** Security Auditor
**Actions:**
- Re-run security scans
- Verify fixes address vulnerabilities
- Check for new issues introduced
- Run exploit tests against fixed vulns
- Validate security headers
- Test authentication/authorization
- Review dependency updates

**Verification Checklist:**
- ✅ All critical vulnerabilities fixed
- ✅ High-priority issues addressed or mitigated
- ✅ Security scans show improvement
- ✅ No new vulnerabilities introduced
- ✅ Tests passing after changes
- ✅ Compliance requirements met

**Output:**
- Verification report
- Before/after comparison
- Remaining vulnerabilities
- Compliance status

**Duration:** 6-10 minutes

### Phase 7: Documentation & Reporting (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Generate security assessment report
- Document all findings and fixes
- Create compliance documentation
- Update security runbooks
- Generate metrics dashboard
- Create follow-up tasks for manual fixes

**Output:**
- Security assessment report
- Compliance documentation
- Follow-up task list
- Security metrics

**Duration:** 3-5 minutes

## Security Assessment Report Structure

```markdown
# Security Assessment Report

**Project:** MyApp API
**Date:** 2025-10-25T16:00:00Z
**Scope:** Full codebase + dependencies
**Status:** ⚠️ Action Required
**Overall Risk:** Medium (was High)

---

## 📊 Executive Summary

Security assessment identified 23 vulnerabilities across code, dependencies, and configuration. Automated fixes addressed 12 issues (52%), with 11 requiring manual remediation. Critical and high-priority issues must be fixed before production deployment.

**Risk Reduction:** High → Medium (43% improvement)
**Auto-Fixed:** 12 issues
**Manual Required:** 11 issues
**Compliance:** 85% (SOC 2 ready after manual fixes)

---

## 🚨 Critical Findings (2)

### 1. SQL Injection in User Search API
- **Severity:** Critical (CVSS 9.8)
- **Category:** A03:2021 - Injection
- **Location:** `src/api/users.ts:45`
- **Impact:** Full database compromise, data exfiltration
- **Status:** 🔴 Requires Manual Fix
- **Exploitability:** High (public exploits available)

**Vulnerable Code:**
```typescript
const query = `SELECT * FROM users WHERE name = '${req.query.name}'`;
```

**Recommended Fix:**
Use parameterized queries:
```typescript
const query = 'SELECT * FROM users WHERE name = ?';
db.query(query, [req.query.name]);
```

**Timeline:** Fix within 24 hours

---

### 2. Hardcoded JWT Secret Key
- **Severity:** Critical (CVSS 9.1)
- **Category:** A02:2021 - Cryptographic Failures
- **Location:** `src/auth/jwt.ts:12`
- **Impact:** Authentication bypass, account takeover
- **Status:** ✅ Auto-Fixed
- **Exploitability:** High

**Fix Applied:**
```typescript
// Before
const secret = "my-hardcoded-secret";

// After
const secret = process.env.JWT_SECRET;
if (!secret) throw new Error('JWT_SECRET required');
```

---

## ⚠️ High Priority (8)

### Dependencies with Known CVEs

| Package | Version | CVE | CVSS | Status |
|---------|---------|-----|------|--------|
| lodash | 4.17.20 | CVE-2021-23337 | 7.2 | ✅ Updated to 4.17.21 |
| axios | 0.21.1 | CVE-2021-3749 | 7.5 | ✅ Updated to 0.27.2 |
| express | 4.17.1 | CVE-2022-24999 | 7.5 | 🔴 Manual (breaking) |

### Code Vulnerabilities

1. **XSS in User Profile Display** (CVSS 7.3)
   - Location: `src/components/UserProfile.tsx:89`
   - Status: ✅ Auto-Fixed (added DOMPurify)

2. **Missing Authorization Check** (CVSS 8.1)
   - Location: `src/api/admin.ts:23`
   - Status: 🔴 Requires Manual Fix

[Additional findings...]

---

## 📋 Medium Priority (10)

### Security Configuration Issues

1. **Missing Security Headers** - ✅ Auto-Fixed
   - Added: HSTS, X-Content-Type-Options, X-Frame-Options
   - File: `src/middleware/security.ts`

2. **Weak CORS Policy** - 🔴 Requires Review
   - Current: Allows all origins (*)
   - Recommendation: Whitelist specific domains

[Additional findings...]

---

## 📈 Security Metrics

### Vulnerability Distribution

| Severity | Before | After | Fixed |
|----------|--------|-------|-------|
| Critical | 2 | 1 | 50% |
| High | 10 | 3 | 70% |
| Medium | 15 | 7 | 53% |
| Low | 8 | 3 | 63% |
| **Total** | **35** | **14** | **60%** |

### By Category (OWASP Top 10)

| Category | Findings | Status |
|----------|----------|--------|
| A01: Broken Access Control | 3 | 1 fixed, 2 manual |
| A02: Cryptographic Failures | 4 | 3 fixed, 1 manual |
| A03: Injection | 5 | 2 fixed, 3 manual |
| A05: Security Misconfiguration | 8 | 6 fixed, 2 manual |
| A06: Vulnerable Components | 12 | 9 fixed, 3 manual |

---

## ✅ Automated Fixes Applied (12)

1. Updated 9 vulnerable dependencies (patch/minor versions)
2. Removed 2 hardcoded secrets, using environment variables
3. Added security headers middleware
4. Fixed XSS vulnerability with DOMPurify
5. Updated crypto from MD5 to SHA-256
6. Fixed path traversal in file upload
7. Added input validation for API endpoints
8. Enabled HTTPS redirect
9. Configured CSP headers
10. Fixed insecure random number generation
11. Added rate limiting middleware
12. Updated session configuration (secure cookies)

---

## 🔴 Manual Fixes Required (11)

### High Priority (5)

1. **Fix SQL injection in user search** (est. 2 hours)
   - See detailed guidance above
   - Priority: P0 (block deployment)

2. **Add authorization check to admin endpoints** (est. 3 hours)
   - Implement RBAC middleware
   - Priority: P0 (block deployment)

3. **Upgrade Express to v4.18.2** (est. 4 hours)
   - Breaking changes in middleware API
   - Priority: P1 (within 1 week)

[Additional manual fixes...]

### Medium Priority (6)

1. **Review and restrict CORS policy** (est. 1 hour)
2. **Implement API rate limiting per user** (est. 2 hours)
3. **Add request logging for audit trail** (est. 1 hour)
[...]

---

## 📜 Compliance Status

### SOC 2 Requirements

| Control | Status | Notes |
|---------|--------|-------|
| Access Control | ⚠️ 85% | Missing RBAC on 2 endpoints |
| Encryption | ✅ 100% | TLS 1.3, AES-256 |
| Logging | ⚠️ 75% | Need audit logging |
| Vulnerability Mgmt | ✅ 90% | Active scanning + remediation |

**Overall Compliance:** 85% (95% after manual fixes)

---

## 🎯 Recommendations

### Immediate (Within 24 Hours)
1. Fix SQL injection vulnerability (P0)
2. Add authorization checks to admin endpoints (P0)
3. Deploy automated fixes to production

### Short-term (Within 1 Week)
1. Complete all high-priority manual fixes
2. Upgrade Express and test thoroughly
3. Implement comprehensive RBAC system
4. Add audit logging for compliance

### Long-term (Ongoing)
1. Implement security testing in CI/CD
2. Schedule monthly security audits
3. Train team on secure coding practices
4. Enable automated dependency updates
5. Implement WAF (Web Application Firewall)

---

## 📊 Before/After Comparison

### Security Posture

**Before:**
- 35 total vulnerabilities
- 2 critical, 10 high, 15 medium, 8 low
- Overall risk: High
- Compliance: 60%

**After:**
- 14 total vulnerabilities (-60%)
- 1 critical, 3 high, 7 medium, 3 low
- Overall risk: Medium
- Compliance: 85%

**Improvement:** 60% vulnerability reduction, 43% risk reduction

---

**Assessment By:** AI Security Hardening Workflow
**Report Generated:** 2025-10-25T16:30:00Z
**Next Assessment:** Scheduled for 2025-11-25
**Status:** In Remediation
```

## Best Practices

### Security Scanning
- **Comprehensive coverage**: SAST + dependency + manual review
- **Regular cadence**: Weekly scans, daily for critical systems
- **False positive management**: Suppress known false positives
- **Tool diversity**: Use multiple tools for better coverage

### Prioritization
- **Risk-based**: CVSS score + exploitability + business impact
- **Context matters**: Public-facing > internal services
- **Patch availability**: Prioritize issues with available fixes
- **Exploit maturity**: Actively exploited > theoretical

### Remediation
- **Defense in depth**: Multiple security layers
- **Least privilege**: Minimal necessary permissions
- **Secure by default**: Security-first configurations
- **Fail securely**: Errors should fail closed, not open

### Compliance
- **Documentation**: Maintain audit trail of findings and fixes
- **Regular assessment**: Quarterly security audits
- **Policy enforcement**: Automated security gates in CI/CD
- **Training**: Regular security training for developers

## Example Usage

### Triggering the Workflow

```bash
# Via Claude Code
You: "Run security hardening scan using security-hardening workflow"

# Via CLI
claude-security --workflow security-hardening --compliance SOC2

# Pre-deployment scan
claude-security --workflow security-hardening \
  --severity critical,high \
  --block-on-critical
```

### Orchestrator Prompt Example

```markdown
Run comprehensive security assessment using security-hardening workflow:

**Scope:**
- Full codebase in `src/`
- All dependencies (production + development)
- Configuration files (docker, nginx, env.example)

**Compliance Requirements:**
- SOC 2 Type II
- OWASP Top 10 compliance
- PCI-DSS Level 1 (payment processing)

**Thresholds:**
- Block deployment if critical vulnerabilities found
- Auto-fix all safe updates (patch/minor dependencies)
- Generate manual fix guidance for complex issues

**Tools:**
- SAST: Semgrep + ESLint security plugins
- Dependencies: npm audit + Snyk
- Manual review: Authentication, authorization, crypto

**Output:**
- Detailed security report
- Compliance status dashboard
- Prioritized remediation plan
- Automated fixes where possible
```

## Error Handling

### Scanner Failures
- **Action:** Continue with other scanners, note failure
- **Escalation:** Manual tool configuration or update

### Too Many Findings (>100)
- **Action:** Focus on critical/high only
- **Escalation:** Incremental remediation plan

### Breaking Dependency Updates
- **Action:** Document breaking changes, manual review
- **Escalation:** Create compatibility update project

### Compliance Gaps
- **Action:** Document gaps, create remediation timeline
- **Escalation:** Delay deployment until compliant

## Performance Metrics

### Scan Times by Codebase Size

| Codebase Size | SAST | Deps | Review | Total |
|---------------|------|------|--------|-------|
| Small (<10K LOC) | 3-5 min | 2-3 min | 5-8 min | 15-20 min |
| Medium (10-50K) | 6-10 min | 3-5 min | 8-12 min | 20-30 min |
| Large (50-200K) | 10-15 min | 5-8 min | 12-18 min | 30-45 min |

### Success Criteria

- **Scan completion**: >98% successful scans
- **False positive rate**: <10%
- **Auto-fix success**: >80% of fixable issues
- **Time to remediation**: <7 days for critical, <30 days for high

## Related Workflows

- **Code Review Pipeline**: Include security review in PR process
- **Full-Stack Feature Development**: Security scan before deployment
- **Bug Fix Debugging**: If security vulnerabilities found
- **Testing QA Orchestration**: Security test execution

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
