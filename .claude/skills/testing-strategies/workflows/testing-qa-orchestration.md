---
title: Testing & QA Orchestration
description: Comprehensive testing workflow coordinating unit, integration, and E2E tests with automated reporting
tags: [workflow, testing, qa, automation, coverage]
type: workflow
version: "1.0.0"
orchestration:
  pattern: sequential-with-parallel-execution
  agents: 5
  estimatedTime: "20-35 minutes"
  complexity: medium-high
---

# Testing & QA Orchestration Workflow

## Overview

This workflow orchestrates comprehensive testing across all layers of your application, from unit tests through end-to-end scenarios. It combines sequential planning with parallel test execution for optimal speed while maintaining thorough coverage.

**Use this workflow when:**
- Validating new features before deployment
- Running comprehensive QA before releases
- Generating test coverage reports
- Identifying gaps in test coverage
- Automating regression testing

**Pattern:** Sequential planning → Parallel execution → Consolidated reporting
**Estimated execution:** 20-35 minutes depending on test suite size
**Token usage:** ~50K-90K tokens across all agents

## Agent Roles

### 1. Orchestrator Agent
- **Responsibility**: Coordinate test execution, consolidate results, generate reports
- **Tools**: `Task`, `TodoWrite`, `Read`, `Bash`, `Write`
- **Permissions**: Read-only on codebase, full access to test runners
- **Context**: Test strategy, coverage requirements, CI/CD integration

### 2. Unit Test Generator Agent
- **Responsibility**: Generate and execute unit tests for individual components
- **Tools**: `Read`, `Write`, `Edit`, `Bash`, `Grep`
- **Permissions**: Full access to test files and source code
- **Context**: Testing frameworks (Jest, Pytest, etc.), mocking patterns, assertion libraries

### 3. Integration Test Agent
- **Responsibility**: Test component interactions and API endpoints
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to integration tests, database access
- **Context**: API testing, database seeding, test fixtures, test containers

### 4. E2E Test Agent
- **Responsibility**: Execute end-to-end user workflow tests
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to E2E tests, browser automation tools
- **Context**: Playwright/Cypress, page objects, user scenarios, visual regression

### 5. Test Reporter Agent
- **Responsibility**: Aggregate results, calculate metrics, generate reports
- **Tools**: `Read`, `Bash`, `Write`
- **Permissions**: Read test results, write reports
- **Context**: Coverage tools, report formats, quality gates, metrics dashboards

## Orchestration Flow

### Phase 1: Test Planning (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Analyze changed files to determine test scope
- Identify which test types are needed (unit, integration, E2E)
- Set coverage targets (>80% for unit, >70% for integration)
- Configure test environment (databases, mock services)
- Create test execution plan
- Initialize test results collection

**Output:**
- Test execution plan
- Activated test agents
- Coverage targets
- Environment configuration

**Duration:** 3-5 minutes

### Phase 2: Test Environment Setup (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Start test databases (Docker containers)
- Initialize mock services
- Seed test data
- Configure environment variables
- Verify service health checks

**Output:**
- Running test environment
- Test database ready
- Mock services available

**Duration:** 2-4 minutes

### Phase 3: Parallel Test Execution

Run these 3 agents **in parallel** for maximum efficiency:

#### 3a. Unit Testing (Unit Test Generator)
**Agent:** Unit Test Generator
**Actions:**
- Identify untested or under-tested code
- Generate missing unit tests using TDD patterns
- Execute unit test suite
- Calculate line and branch coverage
- Identify edge cases and boundary conditions
- Generate test fixtures and mocks
- Run tests in watch mode for feedback

**Test Coverage:**
- Functions and methods (100% of public API)
- Edge cases and error conditions
- Boundary values and null handling
- Mocking external dependencies

**Output:**
- Unit test files (`.test.ts`, `_test.py`, etc.)
- Test coverage report (line, branch, function coverage)
- Failed test details
- Coverage gaps

**Success Criteria:**
- All tests passing
- >80% line coverage
- >75% branch coverage

**Duration:** 8-12 minutes

#### 3b. Integration Testing (Integration Test Agent)
**Agent:** Integration Test Agent
**Actions:**
- Test API endpoint functionality
- Validate database operations (CRUD)
- Test service layer interactions
- Verify authentication and authorization flows
- Test error handling and validation
- Check data consistency across operations
- Test transaction rollbacks

**Test Scenarios:**
- API contract testing (request/response validation)
- Database integration (queries, transactions)
- Service-to-service communication
- Authentication flows (login, logout, refresh)
- Error scenarios (400, 401, 403, 404, 500)

**Output:**
- Integration test files
- API test results
- Database operation validation
- Service integration reports

**Success Criteria:**
- All integration tests passing
- >70% integration coverage
- All API endpoints tested

**Duration:** 8-15 minutes

#### 3c. E2E Testing (E2E Test Agent)
**Agent:** E2E Test Agent
**Actions:**
- Execute critical user journey tests
- Validate complete workflows (signup → login → action → logout)
- Test UI interactions and navigation
- Verify data persistence across sessions
- Run visual regression tests
- Test across multiple browsers (Chrome, Firefox, Safari)
- Capture screenshots and videos of failures

