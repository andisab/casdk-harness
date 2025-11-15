# Claude Agent SDK Harness - Runtime Context

## Working Environment

You are running within the Claude Agent SDK Harness, a production-ready framework for autonomous software development.

### Directory Structure
- **Workspace**: `/workspace` - Your primary working directory for code and projects
- **Memory**: `/memory` - Persistent state storage (checkpoints, context)
- **Logs**: `/logs` - Structured application and action logs
- **Config**: `/config` - System configuration files

### Available MCP Servers
The following MCP servers are registered and available for use:
- **git**: Git operations and version control
- **docker**: Container management and orchestration
- **memory**: Knowledge graph for persistent memory
- **context7**: Library documentation lookup
- **joplin**: Note-taking and documentation
- **github**: GitHub API operations
- **playwright**: Browser automation and testing

### Monitoring & Observability
- Prometheus metrics are collected on port 9090
- Grafana dashboards available for session monitoring
- Action logging via hooks for audit trails
- Token usage and cost tracking enabled

## Guidelines for Agents

### Checkpointing
- Checkpoints are automatically saved every hour
- Recovery from latest checkpoint on restart
- Use memory MCP server for important context persistence

### Task Management
- Use TodoWrite tool for task planning and tracking
- Mark tasks as in_progress when starting
- Mark as completed immediately when done
- Break complex tasks into smaller steps

### Agent Delegation
- 44 specialized agents are available in `.claude/agents/`
- SDK will auto-discover and delegate to appropriate agents
- Each agent has specific tools and expertise areas
- Agents are organized by prefix: `dev-*`, `db-*`, `infra-*`, `ml-*`, `web-*`

### Best Practices
1. Check memory for existing project context before starting
2. Log important decisions and findings to memory
3. Use appropriate specialized agents for domain-specific tasks
4. Provide progress updates for long-running operations
5. Follow the coding standards in `.claude/specs/`
6. Test code changes before committing
7. Use structured logging for better observability

### Security & Permissions
- Permission mode can be `manual`, `acceptAll`, or `acceptNone`
- Workspace access is read-write by default
- Some agents may have read-only access (e.g., reviewer agents)
- Never expose secrets in logs or commits

## Session Context

This harness supports two primary modes:
1. **Interactive Mode**: Direct conversation with immediate feedback
2. **Service Mode**: Long-running autonomous development sessions

The SDK will automatically discover and load:
- This CLAUDE.md file for runtime context
- All agent definitions from `.claude/agents/`
- Skills from `.claude/skills/`
- Coding standards from `.claude/specs/`

Remember: You have access to the full agent library. The SDK will handle progressive disclosure and context management automatically.