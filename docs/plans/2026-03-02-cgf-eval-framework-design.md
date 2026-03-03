# CGF Evaluation Framework & Plugin Integration Design

**Date:** 2026-03-02
**Branch:** contextgrad-framework
**Status:** Approved design, pending implementation

---

## Overview

This design addresses two interlocking objectives for the ContextGrad Framework:

1. **Plugin Integration Improvement** — Formalize how the three plugins (research-team, context-engineering, cgf-agents) coordinate, add MCP server/tool creation to context-engineering, and insert a resource architecture decision step between research and generation.

2. **Evaluation Framework** — Build a hybrid evaluation system combining LLM-judge assessment (fast, cheap) with sandboxed execution-based evaluation (definitive) to measure whether generated resources actually work.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target environment | This harness (Docker) | Long-running generate-evaluate-optimize cycles need Docker isolation |
| Evaluation dimensions | Task completion + output quality + behavioral correctness | All three, dynamically designed per use case |
| MCP creation scope | Tool scripts + full MCP servers (uvx/npx) | Context-engineering becomes a full resource factory |
| Plugin architecture | Keep separate + shared protocol layer | cgf-agents orchestrates, others own their domains |
| Evaluation execution | Hybrid: LLM-judge + sandboxed agent sessions | Fast feedback during iteration, real validation before finalization |
| Resource architecture ownership | New dedicated agent (cgf-resource-architect) | Clean separation: architect designs, context-engineer executes |

### Reference Material

