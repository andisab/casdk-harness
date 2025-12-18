>[toc]
# Universal Code Standards

## Quick Reference
| Principle | Key Practice |
|-----------|-------------|
| **Clarity** | Descriptive names, explicit logic, meaningful comments |
| **Security** | Input validation, parameterized queries, least privilege |
| **Performance** | Measure first, optimize common cases, appropriate data structures |
| **Testing** | TDD cycle, 80%+ coverage, isolated tests |
| **Quality** | Peer reviews, automated checks, consistent patterns |

## Core Principles
### KISS, DRY, SOLID, and YAGNI
- **Keep It Simple** - Choose clarity over cleverness. 
- **Don't Repeat Yourself** - Extract & consolidate common patterns. 
- **SOLID Principles** - Single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion. 
- **You Ain't Gonna Need It** - Don't over-engineer and reduce cognitive load wherever possible.

## Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| **Variables** | camelCase or snake_case, depending on established convention, descriptive | `userEmail`, `is_active` |
| **Functions** | Verb + description | `calculateTax()`, `getUserById()` |
| **Classes** | PascalCase nouns | `UserRepository`, `EmailService` |
| **Files** | Project convention | `user-service.ts`, `UserService.java` |
| **Booleans** | Question form | `hasPermission`, `canEdit` |
| **Constants** | UPPER_SNAKE_CASE | `MAX_RETRIES`, `API_KEY` |

### Guiding Ideas
- Follow consistent code structure and established patterns within the project
- Consider performance implications of code choices and optimize for robust, stable functionality
- Minimize volume of code to ease maintenance for the developer
- Avoid premature optimization, but don't ignore obvious inefficiencies
- Use appropriate data structures for the task

## Code Organization
### Architecture Patterns
- **Separation of Concerns**: Business logic, data access, presentation layers
- **Dependency Injection**: Inject dependencies, don't create them
- **Single Responsibility**: Each module/class/function does one thing well
- **Interface-Based Design**: Program to interfaces, not implementations

## Development Workflow
### Git Workflow
```bash
# Feature branch workflow
git checkout -b feature/descriptive-name
# Make changes with TDD approach
git commit -m "type(scope): description"
git push origin feature/descriptive-name
# Create PR with detailed description
```

### Code Review Checklist
- [ ] Temporary files, logs, and other unnecessary code removed
- [ ] Tests pass and coverage adequate
- [ ] Security vulnerabilities addressed
- [ ] Performance impact considered
- [ ] Documentation updated
- [ ] Follows project conventions
- [ ] Error handling implemented

## Testing Standards
### Test-Driven Development
- **Red**: Write failing test first
- **Green**: Implement minimal code to pass
- **Refactor**: Improve code while keeping tests green
- Consolidate tests to a dedicated tests directory
- Tests should be clear, maintainable, reliable, and as efficient/quick as possible to run
- Maintain tests for critical paths IN PARALLEL TO IMPLEMENTATION
- All code should have 80%+ test coverage before we commit
- For TDD, use the Red-Green-Refactor cycle: Write failing test → Make it pass → Refactor

### Test Types & Coverage

| Type | Purpose | Coverage Target |
|------|---------|----------------|
| **Unit** | Individual functions | 80%+ |
| **Integration** | Component interactions | Critical paths |
| **E2E** | User workflows | Key user journeys |
| **Contract** | API contracts | All public APIs |

### Test Structure
```javascript
describe('Component', () => {
  it('should perform specific behavior', () => {
    // Arrange
    const input = setupTestData();
    
    // Act
    const result = functionUnderTest(input);
    
    // Assert
    expect(result).toBe(expected);
  });
});
```

## Error Handling & Logging
### Logging Levels

