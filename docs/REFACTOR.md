# Harness Status, Forward Plan, Hardening & Observability

This is the canonical engineering reference for the casdk-harness, consolidating
what used to live in three separate docs (REFACTOR.md, HARDENING.md, OBSERVABILITY.md).
Five sections, each independently useful:

1. **[Status](#1-status)** — what's shipped, current numbers, branch state.
2. **[Forward plan](#2-forward-plan)** — Stage 3 (Eval Harness) and beyond.
3. **[Hardening](#3-hardening)** — security + test-coverage priorities.
4. **[Observability](#4-observability)** — operator guide for the bundled stack.
5. **[Reference](#5-reference)** — Anthropic-canonical pointers, what-shipped log, verification rule. (SDK loading behavior reference moved to `CLAUDE.md`.)

---

## 1. Status

**As of 2026-05-07:**

- All four reorganization blocks (1, 2, 3, 4) merged to `main`.
- `main` and `contextgrad-eval` are equal (both at PR #5 merge `ece4269`); `contextgrad-eval` (renamed 2026-05-07 from `contextgrad-framework`) is reserved for forthcoming Stage 3 work.
- **Tests:** 1534 unit passing (51 files, 1379 distinct + parametrize), 41 integration tests across 21 files, 82 e2e tests across 5 files.
- **CGF Stages 1+2 shipped on `main`:** protocol layer, resource architect, DESIGN phase, MCP tool/server creation skills with Python+TypeScript scaffolds.
- **Multi-resource pipeline working end-to-end:** `PLANNING → RESEARCH → DESIGN → GENERATE → ITERATE → VALIDATE`.
- **Observability stack live:** OTel Collector → Prometheus, two pre-provisioned Grafana dashboards, AlertManager + 10 active alert rules.

| Stage | Status | Where |
|---|---|---|
| **Stage 1 — Protocol layer + resource architect + DESIGN phase** | shipped | `main`, via Block 1 |
| **Stage 2 — MCP tool/server creation skills + Python/TypeScript scaffolds** | shipped | `main`, via Block 1 |
| **Stage 3 — Evaluation Framework** | **not started** | `contextgrad-eval` |
| **Stage 4 — Integration & hardening** | not started; depends on Stage 3 | `contextgrad-eval` |

Two phases exist in the `OptimizationPhase` enum but are not yet wired into the
orchestrator: `EVAL_DESIGN` and `EXECUTION_EVAL` — those are Stage 3's job.

---

## 2. Forward plan

### Stage 3 — Eval Harness

Branch: `contextgrad-eval` (renamed 2026-05-07 from `contextgrad-framework`; equal to `main`).

**Canonical plan:** [`docs/CGF-EVAL-FRAMEWORK.md`](CGF-EVAL-FRAMEWORK.md) (v2, 2026-05-07). Four phases (A → D) ship independently, gated by runtime smoke + unit-test pass:

- **Phase A** — Comparison-aware in-process harness, two-arm eval (baseline vs candidate), simple-threshold promotion gate, `cgf-eval-architect` agent, three-tier graders (deterministic/trajectory/LLM-judge), wire `EVAL_DESIGN` and `EXECUTION_EVAL` into the orchestrator.
- **Phase B** — Bootstrap-CI promotion gate, token-regression check, trigger precision/recall, pairwise judge with position balancing.
- **Phase C** — Ephemeral container runtime (layered Dockerfile, `eval` compose profile, `make eval-*` targets) for SWE-bench-style determinism.
- **Phase D** — Calibration harness (Cohen's kappa per resource type × judge × rubric), judge ensemble fallback, `.github/workflows/eval.yml` CI on PR.

All open questions previously listed here (eval-suite format, sandbox isolation, grader composition, LLM-judge failure mode) are resolved in CGF-EVAL-FRAMEWORK.md § 0 "Key decisions".

### Stage 4 — Integration & hardening (post-Phase-D)

End-to-end pipeline tests across the new phases, checkpoint/resume across the
new phases, ACCEPT/REFINE/REJECT human-review gates surfacing in the orchestrator.
Detailed planning deferred until after Phase D ships — the shape of the human-review
UX depends on what calibration data tells us about which gates need human eyes.

### Independent forward TODOs

Two items unrelated to Stage 3 but worth addressing when bandwidth allows:

- **Sub-agent `HOME` mismatch** — when sub-agents (e.g., `research-team:research-specialist`) expand `~` in paths via Bash, it sometimes resolves to `/root` while the runtime user is `claude` (`$HOME=/home/claude`). The subsequent Write tool fails with `EACCES`. Three fix candidates queued; (a) explicit `HOME=/home/claude` env passthrough in `_build_sdk_options()` is the leading suspect.
- **`make interactive` terminal UX audit** — corrupted Rich panel borders, repeated "Thinking..." displays, verbose logs interleaved with conversation. Audit `harness/cli.py`, `harness/interactive.py`, possibly `harness/agent_progress.py`.

### Build improvements

Tier 1 + 2.3 + 2.4 from the 2026-05-07 build review shipped (see commit
`build(docker): drop redundant uv install...`). Two follow-up commits handled
the Playwright fallout:

1. **Browser channel correction.** `@playwright/mcp` defaults to `--browser=chrome`
   (Google Chrome stable), which has no Linux arm64 build — fails on Apple Silicon.
   We now install **chrome-for-testing** (Playwright's cross-platform CfT build,
   arm64 + amd64) via `npx @playwright/mcp install-browser chrome-for-testing`
   and pass `--browser chromium` in `.mcp.json` (which the MCP maps to CfT).
2. **Permissions per Microsoft's official Playwright Docker pattern.** Browsers
   are installed at `PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright` and the parent
   dir is `chmod -R 777` so non-root runtime users can create per-session
   profile dirs (`mcp-chrome-for-testing-XXX`). Browser binaries themselves stay
   root-owned (immutable, good for layer dedup). Verified end-to-end via
   JSON-RPC against the MCP server running as the `claude` user.
3. **`@playwright/mcp` pinned to `0.0.74`** in both build (`PLAYWRIGHT_MCP_VERSION`
   build arg) and runtime (`.mcp.json`). The earlier `@latest` caused two
   separate regressions over a 24-hour window when upstream defaults drifted.

The pieces below remain queued.

#### Image size — recommended next

- **Prune `/opt/ms-playwright/chromium-1223/`** if `chromium_headless_shell-1223` covers all use cases. The `install-browser chrome-for-testing` step installs both the full chromium binary (~620 MB) and the headless-shell variant (~333 MB). The MCP server in headless mode (default) likely only uses headless-shell. Verification spike: take a screenshot, render a page, run a console-error check — all with the full chromium dir removed via `RUN rm -rf /opt/ms-playwright/chromium-1223` after install. If everything passes, ~620 MB drops out of the image. *Effort: ~1h with smoke tests.*
- **Drop CJK + emoji fonts** pulled in by `playwright install-deps`. The deps macro installs `fonts-ipafont-gothic` (3.5 MB), `fonts-noto-color-emoji` (10.1 MB), `fonts-wqy-zenhei` (7.5 MB), `fonts-freefont-ttf` (5.3 MB) — useful only if rendering pages with Asian scripts or emoji. Skipping `install-deps` and curating system libs explicitly saves ~25 MiB. Tradeoff: full-page screenshots of CJK-heavy pages will use fallback fonts. *Effort: ~2h, includes a curated apt list.*

#### Build infrastructure

- **GHCR registry push cache.** `docker-compose.prod.yml` has `cache_to: type=registry,ref=${REGISTRY}/main:cache,mode=max` configured but it requires authenticated `docker login ghcr.io` to actually push. The dev compose's anonymous `cache_from` was removed in the Tier 1 commit because the cache image either didn't exist or wasn't world-readable. To re-enable cross-environment cache sharing: (a) confirm a CI job actually pushes the cache image, (b) make the cache image public on GHCR, (c) restore `cache_from` in dev compose. Until then, every fresh checkout pays the full cold-build cost. *Effort: ~3h including CI wiring.*
- **Restructure `deps` stage for finer cache invalidation.** Currently `COPY src/` precedes `uv pip install --system -e .`, so any `src/` edit busts the deps install. Splitting into two installs (`uv pip install --system -r <(uv pip compile pyproject.toml)` for third-party deps first, then `uv pip install --system -e . --no-deps` after `COPY src/`) saves ~2-3s per src-only rebuild. Pattern is well-known but requires sequencing care. *Effort: ~2h.*

#### Larger spikes (do separately)

- **Bump `PYTHON_VERSION=3.13`** in the Dockerfile + `pyproject.toml` `requires-python` + `mypy` config. 3.13 has measurable interpreter perf wins (~10-15% on some workloads) and shorter startup. Risk: needs verification that `claude-agent-sdk`, `mcp`, `pydantic-core`, `cryptography`, `aiohttp`, `uvloop` all ship arm64 wheels for 3.13 (most do as of early 2026). Required: `make build && make test-unit && make test-integration` clean. *Effort: ~3h.*
- **Bump `glab` from v1.46.1** (Sept 2024) to current (~v1.50+). Pin update only, low risk. Bundle with the next dependency-refresh pass. *Effort: ~30min.*

#### Considered and rejected

- **`python:3.12-alpine`** instead of `python:3.12-slim`. Many native wheels (`pydantic-core`, `cryptography`, `uvloop`, `aiohttp`) need musl rebuilds or aren't available. Almost certainly net-negative. Skip.
- **Move `npx playwright install` into `base` stage** to share across variants. Negative: would bloat the production image with browser binaries it doesn't use. Skip.
- **Combine `tini` install into a non-`gh` apt step.** Already done in the Tier 1 commit alongside the `gh` install — single combined apt step now handles both.

---

## 3. Hardening

Security + test-coverage prioritization. Items below are the open work; resolved
items are listed at the end of this section for reference.

### Priority summary (open items)

| Priority | Open items | Effort estimate |
|----------|-----------|-----------------|
| **P0 Critical** | 3 | ~20h |
| **P1 High** | 2 | ~6h |
| **P2 Medium** | 6 | ~16h |
| **P3 Low** | 4 | ~11h |
| **Test gaps** (P1) | 3 modules | ~12h |

### P0 — Critical (block release)

#### CRIT-01: Plaintext checkpoint data
- **CVSS:** 9.1 | **Location:** `src/harness/checkpoint.py` (567 LOC) | **Effort:** ~8h
- Checkpoints store complete agent state in plaintext JSON, including conversation history (may contain API keys / passwords), workspace snapshots, and session tokens.
- **Impact:** PII exposure, credential leakage, GDPR/HIPAA violations.
- **Remediation:** AES-256-GCM encryption + HMAC-SHA256 integrity, keys in vault (KMS/HashiCorp Vault), 30-day key rotation. Sanitization layer (`sanitize_sensitive_data()` in `security.py`) is already applied but is not a substitute for encryption.

#### CRIT-02: SSH private keys in containers
- **CVSS:** 8.8 | **Location:** `docker-compose.yml` lines 69-70, 149-150, 220-221 | **Effort:** ~4h
- SSH private keys mounted into all three agent containers (`./.ssh:/home/claude/.ssh:ro`). Compromised container = stolen credentials.
- **Impact:** Repository access, lateral movement, supply-chain attack.
- **Remediation:** Replace with ephemeral GitHub/GitLab PATs via git credential helper (24h expiry). Drop the SSH bind mounts. Move to container-level secret injection.

#### God-object refactor — `agent.py`
- **Location:** `src/harness/agent.py` (1603 LOC) | **Effort:** ~8h
- `AgentSession` still owns 9+ responsibilities. Block 3 split out the plugin pipeline (`plugin_manager.py` 637 → 182 LoC) but the rest of the decomposition is open.
- **Proposed structure:**
  ```
  AgentSession        ~300 LOC   session lifecycle + dispatch
  ├── MCPServerManager ~200 LOC  MCP discovery + lifecycle
  ├── SessionManager   ~150 LOC  state transitions
  ├── CheckpointManager        already separate (567 LOC, see CRIT-01)
  └── MetricsCollector         already separate (499 LOC, post-Block-4 trim)
  ```
- **Note:** `multi_resource_orchestrator.py` (2157 LOC) and `autonomous.py` (1618 LOC) are now the largest files in the tree. They're candidates for the same treatment in a future pass.

### P1 — High (fix before beta testing)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Missing rate limiting | 7.5 | `src/harness/autonomous.py` (1618 LOC, no rate-limit primitives) | 4h |
| Redis password in env vars | 7.0 | `.env.example` | 2h |

#### Test coverage gaps (P1)

| Module | LOC | Tests | Status |
|--------|-----|-------|--------|
| `optimization/api.py` | 421 | **0** | Public API still untested |
| `optimization/cli/section_optimize.py` | ~300 | 0 | Entry point untested |
| `cli.py` (Rich UI formatting) | 581 | partial | Linked to interactive UX audit (Section 2) |

Closed since the previous HARDENING revision: `optimization/orchestrator.py` (511 LOC) has 8 tests in `test_orchestrator_design_phase.py`; `optimization/multi_resource_orchestrator.py` (2157 LOC) has 43 tests in `test_multi_resource_orchestrator.py`; `optimizers/agentic_optimizer.py` is exercised by 30 tests in `test_optimizers.py`; `pipeline` has 12 tests.

### P2 — Medium

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Security headers missing | 6.5 | `docker-compose.prod.yml` | 3h |
| Docker socket exposure | 9.0 | `mcp_servers/docker` | 4h |
| Checkpoint cleanup race | — | `checkpoint.py` | 2h |
| Error message sanitization | 5.0 | `agent.py` (~lines 600-630 area) | 2h |
| Dependency vulnerability scanning | 5.5 | `pyproject.toml` (no `.github/workflows/` yet) | 2h |
| Cost budget enforcement | 4.0 | `monitoring.py` cost path | 3h |

### P3 — Low

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Memory graph encryption | 5.0 | `mcp_servers/memory` | 4h |
| Container image signing | 5.0 | Build pipeline | 3h |
| Redis stream ACLs | 4.5 | `messaging.py` | 3h |
| Test workspace isolation | 6.0 | `docker-compose.yml` | 1h |

### Recently resolved

| Item | CVSS | Resolution |
|-------|------|------------|
| ~~CRIT-03: Log sanitization~~ | 7.5 | `sanitize_sensitive_data()` in `security.py`, applied to prompt storage |
| ~~HIGH-04: Bash bypass flag (`--allow-all-commands`)~~ | 8.8 | Flag removed entirely; verified absent from `src/` |
| ~~P2: Session timeout~~ | 5.3 | `_check_session_timeout()` enforces `claude_session_timeout` |
| ~~P3: Default passwords~~ | 3.0 | All `.env.example` defaults use `CHANGE_ME_BEFORE_PRODUCTION` placeholders |
| ~~P3: Metrics auth~~ | 3.5 | Optional basic auth via `METRICS_AUTH_TOKEN` |
| ~~Plugin SDK Workaround (`agent.py:64-72`)~~ | — | Removed in Block 3 follow-up `d8571b2`; `_register_agents` / `agents=sdk_agents` workaround was redundant once plugin manifests passed `claude plugin validate` |

---

## 4. Observability

The harness ships a self-contained observability stack: native OpenTelemetry signals
from the Claude Code CLI flow through a sidecar OTel Collector into Prometheus,
where they power two pre-provisioned Grafana dashboards and AlertManager-delivered
alerting rules.

### Architecture

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

1. **Native SDK telemetry (`claude_code_*` namespace)** — emitted by the Claude Code CLI when `CLAUDE_CODE_ENABLE_TELEMETRY=1` and the OTLP exporter envvars are set (compose hardcodes both — see `docker-compose.yml`). The collector receives OTLP on `:4317` (gRPC) or `:4318` (HTTP) and re-exposes on `:8889` for Prometheus.
2. **Harness instruments (`harness_*` and `cgf_*` namespaces)** — `prometheus_client` counters/gauges/histograms inside `src/harness/monitoring.py`, scraped from each agent container's `:9090` (host-mapped to `:9091`+).

### Service map

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

### Dashboards

Two dashboards are auto-provisioned via `config/monitoring/dashboards/dashboard-provider.yml`.
Files are watched with `updateIntervalSeconds: 10`, so editing the JSON on disk
propagates without a Grafana restart.

#### Overview (`/d/casdk-overview`)

Single-pane dashboard for day-to-day use. Five rows:

| Row | Panels |
|---|---|
| Session Health | Active sessions, sessions started (1h), prompts (1h), tokens (1h), cost (1h), cache hit ratio |
| Tokens & Cost | Tokens/min by model+query_source, cost/hour by model, token type mix (stacked), cumulative cost, cost per session, top models |
| Tools & Messages | Top tools, tool error rate, message type distribution, agent request rate by status |
| Latency | Agent request duration p50/p95/p99, session duration heatmap |
| System (collapsed) | Checkpoint size, workspace files, memory usage by component |

#### CGF (`/d/casdk-cgf`)

CGF optimization framework activity:

| Row | Panels |
|---|---|
| Tracer Activity | Spans collected/exported (selected range), adapter transform success rate, mean composite reward, spans-by-kind, spans-by-exporter |
| Optimization Quality | Composite reward distribution heatmap, feedback dimensions (per resource_type/dimension), adapter transforms by status |
| Future (collapsed) | Stage 3 eval-harness placeholder — populated when phase-transition + per-iteration eval metrics land |

### Adding a new alert rule

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

### First-response actions

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

### Adding a real receiver

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

### Testing alert delivery

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

### Why bundled, not external?

The harness deliberately routes its own telemetry to the bundled collector
rather than inheriting host-shell OTel envvars (which a developer's Claude Code
configuration commonly sets to a personal/corporate collector). That isolation
is hardcoded in `docker-compose.yml`; to redirect to an external collector for
production, edit the `OTEL_EXPORTER_OTLP_ENDPOINT` value directly or use a
docker-compose override file.

### What's not bundled

- **Tracing UI (Tempo / Jaeger).** The collector receives OTLP traces and ships them to a debug exporter (stdout). Add a Tempo backend if you need span querying — out of scope for the bundled stack.
- **Log aggregation (Loki).** Same situation: OTLP logs pipeline goes to stdout. Add Loki / Promtail if structured-log search is required.
- **Authentication on Prometheus / AlertManager.** Exposed without auth on the host (dev posture). Bind only to the docker network or front with a reverse proxy for any non-local deployment.

---

## 5. Reference

### Anthropic-canonical references

Two published Anthropic implementations match this harness's shape and remain
useful as design north stars:

- **`anthropics/claude-agent-sdk-demos/research-agent`** — closest analog for programmatic resource loading. Uses `ClaudeAgentOptions(setting_sources=["project"], agents={...}, hooks={...})` directly with no custom plugin loader.
- **`anthropics/claude-cookbooks/claude_agent_sdk/chief_of_staff_agent`** — closest analog for filesystem-based discovery. Uses `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, `.claude/output-styles/` directly.

Plugin distribution follows `anthropics/claude-plugins-official` and
`anthropics/skills` (both ship `.claude-plugin/marketplace.json`). Hosting
patterns follow the [Anthropic Hosting Guide](https://code.claude.com/docs/en/agent-sdk/hosting).

**Future-state option:** Anthropic's overview suggests prototyping with the
Agent SDK and migrating to [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview)
for long-running asynchronous sessions. Not a near-term migration, but worth
keeping in mind as the harness scales beyond what self-hosted infra can support.

### What shipped — Block log

Execution happened in four "Blocks." Phase-level detail lives in the no-squash
commit messages on each promotion PR.

| Block | Date | Scope | Promotion |
|---|---|---|---|
| **Block 1** | 2026-05-01/02 | Branch reorganization: 73 commits of Stage 1+2 CGF work + multi-resource pipeline promoted from `contextgrad-framework` to `main`; branch reset off the new main. | [PR #1](https://github.com/andisab/casdk-harness/pull/1) |
| **Block 2** | 2026-05-04 | SDK bump (`>=0.1.72`); filesystem agent discovery via `.claude/agents/`; hook event SDK-canonical names; `direct_agent.py` → `subagent.py` rename + slim. | [PR #2](https://github.com/andisab/casdk-harness/pull/2) |
| **Block 3** | 2026-05-04/05 | Plugin pipeline modernization: marketplace adoption (research-team, context-engineering); `plugin_manager.py` collapsed 637 → 182 LoC; `commands.py` and `hooks.py` deleted; SDK upstream investigation closed (no issues filed). | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |
| **Block 4** | 2026-05-05 | Observability: OTel Collector sidecar bridging SDK telemetry into Prometheus; harness metrics renamed `harness_*`; SDK-duplicate counters dropped; two pre-provisioned Grafana dashboards; AlertManager + alert rules wired (rules had been dead since project start). | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |

Block 3 and Block 4 shipped together in PR #3 because both were authored on
`contextgrad-framework` after Block 2's promotion. Two follow-up doc-only PRs
(#4, #5) refreshed `docs/REFACTOR.md` and `CLAUDE.md` to match the new state.

For phase-level detail, see commit messages on the promotion PRs and CLAUDE.md
"Completed Recently" section.

### SDK loading behavior

Verified findings on how the SDK loads plugin resources, plus regression
probes (`scripts/derisk_plugin_loading.py`, `scripts/derisk_slash_init.py`),
live in [`CLAUDE.md` § Verified SDK Loading Behavior](../CLAUDE.md#verified-sdk-loading-behavior-2026-05-05).
That's the canonical reference for sessions debugging plugin-loading or
slash-command behavior. This doc no longer carries the bisection record.

### Verification rule (still binding for Stage 3)

**Tests pass ≠ feature works.** Plugin/agent loading silently degrades in
ways unit tests do not catch (path mismatches, namespace collisions, swallowed
discovery exceptions). Every Stage 3 phase boundary must end with a *runtime*
smoke test, and the user must do their own confirmation run before any phase
is declared complete.

Required at every phase boundary:

1. **Run the full test suite and report actual numbers** — `make test-unit && make test-integration`, not "tests pass." Include passed/failed/skipped counts.
2. **Boot the harness and inspect the runtime registry** — capture the actual values of `discovered_skills`, `agents`, `plugins`. Names, not just counts.
3. **Invoke at least one resource end-to-end** for any change that touches loading. Confirm the actual response, not just that the call returned.
4. **Stop and ask the user to do their own verification run** before declaring any phase complete.
