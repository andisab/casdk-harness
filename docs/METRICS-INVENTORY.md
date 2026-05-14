# Metrics Inventory — Emission Audit (G0)

**Companion to:** [GRAFANA-REFACTOR.md](./GRAFANA-REFACTOR.md) § 7.2 G0.

**Purpose:** Every Prometheus metric the harness can emit, mapped to its
definition site, the code paths that fire it, the pipeline that carries it,
the Grafana panels that consume it, and a status flag identifying dead /
stranded / gap rows. Re-run after any monitoring-touching PR.

**Last source audit:** 2026-05-14 (commits up to `ef8684a` on
`grafana-refactor` plus Phase 1 working-tree changes).

**Live runtime verification:** **PERFORMED 2026-05-14 against `grafana-refactor` @ 7985288.** See § 5 for the captured baseline and § 6 for findings updated from runtime data. Re-run after any SDK bump or monitoring-touching PR.

---

## 1. Pipelines

| Pipeline | Defined in | Sent to | Defect modes |
|---|---|---|---|
| **harness/prom_client** | `prometheus_client` instruments in `src/harness/monitoring.py` | Per-agent HTTP `:9090` endpoint, scraped by Prometheus via the `main-agent` / `agent-two` / `agent-three` jobs in `config/monitoring/prometheus.yml` | (a) instrument defined but no call site; (b) call site exists but only fires on a path the run never takes; (c) agent container's `/metrics` endpoint isn't being scraped |
| **SDK→OTLP→collector** | Claude Code CLI internals | OTLP → `otel-collector:4317` → Prom exporter `:8889`, scraped by `otel-collector-sdk` job | (a) env var missing (`OTEL_LOGS_EXPORTER`, `CLAUDE_CODE_ENABLE_TELEMETRY`); (b) attribute-derived label not propagated through collector; (c) metric name mismatch (dot-notation vs snake_case) |

---

## 2. Inventory

Columns:

- **Metric name** — Prometheus name as exposed on `/metrics`.
- **Type** — Counter / Gauge / Histogram.
- **Defined at** — `src/harness/monitoring.py:LINE`.
- **Emitted from** — production call sites (paths that fire during a real run, not the unit test path).
- **Consumed by** — current `cgf.json` / `overview.json` panels, plus targeted spec panels under `GRAFANA-REFACTOR.md`.
- **Status** — `LIVE` (defined + emitted + consumed), `STRANDED` (defined + emitted but no panel consumes), `DEAD` (defined but never emitted), `GAP` (emitted on one path only — partial coverage), `PENDING` (Phase 1 instrument, awaiting live verification).

### 2.1 Harness — operational

| Metric name | Type | Defined at | Emitted from | Consumed by | Status |
|---|---|---|---|---|---|
| `harness_agent_requests_total` | Counter | `monitoring.py:113` | `agent.py:756, 776, 804` via `MetricsCollector.record_request` | spec D50 (API error proxy); overview.json (verify) | LIVE |
| `harness_agent_duration_seconds` | Histogram | `monitoring.py:119` | `agent.py:777` via `record_duration` | spec D50 (P50/P95), D65 (Agent Execution heat map) | LIVE |
| `harness_agent_active_sessions` | Gauge | `monitoring.py:125` | `agent.py:660, 1485` via `set_active_sessions` | spec D00 (`$mode` discriminator) | LIVE |
| `harness_checkpoint_size_bytes` | Gauge | `monitoring.py:131` | `monitoring.py:621` (internal `collect_system_metrics` loop) | overview.json (verify); no spec panel | STRANDED — emitted but no spec panel; verify overview.json consumer |
| `harness_workspace_files_total` | Gauge | `monitoring.py:136` | `monitoring.py:613` (internal `collect_system_metrics` loop) | overview.json (verify); no spec panel | STRANDED — same |
| `harness_memory_usage_bytes` | Gauge | `monitoring.py:141` | nowhere | nowhere | **DEAD** — no `set_memory_usage` call site outside `monitoring.py` |

