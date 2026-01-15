# CGF Agentic Pipeline Roadmap

> **Goal**: Build a resource-agnostic optimization framework that uses agentic workflows to automatically research, generate tests, optimize, and evaluate any context-engineering resource.

## Executive Summary

The Claude Gradient Feedback (CGF) framework evolves through three major versions:

| Version | Scope | Key Capability |
|---------|-------|----------------|
| **CGF 1.0** | Single resource optimization | CLI-driven optimization with manual tests |
| **CGF 2.0** | Agentic single resource | Auto-research, auto-test-gen, auto-evaluation |
| **CGF 3.0** | Multi-resource composition | Optimize resource combinations for complex outcomes |

This roadmap defines the architecture and implementation plan for **CGF 2.0**, with forward compatibility for CGF 3.0.


## Design Principles

### 1. Resource Agnostic

CGF optimizes **any** context-engineering resource:

| Resource Type | What Gets Optimized | Example Outcome |
|---------------|---------------------|-----------------|
| **Agent** | System prompt, tool selection | Better task completion |
| **Skill** | Activation triggers, instructions | More reliable invocation |
| **Command** | Argument handling, output format | Better UX |
| **MCP Server** | Tool definitions, responses | More useful tools |
| **Workflow** | Orchestration steps, hand-offs | Smoother coordination |
| **Spec** | Requirements, acceptance criteria | Clearer specifications |
| **Hook** | Trigger conditions, actions | More reliable automation |
| **Plugin** | Component composition | Better integration |

### 2. Autonomous with Optional Review

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION MODES                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FULLY AUTONOMOUS (default)                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Research → Tests → Optimize → Evaluate → Accept/Reject   │   │
│  │                                                          │   │
│  │ Human: "Optimize python-expert for async programming"    │   │
│  │ CGF: [runs full pipeline, reports final result]          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  WITH CHECKPOINTS (--review flag)                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Research → [PAUSE] → Tests → [PAUSE] → Optimize → ...    │   │
│  │                                                          │   │
│  │ Human: "Optimize python-expert --review"                 │   │
│  │ CGF: "Research complete. Review eval_criteria.md?"       │   │
│  │ Human: "Proceed" / "Edit X"                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Progressive Enhancement

Each CGF version builds on the previous:

```
CGF 1.0 (Current)              CGF 2.0 (This Roadmap)           CGF 3.0 (Future)
┌─────────────────┐            ┌─────────────────────┐          ┌─────────────────────┐
│ Manual Tests    │            │ Auto Test Gen       │          │ Multi-Resource      │
│ CLI Execution   │     →      │ Agentic Research    │    →     │ Composition         │
│ Quantitative    │            │ Qualitative Eval    │          │ Workflow Synthesis  │
│ Single Resource │            │ Any Resource Type   │          │ Cross-Optimization  │
└─────────────────┘            └─────────────────────┘          └─────────────────────┘
```


## Pre-Requisite: Research-Team Context7 Enhancement

Before CGF 2.0, enhance research-team plugin with intelligent source selection.

### Current State

```
research-specialist → WebSearch only → prose research notes
```

### Target State

```
research-specialist → Source Router → Context7 (docs)
                                   → WebSearch (practices)
                                   → Codebase (implementation)
                                   → structured findings
```

### Implementation: Smart Source Router

Add source selection logic to research-specialist:

```markdown
# Source Selection Rules

## Use Context7 When:
- Topic mentions a library, framework, or language
- Keywords: "documentation", "API", "usage", "reference"
- Examples: "FastAPI routing", "Kubernetes deployments", "React hooks"

## Use WebSearch When:
- Topic is about practices, patterns, comparisons
- Keywords: "best practices", "trends", "industry", "comparison"
- Examples: "microservice patterns 2025", "API design best practices"

## Use Codebase Analysis When:
- Topic references "this project", "our code", "current implementation"
- Keywords: "how we do X", "our approach to Y"
- Examples: "how authentication works here", "our error handling pattern"

## Use Multiple Sources When:
- Topic requires comparison: "compare our API to best practices"
- Topic needs depth: "comprehensive guide to X"
```

### Changes to research-specialist.md

```diff
tools: WebSearch, Write, Read, Glob, Grep
+ tools: WebSearch, Write, Read, Glob, Grep, mcp__context7__resolve-library-id, mcp__context7__query-docs

+ <source_router>
+ ## Automatic Source Selection
+
+ Before starting research, determine the optimal source mix:
+
+ 1. **Scan topic for library/framework names**
+    - If found: Start with Context7 (resolve-library-id → query-docs)
+    - Query for: tutorials, examples, API reference, common patterns
+
+ 2. **Scan topic for practice/pattern keywords**
+    - If found: Use WebSearch for industry practices
+    - Query for: "best practices", "patterns", "architecture"
+
+ 3. **Scan topic for codebase references**
+    - If found: Use Glob/Grep/Read for local analysis
+    - Then optionally WebSearch for comparison
+
+ **Example source routing:**
+ - "Kubernetes deployment patterns" → Context7 (k8s docs) + WebSearch (industry)
+ - "FastAPI async best practices" → Context7 (FastAPI) + WebSearch (async patterns)
+ - "How does our auth work?" → Codebase analysis + WebSearch (comparison)
+ </source_router>
```

### New Output Mode: CGF Research

Add CGF-specific output format to research-specialist:

