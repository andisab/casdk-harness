# Grafana Telemetry & Dashboard Refactor — Plan

**Status:** Planning. Not yet started. Work blocked behind `phase-a-fixes` smoke validation.

**Source:** Joplin note "Claude Agent SDK: Grafana" (id `671394081d114c3ebfa6aa5b6766a3e8`), v2 of 2026-05-13. This document is the codebase-grounded implementation plan derived from that spec.

**Scope:** Single-harness use (this repo only). Multi-developer / multi-team taxonomy from the spec is dropped accordingly — see Single-User Implications below.

---

## 1. Goal

Replace the current two dashboards (`overview.json`, `cgf.json`) with the spec's 10-dashboard architecture organized in three tiers (Overview → SDK Telemetry → Mode-specific Deep-Dives), built on Prometheus-only metrics with Loki and traces explicitly deferred.

Three concrete payoffs:

1. **Make the data right before designing visualizations against it.** Pin OTel temporality, add the three missing harness instruments, and audit which metrics actually fire at runtime.
2. **Replace the CGF dashboard's bargauge with a State Timeline** plus the seven other P1–P8 fixes documented in the spec's audit.
3. **Surface the three north-star KPIs** (cost, cache hit rate, accepted-edit rate) at-a-glance on a mode-aware overview dashboard.

## 2. State of the codebase (audit grounding)

| Component | Status | Notes |
|---|---|---|
| OTel Collector | Running, OTLP gRPC/HTTP receiver, Prom exporter on `:8889` | `resource_to_telemetry_conversion: true` already set (`config/monitoring/otel-collector.yml:48`) |
| Prometheus | 6 scrape jobs incl. SDK metrics via collector | `config/monitoring/prometheus.yml` |
| Grafana | 2 dashboards (`overview.json` 762 LoC / 27 panels, `cgf.json` 1348 LoC / 25 panels, schemaVersion 38) | `config/monitoring/dashboards/` |
| Loki | **Deferred to Stage 3.** Collector pipes logs to `debug` exporter (stdout only) | `otel-collector.yml:10-11, 52-55, 77` |
| Tempo / traces beta | **Deferred to Stage 3.** Collector pipes traces to `debug` exporter | `otel-collector.yml:73` |
| `harness_run_phase_info` / `_iteration` / `_path_info` | Landed on `phase-a-fixes` | `monitoring.py:275-298`; powers the Active Run Status row |
| `harness_run_config_info` | **Not implemented** (Phase 1 deliverable) | Info-metric used by spec D00 Row 0 + D70 Row 0 |
| `harness_run_start_timestamp` | **Not implemented** (Phase 1 deliverable) | Needed for "Run Elapsed" stat panels |
| `harness_task_progress` | **Not implemented** (Phase 1 deliverable) | Needed for D65 (autonomous-mode panels) |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | Not explicitly set | SDK default is `cumulative` for Prometheus targets; pinning is defensive |
| `OTEL_RESOURCE_ATTRIBUTES` | Not set | Useful for `project=` discriminator across repos; team/cost_center skipped for single-user |
| Existing dashboard template variables | None — every query in `cgf.json` hardcodes `resource!~"test_.*"` | G3 deliverable: add `$datasource`, `$mode`, `$resource`, `$path`, `$model` |

## 3. Conflict with ongoing work

`phase-a-fixes` is currently in flight. The recent work just added the "Active Run Status" row with the bargauge phase progression panel to `cgf.json` — which is exactly what spec dashboard 70 (P1) replaces with a State Timeline. Deferred items C/E/F in CLAUDE.md's "CGF state-machine / observability — follow-ups" also touch the same panels.

**Implication:** Dashboard JSON rewrites cannot start until `phase-a-fixes` lands (or branches cleanly). However, the small Phase 1 prep commits (env pin + 3 new instruments) are non-conflicting and can land on `phase-a-fixes` directly.

## 4. Single-user implications

