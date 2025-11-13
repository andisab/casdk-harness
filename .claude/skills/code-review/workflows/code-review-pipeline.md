---
title: Code Review Pipeline
description: Multi-phase automated code review with specialized analysis agents for quality, security, performance, and standards
tags: [workflow, code-review, quality, security, performance, standards]
type: workflow
version: "1.0.0"
orchestration:
  pattern: parallel-analysis-consolidated-report
  agents: 5
  estimatedTime: "15-25 minutes"
  complexity: medium
---

# Code Review Pipeline Workflow

## Overview

This workflow orchestrates 5 specialized review agents that perform parallel code analysis across different quality dimensions, then consolidates findings into a comprehensive review report. The parallel pattern enables fast review cycles while maintaining thorough coverage.

**Use this workflow when:**
- Reviewing pull requests before merge
- Conducting periodic code quality audits
- Validating code against team standards
- Preparing code for production deployment
- Onboarding new team members to codebase standards

**Pattern:** Parallel analysis with consolidated reporting
**Estimated execution:** 15-25 minutes depending on changeset size
**Token usage:** ~40K-70K tokens across all agents

## Agent Roles

### 1. Orchestrator Agent
- **Responsibility**: Coordinate reviewers, consolidate findings, generate final report
- **Tools**: `Task`, `TodoWrite`, `Read`, `Grep`, `Write`
- **Permissions**: Read-only on codebase, full access to agent management
- **Context**: Review standards, severity classifications, report templates

### 2. Code Quality Reviewer Agent
- **Responsibility**: Assess code structure, readability, maintainability
- **Tools**: `Read`, `Grep`, `Bash` (eslint, prettier, etc.)
- **Permissions**: Read-only on source code, execute linting tools
- **Context**: Coding standards, design patterns, naming conventions, DRY/SOLID principles

### 3. Security Reviewer Agent
- **Responsibility**: Identify security vulnerabilities and compliance issues
- **Tools**: `Read`, `Bash` (security scanners), `Grep`
- **Permissions**: Read-only on source, execute security scanning tools
- **Context**: OWASP Top 10, authentication patterns, input validation, secret management

### 4. Performance Reviewer Agent
- **Responsibility**: Analyze performance implications and optimization opportunities
- **Tools**: `Read`, `Grep`, `Bash` (profiling tools)
- **Permissions**: Read-only on source code
- **Context**: Performance patterns, algorithmic complexity, database optimization, caching

### 5. Standards Checker Agent
- **Responsibility**: Verify compliance with team conventions and documentation
- **Tools**: `Read`, `Grep`, `Bash`
- **Permissions**: Read-only on source and documentation
- **Context**: Team style guides, documentation requirements, testing standards, commit conventions

## Orchestration Flow

### Phase 1: Review Initialization (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Parse pull request or commit range
- Identify changed files and scope of review
- Activate relevant review agents based on file types
- Set severity thresholds (blocking vs. advisory)
- Initialize review findings collection

**Output:**
- List of files to review
- Activated reviewers and their scope
- Review configuration (thresholds, standards)

**Duration:** 2-3 minutes

### Phase 2: Parallel Analysis (All Review Agents)

Run these 4 agents **in parallel** for maximum efficiency:

#### 2a. Code Quality Analysis (Code Quality Reviewer)
**Agent:** Code Quality Reviewer
**Actions:**
- Run static analysis tools (ESLint, Pylint, etc.)
- Check for code smells and anti-patterns
- Verify naming conventions
- Assess function/class complexity
- Check for duplicated code
- Verify proper error handling
- Review code organization and modularity

**Findings Categories:**
- Critical: Code breaks builds or has logical errors
- High: Violations of core patterns or major code smells
- Medium: Minor quality issues, readability concerns
- Low: Stylistic suggestions, optional improvements

**Output:**
- Quality findings with severity levels
- Linting violations
- Complexity metrics
- Suggestions for refactoring

**Duration:** 5-8 minutes

#### 2b. Security Analysis (Security Reviewer)
**Agent:** Security Reviewer
**Actions:**
- Run SAST (Static Application Security Testing)
- Check for SQL injection vulnerabilities
- Verify authentication and authorization
- Review input validation and sanitization
- Scan for hardcoded secrets
- Check dependency vulnerabilities
- Verify HTTPS/TLS usage
- Review CORS and CSP configurations