```markdown
# Output Mode: CGF Research

When orchestrator specifies "output_mode: cgf", produce structured findings:

## Format

```yaml
# research_findings.yaml
topic: "{research topic}"
source_mix:
  - context7: {percentage}%
  - websearch: {percentage}%
  - codebase: {percentage}%

key_competencies:
  - name: "{competency 1}"
    description: "{what this competency means}"
    positive_indicators:
      - "{behavior that indicates competence}"
    negative_indicators:
      - "{behavior that indicates incompetence}"
    test_scenarios:
      - "{scenario 1}"
      - "{scenario 2}"

  - name: "{competency 2}"
    ...

edge_cases:
  - scenario: "{edge case}"
    importance: "{why it matters}"
    expected_handling: "{how to handle it}"

common_mistakes:
  - mistake: "{what people get wrong}"
    correction: "{correct approach}"

sources:
  - type: "context7"
    library: "{library-id}"
    topics_queried: ["{topic1}", "{topic2}"]
  - type: "websearch"
    queries: ["{query1}", "{query2}"]
    top_sources: ["{url1}", "{url2}"]
```
```


## CGF 2.0 Architecture

### Resource Type Detection

CGF 2.0 must detect and adapt to any resource type:

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESOURCE TYPE DETECTION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: "Optimize python-expert for async programming"          │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  cgf-orchestrator                         │   │
│  │                                                           │   │
│  │  1. Parse input to identify:                              │   │
│  │     - Resource path or name                               │   │
│  │     - Resource type (detect from path/content)            │   │
│  │     - Optimization goal                                   │   │
│  │                                                           │   │
│  │  2. Load resource via ResourceRegistry                    │   │
│  │     - AgentResource, SkillResource, CommandResource, etc. │   │
│  │                                                           │   │
│  │  3. Determine optimization strategy:                      │   │
│  │     - What aspects can be optimized                       │   │
│  │     - What test patterns apply                            │   │
│  │     - What evaluation criteria matter                     │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Resource Type → Optimization Strategy Mapping:                  │
│                                                                  │
│  ┌──────────────┬────────────────────────────────────────────┐  │
│  │ Resource     │ Optimization Focus                         │  │
│  ├──────────────┼────────────────────────────────────────────┤  │
│  │ Agent        │ System prompt, tool selection, examples    │  │
│  │ Skill        │ Trigger keywords, instructions, examples   │  │
│  │ Command      │ Argument handling, help text, defaults     │  │
│  │ MCP Tool     │ Description, parameter schemas, responses  │  │
│  │ Workflow     │ Steps, hand-offs, error handling           │  │
│  │ Spec         │ Requirements clarity, acceptance criteria  │  │
│  │ Hook         │ Trigger conditions, action reliability     │  │
│  │ Plugin       │ Component integration, discoverability     │  │
│  └──────────────┴────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Full Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CGF 2.0 PIPELINE                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  USER REQUEST                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ "Optimize {resource} for {goal}"                                          │   │
│  │ Examples:                                                                 │   │
│  │   - "Optimize python-expert for async programming"                        │   │
│  │   - "Optimize the /deploy command for better error handling"              │   │
│  │   - "Optimize the joplin-research skill for technical topics"             │   │
│  │   - "Optimize the security-review workflow for faster execution"          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 0: INITIALIZATION                                                   │   │
│  │                                                                           │   │
│  │  cgf-orchestrator:                                                        │   │
│  │  ├── Parse request                                                        │   │
│  │  ├── Detect resource type                                                 │   │
│  │  ├── Load resource via ResourceRegistry                                   │   │
│  │  ├── Determine optimization strategy                                      │   │
│  │  ├── Create workspace: workspace/{resource}/                              │   │
│  │  └── Initialize run state                                                 │   │
│  │                                                                           │   │
│  │  Output: run_config.yaml                                                  │   │
│  │    resource_type: agent                                                   │   │
│  │    resource_id: python-expert                                             │   │
│  │    optimization_goal: "async programming"                                 │   │
│  │    strategy: prompt_optimization                                          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 1: RESEARCH (Parallel)                                              │   │
│  │                                                                           │   │
│  │  cgf-research-lead spawns parallel researchers:                           │   │
│  │                                                                           │   │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐             │   │
│  │  │ Domain Expert   │ │ Best Practices  │ │ Current State   │             │   │
│  │  │ (Context7)      │ │ (WebSearch)     │ │ (Codebase)      │             │   │
│  │  │                 │ │                 │ │                 │             │   │
│  │  │ • Library docs  │ │ • Industry      │ │ • Current impl  │             │   │
│  │  │ • API reference │ │   patterns      │ │ • Usage data    │             │   │
│  │  │ • Examples      │ │ • Blog posts    │ │ • Pain points   │             │   │
│  │  │ • Common issues │ │ • Tutorials     │ │ • Dependencies  │             │   │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘             │   │
│  │           │                   │                   │                       │   │
│  │           └───────────────────┼───────────────────┘                       │   │
│  │                               ▼                                           │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │   │
│  │  │ cgf-criteria-synthesizer                                           │   │   │
│  │  │ Synthesizes findings into resource-appropriate eval criteria       │   │   │
│  │  └───────────────────────────────────────────────────────────────────┘   │   │
│  │                               │                                           │   │
│  │  Output: eval_criteria.yaml                                              │   │
│  │                               │                                           │   │
│  │  [CHECKPOINT if --review]     ▼                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2: TEST GENERATION                                                  │   │
│  │                                                                           │   │
│  │  cgf-test-architect:                                                      │   │
│  │  ├── Read eval_criteria.yaml                                              │   │
│  │  ├── Read resource definition                                             │   │
│  │  ├── Determine test pattern for resource type:                            │   │
│  │  │   • Agent: User prompts → expected behaviors                           │   │
│  │  │   • Skill: Trigger phrases → activation reliability                    │   │
│  │  │   • Command: CLI invocations → correct outputs                         │   │
│  │  │   • MCP: Tool calls → proper responses                                 │   │
│  │  │   • Workflow: Step sequences → successful completion                   │   │
│  │  └── Generate diverse test suite                                          │   │
│  │                               │                                           │   │
│  │                               ▼                                           │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │   │
│  │  │ cgf-test-validator                                                 │   │   │
│  │  │ • Schema compliance                                                │   │   │
│  │  │ • Coverage analysis (all criteria covered?)                        │   │   │
│  │  │ • Difficulty balance (easy/medium/hard)                            │   │   │
│  │  │ • Prompt realism (not artificial)                                  │   │   │
│  │  └───────────────────────────────────────────────────────────────────┘   │   │
│  │                               │                                           │   │
│  │  Output: test_suite.yaml + coverage_report.md                            │   │
│  │                               │                                           │   │
│  │  [CHECKPOINT if --review]     ▼                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 3: OPTIMIZATION (Existing CLI)                                      │   │
│  │                                                                           │   │
│  │  python -m harness.optimization.cli.optimize \                            │   │
│  │      --resource {path} \                                                  │   │
│  │      --test-suite test_suite.yaml \                                       │   │
│  │      --optimizer dspy|textgrad \                                          │   │
│  │      --iterations 10                                                      │   │
│  │                                                                           │   │
│  │  DSPy MIPROv2 or TextGrad TGD:                                           │   │
│  │  ├── Run baseline evaluation                                              │   │
│  │  ├── Generate prompt candidates                                           │   │
│  │  ├── Evaluate each candidate against test suite                           │   │
│  │  ├── Select best performing                                               │   │
│  │  ├── Iterate until convergence or max iterations                          │   │
│  │  └── Output optimized resource                                            │   │
│  │                                                                           │   │
│  │  Output: {resource}-v{N}.md + summary.json                                │   │
│  │                               │                                           │   │
│  │  [NO CHECKPOINT - runs to completion]                                     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 4: EVALUATION                                                       │   │
│  │                                                                           │   │
│  │  cgf-result-evaluator:                                                    │   │
│  │  ├── Read original resource                                               │   │
│  │  ├── Read optimized resource                                              │   │
│  │  ├── Read eval_criteria.yaml (original goals)                             │   │
│  │  ├── Read summary.json (quantitative results)                             │   │
│  │  │                                                                        │   │
│  │  ├── Perform multi-dimensional evaluation:                                │   │
│  │  │   ┌─────────────────────────────────────────────────────────────┐     │   │
│  │  │   │ COHERENCE: Is the optimized resource well-structured?       │     │   │
│  │  │   │ • Readability analysis                                      │     │   │
│  │  │   │ • Structural consistency                                    │     │   │
│  │  │   │ • Logical flow                                              │     │   │
│  │  │   ├─────────────────────────────────────────────────────────────┤     │   │
│  │  │   │ ALIGNMENT: Does it still match the original intent?         │     │   │
│  │  │   │ • Compare to eval_criteria                                  │     │   │
│  │  │   │ • Check for drift from goals                                │     │   │
│  │  │   │ • Verify core functionality preserved                       │     │   │
│  │  │   ├─────────────────────────────────────────────────────────────┤     │   │
│  │  │   │ IMPROVEMENT: What specifically got better?                  │     │   │
│  │  │   │ • Diff analysis                                             │     │   │
│  │  │   │ • Score improvement breakdown                               │     │   │
│  │  │   │ • Capability additions                                      │     │   │
│  │  │   ├─────────────────────────────────────────────────────────────┤     │   │
│  │  │   │ REGRESSION: Did anything get worse or lost?                 │     │   │
│  │  │   │ • Capability comparison                                     │     │   │
│  │  │   │ • Edge case handling                                        │     │   │
│  │  │   │ • Specificity vs generality trade-offs                      │     │   │
│  │  │   └─────────────────────────────────────────────────────────────┘     │   │
│  │  │                                                                        │   │
│  │  └── Generate recommendation:                                             │   │
│  │      • ACCEPT: Use optimized resource (score improved, no regressions)    │   │
│  │      • REFINE: Re-run with specific adjustments                           │   │
│  │      • REJECT: Keep original (regressions or coherence issues)            │   │
│  │                                                                           │   │
│  │  Output: review_report.md with recommendation                             │   │
│  │                               │                                           │   │
│  │  [CHECKPOINT if --review]     ▼                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 5: FINALIZATION                                                     │   │
│  │                                                                           │   │
│  │  Based on evaluation recommendation:                                      │   │
│  │                                                                           │   │
│  │  ACCEPT:                                                                  │   │
│  │  ├── Move optimized resource to standard location                         │   │
│  │  ├── Archive original as {resource}-orig.md                               │   │
│  │  ├── Update any references (if applicable)                                │   │
│  │  └── Generate changelog entry                                             │   │
│  │                                                                           │   │
│  │  REFINE:                                                                  │   │
│  │  ├── Adjust eval_criteria based on feedback                               │   │
│  │  ├── Regenerate or modify test suite                                      │   │
│  │  └── Loop back to Phase 3 with adjustments                                │   │
│  │                                                                           │   │
│  │  REJECT:                                                                  │   │
│  │  ├── Keep original resource unchanged                                     │   │
│  │  ├── Archive optimization attempt for analysis                            │   │
│  │  └── Generate failure report                                              │   │
│  │                                                                           │   │
│  │  Output: final_report.md with actions taken                               │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Orchestrator Design: State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    CGF ORCHESTRATOR STATE MACHINE                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  States and Transitions:                                         │
│                                                                  │
│  ┌──────────┐                                                    │
│  │  INIT    │                                                    │
│  └────┬─────┘                                                    │
│       │ parse request, detect resource type                      │
│       ▼                                                          │
│  ┌──────────┐                                                    │
│  │ RESEARCH │◄──────────────────────────────────────┐           │
│  └────┬─────┘                                        │           │
│       │ spawn researchers, synthesize criteria       │           │
│       ▼                                              │           │
│  ┌──────────┐                                        │           │
│  │ TEST_GEN │                                        │ REFINE    │
│  └────┬─────┘                                        │           │
│       │ generate tests, validate coverage            │           │
│       ▼                                              │           │
│  ┌──────────┐                                        │           │
│  │ OPTIMIZE │                                        │           │
│  └────┬─────┘                                        │           │
│       │ run DSPy/TextGrad optimization               │           │
│       ▼                                              │           │
│  ┌──────────┐     ┌──────────┐                      │           │
│  │ EVALUATE ├────►│ FINALIZE │──────────────────────┤           │
│  └────┬─────┘     └──────────┘                      │           │
│       │                ▲                             │           │
│       │ ACCEPT         │                             │           │
│       └────────────────┘                             │           │
│       │                                              │           │
│       │ REJECT                                       │           │
│       ▼                                              │           │
│  ┌──────────┐                                        │           │
│  │ COMPLETE │ (no changes made)                      │           │
│  └──────────┘                                        │           │
│                                                                  │
│  Checkpoints (when --review):                                    │
│  • After RESEARCH: Review eval_criteria.yaml                     │
│  • After TEST_GEN: Review test_suite.yaml                        │
│  • After EVALUATE: Review recommendation                         │
│                                                                  │
│  State Persistence:                                              │
│  • run_state.json in workspace/{resource}/                       │
│  • Allows resume from any checkpoint                             │
│  • Tracks all intermediate artifacts                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```


### Orchestrator Implementation Detail

The orchestrator is the critical coordination layer. This section provides detailed implementation guidance.

#### State Transitions and Guards

```yaml
# State transition definitions with guards and actions
transitions:
  INIT:
    next: RESEARCH
    guards:
      - resource_exists: "Resource must be loadable via ResourceRegistry"
      - goal_specified: "Optimization goal must be parseable"
    actions:
      - create_workspace: "workspace/{resource_id}/"
      - load_resource: "Load via ResourceRegistry"
      - detect_type: "Determine resource type from content/path"
      - select_strategy: "Load strategy from optimization_strategies.yaml"
      - write_run_config: "run_config.yaml"
      - init_run_state: "run_state.json with state=RESEARCH"

  RESEARCH:
    next: TEST_GEN | CHECKPOINT_RESEARCH
    guards:
      - run_config_valid: "run_config.yaml must exist and be valid"
    actions:
      - spawn_researchers: "Parallel research agents with source routing"
      - wait_all: "Collect all research findings"
      - synthesize_criteria: "cgf-criteria-synthesizer → eval_criteria.yaml"
      - update_run_state: "state=TEST_GEN or CHECKPOINT_RESEARCH"
    checkpoint_condition: "--review flag set"
    checkpoint_action: "Pause for user review of eval_criteria.yaml"

  CHECKPOINT_RESEARCH:
    next: TEST_GEN | RESEARCH
    guards:
      - user_approval: "User must approve or request changes"
    actions:
      - if_approved: "Transition to TEST_GEN"
      - if_changes: "Apply edits, transition back to RESEARCH"

  TEST_GEN:
    next: OPTIMIZE | CHECKPOINT_TEST_GEN
    guards:
      - criteria_exists: "eval_criteria.yaml must exist"
    actions:
      - generate_tests: "cgf-test-architect → test_suite.yaml"
      - validate_tests: "cgf-test-validator → coverage_report.md"
      - update_run_state: "state=OPTIMIZE or CHECKPOINT_TEST_GEN"
    checkpoint_condition: "--review flag set"
    checkpoint_action: "Pause for user review of test_suite.yaml"

  CHECKPOINT_TEST_GEN:
    next: OPTIMIZE | TEST_GEN
    guards:
      - user_approval: "User must approve or request changes"
    actions:
      - if_approved: "Transition to OPTIMIZE"
      - if_changes: "Apply edits, transition back to TEST_GEN"

  OPTIMIZE:
    next: EVALUATE
    guards:
      - test_suite_valid: "test_suite.yaml must pass schema validation"
    actions:
      - run_optimization: "Execute existing CLI with current test suite"
      - collect_results: "{resource}-v{N}.md + summary.json"
      - update_run_state: "state=EVALUATE"
    # No checkpoint - optimization runs to completion

  EVALUATE:
    next: FINALIZE | CHECKPOINT_EVALUATE
    guards:
      - optimized_resource_exists: "{resource}-v{N}.md must exist"
      - summary_exists: "summary.json must exist"
    actions:
      - evaluate_result: "cgf-result-evaluator → review_report.md"
      - determine_recommendation: "ACCEPT | REFINE | REJECT"
      - update_run_state: "state=FINALIZE or CHECKPOINT_EVALUATE"
    checkpoint_condition: "--review flag set"
    checkpoint_action: "Pause for user review of recommendation"

  CHECKPOINT_EVALUATE:
    next: FINALIZE | RESEARCH
    guards:
      - user_decision: "User must confirm or override recommendation"
    actions:
      - if_accept: "Transition to FINALIZE with action=ACCEPT"
      - if_refine: "Transition to RESEARCH with refinement hints"
      - if_reject: "Transition to FINALIZE with action=REJECT"

  FINALIZE:
    next: COMPLETE
    guards:
      - action_determined: "Must have ACCEPT, REFINE, or REJECT action"
    actions:
      - if_accept: "Move optimized resource, archive original, generate changelog"
      - if_refine: "Adjust criteria, loop back to RESEARCH"
      - if_reject: "Keep original, archive attempt, generate failure report"
      - update_run_state: "state=COMPLETE"

  COMPLETE:
    terminal: true
    actions:
      - generate_final_report: "final_report.md"
      - cleanup: "Optional cleanup of intermediate artifacts"