The spec assumes a multi-developer environment in many places. For this single-harness use:

- Drop `$user` template variable from the shared rail.
- Drop "Top users by spend" table on D10.
- Drop "Per-developer scorecard" table on D20.
- DAU/WAU/MAU panels lose signal — replace with "Active days in last 30" sparkline as a proxy, or omit.
- `OTEL_RESOURCE_ATTRIBUTES` reduces to `project=${PROJECT}` (default `ab-casdk-harness`). Useful only if the stack is ever pointed at a second repo. Skip `team`, `cost_center`.

The `query_source` (main/subagent/auxiliary) and `effort` segmentation panels retain their value — they segment within a single user.

## 5. Phasing overview

```
phase-a-fixes (in flight)
   │
   ├── Phase 1 — prep commits (env pins + 3 new instruments)
   │
   └── grafana-v2 worktree (branches from phase-a-fixes)
       │
       G3 (folder + variables)
        │
        G0 (emission audit) ──► METRICS-INVENTORY.md + remediation PRs
        │                       │
        │                       ├── Dead-instrument cleanup
        │                       ├── Missing-call-site instrumentation
        │                       └── Spec-gap resolution (substitute, defer, or add)
        │
        G5a (Dashboard 70) ──► G4 (Tier 2: D10–D50) ──► G5b (D60/D65) ──► G6 (D00 + D99 placeholder)
        │
        merge
```

## 6. Phase 1 — Prep commits on `phase-a-fixes`

Three small diffs that don't conflict with the bargauge work in flight. Lands before `grafana-v2` branches.

### 6.1 Pin OTel temporality explicitly

Add to all three agent service blocks in `docker-compose.yml` (current locations: lines ~62, ~150, ~232):

```yaml
- OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
```

Defensive against future SDK default changes. The spec calls out that VictoriaMetrics, Mimir, and Grafana Cloud silently drop delta-temporality metrics — we don't use any of those, but the pin costs nothing.

### 6.2 Add `OTEL_RESOURCE_ATTRIBUTES` passthrough

In `.env.example`:

```bash
# Optional. Default: ab-casdk-harness. Pass through to OTEL_RESOURCE_ATTRIBUTES
# so all metrics carry a project= label for filtering across multiple repos.
PROJECT=ab-casdk-harness
```

In `docker-compose.yml` (all three agent blocks):

```yaml
- OTEL_RESOURCE_ATTRIBUTES=project=${PROJECT:-ab-casdk-harness}
```

### 6.3 Three new harness instruments

In `src/harness/monitoring.py`, following the existing pattern of try/except-wrapped helpers (`record_phase_entry`, `record_iteration`, `record_run_path`):

| Instrument | Type | Labels | Emitter |
|---|---|---|---|
| `harness_run_config_info` | Gauge (info-metric) | `resource, path, mode, model, effort, eval_enabled, token_budget, max_iterations` | `cgf_session.py` + `multi_resource_orchestrator.py` at run start; cleared to 0 at run end |
| `harness_run_start_timestamp` | Gauge | `resource` | Set once next to `init_run_phases()` call sites |
| `harness_task_progress` | Gauge | `status` (`completed`/`pending`/`in_progress`) | `harness/progress.py`, on every `task_list.json` rewrite |

Helper functions follow the established pattern:

```python
def record_run_config(
    resource: str,
    path: str,
    mode: str,
    model: str,
    effort: str,
    eval_enabled: bool,
    token_budget: int,
    max_iterations: int,
) -> None:
    """Set the run config info-metric to 1 with all config dimensions as labels.
    Call once at run start. Observability never raises."""
    try:
        harness_run_config_info.labels(
            resource=resource, path=path, mode=mode, model=model, effort=effort,
            eval_enabled=str(eval_enabled).lower(),
            token_budget=str(token_budget),
            max_iterations=str(max_iterations),
        ).set(1)
    except Exception as e:  # pragma: no cover
        logger.debug("record_run_config failed", error=str(e))
```

