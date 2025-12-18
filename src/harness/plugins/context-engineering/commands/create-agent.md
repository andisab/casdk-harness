---
description: Create a new agent definition file
allowed-tools: Read, Write, Edit, Glob
argument-hint: <agent-name>
---

Create a new agent definition file for an agent named "$1".

Follow these steps:
1. Create the file at `agents/$1.md` with proper YAML frontmatter
2. Include name, description, model, and tools fields
3. Write a comprehensive system prompt for the agent's role

The agent should follow best practices for Claude Code agent definitions.