```

#### Run State Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CGF Run State",
  "type": "object",
  "required": ["run_id", "state", "resource", "timestamps"],
  "properties": {
    "run_id": {
      "type": "string",
      "pattern": "^cgf-[a-f0-9]{8}$"
    },
    "state": {
      "type": "string",
      "enum": ["INIT", "RESEARCH", "CHECKPOINT_RESEARCH", "TEST_GEN",
               "CHECKPOINT_TEST_GEN", "OPTIMIZE", "EVALUATE",
               "CHECKPOINT_EVALUATE", "FINALIZE", "COMPLETE"]
    },
    "resource": {
      "type": "object",
      "required": ["id", "type", "path"],
      "properties": {
        "id": {"type": "string"},
        "type": {"type": "string", "enum": ["agent", "skill", "command",
                                             "mcp", "workflow", "spec", "hook", "plugin"]},
        "path": {"type": "string"},
        "optimization_goal": {"type": "string"}
      }
    },
    "strategy": {
      "type": "string",
      "enum": ["prompt_optimization", "trigger_optimization",
               "schema_optimization", "workflow_optimization"]
    },
    "artifacts": {
      "type": "object",
      "properties": {
        "run_config": {"type": "string"},
        "eval_criteria": {"type": "string"},
        "test_suite": {"type": "string"},
        "coverage_report": {"type": "string"},
        "optimized_resource": {"type": "string"},
        "summary": {"type": "string"},
        "review_report": {"type": "string"},
        "final_report": {"type": "string"}
      }
    },
    "timestamps": {
      "type": "object",
      "required": ["created"],
      "properties": {
        "created": {"type": "string", "format": "date-time"},
        "updated": {"type": "string", "format": "date-time"},
        "research_started": {"type": "string", "format": "date-time"},
        "research_completed": {"type": "string", "format": "date-time"},
        "test_gen_started": {"type": "string", "format": "date-time"},
        "test_gen_completed": {"type": "string", "format": "date-time"},
        "optimize_started": {"type": "string", "format": "date-time"},
        "optimize_completed": {"type": "string", "format": "date-time"},
        "evaluate_started": {"type": "string", "format": "date-time"},
        "evaluate_completed": {"type": "string", "format": "date-time"},
        "completed": {"type": "string", "format": "date-time"}
      }
    },
    "checkpoints": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "state": {"type": "string"},
          "timestamp": {"type": "string", "format": "date-time"},
          "user_action": {"type": "string", "enum": ["approved", "edited", "rejected"]},
          "notes": {"type": "string"}
        }
      }
    },
    "iterations": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "iteration": {"type": "integer"},
          "recommendation": {"type": "string", "enum": ["ACCEPT", "REFINE", "REJECT"]},
          "refinement_hints": {"type": "array", "items": {"type": "string"}},
          "scores": {
            "type": "object",
            "properties": {
              "original": {"type": "number"},
              "optimized": {"type": "number"},
              "improvement": {"type": "number"}
            }
          }
        }
      }
    },
    "error": {
      "type": "object",
      "properties": {
        "message": {"type": "string"},
        "state_at_error": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "recoverable": {"type": "boolean"}
      }
    }
  }
}
```