**Findings Categories:**
- Critical: Exploitable vulnerabilities (injection, auth bypass)
- High: Security weaknesses (missing validation, weak crypto)
- Medium: Security improvements (logging, rate limiting)
- Low: Best practice suggestions

**Output:**
- Security findings with CVE references where applicable
- Vulnerability severity (CVSS scores)
- Remediation recommendations
- Compliance violations

**Duration:** 5-8 minutes

#### 2c. Performance Analysis (Performance Reviewer)
**Agent:** Performance Reviewer
**Actions:**
- Identify N+1 query problems
- Check for inefficient algorithms (O(n²) loops)
- Review database query optimization
- Verify proper caching strategies
- Check for memory leaks (unclosed resources)
- Analyze bundle size impact (frontend)
- Review async/await usage
- Identify blocking operations

**Findings Categories:**
- Critical: Performance regressions, memory leaks
- High: Inefficient algorithms, missing indexes
- Medium: Suboptimal caching, bundle size increases
- Low: Optimization opportunities

**Output:**
- Performance findings with impact estimates
- Algorithm complexity analysis
- Database optimization suggestions
- Profiling recommendations

**Duration:** 4-7 minutes

#### 2d. Standards Compliance (Standards Checker)
**Agent:** Standards Checker
**Actions:**
- Verify code follows team style guide
- Check documentation completeness
- Verify test coverage meets requirements (>80%)
- Check commit message format
- Verify file naming conventions
- Check for required file headers/licenses
- Verify API documentation (OpenAPI/JSDoc)
- Check changelog updates

**Findings Categories:**
- Critical: Missing required tests or documentation
- High: Incomplete documentation, low test coverage (<50%)
- Medium: Style guide violations, missing comments
- Low: Minor formatting, optional documentation

**Output:**
- Standards compliance report
- Documentation gaps
- Test coverage metrics
- Formatting violations

**Duration:** 4-6 minutes

### Phase 3: Findings Consolidation (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Collect all review agent findings
- Remove duplicate issues
- Prioritize findings by severity
- Classify as blocking vs. non-blocking
- Generate consolidated review report
- Calculate overall quality score
- Create actionable task list

**Output:**
- Consolidated code review report
- Blocking issues requiring fixes
- Advisory suggestions for improvement
- Overall quality metrics

**Duration:** 2-3 minutes

### Phase 4: Report Generation (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Format findings for readability
- Add code snippets and file references
- Include remediation suggestions
- Generate summary statistics
- Create GitHub/GitLab review comments
- Determine approval status (approve/request changes)

**Output:**
- Markdown review report
- GitHub PR comments
- Approval decision
- Follow-up task list

**Duration:** 2-3 minutes

## Review Report Structure

```markdown
# Code Review Report

**Pull Request:** #123 - Add user authentication feature
**Author:** @developer
**Reviewers:** Code Quality, Security, Performance, Standards
**Status:** ⚠️ Changes Requested
**Overall Score:** 72/100

## Executive Summary

This PR adds user authentication with JWT tokens. The implementation is functionally sound but has several security concerns and performance optimizations needed before merge.

**Blocking Issues:** 2
**High Priority:** 5
**Medium Priority:** 8
**Low Priority:** 12

---

## 🚨 Blocking Issues (Must Fix)

### Security: Hardcoded JWT Secret
- **File:** `src/auth/jwt.ts:15`
- **Severity:** Critical
- **Finding:** JWT secret key is hardcoded in source code
- **Remediation:** Move secret to environment variable
```typescript
// Bad
const secret = "my-super-secret-key";

// Good
const secret = process.env.JWT_SECRET;
```

### Testing: Missing Authentication Tests
- **File:** `tests/`
- **Severity:** Critical
- **Finding:** No tests for authentication logic (0% coverage)
- **Remediation:** Add unit tests for login, token validation, refresh

---

## ⚠️ High Priority Issues

### Performance: N+1 Query in User Lookup
- **File:** `src/controllers/user.ts:45`
- **Severity:** High
- **Impact:** 100ms+ latency per user
- **Remediation:** Use eager loading or JOIN query

[Additional findings...]

---

## 📊 Metrics

| Category | Score | Findings |
|----------|-------|----------|
| Code Quality | 75/100 | 8 issues |
| Security | 60/100 | 3 issues |
| Performance | 80/100 | 4 issues |
| Standards | 70/100 | 7 issues |
| **Overall** | **72/100** | **22 issues** |

---

## ✅ What Went Well

- Clean separation of concerns in auth middleware
- Proper async/await usage throughout
- Good error handling with custom exceptions
- Clear variable naming and code structure

---

## 📝 Recommendations

1. Fix the 2 blocking security and testing issues
2. Address high-priority performance concerns
3. Consider refactoring the authentication flow for better testability
4. Add API documentation for authentication endpoints

---

**Decision:** Request Changes
**Next Steps:** Fix blocking issues, re-run review pipeline
```

