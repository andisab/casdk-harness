# tests/ — Test Suite

Auto-loaded when editing tests. For per-module test conventions inside
`src/harness/`, see that package's own `CLAUDE.md`. For smoke-fixture
mechanics specifically, see `tests/smoke/README.md`.

## Quick orientation

```
tests/
├── conftest.py            # session-wide fixtures + markers
├── test_nested_agent.py   # NOT a pytest test — standalone SDK-workaround verifier
├── unit/                  # ~1700 fast tests, no API/Docker, run on every change
├── integration/           # API + Docker + Redis dependent
├── e2e/                   # full-workflow tests (real LLM calls, expensive)
├── smoke/                 # end-to-end optimization fixtures (real LLM, ~$0.50–$8/run)
├── fixtures/              # shared test data (currently empty)
└── optimization/examples/ # legacy YAML test suites used by older CGF code
```

Latest counts (as of 2026-05-08 Phase A close):
**1702 unit + 16 integration passing**.

## How to run

```bash
make test              # full suite
make test-unit         # tests/unit/ only — fast, no API
make test-integration  # tests/integration/ — needs ANTHROPIC_API_KEY + Docker
make test-multi        # multi-agent Redis-coordination subset
make coverage          # HTML coverage report
make smoke FIXTURE=python-expert | iac-team   # real-LLM end-to-end
```

All test targets run inside the `main-agent` container via `docker
compose exec`. There is no host-side venv — tests must run in the
container so plugin paths, MCP server scripts, and env vars are correct.

Single-file or `-k` selection from the host:

```bash
docker compose exec main-agent pytest tests/unit/test_monitoring.py -xvs
docker compose exec main-agent pytest tests/unit/ -k "phase_progression" -xvs
```

`-x` stops on first failure; `-s` disables output capture (needed to
see prints / logs while iterating).

## Layers

### `unit/` — pure, fast, hermetic

No API calls, no Docker, no Redis, no network. Should run in seconds
each. Mocks live where needed (`monkeypatch`, `MagicMock`, fake
spans). Coverage target for `src/harness/` lives here.

The 24 top-level files cluster by component:

| Area | Files |
|---|---|
| AgentSession + SDK wrapper | `test_agent_init.py`, `test_agent_conversation.py`, `test_agent_definitions.py`, `test_agent_progress.py` |
| Modes | `test_autonomous.py`, `test_workspace_state.py`, `test_cgf_session.py` |
| Plugin system | `test_plugin_manager.py`, `test_plugin_loading.py`, `test_plugin_agent_loading.py` |
| Subagent (call_agent) | `test_subagent.py` |
| MCP servers | `test_mcp_loader.py`, `test_mcp_context7.py`, `test_mcp_memory.py` |
| Messaging (Redis Streams) | `test_messaging.py` |
| Checkpointing | `test_checkpoint.py` |
| Progress / task list | `test_progress.py` |
| Monitoring / Prometheus | `test_monitoring.py` |
| CLI rendering | `test_cli.py` |
| Health endpoint | `test_health.py` |
| Config | `test_config.py` |
| Security | `test_security.py`, `test_sanitization.py` |
| Multi-resource orchestrator | `test_multi_resource_orchestrator.py` |

Two large subdirectories under `unit/`:

- **`test_optimization/`** — ~37 files covering the CGF package
  (`src/harness/optimization/`). Includes Phase A surfaces:
  `test_eval_harness.py`, `test_eval_suite_schema.py`,
  `test_eval_telemetry.py`, `test_eval_tracer_spans.py`,
  `test_graders.py`, `test_orchestrator_eval_design_phase.py`,
  `test_orchestrator_execution_eval.py`,
  `test_orchestrator_concurrency.py`. The `test_f7_f8_f9_fixes.py`,
  `test_f10_*` … `test_f15_*` files are the F-series Phase-A-fixes
  regression coverage; one per defect.
- **`test_tracer/`** — OTel tracer (`src/harness/tracer/`):
  `test_otel_tracer.py`, `test_span.py`, `test_context.py`,
  `test_exporters.py`, `test_store_exporter.py`,
  `test_instrumentation.py`.

### `integration/` — real dependencies, focused

23 files. Marked `@pytest.mark.integration`. Need:

- `ANTHROPIC_API_KEY` — auto-skip if unset (see `conftest.py:152`).
- Docker daemon running (for `test_mcp_docker.py`).
- Redis up via `make up-multi` (for `test_multi_agent.py`,
  `test_messaging.py` integration paths).

Coverage by area:

| Area | Files |
|---|---|
| SDK behavior | `test_sdk_initialization.py`, `test_sdk_query_patterns.py`, `test_sdk_plugin_awareness.py`, `test_signal_handling.py` |
| CLI / container | `test_cli_binary.py`, `test_container_buffering.py` |
| Plugins (live SDK) | `test_plugin_discovery.py`, `test_plugin_loading.py`, `test_plugin_agents.py`, `test_harness_plugin_agents.py`, `test_plugin_cli_args.py`, `test_plugin_direct_cli.py`, `test_no_sdk_autodiscovery.py` |
| Skills | `test_skills.py` |
| MCP (live) | `test_mcp_docker.py`, `test_mcp_tier1_tier2_loading.py` |
| CGF pipeline | `test_cgf_pipeline.py`, `test_design_phase_integration.py`, `test_full_pipeline_integration.py` |
| Conversation | `test_conversation_memory.py` |
| Multi-agent | `test_multi_agent.py` |
| Direct SDK | `test_agent_sdk_direct.py` |

`test_full_pipeline_integration.py` is the **Phase A E2E with mocked
SDK calls** — exercises all 9 phases without real LLM cost. Use this
when you need to validate the orchestrator wiring end-to-end without
spending tokens.