### 2.2 Harness — interactive-mode session

| Metric name | Type | Defined at | Emitted from | Consumed by | Status |
|---|---|---|---|---|---|
| `harness_session_prompts_total` | Counter | `monitoring.py:150` | `interactive.py:198` via `record_user_prompt` | spec D60 (Session Header, Conversation Flow), D00 mode summary | LIVE |
| `harness_session_responses_total` | Counter | `monitoring.py:156` | `interactive.py:222` via `record_agent_response` | spec D60 (Session Header, Conversation Flow) | LIVE |
| `harness_session_duration_seconds` | Histogram | `monitoring.py:162` | `interactive.py:325` via `record_interactive_session_duration` | spec D60 (Session Header) | LIVE |
| `harness_tool_calls_total` | Counter | `monitoring.py:169` | `interactive.py:227` via `record_tool_call` | spec D60 (Tool Usage), D00 mode summary | LIVE |
| `harness_message_types_total` | Counter | `monitoring.py:175` | `interactive.py:230, 234, 236` via `record_message_type` | spec D60 (Message Types) | LIVE |

### 2.3 CGF tracer / optimization quality

| Metric name | Type | Defined at | Emitted from | Consumed by | Status |
|---|---|---|---|---|---|
| `cgf_spans_collected_total` | Counter | `monitoring.py:182` | nowhere | cgf.json panel "Spans Collected" | **DEAD** — no `record_span_collected` call site; cgf.json panel renders empty |
| `cgf_spans_exported_total` | Counter | `monitoring.py:188` | nowhere | cgf.json panel "Spans Exported" | **DEAD** |
| `cgf_adapter_transforms_total` | Counter | `monitoring.py:194` | nowhere | cgf.json panel "Adapter Transform Success Rate" | **DEAD** |
| `cgf_reward_composite` | Histogram | `monitoring.py:200` | nowhere | cgf.json panel "Mean Composite Reward" | **DEAD** |
| `cgf_feedback_dimensions` | Gauge | `monitoring.py:207` | nowhere | cgf.json (referenced in P5 Row 3 of spec D70) | **DEAD** |

**Note:** the wrapper methods `MetricsCollector.record_span_collected`, `record_span_exported`, `record_adapter_transform`, `record_reward`, `set_feedback_dimension` are all defined but have zero external callers. Tracer instrumentation in `src/harness/tracer/` does its own OTel span emission; it never crosses over into these prometheus_client counters. Likely disconnected during the Block 4 / Phase 3B refactor.

### 2.4 Eval framework (Phase A telemetry)

| Metric name | Type | Defined at | Emitted from | Consumed by | Status |
|---|---|---|---|---|---|
| `harness_eval_phase_duration_seconds` | Histogram | `monitoring.py:257` | `eval_design.py:212, 229`; `execution_eval.py:124` | cgf.json "Eval Framework" row | LIVE |
| `harness_eval_tokens_to_goal` | Histogram | `monitoring.py:228` | `execution_eval.py:449` | cgf.json "Tokens to Goal" panel | LIVE |
| `harness_eval_scenarios_total` | Counter | `monitoring.py:244` | `execution_eval.py:678` | cgf.json "Scenarios by Outcome" panel | LIVE |
| `harness_eval_arm_score` | Histogram | `monitoring.py:250` | `execution_eval.py:681` | cgf.json "Per-Arm Score" panel | LIVE |
| `harness_eval_judge_no_decision_total` | Counter | `monitoring.py:264` | `graders/llm_judge.py:195` | cgf.json "Judge No-Decision" panel | LIVE |

### 2.5 Run-level status (powers Active Run Status row + spec D70)

