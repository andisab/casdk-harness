---
title: Code Review Techniques
description: Comprehensive code review practices including checklists, automated tools, and effective feedback
tags: [skill, code-review, quality, collaboration, best-practices]
type: skill
version: "1.0.0"
category: collaboration
---

# Code Review Techniques

## Overview

This skill provides comprehensive code review techniques covering review checklists, automated tools, security review, performance analysis, and effective communication practices. Use this skill to conduct thorough, constructive code reviews that improve code quality and share knowledge across the team.

**When to use this skill:**
- Reviewing pull requests before merge
- Conducting architectural reviews
- Performing security audits
- Sharing knowledge across team
- Maintaining code quality standards
- Onboarding new team members

## Key Concepts

### Goals of Code Review

**Primary Goals:**
1. **Find Defects**: Catch bugs before production
2. **Ensure Quality**: Maintain code standards and best practices
3. **Knowledge Sharing**: Spread understanding across team
4. **Mentorship**: Help developers improve skills
5. **Collective Ownership**: Share responsibility for code

**Secondary Benefits:**
- Documentation of design decisions
- Consistent coding style
- Reduced technical debt
- Improved team communication
- Faster onboarding

### Types of Code Reviews

**1. Formal Review (Pre-commit)**
- Required before merging to main
- Multiple reviewers
- Automated checks + manual review
- Most common in production environments

**2. Pair Programming**
- Continuous real-time review
- Two developers at one workstation
- Immediate feedback
- Best for complex features or learning

**3. Over-the-Shoulder Review**
- Informal, synchronous
- Developer walks through code
- Quick feedback on approach
- Good for small changes

**4. Tool-Assisted Review**
- Automated linting, SAST, testing
- Pre-commit hooks
- CI/CD pipeline checks
- Complement to manual review

## Implementation

### Code Review Checklist

```markdown
## Functionality
- [ ] Code does what it's supposed to do
- [ ] Edge cases are handled
- [ ] Error conditions are handled appropriately
- [ ] No obvious bugs or logic errors
- [ ] Code handles concurrent access if applicable

## Design & Architecture
- [ ] Code follows existing patterns and conventions
- [ ] No unnecessary complexity
- [ ] Appropriate design patterns used
- [ ] Code is modular and reusable
- [ ] Dependencies are appropriate
- [ ] No circular dependencies
- [ ] Follows SOLID principles

## Code Quality
- [ ] Code is readable and self-documenting
- [ ] Functions are small and focused
- [ ] Variable and function names are descriptive
- [ ] No commented-out code
- [ ] No duplicate code (DRY principle)
- [ ] Magic numbers replaced with constants
- [ ] Consistent with team style guide

## Performance
- [ ] No obvious performance issues
- [ ] Algorithms have appropriate complexity
- [ ] Database queries are optimized (no N+1)
- [ ] Appropriate caching if needed
- [ ] No memory leaks
- [ ] Resources are properly closed

## Security
- [ ] No hardcoded secrets or credentials
- [ ] Input validation implemented
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] CSRF tokens used appropriately
- [ ] Authentication and authorization checks
- [ ] Sensitive data is encrypted
- [ ] No exposure of sensitive information in logs

## Testing
- [ ] Adequate test coverage (>80% for new code)
- [ ] Tests are meaningful, not just coverage padding
- [ ] Edge cases are tested
- [ ] Error conditions are tested
- [ ] Tests are independent and isolated
- [ ] No flaky tests introduced
- [ ] Tests follow AAA pattern (Arrange, Act, Assert)

## Documentation
- [ ] Public APIs are documented
- [ ] Complex logic has explanatory comments
- [ ] README updated if needed
- [ ] API documentation updated (OpenAPI/Swagger)
- [ ] Changelog updated for user-facing changes
- [ ] Migration notes if database changes

## Dependencies
- [ ] New dependencies are justified
- [ ] Dependencies are up-to-date
- [ ] No vulnerable dependencies (check security audit)
- [ ] License compatibility verified
- [ ] Bundle size impact considered (frontend)

## Git & Process
- [ ] Commit messages are descriptive
- [ ] Commits are logical and atomic
- [ ] No merge conflicts
- [ ] Branch is up-to-date with main
- [ ] CI/CD pipeline passes
- [ ] Breaking changes are documented
```

### Review Workflow

