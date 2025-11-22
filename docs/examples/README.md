# Claude Agent SDK - Quick Start Examples

This directory contains simple, standalone examples to help you get started with the Claude Agent SDK **without requiring Docker or the full harness infrastructure**.

## Overview

These examples are perfect for:
- 🎓 **Learning** the Claude Agent SDK basics
- 🧪 **Testing** quick ideas without overhead
- 📖 **Understanding** core SDK patterns before using the full harness
- 💰 **Cost-effective** experimentation with cheaper models

## Prerequisites

```bash
# 1. Navigate to the repository root
cd ~/Projects/claudeagentsdk-harness

# 2. Set up virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
uv pip install -e .

# 4. Set your API key in .env
echo "ANTHROPIC_API_KEY=sk-ant-your_key_here" >> .env
```

## Available Examples

### 1. `simple_query.py` - Basic Query Patterns

**Learn**: How to use `query()` vs `ClaudeSDKClient`

**Run**:
```bash
python examples/simple_query.py                 # Uses haiku (cheapest)
python examples/simple_query.py --model sonnet  # More capable
python examples/simple_query.py --model opus    # Most capable
```

**Cost**: ~$0.001-0.01 per run

**What you'll see**:
- Example 1: Stateless `query()` - Creates new session each time
- Example 2: Stateful `ClaudeSDKClient` - Maintains conversation context

**When to use**:
- `query()`: One-off questions, independent tasks
- `ClaudeSDKClient`: Multi-turn conversations, context needed

---

### 2. `interactive_basic.py` - Simple Chat Loop

**Learn**: Building an interactive conversation interface

**Run**:
```bash
python examples/interactive_basic.py                 # Uses haiku
python examples/interactive_basic.py --model sonnet  # Better responses
python examples/interactive_basic.py --stats         # Show session stats
```

**Cost**: ~$0.01-0.10 per session (varies by length)

**Features**:
- ✅ Continuous conversation loop
- ✅ Rich formatted output with colored panels
- ✅ Syntax highlighting for JSON/code
- ✅ Graceful exit with `exit` or `quit`
- ✅ Optional session statistics

**Exit**: Type `exit` or `quit` to end the session

---

## Model Selection Guide

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| **haiku** | ⚡️ Fastest | 💰 Cheapest | Testing, simple tasks |
| **sonnet** | ⚡️ Fast | 💰💰 Moderate | General use, balanced |
| **opus** | 🐌 Slower | 💰💰💰 Expensive | Complex reasoning, accuracy |

**Tip**: Start with `haiku` for testing, use `sonnet` for real work.

## Quick Start vs Full Harness

| Feature | Quick Start Examples | Full Harness (`make interactive`) |
|---------|---------------------|-----------------------------------|
| Setup Time | < 1 minute | ~5-10 minutes |
| Docker Required | ❌ No | ✅ Yes |
| Checkpointing | ❌ No | ✅ Auto-save every hour |
| Metrics/Monitoring | ❌ No | ✅ Prometheus + Grafana dashboards |
| MCP Servers | ❌ Basic only | ⚠️ Infrastructure exists (currently disabled) |
| Multi-Agent Orchestration | ❌ No | ✅ Yes (Phase 2 - planned) |
| Production Ready | ❌ No | ✅ Yes |
| Best For | Learning, quick tests | Production, long sessions (20+ hours) |

## Next Steps

Once you're comfortable with these examples:

1. **Explore the full harness**: See [CLAUDE.md](../CLAUDE.md#phase-1-interactive-agent-setup)
2. **Add MCP servers**: Extend Claude with custom tools
3. **Multi-agent workflows**: Coordinate multiple specialized agents
4. **Production deployment**: Use Docker, monitoring, checkpoints

## Workflow Examples (Coming Soon)

More complex examples for production workflows:

- `simple-feature/` - Single feature implementation
- `bug-fix/` - Debug and fix workflow
- `refactoring/` - Code improvement workflow
- `full-project/` - Complete project from spec

See [CLAUDE.md](../CLAUDE.md#24-workflow-templates) for Phase 2 roadmap.

## Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'claude_agent_sdk'`
```bash
# Make sure you installed dependencies
uv pip install -e .
```

**Issue**: `ANTHROPIC_API_KEY not found`
```bash
# Check your .env file
cat .env | grep ANTHROPIC_API_KEY

# Or set it manually
export ANTHROPIC_API_KEY=sk-ant-your_key_here
```

**Issue**: `ImportError: harness.cli not found`
```bash
# This is expected if running outside the harness context
# The examples will fall back to basic output
# To use harness CLI, run: uv pip install -e .
```

**Issue**: Rate limit errors
```bash
# Use a cheaper model or add delays between requests
python examples/simple_query.py --model haiku
```

## Cost Estimation

Using **haiku** (cheapest model):
- Input: $0.00025 per 1K tokens
- Output: $0.00125 per 1K tokens

Example costs:
- Simple query: ~500 input + 100 output = ~$0.0003
- 10-turn conversation: ~5K input + 1K output = ~$0.003
- 1-hour session: ~50K input + 10K output = ~$0.025

Using **sonnet** (default for production):
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens

**Tip**: Always start with `haiku` for testing to minimize costs!

## Support

- 📚 [Claude Agent SDK Docs](https://docs.claude.com/en/api/agent-sdk/python)
- 📚 [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)
- 🐛 [Report Issues](https://github.com/anthropics/claude-code/issues)

---

**Happy Coding!** 🚀