| Metric name | Type | Defined at | Emitted from | Consumed by | Status |
|---|---|---|---|---|---|
| `harness_run_phase_info` | Gauge | `monitoring.py:275` | `cgf_session.py` × 12 sites (`record_phase_entry`); `multi_resource_orchestrator.py:426, 523` | cgf.json "Phase Progression" bargauge; spec D70 State Timeline (P1) | LIVE |
| `harness_run_iteration` | Gauge | `monitoring.py:284` | `cgf_session.py:1776, 2138` (single path) | cgf.json "Iteration" stat; spec D70 R1 panel 2 | **GAP** — multi-resource orchestrator never calls `record_iteration`; D70 Iteration panel will show "—" on multi runs |
| `harness_run_path_info` | Gauge | `monitoring.py:290` | `cgf_session.py:1773`; `multi_resource_orchestrator.py:424` | spec D70 `$path` variable | LIVE |
| `harness_run_config_info` | Gauge | `monitoring.py:389` | `cgf_session.py:1778`; `multi_resource_orchestrator.py:436` (Phase 1) | spec D00 Row 0 Run Config table; spec D70 Row 0 | LIVE — runtime-verified 2026-05-14, all 8 labels (resource/path/mode/model/effort/eval_enabled/token_budget/max_iterations) propagate correctly |
| `harness_run_start_timestamp` | Gauge | `monitoring.py:409` | `cgf_session.py:1777`; `multi_resource_orchestrator.py:427` (Phase 1) | spec D00 / D70 "Run Elapsed" stat | LIVE — runtime-verified 2026-05-14 |
| `harness_task_progress` | Gauge | `monitoring.py:420` | `progress.py:426` via `record_task_progress` (Phase 1) | spec D65 Task Progress Header | LIVE — runtime-verified 2026-05-14, all 3 statuses (completed/failed/pending) propagate correctly |

### 2.6 SDK-native (claude_code_*)

Source: Claude Code CLI; we only verify arrival. Names below are the Prometheus form after collector promotion (dot → underscore).

**Runtime verification 2026-05-14:** 7 of 8 SDK metrics present in live Prometheus (caveats inline). **Two metric-name + label corrections to the upstream spec discovered during verification — see § 6.**

| Metric name | Type | Pipeline | Consumed by | Status |
|---|---|---|---|---|
| `claude_code_session_count_total` | Counter | SDK→OTLP→collector | spec D20 sessions panel; D00 mode summary | LIVE — `start_type` label confirmed |
| `claude_code_lines_of_code_count_total` | Counter | SDK→OTLP→collector | spec D20, D65 (LoC sparkline) | LIVE — `type=added` and `type=removed` both observed in 24h |
| `claude_code_pull_request_count_total` | Counter | SDK→OTLP→collector | spec D10 (Cost per PR) | EXPECTED ABSENT — no Claude-opened PRs in 24h; only fires when Claude calls `gh` in-session |
| `claude_code_commit_count_total` | Counter | SDK→OTLP→collector | spec D10 (Cost per commit), D65 | EXPECTED ABSENT — no commit by Claude in 24h. Likely fires only on interactive sessions; CGF optimization runs don't commit. Panel will render empty until that workflow is exercised. |
| `claude_code_cost_usage_USD_total` | Counter | SDK→OTLP→collector | spec D00, D10 (all spend panels), D70 (Economics row) | LIVE — labels confirmed: `model`, `query_source` (subagent), `effort` (high/xhigh), `agent_name` (Explore/custom), `plugin_name`, `terminal_type` |
| `claude_code_token_usage_tokens_total` | Counter | SDK→OTLP→collector | spec D00 (cache hit), D30 (all panels), D70 | LIVE — **all 4 `type` values confirmed** (input/output/cacheRead/cacheCreation). Cache hit formula will work. |
| **`claude_code_code_edit_tool_decision_total`** | Counter | SDK→OTLP→collector | spec D00 (accept rate), D40 (all panels) | LIVE — **NAME CORRECTION:** SDK emits `_total` not `_count_total`. Labels: `tool_name` (Edit/Write), `decision` (accept), `language` (Bash), **`exported_source`** (NOT `source` — see § 6). |
| `claude_code_active_time_seconds_total` | Counter | SDK→OTLP→collector | spec D20 (CLI vs user time, productivity multiplier) | PARTIAL — `type=cli` confirmed, **`type=user` never observed in 24h**. Productivity-multiplier panel will divide by zero. Likely requires interactive sessions to emit user-type. |

