# config/monitoring/ — Observability Stack Configuration

This directory holds the **provisioned** configuration for the harness's
observability stack: OTel Collector pipeline, Prometheus scrape jobs +
alert rules, Grafana datasources + dashboards, AlertManager routing.

**Authoritative reference:** `docs/OBSERVABILITY.md` (in the repo root).
That doc explains the architecture, every metric the harness can emit,
all 10 dashboards and their main functions, all 13 alert rules, gotchas
worth knowing, data persistence semantics, and Stage 3 follow-ups. Read
it before adding panels or alerts.

## Quick map

```
config/monitoring/
├── otel-collector.yml      OTLP receiver + Prometheus exporter pipeline
├── prometheus.yml          Scrape jobs (main-agent, otel-collector-sdk, etc.)
├── alerting.yml            13 alert rules across 4 groups
├── alertmanager.yml        Routing config; default → alertmanager_webhook_debug.py
├── alertmanager_webhook_debug.py   Stdlib-Python debug receiver (replace for prod)
├── datasources/
│   └── prometheus.yml      Pinned uid: prometheus; deleteDatasources block required
└── dashboards/
    ├── dashboard-provider.yml      "Claude Agent Harness" folder, auto-reload 10s
    ├── 00-harness-overview.json    Mode-aware integration hub
    ├── 10-cost.json                Cost & Spend
    ├── 20-cache.json               Cache & Token Efficiency (highest-leverage)
    ├── 30-productivity-tools.json  Productivity & Tools (combined session + edit quality)
    ├── 40-reliability.json         Errors & Reliability
    ├── 50-mode-interactive.json    Mode: Interactive (make interactive)
    ├── 60-mode-autonomous.json     Mode: Autonomous (make autonomous)
    ├── 70-mode-cgf.json            Mode: CGF Optimization (make optimize)
    └── 99-raw-events.json          TBD: Raw Events (Stage 3 placeholder, Loki-dependent)
```

## When editing here

- **Adding an alert** — Edit `alerting.yml`. Reload via `docker compose restart prometheus`. Verify with `curl localhost:9090/api/v1/rules | jq` and a one-shot expr evaluation against `/api/v1/query`. Update `docs/OBSERVABILITY.md` § 5 alert table.
- **Adding a dashboard** — Drop new JSON into `dashboards/`. Grafana picks it up within ~10s. UID convention: `casdk-...` (short, lowercase-kebab). Match the existing 10-dashboard conventions (schemaVersion 39, 5 shared variables, Dashboard Links bar, `null+nan → "—"` mapping, datasource literal `"uid": "prometheus"`). Add a row to `docs/OBSERVABILITY.md` § 4.
- **Touching a dashboard query** — Re-verify in browser kiosk mode (`/d/<uid>?kiosk`). Run a `make optimize FIXTURE=python-expert` smoke if your change depends on live data.
- **Changing collector config** — `docker compose restart otel-collector` + verify metrics still flow with `curl localhost:9090/api/v1/label/__name__/values | jq -r '.data[]' | grep claude_code_`.
- **Changing datasource UID** — Grafana refuses in-place updates. The `deleteDatasources:` block in `datasources/prometheus.yml` is what lets the new definition land cleanly. Don't remove it.

## Other operator-facing surfaces (outside this directory)

Two surfaces serve operators alongside this dashboard stack — they
live elsewhere in the tree but answer adjacent "what's happening"
questions. Worth knowing about so we don't accidentally rebuild what
already exists.

### RUN_REPORT.md — file-based parallel to Grafana

Rendered by `src/harness/optimization/run_report.py`. Output:
`workspace/{spec}/sessions/RUN_REPORT.md`. Pure derived view over
`optimization-state.json` + `*.summary.json` + `eval/execution-eval-round-*.json`
+ `CHANGELOG.md` — no new persistence (one exception: `phase_timings`
added to the state file, ~10 LOC in `_advance_phase()`).

- **Regenerates** on every phase boundary and per-resource event,
  piggybacked on `_save_state()` — no new write cadence.
- **Re-render manually:** `make report SPEC=workspace/<name>`.
- **Disable:** `CGF_RUN_REPORT=0` (default on).
- **Reset:** `cgf-clean` wipes it along with the rest of session state;
  next `make optimize` regenerates from scratch.

Mermaid gantt + accessible table for phase progression; per-resource
verdict table; collapsible iteration history; auto-emitted open-issues
callouts (F21 unwinnable, F25 GENERATE timeout, pending r2 verdict).

**Deliberate non-goals** (don't try to make it these):
- Not a Grafana replacement — Grafana owns live ops time-series, alerts,
  oncall, cross-run trends.
- Not a replacement for `optimization-state.json` (machine truth) or
  `CHANGELOG.md` (human-authored narrative; the report *links to* it).
- Not a cross-run comparison view ("was today better than yesterday?").
- Not a sign-off workflow — Stage 4 `--review` mode adds checkpoints;
  the report renders the *current* checkpoint state but doesn't host UI.

**Deferred TODO:** `--watch` mode (tail-the-file via entr/watchman).
Defer until the report has been in the workflow for a week and we know
the cadence operators actually want.

### Eval framework instruments (Grafana D7)

The eval-framework metrics (`harness_eval_*`) flow through the same
Prometheus pipeline as everything else here, but their call sites live
in `_orchestrator_phases/execution_eval.py` and `graders/llm_judge.py`.
When a panel on D7 goes empty, check those modules' emit sites and
the singleton-helper semantics in `src/harness/monitoring.py`.

---

## Non-obvious gotchas (full list in `docs/OBSERVABILITY.md` § 6)

- Panel `datasource` fields must use the **literal UID** `"uid": "prometheus"` — Grafana doesn't interpolate `${datasource}` in `datasource.uid`.
- SDK emits `claude_code_code_edit_tool_decision_total`, **not** `_count_total` (upstream spec is wrong).
- SDK's `source` label lands as `exported_source` after Prometheus rename — D3 queries use that.
- LoC counters are delta-style — use `sum_over_time`, not `increase`.
- Run-level gauges (`harness_run_config_info`, `harness_run_path_info`, `harness_run_phase_info`, `harness_run_iteration`, `harness_run_start_timestamp`) have singleton semantic: each emit `.clear()`s prior series. Each gauge represents the **currently active** run, never a history of all runs. Trend queries against TSDB still see history.
- Phase Progression panels in D7 use `max by (phase) (last_over_time(...[2m]))` to dedup across historical resources and forward-fill within-scrape gaps. If you wire a new phase, add it to `SINGLE_PATH_PHASES` or `MULTI_PATH_PHASES` in `src/harness/monitoring.py` AND add a corresponding query target (one per phase) in D7's two State Timeline panels.
- **State-timeline row order = refId order, not alphabetical or `organize`-controllable.** Prometheus returns each series as a separate frame whose value field is literally named `"Value"` (only `displayNameFromDS` carries the legend), so `transformations: [{id: "organize", indexByName: {...}}]` is a no-op — `indexByName` matches field NAMES and every field is "Value". To control row order in a state-timeline, split into one query per series with refIds A, B, C, … in the desired order; state-timeline renders rows in frame order, and frames come back in refId order. D7's Phase Progression panels use this pattern (5 queries for single-resource, 10 for multi-resource).
