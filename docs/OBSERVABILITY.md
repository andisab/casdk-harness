# Observability — Architecture & Operations

Technical reference for the harness's observability stack: how data flows, what's collected, what's visualized, what alerts when, and what to watch out for during ongoing maintenance.

**Scope:** Single-developer harness (this repo). Multi-team / multi-tenant concerns are explicitly out of scope.

**Last updated:** 2026-05-14, after the `grafana-refactor` branch landed the 10-dashboard architecture and 13 alert rules.

---

## 1. Architecture at a glance

Seven services compose the observability stack. The dashed boxes are deferred (Stage 3) and not currently running:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGENT CONTAINERS                                    │
│                                                                              │
│  main-agent (always-on)        agent-two / agent-three (multi-agent profile) │
│  ┌──────────────────────┐      ┌──────────────────────┐                      │
│  │ MetricsCollector     │      │ MetricsCollector     │                      │
│  │   :9090/metrics      │      │   :9090/metrics      │                      │
│  │ (prometheus_client)  │      │ (prometheus_client)  │                      │
│  └──────────┬───────────┘      └──────────┬───────────┘                      │
│             │                              │                                 │
│  ┌──────────▼───────────┐      ┌──────────▼───────────┐                      │
│  │ Claude Code SDK      │      │ Claude Code SDK      │                      │
│  │ OTLP exporter        │      │ OTLP exporter        │                      │
│  └──────────┬───────────┘      └──────────┬───────────┘                      │
└─────────────┼──────────────────────────────┼─────────────────────────────────┘
              │ OTLP gRPC :4317              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                OTel Collector  (contrib :0.119.0)                            │
│   receivers: otlp (gRPC :4317, HTTP :4318)                                   │
│   processors: batch, memory_limiter                                          │
│   exporters: prometheus :8889   debug (logs+traces — Stage 3 placeholder)    │
│   resource_to_telemetry_conversion: enabled (label promotion)                │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │ scrape SDK metrics from :8889
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                Prometheus  (prom/prometheus:latest)                          │
│   6 scrape jobs:                                                             │
│     main-agent       (harness_* and cgf_* from prom_client)                  │
│     agent-two        (multi-agent profile)                                   │
│     agent-three      (multi-agent profile)                                   │
│     otel-collector-sdk    (claude_code_* from collector)                     │
│     otel-collector-self   (collector internal metrics)                       │
│     prometheus            (self-scrape)                                      │
│     alertmanager          (so AlertManagerDown can fire)                     │
│   Retention: ${PROMETHEUS_RETENTION:-30d}                                    │
│   Alert rules: 13 across 4 groups (config/monitoring/alerting.yml)           │
└──────────┬───────────────────────────────────────────────┬──────────────────┘
           │                                               │ alerts
           ▼ queries                                       ▼
┌──────────────────────────────────┐    ┌───────────────────────────────────┐
│   Grafana  (grafana/grafana)     │    │   AlertManager (v0.27.0)          │
│   :3000, admin/${GRAFANA_PASSWORD}│   │   :9093                           │
│   10 provisioned dashboards      │    │   Routes to alertmanager-webhook  │
│   under "Claude Agent Harness"   │    │   (debug receiver) by default     │
│   folder.  Datasource UID:       │    │                                   │
│   `prometheus` (pinned).         │    └───────────────────┬───────────────┘
└──────────────────────────────────┘                        │ webhook
                                                            ▼
                                       ┌───────────────────────────────────┐
                                       │  alertmanager-webhook             │
                                       │  (stdlib-Python debug receiver)   │
                                       │  Logs payloads to stdout.         │
                                       │  Replace for real alerting.       │
                                       └───────────────────────────────────┘

   ┌─ DEFERRED (Stage 3, see § 9) ─────────────────────────────────────────┐
   │  Loki        OTLP logs pipeline (collector currently → debug exporter)│
   │  Tempo       Traces beta (CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1)      │
   └───────────────────────────────────────────────────────────────────────┘
