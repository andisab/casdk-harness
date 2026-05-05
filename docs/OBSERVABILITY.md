# Observability

The harness ships a self-contained observability stack: native OpenTelemetry signals
from the Claude Code CLI flow through a sidecar OTel Collector into Prometheus,
where they power two pre-provisioned Grafana dashboards and a set of AlertManager-
delivered alerting rules.

## Architecture

```
┌──────────────────┐  OTLP/gRPC  ┌──────────────────┐  scrape  ┌────────────┐
│ Claude Code CLI  ├────────────►│  OTel Collector  ├─────────►│ Prometheus │
│  (in main-agent) │  :4317      │  (claude_code_*) │  :8889   │  (TSDB)    │
└──────────────────┘             └──────────────────┘          └─────┬──────┘
                                                                     │
            ┌────────────────────────────────────────────────────────┤
            │ scrape :9090 (harness_*)                               │
            │ scrape :8888 (otelcol_*)                               │
┌───────────┴──────┐                                                 │
│   main-agent     │                                                 │
│ (harness_*       │                                                 │
│  prometheus_     │            ┌─────────────────┐  alert push      │
│  client port)    │            │  AlertManager   │◄─────────────────┘
└──────────────────┘            └────────┬────────┘
                                         │ webhook
                                         ▼
                                ┌──────────────────┐         ┌─────────┐
                                │ webhook receiver │         │ Grafana │
                                │ (logs to stdout) │         │ (UI/    │
                                └──────────────────┘         │  panels)│
                                                             └─────────┘
```

Two metric sources feed Prometheus:

1. **Native SDK telemetry (`claude_code_*` namespace)** — emitted by the Claude Code
   CLI when `CLAUDE_CODE_ENABLE_TELEMETRY=1` and the OTLP exporter envvars are set
   (compose hardcodes both — see `docker-compose.yml`). The collector receives OTLP
   on `:4317` (gRPC) or `:4318` (HTTP) and re-exposes on `:8889` for Prometheus.
2. **Harness instruments (`harness_*` and `cgf_*` namespaces)** — `prometheus_client`
   counters/gauges/histograms inside `src/harness/monitoring.py`, scraped from each
   agent container's `:9090` (host-mapped to `:9091`+).

## Service map

| Service | Container | Host port | Purpose |
|---|---|---|---|
| OTel Collector | `claude-otel-collector` | `:4317` (gRPC), `:4318` (HTTP) | OTLP ingest from SDK |
| Prometheus | `claude-prometheus` | `:9090` | TSDB + rule evaluation |
| Grafana | `claude-grafana` | `:3000` | Dashboards (default login: `admin` / `${GRAFANA_PASSWORD:-changeme123}`) |
| AlertManager | `claude-alertmanager` | `:9093` | Alert routing |
| AlertManager webhook (debug) | `claude-alertmanager-webhook` | `:9099` | Logs alert payloads to stdout |

`8888` (collector self-metrics) and `8889` (SDK metrics exporter) are intentionally
**not** mapped to the host — they're scraped over the docker network. Inspect them
via the Prometheus UI at `http://localhost:9090`.

## Dashboards

Two dashboards are auto-provisioned via `config/monitoring/dashboards/dashboard-provider.yml`.
Files are watched with `updateIntervalSeconds: 10`, so editing the JSON on disk
propagates without a Grafana restart.

### Overview (`/d/casdk-overview`)

Single-pane dashboard for day-to-day use. Five rows:

| Row | Panels |
|---|---|
| Session Health | Active sessions, sessions started (1h), prompts (1h), tokens (1h), cost (1h), cache hit ratio |
| Tokens & Cost | Tokens/min by model+query_source, cost/hour by model, token type mix (stacked), cumulative cost, cost per session, top models |
| Tools & Messages | Top tools, tool error rate, message type distribution, agent request rate by status |
| Latency | Agent request duration p50/p95/p99, session duration heatmap |
| System (collapsed) | Checkpoint size, workspace files, memory usage by component |

### CGF (`/d/casdk-cgf`)

CGF optimization framework activity:

| Row | Panels |
|---|---|
| Tracer Activity | Spans collected/exported (selected range), adapter transform success rate, mean composite reward, spans-by-kind, spans-by-exporter |
| Optimization Quality | Composite reward distribution heatmap, feedback dimensions (per resource_type/dimension), adapter transforms by status |
| Future (collapsed) | Stage 3 eval-harness placeholder — populated when phase-transition + per-iteration eval metrics land |

## Adding a new alert rule

Rules live in `config/monitoring/alerting.yml`, evaluated by Prometheus, routed by
AlertManager. Convention: harness metrics use `harness_*`, SDK metrics use
`claude_code_*`.