**Cardinality caveat (call out in docstring):** `token_budget` and `max_iterations` are numbers stringified into labels. For a single-developer harness this is fine. If ever pointed at long-lived multi-tenant Prometheus, move these to the event log instead.

Unit tests next to existing `tests/unit/test_monitoring.py` cases. ~50 LoC total across `monitoring.py`, call sites, tests.

## 7. Phase 2 — `grafana-v2` worktree

Branched from `phase-a-fixes` after Phase 1 lands. All dashboard work happens here.

### 7.1 G3 — Folder restructure + variable rail

One PR, mechanical:

- Rename `config/monitoring/dashboards/overview.json` → `00-harness-overview.json` (rewrite in G6).
- Rename `config/monitoring/dashboards/cgf.json` → `70-mode-cgf.json` (rewrite in G5a).
- Add Grafana folder provisioning so the UI groups all 10 files under "Claude Agent Harness".
- Bump every dashboard's `schemaVersion` 38 → 39 (Grafana 11.3+).
- Shared template variables on every dashboard: `$datasource`, `$mode`, `$resource`, `$path`, `$model`. **Drop `$user`** (single-user) and `$loki_datasource` (no Loki in Stage 2).
- Stub Dashboard Links between all 10 file UIDs (forward refs 404 gracefully until the target dashboard lands).

### 7.2 G0 — Emission audit

**Sits between G3 and G5a.** No dashboard panel work happens until this is complete and remediation PRs have landed.

#### Why this phase exists

Two metric pipelines exist and they fail in different ways:

| Pipeline | Defined in | Sent to | Common defect mode |
|---|---|---|---|
| Harness (`harness_*`, `cgf_*`) | `prometheus_client` in `monitoring.py` | Per-agent HTTP `:9090`, scraped by Prometheus via `main-agent` / `agent-two` / `agent-three` jobs | Instrument defined but no call site; or call site doesn't fire in the relevant path |
| SDK-native (`claude_code_*`) | Claude Code CLI internals | OTLP → `otel-collector:4317` → Prom exporter `:8889`, scraped by `otel-collector-sdk` job | Wrong env var (e.g., `OTEL_LOGS_EXPORTER` missing → silent total dropout); attribute-derived label not propagated; metric name mismatch |

The phase-a-fixes work already surfaced this once: `harness_run_phase_info` was defined but not called from `multi_resource_orchestrator._advance_phase`, so the panel was effectively blank. There are likely more.

#### Inputs

- `monitoring.py` instrument definitions (canonical list).
- `grep -r '<metric_name>' src/` for each instrument → call site inventory.
- Live `/api/v1/label/__name__/values` from Prometheus after real smoke runs of:
  - `make optimize` against `tests/smoke/python-expert` (single-resource path)
  - `make optimize` against `tests/smoke/iac-team` (multi-resource path)
  - `make interactive` (interactive mode)
  - `make autonomous` (if feasible to scope to a short fixture)
- Every PromQL query referenced in the spec's Stage-2 panels.

#### Verification command

```bash
make up
make optimize FIXTURE=python-expert
# (run for representative duration; let scrape interval populate)
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | jq -r '.data[]' \
  | grep -E '^(harness_|cgf_|claude_code_)' \
  > /tmp/live-metrics.txt
```

This single command is the ground truth for what flows at runtime. Every subsequent dashboard PR should re-run it against the relevant `make` target before claiming a panel is "done." Same pattern as `feedback_verification.md` documents for code: unit tests passing ≠ feature working.

#### Output: `docs/METRICS-INVENTORY.md`

One table; rows look like:

