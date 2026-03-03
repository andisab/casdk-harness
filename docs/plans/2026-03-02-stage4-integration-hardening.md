# Stage 4: End-to-End Integration & Hardening — Implementation Plan (DRAFT)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> **Status: DRAFT** — Task outlines only. Full TDD steps to be added after Stages 1-3 are complete and real integration experience informs what needs hardening.

**Goal:** Polish the full pipeline, add checkpoint/resume for new phases, human review gates, performance optimization, comprehensive documentation, and edge case handling.

**Architecture:** No new components — this stage hardens, optimizes, and documents Stages 1-3.

**Depends on:** Stages 1, 2, 3

**Design doc:** `docs/plans/2026-03-02-cgf-eval-framework-design.md` (Section: Implementation Staging)

---

## Task 1: Full Pipeline E2E Test

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

## Task 2: Checkpoint/Resume for New Phases

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

## Task 3: Human Review Gates

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

## Task 4: Performance Optimization

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

## Task 5: Edge Case Handling

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

## Task 6: Error Recovery and Retry

**Files:**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py`
- Modify: `src/harness/optimization/eval_harness.py`

**Scope:**
- Add configurable retry for agent delegation failures (1 retry with simplified prompt)
- Add eval scenario retry for transient failures (API timeout, rate limit)
- Distinguish between transient errors (retry) and permanent errors (mark failed)
- Log all retries with structured data for debugging

---

## Task 7: Comprehensive Documentation Update

**Files:**
- Modify: `CLAUDE.md` — Full rewrite of CGF section to reflect new pipeline
- Modify: `README.md` — Update user-facing docs with new commands and workflow
- Modify: `docs/plans/2026-03-02-cgf-eval-framework-design.md` — Mark all stages as implemented
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

## Task 8: Memory and Auto-Memory Updates

**Files:**
- Modify: Auto-memory MEMORY.md — Update project status, key files, recent work
- Update: Memory MCP entity for ab-casdk-harness — Update observations

**Content:**
- Summarize the full CGF evaluation pipeline
- Document the plugin coordination architecture
- Note key architectural decisions and their rationale
- Update inter-project relationships (if applicable)
