# CGF Evaluation Framework & Plugin Integration

**Created:** 2026-03-02
**Branch:** contextgrad-framework
**Status:** Stages 1-2 complete, Stages 3-4 pending

---

## Overview

This plan addresses two interlocking objectives for the ContextGrad Framework:

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

## Pipeline Architecture

The multi-resource optimization pipeline, showing completed and pending phases:

```
SPEC.md (business objective + capabilities + constraints)
    |
    v
+------------------------------------------------------------------+
|  PHASE 1: RESEARCH                                    [COMPLETE]  |
|  Owner: cgf-research-lead -> research-team:research-specialists  |
|  Input: SPEC capabilities, constraints, research_topics          |
|  Output: research/notes/*_findings.yaml, eval_criteria.yaml      |
|  Signal: [RESEARCH_COMPLETE]                                     |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 2: DESIGN                                      [COMPLETE]  |
|  Owner: cgf-resource-architect (cgf-agents plugin)               |
|  Input: SPEC + research findings + resource-type-guide           |
|  Output: resource-plan.yaml (what to build, why, dependencies)   |
|  Signal: [DESIGN_COMPLETE]                                       |
|  Human checkpoint: Optional review of proposed architecture      |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 3: GENERATE                                    [COMPLETE]  |
|  Owner: context-engineering:context-engineer                     |
|  Input: resource-plan.yaml + research findings                   |
|  Output: Generated resource files (agents, skills, MCP, etc.)    |
|  Signal: [GENERATE_COMPLETE:{path}] per resource                 |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 4: EVAL-DESIGN                                 [STAGE 3]  |
|  Owner: cgf-eval-architect (new agent in cgf-agents)             |
|  Input: Generated resources + SPEC + research findings           |
|  Output: eval-suite.yaml (unit, trajectory, e2e eval scenarios)  |
|  Signal: [EVAL_DESIGN_COMPLETE]                                  |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 5: FAST-ITERATE (existing, enhanced)           [COMPLETE]  |
|  Owner: cgf-prompt-optimizer                                     |
|  Input: Resources + eval_criteria + research                     |
|  Output: Versioned resources ({resource}-v{N}.md)                |
|  Evaluation: LLM-judge (CAIR framework) -- fast, cheap           |
|  Signal: [ITERATE_COMPLETE:{path}] + quality scores              |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 6: EXECUTION-EVAL                              [STAGE 3]  |
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
|  PHASE 7: VALIDATE (existing, enhanced)               [COMPLETE]  |
|  Owner: cgf-coherence-validator                                  |
|  Input: All finalized resources                                  |
|  Output: Coherence report + [VALIDATE_COMPLETE]                  |
|  Enhanced: Also validates MCP tool schemas, dependency graph     |
+------------------------------------------------------------------+
    |
    v
  FINALIZE -> Versioned, tested resources
```

---

## Completed Work

### Stage 1: Protocol Layer + Resource Architect (2026-03-02)

Extracted implicit plugin contracts into a shared protocol layer and added a resource-architect agent with a DESIGN phase between RESEARCH and GENERATE.

**Built:**
- `src/harness/optimization/protocols/` — 5 modules: `signals.py` (unified signal parsing replacing scattered regex), `resource_types.py` (extensible resource type registry with 7 types), `quality.py` (unified quality + execution scoring), `state.py` (extended state schema with DESIGN/EVAL_DESIGN/EXECUTION_EVAL phases), `workspace.py` (formalized directory structure)
- `src/harness/plugins/cgf-agents/agents/cgf-resource-architect.md` — Opus-model agent that analyzes SPEC + research + resource-type-guide to produce `resource-plan.yaml`
- `src/harness/plugins/cgf-agents/schemas/resource_plan.schema.json` — JSON Schema for resource plans
- Orchestrator refactored to use `SignalParser` protocol instead of ad-hoc regex
- `OptimizationPhase` enum extended from 6 to 9 phases
- SPEC parser extended with `ProposedMCPTool` and `ProposedMCPServer` types
- **120 tests** passing

### Stage 2: MCP Creation Skills (2026-03-02)

Added MCP tool and server creation capabilities to the context-engineering plugin, with orchestrator support for MCP resource types.

**Built:**
- `skills/mcp-tool-creation/` — Skill with FastMCP patterns, Anthropic tool description best practices, signal protocol
- `skills/mcp-server-creation/` — Skill covering Python (FastMCP) and TypeScript (@modelcontextprotocol/sdk) with packaging for uvx/npx
- 3 templates: `mcp-tool-template.py`, `mcp-server-python-template/`, `mcp-server-typescript-template/`
- `resource-type-guide.md` updated with MCP Tool and MCP Server sections, decision matrix entries, quality checklists
- `context-engineer.md` agent updated with MCP awareness, resource types 10-11, signal examples
- Orchestrator: conditional MCP directory creation, purpose lookup, generation instructions, plugin.json entries
- **47 tests** passing