#### Agent Communication Protocol

All CGF agents communicate via file-based hand-offs in the workspace:

```
┌──────────────────────────────────────────────────────────────────┐
│                  AGENT COMMUNICATION FLOW                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  cgf-orchestrator                                                 │
│       │                                                           │
│       │ writes run_config.yaml, sets state=RESEARCH               │
│       ▼                                                           │
│  cgf-research-lead                                                │
│       │ reads: run_config.yaml                                    │
│       │ writes: research/notes/*.yaml (parallel researchers)      │
│       │                                                           │
│       │ spawns in parallel:                                       │
│       ├─────► research-specialist (Context7 focus)                │
│       │       writes: research/notes/context7_findings.yaml       │
│       │                                                           │
│       ├─────► research-specialist (WebSearch focus)               │
│       │       writes: research/notes/websearch_findings.yaml      │
│       │                                                           │
│       └─────► research-specialist (Codebase focus)                │
│               writes: research/notes/codebase_findings.yaml       │
│                                                                   │
│  cgf-criteria-synthesizer                                         │
│       │ reads: research/notes/*.yaml                              │
│       │ writes: research/eval_criteria.yaml                       │
│       │ notifies: orchestrator (state=TEST_GEN)                   │
│       ▼                                                           │
│  cgf-test-architect                                               │
│       │ reads: eval_criteria.yaml, resource definition            │
│       │ writes: tests/test_suite.yaml                             │
│       ▼                                                           │
│  cgf-test-validator                                               │
│       │ reads: test_suite.yaml, eval_criteria.yaml                │
│       │ writes: tests/coverage_report.md                          │
│       │ notifies: orchestrator (state=OPTIMIZE)                   │
│       ▼                                                           │
│  [optimization CLI - subprocess]                                  │
│       │ reads: resource, test_suite.yaml                          │
│       │ writes: {resource}-v{N}.md, summary.json                  │
│       │ notifies: orchestrator (state=EVALUATE)                   │
│       ▼                                                           │
│  cgf-result-evaluator                                             │
│       │ reads: original, optimized, criteria, summary             │
│       │ writes: reviews/v{N}_review.md                            │
│       │ notifies: orchestrator (recommendation + state)           │
│       ▼                                                           │
│  cgf-orchestrator                                                 │
│       │ reads: review recommendation                              │
│       │ executes: ACCEPT/REFINE/REJECT workflow                   │
│       │ writes: final_report.md, updates run_state.json           │
│       ▼                                                           │
│  COMPLETE                                                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

#### Orchestrator Agent Skeleton

```markdown
---
name: cgf-orchestrator
description: CGF pipeline orchestrator - coordinates research, test generation, optimization, and evaluation
model: sonnet
tools: Read, Write, Bash, Task, Glob, Grep
max_turns: 200
---

