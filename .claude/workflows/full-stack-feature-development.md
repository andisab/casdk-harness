---
title: Full-Stack Feature Development
description: Multi-agent orchestration workflow for implementing complete features from backend to deployment
tags: [workflow, orchestration, full-stack, development, multi-agent]
type: workflow
version: "1.0.0"
orchestration:
  pattern: sequential-with-gates
  agents: 7
  estimatedTime: "30-60 minutes"
  complexity: high
---

# Full-Stack Feature Development Workflow

## Overview

This workflow orchestrates 7 specialized agents to implement a complete full-stack feature from initial architecture through production deployment. The workflow follows a sequential pattern with verification gates between phases, ensuring quality and consistency at each step.

**Use this workflow when:**
- Implementing new features that span backend, frontend, and database
- Building features that require coordinated development across the stack
- Ensuring consistent architecture and security practices
- Automating the complete development-to-deployment pipeline

**Pattern:** Sequential pipeline with verification gates
**Estimated execution:** 30-60 minutes depending on feature complexity
**Token usage:** ~80K-150K tokens across all agents

## Agent Roles

### 1. Orchestrator Agent
- **Responsibility**: Overall coordination, task delegation, and quality gates
- **Tools**: `Task`, `TodoWrite`, `Read`, `Grep`
- **Permissions**: Read-only on codebase, full access to agent management
- **Context**: High-level feature requirements and acceptance criteria

### 2. Backend Architect Agent
- **Responsibility**: Design API endpoints, business logic, and data flow
- **Tools**: `Read`, `Write`, `Edit`, `Grep`, `Bash`
- **Permissions**: Full access to backend source code and tests
- **Context**: API design patterns, authentication, error handling standards

### 3. Database Architect Agent
- **Responsibility**: Schema design, migrations, query optimization
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to database migrations and models
- **Context**: Database conventions, indexing strategies, data validation

### 4. Frontend Developer Agent
- **Responsibility**: UI components, state management, API integration
- **Tools**: `Read`, `Write`, `Edit`, `Bash`, `Grep`
- **Permissions**: Full access to frontend source code and components
- **Context**: Component patterns, styling conventions, accessibility standards

### 5. Test Automator Agent
- **Responsibility**: Unit tests, integration tests, E2E test coverage
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to test directories and test runners
- **Context**: Testing frameworks, coverage requirements, mocking patterns

### 6. Security Auditor Agent
- **Responsibility**: Security review, vulnerability scanning, compliance checks
- **Tools**: `Read`, `Bash`, `Grep`
- **Permissions**: Read-only on source, execute security scanning tools
- **Context**: OWASP guidelines, auth patterns, data validation requirements

### 7. Deployment Engineer Agent
- **Responsibility**: Build verification, deployment configs, environment setup
- **Tools**: `Read`, `Write`, `Edit`, `Bash`
- **Permissions**: Full access to build configs and deployment scripts
- **Context**: CI/CD patterns, environment variables, rollback procedures

## Orchestration Flow

### Phase 1: Planning & Architecture (Orchestrator)
**Agent:** Orchestrator
**Actions:**
- Parse feature requirements and acceptance criteria
- Create task breakdown with dependencies
- Identify affected components (backend, frontend, database)
- Set up verification gates for each phase
- Initialize todo list for tracking

**Output:**
- Detailed task plan with dependencies
- List of agents to activate and their sequences
- Success criteria for each phase

**Verification Gate:** Architecture plan reviewed and approved

### Phase 2: Database Schema Design (Database Architect)
**Agent:** Database Architect
**Actions:**
- Design database schema changes (tables, columns, indexes)
- Create migration files with rollback support
- Define data models and relationships
- Plan query optimization strategies
- Document schema changes

**Output:**
- Migration files (up/down migrations)
- Updated data models
- Schema documentation

**Verification Gate:** Schema design passes validation, no breaking changes

### Phase 3: Backend Implementation (Backend Architect)
**Agent:** Backend Architect
**Actions:**
- Implement API endpoints following REST/GraphQL conventions
- Add business logic and data validation
- Integrate with database models
- Implement error handling and logging
- Add API documentation (OpenAPI/Swagger)

**Output:**
- API endpoint implementations
- Business logic modules
- Error handling middleware
- API documentation

**Verification Gate:** Backend code passes linting, type checking, and initial tests

### Phase 4: Frontend Implementation (Frontend Developer)
**Agent:** Frontend Developer
**Actions:**
- Create UI components following design system
- Implement state management (Redux, Context, etc.)
- Integrate with backend API endpoints
- Add form validation and error handling
- Implement loading states and error boundaries

**Output:**
- React/Vue/Angular components
- State management integration
- API client integration
- UI error handling

**Verification Gate:** Frontend builds successfully, no console errors

### Phase 5: Test Coverage (Test Automator)
**Agent:** Test Automator
**Actions:**
- Write unit tests for backend logic (>80% coverage)
- Create integration tests for API endpoints
- Implement E2E tests for user workflows
- Add test fixtures and mocks
- Verify all tests pass

**Output:**
- Unit test suites
- Integration test suites
- E2E test scenarios
- Test coverage report

**Verification Gate:** All tests passing, coverage meets requirements (>80%)

### Phase 6: Security Review (Security Auditor)
**Agent:** Security Auditor
**Actions:**
- Run SAST (Static Application Security Testing)
- Check for SQL injection vulnerabilities
- Verify authentication and authorization
- Review input validation and sanitization
- Check for exposed secrets or sensitive data
- Scan dependencies for vulnerabilities