## Best Practices

### Orchestration
- **Parallel execution**: Run all 4 review agents simultaneously
- **Timeout handling**: Set 10-minute timeout per reviewer
- **Graceful degradation**: If one reviewer fails, continue with others
- **Incremental review**: For large PRs, review changed files only

### Finding Classification
- **Severity levels**: Critical > High > Medium > Low
- **Blocking criteria**: Critical security/functionality issues
- **Auto-approval threshold**: >85 score, zero critical/high issues
- **Consistency**: Same issue types always get same severity

### Report Quality
- **Actionable feedback**: Every finding includes remediation
- **Code examples**: Show bad vs. good patterns
- **File references**: Link to exact lines in source
- **Positive feedback**: Acknowledge good practices

### Performance
- **Scope limiting**: Review only changed files
- **Smart caching**: Skip unchanged files
- **Incremental analysis**: Compare against base branch
- **Tool selection**: Use fast linters (ESLint, not heavyweight analysis)

## Example Usage

### Triggering the Review

```bash
# Via Claude Code
You: "Review PR #123 using the code-review-pipeline workflow"

# Via CLI with GitHub
gh pr review 123 --workflow code-review-pipeline

# Via Git
git diff main...feature-branch | claude-review --workflow code-review
```

### Orchestrator Prompt Example

```markdown
Please review the following code changes using the code-review-pipeline workflow:

**Target:** Pull Request #456
**Branch:** feature/user-dashboard
**Changed Files:** 23 files (+850, -120 lines)
**Description:** Implement user dashboard with analytics

**Review Scope:**
- All changed files in `src/` and `tests/`
- Focus on security (authentication/authorization)
- Performance (database queries, caching)
- Test coverage (require >80%)

**Standards:**
- Follow team TypeScript style guide
- Require JSDoc for public APIs
- Conventional commit messages

**Thresholds:**
- Auto-approve if score >85 and zero critical issues
- Request changes if critical or >5 high-priority issues
- Comment only if score >70 and <3 high-priority issues
```

## Error Handling

### Common Issues

**Reviewer Timeout:**
- Action: Continue with completed reviewers, note timeout in report
- Escalation: Manual review for timed-out category

**Linter Failures:**
- Action: Report tool failure, continue with manual analysis
- Escalation: Fix linter configuration

**Large Changesets (>500 files):**
- Action: Sample-based review or request PR split
- Escalation: Extended timeout or multiple review batches

**Conflicting Findings:**
- Action: Orchestrator prioritizes higher-severity reviewer
- Escalation: Manual decision on contradictory recommendations

## Performance Metrics

### Execution Times by PR Size

| PR Size | Files Changed | Duration | Tokens |
|---------|---------------|----------|--------|
| Small | 1-10 files | 10-15 min | 20-30K |
| Medium | 11-50 files | 15-20 min | 40-60K |
| Large | 51-200 files | 20-25 min | 60-100K |
| X-Large | 200+ files | 25-30 min | 100K+ |

### Success Criteria

- **Completion rate**: >95% of reviews complete without errors
- **Accuracy**: <5% false positive rate on findings
- **Coverage**: Review 100% of changed code
- **Turnaround**: <25 minutes for 95% of reviews

## Integration Points

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Code Review Pipeline
  run: |
    claude-review --workflow code-review-pipeline \
      --pr ${{ github.event.pull_request.number }} \
      --format github-comments
```

### Git Hooks
```bash
# pre-push hook
claude-review --workflow code-review-pipeline \
  --branch $(git branch --show-current) \
  --quick
```

## Related Workflows

- **Full-Stack Feature Development**: Run before feature completion
- **Security Hardening**: Deep security analysis if vulnerabilities found
- **Testing QA Orchestration**: Comprehensive testing if coverage low
- **Bug Fix Debugging**: If critical bugs identified

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