```python
# Example: GitHub PR Review Process

def review_pull_request(pr_number: int) -> ReviewResult:
    """
    Comprehensive pull request review process.

    Steps:
    1. Understand the context (read PR description, linked issues)
    2. Check automated checks (CI/CD, linting, tests)
    3. Review code changes
    4. Run code locally if needed
    5. Provide feedback
    6. Approve or request changes
    """

    # Step 1: Context
    pr = github.get_pull_request(pr_number)
    issue = pr.linked_issue
    print(f"Reviewing: {pr.title}")
    print(f"Related issue: {issue.title if issue else 'None'}")
    print(f"Description: {pr.description}")

    # Step 2: Automated Checks
    checks = pr.get_checks()
    if not all(check.status == "success" for check in checks):
        return ReviewResult(
            status="CHANGES_REQUESTED",
            comment="Please fix failing CI/CD checks before review."
        )

    # Step 3: Code Review
    files_changed = pr.get_files()
    comments = []

    for file in files_changed:
        # Check file-level concerns
        if file.lines_changed > 500:
            comments.append({
                "file": file.name,
                "comment": "⚠️ Large file change. Consider breaking into smaller PRs."
            })

        # Review specific changes
        for change in file.changes:
            # Check for common issues
            if "TODO" in change.added_line:
                comments.append({
                    "file": file.name,
                    "line": change.line_number,
                    "comment": "❓ TODO comment. Should this be done before merge?"
                })

            if "console.log" in change.added_line:
                comments.append({
                    "file": file.name,
                    "line": change.line_number,
                    "comment": "🔍 Debug console.log left in code. Remove before merge."
                })

            if "password" in change.added_line.lower() and "=" in change.added_line:
                comments.append({
                    "file": file.name,
                    "line": change.line_number,
                    "comment": "🚨 Potential hardcoded password. Use environment variable."
                })

    # Step 4: Local Testing (if needed)
    if pr.affects_critical_path():
        local_test_result = run_local_tests(pr.branch)
        if not local_test_result.passed:
            comments.append({
                "general": True,
                "comment": f"❌ Local testing failed: {local_test_result.error}"
            })

    # Step 5: Provide Feedback
    return ReviewResult(
        status="APPROVED" if len(comments) == 0 else "CHANGES_REQUESTED",
        comments=comments,
        summary=generate_review_summary(pr, comments)
    )
```

### Effective Feedback Examples

**❌ Poor Feedback:**
```
"This is wrong."
"Bad code."
"Why did you do it this way?"
"This won't work."
```

**✅ Good Feedback:**
```
"Consider using a dictionary here instead of multiple if-else statements.
This would make the code more maintainable and easier to extend."

"This could potentially cause a race condition if two requests
come in simultaneously. Consider using a database lock or mutex.
Example: db.query(User).with_for_update().filter(...)"

"Great use of the factory pattern here! One suggestion: we could
extract the validation logic into a separate validator class to
make it more reusable. What do you think?"

"I noticed this query could have an N+1 problem with large datasets.
We might want to use eager loading here. Would you like me to show
you an example?"
```

### Comment Categories and Tone

```python
# Use prefixes to indicate comment severity

# 🔴 Blocking (must fix)
"🔴 BLOCKING: This SQL query is vulnerable to injection attacks.
Please use parameterized queries instead."

# 🟡 Important (should fix)
"🟡 SUGGESTION: This function is doing too much. Consider splitting
into smaller, focused functions following Single Responsibility Principle."

# 🟢 Optional (nice to have)
"🟢 NIT: Minor style issue - we typically use const instead of let
when the variable isn't reassigned."

# 💡 Learning opportunity
"💡 FYI: You might find the functools.lru_cache decorator useful here
for memoization. Not necessary for this PR, but good to know!"

# ❓ Question (seeking clarification)
"❓ QUESTION: Why did we choose to use polling here instead of
websockets? Is there a specific requirement I'm missing?"

# ✅ Praise (positive reinforcement)
"✅ Nice! I really like how you handled the error cases here.
Very thorough!"
```

### Automated Review Tools

```yaml
# .github/workflows/code-review.yml
name: Automated Code Review

on: [pull_request]

jobs:
  code-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Linting
      - name: Run ESLint
        run: npm run lint

      - name: Run Prettier
        run: npm run format:check

      # Type Checking
      - name: TypeScript Check
        run: npm run typecheck

      # Security Scanning
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1

      - name: Dependency Security Audit
        run: npm audit --audit-level=moderate

      # Code Quality Metrics
      - name: SonarCloud Scan
        uses: SonarSource/sonarcloud-github-action@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}

      # Test Coverage
      - name: Run Tests with Coverage
        run: npm run test:coverage

      - name: Coverage Report
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json
          fail_ci_if_error: true
          verbose: true

  # Size Impact Analysis
  bundle-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Analyze Bundle Size
        uses: andresz1/size-limit-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Best Practices

### For Reviewers

**Before Reviewing:**
- ✅ Understand the context (read PR description, linked issues)
- ✅ Check automated checks passed
- ✅ Allocate sufficient time (don't rush)
- ✅ Review in short sessions (max 60 minutes)

**During Review:**
- ✅ Start with understanding intent, then implementation
- ✅ Look at tests first to understand expected behavior
- ✅ Check for security vulnerabilities
- ✅ Suggest alternatives, don't demand
- ✅ Praise good code
- ✅ Ask questions instead of making statements
- ✅ Provide context and examples
- ✅ Distinguish between "must fix" and "nice to have"

**Don't:**
- ❌ Be condescending or dismissive
- ❌ Focus only on style issues (use linter instead)
- ❌ Review your own major code changes alone
- ❌ Approve without actually reviewing
- ❌ Let reviews sit for days
- ❌ Nitpick unrelated code

### For Authors

**Before Requesting Review:**
- ✅ Self-review first (review your own diff)
- ✅ Run tests and linters locally
- ✅ Write clear PR description
- ✅ Link related issues
- ✅ Add screenshots for UI changes
- ✅ Keep PRs small (<400 lines)
- ✅ Commit message follows conventions

**During Review:**
- ✅ Respond to all comments
- ✅ Ask for clarification if needed
- ✅ Be open to feedback
- ✅ Don't take criticism personally
- ✅ Push changes in response to feedback
- ✅ Mark resolved comments as resolved

**Don't:**
- ❌ Get defensive
- ❌ Ignore feedback
- ❌ Submit huge PRs (split into smaller ones)
- ❌ Force push after review starts (use new commits)
- ❌ Rush reviewers

### Review Response Times

**Target Response Times:**
- Critical/Blocking PR: < 4 hours
- Normal PR: < 24 hours
- Low Priority PR: < 48 hours

**Review SLA:**
- First response: within 24 hours
- Follow-up responses: within 8 hours (during business hours)
- Final approval: within 48 hours of submission

## Specialized Review Types

### Security Review

```markdown
## Security Review Checklist