```

Default `make up` brings up: `main-agent`, `prometheus`, `grafana`, `otel-collector`, `alertmanager`, `alertmanager-webhook`. The multi-agent profile adds `agent-two`, `agent-three`, `redis`.

---

## 2. The two metric pipelines

Different defect modes; debug differently.

| Pipeline | Defined in | Sent to | Common defect modes |
|---|---|---|---|
| **harness/prom_client** | `prometheus_client` instruments in `src/harness/monitoring.py` | Per-agent HTTP `:9090/metrics`, scraped by Prometheus via the `main-agent` / `agent-two` / `agent-three` jobs | (a) instrument defined but no call site; (b) call site exists but only fires on a path the run never takes; (c) agent's `/metrics` endpoint isn't being scraped (e.g. no active `MetricsCollector` instance) |
| **SDK→OTLP→collector** | Claude Code CLI internals | OTLP → `otel-collector:4317` → Prom exporter `:8889`, scraped by `otel-collector-sdk` job | (a) env var missing (`CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER`); (b) attribute-derived label not propagated through collector; (c) metric-name collision after Prometheus rename (e.g. SDK `source` → `exported_source`) |

---

## 3. Metrics inventory

All metrics carry a `LIVE` status as of 2026-05-14. Runtime verification is documented in § 7.

### 3.1 Harness — operational (5 metrics)

| Metric | Type | Emitted from | Notes |
|---|---|---|---|
| `harness_agent_requests_total{agent, status}` | Counter | `agent.py` via `record_request` | Status: `success` / `error` / `timeout`. The API-reliability proxy until Loki lands. |
| `harness_agent_duration_seconds{agent}` | Histogram | `agent.py` via `record_duration` | Per-cycle agent execution latency. Buckets default. |
| `harness_agent_active_sessions{agent}` | Gauge | `agent.py` via `set_active_sessions` | Set 1 at `start()`, 0 at `shutdown()`. |
| `harness_checkpoint_size_bytes` | Gauge | `collect_system_metrics` loop (60s) | Total bytes across all checkpoint files. |
| `harness_workspace_files_total` | Gauge | `collect_system_metrics` loop (60s) | Count of `.py` files in workspace. |
| `harness_memory_usage_bytes{component}` | Gauge | `collect_system_metrics` loop (60s) | Reads `/proc/self/status` `VmRSS`. Label `component="agent_rss"`. ~92 MB at idle. |

### 3.2 Harness — interactive-mode session (5 metrics)

Populated by `interactive.py` only. Quiet during `make autonomous` and `make optimize`.

| Metric | Type | Emitted from |
|---|---|---|
| `harness_session_prompts_total` | Counter | `record_user_prompt` |
| `harness_session_responses_total` | Counter | `record_agent_response` |
| `harness_session_duration_seconds` | Histogram | `record_interactive_session_duration` |
| `harness_tool_calls_total{tool_name, status}` | Counter | `record_tool_call` |
| `harness_message_types_total{message_type}` | Counter | `record_message_type` (text / tool_use / tool_result / thinking) |

### 3.3 Eval framework — Stage 3 Phase A telemetry (5 metrics)

Populated by `multi_resource_orchestrator` + `_orchestrator_phases/{eval_design,execution_eval}.py` and the LLM judge in `graders/llm_judge.py`.

| Metric | Type | Notes |
|---|---|---|
| `harness_eval_phase_duration_seconds{phase}` | Histogram | EVAL_DESIGN / EXECUTION_EVAL phase wall-clock. |
| `harness_eval_tokens_to_goal{resource_type}` | Histogram | Tokens consumed to reach the eval goal per resource. |
| `harness_eval_scenarios_total{level, status, arm}` | Counter | Per-scenario outcomes broken out by arm + level + status. |
| `harness_eval_arm_score{arm, level}` | Histogram | Score distribution per arm. |
| `harness_eval_judge_no_decision_total{model}` | Counter | Judge parse failures or transport errors after retry. |

### 3.4 Run-level status (6 metrics)

Powers the D00 / D70 Active Run Status row and the spec's `$mode` / `$path` / `$resource` template variables.

| Metric | Type | Emitted from | Notes |
|---|---|---|---|
| `harness_run_phase_info{resource, phase}` | Gauge | `cgf_session.py` (single path) + `multi_resource_orchestrator._advance_phase` (multi path) | 1 when phase active, 0 otherwise. Pre-seeded at `init_run_phases`. |
| `harness_run_iteration{resource}` | Gauge | `cgf_session.py` + `_orchestrator_phases/iterate.py:185` | Current iteration counter on both paths. |
| `harness_run_path_info{resource, path}` | Gauge | Both paths via `record_run_path` | `path ∈ {single, multi}`. |
| `harness_run_config_info{resource, path, mode, model, effort, eval_enabled, token_budget, max_iterations}` | Gauge | Both paths at run start via `record_run_config` | Info-metric. Set to 1 at start, 0 at end. Surfaces as Run Config table via Labels-to-fields transform. |
| `harness_run_start_timestamp{resource}` | Gauge | Both paths via `record_run_start` | Unix epoch seconds. Drives "Run Elapsed" panels as `time() - this`. |
| `harness_task_progress{status}` | Gauge | `progress.py:save_task_list` | Status: `completed` / `failed` / `pending`. Autonomous mode only. |

### 3.5 SDK-native (claude_code_*)

The Claude Code CLI emits these natively over OTLP when `CLAUDE_CODE_ENABLE_TELEMETRY=1`. The harness does not own emission; we verify arrival via the live capture command in § 7.

| Metric | Notes |
|---|---|
| `claude_code_session_count_total{start_type}` | `start_type ∈ {fresh, resume, continue}`. |
| `claude_code_lines_of_code_count_total{type}` | `type=added` and `type=removed` confirmed live. Use `sum_over_time` not `increase` (delta-style counter). |
| `claude_code_pull_request_count_total` | Fires only when Claude in-session opens a PR. Expected absent on CGF workloads. |
| `claude_code_commit_count_total` | Fires only when Claude in-session calls `git commit`. Expected absent on CGF workloads. |
| `claude_code_cost_usage_USD_total{model, query_source, effort, agent_name, plugin_name, terminal_type}` | All 6 segmentation dimensions land. Core of D10 spend panels. |
| `claude_code_token_usage_tokens_total{type, model, query_source, effort, agent_name}` | All 4 `type` values (input/output/cacheRead/cacheCreation) confirmed. Cache hit formula = `cacheRead / (cacheRead + cacheCreation + input)`. |
| `claude_code_code_edit_tool_decision_total{tool_name, decision, language, exported_source}` | **Name correction vs upstream spec:** SDK emits `_total`, not `_count_total`. Label `exported_source` (renamed from SDK's `source` due to Prometheus collision — see § 6). |
| `claude_code_active_time_seconds_total{type}` | `type=cli` consistent; `type=user` interactive-only. Productivity-multiplier panel divides by zero on non-interactive workloads. |

### 3.6 Removed instruments (2026-05-14)

Five `cgf_*` instruments (`cgf_spans_collected_total`, `cgf_spans_exported_total`, `cgf_adapter_transforms_total`, `cgf_reward_composite`, `cgf_feedback_dimensions`) and their `MetricsCollector` wrappers were deleted as part of the G0 emission audit. They had zero production call sites — holdovers from an earlier optimization-store / reward-pipeline architecture simplified during Block 4. The `harness_eval_*` family in § 3.3 functionally replaces them.

---

## 4. Dashboards

10 dashboards under the **"Claude Agent Harness"** folder. UIDs are stable; bookmarks and Data Links use them.

| # | UID | Main function | Headline panels |
|---|---|---|---|
| **00** | `casdk-overview` | **Mode-aware integration hub.** First stop. Active Mode panel value-maps to deep-link the relevant Tier 3 dashboard. | Active Mode, Run Config, Run Elapsed; 5 universal KPIs (Spend, Cache Hit, Edit Accept, Tokens, Error Rate) with Data Links to D10/D30/D40/D50; Spend by Model + Cache Hit Rate trends; three collapsed mode-aware rows; System Health row (workspace files, checkpoint size, agent RSS). |
| **10** | `casdk-sdk-cost` | **Cost & Spend.** Where the money goes. | Spend rate, total spend, $/accepted-edit, projected monthly. Spend by model / query_source / effort / terminal_type. $/commit + $/PR with empty-panel caveats. |
| **20** | `casdk-sdk-productivity` | **Session & Productivity.** | Active sessions, sessions started, net LoC (`sum_over_time`, not `increase`). Sessions by start_type, LoC added/removed, CLI vs user time, harness session duration P50/P95. |
| **30** | `casdk-sdk-cache` | **Cache & Token Efficiency.** Highest-leverage dashboard per spec — cache health directly drives cost. | Cache hit rate (overall + threshold-banded; ≥90% green / 60-80% amber / <60% red), effective $/Mtok, cache read:creation ratio, hit rate over time, hit rate by model, token mix stacked area, output:input ratio by model, hit rate by query_source. |
| **40** | `casdk-sdk-tools` | **Tool & Code Quality.** | Edit acceptance rate overall + per-tool small-multiples. Rejection rate by `language` and `exported_source`. Most-used tools horizontal bar. Harness-side tool calls by status. Stage-3 panels (P50/P95 duration, MCP tool calls, Bash frequency) noted as deferred. |
| **50** | `casdk-sdk-reliability` | **Reliability & Errors.** Prometheus-only subset; richer SDK error breakdown needs Loki. | Harness error rate (proxy), counts (error/timeout/success), per-agent error rate, request status by agent, agent duration P50/P95/P99. Collapsed Stage-3 placeholder row for status-code segmentation + TTFT + retries. |
| **60** | `casdk-mode-interactive` | **Mode: Interactive.** Active during `make interactive`. | Session header (sessions, prompts, responses, P95 duration), conversation flow (overlaid prompts + responses rate), tool usage time-series + bar, message types stacked area. Collapsed SDK Economics row with deep-links. |
| **65** | `casdk-mode-autonomous` | **Mode: Autonomous.** Active during `make autonomous`. | Task progress header (completed / pending / failed / completion %), commits over time + LoC delta, agent duration P50/P95 by agent, task progress as time-series. Collapsed SDK Economics row. |
| **70** | `casdk-cgf` | **Mode: CGF Optimization.** Active during `make optimize`. | Run Config table, Phase Progression State Timeline (was bargauge), Iteration + Run Elapsed + Active Path/Resource, Cost + Tokens + Cache Hit + Cost-by-Model. Eval Framework row (collapsed) with phase duration + tokens-to-goal + scenarios + arm scores + judge no-decisions. |
| **99** | `casdk-raw-events` | **Stage 3 placeholder.** Text panel explaining the Loki prerequisite. Holds the UID for cross-dashboard Data Links. | (Single Text panel; activates when Loki lands.) |

**Shared conventions across all 10:**

- `schemaVersion: 39` (Grafana 11.3+ `Scenes`-powered dashboards).
- Datasource UID pinned to `prometheus` (provisioned via `config/monitoring/datasources/prometheus.yml`). Panel `datasource` fields use the literal UID, **not** `${datasource}` — Grafana doesn't resolve template variables in panel `datasource.uid` fields, only in query expressions.
- 5 shared template variables: `$datasource`, `$mode`, `$resource`, `$path`, `$model`. (`$user` and `$loki_datasource` deliberately omitted — single-user; no Loki.)
- Dashboard Links bar at top of every dashboard linking to all siblings.
- `null+nan → "—"` gray on every Stat / Table panel.
- Structural color only: gray=context, blue=informational, green=healthy, amber=warning band, red=error/failure, purple=optimize-mode discriminator on D00.

---

## 5. Alert rules

13 rules across 4 groups in `config/monitoring/alerting.yml`. AlertManager (`prom/alertmanager:v0.27.0`) routes to `alertmanager-webhook` by default — a stdlib-Python debug receiver that prints payloads to stdout. Replace with Slack/email/PagerDuty config in `config/monitoring/alertmanager.yml` for real alerting.

| Group | Rule | Threshold | Severity | Purpose |
|---|---|---|---|---|
| `agent_alerts` | `HighErrorRate` | `harness_agent_requests_total{status="error"}` rate > 0.05 for 5m | warning | Approximates SDK API-error rate (Loki proxy until Stage 3). |
| `agent_alerts` | `SlowResponseTime` | `harness_agent_duration_seconds` P95 > 30s for 10m | warning | Long agent cycles. |
| `agent_alerts` | `NoActiveSessions` | `harness_agent_active_sessions == 0` for 15m | info | Quiet harness — informational only. |
| `resource_alerts` | `HighMemoryUsage` | `harness_memory_usage_bytes > 7GB` for 5m | warning | Process RSS. |
| `resource_alerts` | `LargeCheckpointSize` | `harness_checkpoint_size_bytes > 1GB` for 10m | info | Checkpoint hygiene. |
| `resource_alerts` | `WorkspaceFilesHigh` | `harness_workspace_files_total > 10000` for 30m | info | Bloated workspace. |
| `cost_alerts` | `HighAPICost` | Rolling spend > $10/hour for 1h | warning | Standing operational cap. |
| `cost_alerts` | `HighTokenUsage` | Per-model rate > 1M tok/hour for 1h | info | Sustained heavy usage. |
| `cost_alerts` | `CostSpike` | `increase(claude_code_cost_usage_USD_total[1h]) > $30` for 5m | warning | Sudden spike vs typical operational rate (~3×). |
| `cost_alerts` | `CacheHitRateDegraded` | Hit rate < 60% for 30m (gated by non-zero traffic) | warning | Cache busted — investigate CLAUDE.md volatility, mid-session model switches. |
| `cost_alerts` | `TokenBurnSustained` | `rate(claude_code_token_usage_tokens_total[5m]) > 100k tok/s` for 10m | **critical** | Catastrophic burn — runaway agent loop. |
| `pipeline_alerts` | `OTelCollectorDown` | `up{job="otel-collector-self"} == 0` for 2m | **critical** | Collector unreachable → SDK telemetry stops flowing. |
| `pipeline_alerts` | `AlertManagerDown` | `absent(up{job="alertmanager"}) or up == 0` for 5m | **critical** | Prometheus cannot deliver alerts. |

**Deferred:** The upstream spec's `SustainedRetryExhaustion` alert is documented as a commented-out stub at the bottom of `cost_alerts` because it requires Loki — `api_retries_exhausted` is an OTLP event, not a metric. Until Loki (Stage 3) lands, `HighErrorRate` is the proxy.

---

## 6. Non-obvious behaviors worth knowing

These are the gotchas that have surfaced during the refactor. Re-read before debugging "why is this panel empty" or "why didn't this alert fire."

1. **`metric_expiration: 5m` on the collector.** SDK metrics age out 5 minutes after the agent process stops emitting. An idle stack returns "no recent data" on instant queries — the data IS in Prometheus, but the staleness window has elapsed. Verify with range queries (`[24h]`) instead.

2. **Datasource UID pinning is mandatory.** The provisioner refuses to update a datasource's UID in place — if you change `uid:` in `datasources/prometheus.yml`, Grafana logs `"Datasource provisioning error: data source not found"` and the Grafana container enters restart-loop. The current config uses a `deleteDatasources:` directive to recreate cleanly. Don't remove that block.

3. **`${datasource}` doesn't interpolate in panel `datasource.uid`.** Only in query expressions. Use the literal `"uid": "prometheus"` in every panel JSON. The template variable still works for query-level dynamic switching if a second datasource is ever added.

4. **SDK metric-name correction.** Upstream Anthropic spec lists the edit-decision counter as `claude_code_code_edit_tool_decision_count_total`. **Reality: SDK emits `claude_code_code_edit_tool_decision_total`** (no `_count` infix). Every D40 PromQL panel uses the corrected name.

5. **Prometheus label-collision rename.** The scrape job applies a `source="claude-sdk-harness"` label. The SDK separately emits its own `source` attribute on `code_edit_tool_decision` (with values `config`/`hook`/`user_permanent`/…). Prometheus resolves the collision by renaming the SDK's attribute to **`exported_source`**. Same applies to `job` → `exported_job`. D40 "Rejection rate by source" panels query `exported_source`.

6. **LoC counters are delta-style.** Use `sum_over_time(...[$__range])`, **not** `increase()`, on `claude_code_lines_of_code_count_total`. `increase()` extrapolates them to nonsense values — single most common dashboard mistake in community examples.

7. **`claude_code_commit_count_total` and `pull_request_count_total` are typically empty.** They fire only when Claude in-session invokes `git commit` / `gh pr create`. CGF optimization runs don't commit; autonomous mode may, depending on workflow. D10's $/commit and $/PR panels carry explicit caveats; expect them to render empty on a typical workload.

8. **`claude_code_active_time_seconds_total{type="user"}` is interactive-only.** The "Productivity multiplier (cli/user)" panel divides by zero on non-interactive workloads. D20 documents this; treat the metric as directional, never as a performance KPI.

9. **Compose env passthrough is enumeration-based.** The `environment:` block in `docker-compose.yml` lists explicit `${VAR:-default}` entries. Variables not enumerated never reach the container even if set in `.env`. OTel envvars (`OTEL_*`) use literal values, not shell-interpolated, so host-shell envvars cannot leak into the harness containers.

10. **Required SDK envvars (don't skip).** `CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_METRICS_EXPORTER=otlp` + `OTEL_LOGS_EXPORTER=otlp`. Without the latter two, the CLI silently emits nothing — silent total dropout.

11. **`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative` pinned defensively.** Defensive against future SDK default changes. VictoriaMetrics, Mimir, and Grafana Cloud silently drop delta-temporality metrics; we use Prometheus, but the pin costs nothing.

12. **`HOME=/home/claude` pinned in `_build_sdk_options()`.** Sub-agent Bash tools that expand `~` (e.g. research-team `~/Documents/ClaudeResearch/...`) had been observed resolving `HOME` to `/root` despite the runtime user being `claude`. The explicit pin removes the ambiguity for the entire SDK subprocess chain.

13. **Stale `session_id` labels from older SDK versions.** Older series (e.g., `service_version: 2.1.128`) carry a `session_id` label despite our `OTEL_METRICS_INCLUDE_SESSION_ID=false`. New series from current SDK versions do not. Stale series age out at `metric_expiration: 5m` plus Prometheus retention. Not actionable.

---

## 7. Data persistence and historical runs

Three retention layers shape what dashboards can show.

| Layer | Retention | Effect |
|---|---|---|
| **OTel Collector** `metric_expiration` | 5 min | If a metric stops being scraped (e.g., agent shuts down), the collector drops it from its `/metrics` exposition after 5 min.  Has no effect on what's already in Prometheus. |
| **Prometheus TSDB** | `PROMETHEUS_RETENTION` (default 30d) | Every scraped sample is durably stored with its timestamp.  Trend panels read from this. |
| **Singleton helpers** | n/a | `record_run_config` / `record_run_path` / `init_run_phases` / `record_run_start` all call `.clear()` before setting the new value.  Each gauge has "current active run" semantic; only the most recent emit is exposed.  This affects what *new* scrapes see — historical samples already in the TSDB are unchanged. |

### How dashboards behave for past runs

- **Trend panels** (time-series like Spend by Model, Cache Hit Rate Over Time, Phase Progression State Timeline, Task Progress Over Time, etc.) — display every sample within the dashboard time range.  Set the time picker to "Last 7 days" and the panel renders the last week.
- **Stat panels with `lastNotNull`** (Spend, Cache Hit, Edit Accept Rate, etc.) — evaluate at the *end* of the dashboard time range and reduce to the most recent non-null sample.  Set the range to a past hour and the stat reflects what was happening then.
- **Instant `== 1` panels** (D00/D70 Run Config table, D00 Active Mode) — Grafana evaluates these at the end of the dashboard time range.  Set the range to "yesterday 14:00 → 15:00" and the Run Config table shows whatever run was active at 15:00 yesterday.  Genuinely useful for historical drill-down.

So **yes, data from just-finished runs appears in the dashboards** — within retention.  Trend panels show it automatically; current-state panels (Run Config, Phase Progression rightmost segment) require shifting the time picker back to encompass the run.

### What is not currently set up

- **No run-history listing UI.** The State Timeline on D70 is the closest thing — colored bars show when each phase was active over the dashboard window, which implicitly lists past runs as colored segments separated by gaps.  But there's no "list all runs in the last week" Grafana panel.
- **No durable per-run summary store.** Prometheus is the only persistence layer for metrics.  On-disk artifacts (`CHANGELOG.md`, `summary.json`, `task_list.json` per the run's workspace directory) exist but are not surfaced in Grafana.  To inspect a past run's full state, walk the workspace tree on disk.
- **No fine-grained event drill-down.** That requires Loki (see § 9.1) — `prompt.id` and `session.id` would let you reconstruct an individual session from its event stream.

### Practical recipes

| Task | How |
|---|---|
| See what ran yesterday | Open D70 → time picker → "yesterday".  Phase Progression shows the run as a sequence of colored segments; Run Config row reflects the config at end of range. |
| Compare two runs | Open two browser tabs with D00 / D70 at different time ranges. |
| Find the cost of a specific past run | D10, set time range to the run's window.  "Spend (selected range)" stat shows total. |
| Investigate a cache regression | D30, "Last 24 hours" or wider.  Cache Hit Rate Over Time visualizes the drop; switch to per-model variant to identify which model lost cache health. |
| Audit alert firings | D-pipeline rules in Prometheus (`/api/v1/rules`); past firings: `ALERTS{alertname="..."}` over a wide time range. |

---

## 8. Maintenance

### Re-audit cadence

After any PR that touches:

- `src/harness/monitoring.py` (instrument definitions)
- `src/harness/optimization/_orchestrator_phases/` (run-level + eval emitters)
- `src/harness/interactive.py` (interactive session emitters)
- `src/harness/agent.py` (operational emitters + SDK options)
- `config/monitoring/otel-collector.yml` or `prometheus.yml` (pipeline config)
- Any SDK bump that might change `claude_code_*` emission

…re-run the live capture below and verify the inventory in § 3 matches.

### Live capture command

Ground truth for what flows at runtime. Same pattern as `feedback_verification.md` documents for code: unit tests passing ≠ feature working.

```bash
# Single-resource CGF path
make up
make optimize FIXTURE=python-expert
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | jq -r '.data[]' \
  | grep -E '^(harness_|cgf_|claude_code_)' \
  | sort > /tmp/live-metrics-single.txt