---

## 3. Remediation lists

### 3.1 Dead instruments

Six instruments defined in `monitoring.py` with zero production call sites:

1. `harness_memory_usage_bytes` — no `set_memory_usage` call site.
2. `cgf_spans_collected_total` — no `record_span_collected` call site.
3. `cgf_spans_exported_total` — no `record_span_exported` call site.
4. `cgf_adapter_transforms_total` — no `record_adapter_transform` call site.
5. `cgf_reward_composite` — no `record_reward` call site.
6. `cgf_feedback_dimensions` — no `set_feedback_dimension` call site.

**Decision per row (TBD by maintainer):**

| Instrument | Option A: Wire up | Option B: Delete |
|---|---|---|
| `harness_memory_usage_bytes` | Add a call from `collect_system_metrics` loop using `psutil.Process().memory_info()` — useful + cheap. | If we don't actually want per-component memory tracking, delete. |
| `cgf_spans_collected_total` | Bridge from `src/harness/tracer/` instrumentation — wire `record_span_collected` into the OTel `SpanProcessor.on_start` hook. | If the existing OTel span pipeline already exposes equivalent data via `otelcol_exporter_*` series, delete. |
| `cgf_spans_exported_total` | Same as above, via `SpanProcessor.on_end`. | Same. |
| `cgf_adapter_transforms_total` | Wire from the adapter pipeline (need to locate adapter call sites). | Delete if adapters are not central to current workflow. |
| `cgf_reward_composite` | Wire from `quality_evaluator.py` when a composite score is computed. | Delete if composite reward is a Phase B concept that hasn't been operationalized. |
| `cgf_feedback_dimensions` | Wire from `cgf_session.py` after the evaluator returns a recommendation. | Delete. |

**Recommendation:** delete all five `cgf_*` instruments and their wrapper methods. They appear to be leftover from an earlier optimization-store-based architecture that was simplified during Block 4. The current Phase A telemetry (`harness_eval_*` family in §2.4) replaces them. The corresponding cgf.json panels are slated for replacement in G5a anyway — don't carry forward references to dead series. Keep `harness_memory_usage_bytes` and wire it up since psutil memory is genuinely useful and the diff is ~5 LoC.

### 3.2 Stranded instruments

Two instruments emitted but referenced only in `overview.json` (which is being rewritten in G6):

1. `harness_checkpoint_size_bytes`
2. `harness_workspace_files_total`

