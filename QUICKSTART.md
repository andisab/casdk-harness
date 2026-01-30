# Quick Start Guide (5 Minutes)

Get chatting with Claude in 5 minutes or less.

## Prerequisites

- **Docker Desktop** (or [OrbStack](https://orbstack.dev) on Mac - faster)
- **Anthropic API Key** from [console.anthropic.com](https://console.anthropic.com)

Verify Docker is running:
```bash
docker info
```

## Setup

```bash
# 1. Clone and enter the repository
git clone https://www.github.com/andisab/ab-casdk-harness.git
cd casdk-harness

# 2. Initialize the project
make init

# 3. Add your API key to .env
# Open .env and set: ANTHROPIC_API_KEY=sk-ant-your_key_here

# 4. Build and start services
make build
make up

# 5. Start chatting!
make interactive
```

## Model Selection

```bash
make interactive              # Default (sonnet)
make interactive MODEL=haiku  # Faster, cheaper
make interactive MODEL=opus   # Most capable
```

## Two Modes Available

| Mode | Command | Use Case |
|------|---------|----------|
| **Interactive** | `make interactive` | Direct conversation, exploration, quick tasks |
| **Autonomous** | `make autonomous` | Automated development from a SPEC.md file |

## Try These Prompts

Once in interactive mode, try:

- `"List files in /workspace"`
- `"Create a hello world script in Python"`
- `"What MCP servers are available?"`
- `"Help me write a function to validate email addresses"`

Type `exit` or `quit` to end your session.

## Common Issues

| Problem | Solution |
|---------|----------|
| Container won't start | Run `docker info` - is Docker running? |
| "API key invalid" | Check `.env` - key should start with `sk-ant-` |
| "Port already in use" | Run `make down` first, or check `lsof -i :8080` |
| Build failures | Run `make build-no-cache` |

Run `make doctor` to diagnose setup issues.

## Essential Commands

```bash
make interactive      # Chat with the agent
make autonomous       # Run automated development
make optimize         # Optimize agent prompts (discovers SPEC.md)
make logs            # View logs
make shell           # Shell into container
make down            # Stop everything
make doctor          # Diagnose setup issues
```

## Next Steps

- **Full documentation**: [README.md](./README.md)
- **Troubleshooting**: [README.md#troubleshooting](./README.md#troubleshooting)
- **Autonomous mode**: Run `make init-spec` to create a SPEC.md template
- **Prompt optimization**: `make cgf-init NAME=my-agent` then `make optimize` (auto-discovers SPEC.md)
- **Multi-resource optimization**: Create SPEC.md in `workspace/my-plugin/` then `make optimize`
- **Technical details**: [CLAUDE.md](./CLAUDE.md)