**Test Scenarios:**
- User registration and onboarding
- Login and authentication flows
- Core feature workflows
- Payment and checkout processes
- Admin dashboard operations
- Mobile responsive behavior

**Output:**
- E2E test results
- Screenshots and videos
- Performance metrics (page load times)
- Visual regression comparisons

**Success Criteria:**
- All critical paths tested
- <5% flaky test rate
- All tests passing

**Duration:** 10-18 minutes

### Phase 4: Results Aggregation (Test Reporter)
**Agent:** Test Reporter
**Actions:**
- Collect test results from all agents
- Calculate overall coverage metrics
- Identify failed tests and patterns
- Generate coverage reports (HTML, XML, JSON)
- Calculate quality scores
- Identify regression issues
- Compare with previous test runs

**Metrics Collected:**
- Total tests: passed, failed, skipped
- Coverage: line, branch, function, statement
- Execution time per test suite
- Flaky test identification
- Code complexity vs. coverage correlation

**Output:**
- Consolidated test report
- Coverage reports (HTML dashboard)
- Failed test analysis
- Quality metrics dashboard

**Duration:** 3-5 minutes

### Phase 5: Report Generation (Test Reporter)
**Agent:** Test Reporter
**Actions:**
- Format test results for readability
- Generate executive summary
- Create actionable recommendations
- Produce CI/CD compatible outputs
- Generate GitHub PR comments
- Update test metrics dashboard

**Output:**
- Markdown test report
- HTML coverage dashboard
- JUnit XML for CI/CD
- GitHub/GitLab comments
- Quality gate decision (pass/fail)

**Duration:** 2-3 minutes

## Test Report Structure

```markdown
# QA Test Report

**Build:** #456
**Branch:** feature/user-authentication
**Commit:** abc123def
**Timestamp:** 2025-10-25T14:30:00Z
**Status:** ✅ Passed
**Overall Coverage:** 84.5%

---

## 📊 Executive Summary

All test suites passed successfully with 84.5% overall coverage, exceeding the 80% target. The implementation includes comprehensive unit tests, integration tests for all API endpoints, and E2E tests covering critical user journeys.

**Quality Gate:** ✅ PASSED
- All tests passing (234/234)
- Coverage >80% (84.5%)
- Zero critical issues
- <5% flaky tests (2.1%)

---

## 🧪 Test Results by Type

### Unit Tests
- **Status:** ✅ Passed
- **Tests:** 156 passed, 0 failed, 2 skipped
- **Coverage:** 86.3% lines, 81.2% branches
- **Duration:** 8.2 seconds
- **Failures:** None

### Integration Tests
- **Status:** ✅ Passed
- **Tests:** 45 passed, 0 failed, 0 skipped
- **Coverage:** 78.9% of API endpoints
- **Duration:** 42.5 seconds
- **Failures:** None

### E2E Tests
- **Status:** ✅ Passed
- **Tests:** 33 passed, 0 failed, 1 skipped (known browser issue)
- **Coverage:** 12 critical user journeys
- **Duration:** 2m 18s
- **Failures:** None

---

## 📈 Coverage Metrics

| Category | Coverage | Target | Status |
|----------|----------|--------|--------|
| Lines | 86.3% | >80% | ✅ |
| Branches | 81.2% | >75% | ✅ |
| Functions | 88.7% | >80% | ✅ |
| Statements | 85.9% | >80% | ✅ |

### Coverage by Module

| Module | Lines | Branches | Functions |
|--------|-------|----------|-----------|
| `src/auth/` | 92.1% | 87.3% | 95.0% |
| `src/api/` | 84.5% | 79.8% | 86.2% |
| `src/db/` | 78.9% | 72.1% | 82.3% |
| `src/utils/` | 88.3% | 84.5% | 90.1% |

---

## 🎯 Test Quality Metrics

- **Test Reliability:** 97.9% (5 flaky tests out of 234)
- **Avg Execution Time:** 3m 8s (within 5min target)
- **Test Maintenance:** 12 tests updated this cycle
- **New Tests Added:** 23 tests (covering new auth features)

---

## 🔍 Coverage Gaps

### Files with <80% Coverage

1. **src/auth/refresh-token.ts** (67.2%)
   - Missing: Error handling for expired tokens
   - Missing: Edge case for concurrent refresh requests
   - Recommendation: Add 3-4 unit tests

2. **src/db/migrations/004-add-auth.ts** (45.1%)
   - Note: Migration files have lower coverage by design
   - Recommendation: Test via integration tests (already covered)

---

## ⚠️ Flaky Tests (5 identified)

1. **E2E: User Login Flow** (2.1% flake rate)
   - Issue: Occasional timeout waiting for redirect
   - Recommendation: Increase timeout from 5s to 10s

---

## ✅ Highlights

- 23 new tests added covering authentication feature
- 100% coverage on critical auth flows
- Zero regression issues detected
- All E2E tests passing across Chrome, Firefox, Safari
- Performance: All page loads <2s

---

## 📝 Recommendations

1. ✅ Ready for deployment - all quality gates passed
2. Consider adding tests for refresh token edge cases
3. Monitor flaky E2E login test - may need timeout adjustment
4. Coverage trending upward (+3.2% from last build)

---

**Next Steps:** Approved for merge and deployment to staging

**Detailed Reports:**
- [HTML Coverage Report](./coverage/index.html)
- [JUnit XML Results](./test-results.xml)
- [E2E Screenshots](./e2e/screenshots/)
```