| Metric name | Defined at | Emitted from | Pipeline | Consumed by | Status |
|---|---|---|---|---|---|
| `harness_run_phase_info` | `monitoring.py:275` | `cgf_session.py:NNN`, `_orchestrator_phases/...` | harness/prom_client | spec D70 R1 panel 1 | LIVE |
| `harness_run_path_info` | `monitoring.py:290` | `cgf_session.py` only | harness/prom_client | spec D70 `$path` variable | **GAP — multi-orchestrator doesn't call it** |
| `claude_code_token_usage_tokens_total{type="cacheRead"}` | SDK | SDK | OTLP→collector | spec D30 cache hit panels | NEEDS RUNTIME VERIFY |
| `harness_session_responses_total` | `monitoring.py:NNN` | nowhere | harness/prom_client | spec D60 panel | **DEAD — no call site** |
| ... | | | | | |

#### Three remediation lists fall out of the table

1. **Dead instruments** — defined but never called. Either add call sites or delete from `monitoring.py`. Deletion is cheap; defending an unused instrument later is not.
2. **Stranded instruments** — emitted but no panel/alert consumes them. Decide per-instrument: add panel, leave (someone may query ad-hoc), or delete.
3. **Spec gaps** — PromQL in the spec that no current metric satisfies. For each: (a) add the missing instrument and emitter, (b) substitute an equivalent existing metric, or (c) defer the panel to Stage 3.

#### SDK-side audit caveat

The SDK-native `claude_code_*` audit is shallower than the harness side because we don't own the emission code — we can only verify metrics arrive, not why they're missing if they don't. For SDK metrics the audit reduces to:

(a) verify env-var wiring in compose (`CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`, endpoint, protocol);
(b) capture live series after a smoke run;
(c) flag any spec-referenced metric that isn't in the live capture.

The fix is then either an env-var change, a collector-config change, or "this metric isn't actually emitted by our SDK version — defer the panel."

#### Estimated effort

Half a day to one day for the inventory + verification runs. Remediation PRs scope-dependent — could be one small PR if everything's wired correctly, or three to five if there are real gaps.

### 7.3 G5a — Dashboard 70 (CGF Optimization)