### `e2e/` — full-workflow, expensive

Real LLM calls against the full harness. Five files total:

- `test_simple_feature.py` (top level) — autonomous-mode feature
  development workflow.
- `cgf/test_agent_optimization.py`, `test_skill_optimization.py`,
  `test_command_optimization.py`, `test_workflow_optimization.py` —
  per-resource-type CGF optimization end-to-end.

`tests/e2e/cgf/conftest.py` provides shared CGF E2E fixtures
(`MockOptimizationResult`, isolated workspace setup, optimizer mocking
helpers).

Marked `@pytest.mark.e2e`. **Don't run as part of normal iteration** —
costly. Reach for these when validating a release candidate or
investigating a regression that smoke tests can't pin down.

### `smoke/` — production-shape end-to-end optimization

Real-LLM optimization runs against curated workspaces. Two fixtures
today, room for ~6 in the plan. **Not pytest** — invoked via
`make smoke FIXTURE=<name>`. The runner copies `tests/smoke/<name>/`
into `workspace/<name>/`, runs the orchestrator, and reports pass/fail
based on artifact + telemetry presence.

Full details in `tests/smoke/README.md`. Worth reading before adding a
new fixture — covers PASS criteria, cost expectations, and the
smoke → research → refine loop these are designed for.

| Fixture | Type | Cost (sonnet+opus) |
|---|---|---|
| `python-expert/` | single-resource agent | $0.50–$2 |
| `iac-team/` | multi-resource plugin (3 agents + 1 command + 17 skills) | $3–$8 |

## Markers

Configured in `pyproject.toml::[tool.pytest.ini_options].markers` and
reinforced in `conftest.py::pytest_configure`:

| Marker | Meaning | Auto-skip behavior |
|---|---|---|
| `integration` | Real API + container deps | `make test-integration` selects |
| `e2e` | Full LLM workflow | Manual select only |
| `smoke` | Smoke run | Manual select; mostly `make smoke` instead |
| `slow` | >30 s wall time | `-m "not slow"` to skip |
| `requires_api_key` | Needs `ANTHROPIC_API_KEY` | Auto-skipped if unset |
| `docker` | Needs Docker daemon | Manual select |
| `redis` | Needs Redis up | Use after `make up-multi` |

`asyncio_mode = "auto"` — every `async def test_*` is automatically
treated as an asyncio test. No `@pytest.mark.asyncio` needed.

`timeout = 300` — 5-minute hard cap per test. Override per-test with
`@pytest.mark.timeout(N)` when needed (real-API tests sometimes legit).

## Shared fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `api_key` | function | Reads `ANTHROPIC_API_KEY` env var, returns None if absent |
| `workspace_dir` | function | Temp dir via `tempfile.TemporaryDirectory`, auto-cleaned |
| `token_budget` | session | 1M-token tracker (cross-test) |
| `skip_if_no_api_key` | function | `pytest.skip()` if no key |
| `check_token_budget` | function | `pytest.fail()` if budget exceeded |
| `_reset_run_phase_gauges` | function, autouse | Clears `harness_run_phase_info` + `harness_run_iteration` Prometheus gauges between tests so fixture names don't leak onto the live Grafana dashboard |

The autouse gauge-reset is **load-bearing**: pytest runs inside the
`main-agent` container whose Prometheus endpoint is live. Without it,
test resource names show up on the "Active Resource" panel.

## Conventions

- **One concept per file.** When `test_<module>.py` grows past ~600
  lines, split by sub-concern (e.g., `test_monitoring_singletons.py`
  alongside `test_monitoring.py`).
- **Mock at SDK boundary**, not internal harness boundary. Tests for
  multi-resource orchestrator mock `call_agent_simple` returns; they
  don't mock `_orchestrator_phases.research.execute` etc.
- **Real schemas, not strings.** Tests that validate eval-suite shape
  load `eval_suite.schema.json` via the real loader, not a hand-rolled
  comparator.
- **Phase A F-series regressions** — every numbered defect from the
  Phase A smoke runs has a `test_fNN_*.py` under `test_optimization/`.
  If you fix a smoke-surfaced defect, the pattern is: write a unit test
  named for the defect number first, then ship the fix.
- **No new top-level pytest discoverable files** under `tests/` itself.
  `test_nested_agent.py` is a historical odd duck (a script, not a
  pytest test); don't add more.

## Coverage policy

`make coverage` produces `htmlcov/index.html`. The project's stated
goal in user-global standards is 80%+. Current coverage focuses on
`src/harness/optimization/` and `src/harness/monitoring.py` (Phase A
shipped with thorough unit tests). The interactive/autonomous-mode
paths and MCP servers have lighter coverage — known gap.

When adding code under `src/harness/optimization/`, add the unit test
in the same PR. The Phase A track was strict about this and it kept
the F-series fix loop tractable.

## Where to add a new test

Mental flow:

1. Pure function, no I/O? → `tests/unit/<area>/`
2. Uses SDK, MCP, or Docker? → `tests/integration/`
3. Needs real LLM but is short and focused? → `tests/integration/` with
   `@pytest.mark.requires_api_key` (auto-skips in CI without key).
4. End-to-end multi-phase workflow with real LLM? → `tests/e2e/`
5. Full optimization run with curated workspace? → new fixture under
   `tests/smoke/` + entry in `tests/smoke/README.md`.

When in doubt, default to unit. Cheap to run = cheap to keep green.

## Pre-commit signal

```bash
make lint && make typecheck && make test-unit
```

These three should pass before pushing. `make test-integration` is
not required pre-push (cost + flakiness), but is required for any PR
touching `src/harness/optimization/`, the SDK wrapper in `agent.py`,
or `plugin_manager.py`.