# Multi-resource CGF path
make optimize FIXTURE=iac-team
# ... same capture command, redirect to /tmp/live-metrics-multi.txt

# Interactive mode (run a handful of prompts that exercise text, Read, Bash, Write)
make interactive
# ... same capture, redirect to /tmp/live-metrics-interactive.txt
```

**Triage:** any metric in this doc but missing from the live capture is a gap (env-var / collector-config / wire-up fix, or defer to Stage 3). Any metric in the live capture but not in this doc is a new metric the SDK or harness started emitting — investigate and add a row to § 3.

### Common operational tasks

| Task | Command / file |
|---|---|
| Bring stack up | `make up` |
| Add a new alert | Edit `config/monitoring/alerting.yml`; `docker compose restart prometheus` |
| Add a new dashboard | Drop JSON into `config/monitoring/dashboards/`; Grafana auto-reloads every 10s (`updateIntervalSeconds`) |
| Add a new instrument | `src/harness/monitoring.py` (definition) + call site + unit test in `tests/unit/test_monitoring.py` + add a row in § 3 of this doc |
| Verify rule syntax | `curl -s 'http://localhost:9090/api/v1/rules' \| jq` and `curl -s 'http://localhost:9090/api/v1/query?query=<expr>'` |
| Check provisioning errors | `docker compose logs grafana \| grep -iE "level=error\|level=warn.*dashboard"` |
| Diff against historical baseline | `git diff --stat config/monitoring/dashboards/` |

### Authoring conventions for new dashboards

If you add an 11th dashboard, match the existing 10:

- File name: `NN-name.json` where `NN` follows the tier scheme (00 hub / 10–50 SDK / 60+ mode-specific / 99 utility).
- `schemaVersion: 39`.
- `uid: casdk-...` — stable, short, lowercase-kebab.
- Add tags `["claude", "harness"]` (plus `["cgf"]` if CGF-specific).
- Copy the 5-variable templating block + the Dashboard Links bar (with self excluded) from any existing dashboard.
- Every panel: `"datasource": {"type": "prometheus", "uid": "prometheus"}` literal.
- Every Stat / Table panel: include the `null+nan → "—"` mapping.
- Add a row to § 4 of this doc.

---

## 9. Possible Observability Follow-ups

Both deferred indefinitely per the v2 dashboard spec — turn on when there's a clear ROI signal that aggregate Prometheus metrics can't explain.

### 8.1 Loki + log pipeline

**What it unlocks:**

- Per-request cost attribution ("which API call cost $1.40?")
- Tool execution P50/P95/P99 latency by tool name (LogQL `quantile_over_time` on `tool_result` `duration_ms`)
- Session reconstruction via `prompt.id` join across events
- Error detail: 429 vs 5xx vs 529 segmentation (the SDK metric counts errors but doesn't segment by code)
- Compaction event correlation with metric dips
- D99 (Raw Events) dashboard activation
- The D40 / D50 panels marked "Loki-dependent"
- The `SustainedRetryExhaustion` alert from § 5

**Infrastructure cost:** one additional container (~200 MB RAM for single-tenant monolithic Loki with filesystem storage), plus OTel Collector configured with a Loki exporter.

**Concrete changes:**

- Add `grafana/loki:3.x` service to `docker-compose.yml`.
- Add `loki` exporter to `otel-collector.yml`; replace `[debug]` in the `logs:` pipeline.
- Add a Loki datasource to `config/monitoring/datasources/`.
- Verify the `service_name="claude-code"` label survives the OTLP→Loki path (Loki uses `service_name`, not `service.name`, after promotion).
- Re-introduce a `$loki_datasource` template variable on dashboards that consume Loki.
- Restore the commented-out `SustainedRetryExhaustion` rule in `alerting.yml`.

### 8.2 Tempo + traces beta

**What it unlocks:**

- **TTFT (time to first token)** P50 / P95 by model — `ttft_ms` on `claude_code.llm_request` spans. Highest-value traces panel; add first.
- Per-prompt execution waterfall — nested causal structure showing LLM thinking → tool dispatch → user permission wait → tool execution → LLM continuation, with wall-clock alignment.
- **`TRACEPARENT` propagation** — Bash tool subprocesses inherit the trace context. OTel-instrumented test runners, linters, or eval harnesses become child spans automatically. For the CGF pipeline, this could show a single trace from prompt through eval scoring without custom wiring.
- `stop_reason` per LLM call (`end_turn` / `max_tokens` / `tool_use`) — frequent `max_tokens` hits indicate the model is being cut off mid-thought.
- Per-request retry counts on **successful** requests (`attempt` attribute on `llm_request` spans). The `api_retries_exhausted` event only fires on terminal failure; traces show silent 2nd-attempt successes.
- `blocked_on_user` latency — explicit measurement of human approval time on permission-gated operations.

**Infrastructure cost:** one additional container (Tempo ~150 MB RAM). Beta status means the span schema may change between Claude Code releases; dashboard panels built on trace queries carry upgrade risk.

**Concrete changes:**

- Add `grafana/tempo:2.x` to `docker-compose.yml`.
- Set `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` and `OTEL_TRACES_EXPORTER=otlp` on the agent service env in `docker-compose.yml`.
- Add an `otlp` traces exporter to `otel-collector.yml`; replace `[debug]` in the `traces:` pipeline.
- Add a Tempo datasource to `config/monitoring/datasources/`.
- Build the deferred Stage 3 panels in D50 (currently a collapsed Text-panel placeholder).