# CGF Orchestrator

You are the CGF (Claude Gradient Feedback) pipeline orchestrator. You coordinate the optimization of context-engineering resources through a multi-phase pipeline.

## Core Responsibilities

1. **Parse optimization requests** and extract resource + goal
2. **Manage pipeline state** via run_state.json
3. **Spawn and coordinate agents** for each pipeline phase
4. **Handle checkpoints** when --review mode is active
5. **Execute finalization** based on evaluation recommendation

## State Machine

You operate as a state machine. Always:
1. Read current state from run_state.json (or initialize if starting)
2. Determine valid next actions based on current state
3. Execute actions for current state
4. Update run_state.json with new state
5. Report progress to user

## Phase Execution

### INIT Phase
1. Parse request to extract: resource_path, optimization_goal
2. Create workspace: workspace/{resource_id}/
3. Load resource via: `python -c "from harness.optimization.resources import load_resource; ..."`
4. Detect resource type from loaded resource
5. Select optimization strategy from optimization_strategies.yaml
6. Write run_config.yaml
7. Initialize run_state.json with state=RESEARCH

### RESEARCH Phase
1. Spawn cgf-research-lead via Task tool
2. Wait for research completion (check for eval_criteria.yaml)
3. If --review: transition to CHECKPOINT_RESEARCH
4. Else: transition to TEST_GEN