1. Add a rule under an existing `groups[*].rules` list (or create a new group):

   ```yaml
   - alert: MyAlertName
     expr: |
       histogram_quantile(0.99, rate(harness_agent_duration_seconds_bucket[5m])) > 60
     for: 5m
     labels:
       severity: warning
     annotations:
       summary: "Agent p99 latency > 60s"
       description: "Agent {{ $labels.agent }} p99 is {{ $value }}s."
   ```

2. Validate locally before committing:

   ```bash
   docker run --rm --entrypoint promtool \
     -v "$PWD/config/monitoring/alerting.yml:/x/alerting.yml:ro" \
     prom/prometheus:latest check rules /x/alerting.yml
   ```

3. Reload Prometheus to pick up the new rule (no restart needed):

   ```bash
   curl -XPOST http://localhost:9090/-/reload
   ```

   Or, if running with the bundled compose, recreate the prometheus service:
   `docker compose up -d --force-recreate prometheus`.

4. Verify the rule appears via `http://localhost:9090/rules`.

## First-response actions

Common alert payloads and what to check first.

| Alert | Likely cause | First-response |
|---|---|---|
| **`OTelCollectorDown`** | Collector container crashed or OOM-killed | `docker compose ps otel-collector` and `docker compose logs otel-collector` |
| **`AlertManagerDown`** | AM container down or scrape job misconfigured | `docker compose ps alertmanager`; check `prometheus.yml` alertmanager target |
| **`HighErrorRate`** | Agent throwing — bad permissions, API timeouts, or tool failures | `make logs-main`; look for ERROR-level entries; check `harness_tool_calls_total{status="error"}` |
| **`SlowResponseTime`** | API throttling, retries, or large prompt context | Check Prometheus `claude_code_token_usage_tokens_total{type="input"}` rate; look for token spikes |
| **`HighAPICost`** | Loops, oversized prompts, or expensive model in subagent role | Inspect `Cost ($/hour) by Model` panel on Overview dashboard; review `query_source` split |
| **`HighTokenUsage`** | Same as above — usually correlated with HighAPICost | Same panel |
| **`HighMemoryUsage`** | Large workspace or runaway tracer | `docker stats` and check `harness_memory_usage_bytes{component}` panel |
| **`LargeCheckpointSize`** | Old/stale checkpoints not pruned | `ls -la memory/checkpoints/` and `make checkpoint-clean` if available |
| **`NoActiveSessions`** | Informational — main-agent idle for 15m | None required; suppress with a silence in AlertManager UI if expected |

## Adding a real receiver

The bundled `webhook-debug` receiver only logs to stdout — fine for development,
not actionable in production. To wire Slack / email / PagerDuty, edit
`config/monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'slack-prod'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#alerts'
        send_resolved: true

route:
  receiver: 'slack-prod'      # change default
  routes:
    - matchers: [severity = critical]
      receiver: 'slack-prod'  # or a separate pager-style receiver
```

Then validate and reload:

```bash
docker run --rm --entrypoint amtool \
  -v "$PWD/config/monitoring/alertmanager.yml:/x/alertmanager.yml:ro" \
  prom/alertmanager:v0.27.0 check-config /x/alertmanager.yml
docker compose restart alertmanager
```

## Testing alert delivery

Inject a synthetic alert directly via the AM v2 API to test routing without
waiting for a rule to fire:

```bash
curl -XPOST -H 'Content-Type: application/json' \
  --data '[{
    "labels": {"alertname":"TestAlert","severity":"warning"},
    "annotations": {"summary":"manual smoke test"},
    "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }]' http://localhost:9093/api/v2/alerts

# After ~10s (group_wait), check the receiver:
docker compose logs alertmanager-webhook | tail -30
```

## Why bundled, not external?

The harness deliberately routes its own telemetry to the bundled collector
rather than inheriting host-shell OTel envvars (which a developer's Claude Code
configuration commonly sets to a personal/corporate collector). That isolation
is hardcoded in `docker-compose.yml`; to redirect to an external collector for
production, edit the `OTEL_EXPORTER_OTLP_ENDPOINT` value directly or use a
docker-compose override file.

## What's not here

- **Tracing UI (Tempo / Jaeger).** The collector receives OTLP traces and
  ships them to a debug exporter (stdout). Add a Tempo backend if you need
  span querying — out of scope for the bundled stack.
- **Log aggregation (Loki).** Same situation: OTLP logs pipeline goes to
  stdout. Add Loki / Promtail if structured-log search is required.
- **Authentication on Prometheus / AlertManager.** Exposed without auth on
  the host (dev posture). Bind only to the docker network or front with a
  reverse proxy for any non-local deployment.