## Best Practices

### Test Strategy
- **Pyramid structure**: Many unit tests, fewer integration, even fewer E2E
- **Fast feedback**: Run unit tests first (fail fast)
- **Parallel execution**: Run test suites simultaneously
- **Isolation**: Tests don't depend on each other

### Coverage Goals
- **Unit tests**: >80% line coverage
- **Integration tests**: All API endpoints covered
- **E2E tests**: All critical user paths covered
- **Edge cases**: Error conditions and boundary values

### Test Quality
- **Deterministic**: Tests produce same results every run
- **Fast**: Unit tests <10s, integration <60s, E2E <5min
- **Isolated**: Use mocks/stubs for external dependencies
- **Maintainable**: Clear test names, DRY principles

### Performance
- **Parallel execution**: Run test types simultaneously
- **Smart caching**: Cache dependencies and build artifacts
- **Incremental testing**: Test only changed code when possible
- **Resource management**: Clean up test data and connections

## Example Usage

### Triggering the Workflow

```bash
# Via Claude Code
You: "Run comprehensive QA tests using testing-qa-orchestration workflow"

# Via CLI
npm run test:qa -- --workflow testing-qa-orchestration

# Via CI/CD
- name: QA Testing
  run: claude-test --workflow testing-qa-orchestration --coverage-target 80
```

### Orchestrator Prompt Example

```markdown
Run comprehensive QA testing using the testing-qa-orchestration workflow:

**Scope:** All code in `src/auth/` directory
**Changed Files:** 8 files modified for user authentication feature

**Test Requirements:**
- Unit tests: >80% coverage for all auth functions
- Integration tests: All auth API endpoints (login, logout, refresh, verify)
- E2E tests: Complete user registration and login flows

**Quality Gates:**
- All tests must pass
- Coverage must exceed 80%
- Zero high-priority issues
- E2E tests passing in Chrome, Firefox, Safari

**Environment:**
- Use test database (PostgreSQL in Docker)
- Mock email service (Mailhog)
- Mock payment gateway (test mode)

**Reporting:**
- Generate HTML coverage report
- Post summary to PR #456
- Update quality dashboard
```

## Error Handling

### Common Failure Scenarios

**Unit Test Failures:**
- Action: Identify failing tests, provide detailed error messages
- Escalation: If >10% fail, halt pipeline for investigation

**Integration Test Failures:**
- Action: Check service availability, database connection
- Escalation: Review API contract changes, data model migrations

**E2E Test Failures:**
- Action: Capture screenshots/videos, analyze flakiness
- Escalation: If consistent failure, delegate to Bug Fix workflow

**Coverage Below Target:**
- Action: Identify uncovered code paths
- Escalation: Generate missing tests, re-run suite

**Environment Issues:**
- Action: Restart containers, verify service health
- Escalation: Manual environment debugging

### Recovery Strategies

1. **Retry flaky tests**: Automatically retry failed tests up to 3 times
2. **Parallel failure isolation**: One suite failure doesn't stop others
3. **Checkpoint saves**: Save test results even if later phases fail
4. **Detailed logging**: Capture logs for all test execution
5. **Screenshot evidence**: E2E failures include visual proof

## Performance Metrics

### Execution Times by Test Count

| Test Count | Unit | Integration | E2E | Total |
|------------|------|-------------|-----|-------|
| Small (<50) | 5-10s | 30-60s | 2-3min | 5-8min |
| Medium (50-200) | 10-30s | 1-2min | 3-5min | 10-15min |
| Large (200-500) | 30-60s | 2-4min | 5-8min | 15-25min |
| X-Large (>500) | 1-2min | 4-8min | 8-15min | 25-35min |

### Success Criteria

- **Test pass rate**: >95% on first run
- **Flaky test rate**: <5% across all suites
- **Coverage compliance**: >80% of builds meet coverage target
- **Execution speed**: <30 minutes for 95% of test runs

## Integration with CI/CD

```yaml
# GitHub Actions example
name: QA Testing

on: [push, pull_request]

jobs:
  qa-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Test Environment
        run: |
          docker-compose up -d test-db
          npm install

      - name: Run QA Orchestration
        run: |
          claude-test --workflow testing-qa-orchestration \
            --coverage-target 80 \
            --format github-actions

      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json

      - name: Publish Test Results
        uses: EnricoMi/publish-unit-test-result-action@v2
        with:
          files: ./test-results.xml
```

## Related Workflows

- **Full-Stack Feature Development**: Run tests during development
- **Code Review Pipeline**: Quick smoke tests before review
- **Bug Fix Debugging**: Regression test after fixes
- **Security Hardening**: Security-focused test execution

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