### TEST_GEN Phase
1. Spawn cgf-test-architect via Task tool
2. Spawn cgf-test-validator for quality check
3. Wait for test_suite.yaml and coverage_report.md
4. If --review: transition to CHECKPOINT_TEST_GEN
5. Else: transition to OPTIMIZE

### OPTIMIZE Phase
1. Run optimization CLI via Bash:
   ```bash
   python -m harness.optimization.cli.optimize \
       --agent {resource_path} \
       --test-suite tests/test_suite.yaml \
       --optimizer dspy \
       --output {resource_id}-v{iteration}.md
   ```
2. Wait for completion
3. Transition to EVALUATE

### EVALUATE Phase
1. Spawn cgf-result-evaluator via Task tool
2. Wait for review_report.md with recommendation
3. If --review: transition to CHECKPOINT_EVALUATE
4. Else: transition to FINALIZE based on recommendation

### FINALIZE Phase
Based on recommendation:
- **ACCEPT**: Move optimized resource, archive original, generate changelog
- **REFINE**: Update criteria hints, loop back to RESEARCH
- **REJECT**: Keep original, archive attempt, generate failure report

## Error Handling

If any phase fails:
1. Log error to run_state.json.error
2. Determine if recoverable
3. If recoverable: retry with backoff
4. If not: transition to COMPLETE with failure status

## Communication Pattern

All inter-agent communication uses file-based hand-offs:
- Write outputs to designated paths in workspace
- Read inputs from designated paths
- Update run_state.json after each phase completion
```

#### Checkpoint Handling Detail

When `--review` is specified, the orchestrator must pause and wait for user input:

```python
# Pseudocode for checkpoint handling
async def handle_checkpoint(state: str, artifact_path: str) -> tuple[str, dict]:
    """
    Handle checkpoint by pausing for user review.

    Returns:
        tuple of (next_state, user_feedback)
    """
    # Update run_state to checkpoint state
    run_state["state"] = f"CHECKPOINT_{state}"
    write_run_state()

    # Report to user what's available for review
    print(f"\n[CHECKPOINT] {state} phase complete.")
    print(f"Review artifact: {artifact_path}")
    print("Options:")
    print("  /cgf proceed     - Accept and continue")
    print("  /cgf edit        - Make changes then continue")
    print("  /cgf abort       - Stop optimization")

    # Wait for user response via skill invocation
    # The /cgf skill handles user input and updates run_state

    # Resume when user provides input
    user_response = await wait_for_checkpoint_response()

    if user_response.action == "proceed":
        return (next_state_map[state], {})
    elif user_response.action == "edit":
        return (state, {"edits": user_response.edits})  # Re-run phase
    else:  # abort
        return ("COMPLETE", {"aborted": True})
