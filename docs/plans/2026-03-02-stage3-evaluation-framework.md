# Stage 3: Evaluation Framework — Implementation Plan (DRAFT)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> **Status: DRAFT** — Task outlines only. Full TDD steps, code, and exact file references to be added before implementation begins.

**Goal:** Build a hybrid evaluation system: an eval-architect agent that generates eval suites, a Python eval harness that runs sandboxed agent sessions, grader implementations (deterministic + trajectory + LLM-judge), and a feedback loop from execution results back to the optimizer.

**Architecture:** New `cgf-eval-architect` agent in cgf-agents plugin generates `eval-suite.yaml`. Python `eval_harness.py` + `graders/` package executes scenarios via `direct_agent.call_agent()`. Results in `eval-results.json` with pass@k/pass^k metrics. EXECUTION_EVAL phase added to orchestrator.

**Tech Stack:** Python 3.12+, dataclasses, structlog, pytest, YAML, Claude Agent SDK (for sandboxed sessions)

**Depends on:** Stage 1 (protocol layer, phase extensions), Stage 2 (MCP resources to evaluate)

**Design doc:** `docs/plans/2026-03-02-cgf-eval-framework-design.md` (Section: Component 3)

---

## Task 1: Eval Suite Schema

**Files:**
- Create: `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json`
- Test: Schema validation tests

**Content:**
- Define scenario structure: id, level (unit/trajectory/e2e), target_resource, description, prompt, setup, graders, tags
- Define grader types: exact, contains, regex, code, trajectory, llm_judge
- Define config: trials_per_scenario, timeout_seconds, eval_model
- Validate against JSON Schema draft-07

---

## Task 2: Eval-Architect Agent Definition

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

## Task 3: Grader Infrastructure

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

## Task 4: Agent Transcript Capture

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

## Task 5: Eval Harness

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

## Task 6: EVAL_DESIGN Phase in Orchestrator

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

## Task 7: EXECUTION_EVAL Phase in Orchestrator

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

## Task 8: Feedback Loop Integration

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

## Task 9: Integration Tests

**Files:**
- Create: `tests/integration/test_eval_framework_integration.py`

**Tests:**
- Full eval suite generation → execution → grading round-trip (with mocked agent)
- Feedback loop: failing eval → re-optimize → passing eval
- Grader accuracy: known-good and known-bad transcripts scored correctly
- Resume: interrupt mid-eval, resume from checkpoint

---

## Task 10: Documentation

**Files:**
- Modify: `CLAUDE.md` — Update pipeline diagram, agent counts, phase descriptions
- Modify: `docs/plans/2026-03-02-cgf-eval-framework-design.md` — Mark Stage 3 as implemented
