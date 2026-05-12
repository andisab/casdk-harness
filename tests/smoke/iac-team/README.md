# Smoke fixture: iac-team (multi-resource)

Plugin-scale multi-resource fixture for Infrastructure-as-Code
automation. Drives the **full Phase A pipeline** end-to-end:
RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE →
EXECUTION_EVAL → VALIDATE → COMPLETE.

## What this fixture exercises

- **`multi_resource_orchestrator`** end-to-end (the canonical Phase A code path)
- **`cgf-eval-architect`** — designs `eval-suite.yaml` covering 21 resources
- **`EvalHarness`** — two-arm baseline-vs-candidate comparison per resource
- **Promotion gate** — simple-threshold (Phase A); refinement loop-back
  on regression
- **Telemetry** — all five `harness_eval_*` Prometheus instruments,
  populated dashboard panels, OTel tracer spans
- **Cross-resource coherence** — `cgf-coherence-validator` on a plugin
  with 21 inter-referenced resources

## Resources (18 baseline files)

| Type | Count | Names |
|---|---|---|
| Agents | 3 | iac-analyzer, iac-generator, iac-validator |
| Commands | 1 | iac |
| Skills | 14 | aws-cli, aws-eks, container-analysis, crossplane, github-actions, gitlab-ci, gitops-argocd, gitops-flux, helm-charts, kubernetes-native, pulumi-cdk, repo-analysis, security-validation, terraform-modules |

> **Note (2026-05-11):** GCP skills (`gcloud-cli`, `gcp-gke`) were
> removed from the SPEC to scope eval graders to a single
> locally-provisionable infrastructure stack. The skills directory
> count therefore dropped from 17 → 14; total resources from 21 → 18.

The skills are non-trivial — some include `examples/` and `templates/`
subdirectories with YAML/JSON snippets. The optimizer must preserve
these auxiliary files; only `SKILL.md` and the markdown agent/command
files get versioned.

## PASS criteria

A run is PASS when:

1. **Phase A artifacts exist**:
   - `eval/eval-suite.yaml` (validates against `eval_suite.schema.json`)
   - `eval/execution-eval-round-1.json` (aggregate per-arm results)
   - `eval/transcripts/baseline/` and `eval/transcripts/candidate/` populated
   - Per-resource `eval/results/{resource}-v1/eval-results.json`
2. **All 18 resources advanced** — every resource has either
   `status: "optimized"` or `status: "needs_refinement"` in
   `optimization-state.json`; none with `status: "failed"`
3. **State machine reached COMPLETE**:
   `optimization-state.json.current_phase == "COMPLETE"`
4. **Telemetry visible** in Prometheus:
   - `harness_eval_phase_duration_seconds_count` has series for EACH of
     `RESEARCH`, `DESIGN`, `QA`, `GENERATE`, `EVAL_DESIGN`, `ITERATE`,
     `EXECUTION_EVAL`, `VALIDATE`
   - `harness_eval_scenarios_total` non-empty (split by `level`, `status`, `arm`)
   - `harness_eval_arm_score_count` non-empty for both `baseline` and `candidate`
5. **Grafana CGF dashboard** Phase A panels render data (visual check)
6. **Promotion-loop coverage** (lifecycle PASS) — at least one resource
   should hit either a successful PROMOTE *or* a feedback-loop-back to
   ITERATE. If every resource short-circuits to "no eval data", that's
   a regression of one of the Phase A fixes.

## Run

From the repo root:

```bash
make smoke FIXTURE=iac-team
```

This copies the fixture into `workspace/iac-team/` (overwriting any
prior contents) and runs the multi-resource orchestrator against it.

## Cost

Typical run cost: **$3 – $8** with sonnet for design and opus for
judge. 21 resources × research + design + generation + 1-3 iteration
rounds + two-arm eval per resource is a real workload.

Set `CGF_DESIGN_MODEL=haiku` and `CGF_JUDGE_MODEL=haiku` in `.env` to
cut cost roughly 5-10× at the price of noisier verdicts (still
acceptable for harness smoke purposes).

## Source of the baseline

`SPEC.md` and the 21 resource files are copied from
`workspace/iac-team-v3/` as of 2026-05-11. That workspace had been
optimized two rounds already; the smoke fixture uses the ORIGINAL
unversioned files (`agents/iac-analyzer.md` etc. — not `-v1.md` or
`-v2.md`) as the v0 baseline.

The CHANGELOG.md from the prior optimization runs is NOT copied — we
want a fresh history each smoke run.

## Known caveats

- Skill subdirectories (`examples/`, `templates/`) are baseline support
  files only. The optimizer should leave them alone. If a smoke run
  ends with modifications to those files, that's a defect worth
  investigating (the optimizer scope is the markdown files only).
- IaC is a domain where deterministic graders shine: outputs can be
  validated with `terraform validate`, `helm lint`, `kubectl --dry-run`.
  The eval-architect should pick up on this; if it falls back to
  llm_judge for everything, that's a prompt-tuning opportunity.