```

### Resource-Specific Strategies

```yaml
# optimization_strategies.yaml

agent:
  optimizable_aspects:
    - system_prompt: "Main instruction text"
    - description: "Discovery description with examples"
    - tool_selection: "Which tools to grant"
  test_pattern: "user_prompt → expected_behavior"
  evaluation_focus:
    - task_completion_rate
    - output_quality
    - tool_usage_efficiency
  research_sources:
    primary: context7  # Domain documentation
    secondary: websearch  # Best practices
    optional: codebase  # Current implementation

skill:
  optimizable_aspects:
    - trigger_keywords: "Activation terms"
    - instructions: "Core skill content"
    - examples: "Usage examples"
  test_pattern: "trigger_phrase → activation_reliability"
  evaluation_focus:
    - activation_precision
    - false_positive_rate
    - instruction_clarity
  research_sources:
    primary: context7  # Related library docs
    secondary: websearch  # UX patterns

command:
  optimizable_aspects:
    - help_text: "Usage documentation"
    - argument_handling: "Parameter processing"
    - output_format: "Response structure"
  test_pattern: "cli_invocation → expected_output"
  evaluation_focus:
    - usability_score
    - error_message_clarity
    - completion_rate
  research_sources:
    primary: websearch  # CLI UX best practices
    secondary: context7  # Library CLIs for reference

workflow:
  optimizable_aspects:
    - step_definitions: "Phase descriptions"
    - hand_off_logic: "Agent coordination"
    - error_handling: "Failure recovery"
  test_pattern: "workflow_trigger → successful_completion"
  evaluation_focus:
    - end_to_end_success_rate
    - step_transition_reliability
    - error_recovery_effectiveness
  research_sources:
    primary: context7  # Orchestration patterns
    secondary: websearch  # Workflow best practices

mcp_tool:
  optimizable_aspects:
    - description: "Tool purpose and usage"
    - parameter_schemas: "Input definitions"
    - response_format: "Output structure"
  test_pattern: "tool_call → expected_response"
  evaluation_focus:
    - invocation_success_rate
    - response_usefulness
    - error_clarity
  research_sources:
    primary: context7  # MCP protocol docs
    secondary: codebase  # Current implementation

hook:
  optimizable_aspects:
    - trigger_conditions: "When to fire"
    - matcher_patterns: "What to match"
    - action_commands: "What to execute"
  test_pattern: "event_trigger → action_execution"
  evaluation_focus:
    - trigger_reliability
    - action_success_rate
    - false_trigger_rate
  research_sources:
    primary: codebase  # Existing hook patterns
    secondary: websearch  # Automation best practices
```


## Implementation Plan

### Milestone 0: Research-Team Enhancement (Pre-requisite)

**Duration**: 1 week

**Deliverables**:

1. **Context7 Integration**
   - [x] Add Context7 tools to research-specialist
   - [x] Implement source router logic
   - [x] Add library detection heuristics

2. **CGF Output Mode**
   - [x] Define structured findings schema (YAML)
   - [x] Add output_mode parameter to research-specialist
   - [x] Create findings-to-criteria transformation

3. **Testing**
   - [x] Test source routing with various topics
   - [x] Validate Context7 queries for common libraries
   - [x] Verify structured output format


### Milestone 1: CGF Orchestrator

**Duration**: 1-2 weeks

**Deliverables**:

1. **cgf-orchestrator Agent**
   - [x] State machine implementation
   - [x] Resource type detection
   - [x] Strategy selection logic
   - [x] Checkpoint handling (--review mode)

2. **Run State Management**
   - [x] run_state.json schema
   - [x] State persistence/resume
   - [x] Artifact tracking

3. **CLI Integration**
   - [x] `/cgf-optimize` skill
   - [x] Makefile targets
   - [x] Progress reporting


### Milestone 2: Research Phase

**Duration**: 1 week

**Deliverables**:

1. **cgf-research-lead Agent**
   - [x] Fork from lead-research-coordinator
   - [x] CGF-specific subtopic decomposition
   - [x] Source routing guidance for specialists

2. **cgf-criteria-synthesizer Agent**
   - [x] Research findings aggregation
   - [x] eval_criteria.yaml generation
   - [x] Coverage validation

3. **Templates**
   - [x] eval_criteria.yaml template
   - [x] Per-resource-type criteria templates


### Milestone 3: Test Generation Phase

**Duration**: 1-2 weeks

**Deliverables**:

1. **cgf-test-architect Agent**
   - [x] Criteria-to-tests transformation
   - [x] Resource-type-specific test patterns
   - [x] Validation rule selection logic

2. **cgf-test-validator Agent**
   - [x] Schema compliance checking
   - [x] Coverage analysis
   - [x] Quality metrics

3. **Test Suite Templates**
   - [x] Per-resource-type test templates
   - [x] Validation rule examples


### Milestone 4: Evaluation Phase

**Duration**: 1 week

**Deliverables**:

1. **cgf-result-evaluator Agent**
   - [x] Multi-dimensional evaluation
   - [x] Recommendation logic
   - [x] REFINE guidance generation

2. **Review Report Template**
   - [x] Structured report format
   - [x] Visualization of improvements/regressions

3. **Finalization Logic**
   - [x] ACCEPT workflow
   - [x] REFINE loop implementation
   - [x] REJECT archival


### Milestone 5: Integration & Polish

**Duration**: 1 week

**Deliverables**:

1. **End-to-End Testing**
   - [ ] Test with agent optimization
   - [ ] Test with skill optimization
   - [ ] Test with command optimization
   - [ ] Test with workflow optimization

2. **Documentation**
   - [ ] User guide
   - [ ] API documentation
   - [ ] Example workflows

3. **Performance Optimization**
   - [ ] Parallel execution tuning
   - [ ] Token usage optimization
   - [ ] Caching for repeated runs


## CGF 3.0 Preview: Multi-Resource Composition

CGF 3.0 extends beyond single-resource optimization to optimize **combinations of resources** for complex outcomes.

### Use Cases

```
# Example 1: Optimize a complete workflow
"Optimize the code-review system (agents + skills + workflow)"