Design informed by five Anthropic engineering articles:
- [Implement Tool Use: Best Practices](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use#best-practices-for-tool-definitions)
- [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

---

## Revised Pipeline Architecture

The core changes: insert a DESIGN phase between RESEARCH and GENERATE, add EVAL-DESIGN and EXECUTION-EVAL phases after the LLM-judge iteration loop.

```
SPEC.md (business objective + capabilities + constraints)
    |
    v
+------------------------------------------------------------------+
|  PHASE 1: RESEARCH                                               |
|  Owner: cgf-research-lead -> research-team:research-specialists  |
|  Input: SPEC capabilities, constraints, research_topics          |
|  Output: research/notes/*_findings.yaml, eval_criteria.yaml      |
|  Signal: [RESEARCH_COMPLETE]                                     |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 2: DESIGN  <- NEW                                         |
|  Owner: cgf-resource-architect (new agent in cgf-agents)         |
|  Input: SPEC + research findings + resource-type-guide           |
|  Output: resource-plan.yaml (what to build, why, dependencies)   |
|  Signal: [DESIGN_COMPLETE]                                       |
|  Human checkpoint: Optional review of proposed architecture      |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 3: GENERATE                                               |
|  Owner: context-engineering:context-engineer                     |
|  Input: resource-plan.yaml + research findings                   |
|  Output: Generated resource files (agents, skills, MCP, etc.)    |
|  Signal: [GENERATE_COMPLETE:{path}] per resource                 |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 4: EVAL-DESIGN  <- NEW                                    |
|  Owner: cgf-eval-architect (new agent in cgf-agents)             |
|  Input: Generated resources + SPEC + research findings           |
|  Output: eval-suite.yaml (unit, trajectory, e2e eval scenarios)  |
|  Signal: [EVAL_DESIGN_COMPLETE]                                  |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 5: FAST-ITERATE (existing, enhanced)                      |
|  Owner: cgf-prompt-optimizer                                     |
|  Input: Resources + eval_criteria + research                     |
|  Output: Versioned resources ({resource}-v{N}.md)                |
|  Evaluation: LLM-judge (CAIR framework) -- fast, cheap           |
|  Signal: [ITERATE_COMPLETE:{path}] + quality scores              |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 6: EXECUTION-EVAL  <- NEW                                 |
|  Owner: Python eval harness (not an agent -- deterministic)      |
|  Input: Optimized resources + eval-suite.yaml                    |
|  Output: eval-results.json (pass/fail per scenario, transcripts) |
|  Method: Sandboxed agent sessions via direct_agent               |
|  Metrics: pass@k, pass^k, tool accuracy, constraint compliance   |
|  Signal: [EVAL_COMPLETE] + aggregate scores                      |
+------------------------------------------------------------------+
    |
    +--- If scores < threshold -> loop back to FAST-ITERATE with
    |    execution feedback (concrete failures, not LLM opinions)
    v
+------------------------------------------------------------------+
|  PHASE 7: VALIDATE (existing, enhanced)                          |
|  Owner: cgf-coherence-validator                                  |
|  Input: All finalized resources                                  |
|  Output: Coherence report + [VALIDATE_COMPLETE]                  |
|  Enhanced: Also validates MCP tool schemas, dependency graph     |
+------------------------------------------------------------------+
    |
    v
  FINALIZE -> Versioned, tested resources
```

### Key Changes from Current Pipeline

1. **Structure is no longer locked at PLANNING** -- determined by resource-architect after research
2. **Eval suite is dynamically generated** per resource set (not static rubrics)
3. **Execution-based evaluation** runs real agent sessions, not just LLM opinions
4. **Failure feedback from execution** flows back to optimizer with concrete data

---

## Component 1: Resource Architect Agent

**Location:** `src/harness/plugins/cgf-agents/agents/cgf-resource-architect.md`
**Model:** Opus (highest-stakes reasoning task in the pipeline)

### Role

Analyzes SPEC capabilities + research findings + resource-type-guide decision matrix to produce a `resource-plan.yaml` defining what resources to build, why, and how they relate.

### Why This Is Needed

Today's pipeline has a critical gap: the SPEC's `## Proposed Structure` is locked in during PLANNING before any research happens. Research findings never influence structure decisions. The Q&A phase that should validate structure is explicitly a placeholder (`"For now, auto-accept proposed structure"`). The resource-type-guide.md contains a comprehensive decision matrix, but no code or agent actually uses it.

### Decision Logic

1. For each SPEC capability, determine optimal resource type (agent, skill, command, hook, MCP tool, MCP server, or combination)
2. Apply resource-type-guide decision matrix
3. Identify dependencies between resources (e.g., agent X needs MCP tool Y)
4. If SPEC includes a `## Proposed Structure`, validate against research -- accept, modify, or override with justification
5. Produce dependency-ordered plan

### Output Schema: `resource-plan.yaml`

```yaml
plan_version: 1
spec_hash: <sha256 of SPEC.md>
rationale: "Brief explanation of overall architecture choice"

resources:
  - path: agents/iac-analyzer.md
    type: agent
    purpose: "Analyze IaC templates for compliance violations"
    capabilities_served: [cap_1, cap_3]
    depends_on: [tools/terraform-parser]
    model: sonnet
    tools: [Read, Write, Bash, mcp__terraform_parser]
    priority: 1

  - path: tools/terraform-parser.py
    type: mcp_tool
    purpose: "Parse and validate Terraform HCL files"
    capabilities_served: [cap_1]
    depends_on: []
    language: python
    priority: 0

  - path: skills/compliance-rules/SKILL.md
    type: skill
    purpose: "Compliance rule knowledge base"
    capabilities_served: [cap_2, cap_4]
    depends_on: []
    triggers: ["compliance", "regulation", "policy"]
    priority: 0

generation_order:
  - tools/terraform-parser.py
  - skills/compliance-rules/SKILL.md
  - agents/iac-analyzer.md

rejected_proposals: []
```

### Design Principles

- Architect can override user proposals but must justify why
- `generation_order` respects dependencies (tools before agents that use them)
- Each resource traces to specific SPEC capabilities (`capabilities_served`)
- Plan is a checkpoint -- optional human review before proceeding

---

## Component 2: MCP Server/Tool Creation in Context-Engineering

Two new skills and corresponding templates to handle the spectrum from lightweight scripts to production MCP servers.

### Skill 1: `mcp-tool-creation`

**Location:** `src/harness/plugins/context-engineering/skills/mcp-tool-creation/SKILL.md`

**Scope:** Lightweight Python tool scripts -- standalone `.py` files that perform a specific function (parsing, validation, transformation, API calls).

**Covers:**
- Tool function design (clear input/output contracts, error handling)
- Anthropic's tool description best practices (3-4 sentence descriptions, parameter semantics, when to use / not use)
- Input validation and schema definition
- Return value design (high-signal, minimal, human-readable identifiers)
- Testing patterns for tool scripts

### Skill 2: `mcp-server-creation`

**Location:** `src/harness/plugins/context-engineering/skills/mcp-server-creation/SKILL.md`

**Scope:** Full MCP server implementations deployable via `uvx` (Python) or `npx` (TypeScript).

**Covers:**
- MCP protocol fundamentals (tools, resources, prompts)
- Server scaffolding (Python `mcp` SDK or TypeScript `@modelcontextprotocol/sdk`)
- Tool definition best practices from Anthropic's guidance:
  - Detailed descriptions (explain what, when, why, limitations)
  - Consolidate related operations (fewer tools > many narrow ones)
  - Meaningful namespacing (`service_resource_action`)
  - Response design (high-signal, concise/detailed modes)
  - Input examples for complex tools
- Discovery-first architecture (defer loading for 10+ tools)
- Packaging for distribution (pyproject.toml for uvx, package.json for npx)
- Configuration patterns (env vars, config files)
- Error handling (specific corrective messages, not opaque codes)
- **Testing strategy (emphasized):** Unit tests for handlers, integration tests with MCP client, end-to-end with agent sessions

**Implementation requirement:** Dedicated research phase on MCP SDK patterns, testing strategies, and real-world server examples before writing the skills. Skills must emphasize testing at every level.

### New Templates

| Template | Purpose |
|----------|---------|
| `mcp-tool-template.py` | Single-file Python tool with CLI + function interface |
| `mcp-server-python-template/` | Python MCP server scaffold (pyproject.toml, src/, tests/) |
| `mcp-server-typescript-template/` | TypeScript MCP server scaffold (package.json, src/, tests/) |

### Resource-Type-Guide Additions

| Signal | Resource Type |
|--------|--------------|
| Needs external data integration or API access | MCP server |
| Needs to expose a single utility function | MCP tool (Python script) |
| Needs to serve multiple related operations | MCP server (consolidated tools) |
| 10+ tools in same domain | MCP server with discovery-first architecture |

### Integration Impact

- Resource-architect sees MCP types in decision matrix, can propose `type: mcp_tool` or `type: mcp_server`
- `multi_resource_spec.py` extended to parse MCP resources in SPEC proposed structures
- Context-engineer prompt updated to handle MCP resource generation using new skills

---

## Component 3: Evaluation Framework

Three subcomponents: eval-architect agent, eval harness (Python), and feedback loop.

### Subcomponent 3a: `cgf-eval-architect` Agent

**Location:** `src/harness/plugins/cgf-agents/agents/cgf-eval-architect.md`
**Model:** Sonnet

**Role:** Analyzes generated resources + SPEC + research findings to produce `eval-suite.yaml` with executable test scenarios at three levels.

**Key insight:** Eval design is task-specific. A coding agent needs unit test graders; a research agent needs groundedness checks; a tool-using agent needs trajectory analysis. The eval-architect reasons about what kind of resource it's evaluating and selects appropriate strategies.

**Inputs:**
- Generated resources (actual files)
- SPEC.md (defines what "success" means)
- Research findings (informs realistic scenarios)
- Resource plan (knows resource types and dependencies)

**Output:** `eval-suite.yaml`

```yaml
eval_version: 1
resource_plan_hash: <sha256>
config:
  trials_per_scenario: 3
  timeout_seconds: 300
  eval_model: sonnet

scenarios:
  # UNIT EVALS (single-turn, fast, cheap)
  - id: unit_001
    level: unit
    target_resource: agents/iac-analyzer.md
    description: "Agent correctly identifies missing required tags"
    prompt: "Analyze this Terraform file: {inline_content}"
    graders:
      - type: contains
        expected: "missing required tag"
      - type: code
        script: "assert 'Name' in output.get('missing_tags', [])"
    tags: [cap_1, basic]

  # TRAJECTORY EVALS (multi-step, tool usage)
  - id: traj_001
    level: trajectory
    target_resource: agents/iac-analyzer.md
    description: "Agent uses terraform-parser tool before making claims"
    setup:
      files:
        - path: test_input/main.tf
          content: |
            resource "aws_instance" "example" { ... }
    prompt: "Analyze the Terraform files in test_input/ for compliance"
    graders:
      - type: trajectory
        assertions:
          - tool_called: mcp__terraform_parser
            before: first_text_output
          - no_tool: Write
          - constraint: "Agent must not hallucinate resources not in the file"
    tags: [cap_1, behavioral]

  # END-TO-END EVALS (full task, outcome verification)
  - id: e2e_001
    level: e2e
    target_resource: agents/iac-analyzer.md
    description: "Full compliance analysis produces actionable report"
    setup:
      files:
        - path: test_input/main.tf
          content: |
            # Terraform with 3 known violations
      expected_outcomes:
        violations_found: 3
    prompt: "Run a full compliance analysis on test_input/"
    graders:
      - type: llm_judge
        rubric: |
          Score 1-5 on: completeness (all 3 violations found),
          actionability (each violation has remediation steps),
          accuracy (no false positives)
        pass_threshold: 4
      - type: code
        script: |
          import os
          assert os.path.exists('compliance_report.md')
    tags: [cap_1, cap_2, e2e]
```

**Balanced test design (per Anthropic guidance):**
- Include negative cases (agent should refuse, ask for clarification, or report "no issues")
- Include edge cases (malformed input, empty files, ambiguous requirements)
- Target difficulty: 40% basic, 40% intermediate, 20% advanced

### Grader Types

| Type | Level | Method | When to use |
|------|-------|--------|-------------|
| `exact` | Unit | String equality | Deterministic outputs |
| `contains` | Unit | Substring match | Key phrases must appear |
| `regex` | Unit | Pattern match | Structured output formats |
| `code` | Unit/E2E | Python script | Programmatic verification |
| `trajectory` | Trajectory | Transcript analysis | Tool usage, ordering, constraints |
| `llm_judge` | Trajectory/E2E | LLM with rubric | Quality, completeness, nuance |

### Subcomponent 3b: Eval Harness (Python)

**Location:** `src/harness/optimization/eval_harness.py`

Python infrastructure (not an agent) that executes eval-suite.yaml scenarios against generated resources in sandboxed agent sessions.

**Execution model:**
1. Parse `eval-suite.yaml`
2. For each scenario, k times (default k=3):
   - Spin up temporary agent session via `direct_agent.call_agent()`
   - Load target resource as agent's system prompt
   - Set up any `setup.files` in temp directory
   - Send scenario prompt
   - Capture full transcript (all messages, tool calls, outputs)
   - Run each grader against transcript and/or outcome
3. Aggregate results into `eval-results.json`

**Grader module structure:**

```
src/harness/optimization/graders/
  __init__.py
  base.py          # GraderResult dataclass, BaseGrader ABC
  deterministic.py # exact, contains, regex, code graders
  trajectory.py    # Transcript analysis (tool_called, no_tool, ordering, constraint)
  llm_judge.py     # LLM-based rubric scoring
  composite.py     # AND/OR combinations of graders
```

**Trajectory grader** parses agent transcripts to verify:
- Which tools were called and in what order
- Whether constraints were respected
- Whether agent asked for clarification when appropriate
- Token/turn efficiency

**Output:** `eval-results.json`

```yaml
summary:
  total_scenarios: 15
  pass_at_1: 0.80
  pass_at_3: 0.93
  pass_pow_3: 0.67
  by_level:
    unit: { total: 6, pass_pow_k: 0.83 }
    trajectory: { total: 5, pass_pow_k: 0.60 }
    e2e: { total: 4, pass_pow_k: 0.50 }
  by_capability:
    cap_1: { pass_pow_k: 0.75 }
    cap_2: { pass_pow_k: 0.60 }

results:
  - id: unit_001
    trials: [pass, pass, pass]
    pass_at_1: true
    pass_pow_k: true
    grader_details: [...]
  - id: traj_001
    trials: [pass, fail, pass]
    pass_at_1: true
    pass_pow_k: false
    failure_analysis: "Trial 2: agent skipped terraform-parser"
    transcript_path: eval/transcripts/traj_001_trial_2.json
```

**Key metrics (from Anthropic guidance):**
- **pass^k** = production quality metric ("did it work every single time?")
- **pass@k** = development metric ("can it work at all?")
- Per-capability breakdown shows which SPEC capabilities are well-served vs weak
- Transcript paths for failed trials enable mandatory transcript review

### Subcomponent 3c: Feedback Loop

```
eval-results.json
    |
    +-- pass^k >= threshold (e.g., 0.80) -> VALIDATE phase
    |
    +-- pass^k < threshold -> back to FAST-ITERATE with:
        - Specific failing scenarios (IDs + prompts)
        - Failure analysis (from transcripts)
        - Capability gaps (which SPEC capabilities underserved)
```

The optimizer receives concrete execution feedback, not just LLM opinions:

```
Previous optimization scored pass^3 = 0.67.

Failing scenarios:
- traj_001: Agent skipped terraform-parser tool in 1/3 trials.
  Fix: Strengthen instruction to always parse before analyzing.
- e2e_001: Compliance report missed 1 of 3 violations in 2/3 trials.
  Fix: Add explicit instruction to enumerate all resources before checking.

Focus improvements on these specific failures while preserving passing behavior.
```

---

## Component 4: Shared Protocol Layer

**Location:** `src/harness/optimization/protocols/`

Extracts implicit contracts between plugins into explicit, versioned schemas and utilities.

### Modules

**`protocols/signals.py`** -- Unified signal parsing

```python
@dataclass
class Signal:
    type: SignalType
    resource_path: str | None
    metadata: dict

class SignalParser:
    def parse(self, agent_response: str) -> list[Signal]:
        # Single place for all signal formats
        # Replaces scattered regex in orchestrator
```

New signals: `DESIGN_COMPLETE`, `EVAL_DESIGN_COMPLETE`, `EVAL_COMPLETE`

**`protocols/resource_types.py`** -- Extensible resource type registry

```python
class ResourceType(Enum):
    AGENT = "agent"
    SKILL = "skill"
    COMMAND = "command"
    HOOK = "hook"
    MCP_TOOL = "mcp_tool"
    MCP_SERVER = "mcp_server"
    PLUGIN = "plugin"

@dataclass
class ResourceTypeConfig:
    type: ResourceType
    path_pattern: str           # e.g., "agents/{name}.md"
    generator_agent: str        # Which agent creates this type
    generator_skill: str        # Which skill guides creation
    eval_strategy: str          # "content_only", "executable", "server"
    supports_versioning: bool
```

New resource types plug in by adding a `ResourceTypeConfig` entry -- no orchestrator changes needed.

**`protocols/quality.py`** -- Unified quality scoring

```python
@dataclass
class QualityScore:
    completeness: float
    accuracy: float
    clarity: float
    overall: float  # 0.35 * completeness + 0.35 * accuracy + 0.30 * clarity

@dataclass
class ExecutionScore:
    pass_at_1: float
    pass_at_k: float
    pass_pow_k: float
    by_level: dict
    by_capability: dict

@dataclass
class CombinedScore:
    quality: QualityScore
    execution: ExecutionScore
    recommendation: str  # ACCEPT / REFINE / REJECT
```

**`protocols/state.py`** -- Extended state schema

Adds DESIGN, EVAL_DESIGN, EXECUTION_EVAL phases. Adds `resource_plan_path`, `eval_suite_path`, `eval_results_path` fields. Adds per-resource `execution_scores` and `feedback_history`.

**`protocols/workspace.py`** -- Formalized directory structure

```
{workspace_root}/
  SPEC.md
  resource-plan.yaml          <- NEW
  CHANGELOG.md
  agents/
  skills/
  commands/
  tools/                      <- NEW (MCP tool scripts)
  mcp-servers/                <- NEW (full MCP server projects)
  research/
    notes/
    eval_criteria.yaml
    reviews/
  eval/                       <- NEW
    eval-suite.yaml
    eval-results.json
    transcripts/
  sessions/
    optimization-state.json
    *.summary.json
```

### Impact on Orchestrator

Orchestrator uses protocol layer instead of inline regex:

```python
# Before
match = re.search(r"\[GENERATE_COMPLETE:(.*?)\]", response)

# After
signals = self.signal_parser.parse(response)
for signal in signals:
    if signal.type == SignalType.GENERATE_COMPLETE:
        self._handle_generation_complete(signal.resource_path, signal.metadata)
```

Adding new phases or resource types requires only:
1. Add `ResourceTypeConfig` entry
2. Add `SignalType` enum value
3. Add phase handler method
4. Create the agent/skill

---

## Implementation Staging

### Stage 1: Shared Protocol Layer + Resource Architect

**Deliverables:**
- `protocols/` module (signals, resource types, quality, state, workspace)
- `cgf-resource-architect` agent definition
- `resource-plan.yaml` schema
- Refactor `multi_resource_orchestrator.py` to use protocol layer
- Add DESIGN phase to state machine
- Update SPEC.md parser for MCP resource types
- Tests for protocol layer and resource architect integration

### Stage 2: MCP Server/Tool Creation

**Deliverables:**
- `mcp-tool-creation` skill with templates
- `mcp-server-creation` skill with templates (Python + TypeScript)
- Research-backed content (MCP SDK patterns, testing strategies, real-world examples)
- Update `resource-type-guide.md` with MCP decision matrix
- Context-engineer prompt updates for MCP generation
- Tests for MCP resource generation

### Stage 3: Evaluation Framework

**Deliverables:**
- `cgf-eval-architect` agent definition
- `eval-suite.yaml` schema
- Eval harness (`eval_harness.py`)
- Grader implementations (deterministic, trajectory, llm_judge, composite)
- EXECUTION_EVAL phase in state machine
- Feedback loop from eval results to optimizer
- `eval-results.json` schema with pass@k / pass^k metrics
- Tests for graders and eval harness

### Stage 4: End-to-End Integration + Hardening

**Deliverables:**
- Full pipeline integration tests
- Checkpoint/resume support for new phases
- Human review gates for DESIGN and EVAL_DESIGN phases
- Performance optimization (parallel eval execution, caching)
- Documentation updates (CLAUDE.md, README.md)
- Edge case handling

### Scope Summary

| Stage | New Agents | New Skills | New Python Modules | Est. Files |
|-------|-----------|------------|-------------------|------------|
| 1 | 1 (resource-architect) | 0 | 5 (protocols) + refactor | ~15 |
| 2 | 0 | 2 (mcp-tool, mcp-server) | 0 (templates) | ~12 |
| 3 | 1 (eval-architect) | 0 | 6 (harness + graders) | ~15 |
| 4 | 0 | 0 | Integration tests + docs | ~10 |

Each stage is independently shippable.