**Decision:** verify overview.json actually queries these (the new D00 spec doesn't). If yes, port the panel to D00; if no, delete the instrument and the corresponding `collect_system_metrics` block. Defer to G6.

### 3.3 Gaps — emitted on one path only

1. **`harness_run_iteration` only emits on the single-resource (`cgf_session.py`) path.** Multi-resource orchestrator never calls `record_iteration`, so D70's iteration stat panel shows "—" for `make optimize` against multi-resource fixtures (e.g., `tests/smoke/iac-team`). **Fix:** wire `record_iteration` into `multi_resource_orchestrator._advance_phase` or `_delegate_iteration` — needs to determine which iteration concept to surface (per-resource current iteration, vs. total iterations across all resources). Defer the fix to G5a where D70 lands; document the gap in the meantime.

### 3.4 Spec PromQL referencing missing series

Per [GRAFANA-REFACTOR.md § 7.4 / 7.5], the following spec panels reference SDK metrics we haven't runtime-verified:

- D10 — spend-rate, spend-by-* panels: depend on `claude_code_cost_usage_USD_total` with `model` / `query_source` / `effort` labels.
- D30 — cache hit panels: depend on `claude_code_token_usage_tokens_total` with `type ∈ {cacheRead, cacheCreation, input, output}`.
- D40 — most-used tools: depends on `claude_code_code_edit_tool_decision_count_total` with `tool_name` / `decision` / `source` / `language`.
- D20, D65 — LoC, commits: depend on `claude_code_lines_of_code_count_total`, `claude_code_commit_count_total`.

**Resolution path for each:** runtime verification (§5 below). If a metric or label dimension is absent from the live capture, the resolution per panel is one of:

- (a) **env-var fix** — most likely cause for total dropout (e.g., `OTEL_METRICS_INCLUDE_VERSION` or similar).
- (b) **collector-config fix** — labels not promoted via `resource_to_telemetry_conversion`.
- (c) **defer the panel to Stage 3** — the metric simply isn't emitted by our SDK version.

Decisions logged here as they're made.

---

## 4. Action items (rolled up)

Prerequisite to G4 (Tier 2 dashboards) and G5a (Dashboard 70):

- [ ] **Delete 5 dead `cgf_*` instruments** plus their wrapper methods + their references in `cgf.json`. Cleans ~70 LoC from monitoring.py and ~5 dead panels from cgf.json (which is being replaced anyway, but the metrics shouldn't outlive their consumers).
- [ ] **Wire `harness_memory_usage_bytes`** into `collect_system_metrics` via `psutil` (~5 LoC).
- [ ] **Wire `record_iteration` into multi-resource orchestrator.** Defer to G5a unless cheap; flag iteration panel as "single-path-only for now" in D70 spec.
- [ ] **Verify `harness_checkpoint_size_bytes` and `harness_workspace_files_total` consumers.** Decide port-or-delete during G6.
- [ ] **Runtime verification** (§5) for SDK-side metrics. Must happen before G4 / G5a / G6 are claimed done.

---

## 5. Runtime verification

Ground truth for what flows at runtime. Re-run after any monitoring or
docker-compose change. Same pattern as `feedback_verification.md`
documents for code: unit tests passing ≠ feature working.

### 5.1 Single-resource path (`cgf_session.py`)

```bash
make up
make optimize FIXTURE=python-expert
# Let it run long enough for Prometheus's 15s scrape to catch metrics
# from the first phase or two; full convergence is not required.
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | jq -r '.data[]' \
  | grep -E '^(harness_|cgf_|claude_code_)' \
  | sort \
  > /tmp/live-metrics-single.txt
```

### 5.2 Multi-resource path (`multi_resource_orchestrator.py`)

```bash
make optimize FIXTURE=iac-team
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | jq -r '.data[]' \
  | grep -E '^(harness_|cgf_|claude_code_)' \
  | sort \
  > /tmp/live-metrics-multi.txt
```

### 5.3 Interactive mode

```bash
make interactive
# Run a handful of prompts that exercise: text reply, tool call (Read),
# tool call (Bash), tool call (Write). Then exit.
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | jq -r '.data[]' \
  | grep -E '^(harness_|cgf_|claude_code_)' \
  | sort \
  > /tmp/live-metrics-interactive.txt
```

### 5.4 Expected diff against this inventory

For each capture file, compare against the corresponding column-set above:

```bash
# Single-resource path should populate ALL §2.5 PENDING rows after Phase 1,
# plus §2.1, §2.4, §2.6 LIVE rows.
diff <(cat docs/METRICS-INVENTORY.md \
         | grep -oE '`(harness_|cgf_|claude_code_)[a-z_]+`' \
         | tr -d '`' | sort -u) \
     /tmp/live-metrics-single.txt
```

Any metric in the inventory but missing from the live capture is a gap to
either fix (env-var / collector-config / wire-up) or defer (Stage 3).

Any metric in the live capture but missing from the inventory is a metric
we didn't know existed — investigate and add a row.

---

## 6. Runtime-verification findings (2026-05-14)

### 6.1 SDK metric name correction

Upstream spec ([GRAFANA-REFACTOR.md § 1 source]) lists the edit-decision counter as `claude_code_code_edit_tool_decision_count_total`. **Reality: SDK emits it as `claude_code_code_edit_tool_decision_total`** (no `_count` infix).

**Impact:** every D40 PromQL panel and D00 "Accepted edits / total edit decisions" stat panel that uses the spec's name verbatim will return no data. Fix at panel-authoring time: drop the `_count` infix.

### 6.2 SDK `source` attribute renamed to `exported_source`

The Prometheus scrape job applies a `source="claude-sdk-harness"` label (see `config/monitoring/prometheus.yml` job `otel-collector-sdk`). The SDK separately emits its own `source` attribute on `code_edit_tool_decision` (with values `config`/`hook`/`user_permanent`/`user_temporary`/`user_abort`/`user_reject`).

Prometheus resolves the collision by renaming the SDK's attribute → **`exported_source`**.

**Impact:** D40 "Rejection rate by `source`" panel must query `exported_source` not `source`. Note this in the dashboard JSON comment alongside the query. Same collision applies to `job` (SDK `service.name` lands as `exported_job`).

### 6.3 `claude_code_commit_count_total` and `pull_request_count_total` likely empty for harness-typical workloads

Both counters were emitted at some point in the past (metric names appear in `__name__/values`) but **zero series within a 24h window**. Plausible causes:

- **Commit counter:** SDK fires this when the agent invokes `git commit` in-session. CGF optimization runs don't commit; autonomous mode does commit but may go via a hook/wrapper that the SDK doesn't intercept. Verify by running `make autonomous` once and re-checking.
- **PR counter:** Documented in spec as Claude-opened-PRs-only. Requires a session where Claude actually runs `gh pr create` (or the equivalent MCP tool).

**Impact:** D10 "Cost per commit" and "Cost per PR" panels will render empty for the typical CGF-optimization workload. Either:

- (a) Add a panel description noting "requires commits/PRs to be opened from inside a Claude session",
- (b) Defer those panels to a future iteration, or
- (c) Augment the harness with a custom commit counter via a hook.

Recommend (a) for now — they're aspirational panels, not load-bearing.

### 6.4 `claude_code_active_time_seconds_total{type="user"}` likely empty for non-interactive workloads

`type=cli` is consistently emitted on all sessions. `type=user` (human-keyboard idle / typing time) was not observed in 24h. Plausible cause: SDK only emits `user` on interactive `make interactive` sessions, not on autonomous or CGF runs.

**Impact:** D20 "Productivity multiplier (cli/user)" panel will divide by zero. Defer the panel or compute as `cli / max(cli, 1)` with a description noting the caveat.

### 6.5 SDK label dimensions worth noting for D10/D30/D70 panel authoring

The live capture confirms the SDK emits these cardinality-bearing labels (so the spec's small-multiples / `Repeat by variable` patterns will work):

- `claude_code_cost_usage_USD_total`: `{model, query_source, effort, agent_name, plugin_name, terminal_type}` — all 6 segmentation dimensions land. The spec's per-`effort` and per-`agent_name` panels are buildable.
- `claude_code_token_usage_tokens_total`: `{type, model, query_source, effort, agent_name}` — `type` has all 4 values (input/output/cacheRead/cacheCreation), so the cache-hit formula is sound.

### 6.6 Stale `session_id` labels from older SDK versions

Older series (e.g., `service_version: 2.1.128`) carry a `session_id` label despite our `OTEL_METRICS_INCLUDE_SESSION_ID=false` env var. New series from the current SDK version (`2.1.139`) do not. The stale series will age out at `metric_expiration: 5m` (collector) plus Prometheus retention. Not actionable.

---

## 7. Maintenance

This document is auto-staleable but not auto-generated. After any PR that
touches `src/harness/monitoring.py`, `src/harness/optimization/_orchestrator_phases/`,
`src/harness/interactive.py`, `src/harness/agent.py`, or the OTel collector
config, re-run §5 and update the affected rows.

Re-audit cadence: at minimum once per dashboard-refactor block (G4, G5a,
G5b, G6), and after any SDK bump that might change `claude_code_*` emission.