| Level | Use Case | Example |
|-------|----------|---------|
| **ERROR** | System failures | Database connection lost |
| **WARN** | Recoverable issues | Rate limit approaching |
| **INFO** | Key events | User login, order placed |
| **DEBUG** | Development details | Variable values, flow trace |

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email address is invalid",
    "field": "email",
    "requestId": "uuid-here"
  }
}
```

### Structured Logging
```javascript
logger.info('User action performed', {
  userId: user.id,
  action: 'UPDATE_PROFILE',
  requestId: req.id,
  duration: 145
});
```

## Security 
### Security Guidelines
- Centralize all environment-based config and secrets to a gitignored env file located at project root.
- Never store secrets in code or version control.
- Follow principle of least privilege for permissions
- Encrypt sensitive data at rest and in transit
- Validate all inputs at boundaries using whitelist approach
- Use parameterized queries and prepared statements
- Never expose sensitive data in logs, errors, or commits
- Prefer HTTPS for all communications

### Input Validation
```javascript
// Whitelist approach
const validEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
if (!validEmail.test(email)) {
  throw new ValidationError('Invalid email format');
}
```

### Authentication & Authorization
- Use established libraries (Passport, Auth0, etc.)
- Use API keys/tokens for authentication with appropriate expiration (e.g. 30min access, 7d refresh)
- Rate limiting: 100 requests/minute per IP
- CORS: Explicit allowed origins only

### Secrets Management
```bash
# .env.example (committed)
DATABASE_URL=postgresql://user:pass@host:5432/db
API_KEY=your_api_key_here

# .env (never committed)
DATABASE_URL=postgresql://prod:secret@prod:5432/mydb
API_KEY=sk_live_actual_key
```

## Performance Standards
### Database Optimization
- Index foreign keys and commonly queried fields
- Use `EXPLAIN ANALYZE` for query optimization
- Implement connection pooling (min: 2, max: 10)
- Batch operations when processing multiple records

### API Performance
- Pagination: Default 50, max 100 items
- Response caching: GET requests with ETags
- Compression: gzip for responses > 1KB
- Timeout: 30s default, 5min for long operations

### Frontend Optimization
- Bundle splitting by route
- Lazy load below-the-fold content
- Image optimization: WebP with fallbacks
- Cache headers: 1 year for assets, 5 min for API

## Configuration Management
### Environment Configuration
```javascript
// config/index.js
module.exports = {
  port: process.env.PORT || 3000,
  database: {
    url: process.env.DATABASE_URL,
    pool: {
      min: parseInt(process.env.DB_POOL_MIN || '2'),
      max: parseInt(process.env.DB_POOL_MAX || '10')
    }
  },
  features: {
    newDashboard: process.env.FEATURE_NEW_DASHBOARD === 'true'
  }
};
```

### Feature Flags
```javascript
if (features.isEnabled('newCheckout')) {
  return renderNewCheckout();
}
return renderLegacyCheckout();
```

## Build & Deployment
### CI/CD Pipeline
```yaml
# .github/workflows/ci.yml
steps:
  - lint        # Code style checks
  - test        # Unit & integration tests
  - security    # Vulnerability scanning
  - build       # Create artifacts
  - deploy      # Environment-specific
```

### Deployment Checklist
- [ ] All tests passing
- [ ] Security scan complete
- [ ] Database migrations ready
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] Feature flags set appropriately

## Monitoring & Observability
### Key Metrics
- **Response Time**: p50 < 200ms, p99 < 1s
- **Error Rate**: < 1% of requests
- **Availability**: 99.9% uptime target
- **Business Metrics**: Specific to application

### Distributed Tracing
```javascript
// Correlation ID for request tracking
app.use((req, res, next) => {
  req.id = req.headers['x-request-id'] || uuid();
  res.setHeader('x-request-id', req.id);
  next();
});
```

## Dependency Management
### Update Schedule
- **Security patches**: Immediately
- **Minor updates**: Monthly
- **Major updates**: Quarterly with testing

### Dependency Documentation
```json
{
  "dependencies": {
    "express": "^4.18.0",  // Web framework
    "pg": "^8.11.0",       // PostgreSQL client
    "winston": "^3.8.0"    // Logging library
  }
}
```

## Code Review Process
### Review Focus Areas
1. **Logic correctness** - Does it solve the problem?
2. **Edge cases** - Are errors handled?
3. **Performance** - Any obvious bottlenecks?
4. **Security** - Input validation present?
5. **Maintainability** - Will others understand?

### Review SLA
- **Critical fixes**: 2 hours
- **Features**: 24 hours
- **Refactoring**: 48 hours

## Quick Commands
```bash
# Development
npm run dev           # Start development server
npm test             # Run tests
npm run lint         # Check code style
npm run typecheck    # TypeScript validation

# Debugging
npm run test:debug   # Test with debugger
npm run analyze      # Bundle analysis

# Deployment
npm run build        # Production build
npm run migrate      # Database migrations
npm run deploy       # Deploy to environment
```
---
_Last updated: August 2025 | Review quarterly_