**Start here in Phase 2, per spec.** This dashboard has the densest concrete panel specs (P1–P8 in the spec's audit section) and a live test loop via `make optimize` for end-to-end validation. Replaces `cgf.json` entirely.

P1–P8 applied:

- **P1** — Bargauge → State Timeline (Grafana native `state-timeline` panel type). Eliminates the `● NOW` text-marker hack.
- **P2** — `$path` variable filter replaces the 14 per-phase override blocks. 14 phase rows → 7–8 depending on path.
- **P3** — Null/NaN → "—" gray, not red "No data".
- **P4** — Add Cache Hit Rate (stat + sparkline), Cost by Model (horizontal bar), Run Elapsed (stat). Run Elapsed uses `harness_run_start_timestamp` from Phase 1.
- **P5** — Two-tier hierarchy: Row 1 Run Header (State Timeline + stacked stats + Cache Hit Rate, h=5), Row 2 Economics (Cost + Tokens + Cost by Model + Run Elapsed, h=4), Rows 3–5 collapsed (Optimization Quality, Eval Framework, Tracer Internals).
- **P6** — Drop `fixedColor: "purple"` everywhere. Gray for completed/context, green for active, blue for `complete` terminal, red only for `failed` + genuine errors, amber for warning thresholds only.
- **P7** — `$resource` variable replaces the hardcoded `resource!~"test_.*"` matchers.
- **P8** — Cost/Token Stat panels: range queries (`[5m]`) instead of `instant: true`, so sparklines populate. Reduction stays `lastNotNull`.

Row 0 (height 3) **Run Config** — Table panel of `harness_run_config_info == 1` with "Labels to fields" transform. Uses new Phase 1 instrument.

### 7.4 G4 — Tier 2 SDK dashboards (D10–D50)

PromQL-only. All five panels follow the same conventions: transparent backgrounds, single-color + structural-red palette, sparkline on every Stat panel, small multiples via "Repeat by variable" where >3 series.

#### D10 — Cost & Spend (~10 panels)

- Spend rate, $/hour (Stat + sparkline).
- Spend by model (small multiples via `Repeat by $model`).
- Spend by `query_source` (main/subagent/auxiliary) — surfaces the 7× Task-tool cost.
- Spend by `effort` (low/medium/high/xhigh/max).
- Cost per accepted edit time-series (per model).
- Cost per commit time-series.
- Cost per PR time-series (panel description must include "only counts Claude-Code-opened PRs" caveat).
- Projected monthly spend (`predict_linear(claude_code_cost_usage_USD_total[7d], 30*86400)`).
- Cost by terminal type (horizontal bar, not pie).

**Single-user implications applied:** drop "Top users by spend" table.

#### D20 — Session & Productivity

- Sessions started by `start_type` (fresh/resume/continue, small multiples).
- Active CLI time vs. user time side-by-side.
- Lines of code (added − removed) using `sum_over_time`, not `increase` (spec gotcha).
- Commits per session histogram.
- Session duration distribution.
- Plugin & skill activation frequency (if SDK emits these; verify in G0).

**Single-user implications applied:** drop per-developer scorecard table. DAU/WAU/MAU panels replaced with "Active days in last 30" sparkline or omitted.

#### D30 — Cache & Token Efficiency

**Highest-value dashboard. Pure PromQL, no Stage-3 dependencies.** Build first within G4 if prioritizing.

- Cache hit rate overall (Stat + sparkline, threshold colors: red <60%, amber 60–80%, green ≥90%).
- Cache hit rate over time (single line, threshold fill regions).
- Cache hit rate by model (small multiples — mid-session model switches destroy cache).
- Token mix stacked area (input / output / cacheCreation / cacheRead).
- Effective input $/Mtok (computed via the formula in the spec).
- Cache creation vs. cache read ratio (diagnoses TTL too short or unstable system prompts).
- Output:input ratio by model.

#### D40 — Tool & Code Quality (Prometheus-only subset)

Per spec v2 split:

- Edit acceptance rate overall + per-tool (Edit/Write/NotebookEdit) small multiples.
- Rejection rate by `language` (small multiples — reveals where Claude struggles).
- Rejection rate by `source` (config/hook/user_permanent/user_temporary/user_abort/user_reject).
- Most-used tools derived from `claude_code_code_edit_tool_decision_count_total` by `tool_name` (horizontal bar).
- Permission-mode changes time-series (security signal — `bypassPermissions` escalations).

**Deferred to Stage 3 (Loki):** P50/P95/P99 tool execution duration, tool success rate by name, MCP tool calls by `mcp_server_name`, Bash command frequency.

#### D50 — Reliability & Errors (Prometheus-only subset)

- API error count (Stat + sparkline) using `harness_agent_requests_total{status="error"}` — harness-level proxy per spec v2's explicit fallback recommendation.
- Harness agent error rate (`rate(harness_agent_requests_total{status="error"}[5m]) / rate(harness_agent_requests_total[5m])`).
- Harness agent duration P50/P95 (`histogram_quantile` on `harness_agent_duration_seconds_bucket`) by agent.

**Deferred to Stage 3 (Loki):** API errors by `status_code` (429/5xx/529 segmentation), API errors by `model`, API request P50/P95/P99 latency by model, MCP server connection failures, internal/auth/compaction failure breakdowns.

**Deferred to Stage 3 (Traces beta):** TTFT P50/P95 by model, average attempts per request (silent retries on success).

### 7.5 G5b — Mode dashboards D60 + D65

#### D60 — Mode: Interactive

Displayed when `$mode = interactive`. Linked from D00's mode summary row.

- Session Header (h=3): Active agent + Session duration + Prompts this session + Responses this session — all Stat + sparkline.
- Conversation Flow (h=8): time-series of `harness_session_prompts_total` and `harness_session_responses_total` rates, overlaid.
- Tool Usage (h=6): horizontal bar of `harness_tool_calls_total` by `tool_name`, colored by `status`. Plus top-10 table with success rate column.
- Message Types (h=4): stacked area of `harness_message_types_total` by `message_type`.
- SDK Economics row (collapsed): deep-links to D10 and D30.

**Depends on existing `harness_session_*` and `harness_tool_calls_total` instruments — G0 will verify these fire.**

#### D65 — Mode: Autonomous

Displayed when `$mode = autonomous`.

- Task Progress Header (h=4): Tasks completed/total (Stat as %), Tasks remaining, Current task, Workspace state (with value mappings).
- Commit & Code Activity (h=6): `claude_code_commit_count_total` over time + LoC sparkline (using `sum_over_time`, not `increase`).
- Agent Execution (h=8): `harness_agent_duration_seconds` histogram heat map by agent name.
- SDK Economics row (collapsed): deep-links to D10 and D30.

**Depends on `harness_task_progress` from Phase 1.** Without that instrument the Task Progress Header panels return null and G0 will flag the gap.

### 7.6 G6 — Dashboard 00 (Harness Overview) + 99 placeholder

#### D00 — Harness Overview

Built last because it depends on all other dashboard UIDs existing (for deep-link Data Links).

Row 0 (h=3) — Mode & Config:
1. Active Mode (Stat, w=4) — value-mapped from `harness_agent_active_sessions > 0`. Data Link opens the matching Tier 3 dashboard.
2. Run Config (Table, w=14) — `harness_run_config_info == 1` with Labels-to-fields transform. Single-row table, header hidden.
3. Run Elapsed (Stat, w=6) — `time() - harness_run_start_timestamp`.

Row 1 (h=4) — Universal SDK KPIs (5 Stat + sparkline panels):
- Spend this period + delta
- Cache hit rate + threshold colors
- Accepted edits / total edit decisions
- Cost per commit
- API error rate (using `harness_agent_requests_total{status="error"}` proxy per Stage-2 subset)

Row 2 (h=8) — Cost & Cache Trends:
- Spend over time by model (line, not stacked).
- Cache hit rate over time (single line with threshold fill regions).

Row 3 (h=6) — Mode-Specific Summary (content depends on `$mode`; panels return "—" when their mode isn't active, no conditional visibility needed):
- If `$mode = optimize`: Phase Timeline + Iteration + Mean Composite Reward + deep-link to D70.
- If `$mode = interactive`: Active Sessions + Prompts + Session Duration + Tool Calls by Type + deep-link to D60.
- If `$mode = autonomous`: Task Completion + Tasks Remaining + Commits + LoC + Workspace State + deep-link to D65.

#### D99 — Raw Events (placeholder)

Single Text panel: "This dashboard requires Loki. See `docs/GRAFANA-REFACTOR.md` § Stage 3."

Ships with D00. Trivial. Holds the dashboard UID so cross-dashboard Data Links from session tables work after Loki is enabled.

## 8. Stage 3 — Deferred

Per spec v2, both items are deferred indefinitely and called out only in the appendix:

### 8.1 Loki + log pipeline

Unlocks: dashboard 99 activation; D40 panels (tool execution latency, tool success rate, MCP tool calls, Bash frequency); D50 panels (status-code segmentation, per-model API errors, per-model API latency, MCP server failures, internal/auth/compaction failures).

Infrastructure cost: one additional container (~200MB RAM for single-tenant monolithic Loki with filesystem storage). Concrete changes:
- Add `grafana/loki:3.x` service to `docker-compose.yml`.
- Add `loki` exporter to `otel-collector.yml`, replace `[debug]` in the `logs` pipeline.
- Add Loki datasource provisioning to `config/monitoring/datasources/`.
- Verify `service_name="claude-code"` label survives the OTLP→Loki path.
- Re-introduce `$loki_datasource` template variable.

### 8.2 Tempo + traces beta

Unlocks: D50 TTFT panels, average-attempts-per-request, `stop_reason` analysis, `blocked_on_user` latency, `TRACEPARENT` propagation into CGF pipeline subprocesses.

Infrastructure cost: one additional container (Tempo ~150MB RAM). Concrete changes:
- Add `grafana/tempo:2.x` service to `docker-compose.yml`.
- Set `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` and `OTEL_TRACES_EXPORTER=otlp` in agent service env.
- Add `otlp` traces exporter to `otel-collector.yml`, replace `[debug]` in the traces pipeline.
- Add Tempo datasource provisioning.

**Schema is beta and may change between Claude Code releases.** Dashboard panels built on trace queries carry upgrade risk. Defer until there's a clear ROI signal (e.g., debugging a TTFT regression that metrics can't explain).

## 9. Optional follow-ups

### 9.1 Alerts (G8)

Spec recommends four threshold alerts. Add to existing `config/monitoring/alerting.yml`:

- Cost spike: `sum(increase(claude_code_cost_usage_USD_total[1h])) > 3 * historical_P95_1h`.
- Cache hit rate degradation: `cache_hit_rate < 0.6 for 30m`.
- Sustained retry exhaustion: `rate(api_retries_exhausted) > 0 for 10m` (requires Loki for `api_retries_exhausted` access, OR a Collector transform promoting it to a Prom counter).
- Token burn: `sum(rate(claude_code_token_usage_tokens_total[5m])) > 100k for 10m`.

Independent of dashboard work; can land anytime after Phase 1.

### 9.2 Dashboards-as-code workflow

Already done. Repo provisions dashboards from `config/monitoring/dashboards/*.json` via `dashboard-provider.yml`. Grafonnet / Terraform would be over-engineering for a single-environment setup. Skip unless we start running this against multiple environments.

### 9.3 Weekly digest

Spec Stage 3 item #11. Out of scope for this refactor; would be a separate workstream (scheduled job, Prometheus HTTP API, Slack/email sink).

## 10. Open questions

### 10.1 Phase 1 branching

Two options for landing the Phase 1 prep commits:

- **(a)** Direct on `phase-a-fixes` — per spec, simpler, lower branch count.
- **(b)** Short-lived `grafana-prep` branch off `phase-a-fixes`, merged back before `grafana-v2` branches — keeps in-flight smoke work cleanly separable from observability prep, at the cost of one extra merge.

Preference: **(b)** for blast-radius reasons. Default to (a) if branch hygiene isn't a concern.

### 10.2 Cardinality of `harness_run_config_info`

`token_budget` and `max_iterations` as string labels create one series per distinct combination. For single-user this is fine. Document the constraint in the docstring; revisit only if the harness is ever pointed at long-lived multi-tenant Prometheus.

### 10.3 G0 audit scope vs. depth

The audit's harness-side is deep (every instrument traced to call sites and consumers). The SDK side is necessarily shallow (we only verify metrics arrive, not why they're missing). If a spec-referenced SDK metric doesn't appear in the live capture, the resolution is: (a) env-var fix, (b) collector-config fix, (c) defer the panel. Document any (c) decisions in `METRICS-INVENTORY.md` so they don't get forgotten.

---

## Appendix: spec source

Joplin note "Claude Agent SDK: Grafana", id `671394081d114c3ebfa6aa5b6766a3e8`, v2 of 2026-05-13. The five-dashboard architecture, P1–P8 CGF dashboard audit, PromQL query library, Tufte principles applied to Grafana, and infrastructure gotchas are all sourced from there.

**Diff against v1:** Loki and traces beta were promoted from "Stage 2" to "Stage 3 (deferred)" with the dashboards 40/50 split into Prometheus-only and Stage-3 subsets. Dashboard 99 became a placeholder. Spec now explicitly directs Stage-2 work to start with dashboard 70 (concrete spec + live `make optimize` test loop) and to branch a `grafana-v2` worktree from `phase-a-fixes`.