**Output:**
- Security scan report
- List of vulnerabilities (if any)
- Recommendations for fixes

**Verification Gate:** No high/critical vulnerabilities, all recommendations addressed

### Phase 7: Deployment Preparation (Deployment Engineer)
**Agent:** Deployment Engineer
**Actions:**
- Update build configuration
- Configure environment variables
- Update CI/CD pipeline if needed
- Create deployment documentation
- Verify build process
- Test in staging environment

**Output:**
- Updated build configs
- Environment setup documentation
- Deployment runbook
- Staging verification results

**Verification Gate:** Staging deployment successful, all smoke tests passing

## Best Practices

### Orchestration
- **Explicit delegation**: Clearly specify which agent handles each task
- **Context isolation**: Each agent maintains its own context window
- **Gate enforcement**: Don't proceed if verification gate fails
- **Parallel opportunities**: Database and backend planning can happen simultaneously

### Communication
- **Handoff documents**: Each agent produces clear output for the next
- **Shared state**: Use file system or shared data structures for coordination
- **Status updates**: Orchestrator tracks progress via todo list
- **Error reporting**: Failed gates should report specific issues

### Performance
- **Token efficiency**: Minimize redundant context loading
- **Lazy activation**: Only activate agents when needed
- **Early termination**: Stop workflow if critical gates fail
- **Incremental work**: Break large features into smaller workflows

### Quality
- **Double verification**: Critical phases reviewed by multiple agents
- **Rollback capability**: Each phase should be reversible
- **Documentation**: Every agent documents their work
- **Compliance**: Security and standards checked at each phase

## Example Usage

### Triggering the Workflow

```bash
# Via Claude Code
You: "Implement a new user profile feature with avatar upload using the full-stack workflow"

# Via CLI
node run-workflow.js full-stack-feature-development \
  --feature "user profile with avatar upload" \
  --requirements requirements.md
```

### Orchestrator Prompt Example

```markdown
I need to implement a complete user profile feature with the following requirements:

**Feature:** User Profile Management
**Requirements:**
- Users can view and edit their profile information
- Support for avatar image upload (max 5MB)
- Profile fields: name, bio, location, avatar URL
- Backend API with validation
- Frontend form with real-time validation
- Secure file upload to S3/cloud storage

Use the full-stack-feature-development workflow to coordinate this implementation.

**Acceptance Criteria:**
- [ ] Database migration creates profile table
- [ ] Backend API endpoints (GET /profile, PUT /profile, POST /profile/avatar)
- [ ] Frontend profile page with edit functionality
- [ ] File upload with size and type validation
- [ ] >80% test coverage
- [ ] No security vulnerabilities
- [ ] Deployed to staging successfully
```

## Error Handling

### Common Failure Scenarios

**Database Migration Failure:**
- Agent: Database Architect
- Action: Review migration, fix conflicts, re-test
- Escalation: Orchestrator pauses workflow for manual review

**Test Failures:**
- Agent: Test Automator
- Action: Identify failing tests, delegate fixes to appropriate agent
- Escalation: Return to Backend/Frontend phase for corrections

**Security Vulnerabilities Found:**
- Agent: Security Auditor
- Action: Document vulnerabilities, delegate fixes
- Escalation: Critical vulnerabilities block deployment

**Build Failures:**
- Agent: Deployment Engineer
- Action: Analyze build logs, identify root cause
- Escalation: Return to development phase if code changes needed

### Recovery Strategies

1. **Checkpoint saves**: Each phase completion creates a git commit
2. **Rollback capability**: Failed gates can revert to last checkpoint
3. **Partial success**: Completed phases preserved, resume from failure point
4. **Manual intervention**: Orchestrator can request human review at any gate

## Performance Metrics

### Estimated Execution Times

| Phase | Agent | Time | Tokens |
|-------|-------|------|--------|
| Planning | Orchestrator | 2-5 min | 5-10K |
| Database | Database Architect | 5-10 min | 10-15K |
| Backend | Backend Architect | 10-20 min | 20-30K |
| Frontend | Frontend Developer | 10-20 min | 20-30K |
| Testing | Test Automator | 10-15 min | 15-25K |
| Security | Security Auditor | 5-10 min | 10-15K |
| Deployment | Deployment Engineer | 5-10 min | 10-15K |
| **Total** | **7 agents** | **30-60 min** | **80-150K** |

### Success Metrics

- **Feature completeness**: All acceptance criteria met
- **Code quality**: Linting passed, >80% test coverage
- **Security**: Zero high/critical vulnerabilities
- **Performance**: Build time <5 minutes
- **Documentation**: All phases documented

## Integration with CI/CD

This workflow integrates with standard CI/CD pipelines:

1. **Pre-commit**: Orchestrator validates requirements
2. **Development**: Agents implement feature in feature branch
3. **Testing**: Automated test suite runs
4. **Security**: Security scans in CI pipeline
5. **Staging**: Deployment Engineer deploys to staging
6. **Production**: Manual approval → production deployment

## Related Workflows

- **Code Review Pipeline**: Run after feature completion for peer review
- **Testing QA Orchestration**: Deep testing before production
- **Security Hardening**: Comprehensive security assessment
- **Bug Fix Debugging**: If issues found post-deployment

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
