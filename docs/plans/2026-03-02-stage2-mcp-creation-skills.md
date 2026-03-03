# Stage 2: MCP Server/Tool Creation Skills — Implementation Plan (DRAFT)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> **Status: DRAFT** — Task outlines only. Full TDD steps, code, and exact file references to be added before implementation begins. Implementation requires dedicated research phase on MCP SDK patterns.

**Goal:** Add MCP tool and MCP server creation capabilities to the context-engineering plugin, backed by research on MCP SDK best practices and with emphasis on testing strategies.

**Architecture:** Two new skills (`mcp-tool-creation`, `mcp-server-creation`) with templates for Python and TypeScript MCP servers. Context-engineer agent prompt updated to handle MCP resource generation. Resource-type-guide.md updated with MCP decision matrix.

**Tech Stack:** Python MCP SDK, TypeScript `@modelcontextprotocol/sdk`, uvx/npx packaging

**Depends on:** Stage 1 (resource type registry, SPEC parser MCP support)

**Design doc:** `docs/plans/2026-03-02-cgf-eval-framework-design.md` (Section: Component 2)

---

## Pre-Implementation: MCP Research Phase

Before writing the skills, conduct dedicated research using the research-team plugin:

**Research topics:**
1. MCP Python SDK (`mcp` package) — server creation patterns, tool registration, resource/prompt handling, testing approaches
2. MCP TypeScript SDK (`@modelcontextprotocol/sdk`) — same coverage
3. Real-world MCP server examples — study 3-5 well-built servers from the MCP ecosystem (e.g., conventions-mcp, filesystem server, GitHub server)
4. MCP tool definition best practices — Anthropic's guidance on descriptions, parameters, response design
5. Testing strategies — how to unit test MCP handlers, integration test with MCP client, e2e test with an agent
6. Packaging for distribution — uvx (Python) and npx (TypeScript) deployment patterns

**Output:** Research findings saved to workspace, synthesized into skill content.

---

## Task 1: Research MCP SDK Patterns

**Files:**
- Output: `workspace/mcp-research/research/notes/` (research findings)

**Steps:**
1. Run `/research "MCP Python SDK server creation patterns, testing, and packaging for uvx"` via research-team
2. Run `/research "MCP TypeScript SDK patterns and npx distribution"` via research-team
3. Study `src/mcp_servers/` in this repo for existing patterns (context7, docker, memory servers)
4. Study conventions-mcp (`~/Projects/ab-github/conventions-mcp/`) as a production MCP server example
5. Synthesize findings into skill content requirements

---

## Task 2: Create `mcp-tool-creation` Skill

**Files:**
- Create: `src/harness/plugins/context-engineering/skills/mcp-tool-creation/SKILL.md`
- Create: `src/harness/plugins/context-engineering/templates/mcp-tool-template.py`

**Content areas (informed by research):**
- Tool function design patterns (input/output contracts)
- Anthropic's tool description best practices (3-4 sentences, parameter semantics, when to use/not use)
- Input validation and schema definition
- Return value design (high-signal, minimal, human-readable)
- Error handling (specific corrective messages)
- Testing patterns:
  - Unit tests for tool functions
  - Integration tests with CLI interface
  - Schema validation tests
- Template: single-file Python script with argparse CLI + importable function + test file

---

## Task 3: Create `mcp-server-creation` Skill

**Files:**
- Create: `src/harness/plugins/context-engineering/skills/mcp-server-creation/SKILL.md`
- Create: `src/harness/plugins/context-engineering/templates/mcp-server-python-template/` (scaffold)
- Create: `src/harness/plugins/context-engineering/templates/mcp-server-typescript-template/` (scaffold)

**Content areas (informed by research):**
- MCP protocol fundamentals (tools, resources, prompts)
- Server scaffolding for Python (`mcp` SDK) and TypeScript (`@modelcontextprotocol/sdk`)
- Tool definition best practices (from Anthropic articles):
  - Detailed descriptions
  - Consolidate related operations
  - Meaningful namespacing
  - Response design (concise/detailed modes)
  - Input examples for complex tools
- Discovery-first architecture (defer loading for 10+ tools)
- Packaging:
  - Python: `pyproject.toml` with `[project.scripts]` for uvx
  - TypeScript: `package.json` with `bin` for npx
- Configuration patterns (env vars, config files)
- Error handling
- **Testing strategy (emphasized):**
  - Unit tests for each tool handler
  - Integration tests with MCP client library
  - E2E tests with an agent session
  - Schema validation for tool definitions
  - Performance tests (response time, token usage)

**Template structures:**

Python template:
```
mcp-server-python-template/
├── pyproject.toml          # uvx-compatible with [project.scripts]
├── src/
│   └── {server_name}/
│       ├── __init__.py
│       ├── server.py       # MCP server setup + tool registration
│       └── tools/          # Individual tool handlers
├── tests/
│   ├── test_tools.py       # Unit tests per tool
│   ├── test_integration.py # MCP client integration
│   └── conftest.py         # Fixtures
└── README.md
```

TypeScript template:
```
mcp-server-typescript-template/
├── package.json            # npx-compatible with bin entry
├── tsconfig.json
├── src/
│   ├── index.ts            # Server entry point
│   ├── server.ts           # MCP server setup
│   └── tools/              # Individual tool handlers
├── tests/
│   └── tools.test.ts
└── README.md
```

---

## Task 4: Update Resource-Type-Guide

**Files:**
- Modify: `src/harness/plugins/context-engineering/templates/resource-type-guide.md`

**Additions:**
- MCP Tool section: when to use, design principles, testing requirements
- MCP Server section: when to use, architecture patterns, scaling considerations
- Decision matrix entries:
  - External data/API → MCP server
  - Single utility function → MCP tool
  - Multiple related operations → MCP server (consolidated)
  - 10+ tools in domain → MCP server with discovery-first
- MCP vs Agent comparison (when to put logic in tool vs agent prompt)

---

## Task 5: Update Context-Engineer Agent Prompt

**Files:**
- Modify: `src/harness/plugins/context-engineering/agents/context-engineer.md`

**Changes:**
- Add MCP tool generation capability (reference mcp-tool-creation skill)
- Add MCP server generation capability (reference mcp-server-creation skill)
- Add `[GENERATE_COMPLETE:{path}]` signal emission for MCP resources
- Update multi-resource detection to handle MCP resource types

---

## Task 6: Validation Tests

**Files:**
- Create: `tests/unit/test_optimization/test_mcp_resource_generation.py`

**Tests:**
- Verify resource-type-guide includes MCP entries
- Verify context-engineer can be invoked with MCP resource type
- Verify SPEC parser → resource-plan → generation flow works for MCP types
- Verify templates are syntactically valid (Python template passes ruff, TypeScript template passes tsc)

---

## Task 7: Documentation

**Files:**
- Modify: `CLAUDE.md` — Update skill counts, add MCP resource type docs
- Modify: `src/harness/plugins/context-engineering/README.md` — Add MCP skills
