# src/harness/ — Harness Package

The Python package that wraps the Claude Agent SDK and implements the
harness's three execution modes (`interactive`, `autonomous`, CGF
`optimize`), agent orchestration, MCP server hosting, and Prometheus
instrumentation.

The architecture diagram, module map, and execution-mode comparison
live in the project-root `CLAUDE.md` (sections "Core Harness" through
"CGF Optimization Framework"). Re-read that before editing across
modules.

## Observability quick-pointer

Whenever you touch metric emission — adding instruments, changing call
sites, debugging "why is the dashboard empty" — open
**`docs/OBSERVABILITY.md`** first. It explains:

- Both metric pipelines (harness/prom_client vs SDK→OTLP→collector) and
  how they fail differently (§ 2)
- Every metric the harness can emit, with definition site + emitters
  + Grafana consumers (§ 3)
- 13 alert rules and what they fire on (§ 5)
- Singleton-helper semantics — `record_run_*` and `init_run_phases`
  all `.clear()` prior series; gauges represent the **currently active**
  run, not a history (§ 6 + § 7)
- Live runtime-verification command for confirming new emits actually
  reach Prometheus (§ 8)
- Stage 3 follow-ups: Loki + Tempo (§ 9) — deferred indefinitely

The dashboard JSON, alert rules, and OTel collector config live under
`config/monitoring/` (which has its own CLAUDE.md). Wiring changes
typically span both directories.

## Common observability touchpoints in this package

| File | What it emits | Notes |
|---|---|---|
| `monitoring.py` | All harness-side instruments + helpers (`record_run_*`, `init_run_phases`, `record_task_progress`, etc.) | Singleton helpers call `.clear()` before set. Add unit tests in `tests/unit/test_monitoring.py` whenever you change. |
| `agent.py` | `harness_agent_requests_total`, `harness_agent_duration_seconds`, `harness_agent_active_sessions` via `MetricsCollector` methods. Also pins `HOME=/home/claude` and `PYTHONUNBUFFERED=1` on SDK subprocess env. | Bind-mounted in dev compose; restart picks up changes. |
| `interactive.py` | `harness_session_*` family, `harness_tool_calls_total`, `harness_message_types_total`. | Only emits during `make interactive` — D5 dashboard. |
| `progress.py` | `harness_task_progress{status}` on every `save_task_list` (autonomous mode). | Powers D6. |
| `cgf_session.py` | Single-resource CGF path: `record_run_config / record_run_path / record_run_start / init_run_phases / record_phase_entry / record_iteration`. | Emits 5 phases: research, optimize, finalize, complete, failed. See `SINGLE_PATH_PHASES` in monitoring.py. |
| `optimization/multi_resource_orchestrator.py` + `_orchestrator_phases/` | Multi-resource CGF path: same setup as single + per-resource iteration in `iterate.py:185`. | Emits 10 phases. See `MULTI_PATH_PHASES`. |
| `optimization/_orchestrator_phases/eval_design.py` + `execution_eval.py` + `optimization/graders/llm_judge.py` | `harness_eval_*` family (Phase A telemetry). | D7 Eval Framework collapsed row. |

## Rules of thumb when editing

1. **Adding a new metric** — define in `monitoring.py`, add a helper if cardinality control is needed, add a call site, add a unit test, add a row to `docs/OBSERVABILITY.md` § 3, and if you want it on a dashboard, add a panel in `config/monitoring/dashboards/` and a row to § 4.
2. **Adding a new phase name** to either path's state machine — update `SINGLE_PATH_PHASES` or `MULTI_PATH_PHASES` in `monitoring.py` (the union is auto-derived as `KNOWN_RUN_PHASES`). Then update the two State Timeline regex filters in `config/monitoring/dashboards/70-mode-cgf.json`. Without both, D7 won't show the new phase.
3. **Changing a singleton helper** — `.clear()`-on-set semantic is load-bearing for D0/D7 Run Config table dedup. Regression tests are in `tests/unit/test_monitoring.py::test_singleton_semantic_*`.
4. **Operations that never raise** — observability helpers wrap their body in `try/except`. `# pragma: no cover` on the except branch. Observability code never breaks the pipeline.

## When you're working in a sub-package

- `optimization/` — CGF orchestration code. Specific to the optimize path.
- `tracer/` — OTel tracer instrumentation (for the deferred Stage 3 traces pipeline). Distinct from the Prom metrics in `monitoring.py`.
- `optimization/graders/` — Eval grader implementations (deterministic / LLM-judge / trajectory).
- `plugins/`, `agents/configs/` — agent definitions, not observability.
