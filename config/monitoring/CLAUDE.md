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
    ├── 10-sdk-cost.json            Cost & Spend
    ├── 20-sdk-productivity.json    Session & Productivity
    ├── 30-sdk-cache.json           Cache & Token Efficiency (highest-leverage)
    ├── 40-sdk-tools.json           Tool & Code Quality
    ├── 50-sdk-reliability.json     Reliability & Errors
    ├── 60-mode-interactive.json    Mode: Interactive (make interactive)
    ├── 65-mode-autonomous.json     Mode: Autonomous (make autonomous)
    ├── 70-mode-cgf.json            Mode: CGF Optimization (make optimize)
    └── 99-raw-events.json          Stage 3 placeholder (Loki-dependent)
```

## When editing here

- **Adding an alert** — Edit `alerting.yml`. Reload via `docker compose restart prometheus`. Verify with `curl localhost:9090/api/v1/rules | jq` and a one-shot expr evaluation against `/api/v1/query`. Update `docs/OBSERVABILITY.md` § 5 alert table.
- **Adding a dashboard** — Drop new JSON into `dashboards/`. Grafana picks it up within ~10s. UID convention: `casdk-...` (short, lowercase-kebab). Match the existing 10-dashboard conventions (schemaVersion 39, 5 shared variables, Dashboard Links bar, `null+nan → "—"` mapping, datasource literal `"uid": "prometheus"`). Add a row to `docs/OBSERVABILITY.md` § 4.
- **Touching a dashboard query** — Re-verify in browser kiosk mode (`/d/<uid>?kiosk`). Run a `make optimize FIXTURE=python-expert` smoke if your change depends on live data.
- **Changing collector config** — `docker compose restart otel-collector` + verify metrics still flow with `curl localhost:9090/api/v1/label/__name__/values | jq -r '.data[]' | grep claude_code_`.
- **Changing datasource UID** — Grafana refuses in-place updates. The `deleteDatasources:` block in `datasources/prometheus.yml` is what lets the new definition land cleanly. Don't remove it.

## Non-obvious gotchas (full list in `docs/OBSERVABILITY.md` § 6)

- Panel `datasource` fields must use the **literal UID** `"uid": "prometheus"` — Grafana doesn't interpolate `${datasource}` in `datasource.uid`.
- SDK emits `claude_code_code_edit_tool_decision_total`, **not** `_count_total` (upstream spec is wrong).
- SDK's `source` label lands as `exported_source` after Prometheus rename — D40 queries use that.
- LoC counters are delta-style — use `sum_over_time`, not `increase`.
- Run-level gauges (`harness_run_config_info`, `harness_run_path_info`, `harness_run_phase_info`, `harness_run_iteration`, `harness_run_start_timestamp`) have singleton semantic: each emit `.clear()`s prior series. Each gauge represents the **currently active** run, never a history of all runs. Trend queries against TSDB still see history.
- Phase Progression panels in D70 use `max by (phase) (last_over_time(...[2m]))` to dedup across historical resources and forward-fill within-scrape gaps. If you wire a new phase, add it to `SINGLE_PATH_PHASES` or `MULTI_PATH_PHASES` in `src/harness/monitoring.py` AND add a corresponding query target (one per phase) in D70's two State Timeline panels.
- **State-timeline row order = refId order, not alphabetical or `organize`-controllable.** Prometheus returns each series as a separate frame whose value field is literally named `"Value"` (only `displayNameFromDS` carries the legend), so `transformations: [{id: "organize", indexByName: {...}}]` is a no-op — `indexByName` matches field NAMES and every field is "Value". To control row order in a state-timeline, split into one query per series with refIds A, B, C, … in the desired order; state-timeline renders rows in frame order, and frames come back in refId order. D70's Phase Progression panels use this pattern (5 queries for single-resource, 10 for multi-resource).