CGF 3.0 would:
- Analyze how agents, skills, and workflow interact
- Optimize each component in context of the whole
- Test the complete system, not just parts

# Example 2: Create optimal resource combination
"Create the best setup for API development"

CGF 3.0 would:
- Determine which resources are needed (agents, skills, commands)
- Generate or select optimal components
- Test the combination as a system

# Example 3: Cross-optimize for specific outcome
"Maximize deployment success rate across all deployment-related resources"

CGF 3.0 would:
- Identify all resources that affect deployments
- Optimize them collectively with shared objective
- Measure and improve system-level metrics
```

### Architecture Preview

```
CGF 3.0 Components:

1. SYSTEM ANALYZER
   - Map resource dependencies
   - Identify interaction patterns
   - Find optimization opportunities

2. COMPOSITION OPTIMIZER
   - Multi-resource test suites
   - System-level evaluation metrics
   - Cross-resource trade-off analysis

3. SYNTHESIS ENGINE
   - Generate new resources to fill gaps
   - Recommend resource combinations
   - Create optimal configurations
```


## Success Metrics

### CGF 2.0 Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **End-to-end success rate** | >80% | Optimization runs that produce accepted result |
| **Time to optimize** | <15 min | From request to accepted result |
| **Test generation quality** | >90% coverage | Criteria coverage in generated tests |
| **Evaluation accuracy** | >85% | Agreement with human evaluation |
| **Token efficiency** | <100K per run | Total tokens used in pipeline |


## Workspace Structure

```
workspace/
└── python-expert/                    # Resource workspace
    ├── run_state.json                # Current state for resume
    ├── run_config.yaml               # Optimization configuration
    │
    ├── research/
    │   ├── notes/
    │   │   ├── context7_findings.yaml
    │   │   ├── websearch_findings.yaml
    │   │   └── codebase_findings.yaml
    │   └── eval_criteria.yaml        # Synthesized criteria
    │
    ├── tests/
    │   ├── test_suite.yaml           # Generated tests
    │   └── coverage_report.md        # Coverage analysis
    │
    ├── python-expert-orig.md         # Preserved original
    ├── python-expert-v1.md           # Optimized version 1
    ├── python-expert-v1.summary.json # Quantitative results
    │
    └── reviews/
        └── v1_review.md              # Evaluation report
```


## Plugin Structure

```
cgf-agents/
├── .claude-plugin/
│   └── plugin.json
├── README.md
│
├── agents/
│   ├── cgf-orchestrator.md           # Main coordinator (state machine)
│   ├── cgf-research-lead.md          # Research phase coordinator
│   ├── cgf-criteria-synthesizer.md   # Research → criteria
│   ├── cgf-test-architect.md         # Criteria → tests
│   ├── cgf-test-validator.md         # Test suite validation
│   └── cgf-result-evaluator.md       # Results evaluation
│
├── skills/
│   ├── cgf-optimize/                 # /cgf-optimize
│   │   └── SKILL.md
│   └── cgf-status/                   # /cgf-status (check run state)
│       └── SKILL.md
│
├── templates/
│   ├── run_config.yaml               # Run configuration template
│   ├── eval_criteria.yaml            # Criteria output template
│   ├── test_suite.yaml               # Test suite template
│   └── review_report.md              # Review template
│
├── schemas/
│   ├── run_state.schema.json         # State validation
│   ├── eval_criteria.schema.json     # Criteria validation
│   └── test_suite.schema.json        # Test suite validation
│
└── patterns/
    └── cgf-optimization-workflow.md  # Documentation
```


## Timeline Summary

| Phase | Duration | Key Deliverable | Status |
|-------|----------|-----------------|--------|
| **M0: Research Enhancement** | 1 week | Context7 in research-team, CGF output mode | ✅ |
| **M1: Orchestrator** | 1-2 weeks | State machine, resource detection, CLI | ✅ |
| **M2: Research Phase** | 1 week | Research agents, criteria synthesis | ✅ |
| **M3: Test Generation** | 1-2 weeks | Test generation, validation | ✅ |
| **M4: Evaluation** | 1 week | Result evaluation, recommendation | ✅ |
| **M5: Integration** | 1 week | E2E testing, documentation | ⏳ |
| **Total** | 6-8 weeks | Full CGF 2.0 pipeline | |


## Next Steps

1. **M5: Integration & Polish**: End-to-end testing, documentation, performance optimization
2. **Testing**: Run full pipeline with agent, skill, command resource types
3. **Documentation**: Complete user guide and example workflows
4. **Performance**: Token usage optimization and caching for repeated runs

---

**Author**: Andis A. Blukis
**Created**: 2025-01-14
**Last Updated**: 2025-01-15
**Status**: M0-M4 Complete, M5 Pending