> **Where these live now:** the `context-engineering` plugin moved out of
> the harness in Block 3 Step 2 and is consumed from the swe-marketplace
> clone (`/opt/plugins/swe-marketplace/plugins/context-engineering/` in the
> container, `<repo>/.plugins/swe-marketplace/...` after `make plugins-sync`
> for local dev). The two skills were also renamed
> `mcp-tool-creation` → `mcp-tool-dev` and
> `mcp-server-creation` → `mcp-server-dev` to match the marketplace
> `*-dev` naming convention. Of the 47 unit tests originally landed for
> Stage 2, 11 orchestrator-side tests remain in the harness; the 36 that
> asserted file paths inside the plugin were deleted on 2026-05-08
> (those are now swe-marketplace's responsibility to test).

---

## Stage 3: Evaluation Framework (DRAFT)

**Status:** Not started
**Goal:** Build a hybrid evaluation system: an eval-architect agent that generates eval suites, a Python eval harness that runs sandboxed agent sessions, grader implementations (deterministic + trajectory + LLM-judge), and a feedback loop from execution results back to the optimizer.
**Depends on:** Stage 1 (protocol layer, phase extensions), Stage 2 (MCP resources to evaluate)

### Task 1: Eval Suite Schema

**Files:**
- Create: `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json`
- Test: Schema validation tests

**Content:**
- Define scenario structure: id, level (unit/trajectory/e2e), target_resource, description, prompt, setup, graders, tags
- Define grader types: exact, contains, regex, code, trajectory, llm_judge
- Define config: trials_per_scenario, timeout_seconds, eval_model
- Validate against JSON Schema draft-07

---

### Task 2: Eval-Architect Agent Definition

**Files:**
- Create: `src/harness/plugins/cgf-agents/agents/cgf-eval-architect.md`

**Agent design:**
- Model: sonnet
- Tools: Read, Write, Glob, Grep
- Max turns: 100
- Reads: generated resources, SPEC.md, research findings, resource plan
- Reasons about resource type → appropriate eval strategies
- Produces eval-suite.yaml following schema
- Balanced test design: positive + negative cases, 40/40/20 difficulty split
- Emits `[EVAL_DESIGN_COMPLETE]` signal

**Key reasoning the agent must do:**
- Agent resource → trajectory evals (tool usage, constraints)
- Skill resource → unit evals (content quality, trigger accuracy)
- MCP tool → executable evals (function correctness, error handling)
- MCP server → server evals (tool registration, response format, error messages)
- All types → e2e evals (full task completion)

---

### Task 3: Grader Infrastructure

**Files:**
- Create: `src/harness/optimization/graders/__init__.py`
- Create: `src/harness/optimization/graders/base.py`
- Create: `src/harness/optimization/graders/deterministic.py`
- Create: `src/harness/optimization/graders/trajectory.py`
- Create: `src/harness/optimization/graders/llm_judge.py`
- Create: `src/harness/optimization/graders/composite.py`
- Test: `tests/unit/test_optimization/test_graders.py`

**base.py:**
```python
@dataclass
class GraderResult:
    passed: bool
    score: float       # 0.0-1.0
    details: str       # Human-readable explanation
    grader_type: str

class BaseGrader(ABC):
    @abstractmethod
    async def grade(self, transcript: AgentTranscript, scenario: EvalScenario) -> GraderResult: ...
```

**deterministic.py:**
- ExactGrader: string equality
- ContainsGrader: substring match (case-insensitive option)
- RegexGrader: pattern match
- CodeGrader: execute Python snippet, check assertions

**trajectory.py:**
- Parse agent transcript for tool calls
- Assert tool_called (optionally before/after another event)
- Assert no_tool (tool was NOT called)
- Assert ordering (tool A before tool B)
- Assert constraint (LLM-verified constraint from transcript)
- This is the most complex grader — needs careful design of transcript parsing

**llm_judge.py:**
- Takes rubric + transcript/output
- Calls eval model (configurable: haiku/sonnet/opus)
- Parses score (1-5 scale, mapped to 0.0-1.0)
- Pass threshold configurable per scenario

**composite.py:**
- AndGrader: all sub-graders must pass
- OrGrader: at least one sub-grader must pass

---

### Task 4: Agent Transcript Capture

**Files:**
- Create: `src/harness/optimization/graders/transcript.py`

**Purpose:** Structured representation of an agent session for grading.

```python
@dataclass
class AgentTranscript:
    messages: list[TranscriptMessage]  # All messages in order
    tool_calls: list[ToolCall]         # Extracted tool calls
    final_output: str                  # Last text message
    total_turns: int
    total_tokens: int

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    result: str
    turn_number: int
    timestamp: float
```

Build from `direct_agent.call_agent()` message stream — each yielded message includes tool call data.

---

### Task 5: Eval Harness

**Files:**
- Create: `src/harness/optimization/eval_harness.py`
- Test: `tests/unit/test_optimization/test_eval_harness.py`

**Core loop:**
```python
class EvalHarness:
    async def run(self, eval_suite_path: Path, workspace: Path) -> EvalResults:
        suite = self._load_suite(eval_suite_path)
        results = []
        for scenario in suite.scenarios:
            trials = []
            for trial_num in range(suite.config.trials_per_scenario):
                transcript = await self._run_scenario(scenario, workspace)
                grader_results = await self._grade(scenario, transcript)
                trials.append(TrialResult(grader_results, transcript))
            results.append(ScenarioResult(scenario, trials))
        return self._aggregate(results)
```

**_run_scenario:**
- Create temp directory for scenario files (setup.files)
- Call `direct_agent.call_agent()` with target resource as system prompt
- Capture full transcript
- Clean up temp directory

**_aggregate:**
- Calculate pass@1, pass@k, pass^k per scenario
- Roll up by level (unit/trajectory/e2e) and by capability tag
- Save to eval-results.json
- Save failed trial transcripts to eval/transcripts/

---

### Task 6: EVAL_DESIGN Phase in Orchestrator

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Test: `tests/unit/test_optimization/test_orchestrator_eval_design_phase.py`

**Changes:**
- Add `AGENT_EVAL_ARCHITECT = "cgf-agents:cgf-eval-architect"` constant
- Add `_delegate_eval_design()` method
- Insert EVAL_DESIGN phase after GENERATE in `_run_pipeline()`
- Parse `[EVAL_DESIGN_COMPLETE]` signal
- Store eval_suite_path in state

---

### Task 7: EXECUTION_EVAL Phase in Orchestrator

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Test: `tests/unit/test_optimization/test_orchestrator_execution_eval.py`

**Changes:**
- Add `_run_execution_eval()` method (calls EvalHarness, not an agent)
- Insert EXECUTION_EVAL phase after ITERATE in `_run_pipeline()`
- Implement feedback loop: if pass^k < threshold, build feedback prompt and loop back to ITERATE
- Store eval_results_path and feedback_history in state
- Add `design_timeout` and `execution_eval_timeout` to MultiResourceConfig

---

### Task 8: Feedback Loop Integration

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py` (_delegate_iteration)

**Changes:**
- When iteration is triggered by execution eval feedback:
  - Include failing scenario details in optimizer prompt
  - Include failure analysis from transcripts
  - Include capability gap analysis
  - Instruct optimizer to fix specific failures while preserving passing behavior
- Track feedback_history in state for resume support
- Limit feedback-driven iterations (max 2 before escalating to human review)

---

### Task 9: Integration Tests

**Files:**
- Create: `tests/integration/test_eval_framework_integration.py`

**Tests:**
- Full eval suite generation → execution → grading round-trip (with mocked agent)
- Feedback loop: failing eval → re-optimize → passing eval
- Grader accuracy: known-good and known-bad transcripts scored correctly
- Resume: interrupt mid-eval, resume from checkpoint

---

### Task 10: Documentation

**Files:**
- Modify: `CLAUDE.md` — Update pipeline diagram, agent counts, phase descriptions
- Mark Stage 3 as implemented in this plan

---

## Stage 4: End-to-End Integration & Hardening (DRAFT)

**Status:** Not started
**Goal:** Polish the full pipeline, add checkpoint/resume for new phases, human review gates, performance optimization, comprehensive documentation, and edge case handling.
**Depends on:** Stages 1, 2, 3

### Task 1: Full Pipeline E2E Test

**Files:**
- Create: `tests/e2e/cgf/test_full_pipeline.py`

**Scope:** Test the complete pipeline from SPEC.md to finalized, evaluated resources:

```
SPEC.md → RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → FINALIZE
```

**Approach:**
- Use a simple, well-defined SPEC (e.g., a 2-resource plugin: 1 agent + 1 skill)
- Mock external API calls but exercise all Python orchestration code
- Verify:
  - All phases execute in order
  - State file updated at each transition
  - Resource files created with correct versions
  - Eval suite generated and executed
  - Final resources pass quality + execution thresholds
  - CHANGELOG.md populated correctly
  - No orphaned temp files

---

### Task 2: Checkpoint/Resume for New Phases

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Modify: `src/harness/progress.py` (state serialization)
- Test: `tests/unit/test_optimization/test_checkpoint_resume.py`

**Scope:**
- Verify resume from each new phase: DESIGN, EVAL_DESIGN, EXECUTION_EVAL
- Ensure resource-plan.yaml is preserved on resume from DESIGN
- Ensure eval-suite.yaml is preserved on resume from EVAL_DESIGN
- Ensure partial eval-results.json is loadable on resume from EXECUTION_EVAL
- Test: kill orchestrator mid-phase, restart, verify correct phase resumes

---

### Task 3: Human Review Gates

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Modify: `src/harness/plugins/cgf-agents/commands/cgf.md` (add `/cgf review` subcommand)

**Scope:**
- Add optional review checkpoints after DESIGN and EVAL_DESIGN phases
- When `--review` flag is set:
  - After DESIGN: pause, display resource-plan.yaml summary, wait for `/cgf proceed` or `/cgf edit`
  - After EVAL_DESIGN: pause, display eval-suite.yaml summary, wait for approval
  - After EXECUTION_EVAL: pause, display eval-results.json summary with pass^k scores
- User can modify resource-plan.yaml or eval-suite.yaml before proceeding
- State tracks `checkpoint_phase` and `checkpoint_approved` for resume

---

### Task 4: Performance Optimization

**Files:**
- Modify: `src/harness/optimization/eval_harness.py`
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`

**Scope:**
- Parallel eval scenario execution: run independent scenarios concurrently (respecting API rate limits)
- Eval result caching: skip re-running scenarios that passed in previous iteration
- Generation parallelism: generate independent resources (no dependency) in parallel
- Timeout tuning: add DESIGN and EVAL_DESIGN timeouts to config
- Token usage tracking: log total tokens consumed per phase for cost awareness

---

### Task 5: Edge Case Handling

**Files:**
- Modify: Various orchestrator and eval harness files
- Test: `tests/unit/test_optimization/test_edge_cases.py`

**Scenarios to handle:**
- Empty eval results (no scenarios generated → skip EXECUTION_EVAL)
- All scenarios fail (every pass^k = 0 → REJECT, don't loop forever)
- MCP server build failure (compilation error → mark resource as failed, continue others)
- Resource-architect proposes 0 resources (invalid plan → error with guidance)
- SPEC has no capabilities section (minimal SPEC → resource-architect uses defaults)
- Agent timeout during eval (individual scenario timeout → mark trial as fail, continue)
- Disk space exhaustion (transcript storage → warn and truncate)
- Circular dependencies in resource plan (validate and reject)
- Research phase produces no findings (proceed with reduced confidence)

---

### Task 6: Error Recovery and Retry

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Modify: `src/harness/optimization/eval_harness.py`

**Scope:**
- Add configurable retry for agent delegation failures (1 retry with simplified prompt)
- Add eval scenario retry for transient failures (API timeout, rate limit)
- Distinguish between transient errors (retry) and permanent errors (mark failed)
- Log all retries with structured data for debugging

---

### Task 7: Comprehensive Documentation Update

**Files:**
- Modify: `CLAUDE.md` — Full rewrite of CGF section to reflect new pipeline
- Modify: `README.md` — Update user-facing docs with new commands and workflow
- Create: `docs/examples/CGF_EVAL_EXAMPLE.md` — Walkthrough of a full optimization with eval

**CLAUDE.md updates:**
- Pipeline diagram with all 9 phases
- Complete agent table (all agents across 3 plugins)
- Resource type table (all 7 types)
- Workspace layout with eval/ directory
- Eval metrics explanation (pass@k, pass^k)
- Configuration reference for all new settings
- Troubleshooting section for eval-related issues

---

### Task 8: Memory and Auto-Memory Updates

**Files:**
- Modify: Auto-memory MEMORY.md — Update project status, key files, recent work
- Update: Memory MCP entity for ab-casdk-harness — Update observations

**Content:**
- Summarize the full CGF evaluation pipeline
- Document the plugin coordination architecture
- Note key architectural decisions and their rationale
- Update inter-project relationships (if applicable)

---

## Staging Summary

| Stage | New Agents | New Skills | New Python Modules | Status |
|-------|-----------|------------|-------------------|--------|
| 1 | 1 (resource-architect) | 0 | 5 (protocols) + refactor | **Complete** (120 tests) |
| 2 | 0 | 2 (mcp-tool, mcp-server) | 0 (templates only) | **Complete** (47 tests) |
| 3 | 1 (eval-architect) | 0 | 6 (harness + graders) | Draft |
| 4 | 0 | 0 | Integration tests + docs | Draft |

Each stage is independently shippable. Stages 3-4 task lists are outlines — full TDD steps and exact code to be added before implementation.