### Authentication & Authorization
- [ ] Proper authentication checks on all endpoints
- [ ] Authorization checks (user can only access their own data)
- [ ] Password hashing (bcrypt, Argon2)
- [ ] Secure session management
- [ ] JWT tokens properly validated

### Input Validation
- [ ] All user input is validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] CSRF tokens for state-changing operations
- [ ] File upload validation (type, size, content)

### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] HTTPS enforced for all communications
- [ ] No secrets in code (use environment variables)
- [ ] PII handling follows regulations (GDPR, CCPA)
- [ ] Secure headers configured (HSTS, CSP, etc.)

### API Security
- [ ] Rate limiting implemented
- [ ] API authentication required
- [ ] CORS properly configured
- [ ] Appropriate HTTP methods used
- [ ] Sensitive data not in URL parameters

### Dependencies
- [ ] No known vulnerabilities (npm audit, Snyk)
- [ ] Dependencies from trusted sources
- [ ] Minimal dependency footprint
```

### Performance Review

```markdown
## Performance Review Checklist

### Database
- [ ] No N+1 query problems
- [ ] Appropriate indexes on queried columns
- [ ] Query complexity is acceptable (EXPLAIN ANALYZE)
- [ ] Connection pooling configured
- [ ] Transactions used appropriately

### Caching
- [ ] Appropriate caching strategy
- [ ] Cache invalidation logic correct
- [ ] Cache TTL configured appropriately

### Frontend
- [ ] Bundle size impact analyzed
- [ ] Images optimized
- [ ] Lazy loading for non-critical resources
- [ ] Unnecessary re-renders minimized (React)
- [ ] Web vitals considered (LCP, FID, CLS)

### API
- [ ] Pagination for large datasets
- [ ] Response size reasonable
- [ ] Appropriate HTTP caching headers
- [ ] No synchronous operations on critical path

### Algorithms
- [ ] Time complexity is acceptable
- [ ] Space complexity is acceptable
- [ ] No unnecessary loops or iterations
```

## Common Review Patterns

### Pattern: Suggest, Don't Demand

```markdown
❌ "Change this to use async/await."

✅ "Have you considered using async/await here? It might make
the error handling clearer. Something like:

```javascript
async function fetchData() {
  try {
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    logger.error('Failed to fetch', error);
    throw error;
  }
}
```

What do you think?"
```

### Pattern: Ask Questions

```markdown
❌ "This is inefficient."

✅ "I'm curious about the performance of this approach with large
datasets. Have we tested it with 10,000+ items? Would a Map data
structure be more efficient here for O(1) lookups?"
```

### Pattern: Provide Context

```markdown
❌ "Don't use var."

✅ "We typically use 'const' or 'let' instead of 'var' to avoid
issues with function-scoped hoisting. 'const' is preferred when
the variable won't be reassigned.

Example:
const userEmail = 'user@example.com'; // Won't be reassigned
let counter = 0; // Will be reassigned
```

### Pattern: Acknowledge Good Code

```markdown
✅ "Love this! The error handling here is really comprehensive.
The specific error messages will make debugging much easier."

✅ "Great catch on the edge case with negative numbers. This
kind of defensive programming prevents a lot of bugs."

✅ "Nice refactoring! This is much more readable than the previous
version."
```

## Related Skills & Conventions

- [Code Review Pipeline Workflow](../workflows/code-review-pipeline.md) - Automated review workflow
- [Testing Strategies](./testing-strategies.md) - Reviewing test quality
- [Security Hardening](../workflows/security-hardening.md) - Security review workflow
- [Git Workflow](./git-workflow.md) - PR and branch management

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
